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


# class TaskListAPIView(APIView):
#     serializer_class = TaskListSerializer

#     def get_permissions(self):
#         if self.request.method == 'GET':
#             return [IsAuthenticated()]
#         if self.request.method == 'POST':
#             return [IsAuthenticated()]
#         if self.request.method in ['PUT', 'DELETE']:
#             return [IsOwnerOrStaffApprover()]
#         return [IsAuthenticated()]

#     def get_queryset(self):
#         user = self.request.user
#         queryset = TaskList.objects.select_related(
#             'platform', 'task', 'subtask', 'status',
#             'l1_approver', 'l2_approver', 'last_modified_by'
#         ).order_by('-date', 'task__name')

#         if not user.is_staff:
#             queryset = queryset.filter(user=user)

#         return queryset

#     # def get_object(self, pk):
#     #     task = get_object_or_404(TaskList, pk=pk)
#     #     if task.user != self.request.user and not self.request.user.is_staff:
#     #         raise PermissionDenied("You don't have permission to access this task.")
#     #     return task
#     def get_object(self, pk):
#         task = get_object_or_404(TaskList, pk=pk)
#         user = self.request.user

#         if not (
#             task.user == user or
#             task.l1_approver_id == user.id or
#             task.l2_approver_id == user.id or
#             user.is_staff
#         ):
#             raise PermissionDenied("You don't have permission to access this task.")

#         return task

#     def _create_audit_log(self, task, action, old_values=None, new_values=None, remarks=None):
#         TaskListAuditLog.objects.create(
#             task=task,
#             action=action,
#             performed_by=self.request.user,
#             old_values=old_values or {},
#             new_values=new_values or {},
#             remarks=remarks or '',
#             ip_address=self._get_client_ip(self.request),
#             user_agent=self.request.META.get('HTTP_USER_AGENT', '')
#         )

#     def _get_client_ip(self, request):
#         x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#         if x_forwarded_for:
#             return x_forwarded_for.split(',')[0].strip()
#         return request.META.get('REMOTE_ADDR', '')

#     def apply_filters(self, request, queryset):
#         params = request.query_params
#         if params.get('user_id') and request.user.is_staff:
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
#             return Response(self.serializer_class(task).data)

#         qs = self.get_queryset()
#         qs = self.apply_filters(request, qs)
#         return Response(self.serializer_class(qs, many=True).data)

#     def post(self, request):
#         if request.user.is_staff:
#             return Response(
#                 {"error": "Staff users cannot create tasks"},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         data = request.data
#         is_bulk = isinstance(data, list)

#         serializer = self.serializer_class(
#             data=data,
#             many=is_bulk,
#             context={'request': request}
#         )

#         if not serializer.is_valid():
#             print("Create errors:", serializer.errors)
#             return Response(serializer.errors, status=400)

#         tasks = serializer.save()

#         for task in (tasks if is_bulk else [tasks]):
#             if task.user.first_level_manager:
#                 task.l1_approver = task.user.first_level_manager
#             if task.user.second_level_manager:
#                 task.l2_approver = task.user.second_level_manager

#             task.save()
#             self._create_audit_log(
#                 task=task,
#                 action='CREATE',
#                 new_values=self.serializer_class(task).data,
#                 remarks="Bulk task created" if is_bulk else "Task created"
#             )

#         return Response(serializer.data, status=status.HTTP_201_CREATED)

#     def put(self, request, pk):
#         task = self.get_object(pk)
#         user = request.user
#         action = request.data.get('action') 
#         status_lower = (task.status.name or '').lower().strip() if task.status else ''

#         # Capture old values
#         old_values = {
#             'status': task.status.name if task.status else None,
#             'duration': str(task.duration) if task.duration is not None else None,
#             'description': task.description or "",
#             'bitrix_id': task.bitrix_id or "",
#             'l1_approver_id': task.l1_approver_id,
#             'l2_approver_id': task.l2_approver_id,
#             'l1_approved_at': task.l1_approved_at.isoformat() if task.l1_approved_at else None,
#             'l2_approved_at': task.l2_approved_at.isoformat() if task.l2_approved_at else None,
#         }

#         serializer = self.serializer_class(
#             task,
#             data=request.data,
#             partial=True,
#             context={'request': request}
#         )

#         if not serializer.is_valid():
#             return Response(serializer.errors, status=400)

#         # Status objects
#         in_progress = Status.objects.filter(name__iexact='In Progress').first() or \
#                     Status.objects.filter(name__iexact='inprogress').first()
#         completed = Status.objects.filter(name__iexact='Completed').first() or \
#                     Status.objects.filter(name__iexact='Done').first()
#         rejected = Status.objects.filter(name__iexact='Rejected').first()
#         draft = Status.objects.filter(name__iexact='Draft').first()

#         # ----------------- L1 Approve -----------------
#         if action == 'L1_APPROVE' and in_progress:
#             if not task.l1_approver or task.l1_approver != user:
#                 return Response({"error": "Only assigned L1 approver can approve"}, status=403)

#             serializer.validated_data['l1_approver'] = user
#             serializer.validated_data['l1_approved_at'] = timezone.now()
#             if task.user.second_level_manager:
#                 serializer.validated_data['l2_approver'] = task.user.second_level_manager
#             if status_lower == 'draft':
#                 serializer.validated_data['status'] = in_progress

#         # ----------------- L2 Approve -----------------
#         if action == 'L2_APPROVE' and completed:
#             if not task.l2_approver or task.l2_approver != user:
#                 return Response({"error": "Only assigned L2 approver can approve"}, status=403)

#             serializer.validated_data['l2_approver'] = user
#             serializer.validated_data['l2_approved_at'] = timezone.now()
#             serializer.validated_data['status'] = completed


#         if action == 'SUBMIT' and in_progress:

#             if task.user != user:
#                 return Response({"error": "Only task owner can submit"}, status=403)

#             if not task.user.first_level_manager:
#                 return Response({"error": "No reporting manager assigned"}, status=400)

#             serializer.validated_data['status'] = in_progress
#             serializer.validated_data['l1_approver'] = task.user.first_level_manager

#         # ----------------- L1 Reject -----------------
#         if action == 'L1_REJECT' and rejected:
#             serializer.validated_data['status'] = rejected
#             serializer.validated_data['l1_rejected_at'] = timezone.now()
      

#         # ----------------- L2 Reject -----------------
#         if action == 'L2_REJECT' and rejected:
#             serializer.validated_data['status'] = rejected
#             serializer.validated_data['l2_rejected_at'] = timezone.now()
   

#         # ----------------- Resubmit by Owner -----------------
#         if action == 'RESUBMIT' and in_progress:
#             if task.user != user:
#                 return Response({"error": "Only task owner can resubmit"}, status=403)

#             serializer.validated_data['status'] = in_progress
#             serializer.validated_data['l1_approved_at'] = None
#             serializer.validated_data['l2_approved_at'] = None
#             serializer.validated_data['l1_approver'] = task.user.first_level_manager
#             serializer.validated_data['l2_approver'] = task.user.second_level_manager

#         # ----------------- Last Modified -----------------
#         serializer.validated_data['last_modified_by'] = user
#         updated_task = serializer.save()
#         new_values = {
#             'status': updated_task.status.name if updated_task.status else None,
#             'duration': str(updated_task.duration) if updated_task.duration is not None else None,
#             'description': updated_task.description or "",
#             'bitrix_id': updated_task.bitrix_id or "",
#             'l1_approver_id': updated_task.l1_approver_id,
#             'l2_approver_id': updated_task.l2_approver_id,
#             'l1_approved_at': updated_task.l1_approved_at.isoformat() if updated_task.l1_approved_at else None,
#             'l2_approved_at': updated_task.l2_approved_at.isoformat() if updated_task.l2_approved_at else None,
#         }

#         log_action = action if action in ['L1_APPROVE', 'L2_APPROVE', 'L1_REJECT', 'L2_REJECT', 'RESUBMIT'] else 'UPDATE'
#         remarks = request.data.get('remarks', f"Task {log_action.lower()}d")
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
#         status_name = (task.status.name or '').lower().strip() if task.status else ''
#         if task.user != request.user or status_name != 'draft':
#             return Response({"error": "Only owner can delete draft tasks"}, status=403)

#         self._create_audit_log(
#             task=task,
#             action='DELETE',
#             old_values={'id': task.id, 'task_name': task.task.name if task.task else None},
#             remarks="Deleted by owner"
#         )
#         task.delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)
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
            'l1_approver', 'l2_approver', 'last_modified_by', 'user'
        ).order_by('-date', 'task__name')

        # Staff can see all tasks
        if user.is_staff:
            return queryset
        
        # Non-staff users can see:
        # - Tasks they own
        # - Tasks where they are L1 approver
        # - Tasks where they are L2 approver
        queryset = queryset.filter(
            Q(user=user) |
            Q(l1_approver=user) |
            Q(l2_approver=user)
        )
        
        return queryset

    def get_object(self, pk):
        task = get_object_or_404(TaskList, pk=pk)
        user = self.request.user

        # Check if user has permission to access this task
        if not (
            task.user == user or
            task.l1_approver_id == user.id or
            task.l2_approver_id == user.id or
            user.is_staff
        ):
            raise PermissionDenied("You don't have permission to access this task.")

        return task

    # def _create_audit_log(self, task, action, old_values=None, new_values=None, remarks=None):
    #     TaskListAuditLog.objects.create(
    #         task=task,
    #         action=action,
    #         performed_by=self.request.user,
    #         old_values=old_values or {},
    #         new_values=new_values or {},
    #         remarks=remarks or '',
    #         ip_address=self._get_client_ip(self.request),
    #         user_agent=self.request.META.get('HTTP_USER_AGENT', '')
    #     )
    def _create_audit_log(self, task, action, old_values=None, new_values=None, remarks=None):
        TaskListAuditLog.objects.create(
            task=task,
            action=action,
            performed_by=self.request.user,
            old_values=old_values or {},
            new_values=new_values or {},
            remarks=remarks or '',
            ip_address=self._get_client_ip(self.request),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            l1_status=task.l1_status if hasattr(task, 'l1_status') else None,
            l2_status=task.l2_status if hasattr(task, 'l2_status') else None,
            l1_action_by=task.l1_approver,
            l1_action_at=task.l1_approved_at,
            l2_action_by=task.l2_approver,
            l2_action_at=task.l2_approved_at,
            l1_rejected_at=task.l1_rejected_at,
            l2_rejected_at=task.l2_rejected_at,
        )

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    def apply_filters(self, request, queryset):
        params = request.query_params
        
        # Staff can filter by user_id
        if params.get('user_id') and request.user.is_staff:
            queryset = queryset.filter(user_id=params['user_id'])
        
        # Date filters
        if params.get('start_date'):
            queryset = queryset.filter(date__gte=params['start_date'])
        if params.get('end_date'):
            queryset = queryset.filter(date__lte=params['end_date'])
        
        # Other filters
        if params.get('platform'):
            queryset = queryset.filter(platform_id=params['platform'])
        if params.get('task'):
            queryset = queryset.filter(task_id=params['task'])
        if params.get('status'):
            queryset = queryset.filter(status_id=params['status'])
        
        # Search filter
        if search := params.get('search'):
            queryset = queryset.filter(
                Q(description__icontains=search) |
                Q(bitrix_id__icontains=search) |
                Q(task__name__icontains=search) |
                Q(subtask__name__icontains=search) |
                Q(user__username__icontains=search)
            )
        
        return queryset

    # def get(self, request, pk=None):
    #     if pk:
    #         task = self.get_object(pk)
    #         return Response(self.serializer_class(task).data)

    #     qs = self.get_queryset()
    #     qs = self.apply_filters(request, qs)
        
    #     # Debug: Print count
    #     print(f"Total tasks found: {qs.count()}")
        
    #     serializer = self.serializer_class(qs, many=True)
    #     return Response(serializer.data)
    def get(self, request, pk=None):
        if pk:
            task = self.get_object(pk)
            return Response(self.serializer_class(task).data)

        qs = self.get_queryset()
        qs = self.apply_filters(request, qs)
        
        # Debug: Print count
        print(f"Total tasks found: {qs.count()}")
        
        # Group tasks by date using defaultdict
        grouped_data = defaultdict(list)
        
        for task in qs:
            task_data = self.serializer_class(task).data
            date_str = task.date.strftime('%Y-%m-%d')
            grouped_data[date_str].append(task_data)
        
        # Convert to list of dictionaries
        response_data = [
            {'date': date, 'tasks': tasks} 
            for date, tasks in grouped_data.items()
        ]
        
        # Sort by date descending
        response_data.sort(key=lambda x: x['date'], reverse=True)
        
        return Response(response_data)

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

        # Capture old values for audit
        old_values = self.serializer_class(task).data

        serializer = self.serializer_class(
            task,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        # Status objects
        in_progress = Status.objects.filter(name__iexact='In Progress').first() or Status.objects.filter(name__iexact='inprogress').first()
        completed = Status.objects.filter(name__iexact='Completed').first() or Status.objects.filter(name__iexact='Done').first()
        rejected = Status.objects.filter(name__iexact='Rejected').first()
        draft = Status.objects.filter(name__iexact='Draft').first()

        # ----------------- ACTION HANDLING -----------------
        # L1 Approve
        if action == 'L1_APPROVE':
            if not task.l1_approver or task.l1_approver != user:
                return Response({"error": "Only assigned L1 approver can approve"}, status=403)
            if status_lower not in ['submitted', 'submited', 'in progress']:
                return Response({"error": "Task must be in submitted or in progress state for L1 approval"}, status=400)

            serializer.validated_data['l1_approver'] = user
            serializer.validated_data['l1_approved_at'] = timezone.now()
            serializer.validated_data['l1_status'] = 'APPROVED'

            if task.user.second_level_manager:
                serializer.validated_data['l2_approver'] = task.user.second_level_manager
            if in_progress:
                serializer.validated_data['status'] = in_progress

        # L2 Approve
        if action == 'L2_APPROVE' and completed:
            if not task.l2_approver or task.l2_approver != user:
                return Response({"error": "Only assigned L2 approver can approve"}, status=403)
            serializer.validated_data['l2_approver'] = user
            serializer.validated_data['l2_approved_at'] = timezone.now()
            serializer.validated_data['l2_status'] = 'APPROVED'
            serializer.validated_data['status'] = completed

        # Submit
        if action == 'SUBMIT' and in_progress:
            if task.user != user:
                return Response({"error": "Only task owner can submit"}, status=403)
            if not task.user.first_level_manager:
                return Response({"error": "No reporting manager assigned"}, status=400)
            serializer.validated_data['status'] = in_progress
            serializer.validated_data['l1_approver'] = task.user.first_level_manager
            serializer.validated_data['l1_status'] = None
            serializer.validated_data['l2_status'] = None

        # L1 Reject
        if action == 'L1_REJECT' and rejected:
            if not task.l1_approver or task.l1_approver != user:
                return Response({"error": "Only assigned L1 approver can reject"}, status=403)
            serializer.validated_data['status'] = rejected
            serializer.validated_data['l1_rejected_at'] = timezone.now()
            serializer.validated_data['l1_status'] = 'REJECTED'

        # L2 Reject
        if action == 'L2_REJECT' and rejected:
            if not task.l2_approver or task.l2_approver != user:
                return Response({"error": "Only assigned L2 approver can reject"}, status=403)
            serializer.validated_data['status'] = rejected
            serializer.validated_data['l2_rejected_at'] = timezone.now()
            serializer.validated_data['l2_status'] = 'REJECTED'

        # Resubmit
        if action == 'RESUBMIT' and in_progress:
            if task.user != user:
                return Response({"error": "Only task owner can resubmit"}, status=403)
            serializer.validated_data['status'] = in_progress
            serializer.validated_data['l1_approved_at'] = None
            serializer.validated_data['l2_approved_at'] = None
            serializer.validated_data['l1_status'] = None
            serializer.validated_data['l2_status'] = None
            serializer.validated_data['l1_approver'] = task.user.first_level_manager
            serializer.validated_data['l2_approver'] = task.user.second_level_manager

        # ----------------- DEFAULT PAYLOAD UPDATES -----------------
        # Apply status from payload if no action
        if not action and request.data.get('status'):
            serializer.validated_data['status_id'] = request.data.get('status')

        # Update last modified
        serializer.validated_data['last_modified_by'] = user
        updated_task = serializer.save()

        # Capture new values for audit
        new_values = self.serializer_class(updated_task).data

        log_action = action if action in ['L1_APPROVE', 'L2_APPROVE', 'L1_REJECT', 'L2_REJECT', 'RESUBMIT'] else 'UPDATE'
        remarks = request.data.get('remarks') or f"Task {log_action.lower()}d"

        self._create_audit_log(
            task=updated_task,
            action=log_action,
            old_values=old_values,
            new_values=new_values,
            remarks=remarks
        )

        return Response(new_values)
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
    """
    Endpoint for L1/L2 approval, rejection, and resubmission
    """
    serializer_class = TaskListSerializer

    def post(self, request, pk):
        task = get_object_or_404(TaskList, pk=pk)
        user = request.user
        action = request.data.get('action')

        # Capture old values
        old_values = {
            'status': task.status.name if task.status else None,
            'l1_status': 'APPROVED' if task.l1_approved_at else ('REJECTED' if task.l1_rejected_at else None),
            'l2_status': 'APPROVED' if task.l2_approved_at else ('REJECTED' if task.l2_rejected_at else None),
        }

        # Status objects
        in_progress = Status.objects.filter(name__iexact='In Progress').first()
        completed = Status.objects.filter(name__iexact='Completed').first() or Status.objects.filter(name__iexact='Done').first()
        rejected = Status.objects.filter(name__iexact='Rejected').first()

        serializer = self.serializer_class(task, data={}, partial=True, context={'request': request})

        # ----------------- L1 Approve -----------------
        if action == 'L1_APPROVE':
            if task.l1_approver != user:
                return Response({"error": "Only assigned L1 approver can approve"}, status=403)
            if task.status.name.lower() not in ['submitted', 'submited', 'in progress']:
                return Response({"error": "Task must be in submitted/in progress state"}, status=400)

            serializer.validated_data['l1_approver'] = user
            serializer.validated_data['l1_approved_at'] = timezone.now()
            serializer.validated_data['l1_status'] = 'APPROVED'
            if task.user.second_level_manager:
                serializer.validated_data['l2_approver'] = task.user.second_level_manager
            if in_progress:
                serializer.validated_data['status'] = in_progress

        # ----------------- L2 Approve -----------------
        elif action == 'L2_APPROVE':
            if task.l2_approver != user:
                return Response({"error": "Only assigned L2 approver can approve"}, status=403)
            serializer.validated_data['l2_approver'] = user
            serializer.validated_data['l2_approved_at'] = timezone.now()
            serializer.validated_data['l2_status'] = 'APPROVED'
            serializer.validated_data['status'] = completed

        # ----------------- L1 Reject -----------------
        elif action == 'L1_REJECT':
            if task.l1_approver != user:
                return Response({"error": "Only assigned L1 approver can reject"}, status=403)
            serializer.validated_data['l1_rejected_at'] = timezone.now()
            serializer.validated_data['l1_status'] = 'REJECTED'
            serializer.validated_data['status'] = rejected

        # ----------------- L2 Reject -----------------
        elif action == 'L2_REJECT':
            if task.l2_approver != user:
                return Response({"error": "Only assigned L2 approver can reject"}, status=403)
            serializer.validated_data['l2_rejected_at'] = timezone.now()
            serializer.validated_data['l2_status'] = 'REJECTED'
            serializer.validated_data['status'] = rejected

        # ----------------- RESUBMIT -----------------
        elif action == 'RESUBMIT':
            if task.user != user:
                return Response({"error": "Only task owner can resubmit"}, status=403)
            serializer.validated_data['status'] = in_progress
            serializer.validated_data['l1_approved_at'] = None
            serializer.validated_data['l2_approved_at'] = None
            serializer.validated_data['l1_status'] = None
            serializer.validated_data['l2_status'] = None
            serializer.validated_data['l1_approver'] = task.user.first_level_manager
            serializer.validated_data['l2_approver'] = task.user.second_level_manager

        else:
            return Response({"error": "Invalid action"}, status=400)

        serializer.validated_data['last_modified_by'] = user
        updated_task = serializer.save()

        # Log audit
        new_values = {
            'status': updated_task.status.name if updated_task.status else None,
            'l1_status': 'APPROVED' if updated_task.l1_approved_at else ('REJECTED' if updated_task.l1_rejected_at else None),
            'l2_status': 'APPROVED' if updated_task.l2_approved_at else ('REJECTED' if updated_task.l2_rejected_at else None),
        }
        self._create_audit_log(updated_task, action, old_values=old_values, new_values=new_values)

        return Response(self.serializer_class(updated_task).data, status=200)

    def _create_audit_log(self, task, action, old_values=None, new_values=None):
        TaskListAuditLog.objects.create(
            task=task,
            action=action,
            performed_by=self.request.user,
            old_values=old_values or {},
            new_values=new_values or {},
            ip_address=self._get_client_ip(self.request),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            l1_status=task.l1_status,
            l2_status=task.l2_status,
            l1_action_by=task.l1_approver,
            l1_action_at=task.l1_approved_at,
            l2_action_by=task.l2_approver,
            l2_action_at=task.l2_approved_at,
            l1_rejected_at=task.l1_rejected_at,
            l2_rejected_at=task.l2_rejected_at,
        )

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
    
class BulkTaskListUpdate(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            task_ids = data.get("taskids", [])
            action = data.get("action")
            remarks = data.get("remarks", "")
            user = request.user

            # ✅ Validate input
            if not task_ids:
                return Response({"error": "taskids is required"}, status=400)

            VALID_ACTIONS = [
                'L1_APPROVE', 'L2_APPROVE',
                'L1_REJECT', 'L2_REJECT',
                'RESUBMIT'
            ]

            if action not in VALID_ACTIONS:
                return Response({"error": "Invalid action"}, status=400)

            tasks = TaskList.objects.filter(id__in=task_ids)

            if not tasks.exists():
                return Response({"error": "No valid tasks found"}, status=404)

            updated_tasks = []
            failed_tasks = []

            # Status objects
            in_progress = Status.objects.filter(name__iexact='In Progress').first()
            completed = Status.objects.filter(name__iexact='Completed').first()
            rejected = Status.objects.filter(name__iexact='Rejected').first()

            # ✅ Transaction safety
            with transaction.atomic():

                for task in tasks:

                    # ✅ Permission check (same as your get_object)
                    if not (
                        task.user == user or
                        task.l1_approver_id == user.id or
                        task.l2_approver_id == user.id or
                        user.is_staff
                    ):
                        failed_tasks.append({
                            "task_id": task.id,
                            "reason": "Permission denied"
                        })
                        continue

                    # Capture old values
                    old_values = {
                        'status': task.status.name if task.status else None,
                        'l1_status': 'APPROVED' if task.l1_approved_at else ('REJECTED' if task.l1_rejected_at else None),
                        'l2_status': 'APPROVED' if task.l2_approved_at else ('REJECTED' if task.l2_rejected_at else None),
                    }

                    try:
                        # ---------------- ACTION LOGIC ----------------

                        if action == 'L1_APPROVE':
                            if task.l1_approver_id != user.id:
                                raise Exception("Not L1 approver")

                            task.l1_approved_at = timezone.now()
                            task.l1_status = 'APPROVED'

                            if task.status and task.status.name.lower() == 'draft':
                                task.status = in_progress

                            task.l2_approver = task.user.second_level_manager

                        elif action == 'L2_APPROVE':
                            if task.l2_approver_id != user.id:
                                raise Exception("Not L2 approver")

                            task.l2_approved_at = timezone.now()
                            task.l2_status = 'APPROVED'
                            task.status = completed

                        elif action == 'L1_REJECT':
                            if task.l1_approver_id != user.id:
                                raise Exception("Not L1 approver")

                            task.l1_rejected_at = timezone.now()
                            task.l1_status = 'REJECTED'
                            task.status = rejected

                        elif action == 'L2_REJECT':
                            if task.l2_approver_id != user.id:
                                raise Exception("Not L2 approver")

                            task.l2_rejected_at = timezone.now()
                            task.l2_status = 'REJECTED'
                            task.status = rejected

                        elif action == 'RESUBMIT':
                            if task.user != user:
                                raise Exception("Only owner can resubmit")

                            task.status = in_progress
                            task.l1_approved_at = None
                            task.l2_approved_at = None
                            task.l1_rejected_at = None
                            task.l2_rejected_at = None
                            task.l1_status = None
                            task.l2_status = None
                            task.l1_approver = task.user.first_level_manager
                            task.l2_approver = task.user.second_level_manager

                        # Update modifier
                        task.last_modified_by = user
                        task.save()

                        # Capture new values
                        new_values = {
                            'status': task.status.name if task.status else None,
                            'l1_status': task.l1_status,
                            'l2_status': task.l2_status,
                        }

                        # ✅ Audit log (same style as your API)
                        TaskListAuditLog.objects.create(
                            task=task,
                            action=action,
                            performed_by=user,
                            old_values=old_values,
                            new_values=new_values,
                            remarks=remarks or f"Bulk {action.lower()}",
                        )

                        updated_tasks.append(task.id)

                    except Exception as e:
                        failed_tasks.append({
                            "task_id": task.id,
                            "reason": str(e)
                        })

            return Response({
                "message": "Bulk action completed",
                "success_count": len(updated_tasks),
                "failed_count": len(failed_tasks),
                "updated_task_ids": updated_tasks,
                "failed_tasks": failed_tasks
            }, status=200)

        except Exception as e:
            return Response({'error': str(e)}, status=500)
        
class TaskApproverAPIView(APIView):
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




# class TaskListAuditLogAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, task_id=None):
#         if task_id:
#             task = get_object_or_404(TaskList, pk=task_id)
#             if task.user != request.user and not request.user.is_staff:
#                 raise PermissionDenied()
#             logs = TaskListAuditLog.objects.filter(task=task).order_by('-created_at')
#         else:
#             if request.user.is_staff:
#                 logs = TaskListAuditLog.objects.all().order_by('-created_at')
#             else:
#                 logs = TaskListAuditLog.objects.filter(task__user=request.user).order_by('-created_at')

#         serializer = TaskListAuditLogSerializer(logs, many=True)
#         return Response(serializer.data)

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
    

class DailyTimelineAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskListSerializer

    def get(self, request):
        today = timezone.localdate()
        user = request.user

        queryset = TaskList.objects.select_related(
            'platform', 'task', 'subtask', 'status',
            'l1_approver', 'l2_approver'
        ).filter(date=today)

        # If not staff → show only own tasks
        if not user.is_staff:
            queryset = queryset.filter(user=user)

        queryset = queryset.order_by('created_at')

        return Response(self.serializer_class(queryset, many=True).data)
    

# Work Hours Overview
# class WorkHoursOverviewAPIView(APIView):
#     """
#     Work hours overview API
    
#     Supported views:
#     • ?view=week          → current week (Mon–Sun)
#     • ?view=week&year=2026&week=6   → specific week
#     • ?view=year          → current year (all 12 months summary)
#     • ?view=year&year=2026   → specific year (all 12 months)
#     """
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         user = request.user
#         today = timezone.now().date()

#         view_mode = request.query_params.get('view', 'week').lower()

#         if view_mode not in ['week', 'year']:
#             return Response(
#                 {"error": "Invalid view parameter. Use ?view=week or ?view=year"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         year = int(request.query_params.get('year', today.year))

#         # ────────────────────────────────────────────────
#         # WEEK VIEW
#         # ────────────────────────────────────────────────
#         if view_mode == 'week':
#             week_input = request.query_params.get('week')

#             if week_input:
#                 if '-W' in week_input:
#                     try:
#                         y, w = week_input.split('-W')
#                         year = int(y)
#                         week_num = int(w)
#                     except Exception:
#                         return Response({"error": "Invalid week format (use YYYY-WWW)"}, status=400)
#                 else:
#                     try:
#                         week_num = int(week_input)
#                     except Exception:
#                         return Response({"error": "Invalid week number"}, status=400)
#             else:
#                 # current week
#                 _, week_num, _ = today.isocalendar()

#             # Calculate Monday of target week
#             jan4 = date(year, 1, 4)
#             monday_week1 = jan4 - timedelta(days=jan4.weekday())
#             start_date = monday_week1 + timedelta(weeks=week_num - 1)
#             end_date = start_date + timedelta(days=6)

#             title_key = "week"
#             title_value = f"{year}-W{week_num:02d}"
#             range_str = f"{start_date.isoformat()} to {end_date.isoformat()}"

#             # Query & aggregate per day
#             qs = TaskList.objects.filter(date__range=[start_date, end_date])
#             if not user.is_staff:
#                 qs = qs.filter(user=user)

#             daily_agg = qs.values('date').annotate(
#                 total_duration=Sum('duration'),
#                 entry_count=Count('id')
#             )

#             daily_map = {
#                 row['date']: {
#                     'duration': float(row['total_duration'] or 0.0),
#                     'count': row['entry_count']
#                 }
#                 for row in daily_agg
#             }

#             days = []
#             total_hours = 0.0
#             total_entries = 0
#             day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

#             current = start_date
#             for i in range(7):
#                 data = daily_map.get(current, {'duration': 0.0, 'count': 0})
#                 hours_str = f"{data['duration']:.2f}"

#                 days.append({
#                     "day": day_names[i],
#                     "date": current.isoformat(),
#                     "duration_hours": hours_str,
#                     "entry_count": data['count']
#                 })

#                 total_hours += data['duration']
#                 total_entries += data['count']
#                 current += timedelta(days=1)

#             return Response({
#                 "status": "success",
#                 "view": "week",
#                 title_key: title_value,
#                 "date_range": range_str,
#                 "total_hours": f"{total_hours:.2f}",
#                 "total_entries": total_entries,
#                 "days": days
#             })

#         # ────────────────────────────────────────────────
#         # YEAR VIEW - summary per month
#         # ────────────────────────────────────────────────
#         else:  # view == 'year'
#             yearly_data = []
#             yearly_total_hours = 0.0
#             yearly_total_entries = 0

#             for m in range(1, 13):
#                 try:
#                     month_start = date(year, m, 1)
#                     next_month_start = date(year + 1, 1, 1) if m == 12 else date(year, m + 1, 1)
#                     month_end = next_month_start - timedelta(days=1)
#                 except ValueError:
#                     continue

#                 qs = TaskList.objects.filter(date__range=[month_start, month_end])
#                 if not user.is_staff:
#                     qs = qs.filter(user=user)

#                 agg = qs.aggregate(
#                     total_duration=Sum('duration'),
#                     entry_count=Count('id'),
#                     active_days=Count('date', distinct=True)
#                 )

#                 hours = float(agg['total_duration'] or 0.0)
#                 entries = agg['entry_count'] or 0
#                 active_days_count = agg['active_days'] or 0

#                 yearly_data.append({
#                     "month": month_start.strftime("%Y-%m"),
#                     "month_name": month_start.strftime("%B"),
#                     "total_hours": f"{hours:.2f}",
#                     "entry_count": entries,
#                     "days_with_entries": active_days_count
#                 })

#                 yearly_total_hours += hours
#                 yearly_total_entries += entries

#             return Response({
#                 "status": "success",
#                 "view": "year",
#                 "year": str(year),
#                 "total_hours": f"{yearly_total_hours:.2f}",
#                 "total_entries": yearly_total_entries,
#                 "months": yearly_data
#             })
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import date, timedelta
from .models import TaskList

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

    def parse_duration_to_hours(self, duration_str):
        """Convert duration string like '1h 30m' to decimal hours (1.5)"""
        if not duration_str:
            return 0
        
        if isinstance(duration_str, (int, float)):
            return float(duration_str)
        
        duration_str = str(duration_str).strip()
        
        try:
            return float(duration_str)
        except ValueError:
            pass
        
        hours = 0
        minutes = 0
        
        hour_match = re.search(r'(\d+(?:\.\d+)?)\s*h', duration_str, re.IGNORECASE)
        if hour_match:
            hours = float(hour_match.group(1))
        
        minute_match = re.search(r'(\d+(?:\.\d+)?)\s*m', duration_str, re.IGNORECASE)
        if minute_match:
            minutes = float(minute_match.group(1))
        
        if not hour_match and not minute_match:
            try:
                return float(duration_str)
            except ValueError:
                return 0
        
        return hours + (minutes / 60)

    def format_hours_to_duration(self, hours):
        """Convert decimal hours (2.5) to readable format like '2h 30m'"""
        if not hours or hours == 0:
            return "0h"
        
        total_minutes = int(hours * 60)
        h = total_minutes // 60
        m = total_minutes % 60
        
        if h > 0 and m > 0:
            return f"{h}h {m}m"
        elif h > 0:
            return f"{h}h"
        else:
            return f"{m}m"

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

            # Get all entries in date range
            qs = TaskList.objects.filter(date__range=[start_date, end_date])
            if not user.is_staff:
                qs = qs.filter(user=user)

            # Get all entries with their duration strings
            entries = qs.values('date', 'duration')
            
            # Aggregate manually since durations are strings
            daily_map = {}
            for entry in entries:
                entry_date = entry['date']
                duration_str = entry['duration']
                hours = self.parse_duration_to_hours(duration_str)
                
                if entry_date not in daily_map:
                    daily_map[entry_date] = {
                        'duration': 0.0,
                        'count': 0
                    }
                daily_map[entry_date]['duration'] += hours
                daily_map[entry_date]['count'] += 1

            days = []
            total_hours = 0.0
            total_entries = 0
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

            current = start_date
            for i in range(7):
                data = daily_map.get(current, {'duration': 0.0, 'count': 0})
                
                # Format hours to readable format
                formatted_hours = self.format_hours_to_duration(data['duration'])
                
                days.append({
                    "day": day_names[i],
                    "date": current.isoformat(),
                    "duration_hours": formatted_hours,  # Now returns "2h 30m" instead of "2.50"
                    "duration_decimal": round(data['duration'], 2),  # Optional: keep decimal for calculations
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
                "total_hours": self.format_hours_to_duration(total_hours),  # Formatted total
                "total_hours_decimal": round(total_hours, 2),  # Optional: decimal total
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

                # Get all entries for this month
                qs = TaskList.objects.filter(date__range=[month_start, month_end])
                if not user.is_staff:
                    qs = qs.filter(user=user)

                # Get all entries with their duration strings
                entries = qs.values('date', 'duration')
                
                # Calculate totals manually
                month_hours = 0.0
                unique_dates = set()
                entry_count = 0
                
                for entry in entries:
                    duration_str = entry['duration']
                    hours = self.parse_duration_to_hours(duration_str)
                    month_hours += hours
                    entry_count += 1
                    unique_dates.add(entry['date'])
                
                active_days_count = len(unique_dates)

                yearly_data.append({
                    "month": month_start.strftime("%Y-%m"),
                    "month_name": month_start.strftime("%B"),
                    "total_hours": self.format_hours_to_duration(month_hours),  # Formatted hours
                    "total_hours_decimal": round(month_hours, 2),  # Optional: decimal
                    "entry_count": entry_count,
                    "days_with_entries": active_days_count
                })

                yearly_total_hours += month_hours
                yearly_total_entries += entry_count

            return Response({
                "status": "success",
                "view": "year",
                "year": str(year),
                "total_hours": self.format_hours_to_duration(yearly_total_hours),  # Formatted total
                "total_hours_decimal": round(yearly_total_hours, 2),  # Optional: decimal
                "total_entries": yearly_total_entries,
                "months": yearly_data
            })

# class TopMembersAPIView(APIView):
#     """
#     GET /api/top-members/
    
#     Returns top users ranked by total task hours (shown as hrs + mins).
    
#     Query params:
#     - limit: number of top members (default 10, max 50)
#     - period: overall / today (default: overall)
#     """
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         limit = min(int(request.query_params.get('limit', 10)), 50)
#         period = request.query_params.get('period', 'overall').lower()

#         today = timezone.now().date()

#         # Base queryset: all tasks (adjust status filter if you only want completed)
#         qs = TaskList.objects.all()

#         # Date filter
#         if period == 'today':
#             qs = qs.filter(date=today)
#         elif period == 'overall':
#             pass  # all time
#         else:
#             return Response({"error": "Invalid period. Use: overall / today"}, status=400)

#         if not request.user.is_staff:
#             qs = qs.filter(user=request.user)

#         # Aggregate: total duration (decimal) + task count per user
#         top_members = qs.values(
#             'user__id',
#             'user__name',
#             'user__firstname',
#             'user__email'
#         ).annotate(
#             total_duration=Sum('duration', default=0),
#             task_count=Count('id')
#         ).order_by('-total_duration')[:limit]

#         # Format result with hrs + mins
#         result = []
#         rank = 1
#         for row in top_members:
#             total_hours_decimal = float(row['total_duration'] or 0)  # decimal → float
#             hours = int(total_hours_decimal)
#             minutes = int((total_hours_decimal - hours) * 60)

#             name = row['user__firstname'] or row['user__name'] or "Unknown User"
#             username = row['user__name'] or row['user__email'] or "N/A"

#             result.append({
#                 "rank": rank,
#                 "user_id": row['user__id'],
#                 "name": name,
#                 "username": username,
#                 "total_time": f"{hours} hrs {minutes} mins",
#                 "total_hours_decimal": f"{total_hours_decimal:.2f}",
#                 "task_count": row['task_count']
#             })
#             rank += 1

#         total_members = User.objects.filter(is_active=True).count()

#         return Response({
#             "status": "success",
#             "total_members_in_system": total_members,
#             "period": period.capitalize(),
#             "top_members_count": len(result),
#             "top_members": result
#         })
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import TaskList

User = get_user_model()

class TopMembersAPIView(APIView):
    """
    GET /task/top-members/
    
    Returns top users ranked by total task hours (shown as hrs + mins).
    
    Query params:
    - limit: number of top members (default 10, max 50)
    - period: overall / today (default: overall)
    """
    permission_classes = [IsAuthenticated]

    def parse_duration_to_hours(self, duration_str):
        """Convert duration string like '4.50', '1h 30m', or '4h 30m' to decimal hours (4.5)"""
        if not duration_str:
            return 0
        
        if isinstance(duration_str, (int, float)):
            return float(duration_str)
        
        duration_str = str(duration_str).strip()
        
        # Try parsing as decimal number first
        try:
            return float(duration_str)
        except ValueError:
            pass
        
        # Parse "Xh Ym" format
        hours = 0
        minutes = 0
        
        hour_match = re.search(r'(\d+(?:\.\d+)?)\s*h', duration_str, re.IGNORECASE)
        if hour_match:
            hours = float(hour_match.group(1))
        
        minute_match = re.search(r'(\d+(?:\.\d+)?)\s*m', duration_str, re.IGNORECASE)
        if minute_match:
            minutes = float(minute_match.group(1))
        
        # If no patterns matched, try to convert directly
        if not hour_match and not minute_match:
            try:
                return float(duration_str)
            except ValueError:
                return 0
        
        return hours + (minutes / 60)

    def format_hours_to_duration(self, hours):
        """Convert decimal hours (2.5) to readable format like '2h 30m'"""
        if not hours or hours == 0:
            return "0h"
        
        total_minutes = int(hours * 60)
        h = total_minutes // 60
        m = total_minutes % 60
        
        if h > 0 and m > 0:
            return f"{h}h {m}m"
        elif h > 0:
            return f"{h}h"
        else:
            return f"{m}m"

    def get(self, request):
        limit = min(int(request.query_params.get('limit', 10)), 50)
        period = request.query_params.get('period', 'overall').lower()

        today = timezone.now().date()

        # Base queryset: all tasks
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

        # Get all tasks with user and duration data
        # Use the actual field names from your User model
        tasks = qs.select_related('user').values(
            'user__id',
            'user__firstname',  # Use firstname instead of username
            'user__email',
            'duration'
        )

        # Manual aggregation by user
        user_data = {}
        
        for task in tasks:
            user_id = task['user__id']
            
            if not user_id:
                continue
                
            duration_str = task['duration']
            hours = self.parse_duration_to_hours(duration_str)
            
            if user_id not in user_data:
                user_data[user_id] = {
                    'user_id': user_id,
                    'firstname': task['user__firstname'],
                    'email': task['user__email'],
                    'total_hours': 0,
                    'task_count': 0
                }
            
            user_data[user_id]['total_hours'] += hours
            user_data[user_id]['task_count'] += 1

        # Convert to list and sort by total_hours
        top_members_list = list(user_data.values())
        top_members_list.sort(key=lambda x: x['total_hours'], reverse=True)
        top_members_list = top_members_list[:limit]

        # Format result with hrs + mins
        result = []
        rank = 1
        for row in top_members_list:
            total_hours = row['total_hours']
            
            # Get name - use firstname, fallback to email if needed
            name = row['firstname'] or "Unknown User"
            display_name = row['firstname'] or row['email'] or "N/A"

            result.append({
                "rank": rank,
                "user_id": row['user_id'],
                "name": name,
                "display_name": display_name,
                "email": row['email'],
                "total_time": self.format_hours_to_duration(total_hours),
                "total_hours_decimal": f"{total_hours:.2f}",
                "task_count": row['task_count']
            })
            rank += 1

        # Get total active members - adjust based on your User model
        # You might have an 'is_active' field or similar
        try:
            total_members = User.objects.filter(is_active=True).count()
        except:
            # If is_active field doesn't exist, count all users
            total_members = User.objects.count()

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
# class TimeDistributionAPIView(APIView):

#     def get(self, request):
#         user = request.user
#         view_type = request.query_params.get("view", "daily")

#         today = timezone.now().date()

#         # ---------------- DATE FILTER ----------------
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

#         # ---------------- USER FILTER ----------------
#         if not user.is_staff:
#             queryset = queryset.filter(user=user)

#         # ---------------- AGGREGATION ----------------
#         data = (
#             queryset
#             .values("task__name")
#             .annotate(total_hours=Sum("duration"))
#             .order_by("-total_hours")
#         )

#         labels = [d["task__name"] for d in data if d["task__name"]]
#         series = [float(d["total_hours"] or 0) for d in data if d["task__name"]]

#         return Response({
#             "labels": labels if labels else ["No Data"],
#             "series": series if series else [0]
#         })
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from .models import TaskList

class TimeDistributionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def parse_duration_to_hours(self, duration_str):
        """Convert duration string like '1h 30m' to decimal hours (1.5)"""
        if not duration_str:
            return 0
        
        if isinstance(duration_str, (int, float)):
            return float(duration_str)
        
        duration_str = str(duration_str).strip()
        
        try:
            return float(duration_str)
        except ValueError:
            pass
        
        hours = 0
        minutes = 0
        
        hour_match = re.search(r'(\d+(?:\.\d+)?)\s*h', duration_str, re.IGNORECASE)
        if hour_match:
            hours = float(hour_match.group(1))
        
        minute_match = re.search(r'(\d+(?:\.\d+)?)\s*m', duration_str, re.IGNORECASE)
        if minute_match:
            minutes = float(minute_match.group(1))
        
        if not hour_match and not minute_match:
            try:
                return float(duration_str)
            except ValueError:
                return 0
        
        return hours + (minutes / 60)

    def format_hours_to_duration(self, hours):
        """Convert decimal hours (2.5) to readable format like '2h 30m'"""
        if not hours or hours == 0:
            return "0h"
        
        total_minutes = int(hours * 60)
        h = total_minutes // 60
        m = total_minutes % 60
        
        if h > 0 and m > 0:
            return f"{h}h {m}m"
        elif h > 0:
            return f"{h}h"
        else:
            return f"{m}m"

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

        # Get all entries with their duration strings
        entries = queryset.values("task__name", "duration")
        
        # Aggregate durations manually since they're stored as strings
        task_durations = {}
        for entry in entries:
            task_name = entry["task__name"]
            if not task_name:  # Skip tasks without name
                continue
                
            duration_str = entry["duration"]
            hours = self.parse_duration_to_hours(duration_str)
            
            if task_name not in task_durations:
                task_durations[task_name] = 0
            task_durations[task_name] += hours
        
        # Convert to list and sort by total hours
        tasks_list = [
            {"task__name": task_name, "total_hours": total_hours}
            for task_name, total_hours in task_durations.items()
        ]
        tasks_list.sort(key=lambda x: x["total_hours"], reverse=True)
        
        # Prepare response data
        labels = [task["task__name"] for task in tasks_list]
        series = [round(task["total_hours"], 1) for task in tasks_list]  # Decimal hours for chart
        
        # Optional: Also provide formatted hours for display
        formatted_series = [self.format_hours_to_duration(task["total_hours"]) for task in tasks_list]

        return Response({
            "labels": labels if labels else ["No Data"],
            "series": series if series else [0],
            "formatted_series": formatted_series if formatted_series else ["0h"],  # For display
            "view": view_type,
            "total_hours": self.format_hours_to_duration(sum(series)),
            "total_hours_decimal": round(sum(series), 1)
        })


# class RecentTasksAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         user = request.user

#         # Get last 10 tasks
#         queryset = (
#             TaskList.objects
#             .select_related("task", "platform", "status")
#             .filter(user=user)
#             .order_by("-date", "-id")[:10]
#         )

#         data = []

#         for task in queryset:
#             # ✅ Convert decimal hours → "Xh Ym"
#             total_hours = float(task.duration or 0)
#             hours = int(total_hours)
#             minutes = int(round((total_hours - hours) * 60))

#             duration_str = f"{hours}h {minutes}m" if hours else f"{minutes}m"

#             data.append({
#                 "id": task.id,
#                 "task": task.task.name if task.task else "",
#                 "platform": task.platform.name if task.platform else "",
#                 "date": task.date.strftime("%d %b %Y") if task.date else "",
#                 "duration": duration_str,
#                 "status": task.status.name if task.status else "",
#             })

#         return Response(data)
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import TaskList

class RecentTasksAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def parse_duration_to_hours(self, duration_str):
        """Convert duration string like '1h 30m' to decimal hours (1.5)"""
        if not duration_str:
            return 0
        
        if isinstance(duration_str, (int, float)):
            return float(duration_str)
        
        duration_str = str(duration_str).strip()
        
        try:
            return float(duration_str)
        except ValueError:
            pass
        
        hours = 0
        minutes = 0
        
        hour_match = re.search(r'(\d+(?:\.\d+)?)\s*h', duration_str, re.IGNORECASE)
        if hour_match:
            hours = float(hour_match.group(1))
        
        minute_match = re.search(r'(\d+(?:\.\d+)?)\s*m', duration_str, re.IGNORECASE)
        if minute_match:
            minutes = float(minute_match.group(1))
        
        if not hour_match and not minute_match:
            try:
                return float(duration_str)
            except ValueError:
                return 0
        
        return hours + (minutes / 60)

    def format_hours_to_duration(self, hours):
        """Convert decimal hours (2.5) to readable format like '2h 30m'"""
        if not hours or hours == 0:
            return "0h"
        
        total_minutes = int(hours * 60)
        h = total_minutes // 60
        m = total_minutes % 60
        
        if h > 0 and m > 0:
            return f"{h}h {m}m"
        elif h > 0:
            return f"{h}h"
        else:
            return f"{m}m"

    def get(self, request):
        user = request.user

        # Get last 10 tasks
        queryset = (
            TaskList.objects
            .select_related("task", "platform", "status", "subtask")
            .filter(user=user)
            .order_by("-date", "-id")[:10]
        )

        data = []

        for task in queryset:
            # Parse duration string to hours
            total_hours = self.parse_duration_to_hours(task.duration)
            
            # Format hours to readable duration string
            duration_str = self.format_hours_to_duration(total_hours)

            data.append({
                "id": task.id,
                "task": task.task.name if task.task else "",
                "subtask": task.subtask.name if task.subtask else "",
                "platform": task.platform.name if task.platform else "",
                "date": task.date.strftime("%d %b %Y") if task.date else "",
                "duration": duration_str,  # Formatted like "2h 30m"
                "duration_decimal": round(total_hours, 2),  # Optional: decimal version
                "status": task.status.name if task.status else "",
                "description": task.description if task.description else "",
                "bitrix_id": task.bitrix_id if task.bitrix_id else ""
            })

        return Response(data)
# class TopUsedTasksAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         user = request.user

#         # Aggregate total duration per task
#         tasks = (
#             TaskList.objects
#             .filter(user=user)
#             .values("task", "task__name")   # adjust if field is task_name
#             .annotate(total_duration=Sum("duration"))
#             .order_by("-total_duration")[:10]
#         )

#         # Total time (for percentage calculation)
#         total_time = sum(float(t["total_duration"] or 0) for t in tasks)

#         data = []
#         for i, task in enumerate(tasks, start=1):
#             hours = float(task["total_duration"] or 0)

#             percentage = (hours / total_time * 100) if total_time > 0 else 0

#             data.append({
#                 "id": i,
#                 "task": task["task__name"],  
#                 "hours": round(hours, 1),
#                 "percentage": round(percentage),
#             })

#         return Response(data)
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import TaskList

class TopUsedTasksAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def parse_duration_to_hours(self, duration_str):
        """Convert duration string like '1h 30m' to decimal hours (1.5) for calculation"""
        if not duration_str:
            return 0
        
        if isinstance(duration_str, (int, float)):
            return float(duration_str)
        
        duration_str = str(duration_str).strip()
        
        try:
            return float(duration_str)
        except ValueError:
            pass
        
        hours = 0
        minutes = 0
        
        hour_match = re.search(r'(\d+(?:\.\d+)?)\s*h', duration_str, re.IGNORECASE)
        if hour_match:
            hours = float(hour_match.group(1))
        
        minute_match = re.search(r'(\d+(?:\.\d+)?)\s*m', duration_str, re.IGNORECASE)
        if minute_match:
            minutes = float(minute_match.group(1))
        
        if not hour_match and not minute_match:
            try:
                return float(duration_str)
            except ValueError:
                return 0
        
        return hours + (minutes / 60)

    def format_hours_to_duration(self, hours):
        """Convert decimal hours (2.5) to readable format like '2h 30m'"""
        if not hours or hours == 0:
            return "0h"
        
        total_minutes = int(hours * 60)
        h = total_minutes // 60
        m = total_minutes % 60
        
        if h > 0 and m > 0:
            return f"{h}h {m}m"
        elif h > 0:
            return f"{h}h"
        else:
            return f"{m}m"

    def get(self, request):
        user = request.user
        
        # Get all tasks with their duration strings
        task_entries = TaskList.objects.filter(user=user).values("task", "task__name", "duration")
        
        # Aggregate durations
        task_durations = {}
        for entry in task_entries:
            task_id = entry["task"]
            task_name = entry["task__name"]
            duration_str = entry["duration"]
            
            hours = self.parse_duration_to_hours(duration_str)
            
            if task_id not in task_durations:
                task_durations[task_id] = {
                    "name": task_name,
                    "total_hours": 0
                }
            task_durations[task_id]["total_hours"] += hours
        
        # Convert to list and sort by total hours
        tasks_list = [
            {
                "task__name": data["name"],
                "total_hours": data["total_hours"]
            }
            for data in task_durations.values()
        ]
        
        tasks_list.sort(key=lambda x: x["total_hours"], reverse=True)
        tasks = tasks_list[:10]
        
        # Calculate total time
        total_time = sum(t["total_hours"] for t in tasks)
        
        data = []
        for i, task in enumerate(tasks, start=1):
            hours = task["total_hours"]
            percentage = (hours / total_time * 100) if total_time > 0 else 0
            
            data.append({
                "id": i,
                "task": task["task__name"],
                "hours": self.format_hours_to_duration(hours),  # This returns "2h 30m" instead of 2.5
                "hours_decimal": round(hours, 1),  # Optional: keep decimal for calculations
                "percentage": round(percentage),
            })
        
        return Response(data)
# class TopPlatformsAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         user = request.user
#         view_type = request.query_params.get("view", "monthly")

#         today = timezone.now().date()

#         # ---------------- DATE FILTER ----------------
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

#         # ---------------- APPROVER FILTER ----------------
#         if not user.is_staff:
#             queryset = queryset.filter(
#                 Q(l1_approver=user) |
#                 Q(l2_approver=user) |
#                 Q(user__first_level_manager=user) |
#                 Q(user__second_level_manager=user)
#             )

#         # ---------------- AGGREGATION ----------------
#         data = (
#             queryset
#             .values("platform__id", "platform__name")
#             .annotate(
#                 total_hours=Sum("duration"),
#                 user_count=Count("user", distinct=True)
#             )
#             .order_by("-total_hours")[:5]
#         )

#         total_hours_all = sum([float(d["total_hours"] or 0) for d in data]) or 1

#         response = []

#         for d in data:
#             usage_percent = round((float(d["total_hours"]) / total_hours_all) * 100)

#             response.append({
#                 "name": d["platform__name"],
#                 "users": f"{d['user_count']} Active Users",
#                 "usage": usage_percent
#             })

#         return Response(response)
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from .models import TaskList

class TopPlatformsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def parse_duration_to_hours(self, duration_str):
        """Convert duration string like '4.50', '1h 30m', or '4h 30m' to decimal hours (4.5)"""
        if not duration_str:
            return 0
        
        if isinstance(duration_str, (int, float)):
            return float(duration_str)
        
        duration_str = str(duration_str).strip()
        
        # Try parsing as decimal number first
        try:
            return float(duration_str)
        except ValueError:
            pass
        
        # Parse "Xh Ym" format
        hours = 0
        minutes = 0
        
        hour_match = re.search(r'(\d+(?:\.\d+)?)\s*h', duration_str, re.IGNORECASE)
        if hour_match:
            hours = float(hour_match.group(1))
        
        minute_match = re.search(r'(\d+(?:\.\d+)?)\s*m', duration_str, re.IGNORECASE)
        if minute_match:
            minutes = float(minute_match.group(1))
        
        # If no patterns matched, try to convert directly
        if not hour_match and not minute_match:
            try:
                return float(duration_str)
            except ValueError:
                return 0
        
        return hours + (minutes / 60)

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

        # Get all tasks with platform and duration data
        tasks = queryset.select_related('platform', 'user').values(
            'platform__id',
            'platform__name',
            'duration',
            'user_id'
        )

        # Manual aggregation by platform
        platform_data = {}
        
        for task in tasks:
            platform_id = task['platform__id']
            platform_name = task['platform__name']
            
            if not platform_id:
                continue
                
            duration_str = task['duration']
            hours = self.parse_duration_to_hours(duration_str)
            
            if platform_id not in platform_data:
                platform_data[platform_id] = {
                    'platform_id': platform_id,
                    'platform_name': platform_name,
                    'total_hours': 0,
                    'users': set()  # Use set for unique users
                }
            
            platform_data[platform_id]['total_hours'] += hours
            
            # Add unique user
            if task['user_id']:
                platform_data[platform_id]['users'].add(task['user_id'])

        # Convert to list and sort by total_hours
        platforms_list = []
        for platform_id, data in platform_data.items():
            platforms_list.append({
                'platform_id': platform_id,
                'platform_name': data['platform_name'],
                'total_hours': data['total_hours'],
                'user_count': len(data['users'])
            })
        
        # Sort by total hours descending and get top 5
        platforms_list.sort(key=lambda x: x['total_hours'], reverse=True)
        top_platforms = platforms_list[:5]

        # Calculate total hours for percentage
        total_hours_all = sum(p['total_hours'] for p in top_platforms)
        
        # Prevent division by zero
        if total_hours_all == 0:
            total_hours_all = 1

        # Build response
        response = []
        for platform in top_platforms:
            usage_percent = round((platform['total_hours'] / total_hours_all) * 100)
            
            # Format user count text
            user_count_text = f"{platform['user_count']} Active User{'s' if platform['user_count'] != 1 else ''}"
            
            response.append({
                "name": platform['platform_name'],
                "users": user_count_text,
                "usage": usage_percent,
                # Optional: include raw data for debugging
                "_metadata": {
                    "total_hours": round(platform['total_hours'], 2),
                    "user_count": platform['user_count']
                }
            })

        return Response({
            "status": "success",
            "view": view_type,
            "date_range": self._get_date_range_description(view_type, today),
            "top_platforms": response
        })
    
    def _get_date_range_description(self, view_type, today):
        """Get human-readable date range description"""
        if view_type == "daily":
            return f"Today ({today.strftime('%Y-%m-%d')})"
        elif view_type == "weekly":
            start_date = today - timedelta(days=7)
            return f"Last 7 days ({start_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})"
        elif view_type == "monthly":
            start_date = today - timedelta(days=30)
            return f"Last 30 days ({start_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})"
        return "Unknown range"    

# class PlatformPerformanceAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         user = request.user
#         view_type = request.query_params.get("view", "monthly")

#         today = timezone.now().date()

#         # ---------------- DATE FILTER ----------------
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

#         # ---------------- APPROVER FILTER ----------------
#         if not user.is_staff:
#             queryset = queryset.filter(
#                 Q(l1_approver=user) |
#                 Q(l2_approver=user) |
#                 Q(user__first_level_manager=user) |
#                 Q(user__second_level_manager=user)
#             )

#         # ---------------- GROUP BY PLATFORM ----------------
#         platforms = (
#             queryset
#             .values("platform__id", "platform__name")
#             .annotate(
#                 total_hours=Sum("duration"),
#                 total_tasks=Count("id"),
#                 users=Count("user", distinct=True),
#                 completed_tasks=Count("id", filter=Q(status__name__iexact="Completed")),
#                 approved_tasks=Count("id", filter=Q(l1_approved_at__isnull=False)),
#                 integrated_tasks=Count("id", filter=Q(bitrix_id__isnull=False))
#             )
#         )

#         series = []

#         for p in platforms:
#             users = p["users"] or 1
#             total_tasks = p["total_tasks"] or 1

#             # ---------------- METRICS ----------------
#             active_users = min(users * 10, 100)  

#             performance = min(int((float(p["total_hours"] or 0) / users) * 10), 100)

#             reliability = int((p["approved_tasks"] / total_tasks) * 100)

#             integration = int((p["integrated_tasks"] / total_tasks) * 100)

#             satisfaction = int((p["completed_tasks"] / total_tasks) * 100)

#             series.append({
#                 "name": p["platform__name"],
#                 "data": [
#                     active_users,
#                     performance,
#                     reliability,
#                     integration,
#                     satisfaction
#                 ]
#             })

#         return Response({
#             "categories": [
#                 "Active Users",
#                 "Performance",
#                 "Reliability",
#                 "Integration",
#                 "Satisfaction"
#             ],
#             "series": series
#         })
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from .models import TaskList

class PlatformPerformanceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def parse_duration_to_hours(self, duration_str):
        """Convert duration string like '4.50', '1h 30m', or '4h 30m' to decimal hours (4.5)"""
        if not duration_str:
            return 0
        
        if isinstance(duration_str, (int, float)):
            return float(duration_str)
        
        duration_str = str(duration_str).strip()
        
        # Try parsing as decimal number first
        try:
            return float(duration_str)
        except ValueError:
            pass
        
        # Parse "Xh Ym" format
        hours = 0
        minutes = 0
        
        hour_match = re.search(r'(\d+(?:\.\d+)?)\s*h', duration_str, re.IGNORECASE)
        if hour_match:
            hours = float(hour_match.group(1))
        
        minute_match = re.search(r'(\d+(?:\.\d+)?)\s*m', duration_str, re.IGNORECASE)
        if minute_match:
            minutes = float(minute_match.group(1))
        
        # If no patterns matched, try to convert directly
        if not hour_match and not minute_match:
            try:
                return float(duration_str)
            except ValueError:
                return 0
        
        return hours + (minutes / 60)

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

        # Get all tasks with platform and duration data
        tasks = queryset.select_related('platform', 'status').values(
            'platform__id', 
            'platform__name', 
            'duration',
            'status__name',
            'user_id',
            'bitrix_id',
            'l1_approved_at'
        )

        # Manual aggregation by platform
        platform_data = {}
        
        for task in tasks:
            platform_id = task['platform__id']
            platform_name = task['platform__name']
            
            if not platform_id:
                continue
                
            duration_str = task['duration']
            hours = self.parse_duration_to_hours(duration_str)
            
            if platform_id not in platform_data:
                platform_data[platform_id] = {
                    'platform_id': platform_id,
                    'platform_name': platform_name,
                    'total_hours': 0,
                    'total_tasks': 0,
                    'users': set(),  # Use set for unique users
                    'completed_tasks': 0,
                    'approved_tasks': 0,
                    'integrated_tasks': 0
                }
            
            platform_data[platform_id]['total_hours'] += hours
            platform_data[platform_id]['total_tasks'] += 1
            
            # Add unique user
            if task['user_id']:
                platform_data[platform_id]['users'].add(task['user_id'])
            
            # Check for completed status
            status_name = task['status__name']
            if status_name and status_name.lower() in ['completed', 'done', 'finished']:
                platform_data[platform_id]['completed_tasks'] += 1
            
            # Check for approved tasks (l1_approved_at is not null)
            if task['l1_approved_at']:
                platform_data[platform_id]['approved_tasks'] += 1
            
            # Check for integrated tasks (has bitrix_id)
            if task['bitrix_id']:
                platform_data[platform_id]['integrated_tasks'] += 1

        # Build response series
        series = []
        
        for platform_id, data in platform_data.items():
            users_count = len(data['users'])
            total_tasks = data['total_tasks']
            total_hours = data['total_hours']
            
            # Avoid division by zero
            if users_count == 0:
                users_count = 1
            if total_tasks == 0:
                total_tasks = 1
            
            # ---------------- METRICS CALCULATIONS ----------------
            
            # Active Users (scored 0-100 based on user count)
            # Assuming max 10 users per platform for scoring
            active_users = min(int((users_count / 10) * 100), 100) if users_count <= 10 else 100
            
            # Performance (hours per user, scaled to 0-100)
            # Assuming 40 hours per user is excellent (full work week)
            hours_per_user = total_hours / users_count
            performance = min(int((hours_per_user / 40) * 100), 100)
            
            # Reliability (% of approved tasks)
            reliability = int((data['approved_tasks'] / total_tasks) * 100)
            
            # Integration (% of tasks with bitrix_id)
            integration = int((data['integrated_tasks'] / total_tasks) * 100)
            
            # Satisfaction (% of completed tasks)
            satisfaction = int((data['completed_tasks'] / total_tasks) * 100)
            
            series.append({
                "name": data['platform_name'],
                "data": [
                    active_users,
                    performance,
                    reliability,
                    integration,
                    satisfaction
                ],
                # Optional: include raw data for debugging
                "_metadata": {
                    "total_hours": round(total_hours, 2),
                    "total_tasks": total_tasks,
                    "unique_users": users_count,
                    "completed_tasks": data['completed_tasks'],
                    "approved_tasks": data['approved_tasks'],
                    "integrated_tasks": data['integrated_tasks']
                }
            })
        
        # Sort series by performance or total_hours (optional)
        series.sort(key=lambda x: x['data'][1], reverse=True)  # Sort by performance score

        return Response({
            "status": "success",
            "view": view_type,
            "date_range": self._get_date_range_description(view_type, today),
            "categories": [
                "Active Users",
                "Performance",
                "Reliability",
                "Integration",
                "Satisfaction"
            ],
            "series": series
        })
    
    def _get_date_range_description(self, view_type, today):
        """Get human-readable date range description"""
        if view_type == "daily":
            return f"Today ({today.strftime('%Y-%m-%d')})"
        elif view_type == "weekly":
            start_date = today - timedelta(days=7)
            return f"Last 7 days ({start_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})"
        elif view_type == "monthly":
            start_date = today - timedelta(days=30)
            return f"Last 30 days ({start_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})"
        return "Unknown range"
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
    

# class ApprovalTableAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):

#         queryset = TaskList.objects.select_related(
#             "user",
#             "status",
#             "user__department",
#             "user__location"
#         ).all()

#         status_map = {
#             "inprogress": "In Progress",
#             "inreview": "In Review",
#             "completed": "Completed",
#         }

#         grouped = defaultdict(list)

#         for task in queryset:
#             status_name = task.get_status_lower()

#             if not status_name:
#                 continue

#             key = status_name.replace(" ", "")

#             if key not in status_map:
#                 continue

#             grouped[key].append({
#                 "owner": task.user.realname or task.user.name,
#                 "role": task.user.designation or "N/A",
#                 "department": task.user.department.name if task.user.department else "N/A",
#                 "location": (
#                     task.user.location.name
#                     if task.user.location else task.user.location_name or "N/A"
#                 ),
#                 "date": task.date.strftime("%d %b %Y"),
#             })

#         response_data = []

#         for key, title in status_map.items():
#             rows = grouped.get(key, [])

#             response_data.append({
#                 "title": title,
#                 "count": len(rows),
#                 "rows": rows
#             })

#         return Response(response_data)
# class ApprovalTableAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):

#         queryset = TaskList.objects.select_related(
#             "user",
#             "status",
#             "platform",
#             "task",
#             "subtask",
#             "user__department",
#             "user__location"
#         ).all()

#         status_map = {
#             "submited": "Submitted",
#             "approved": "Approved",
#             "rejected": "Rejected",
#             "completed": "Completed",
#         }

#         # Structure: status -> date -> unique owners with their tasks
#         grouped = defaultdict(lambda: defaultdict(dict))

#         for task in queryset:
#             status_name = task.get_status_lower()
            
#             if not status_name:
#                 continue

#             key = status_name.replace(" ", "").lower()

#             if key not in status_map:
#                 continue

#             date_key = task.date.strftime("%d %b %Y")
#             owner_name = task.user.realname or task.user.name
            
#             # Create owner key for deduplication
#             if owner_name not in grouped[key][date_key]:
#                 # First time seeing this owner on this date
#                 grouped[key][date_key][owner_name] = {
#                     "owner": owner_name,
#                     "role": task.user.designation or "N/A",
#                     "department": task.user.department.name if task.user.department else "N/A",
#                     "location": (
#                         task.user.location.name
#                         if task.user.location else task.user.location_name or "N/A"
#                     ),
#                     "date": date_key,
#                     "tasks": []
#                 }
            
#             # Add task details to the owner's task list
#             grouped[key][date_key][owner_name]["tasks"].append({
#                 "id": task.id,
#                 "platform": task.platform.name if task.platform else "N/A",
#                 "task_name": task.task.name if task.task else "N/A",
#                 "subtask_name": task.subtask.name if task.subtask else "N/A",
#                 "duration": str(task.duration),
#                 "description": task.description or "",
#                 "status": status_name,
#                 "bitrix_id": task.bitrix_id,
#                 "l1_approver": task.l1_approver.realname if task.l1_approver else None,
#                 "l2_approver": task.l2_approver.realname if task.l2_approver else None,
#                 "created_at": task.created_at.strftime("%d %b %Y %H:%M") if task.created_at else None,
#                 "updated_at": task.updated_at.strftime("%d %b %Y %H:%M") if task.updated_at else None,
#             })

#         response_data = []

#         for key, title in status_map.items():
#             if key in grouped:
#                 all_rows = []
#                 total_count = 0
                
#                 # Sort dates in descending order (latest first)
#                 sorted_dates = sorted(grouped[key].keys(), reverse=True)
                
#                 for date in sorted_dates:
#                     # Get unique owners for this date
#                     owners = list(grouped[key][date].values())
                    
#                     # Sort owners alphabetically by name
#                     owners.sort(key=lambda x: x["owner"])
                    
#                     all_rows.extend(owners)
#                     total_count += len(owners)
                
#                 response_data.append({
#                     "title": title,
#                     "count": total_count,
#                     "rows": all_rows
#                 })
#             else:
#                 response_data.append({
#                     "title": title,
#                     "count": 0,
#                     "rows": []
#                 })

#         return Response(response_data)
    
    
class ApprovalTableAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Filter tasks where current user is either L1 or L2 approver
        queryset = TaskList.objects.select_related(
            "user",
            "status",
            "platform",
            "task",
            "subtask",
            "user__department",
            "user__location"
        ).filter(
            Q(l1_approver=user) | Q(l2_approver=user)
        ).all()

        status_map = {
            "submited": "Submitted",
            "approved": "Approved",
            "rejected": "Rejected",
            "completed": "Completed",
        }

        # Structure: status -> date -> unique owners with their tasks
        grouped = defaultdict(lambda: defaultdict(dict))

        for task in queryset:
            status_name = task.get_status_lower()
            
            if not status_name:
                continue

            key = status_name.replace(" ", "").lower()

            if key not in status_map:
                continue

            date_key = task.date.strftime("%d %b %Y")
            owner_name = task.user.realname or task.user.name
            
            # Create owner key for deduplication
            if owner_name not in grouped[key][date_key]:
                # First time seeing this owner on this date
                grouped[key][date_key][owner_name] = {
                    "owner": owner_name,
                    "role": task.user.designation or "N/A",
                    "department": task.user.department.name if task.user.department else "N/A",
                    "location": (
                        task.user.location.name
                        if task.user.location else task.user.location_name or "N/A"
                    ),
                    "date": date_key,
                    "tasks": []
                }
            
            # Determine approver level for this task
            approver_level = None
            if task.l1_approver == user:
                approver_level = "L1"
            elif task.l2_approver == user:
                approver_level = "L2"
            
            # Add task details to the owner's task list
            grouped[key][date_key][owner_name]["tasks"].append({
                "id": task.id,
                "platform": task.platform.name if task.platform else "N/A",
                "task_name": task.task.name if task.task else "N/A",
                "subtask_name": task.subtask.name if task.subtask else "N/A",
                "duration": str(task.duration),
                "description": task.description or "",
                "status": status_name,
                "bitrix_id": task.bitrix_id,
                "l1_approver": task.l1_approver.realname if task.l1_approver else None,
                "l2_approver": task.l2_approver.realname if task.l2_approver else None,
                "approver_level": approver_level,  # Add which level approver is viewing
                "created_at": task.created_at.strftime("%d %b %Y %H:%M") if task.created_at else None,
                "updated_at": task.updated_at.strftime("%d %b %Y %H:%M") if task.updated_at else None,
            })

        response_data = []

        for key, title in status_map.items():
            if key in grouped:
                all_rows = []
                total_count = 0
                
                # Sort dates in descending order (latest first)
                sorted_dates = sorted(grouped[key].keys(), reverse=True)
                
                for date in sorted_dates:
                    # Get unique owners for this date
                    owners = list(grouped[key][date].values())
                    
                    # Sort owners alphabetically by name
                    owners.sort(key=lambda x: x["owner"])
                    
                    all_rows.extend(owners)
                    total_count += len(owners)
                
                response_data.append({
                    "title": title,
                    "count": total_count,
                    "rows": all_rows
                })
            else:
                response_data.append({
                    "title": title,
                    "count": 0,
                    "rows": []
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
    
class ApprovalStatusOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        view_type = request.query_params.get("view", "daily")  # daily, weekly, monthly

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
        # Only tasks where the user is first or second level approver
        queryset = queryset.filter(Q(l1_approver=user) | Q(l2_approver=user))

        # ---------------- AGGREGATE COUNTS ----------------
        pending_count = queryset.filter(
            Q(l1_approver=user, l1_approved_at__isnull=True, l1_rejected_at__isnull=True) |
            Q(l2_approver=user, l2_approved_at__isnull=True, l2_rejected_at__isnull=True)
        ).count()

        approved_count = queryset.filter(
            Q(l1_approver=user, l1_approved_at__isnull=False) |
            Q(l2_approver=user, l2_approved_at__isnull=False)
        ).count()

        rejected_count = queryset.filter(
            Q(l1_approver=user, l1_rejected_at__isnull=False) |
            Q(l2_approver=user, l2_rejected_at__isnull=False)
        ).count()

        completed_count = queryset.filter(status__name__iexact="Completed").count()

        total_count = pending_count + approved_count + rejected_count + completed_count

        return Response({
            "total": total_count,
            "completed": completed_count,
            "pending": pending_count,
            "approved": approved_count,
            "rejected": rejected_count,
        })


# class ApprovalStatusOverviewAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         user = request.user
#         view_type = request.query_params.get("view", "daily")  # daily, weekly, monthly

#         today = timezone.now().date()

#         # ---------------- DATE FILTER ----------------
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

#         # ---------------- APPROVER FILTER ----------------
#         # Only show tasks assigned to or approved by this user
#         if not user.is_staff:
#             queryset = queryset.filter(
#                 Q(l1_approver=user) | Q(l2_approver=user)
#             )

#         # ---------------- AGGREGATE BY STATUS ----------------
#         total = queryset.count()
#         completed = queryset.filter(status__name__iexact="Completed").count()
#         pending = queryset.filter(status__name__iexact="In Progress").count()
#         approved = queryset.filter(status__name__iexact="Approved").count()
#         rejected = queryset.filter(status__name__iexact="Rejected").count()

#         return Response({
#             "total": total,
#             "completed": completed,
#             "pending": pending,
#             "approved": approved,
#             "rejected": rejected,
#         })
    
    
    from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from collections import OrderedDict

class TaskStatusOverviewAPIView(APIView):
    """
    API View to get task status overview with counts and percentages
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = TaskList.objects.select_related('status', 'user', 'l1_approver', 'l2_approver')
        
        # Staff can see all tasks
        if user.is_staff:
            return queryset
        
        # Non-staff users see their own tasks and tasks they approve
        return queryset.filter(
            Q(user=user) |
            Q(l1_approver=user) |
            Q(l2_approver=user)
        )
    
    def apply_filters(self, request, queryset):
        """Apply additional filters"""
        params = request.query_params
        
        # Staff can filter by user_id
        if params.get('user_id') and request.user.is_staff:
            queryset = queryset.filter(user_id=params['user_id'])
        
        # Platform filter
        if params.get('platform'):
            queryset = queryset.filter(platform_id=params['platform'])
        
        # Task filter
        if params.get('task'):
            queryset = queryset.filter(task_id=params['task'])
        
        # Specific status filter
        if params.get('status'):
            queryset = queryset.filter(status_id=params['status'])
        
        return queryset
    
    def get_date_range(self, period, reference_date=None):
        """Get start and end date based on period"""
        if reference_date is None:
            reference_date = timezone.now().date()
        else:
            reference_date = datetime.strptime(reference_date, '%Y-%m-%d').date()
        
        if period == 'today':
            start_date = reference_date
            end_date = reference_date
            period_name = reference_date.strftime('%Y-%m-%d')
            
        elif period == 'week':
            # Current week (Monday to Sunday)
            start_date = reference_date - timedelta(days=reference_date.weekday())
            end_date = start_date + timedelta(days=6)
            period_name = f"Week {reference_date.isocalendar()[1]}, {reference_date.year}"
            
        elif period == 'month':
            # Current month
            start_date = reference_date.replace(day=1)
            if reference_date.month == 12:
                end_date = reference_date.replace(year=reference_date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = reference_date.replace(month=reference_date.month + 1, day=1) - timedelta(days=1)
            period_name = reference_date.strftime('%B %Y')
            
        elif period == 'year':
            # Current year
            start_date = reference_date.replace(month=1, day=1)
            end_date = reference_date.replace(month=12, day=31)
            period_name = str(reference_date.year)
            
        else:
            # Default to month
            start_date = reference_date.replace(day=1)
            if reference_date.month == 12:
                end_date = reference_date.replace(year=reference_date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = reference_date.replace(month=reference_date.month + 1, day=1) - timedelta(days=1)
            period_name = reference_date.strftime('%B %Y')
        
        return start_date, end_date, period_name
    
    def calculate_status_breakdown(self, queryset, total_count):
        """Calculate status breakdown with counts and percentages"""
        status_counts = queryset.values('status__name', 'status__id').annotate(
            count=Count('id')
        ).order_by('-count')
        
        breakdown = {}
        for item in status_counts:
            status_name = item['status__name'] or 'Unknown'
            count = item['count']
            percentage = (count / total_count * 100) if total_count > 0 else 0
            
            breakdown[status_name] = {
                'count': count,
                'percentage': round(percentage, 2),
                'status_id': item['status__id']
            }
        
        return breakdown
    
    def get(self, request):
        """
        Get task status overview
        Query Parameters:
            - period: today, week, month, year (default: month)
            - date: specific date in YYYY-MM-DD format (default: current date)
            - user_id: filter by user (staff only)
            - platform: filter by platform ID
            - task: filter by task ID
            - status: filter by status ID
        """
        params = request.query_params
        period = params.get('period', 'month').lower()
        date_param = params.get('date')
        
        # Get base queryset with permissions
        queryset = self.get_queryset()
        
        # Apply additional filters
        queryset = self.apply_filters(request, queryset)
        
        # Get date range for the period
        start_date, end_date, period_name = self.get_date_range(period, date_param)
        
        # Filter by date range
        queryset = queryset.filter(date__gte=start_date, date__lte=end_date)
        
        # Get total count for the period
        total_count = queryset.count()
        
        # Calculate status breakdown
        status_breakdown = self.calculate_status_breakdown(queryset, total_count)
        
        # Prepare response data
        response_data = {
            'period': period_name,
            'date_range': {
                'start': start_date,
                'end': end_date
            },
            'total_tasks': total_count,
            'status_breakdown': status_breakdown,
            'filters_applied': {
                'period': period,
                'date': date_param if date_param else 'current',
                'platform': params.get('platform'),
                'task': params.get('task'),
                'status': params.get('status'),
                'user_id': params.get('user_id') if request.user.is_staff else None
            }
        }
        
        return Response(response_data)


class MultiPeriodTaskStatusOverviewAPIView(APIView):
    """
    API View to get task status overview for multiple periods at once
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get overview for multiple periods: this month, this week, this year
        Query Parameters:
            - user_id: filter by user (staff only)
            - platform: filter by platform ID
            - task: filter by task ID
            - status: filter by status ID
        """
        params = request.query_params
        today = timezone.now().date()
        
        # Get base queryset with permissions
        queryset = TaskList.objects.select_related('status')
        
        user = request.user
        if not user.is_staff:
            queryset = queryset.filter(
                Q(user=user) |
                Q(l1_approver=user) |
                Q(l2_approver=user)
            )
        
        # Apply filters
        if params.get('user_id') and user.is_staff:
            queryset = queryset.filter(user_id=params['user_id'])
        if params.get('platform'):
            queryset = queryset.filter(platform_id=params['platform'])
        if params.get('task'):
            queryset = queryset.filter(task_id=params['task'])
        if params.get('status'):
            queryset = queryset.filter(status_id=params['status'])
        
        # Define periods
        periods = {
            'today': {
                'start': today,
                'end': today,
                'label': today.strftime('%Y-%m-%d')
            },
            'week': {
                'start': today - timedelta(days=today.weekday()),
                'end': today - timedelta(days=today.weekday()) + timedelta(days=6),
                'label': f"Week {today.isocalendar()[1]}, {today.year}"
            },
            'month': {
                'start': today.replace(day=1),
                'end': (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1),
                'label': today.strftime('%B %Y')
            },
            'year': {
                'start': today.replace(month=1, day=1),
                'end': today.replace(month=12, day=31),
                'label': str(today.year)
            }
        }
        
        # Calculate overview for each period
        overview = OrderedDict()
        for period_key, period_info in periods.items():
            period_queryset = queryset.filter(
                date__gte=period_info['start'],
                date__lte=period_info['end']
            )
            
            total_count = period_queryset.count()
            
            # Calculate status breakdown
            status_counts = period_queryset.values('status__name').annotate(
                count=Count('id')
            ).order_by('-count')
            
            status_breakdown = {}
            for item in status_counts:
                status_name = item['status__name'] or 'Unknown'
                count = item['count']
                percentage = (count / total_count * 100) if total_count > 0 else 0
                
                status_breakdown[status_name] = {
                    'count': count,
                    'percentage': round(percentage, 2)
                }
            
            overview[period_key] = {
                'label': period_info['label'],
                'date_range': {
                    'start': period_info['start'],
                    'end': period_info['end']
                },
                'total_tasks': total_count,
                'status_breakdown': status_breakdown
            }
        
        # Add summary
        summary = {
            'most_active_period': max(overview.items(), key=lambda x: x[1]['total_tasks'])[0] if overview else None,
            'highest_completion_rate': None
        }
        
        # Calculate completion rate
        for period_key, period_data in overview.items():
            if 'Completed' in period_data['status_breakdown']:
                completion_rate = period_data['status_breakdown']['Completed']['percentage']
                if summary['highest_completion_rate'] is None or completion_rate > summary['highest_completion_rate'][1]:
                    summary['highest_completion_rate'] = (period_key, completion_rate)
        
        response_data = {
            'overview': overview,
            'summary': summary,
            'filters_applied': {
                'user_id': params.get('user_id') if user.is_staff else None,
                'platform': params.get('platform'),
                'task': params.get('task'),
                'status': params.get('status')
            }
        }
        
        return Response(response_data)
    
    
# class TaskCountsAPIView(APIView):
#     permission_classes = [IsAuthenticated]
    
#     def get(self, request):
#         user = request.user
        
#         # Get current date for "today" calculations
#         today = timezone.now().date()
#         today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
#         today_end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
        
#         # Base queryset based on user permissions
#         if user.is_staff:
#             queryset = TaskList.objects.select_related('status')
#         else:
#             # Non-staff users can see:
#             # - Tasks they own
#             # - Tasks where they are L1 approver
#             # - Tasks where they are L2 approver
#             queryset = TaskList.objects.select_related('status').filter(
#                 Q(user=user) |
#                 Q(l1_approver=user) |
#                 Q(l2_approver=user)
#             )
        
#         # Get status objects
#         in_progress_status = Status.objects.filter(name__iexact='In Progress').first() or \
#                             Status.objects.filter(name__iexact='inprogress').first()
#         completed_status = Status.objects.filter(name__iexact='Completed').first() or \
#                           Status.objects.filter(name__iexact='Done').first()
#         rejected_status = Status.objects.filter(name__iexact='Rejected').first()
#         draft_status = Status.objects.filter(name__iexact='Draft').first()
        
#         # Calculate Total Hours (sum of duration for all tasks)
#         total_hours = queryset.aggregate(total=Sum('duration'))['total'] or 0
        
#         # Calculate Today Hours (sum of duration for tasks created today)
#         today_hours = queryset.filter(
#             date__range=[today_start, today_end]
#         ).aggregate(total=Sum('duration'))['total'] or 0
        
#         # Calculate Total Task (count of all tasks)
#         total_tasks = queryset.count()
        
#         # Calculate Submitted tasks (tasks that have been submitted/in progress)
#         submitted_tasks = 0
#         if in_progress_status:
#             submitted_tasks = queryset.filter(status=in_progress_status).count()
        
#         # Calculate Pending Approval tasks
#         pending_approval_tasks = 0
#         if user.is_staff:
#             # For staff: count tasks where either L1 or L2 approval is pending
#             pending_approval_tasks = queryset.filter(
#                 Q(l1_approved_at__isnull=True, l1_approver__isnull=False) |
#                 Q(l2_approved_at__isnull=True, l2_approver__isnull=False)
#             ).exclude(
#                 Q(l1_rejected_at__isnull=False) | Q(l2_rejected_at__isnull=False)
#             ).count()
#         else:
#             # For non-staff: count tasks where user is approver and approval is pending
#             pending_approval_tasks = queryset.filter(
#                 Q(l1_approver=user, l1_approved_at__isnull=True, l1_rejected_at__isnull=True) |
#                 Q(l2_approver=user, l2_approved_at__isnull=True, l2_rejected_at__isnull=True)
#             ).count()
        
#         # Calculate Rejected tasks
#         rejected_tasks = 0
#         if rejected_status:
#             rejected_tasks = queryset.filter(status=rejected_status).count()
        
#         # Additional counts that might be useful
#         # Completed tasks (if needed)
#         completed_tasks = 0
#         if completed_status:
#             completed_tasks = queryset.filter(status=completed_status).count()
        
#         # Draft tasks
#         draft_tasks = 0
#         if draft_status:
#             draft_tasks = queryset.filter(status=draft_status).count()
        
#         # Format duration (convert hours to decimal if needed)
#         def format_hours(hours):
#             if hours is None:
#                 return 0
#             return float(hours)
        
#         response_data = {
#             "total_hours": format_hours(total_hours),
#             "today_hours": format_hours(today_hours),
#             "total_tasks": total_tasks,
#             "submitted_tasks": submitted_tasks,
#             "pending_approval_tasks": pending_approval_tasks,
#             "rejected_tasks": rejected_tasks,
#             # Optional additional counts
#             "completed_tasks": completed_tasks,
#             "draft_tasks": draft_tasks,
#         }
        
#         # Add filter parameters if needed
#         # Apply date filters if provided
#         start_date = request.query_params.get('start_date')
#         end_date = request.query_params.get('end_date')
        
#         if start_date or end_date:
#             filtered_queryset = queryset
#             if start_date:
#                 filtered_queryset = filtered_queryset.filter(date__gte=start_date)
#             if end_date:
#                 filtered_queryset = filtered_queryset.filter(date__lte=end_date)
            
#             response_data["filtered"] = {
#                 "total_hours": filtered_queryset.aggregate(total=Sum('duration'))['total'] or 0,
#                 "total_tasks": filtered_queryset.count(),
#                 "submitted_tasks": filtered_queryset.filter(status=in_progress_status).count() if in_progress_status else 0,
#                 "rejected_tasks": filtered_queryset.filter(status=rejected_status).count() if rejected_status else 0,
#             }
        
#         return Response(response_data, status=status.HTTP_200_OK)
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status as http_status
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from .models import TaskList, Status, User

class TaskCountsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def parse_duration_to_hours(self, duration_str):
        """Convert duration string like '1h 30m' to decimal hours (1.5)"""
        if not duration_str:
            return 0
        
        if isinstance(duration_str, (int, float)):
            return float(duration_str)
        
        duration_str = str(duration_str).strip()
        
        try:
            return float(duration_str)
        except ValueError:
            pass
        
        hours = 0
        minutes = 0
        
        hour_match = re.search(r'(\d+(?:\.\d+)?)\s*h', duration_str, re.IGNORECASE)
        if hour_match:
            hours = float(hour_match.group(1))
        
        minute_match = re.search(r'(\d+(?:\.\d+)?)\s*m', duration_str, re.IGNORECASE)
        if minute_match:
            minutes = float(minute_match.group(1))
        
        if not hour_match and not minute_match:
            try:
                return float(duration_str)
            except ValueError:
                return 0
        
        return hours + (minutes / 60)
    
    def format_hours_to_duration(self, hours):
        """Convert decimal hours (2.5) to readable format like '2h 30m'"""
        if not hours or hours == 0:
            return "0h"
        
        total_minutes = int(hours * 60)
        h = total_minutes // 60
        m = total_minutes % 60
        
        if h > 0 and m > 0:
            return f"{h}h {m}m"
        elif h > 0:
            return f"{h}h"
        else:
            return f"{m}m"
    
    def aggregate_duration(self, queryset, date_range=None):
        """Aggregate duration from string fields and return both decimal and formatted"""
        if date_range:
            queryset = queryset.filter(date__range=date_range)
        
        entries = queryset.values('duration')
        total_hours = 0
        
        for entry in entries:
            duration_str = entry['duration']
            total_hours += self.parse_duration_to_hours(duration_str)
        
        return total_hours
    
    def get(self, request):
        user = request.user
        
        # Get current date for "today" calculations
        today = timezone.now().date()
        today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        today_end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
        
        # Base queryset based on user permissions
        if user.is_staff:
            all_tasks_queryset = TaskList.objects.select_related('status')
        else:
            # All tasks that user can see (owned or approver)
            all_tasks_queryset = TaskList.objects.select_related('status').filter(
                Q(user=user) |
                Q(l1_approver=user) |
                Q(l2_approver=user)
            )
        
        # Tasks where user is the owner
        owned_tasks_queryset = TaskList.objects.select_related('status').filter(user=user)
        
        # Tasks where user is L1 approver
        l1_approver_tasks_queryset = TaskList.objects.select_related('status').filter(l1_approver=user)
        
        # Tasks where user is L2 approver
        l2_approver_tasks_queryset = TaskList.objects.select_related('status').filter(l2_approver=user)
        
        # Get status objects
        in_progress_status = Status.objects.filter(name__iexact='In Progress').first() or \
                            Status.objects.filter(name__iexact='inprogress').first()
        completed_status = Status.objects.filter(name__iexact='Completed').first() or \
                        Status.objects.filter(name__iexact='Done').first()
        rejected_status = Status.objects.filter(name__iexact='Rejected').first()
        draft_status = Status.objects.filter(name__iexact='Draft').first()
        
        # ============== NORMAL COUNTS (All accessible tasks) ==============
        normal_counts = self._get_normal_counts(
            all_tasks_queryset, 
            in_progress_status, 
            completed_status, 
            rejected_status, 
            draft_status,
            today_start,
            today_end
        )
        
        # ============== APPROVER COUNTS (Based on user role) ==============
        approver_counts = self._get_approver_counts(
            user,
            owned_tasks_queryset,
            l1_approver_tasks_queryset,
            l2_approver_tasks_queryset,
            in_progress_status,
            completed_status,
            rejected_status,
            draft_status,
            today_start,
            today_end
        )
        
        # ============== PENDING APPROVAL COUNTS (Tasks waiting for user's approval) ==============
        pending_approval_counts = self._get_pending_approval_counts(
            user,
            l1_approver_tasks_queryset,
            l2_approver_tasks_queryset,
            in_progress_status
        )
        
        # Combine all data
        response_data = {
            "user": {
                "id": user.id,
                "name": user.firstname,
                "email": user.email,
                "is_staff": user.is_staff
            },
            "normal_counts": normal_counts,
            "approver_counts": approver_counts,
            "pending_approval": pending_approval_counts
        }
        
        return Response(response_data, status=http_status.HTTP_200_OK)
    
    def _get_normal_counts(self, queryset, in_progress_status, completed_status, rejected_status, draft_status, today_start, today_end):
        """Get normal counts for all accessible tasks"""
        
        # Calculate counts using manual aggregation
        total_hours_decimal = self.aggregate_duration(queryset)
        today_hours_decimal = self.aggregate_duration(queryset, [today_start, today_end])
        total_tasks = queryset.count()
        
        submitted_tasks = 0
        if in_progress_status:
            submitted_tasks = queryset.filter(status=in_progress_status).count()
        
        completed_tasks = 0
        if completed_status:
            completed_tasks = queryset.filter(status=completed_status).count()
        
        rejected_tasks = 0
        if rejected_status:
            rejected_tasks = queryset.filter(status=rejected_status).count()
        
        draft_tasks = 0
        if draft_status:
            draft_tasks = queryset.filter(status=draft_status).count()
        
        # Calculate completion percentage
        completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        return {
            "total_hours": self.format_hours_to_duration(total_hours_decimal),  # Formatted like "3h 45m"
            "total_hours_decimal": round(total_hours_decimal, 2),  # Decimal for calculations
            "today_hours": self.format_hours_to_duration(today_hours_decimal),  # Formatted like "1h 30m"
            "today_hours_decimal": round(today_hours_decimal, 2),  # Decimal for calculations
            "total_tasks": total_tasks,
            "submitted_tasks": submitted_tasks,
            "completed_tasks": completed_tasks,
            "rejected_tasks": rejected_tasks,
            "draft_tasks": draft_tasks,
            "completion_percentage": round(completion_percentage, 2)
        }
    
    def _get_approver_counts(self, user, owned_tasks, l1_tasks, l2_tasks, in_progress_status, completed_status, rejected_status, draft_status, today_start, today_end):
        """Get counts based on user role (owner, L1 approver, L2 approver)"""
        
        # Owned tasks counts using manual aggregation
        owned_hours_decimal = self.aggregate_duration(owned_tasks)
        owned_today_hours_decimal = self.aggregate_duration(owned_tasks, [today_start, today_end])
        owned_total = owned_tasks.count()
        
        owned_completed = 0
        if completed_status:
            owned_completed = owned_tasks.filter(status=completed_status).count()
        
        owned_submitted = 0
        if in_progress_status:
            owned_submitted = owned_tasks.filter(status=in_progress_status).count()
        
        owned_rejected = 0
        if rejected_status:
            owned_rejected = owned_tasks.filter(status=rejected_status).count()
        
        owned_draft = 0
        if draft_status:
            owned_draft = owned_tasks.filter(status=draft_status).count()
        
        # L1 Approver tasks counts using manual aggregation
        l1_hours_decimal = self.aggregate_duration(l1_tasks)
        l1_today_hours_decimal = self.aggregate_duration(l1_tasks, [today_start, today_end])
        l1_total = l1_tasks.count()
        
        l1_completed = 0
        if completed_status:
            l1_completed = l1_tasks.filter(status=completed_status).count()
        
        l1_pending = l1_tasks.filter(l1_approved_at__isnull=True, l1_rejected_at__isnull=True).count()
        
        # L2 Approver tasks counts using manual aggregation
        l2_hours_decimal = self.aggregate_duration(l2_tasks)
        l2_today_hours_decimal = self.aggregate_duration(l2_tasks, [today_start, today_end])
        l2_total = l2_tasks.count()
        
        l2_completed = 0
        if completed_status:
            l2_completed = l2_tasks.filter(status=completed_status).count()
        
        l2_pending = l2_tasks.filter(l2_approved_at__isnull=True, l2_rejected_at__isnull=True).count()
        
        return {
            "as_owner": {
                "total_hours": self.format_hours_to_duration(owned_hours_decimal),  # Formatted
                "total_hours_decimal": round(owned_hours_decimal, 2),  # Decimal
                "today_hours": self.format_hours_to_duration(owned_today_hours_decimal),  # Formatted
                "today_hours_decimal": round(owned_today_hours_decimal, 2),  # Decimal
                "total_tasks": owned_total,
                "submitted_tasks": owned_submitted,
                "completed_tasks": owned_completed,
                "rejected_tasks": owned_rejected,
                "draft_tasks": owned_draft,
                "completion_percentage": round((owned_completed / owned_total * 100), 2) if owned_total > 0 else 0
            },
            "as_l1_approver": {
                "total_hours": self.format_hours_to_duration(l1_hours_decimal),  # Formatted
                "total_hours_decimal": round(l1_hours_decimal, 2),  # Decimal
                "today_hours": self.format_hours_to_duration(l1_today_hours_decimal),  # Formatted
                "today_hours_decimal": round(l1_today_hours_decimal, 2),  # Decimal
                "total_tasks": l1_total,
                "completed_tasks": l1_completed,
                "pending_approval": l1_pending,
                "completion_percentage": round((l1_completed / l1_total * 100), 2) if l1_total > 0 else 0
            },
            "as_l2_approver": {
                "total_hours": self.format_hours_to_duration(l2_hours_decimal),  # Formatted
                "total_hours_decimal": round(l2_hours_decimal, 2),  # Decimal
                "today_hours": self.format_hours_to_duration(l2_today_hours_decimal),  # Formatted
                "today_hours_decimal": round(l2_today_hours_decimal, 2),  # Decimal
                "total_tasks": l2_total,
                "completed_tasks": l2_completed,
                "pending_approval": l2_pending,
                "completion_percentage": round((l2_completed / l2_total * 100), 2) if l2_total > 0 else 0
            }
        }
    
    def _get_pending_approval_counts(self, user, l1_tasks, l2_tasks, in_progress_status):
        """Get tasks pending approval for the current user"""
        
        # Tasks pending L1 approval
        pending_l1_approval = l1_tasks.filter(
            l1_approved_at__isnull=True,
            l1_rejected_at__isnull=True,
            status=in_progress_status
        ).count() if in_progress_status else 0
        
        # Tasks pending L2 approval
        pending_l2_approval = l2_tasks.filter(
            l2_approved_at__isnull=True,
            l2_rejected_at__isnull=True,
            status=in_progress_status
        ).count() if in_progress_status else 0
        
        # Get pending tasks details (optional)
        pending_l1_tasks = l1_tasks.filter(
            l1_approved_at__isnull=True,
            l1_rejected_at__isnull=True,
            status=in_progress_status
        ).select_related('user', 'task', 'subtask').order_by('-date')[:10]
        
        pending_l2_tasks = l2_tasks.filter(
            l2_approved_at__isnull=True,
            l2_rejected_at__isnull=True,
            status=in_progress_status
        ).select_related('user', 'task', 'subtask').order_by('-date')[:10]
        
        return {
            "summary": {
                "total_pending": pending_l1_approval + pending_l2_approval,
                "pending_l1_approval": pending_l1_approval,
                "pending_l2_approval": pending_l2_approval
            },
            "l1_pending_tasks": [
                {
                    "id": task.id,
                    "task_name": task.task.name if task.task else None,
                    "subtask_name": task.subtask.name if task.subtask else None,
                    "description": task.description,
                    "duration_decimal": round(self.parse_duration_to_hours(task.duration), 2),  # Decimal
                    "duration_formatted": self.format_hours_to_duration(self.parse_duration_to_hours(task.duration)),  # Formatted
                    "user": task.user.get_full_name() or task.user.username,
                    "date": task.date.strftime('%Y-%m-%d'),
                    "bitrix_id": task.bitrix_id
                }
                for task in pending_l1_tasks
            ],
            "l2_pending_tasks": [
                {
                    "id": task.id,
                    "task_name": task.task.name if task.task else None,
                    "subtask_name": task.subtask.name if task.subtask else None,
                    "description": task.description,
                    "duration_decimal": round(self.parse_duration_to_hours(task.duration), 2),  # Decimal
                    "duration_formatted": self.format_hours_to_duration(self.parse_duration_to_hours(task.duration)),  # Formatted
                    "user": task.user.get_full_name() or task.user.username,
                    "date": task.date.strftime('%Y-%m-%d'),
                    "bitrix_id": task.bitrix_id
                }
                for task in pending_l2_tasks
            ]
        }
# class TaskCountsAPIView(APIView):
#         permission_classes = [IsAuthenticated]
        
#         def get(self, request):
#             user = request.user
            
#             # Get current date for "today" calculations
#             today = timezone.now().date()
#             today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
#             today_end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
            
#             # Base queryset based on user permissions
#             if user.is_staff:
#                 all_tasks_queryset = TaskList.objects.select_related('status')
#             else:
#                 # All tasks that user can see (owned or approver)
#                 all_tasks_queryset = TaskList.objects.select_related('status').filter(
#                     Q(user=user) |
#                     Q(l1_approver=user) |
#                     Q(l2_approver=user)
#                 )
            
#             # Tasks where user is the owner
#             owned_tasks_queryset = TaskList.objects.select_related('status').filter(user=user)
            
#             # Tasks where user is L1 approver
#             l1_approver_tasks_queryset = TaskList.objects.select_related('status').filter(l1_approver=user)
            
#             # Tasks where user is L2 approver
#             l2_approver_tasks_queryset = TaskList.objects.select_related('status').filter(l2_approver=user)
            
#             # Get status objects
#             in_progress_status = Status.objects.filter(name__iexact='In Progress').first() or \
#                                 Status.objects.filter(name__iexact='inprogress').first()
#             completed_status = Status.objects.filter(name__iexact='Completed').first() or \
#                             Status.objects.filter(name__iexact='Done').first()
#             rejected_status = Status.objects.filter(name__iexact='Rejected').first()
#             draft_status = Status.objects.filter(name__iexact='Draft').first()
            
#             # ============== NORMAL COUNTS (All accessible tasks) ==============
#             normal_counts = self._get_normal_counts(
#                 all_tasks_queryset, 
#                 in_progress_status, 
#                 completed_status, 
#                 rejected_status, 
#                 draft_status,
#                 today_start,
#                 today_end
#             )
            
#             # ============== APPROVER COUNTS (Based on user role) ==============
#             approver_counts = self._get_approver_counts(
#                 user,
#                 owned_tasks_queryset,
#                 l1_approver_tasks_queryset,
#                 l2_approver_tasks_queryset,
#                 in_progress_status,
#                 completed_status,
#                 rejected_status,
#                 draft_status,
#                 today_start,
#                 today_end
#             )
            
#             # ============== PENDING APPROVAL COUNTS (Tasks waiting for user's approval) ==============
#             pending_approval_counts = self._get_pending_approval_counts(
#                 user,
#                 l1_approver_tasks_queryset,
#                 l2_approver_tasks_queryset,
#                 in_progress_status
#             )
            
#             # Combine all data
#             response_data = {
#                 "user": {
#                     "id": user.id,
#                     "name":  user.firstname,
#                     "email": user.email,
#                     "is_staff": user.is_staff
#                 },
#                 "normal_counts": normal_counts,
#                 "approver_counts": approver_counts,
#                 "pending_approval": pending_approval_counts
#             }
            
#             return Response(response_data, status=http_status.HTTP_200_OK)
        
#         def _get_normal_counts(self, queryset, in_progress_status, completed_status, rejected_status, draft_status, today_start, today_end):
#             """Get normal counts for all accessible tasks"""
            
#             def format_hours(hours):
#                 return float(hours) if hours else 0
            
#             # Calculate counts
#             total_hours = queryset.aggregate(total=Sum('duration'))['total'] or 0
#             today_hours = queryset.filter(date__range=[today_start, today_end]).aggregate(total=Sum('duration'))['total'] or 0
#             total_tasks = queryset.count()
            
#             submitted_tasks = 0
#             if in_progress_status:
#                 submitted_tasks = queryset.filter(status=in_progress_status).count()
            
#             completed_tasks = 0
#             if completed_status:
#                 completed_tasks = queryset.filter(status=completed_status).count()
            
#             rejected_tasks = 0
#             if rejected_status:
#                 rejected_tasks = queryset.filter(status=rejected_status).count()
            
#             draft_tasks = 0
#             if draft_status:
#                 draft_tasks = queryset.filter(status=draft_status).count()
            
#             # Calculate completion percentage
#             completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
#             return {
#                 "total_hours": format_hours(total_hours),
#                 "today_hours": format_hours(today_hours),
#                 "total_tasks": total_tasks,
#                 "submitted_tasks": submitted_tasks,
#                 "completed_tasks": completed_tasks,
#                 "rejected_tasks": rejected_tasks,
#                 "draft_tasks": draft_tasks,
#                 "completion_percentage": round(completion_percentage, 2)
#             }
        
#         def _get_approver_counts(self, user, owned_tasks, l1_tasks, l2_tasks, in_progress_status, completed_status, rejected_status, draft_status, today_start, today_end):
#             """Get counts based on user role (owner, L1 approver, L2 approver)"""
            
#             def format_hours(hours):
#                 return float(hours) if hours else 0
            
#             # Owned tasks counts
#             owned_hours = owned_tasks.aggregate(total=Sum('duration'))['total'] or 0
#             owned_today_hours = owned_tasks.filter(date__range=[today_start, today_end]).aggregate(total=Sum('duration'))['total'] or 0
#             owned_total = owned_tasks.count()
            
#             owned_completed = 0
#             if completed_status:
#                 owned_completed = owned_tasks.filter(status=completed_status).count()
            
#             owned_submitted = 0
#             if in_progress_status:
#                 owned_submitted = owned_tasks.filter(status=in_progress_status).count()
            
#             owned_rejected = 0
#             if rejected_status:
#                 owned_rejected = owned_tasks.filter(status=rejected_status).count()
            
#             owned_draft = 0
#             if draft_status:
#                 owned_draft = owned_tasks.filter(status=draft_status).count()
            
#             # L1 Approver tasks counts
#             l1_hours = l1_tasks.aggregate(total=Sum('duration'))['total'] or 0
#             l1_today_hours = l1_tasks.filter(date__range=[today_start, today_end]).aggregate(total=Sum('duration'))['total'] or 0
#             l1_total = l1_tasks.count()
            
#             l1_completed = 0
#             if completed_status:
#                 l1_completed = l1_tasks.filter(status=completed_status).count()
            
#             l1_pending = l1_tasks.filter(l1_approved_at__isnull=True, l1_rejected_at__isnull=True).count()
            
#             # L2 Approver tasks counts
#             l2_hours = l2_tasks.aggregate(total=Sum('duration'))['total'] or 0
#             l2_today_hours = l2_tasks.filter(date__range=[today_start, today_end]).aggregate(total=Sum('duration'))['total'] or 0
#             l2_total = l2_tasks.count()
            
#             l2_completed = 0
#             if completed_status:
#                 l2_completed = l2_tasks.filter(status=completed_status).count()
            
#             l2_pending = l2_tasks.filter(l2_approved_at__isnull=True, l2_rejected_at__isnull=True).count()
            
#             return {
#                 "as_owner": {
#                     "total_hours": format_hours(owned_hours),
#                     "today_hours": format_hours(owned_today_hours),
#                     "total_tasks": owned_total,
#                     "submitted_tasks": owned_submitted,
#                     "completed_tasks": owned_completed,
#                     "rejected_tasks": owned_rejected,
#                     "draft_tasks": owned_draft,
#                     "completion_percentage": round((owned_completed / owned_total * 100), 2) if owned_total > 0 else 0
#                 },
#                 "as_l1_approver": {
#                     "total_hours": format_hours(l1_hours),
#                     "today_hours": format_hours(l1_today_hours),
#                     "total_tasks": l1_total,
#                     "completed_tasks": l1_completed,
#                     "pending_approval": l1_pending,
#                     "completion_percentage": round((l1_completed / l1_total * 100), 2) if l1_total > 0 else 0
#                 },
#                 "as_l2_approver": {
#                     "total_hours": format_hours(l2_hours),
#                     "today_hours": format_hours(l2_today_hours),
#                     "total_tasks": l2_total,
#                     "completed_tasks": l2_completed,
#                     "pending_approval": l2_pending,
#                     "completion_percentage": round((l2_completed / l2_total * 100), 2) if l2_total > 0 else 0
#                 }
#             }
        
#         def _get_pending_approval_counts(self, user, l1_tasks, l2_tasks, in_progress_status):
#             """Get tasks pending approval for the current user"""
            
#             # Tasks pending L1 approval
#             pending_l1_approval = l1_tasks.filter(
#                 l1_approved_at__isnull=True,
#                 l1_rejected_at__isnull=True,
#                 status=in_progress_status
#             ).count() if in_progress_status else 0
            
#             # Tasks pending L2 approval
#             pending_l2_approval = l2_tasks.filter(
#                 l2_approved_at__isnull=True,
#                 l2_rejected_at__isnull=True,
#                 status=in_progress_status
#             ).count() if in_progress_status else 0
            
#             # Get pending tasks details (optional)
#             pending_l1_tasks = l1_tasks.filter(
#                 l1_approved_at__isnull=True,
#                 l1_rejected_at__isnull=True,
#                 status=in_progress_status
#             ).select_related('user', 'task', 'subtask').order_by('-date')[:10]
            
#             pending_l2_tasks = l2_tasks.filter(
#                 l2_approved_at__isnull=True,
#                 l2_rejected_at__isnull=True,
#                 status=in_progress_status
#             ).select_related('user', 'task', 'subtask').order_by('-date')[:10]
            
#             return {
#                 "summary": {
#                     "total_pending": pending_l1_approval + pending_l2_approval,
#                     "pending_l1_approval": pending_l1_approval,
#                     "pending_l2_approval": pending_l2_approval
#                 },
#                 "l1_pending_tasks": [
#                     {
#                         "id": task.id,
#                         "task_name": task.task.name if task.task else None,
#                         "subtask_name": task.subtask.name if task.subtask else None,
#                         "description": task.description,
#                         "duration": float(task.duration) if task.duration else 0,
#                         "user": task.user.get_full_name() or task.user.username,
#                         "date": task.date.strftime('%Y-%m-%d'),
#                         "bitrix_id": task.bitrix_id
#                     }
#                     for task in pending_l1_tasks
#                 ],
#                 "l2_pending_tasks": [
#                     {
#                         "id": task.id,
#                         "task_name": task.task.name if task.task else None,
#                         "subtask_name": task.subtask.name if task.subtask else None,
#                         "description": task.description,
#                         "duration": float(task.duration) if task.duration else 0,
#                         "user": task.user.get_full_name() or task.user.username,
#                         "date": task.date.strftime('%Y-%m-%d'),
#                         "bitrix_id": task.bitrix_id
#                     }
#                     for task in pending_l2_tasks
#                 ]
#             }   

from rest_framework import status as http_status  # Rename to avoid conflict

class TaskStatusOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get time filter parameter
        time_filter = request.query_params.get('time_filter', 'all')  # all, day, week, month
        specific_date = request.query_params.get('date')  # For specific date (YYYY-MM-DD)
        
        # Base queryset based on user permissions
        if user.is_staff:
            base_queryset = TaskList.objects.select_related('status')
        else:
            base_queryset = TaskList.objects.select_related('status').filter(
                Q(user=user) |
                Q(l1_approver=user) |
                Q(l2_approver=user)
            )
        
        # Apply time-based filters
        today = timezone.now().date()
        
        if specific_date:
            # Filter by specific date
            specific_date_obj = datetime.strptime(specific_date, '%Y-%m-%d').date()
            date_start = timezone.make_aware(datetime.combine(specific_date_obj, datetime.min.time()))
            date_end = timezone.make_aware(datetime.combine(specific_date_obj, datetime.max.time()))
            base_queryset = base_queryset.filter(date__range=[date_start, date_end])
        elif time_filter == 'day':
            # Today's tasks
            date_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
            date_end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
            base_queryset = base_queryset.filter(date__range=[date_start, date_end])
        elif time_filter == 'week':
            # Current week (Monday to Sunday)
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            week_start = timezone.make_aware(datetime.combine(start_of_week, datetime.min.time()))
            week_end = timezone.make_aware(datetime.combine(end_of_week, datetime.max.time()))
            base_queryset = base_queryset.filter(date__range=[week_start, week_end])
        elif time_filter == 'month':
            # Current month
            start_of_month = today.replace(day=1)
            if today.month == 12:
                end_of_month = today.replace(year=today.year+1, month=1, day=1) - timedelta(days=1)
            else:
                end_of_month = today.replace(month=today.month+1, day=1) - timedelta(days=1)
            month_start = timezone.make_aware(datetime.combine(start_of_month, datetime.min.time()))
            month_end = timezone.make_aware(datetime.combine(end_of_month, datetime.max.time()))
            base_queryset = base_queryset.filter(date__range=[month_start, month_end])
        
        # Get all status objects from master.models
        all_statuses = Status.objects.all()
        
        # Calculate total tasks count
        total_tasks = base_queryset.count()
        
        # Calculate counts and percentages for each status
        status_overview = []
        
        for status_obj in all_statuses:
            status_count = base_queryset.filter(status=status_obj).count()
            percentage = (status_count / total_tasks * 100) if total_tasks > 0 else 0
            
            status_overview.append({
                "status_id": status_obj.id,
                "status_name": status_obj.name,
                "count": status_count,
                "percentage": round(percentage, 2),
                "formatted_percentage": f"{round(percentage, 2)}%"
            })
        
        # Sort by count in descending order
        status_overview.sort(key=lambda x: x['count'], reverse=True)
        
        # Get specific status objects for summary
        in_progress_status = Status.objects.filter(name__iexact='In Progress').first()
        completed_status = Status.objects.filter(name__iexact='Completed').first()
        rejected_status = Status.objects.filter(name__iexact='Rejected').first()
        draft_status = Status.objects.filter(name__iexact='Draft').first()
        
        # Calculate pending approval tasks
        pending_approval = 0
        if user.is_staff:
            pending_approval = base_queryset.filter(
                Q(l1_approved_at__isnull=True, l1_approver__isnull=False) |
                Q(l2_approved_at__isnull=True, l2_approver__isnull=False)
            ).exclude(
                Q(l1_rejected_at__isnull=False) | Q(l2_rejected_at__isnull=False)
            ).count()
        else:
            pending_approval = base_queryset.filter(
                Q(l1_approver=user, l1_approved_at__isnull=True, l1_rejected_at__isnull=True) |
                Q(l2_approver=user, l2_approved_at__isnull=True, l2_rejected_at__isnull=True)
            ).count()
        
        # Prepare response
        response_data = {
            "filter_applied": {
                "type": time_filter,
                "date": specific_date if specific_date else None,
                "period": self._get_period_description(time_filter, today, specific_date)
            },
            "total_tasks": total_tasks,
            "status_overview": status_overview,
            "summary": {
                "in_progress": {
                    "count": base_queryset.filter(status=in_progress_status).count() if in_progress_status else 0,
                    "percentage": round((base_queryset.filter(status=in_progress_status).count() / total_tasks * 100), 2) if total_tasks > 0 and in_progress_status else 0
                },
                "completed": {
                    "count": base_queryset.filter(status=completed_status).count() if completed_status else 0,
                    "percentage": round((base_queryset.filter(status=completed_status).count() / total_tasks * 100), 2) if total_tasks > 0 and completed_status else 0
                },
                "rejected": {
                    "count": base_queryset.filter(status=rejected_status).count() if rejected_status else 0,
                    "percentage": round((base_queryset.filter(status=rejected_status).count() / total_tasks * 100), 2) if total_tasks > 0 and rejected_status else 0
                },
                "draft": {
                    "count": base_queryset.filter(status=draft_status).count() if draft_status else 0,
                    "percentage": round((base_queryset.filter(status=draft_status).count() / total_tasks * 100), 2) if total_tasks > 0 and draft_status else 0
                },
                "pending_approval": {
                    "count": pending_approval,
                    "percentage": round((pending_approval / total_tasks * 100), 2) if total_tasks > 0 else 0
                }
            }
        }
        
        return Response(response_data, status=http_status.HTTP_200_OK)
    
    def _get_period_description(self, time_filter, today, specific_date):
        """Helper method to get human-readable period description"""
        if specific_date:
            return f"Tasks for {specific_date}"
        elif time_filter == 'day':
            return f"Tasks for {today.strftime('%Y-%m-%d')}"
        elif time_filter == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return f"Tasks from {start_of_week.strftime('%Y-%m-%d')} to {end_of_week.strftime('%Y-%m-%d')}"
        elif time_filter == 'month':
            return f"Tasks for {today.strftime('%B %Y')}"
        else:
            return "All tasks"
        
# class TimeDistributionByMembersAPIView(APIView):
#     permission_classes = [IsAuthenticated]
    
#     def get(self, request):
#         user = request.user
        
#         # Get filter parameters
#         time_filter = request.query_params.get('time_filter', 'all')  # all, day, week, month
#         specific_date = request.query_params.get('date')  # For specific date
#         start_date = request.query_params.get('start_date')  # Custom date range
#         end_date = request.query_params.get('end_date')
        
#         # Base queryset
#         if user.is_staff:
#             base_queryset = TaskList.objects.select_related('user', 'status')
#         else:
#             base_queryset = TaskList.objects.select_related('user', 'status').filter(
#                 Q(user=user) |
#                 Q(l1_approver=user) |
#                 Q(l2_approver=user)
#             )
        
#         # Apply time filters
#         base_queryset = self._apply_time_filters(base_queryset, time_filter, specific_date, start_date, end_date)
        
#         # Get completed status for time calculation
#         completed_status = Status.objects.filter(name__iexact='Completed').first()
        
#         # Calculate time distribution by member
#         members_data = []
        
#         # Get all users who have tasks in the filtered queryset
#         user_ids = base_queryset.values_list('user_id', flat=True).distinct()
        
#         for user_id in user_ids:
#             user_tasks = base_queryset.filter(user_id=user_id)
#             user_obj = User.objects.get(id=user_id)
            
#             # Calculate total hours (all tasks)
#             total_hours = user_tasks.aggregate(total=Sum('duration'))['total'] or 0
            
#             # Calculate completed hours (only completed tasks)
#             completed_hours = 0
#             if completed_status:
#                 completed_hours = user_tasks.filter(status=completed_status).aggregate(total=Sum('duration'))['total'] or 0
            
#             # Calculate pending hours (in progress tasks)
#             in_progress_status = Status.objects.filter(name__iexact='In Progress').first()
#             pending_hours = 0
#             if in_progress_status:
#                 pending_hours = user_tasks.filter(status=in_progress_status).aggregate(total=Sum('duration'))['total'] or 0
            
#             # Calculate task count
#             total_tasks = user_tasks.count()
#             completed_tasks = user_tasks.filter(status=completed_status).count() if completed_status else 0
            
#             members_data.append({
#                 "user_id": user_id,
#                 # "name": user_obj.get_firstnamee() or user_obj.username,
#                 "username": user_obj.firstname,
#                 "email": user_obj.email,
#                 "total_hours": float(total_hours),
#                 "completed_hours": float(completed_hours),
#                 "pending_hours": float(pending_hours),
#                 "total_tasks": total_tasks,
#                 "completed_tasks": completed_tasks,
#                 "completion_rate": round((completed_tasks / total_tasks * 100), 2) if total_tasks > 0 else 0,
#                 "avg_hours_per_task": round(float(total_hours / total_tasks), 2) if total_tasks > 0 else 0,
#             })
        
#         # Calculate total hours across all members
#         total_all_hours = sum(member['total_hours'] for member in members_data)
        
#         # Add percentages to each member
#         for member in members_data:
#             member['percentage'] = round((member['total_hours'] / total_all_hours * 100), 2) if total_all_hours > 0 else 0
#             member['formatted_percentage'] = f"{member['percentage']}%"
        
#         # Sort by total hours descending
#         members_data.sort(key=lambda x: x['total_hours'], reverse=True)
        
#         # Calculate summary statistics
#         active_members = len([m for m in members_data if m['total_hours'] > 0])
        
#         response_data = {
#             "filter_applied": self._get_filter_description(time_filter, specific_date, start_date, end_date),
#             "summary": {
#                 "total_members": len(members_data),
#                 "active_members": active_members,
#                 "total_hours_all_members": float(total_all_hours),
#                 "average_hours_per_member": round(float(total_all_hours / len(members_data)), 2) if members_data else 0,
#                 "total_completed_hours": sum(m['completed_hours'] for m in members_data),
#                 "total_pending_hours": sum(m['pending_hours'] for m in members_data),
#             },
#             "members": members_data
#         }
        
#         return Response(response_data, status=http_status.HTTP_200_OK)
    
#     def _apply_time_filters(self, queryset, time_filter, specific_date, start_date, end_date):
#         """Apply time filters to queryset"""
#         today = timezone.now().date()
        
#         if specific_date:
#             specific_date_obj = datetime.strptime(specific_date, '%Y-%m-%d').date()
#             date_start = timezone.make_aware(datetime.combine(specific_date_obj, datetime.min.time()))
#             date_end = timezone.make_aware(datetime.combine(specific_date_obj, datetime.max.time()))
#             return queryset.filter(date__range=[date_start, date_end])
        
#         elif start_date and end_date:
#             start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
#             end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
#             start_datetime = timezone.make_aware(datetime.combine(start_date_obj, datetime.min.time()))
#             end_datetime = timezone.make_aware(datetime.combine(end_date_obj, datetime.max.time()))
#             return queryset.filter(date__range=[start_datetime, end_datetime])
        
#         elif time_filter == 'day':
#             date_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
#             date_end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
#             return queryset.filter(date__range=[date_start, date_end])
        
#         elif time_filter == 'week':
#             start_of_week = today - timedelta(days=today.weekday())
#             end_of_week = start_of_week + timedelta(days=6)
#             week_start = timezone.make_aware(datetime.combine(start_of_week, datetime.min.time()))
#             week_end = timezone.make_aware(datetime.combine(end_of_week, datetime.max.time()))
#             return queryset.filter(date__range=[week_start, week_end])
        
#         elif time_filter == 'month':
#             start_of_month = today.replace(day=1)
#             if today.month == 12:
#                 end_of_month = today.replace(year=today.year+1, month=1, day=1) - timedelta(days=1)
#             else:
#                 end_of_month = today.replace(month=today.month+1, day=1) - timedelta(days=1)
#             month_start = timezone.make_aware(datetime.combine(start_of_month, datetime.min.time()))
#             month_end = timezone.make_aware(datetime.combine(end_of_month, datetime.max.time()))
#             return queryset.filter(date__range=[month_start, month_end])
        
#         return queryset
    
#     def _get_filter_description(self, time_filter, specific_date, start_date, end_date):
#         """Get human-readable filter description"""
#         if specific_date:
#             return f"Tasks for {specific_date}"
#         elif start_date and end_date:
#             return f"Tasks from {start_date} to {end_date}"
#         elif time_filter == 'day':
#             return f"Today's tasks ({timezone.now().date().strftime('%Y-%m-%d')})"
#         elif time_filter == 'week':
#             today = timezone.now().date()
#             start_of_week = today - timedelta(days=today.weekday())
#             end_of_week = start_of_week + timedelta(days=6)
#             return f"This week's tasks ({start_of_week.strftime('%Y-%m-%d')} to {end_of_week.strftime('%Y-%m-%d')})"
#         elif time_filter == 'month':
#             return f"This month's tasks ({timezone.now().date().strftime('%B %Y')})"
#         else:
#             return "All tasks"
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status as http_status
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from .models import TaskList, Status

User = get_user_model()

class TimeDistributionByMembersAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def parse_duration_to_hours(self, duration_str):
        """Convert duration string like '4.50', '1h 30m', or '4h 30m' to decimal hours (4.5)"""
        if not duration_str:
            return 0
        
        if isinstance(duration_str, (int, float)):
            return float(duration_str)
        
        duration_str = str(duration_str).strip()
        
        # Try parsing as decimal number first
        try:
            return float(duration_str)
        except ValueError:
            pass
        
        # Parse "Xh Ym" format
        hours = 0
        minutes = 0
        
        hour_match = re.search(r'(\d+(?:\.\d+)?)\s*h', duration_str, re.IGNORECASE)
        if hour_match:
            hours = float(hour_match.group(1))
        
        minute_match = re.search(r'(\d+(?:\.\d+)?)\s*m', duration_str, re.IGNORECASE)
        if minute_match:
            minutes = float(minute_match.group(1))
        
        # If no patterns matched, try to convert directly
        if not hour_match and not minute_match:
            try:
                return float(duration_str)
            except ValueError:
                return 0
        
        return hours + (minutes / 60)
    
    def get(self, request):
        user = request.user
        
        # Get filter parameters
        view_param = request.query_params.get('view', 'daily')
        specific_date = request.query_params.get('date')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Base queryset with related fields
        if user.is_staff:
            base_queryset = TaskList.objects.select_related('user', 'status')
        else:
            base_queryset = TaskList.objects.select_related('user', 'status').filter(
                Q(user=user) |
                Q(l1_approver=user) |
                Q(l2_approver=user)
            )
        
        # Apply time filters
        base_queryset = self._apply_time_filters(base_queryset, view_param, specific_date, start_date, end_date)
        
        # Get all tasks with their durations and status
        tasks = base_queryset.values('user_id', 'duration', 'status__name')
        
        # Aggregate manually to handle string durations
        members_data_dict = {}
        
        for task in tasks:
            user_id = task['user_id']
            duration_str = task['duration']
            status_name = task['status__name']
            
            # Skip if no user_id
            if not user_id:
                continue
                
            hours = self.parse_duration_to_hours(duration_str)
            
            if user_id not in members_data_dict:
                members_data_dict[user_id] = {
                    'user_id': user_id,
                    'total_hours': 0,
                    'completed_hours': 0,
                    'pending_hours': 0,
                    'total_tasks': 0,
                    'completed_tasks': 0,
                }
            
            members_data_dict[user_id]['total_hours'] += hours
            members_data_dict[user_id]['total_tasks'] += 1
            
            # Check for completed status using model's helper or direct check
            if status_name and status_name.lower() in ['completed', 'done', 'finished']:
                members_data_dict[user_id]['completed_hours'] += hours
                members_data_dict[user_id]['completed_tasks'] += 1
            
            # Check for in progress status
            if status_name and status_name.lower() in ['inprogress', 'in progress']:
                members_data_dict[user_id]['pending_hours'] += hours
        
        # Get user details and build final response
        members_data = []
        for user_id, data in members_data_dict.items():
            try:
                user_obj = User.objects.get(id=user_id)
                
                total_hours = data['total_hours']
                completed_hours = data['completed_hours']
                pending_hours = data['pending_hours']
                total_tasks = data['total_tasks']
                completed_tasks = data['completed_tasks']
                
                completion_rate = round((completed_tasks / total_tasks * 100), 2) if total_tasks > 0 else 0
                avg_hours_per_task = round(total_hours / total_tasks, 2) if total_tasks > 0 else 0
                
                # Get username/display name - adjust based on your User model fields
                display_name = (
                    getattr(user_obj, 'firstname', None) or 
                    getattr(user_obj, 'first_name', None) or 
                    user_obj.username
                )
                
                members_data.append({
                    "user_id": user_id,
                    "username": display_name,
                    "email": user_obj.email,
                    "total_hours": round(total_hours, 2),
                    "completed_hours": round(completed_hours, 2),
                    "pending_hours": round(pending_hours, 2),
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_tasks,
                    "completion_rate": completion_rate,
                    "avg_hours_per_task": avg_hours_per_task,
                })
            except User.DoesNotExist:
                continue
        
        # Calculate totals
        total_all_hours = sum(member['total_hours'] for member in members_data)
        
        # Add percentages
        for member in members_data:
            member['percentage'] = round((member['total_hours'] / total_all_hours * 100), 2) if total_all_hours > 0 else 0
            member['formatted_percentage'] = f"{member['percentage']}%"
        
        # Sort by total hours descending
        members_data.sort(key=lambda x: x['total_hours'], reverse=True)
        
        # Calculate summary
        active_members = len([m for m in members_data if m['total_hours'] > 0])
        
        response_data = {
            "filter_applied": self._get_filter_description(view_param, specific_date, start_date, end_date),
            "summary": {
                "total_members": len(members_data),
                "active_members": active_members,
                "total_hours_all_members": round(total_all_hours, 2),
                "average_hours_per_member": round(total_all_hours / len(members_data), 2) if members_data else 0,
                "total_completed_hours": round(sum(m['completed_hours'] for m in members_data), 2),
                "total_pending_hours": round(sum(m['pending_hours'] for m in members_data), 2),
            },
            "members": members_data
        }
        
        return Response(response_data, status=http_status.HTTP_200_OK)
    
    def _apply_time_filters(self, queryset, view_param, specific_date, start_date, end_date):
        """Apply time filters to queryset based on view parameter"""
        today = timezone.now().date()
        
        if specific_date:
            specific_date_obj = datetime.strptime(specific_date, '%Y-%m-%d').date()
            return queryset.filter(date=specific_date_obj)
        
        elif start_date and end_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            return queryset.filter(date__range=[start_date_obj, end_date_obj])
        
        elif view_param == 'daily':
            return queryset.filter(date=today)
        
        elif view_param == 'weekly':
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return queryset.filter(date__range=[start_of_week, end_of_week])
        
        elif view_param == 'monthly':
            start_of_month = today.replace(day=1)
            if today.month == 12:
                end_of_month = today.replace(year=today.year+1, month=1, day=1) - timedelta(days=1)
            else:
                end_of_month = today.replace(month=today.month+1, day=1) - timedelta(days=1)
            return queryset.filter(date__range=[start_of_month, end_of_month])
        
        return queryset
    
    def _get_filter_description(self, view_param, specific_date, start_date, end_date):
        """Get human-readable filter description"""
        if specific_date:
            return f"Tasks for {specific_date}"
        elif start_date and end_date:
            return f"Tasks from {start_date} to {end_date}"
        elif view_param == 'daily':
            return f"Today's tasks ({timezone.now().date().strftime('%Y-%m-%d')})"
        elif view_param == 'weekly':
            today = timezone.now().date()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return f"This week's tasks ({start_of_week.strftime('%Y-%m-%d')} to {end_of_week.strftime('%Y-%m-%d')})"
        elif view_param == 'monthly':
            return f"This month's tasks ({timezone.now().date().strftime('%B %Y')})"
        else:
            return "All tasks"        
class TaskCompletionSimpleAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get view type parameter
        view_type = request.query_params.get('view', 'daily')  # daily, weekly, monthly
        
        # Get completed status
        completed_status = Status.objects.filter(name__iexact='Completed').first()
        
        # Base queryset based on user permissions
        if user.is_staff:
            base_queryset = TaskList.objects.all()
        else:
            base_queryset = TaskList.objects.filter(
                Q(user=user) |
                Q(l1_approver=user) |
                Q(l2_approver=user)
            )
        
        # Get data based on view type
        if view_type == 'daily':
            data = self._get_daily_data(base_queryset, completed_status)
        elif view_type == 'week':
            data = self._get_weekly_data(base_queryset, completed_status)
        elif view_type == 'month':
            data = self._get_monthly_data(base_queryset, completed_status)
        else:
            data = self._get_daily_data(base_queryset, completed_status)
        
        return Response(data, status=http_status.HTTP_200_OK)
    
    def _get_daily_data(self, queryset, completed_status):
        """Get today's completed tasks data"""
        today = timezone.now().date()
        today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        today_end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
        
        daily_tasks = queryset.filter(date__range=[today_start, today_end])
        total_tasks = daily_tasks.count()
        completed_tasks = 0
        if completed_status:
            completed_tasks = daily_tasks.filter(status=completed_status).count()
        
        completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        return {
            "view": "daily",
            "completed_count": completed_tasks,
            "percentage": round(completion_percentage, 2)
        }
    
    def _get_weekly_data(self, queryset, completed_status):
        """Get current week's completed tasks data"""
        today = timezone.now().date()
        
        # Get week start (Monday) and end (Sunday)
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        week_start = timezone.make_aware(datetime.combine(start_of_week, datetime.min.time()))
        week_end = timezone.make_aware(datetime.combine(end_of_week, datetime.max.time()))
        
        weekly_tasks = queryset.filter(date__range=[week_start, week_end])
        total_tasks = weekly_tasks.count()
        completed_tasks = 0
        if completed_status:
            completed_tasks = weekly_tasks.filter(status=completed_status).count()
        
        completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        return {
            "view": "weekly",
            "completed_count": completed_tasks,
            "percentage": round(completion_percentage, 2)
        }
    
    def _get_monthly_data(self, queryset, completed_status):
        """Get current month's completed tasks data"""
        today = timezone.now().date()
        
        # Get month start and end
        start_of_month = today.replace(day=1)
        if today.month == 12:
            end_of_month = today.replace(year=today.year+1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = today.replace(month=today.month+1, day=1) - timedelta(days=1)
        
        month_start = timezone.make_aware(datetime.combine(start_of_month, datetime.min.time()))
        month_end = timezone.make_aware(datetime.combine(end_of_month, datetime.max.time()))
        
        monthly_tasks = queryset.filter(date__range=[month_start, month_end])
        total_tasks = monthly_tasks.count()
        completed_tasks = 0
        if completed_status:
            completed_tasks = monthly_tasks.filter(status=completed_status).count()
        
        completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        return {
            "view": "monthly",
            "completed_count": completed_tasks,
            "percentage": round(completion_percentage, 2)
        }