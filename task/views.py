# views.py
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone

from .models import TaskList, TaskListAuditLog
from .serializers import TaskListSerializer, TaskListAuditLogSerializer
from master.models import Status
from isoweek import Week
from django.db.models import Count, Q,Sum
from datetime import datetime, timedelta, date
from django.utils import timezone
from dateutil.relativedelta import relativedelta
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

        # Role-based visibility
        if user.is_staff:
            # Admin sees ALL tasks
            pass
        else:
            # Normal users & approvers see only their own created tasks
            queryset = queryset.filter(user=user)

        return queryset

    def get_object(self, pk):
        task = get_object_or_404(TaskList, pk=pk)

        # Only owner or admin (staff) can access
        if task.user != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("You don't have permission to access this task.")

        return task

    def _create_audit_log(self, task, action, old_values=None, new_values=None, remarks=None):
        request = self.request
        TaskListAuditLog.objects.create(
            task=task,
            action=action,
            performed_by=request.user,
            old_values=old_values,
            new_values=new_values,
            remarks=remarks,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    def check_edit_permission(self, task, user):
        """Only owner can edit fields in draft; staff can edit in Inprogress"""
        if not task.status:
            return False
        status_lower = (task.status.name or '').lower().strip()
        if task.user == user:
            return status_lower == 'draft'
        return user.is_staff and status_lower in ('inprogress', 'in progress')

    def apply_filters(self, request, queryset):
        params = request.query_params
        user = request.user

        # Only admin (staff) can filter by other users
        if params.get('user_id') and user.is_staff:
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
            serializer = self.serializer_class(task)
            return Response(serializer.data)

        queryset = self.get_queryset()
        queryset = self.apply_filters(request, queryset)
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Staff (admin/approver) cannot create tasks
        if request.user.is_staff:
            return Response(
                {"error": "Staff users cannot create new tasks. Use a regular account."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid():
            task = serializer.save()
            self._create_audit_log(
                task=task,
                action='CREATE',
                new_values=serializer.data,
                remarks="Task created"
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        task = self.get_object(pk)
        user = request.user

        status_lower = (task.status.name or '').lower().strip() if task.status else ''

        # Define old_values EARLY - prevents NameError
        old_values = {
            'status': task.status.name if task.status else None,
            'duration': str(task.duration),
            'description': task.description or "",
            'bitrix_id': task.bitrix_id or "",
        }

        # Debug prints
        print(f"\n=== PUT DEBUG (Task {pk}) ===")
        print(f"User: {user.firstname} (ID: {user.id}) | is_staff: {user.is_staff}")
        print(f"Current status: {task.status.name if task.status else 'None'}")
        print(f"Before → l1_approver_id: {task.l1_approver_id}, l2_approver_id: {task.l2_approver_id}")
        print(f"Payload: {request.data}")

        if not user.is_staff:
            return Response({"error": "Only staff users can approve or update"}, status=403)

        action = request.data.get('action')

        # Already approved messages (no overwrite)
        if action == 'L1_APPROVE' and task.l1_approver:
            return Response({
                "message": "This task is already L1 approved",
                "l1_approver": task.l1_approver.firstname,
                "l1_approved_at": task.l1_approved_at.strftime("%Y-%m-%d %H:%M:%S") if task.l1_approved_at else None
            }, status=200)

        if action == 'L2_APPROVE' and task.l2_approver:
            return Response({
                "message": "This task is already L2 approved",
                "l2_approver": task.l2_approver.firstname,
                "l2_approved_at": task.l2_approved_at.strftime("%Y-%m-%d %H:%M:%S") if task.l2_approved_at else None
            }, status=200)

        # Field edit permission (no approval action)
        wants_approve = action in ('L1_APPROVE', 'L2_APPROVE')
        if not wants_approve:
            can_edit = (
                (task.user == user and status_lower == 'draft') or
                (user.is_staff and status_lower in ('inprogress', 'in progress'))
            )
            if not can_edit:
                return Response({"error": "No permission to edit fields in this status"}, status=403)

        # Serializer
        serializer = TaskListSerializer(
            task,
            data=request.data,
            context={'request': request},
            partial=True
        )

        if not serializer.is_valid():
            print("Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=400)

        status_changed = False

        # Status objects
        in_progress_status = Status.objects.filter(name__iexact='In Progress').first() or \
                             Status.objects.filter(name__iexact='inprogress').first()

        completed_status = Status.objects.filter(name__iexact='Completed').first() or \
                           Status.objects.filter(name__iexact='Done').first()

        # L1 approval
        if action == 'L1_APPROVE' and in_progress_status:
            if not task.l1_approver:
                serializer.validated_data['l1_approver'] = user
                serializer.validated_data['l1_approved_at'] = timezone.now()

            if status_lower == 'draft':
                serializer.validated_data['status'] = in_progress_status
                status_changed = True

        # L2 approval
        if action == 'L2_APPROVE' and completed_status:
            if not task.l2_approver:
                serializer.validated_data['l2_approver'] = user
                serializer.validated_data['l2_approved_at'] = timezone.now()

            serializer.validated_data['status'] = completed_status
            status_changed = True

        serializer.validated_data['last_modified_by'] = user

        updated_task = serializer.save()

        # Audit log
        new_values = {
            'status': updated_task.status.name if updated_task.status else None,
            'duration': str(updated_task.duration),
            'description': updated_task.description or "",
            'bitrix_id': updated_task.bitrix_id or "",
        }

        action_log = 'L2_APPROVE' if action == 'L2_APPROVE' else \
                     'L1_APPROVE' if action == 'L1_APPROVE' else \
                     'UPDATE'

        remarks = request.data.get('remarks', 'Task updated/approved')

        self._create_audit_log(
            task=updated_task,
            action=action_log,
            old_values=old_values,
            new_values=new_values,
            remarks=remarks
        )

        return Response(serializer.data)

    def delete(self, request, pk):
        task = self.get_object(pk)
        if task.user != request.user or (task.status and (task.status.name or '').lower().strip() != 'draft'):
            return Response(
                {"error": "Only the owner can delete draft tasks"},
                status=status.HTTP_403_FORBIDDEN
            )

        self._create_audit_log(
            task=task,
            action='DELETE',
            old_values={'id': task.id, 'task_name': task.task.name if task.task else None},
            remarks="Task deleted by owner"
        )
        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TaskListAuditLogAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id=None):
        if task_id:
            task = get_object_or_404(TaskList, pk=task_id)
            if task.user != request.user and not request.user.is_staff:
                raise PermissionDenied("You don't have permission to view audit logs for this task.")
            logs = TaskListAuditLog.objects.filter(task=task).order_by('-created_at')
            serializer = TaskListAuditLogSerializer(logs, many=True)
            return Response(serializer.data)

        # Admin (staff) sees all logs
        if request.user.is_staff:
            logs = TaskListAuditLog.objects.all().order_by('-created_at')
        else:
            # Approvers/normal users see only their own tasks' logs
            logs = TaskListAuditLog.objects.filter(task__user=request.user).order_by('-created_at')

        serializer = TaskListAuditLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    

# Daily Timeline code 

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone

from .models import TaskList


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
            
# Time Distribution by Task

