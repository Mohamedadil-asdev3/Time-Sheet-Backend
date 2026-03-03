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

        if not user.is_staff:
            queryset = queryset.filter(user=user)

        return queryset

    def get_object(self, pk):
        task = get_object_or_404(TaskList, pk=pk)
        if task.user != self.request.user and not self.request.user.is_staff:
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

        status_lower = (task.status.name or '').lower().strip() if task.status else ''

        # Capture meaningful old values BEFORE any changes
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

        # ... permission checks, idempotent responses, edit permission ...

        serializer = self.serializer_class(
            task,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        if not serializer.is_valid():
            print("Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=400)

        # Status objects
        in_progress = Status.objects.filter(name__iexact='In Progress').first() or \
                      Status.objects.filter(name__iexact='inprogress').first()
        completed   = Status.objects.filter(name__iexact='Completed').first() or \
                      Status.objects.filter(name__iexact='Done').first()

        changed_fields = set()

        if action == 'L1_APPROVE' and in_progress:
            if task.l1_approver and task.l1_approver != user:
                return Response({"error": "Only assigned L1 approver can approve"}, status=403)

            serializer.validated_data['l1_approver'] = user
            serializer.validated_data['l1_approved_at'] = timezone.now()
            changed_fields.add('l1_approver')
            changed_fields.add('l1_approved_at')

            l2_candidate = None
            if hasattr(user, 'user_id_supervisor') and user.user_id_supervisor:
                if user.user_id_supervisor.is_manager:
                    l2_candidate = user.user_id_supervisor

            if l2_candidate != task.l2_approver:
                serializer.validated_data['l2_approver'] = l2_candidate
                changed_fields.add('l2_approver')

            if status_lower == 'draft':
                serializer.validated_data['status'] = in_progress
                changed_fields.add('status')

        if action == 'L2_APPROVE' and completed:
            if task.l2_approver and task.l2_approver != user:
                return Response({"error": "Only assigned L2 approver can approve"}, status=403)

            serializer.validated_data['l2_approver'] = user
            serializer.validated_data['l2_approved_at'] = timezone.now()
            serializer.validated_data['status'] = completed
            changed_fields.update({'l2_approver', 'l2_approved_at', 'status'})

        serializer.validated_data['last_modified_by'] = user

        # Perform the actual update
        updated_task = serializer.save()

        # Capture new values AFTER save
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

        # Determine action name for log
        if action == 'L1_APPROVE':
            log_action = 'L1_APPROVE'
        elif action == 'L2_APPROVE':
            log_action = 'L2_APPROVE'
        else:
            log_action = 'UPDATE'

        remarks = request.data.get('remarks', f"Task {log_action.lower()}d")

        # Always create audit log (even for normal updates)
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


# Audit log view remains unchanged
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

# class TaskListAuditLogAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, task_id=None):
#         if task_id:
#             task = get_object_or_404(TaskList, pk=task_id)
#             if task.user != request.user and not request.user.is_staff:
#                 raise PermissionDenied("You don't have permission to view audit logs for this task.")
#             logs = TaskListAuditLog.objects.filter(task=task).order_by('-created_at')
#             serializer = TaskListAuditLogSerializer(logs, many=True)
#             return Response(serializer.data)

#         # Admin (staff) sees all logs
#         if request.user.is_staff:
#             logs = TaskListAuditLog.objects.all().order_by('-created_at')
#         else:
#             # Approvers/normal users see only their own tasks' logs
#             logs = TaskListAuditLog.objects.filter(task__user=request.user).order_by('-created_at')

#         serializer = TaskListAuditLogSerializer(logs, many=True)
#         return Response(serializer.data)
# class TaskListAPIView(APIView):
#     serializer_class = TaskListSerializer

#     def get_permissions(self):
#         if self.request.method == 'GET':
#             return [IsAuthenticated()]
#         if self.request.method == 'POST':
#             return [IsAuthenticated()]  # normal users can create
#         if self.request.method in ['PUT', 'DELETE']:
#             return [IsOwnerOrStaffApprover()]
#         return [IsAuthenticated()]

#     def get_queryset(self):
#         user = self.request.user
#         queryset = TaskList.objects.select_related(
#             'platform', 'task', 'subtask', 'status',
#             'l1_approver', 'l2_approver', 'last_modified_by'
#         ).order_by('-date', 'task__name')

#         if user.is_staff:
#             # Staff sees everything
#             pass
#         else:
#             # Normal users see only their own tasks
#             queryset = queryset.filter(user=user)

#         return queryset

#     def get_object(self, pk):
#         task = get_object_or_404(TaskList, pk=pk)

#         # Only owner or staff can access
#         if task.user != self.request.user and not self.request.user.is_staff:
#             raise PermissionDenied("You don't have permission to access this task.")

#         return task

#     def _create_audit_log(self, task, action, old_values=None, new_values=None, remarks=None):
#         request = self.request
#         TaskListAuditLog.objects.create(
#             task=task,
#             action=action,
#             performed_by=request.user,
#             old_values=old_values or {},
#             new_values=new_values or {},
#             remarks=remarks or '',
#             ip_address=self._get_client_ip(request),
#             user_agent=request.META.get('HTTP_USER_AGENT', '')
#         )

#     def _get_client_ip(self, request):
#         x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#         if x_forwarded_for:
#             return x_forwarded_for.split(',')[0].strip()
#         return request.META.get('REMOTE_ADDR', '')

#     def apply_filters(self, request, queryset):
#         params = request.query_params
#         user = request.user

#         if params.get('user_id') and user.is_staff:
#             queryset = queryset.filter(user_id=params['user_id'])

#         if params.get('start_date'):
#             queryset = queryset.filter(date__gte=params['start_date'])
#         if params.get('end_date'):
#             queryset = queryset.filter(date__lte=params['end_date'])
#         if params.get('platform'):
#             queryset = queryset.filter(platform_id=params['platform'])
#         if params.get('task'):
#             queryset = queryset.filter(task_id=params['task'])
#         if params.get('status'):
#             queryset = queryset.filter(status_id=params['status'])
#         if search := params.get('search'):
#             queryset = queryset.filter(
#                 Q(description__icontains=search) |
#                 Q(bitrix_id__icontains=search) |
#                 Q(task__name__icontains=search) |
#                 Q(subtask__name__icontains=search) |
#                 Q(user__username__icontains=search)
#             )
#         return queryset

#     def get(self, request, pk=None):
#         if pk:
#             task = self.get_object(pk)
#             serializer = self.serializer_class(task)
#             return Response(serializer.data)

#         queryset = self.get_queryset()
#         queryset = self.apply_filters(request, queryset)
#         serializer = self.serializer_class(queryset, many=True)
#         return Response(serializer.data)

#     def post(self, request):
#         if not request.user.groups.filter(name='TaskCreators').exists():
#             return Response(
#                 {"error": "You do not have permission to create tasks."},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         serializer = TaskListSerializer(data=request.data, context={'request': request})
#         if serializer.is_valid():
#             task = serializer.save()
#             # audit log...
#             return Response(serializer.data, status=201)
#         return Response(serializer.errors, status=400)
    
#     def put(self, request, pk):
#         task = self.get_object(pk)
#         user = request.user

#         # Prepare old values for audit
#         old_values = {
#             'status': task.status.name if task.status else None,
#             'duration': str(task.duration) if task.duration else None,
#             'description': task.description or "",
#             'bitrix_id': task.bitrix_id or "",
#         }

#         action = request.data.get('action')
#         remarks = request.data.get('remarks', 'Task updated')

#         # Block already approved tasks from being re-approved
#         if action == 'L1_APPROVE' and task.l1_approver:
#             return Response({
#                 "message": "This task is already L1 approved",
#                 "l1_approver": task.l1_approver.name,
#                 "l1_approved_at": task.l1_approved_at
#             }, status=200)

#         if action == 'L2_APPROVE' and task.l2_approver:
#             return Response({
#                 "message": "This task is already L2 approved",
#                 "l2_approver": task.l2_approver.name,
#                 "l2_approved_at": task.l2_approved_at
#             }, status=200)

#         # Status transition rules
#         current_status = (task.status.name or '').lower().strip() if task.status else ''

#         # Normal user can only edit Draft
#         if not user.is_staff:
#             if current_status != 'draft':
#                 return Response({"error": "You can only edit tasks in Draft status"}, status=403)

#         serializer = TaskListSerializer(
#             task,
#             data=request.data,
#             context={'request': request},
#             partial=True
#         )

#         if not serializer.is_valid():
#             return Response(serializer.errors, status=400)

#         # Status objects (cache them)
#         draft_status = Status.objects.filter(name__iexact='draft').first()
#         in_progress_status = Status.objects.filter(
#             Q(name__iexact='In Progress') | Q(name__iexact='inprogress')
#         ).first()
#         completed_status = Status.objects.filter(
#             Q(name__iexact='Completed') | Q(name__iexact='Done')
#         ).first()

#         status_changed = False

#         # L1 Approval (only staff with L1 role or admin)
#         if action == 'L1_APPROVE':
#             if not in_progress_status:
#                 return Response({"error": "In Progress status not found"}, status=500)

#             if current_status == 'draft':
#                 serializer.validated_data['status'] = in_progress_status
#                 serializer.validated_data['l1_approver'] = user
#                 serializer.validated_data['l1_approved_at'] = timezone.now()
#                 status_changed = True
#             else:
#                 return Response({"error": "L1 approval only allowed on Draft tasks"}, status=400)

#         # L2 Approval (only staff with L2 role or admin)
#         if action == 'L2_APPROVE':
#             if not completed_status:
#                 return Response({"error": "Completed status not found"}, status=500)

#             if current_status in ['in progress', 'inprogress']:
#                 serializer.validated_data['status'] = completed_status
#                 serializer.validated_data['l2_approver'] = user
#                 serializer.validated_data['l2_approved_at'] = timezone.now()
#                 status_changed = True
#             else:
#                 return Response({"error": "L2 approval only allowed on In Progress tasks"}, status=400)

#         serializer.validated_data['last_modified_by'] = user

#         updated_task = serializer.save()

#         # Audit log for status change or approval
#         new_values = {
#             'status': updated_task.status.name if updated_task.status else None,
#             'duration': str(updated_task.duration) if updated_task.duration else None,
#             'description': updated_task.description or "",
#             'bitrix_id': updated_task.bitrix_id or "",
#         }

#         log_action = action if action in ['L1_APPROVE', 'L2_APPROVE'] else 'UPDATE'
#         if status_changed:
#             log_action = f"{log_action} (Status Changed)"

#         self._create_audit_log(
#             task=updated_task,
#             action=log_action,
#             old_values=old_values,
#             new_values=new_values,
#             remarks=remarks
#         )

#         return Response(serializer.data)

#     def delete(self, request, pk):
#         task = self.get_object(pk)
#         if task.user != request.user or (task.status and (task.status.name or '').lower().strip() != 'draft'):
#             return Response(
#                 {"error": "Only the owner can delete draft tasks"},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         self._create_audit_log(
#             task=task,
#             action='DELETE',
#             old_values={'id': task.id, 'task_name': task.task.name if task.task else None},
#             remarks="Task deleted by owner"
#         )
#         task.delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)


# class TaskListAuditLogAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, task_id=None):
#         if task_id:
#             task = get_object_or_404(TaskList, pk=task_id)
#             if task.user != request.user and not request.user.is_staff:
#                 raise PermissionDenied("You don't have permission to view audit logs for this task.")
#             logs = TaskListAuditLog.objects.filter(task=task).order_by('-created_at')
#         else:
#             if request.user.is_staff:
#                 logs = TaskListAuditLog.objects.all().order_by('-created_at')
#             else:
#                 logs = TaskListAuditLog.objects.filter(task__user=request.user).order_by('-created_at')

#         serializer = TaskListAuditLogSerializer(logs, many=True)
#         return Response(serializer.data)   
    

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
# Top Members by Hours
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import TaskList

User = get_user_model()

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