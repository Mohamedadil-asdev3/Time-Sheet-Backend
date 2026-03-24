# views.py
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.utils.timezone import localtime
from .models import TaskList, TaskListAuditLog
from .serializers import TaskListSerializer, TaskListAuditLogSerializer
from master.models import Status
from isoweek import Week
from django.contrib.auth import get_user_model
from django.db.models import Count, Q,Sum
from datetime import datetime, timedelta, date
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from collections import defaultdict
User = get_user_model()

class IsOwnerOrStaffApprover(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        if obj.user == request.user:
            return True

        # Only staff (admin) can access/approve/edit non-owned tasks
        return request.user.is_staff


class TaskListAPIView(APIView):
    serializer_class = TaskListSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        if self.request.method in ['PUT', 'DELETE']:
            return [IsOwnerOrStaffApprover()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        queryset = TaskList.objects.select_related(
            'platform', 'task', 'subtask', 'status',
            'l1_approver', 'l2_approver', 'last_modified_by'
        ).order_by('-date', 'task__name')

        if not user.is_staff:
            queryset = queryset.filter(user=user)

        return queryset

    # def get_object(self, pk):
    #     task = get_object_or_404(TaskList, pk=pk)
    #     if task.user != self.request.user and not self.request.user.is_staff:
    #         raise PermissionDenied("You don't have permission to access this task.")
    #     return task
    def get_object(self, pk):
        task = get_object_or_404(TaskList, pk=pk)
        user = self.request.user

        if not (
            task.user == user or
            task.l1_approver_id == user.id or
            task.l2_approver_id == user.id or
            user.is_staff
        ):
            raise PermissionDenied("You don't have permission to access this task.")

        return task

    def _create_audit_log(self, task, action, old_values=None, new_values=None, remarks=None):
        TaskListAuditLog.objects.create(
            task=task,
            action=action,
            performed_by=self.request.user,
            old_values=old_values or {},
            new_values=new_values or {},
            remarks=remarks or '',
            ip_address=self._get_client_ip(self.request),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    def apply_filters(self, request, queryset):
        params = request.query_params
        if params.get('user_id') and request.user.is_staff:
            queryset = queryset.filter(user_id=params['user_id'])
        if params.get('start_date'):
            queryset = queryset.filter(date__gte=params['start_date'])
        if params.get('end_date'):
            queryset = queryset.filter(date__lte=params['end_date'])
        if params.get('platform'):
            queryset = queryset.filter(platform_id=params['platform'])
        if params.get('task'):
            queryset = queryset.filter(task_id=params['task'])
        if params.get('status'):
            queryset = queryset.filter(status_id=params['status'])
        if search := params.get('search'):
            queryset = queryset.filter(
                Q(description__icontains=search) |
                Q(bitrix_id__icontains=search) |
                Q(task__name__icontains=search) |
                Q(subtask__name__icontains=search) |
                Q(user__username__icontains=search)
            )
        return queryset

    def get(self, request, pk=None):
        if pk:
            task = self.get_object(pk)
            return Response(self.serializer_class(task).data)

        qs = self.get_queryset()
        qs = self.apply_filters(request, qs)
        return Response(self.serializer_class(qs, many=True).data)

    def post(self, request):
        if request.user.is_staff:
            return Response(
                {"error": "Staff users cannot create tasks"},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data
        is_bulk = isinstance(data, list)

        serializer = self.serializer_class(
            data=data,
            many=is_bulk,
            context={'request': request}
        )

        if not serializer.is_valid():
            print("Create errors:", serializer.errors)
            return Response(serializer.errors, status=400)

        tasks = serializer.save()

        for task in (tasks if is_bulk else [tasks]):
            if task.user.first_level_manager:
                task.l1_approver = task.user.first_level_manager
            if task.user.second_level_manager:
                task.l2_approver = task.user.second_level_manager

            task.save()
            self._create_audit_log(
                task=task,
                action='CREATE',
                new_values=self.serializer_class(task).data,
                remarks="Bulk task created" if is_bulk else "Task created"
            )

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        task = self.get_object(pk)
        user = request.user
        action = request.data.get('action') 
        status_lower = (task.status.name or '').lower().strip() if task.status else ''

        # Capture old values
        old_values = {
            'status': task.status.name if task.status else None,
            'duration': str(task.duration) if task.duration is not None else None,
            'description': task.description or "",
            'bitrix_id': task.bitrix_id or "",
            'l1_approver_id': task.l1_approver_id,
            'l2_approver_id': task.l2_approver_id,
            'l1_approved_at': task.l1_approved_at.isoformat() if task.l1_approved_at else None,
            'l2_approved_at': task.l2_approved_at.isoformat() if task.l2_approved_at else None,
        }

        serializer = self.serializer_class(
            task,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        # Status objects
        in_progress = Status.objects.filter(name__iexact='In Progress').first() or \
                    Status.objects.filter(name__iexact='inprogress').first()
        completed = Status.objects.filter(name__iexact='Completed').first() or \
                    Status.objects.filter(name__iexact='Done').first()
        rejected = Status.objects.filter(name__iexact='Rejected').first()
        draft = Status.objects.filter(name__iexact='Draft').first()

        # ----------------- L1 Approve -----------------
        if action == 'L1_APPROVE' and in_progress:
            if not task.l1_approver or task.l1_approver != user:
                return Response({"error": "Only assigned L1 approver can approve"}, status=403)

            serializer.validated_data['l1_approver'] = user
            serializer.validated_data['l1_approved_at'] = timezone.now()
            if task.user.second_level_manager:
                serializer.validated_data['l2_approver'] = task.user.second_level_manager
            if status_lower == 'draft':
                serializer.validated_data['status'] = in_progress

        # ----------------- L2 Approve -----------------
        if action == 'L2_APPROVE' and completed:
            if not task.l2_approver or task.l2_approver != user:
                return Response({"error": "Only assigned L2 approver can approve"}, status=403)

            serializer.validated_data['l2_approver'] = user
            serializer.validated_data['l2_approved_at'] = timezone.now()
            serializer.validated_data['status'] = completed


        if action == 'SUBMIT' and in_progress:

            if task.user != user:
                return Response({"error": "Only task owner can submit"}, status=403)

            if not task.user.first_level_manager:
                return Response({"error": "No reporting manager assigned"}, status=400)

            serializer.validated_data['status'] = in_progress
            serializer.validated_data['l1_approver'] = task.user.first_level_manager

        # ----------------- L1 Reject -----------------
        if action == 'L1_REJECT' and rejected:
            serializer.validated_data['status'] = rejected
            serializer.validated_data['l1_rejected_at'] = timezone.now()
      

        # ----------------- L2 Reject -----------------
        if action == 'L2_REJECT' and rejected:
            serializer.validated_data['status'] = rejected
            serializer.validated_data['l2_rejected_at'] = timezone.now()
   

        # ----------------- Resubmit by Owner -----------------
        if action == 'RESUBMIT' and in_progress:
            if task.user != user:
                return Response({"error": "Only task owner can resubmit"}, status=403)

            serializer.validated_data['status'] = in_progress
            serializer.validated_data['l1_approved_at'] = None
            serializer.validated_data['l2_approved_at'] = None
            serializer.validated_data['l1_approver'] = task.user.first_level_manager
            serializer.validated_data['l2_approver'] = task.user.second_level_manager

        # ----------------- Last Modified -----------------
        serializer.validated_data['last_modified_by'] = user
        updated_task = serializer.save()
        new_values = {
            'status': updated_task.status.name if updated_task.status else None,
            'duration': str(updated_task.duration) if updated_task.duration is not None else None,
            'description': updated_task.description or "",
            'bitrix_id': updated_task.bitrix_id or "",
            'l1_approver_id': updated_task.l1_approver_id,
            'l2_approver_id': updated_task.l2_approver_id,
            'l1_approved_at': updated_task.l1_approved_at.isoformat() if updated_task.l1_approved_at else None,
            'l2_approved_at': updated_task.l2_approved_at.isoformat() if updated_task.l2_approved_at else None,
        }

        log_action = action if action in ['L1_APPROVE', 'L2_APPROVE', 'L1_REJECT', 'L2_REJECT', 'RESUBMIT'] else 'UPDATE'
        remarks = request.data.get('remarks', f"Task {log_action.lower()}d")
        self._create_audit_log(
            task=updated_task,
            action=log_action,
            old_values=old_values,
            new_values=new_values,
            remarks=remarks
        )

        return Response(serializer.data)

    def delete(self, request, pk):
        task = self.get_object(pk)
        status_name = (task.status.name or '').lower().strip() if task.status else ''
        if task.user != request.user or status_name != 'draft':
            return Response({"error": "Only owner can delete draft tasks"}, status=403)

        self._create_audit_log(
            task=task,
            action='DELETE',
            old_values={'id': task.id, 'task_name': task.task.name if task.task else None},
            remarks="Deleted by owner"
        )
        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TaskApprovalAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # ------------------- PENDING -------------------
        pending_tasks = TaskList.objects.filter(
            Q(
                l1_approver=user,
                l1_approved_at__isnull=True,
                l1_rejected_at__isnull=True
            ) |
            Q(
                l2_approver=user,
                l1_approved_at__isnull=False,
                l2_approved_at__isnull=True,
                l2_rejected_at__isnull=True
            )
        )

        # ------------------- APPROVED -------------------
        approved_tasks = TaskList.objects.filter(
            Q(l1_approver=user, l1_approved_at__isnull=False) |
            Q(l2_approver=user, l2_approved_at__isnull=False)
        )

        # ------------------- REJECTED -------------------
        rejected_tasks = TaskList.objects.filter(
            Q(l1_approver=user, l1_rejected_at__isnull=False) |
            Q(l2_approver=user, l2_rejected_at__isnull=False)
        )

        data = {
            "pending_count": pending_tasks.count(),
            "approved_count": approved_tasks.count(),
            "rejected_count": rejected_tasks.count(),

            "pending_tasks": TaskListSerializer(pending_tasks, many=True).data,
            "approved_tasks": TaskListSerializer(approved_tasks, many=True).data,
            "rejected_tasks": TaskListSerializer(rejected_tasks, many=True).data,
        }

        return Response(data)

class TaskListAuditLogAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id=None):
        if task_id:
            task = get_object_or_404(TaskList, pk=task_id)
            if task.user != request.user and not request.user.is_staff:
                raise PermissionDenied()
            logs = TaskListAuditLog.objects.filter(task=task).order_by('-created_at')
        else:
            if request.user.is_staff:
                logs = TaskListAuditLog.objects.all().order_by('-created_at')
            else:
                logs = TaskListAuditLog.objects.filter(task__user=request.user).order_by('-created_at')

        serializer = TaskListAuditLogSerializer(logs, many=True)
        return Response(serializer.data)



class SimpleTimeLogView(APIView):
    """
    GET /api/simple-time-logs/          → list (all if staff, own only if normal user)
    GET /api/simple-time-logs/<id>/     → single record (with permission check)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        user = request.user
        tz = timezone.get_current_timezone()

        # ────────────────────────────────────────────────
        #  SINGLE RECORD (when pk is provided)
        # ────────────────────────────────────────────────
        if pk:
            task = get_object_or_404(TaskList, pk=pk)

            # Permission: only owner or staff can see this record
            if task.user != user and not user.is_staff:
                return Response(
                    {"error": "You do not have permission to view this record"},
                    status=status.HTTP_403_FORBIDDEN
                )

            created = task.created_at.astimezone(tz) if task.created_at else None
            updated = task.updated_at.astimezone(tz) if task.updated_at else None

            data = {
                "date": task.date.isoformat() if task.date else None,
                "platform_name": task.platform.name if task.platform else None,
                "task_name": task.task.name if task.task else None,
                "subtask_name": task.subtask.name if task.subtask else None,
                "bitrix_id": task.bitrix_id or None,
                "duration_hours": f"{float(task.duration):.2f}" if task.duration is not None else None,
                "created_time": created.strftime("%I:%M:%S %p") if created else None,
                "updated_time": updated.strftime("%I:%M:%S %p") if updated else None,
            }

            return Response({
                "status": "success",
                "data": data
            })

        # ────────────────────────────────────────────────
        #  LIST OF RECORDS
        # ────────────────────────────────────────────────
        queryset = TaskList.objects.select_related(
            'platform', 'task', 'subtask'
        ).order_by('-date', '-created_at')

        # ──── This is the key logic you asked for ────
        if user.is_staff:
            # Staff → see ALL records (no filter)
            pass
        else:
            # Normal user → see ONLY own records
            queryset = queryset.filter(user=user)

        # Apply filters from query params (same as before)
        params = request.query_params

        if params.get('start_date'):
            queryset = queryset.filter(date__gte=params['start_date'])
        if params.get('end_date'):
            queryset = queryset.filter(date__lte=params['end_date'])
        if params.get('platform'):
            queryset = queryset.filter(platform_id=params['platform'])
        if params.get('task'):
            queryset = queryset.filter(task_id=params['task'])
        if params.get('status'):
            queryset = queryset.filter(status_id=params['status'])
        if search := params.get('search'):
            queryset = queryset.filter(
                Q(description__icontains=search) |
                Q(bitrix_id__icontains=search) |
                Q(task__name__icontains=search) |
                Q(subtask__name__icontains=search)
            )

        # Extra: staff can also filter by specific user if they want
        if user.is_staff and (uid := params.get('user_id')):
            queryset = queryset.filter(user_id=uid)

        # Prepare response data
        result = []
        for task in queryset:
            created = task.created_at.astimezone(tz) if task.created_at else None
            updated = task.updated_at.astimezone(tz) if task.updated_at else None

            item = {
                "date": task.date.isoformat() if task.date else None,
                "platform_name": task.platform.name if task.platform else None,
                "task_name": task.task.name if task.task else None,
                "subtask_name": task.subtask.name if task.subtask else None,
                "bitrix_id": task.bitrix_id or None,
                "duration_hours": f"{float(task.duration):.2f}" if task.duration is not None else None,
                "created_time": created.strftime("%I:%M:%S %p") if created else None,
                "updated_time": updated.strftime("%I:%M:%S %p") if updated else None,
            }
            result.append(item)

        return Response({
            "status": "success",
            "count": len(result),
            "data": result
        })
        
        
# Task Status Overview

class TimeLogStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()

        # ─── Period selection ───────────────────────────────────────
        period = request.query_params.get('period', 'daily').lower()

        if period not in ['daily', 'weekly', 'monthly']:
            return Response({"error": "Invalid period. Use: daily, weekly, monthly"}, status=400)

        # ─── Base queryset ──────────────────────────────────────────
        qs = TaskList.objects.all()

        if not user.is_staff:
            qs = qs.filter(user=user)

        # ─── Date filtering based on period ─────────────────────────
        start_date = None
        end_date = today

        if period == 'daily':
            start_date = today
            title_range = today.isoformat()

        elif period == 'weekly':
            # Monday to Sunday (ISO week)
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
            title_range = f"{start_date.isoformat()} to {end_date.isoformat()}"

        elif period == 'monthly':
            year = int(request.query_params.get('year', today.year))
            month = int(request.query_params.get('month', today.month))
            start_date = datetime(year, month, 1).date()
            # Last day of month
            next_month = start_date + relativedelta(months=1)
            end_date = (next_month - timedelta(days=1)).date()
            title_range = f"{start_date.isoformat()} to {end_date.isoformat()}"

        # Apply date filter
        if start_date:
            qs = qs.filter(date__range=[start_date, end_date])

        # ─── Get status counts ──────────────────────────────────────
        status_counts = qs.values(
            'status__name'
        ).annotate(
            count=Count('id')
        ).order_by('status__name')

        total = sum(item['count'] for item in status_counts)

        # ─── Build result ───────────────────────────────────────────
        result = []
        for row in status_counts:
            name = row['status__name'] or 'Unknown'
            count = row['count']
            percentage = round((count / total * 100), 2) if total > 0 else 0.0

            result.append({
                "status_name": name,
                "count": count,
                "percentage": percentage
            })

        # Sort by count descending (most common first)
        result.sort(key=lambda x: x['count'], reverse=True)

        return Response({
            "period": period,
            "date_range": title_range,
            "total_count": total,
            "statuses": result
        })
        
# Work Hours Overview
class WorkHoursOverviewAPIView(APIView):
    """
    Work hours overview API
    
    Supported views:
    • ?view=week          → current week (Mon–Sun)
    • ?view=week&year=2026&week=6   → specific week
    • ?view=year          → current year (all 12 months summary)
    • ?view=year&year=2026   → specific year (all 12 months)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()

        view_mode = request.query_params.get('view', 'week').lower()

        if view_mode not in ['week', 'year']:
            return Response(
                {"error": "Invalid view parameter. Use ?view=week or ?view=year"},
                status=status.HTTP_400_BAD_REQUEST
            )

        year = int(request.query_params.get('year', today.year))

        # ────────────────────────────────────────────────
        # WEEK VIEW
        # ────────────────────────────────────────────────
        if view_mode == 'week':
            week_input = request.query_params.get('week')

            if week_input:
                if '-W' in week_input:
                    try:
                        y, w = week_input.split('-W')
                        year = int(y)
                        week_num = int(w)
                    except Exception:
                        return Response({"error": "Invalid week format (use YYYY-WWW)"}, status=400)
                else:
                    try:
                        week_num = int(week_input)
                    except Exception:
                        return Response({"error": "Invalid week number"}, status=400)
            else:
                # current week
                _, week_num, _ = today.isocalendar()

            # Calculate Monday of target week
            jan4 = date(year, 1, 4)
            monday_week1 = jan4 - timedelta(days=jan4.weekday())
            start_date = monday_week1 + timedelta(weeks=week_num - 1)
            end_date = start_date + timedelta(days=6)

            title_key = "week"
            title_value = f"{year}-W{week_num:02d}"
            range_str = f"{start_date.isoformat()} to {end_date.isoformat()}"

            # Query & aggregate per day
            qs = TaskList.objects.filter(date__range=[start_date, end_date])
            if not user.is_staff:
                qs = qs.filter(user=user)

            daily_agg = qs.values('date').annotate(
                total_duration=Sum('duration'),
                entry_count=Count('id')
            )

            daily_map = {
                row['date']: {
                    'duration': float(row['total_duration'] or 0.0),
                    'count': row['entry_count']
                }
                for row in daily_agg
            }

            days = []
            total_hours = 0.0
            total_entries = 0
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

            current = start_date
            for i in range(7):
                data = daily_map.get(current, {'duration': 0.0, 'count': 0})
                hours_str = f"{data['duration']:.2f}"

                days.append({
                    "day": day_names[i],
                    "date": current.isoformat(),
                    "duration_hours": hours_str,
                    "entry_count": data['count']
                })

                total_hours += data['duration']
                total_entries += data['count']
                current += timedelta(days=1)

            return Response({
                "status": "success",
                "view": "week",
                title_key: title_value,
                "date_range": range_str,
                "total_hours": f"{total_hours:.2f}",
                "total_entries": total_entries,
                "days": days
            })

        # ────────────────────────────────────────────────
        # YEAR VIEW - summary per month
        # ────────────────────────────────────────────────
        else:  # view == 'year'
            yearly_data = []
            yearly_total_hours = 0.0
            yearly_total_entries = 0

            for m in range(1, 13):
                try:
                    month_start = date(year, m, 1)
                    next_month_start = date(year + 1, 1, 1) if m == 12 else date(year, m + 1, 1)
                    month_end = next_month_start - timedelta(days=1)
                except ValueError:
                    continue

                qs = TaskList.objects.filter(date__range=[month_start, month_end])
                if not user.is_staff:
                    qs = qs.filter(user=user)

                agg = qs.aggregate(
                    total_duration=Sum('duration'),
                    entry_count=Count('id'),
                    active_days=Count('date', distinct=True)
                )

                hours = float(agg['total_duration'] or 0.0)
                entries = agg['entry_count'] or 0
                active_days_count = agg['active_days'] or 0

                yearly_data.append({
                    "month": month_start.strftime("%Y-%m"),
                    "month_name": month_start.strftime("%B"),
                    "total_hours": f"{hours:.2f}",
                    "entry_count": entries,
                    "days_with_entries": active_days_count
                })

                yearly_total_hours += hours
                yearly_total_entries += entries

            return Response({
                "status": "success",
                "view": "year",
                "year": str(year),
                "total_hours": f"{yearly_total_hours:.2f}",
                "total_entries": yearly_total_entries,
                "months": yearly_data
            })


class TopMembersAPIView(APIView):
    """
    GET /api/top-members/
    
    Returns top users ranked by total task hours (shown as hrs + mins).
    
    Query params:
    - limit: number of top members (default 10, max 50)
    - period: overall / today (default: overall)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = min(int(request.query_params.get('limit', 10)), 50)
        period = request.query_params.get('period', 'overall').lower()

        today = timezone.now().date()

        # Base queryset: all tasks (adjust status filter if you only want completed)
        qs = TaskList.objects.all()

        # Date filter
        if period == 'today':
            qs = qs.filter(date=today)
        elif period == 'overall':
            pass  # all time
        else:
            return Response({"error": "Invalid period. Use: overall / today"}, status=400)

        if not request.user.is_staff:
            qs = qs.filter(user=request.user)

        # Aggregate: total duration (decimal) + task count per user
        top_members = qs.values(
            'user__id',
            'user__name',
            'user__firstname',
            'user__email'
        ).annotate(
            total_duration=Sum('duration', default=0),
            task_count=Count('id')
        ).order_by('-total_duration')[:limit]

        # Format result with hrs + mins
        result = []
        rank = 1
        for row in top_members:
            total_hours_decimal = float(row['total_duration'] or 0)  # decimal → float
            hours = int(total_hours_decimal)
            minutes = int((total_hours_decimal - hours) * 60)

            name = row['user__firstname'] or row['user__name'] or "Unknown User"
            username = row['user__name'] or row['user__email'] or "N/A"

            result.append({
                "rank": rank,
                "user_id": row['user__id'],
                "name": name,
                "username": username,
                "total_time": f"{hours} hrs {minutes} mins",
                "total_hours_decimal": f"{total_hours_decimal:.2f}",
                "task_count": row['task_count']
            })
            rank += 1

        total_members = User.objects.filter(is_active=True).count()

        return Response({
            "status": "success",
            "total_members_in_system": total_members,
            "period": period.capitalize(),
            "top_members_count": len(result),
            "top_members": result
        })
    
# class TimeDistributionAPIView(APIView):

#     def get(self, request):
#         user = request.user
#         view_type = request.query_params.get("view", "daily")

#         today = timezone.now().date()

#         # ---------------- DATE FILTER ----------------
#         if view_type == "daily":
#             start_date = today
#         elif view_type == "weekly":
#             start_date = today - timedelta(days=7)
#         elif view_type == "monthly":
#             start_date = today - timedelta(days=30)
#         else:
#             return Response({"error": "Invalid view"}, status=400)

#         queryset = TaskList.objects.filter(date__gte=start_date)

#         # Non-staff → only their data
#         if not user.is_staff:
#             queryset = queryset.filter(user=user)
#         else:
#             user_id = request.query_params.get("user_id")
#             if user_id:
#                 queryset = queryset.filter(user_id=user_id)

#         # ---------------- AGGREGATION ----------------
#         data = (
#             queryset
#             .values("task__name")
#             .annotate(total_hours=Sum("duration"))
#             .order_by("-total_hours")
#         )

#         labels = []
#         series = []

#         for item in data:
#             labels.append(item["task__name"])
#             series.append(float(item["total_hours"] or 0))

#         return Response({
#             "labels": labels,
#             "series": series
#         })
class TimeDistributionAPIView(APIView):

    def get(self, request):
        user = request.user
        view_type = request.query_params.get("view", "daily")

        today = timezone.now().date()

        # ---------------- DATE FILTER ----------------
        if view_type == "daily":
            queryset = TaskList.objects.filter(date=today)

        elif view_type == "weekly":
            start_date = today - timedelta(days=7)
            queryset = TaskList.objects.filter(date__range=[start_date, today])

        elif view_type == "monthly":
            start_date = today - timedelta(days=30)
            queryset = TaskList.objects.filter(date__range=[start_date, today])

        else:
            return Response({"error": "Invalid view"}, status=400)

        # ---------------- USER FILTER ----------------
        if not user.is_staff:
            queryset = queryset.filter(user=user)

        # ---------------- AGGREGATION ----------------
        data = (
            queryset
            .values("task__name")
            .annotate(total_hours=Sum("duration"))
            .order_by("-total_hours")
        )

        labels = [d["task__name"] for d in data if d["task__name"]]
        series = [float(d["total_hours"] or 0) for d in data if d["task__name"]]

        return Response({
            "labels": labels if labels else ["No Data"],
            "series": series if series else [0]
        })
# class TimeDistributionAPIView(APIView):

#     def get(self, request):
#         user = request.user
#         view_type = request.query_params.get("view", "daily")

#         today = timezone.now().date()

#         if view_type == "daily":
#             queryset = TaskList.objects.filter(date=today)

#         elif view_type == "weekly":
#             start_date = today - timedelta(days=7)
#             queryset = TaskList.objects.filter(date__range=[start_date, today])

#         elif view_type == "monthly":
#             start_date = today - timedelta(days=30)
#             queryset = TaskList.objects.filter(date__range=[start_date, today])

#         else:
#             return Response({"error": "Invalid view"}, status=400)

#         # 🔥 DEBUG
#         print("LOGGED USER:", user.id)
#         print("TOTAL RECORDS:", TaskList.objects.count())
#         print("BEFORE USER FILTER:", queryset.count())

#         if not user.is_staff:
#             queryset = queryset.filter(user=user)

#         print("AFTER USER FILTER:", queryset.count())

#         data = (
#             queryset
#             .values("task__name")
#             .annotate(total_hours=Sum("duration"))
#         )

#         labels = [d["task__name"] for d in data if d["task__name"]]
#         series = [float(d["total_hours"] or 0) for d in data if d["task__name"]]

#         if not labels:
#             return Response({
#                 "labels": ["No Data"],
#                 "series": [0]
#             })

#         return Response({
#             "labels": labels,
#             "series": series
#         })


class RecentTasksAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get last 10 tasks
        queryset = (
            TaskList.objects
            .select_related("task", "platform", "status")
            .filter(user=user)
            .order_by("-date", "-id")[:10]
        )

        data = []

        for task in queryset:
            # ✅ Convert decimal hours → "Xh Ym"
            total_hours = float(task.duration or 0)
            hours = int(total_hours)
            minutes = int(round((total_hours - hours) * 60))

            duration_str = f"{hours}h {minutes}m" if hours else f"{minutes}m"

            data.append({
                "id": task.id,
                "task": task.task.name if task.task else "",
                "platform": task.platform.name if task.platform else "",
                "date": task.date.strftime("%d %b %Y") if task.date else "",
                "duration": duration_str,
                "status": task.status.name if task.status else "",
            })

        return Response(data)
    
class TopUsedTasksAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Aggregate total duration per task
        tasks = (
            TaskList.objects
            .filter(user=user)
            .values("task", "task__name")   # adjust if field is task_name
            .annotate(total_duration=Sum("duration"))
            .order_by("-total_duration")[:10]
        )

        # Total time (for percentage calculation)
        total_time = sum(float(t["total_duration"] or 0) for t in tasks)

        data = []
        for i, task in enumerate(tasks, start=1):
            hours = float(task["total_duration"] or 0)

            percentage = (hours / total_time * 100) if total_time > 0 else 0

            data.append({
                "id": i,
                "task": task["task__name"],  
                "hours": round(hours, 1),
                "percentage": round(percentage),
            })

        return Response(data)
    

class TopPlatformsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        view_type = request.query_params.get("view", "monthly")

        today = timezone.now().date()

        # ---------------- DATE FILTER ----------------
        if view_type == "daily":
            queryset = TaskList.objects.filter(date=today)

        elif view_type == "weekly":
            start_date = today - timedelta(days=7)
            queryset = TaskList.objects.filter(date__range=[start_date, today])

        elif view_type == "monthly":
            start_date = today - timedelta(days=30)
            queryset = TaskList.objects.filter(date__range=[start_date, today])

        else:
            return Response({"error": "Invalid view"}, status=400)

        # ---------------- APPROVER FILTER ----------------
        if not user.is_staff:
            queryset = queryset.filter(
                Q(l1_approver=user) |
                Q(l2_approver=user) |
                Q(user__first_level_manager=user) |
                Q(user__second_level_manager=user)
            )

        # ---------------- AGGREGATION ----------------
        data = (
            queryset
            .values("platform__id", "platform__name")
            .annotate(
                total_hours=Sum("duration"),
                user_count=Count("user", distinct=True)
            )
            .order_by("-total_hours")[:5]
        )

        total_hours_all = sum([float(d["total_hours"] or 0) for d in data]) or 1

        response = []

        for d in data:
            usage_percent = round((float(d["total_hours"]) / total_hours_all) * 100)

            response.append({
                "name": d["platform__name"],
                "users": f"{d['user_count']} Active Users",
                "usage": usage_percent
            })

        return Response(response)
    

class PlatformPerformanceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        view_type = request.query_params.get("view", "monthly")

        today = timezone.now().date()

        # ---------------- DATE FILTER ----------------
        if view_type == "daily":
            queryset = TaskList.objects.filter(date=today)

        elif view_type == "weekly":
            start_date = today - timedelta(days=7)
            queryset = TaskList.objects.filter(date__range=[start_date, today])

        elif view_type == "monthly":
            start_date = today - timedelta(days=30)
            queryset = TaskList.objects.filter(date__range=[start_date, today])

        else:
            return Response({"error": "Invalid view"}, status=400)

        # ---------------- APPROVER FILTER ----------------
        if not user.is_staff:
            queryset = queryset.filter(
                Q(l1_approver=user) |
                Q(l2_approver=user) |
                Q(user__first_level_manager=user) |
                Q(user__second_level_manager=user)
            )

        # ---------------- GROUP BY PLATFORM ----------------
        platforms = (
            queryset
            .values("platform__id", "platform__name")
            .annotate(
                total_hours=Sum("duration"),
                total_tasks=Count("id"),
                users=Count("user", distinct=True),
                completed_tasks=Count("id", filter=Q(status__name__iexact="Completed")),
                approved_tasks=Count("id", filter=Q(l1_approved_at__isnull=False)),
                integrated_tasks=Count("id", filter=Q(bitrix_id__isnull=False))
            )
        )

        series = []

        for p in platforms:
            users = p["users"] or 1
            total_tasks = p["total_tasks"] or 1

            # ---------------- METRICS ----------------
            active_users = min(users * 10, 100)  

            performance = min(int((float(p["total_hours"] or 0) / users) * 10), 100)

            reliability = int((p["approved_tasks"] / total_tasks) * 100)

            integration = int((p["integrated_tasks"] / total_tasks) * 100)

            satisfaction = int((p["completed_tasks"] / total_tasks) * 100)

            series.append({
                "name": p["platform__name"],
                "data": [
                    active_users,
                    performance,
                    reliability,
                    integration,
                    satisfaction
                ]
            })

        return Response({
            "categories": [
                "Active Users",
                "Performance",
                "Reliability",
                "Integration",
                "Satisfaction"
            ],
            "series": series
        })
class ProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Manager
        manager_name = ""
        if user.first_level_manager and user.first_level_manager.realname:
            manager_name = user.first_level_manager.realname.split("/")[0]

        # Initials
        initials = ""
        if user.realname:
            parts = user.realname.split()
            initials = "".join([p[0] for p in parts[:2]]).upper()

        return Response({
            "id": user.id,
            "name": user.realname.split("/")[0] if user.realname else "",
            "firstname": user.firstname,
            "email": user.email,
            "phone": user.phone or user.mobile,
            "employee_id": user.employee_id,
            "department": user.department.name if user.department else "",

            # ✅ FIXED FIELDS
            "designation": user.designation or "",
            "business_unit": user.business_unit or "",
            "location": user.location_name or "",

            "manager_name": manager_name,
            "avatar_initials": initials,
        }, status=status.HTTP_200_OK)
    

class ApprovalTableAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        queryset = TaskList.objects.select_related(
            "user",
            "status",
            "user__department",
            "user__location"
        ).all()

        status_map = {
            "inprogress": "In Progress",
            "inreview": "In Review",
            "completed": "Completed",
        }

        grouped = defaultdict(list)

        for task in queryset:
            status_name = task.get_status_lower()

            if not status_name:
                continue

            key = status_name.replace(" ", "")

            if key not in status_map:
                continue

            grouped[key].append({
                "owner": task.user.realname or task.user.name,
                "role": task.user.designation or "N/A",
                "department": task.user.department.name if task.user.department else "N/A",
                "location": (
                    task.user.location.name
                    if task.user.location else task.user.location_name or "N/A"
                ),
                "date": task.date.strftime("%d %b %Y"),
            })

        response_data = []

        for key, title in status_map.items():
            rows = grouped.get(key, [])

            response_data.append({
                "title": title,
                "count": len(rows),
                "rows": rows
            })

        return Response(response_data)

class RecentRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        queryset = TaskList.objects.select_related("user")

        # ------------------- PENDING -------------------
        pending_tasks = queryset.filter(
            Q(
                l1_approver=user,
                l1_approved_at__isnull=True,
                l1_rejected_at__isnull=True
            ) |
            Q(
                l2_approver=user,
                l1_approved_at__isnull=False,
                l2_approved_at__isnull=True,
                l2_rejected_at__isnull=True
            )
        ).order_by("-created_at")[:5]   # 🔥 latest 5

        # ------------------- FORMAT FOR UI -------------------
        recent_requests = []

        for task in pending_tasks:
            start_time = localtime(task.created_at).strftime("%I:%M %p")
            end_time = localtime(task.updated_at).strftime("%I:%M %p")

            recent_requests.append({
                "id": task.id,
                "name": task.user.name,
                "time": f"{start_time} - {end_time}",
            })

        return Response({
            "recent_requests": recent_requests
        })
    
class TaskApproveRejectAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        task_id = request.data.get("task_id")
        action = request.data.get("action")  # approve / reject

        try:
            task = TaskList.objects.get(id=task_id)
        except TaskList.DoesNotExist:
            return Response({"error": "Task not found"}, status=404)

        now = timezone.now()

        # ------------------- L1 APPROVAL -------------------
        if task.l1_approver == user:

            if task.l1_approved_at or task.l1_rejected_at:
                return Response({"error": "Already processed by L1"}, status=400)

            if action == "approve":
                task.l1_approved_at = now

            elif action == "reject":
                task.l1_rejected_at = now

        # ------------------- L2 APPROVAL -------------------
        elif task.l2_approver == user:

            # ❌ Block if L1 not approved
            if not task.l1_approved_at:
                return Response({"error": "L1 approval pending"}, status=400)

            if task.l2_approved_at or task.l2_rejected_at:
                return Response({"error": "Already processed by L2"}, status=400)

            if action == "approve":
                task.l2_approved_at = now

            elif action == "reject":
                task.l2_rejected_at = now

        else:
            return Response({"error": "Not authorized"}, status=403)

        task.save()

        return Response({"message": f"{action.capitalize()}d successfully"})