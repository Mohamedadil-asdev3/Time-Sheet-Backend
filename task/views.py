# from rest_framework import generics, status
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response
# from django.shortcuts import get_object_or_404
# from .models import TaskList
# from .serializers import TaskListSerializer


# from collections import defaultdict
# from rest_framework import generics, status
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated

# class TaskListAPIView(generics.ListCreateAPIView):
#     permission_classes = [IsAuthenticated]
#     serializer_class = TaskListSerializer

#     def get_queryset(self):
#         return (
#             TaskList.objects
#             .filter(user=self.request.user)
#             .select_related('platform', 'task', 'subtask', 'status')
#             .order_by('-date', 'task__name')
#         )

#     def get_serializer(self, *args, **kwargs):
#         if isinstance(self.request.data, list):
#             kwargs['many'] = True
#         return super().get_serializer(*args, **kwargs)

#     def perform_create(self, serializer):
#         serializer.save(user=self.request.user)

#     def list(self, request, *args, **kwargs):
#         queryset = self.get_queryset()
#         serializer = self.get_serializer(queryset, many=True)

#         grouped = defaultdict(list)

#         for item in serializer.data:
#             grouped[item["date"]].append(item)

#         response_data = [
#             {
#                 "date": date,
#                 "tasks": tasks
#             }
#             for date, tasks in grouped.items()
#         ]

#         return Response(response_data, status=status.HTTP_200_OK)
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from collections import defaultdict
from django.shortcuts import get_object_or_404
from .models import TaskList
from .serializers import TaskListSerializer


# class TaskListAPIView(APIView):
#     """
#     Single view handling all operations for TaskList:
#     • GET    /tasks/          → list current user's tasks
#     • POST   /tasks/          → create new task
#     • GET    /tasks/<pk>/     → retrieve single task
#     • PUT    /tasks/<pk>/     → full update
#     • DELETE /tasks/<pk>/     → delete task
#     """

#     permission_classes = [permissions.IsAuthenticated]

#     def get_object(self, pk):
#         """
#         Helper: get task by pk — only if it belongs to the current user
#         """
#         task = get_object_or_404(TaskList, pk=pk)
#         if task.user != self.request.user:
#             self.permission_denied(self.request)
#         return task

#     def get(self, request, pk=None):
#         if pk is not None:
#             # Retrieve single task
#             task = self.get_object(pk)
#             serializer = TaskListSerializer(task)
#             return Response(serializer.data)

#         # List all tasks of current user
#         tasks = TaskList.objects.filter(
#             user=request.user
#         ).select_related(
#             'platform', 'task', 'subtask', 'status'
#         ).order_by('-date', 'task__name')

#         serializer = TaskListSerializer(tasks, many=True)
#         return Response(serializer.data)

#     def post(self, request):
#         # Create new task
#         serializer = TaskListSerializer(
#             data=request.data,
#             context={'request': request}
#         )

#         if serializer.is_valid():
#             serializer.save()  # calls create() → sets user
#             return Response(serializer.data, status=status.HTTP_201_CREATED)

#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     def put(self, request, pk):
#         # Full update
#         task = self.get_object(pk)
#         serializer = TaskListSerializer(
#             task,
#             data=request.data,
#             context={'request': request}
#         )

#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data)

#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     def delete(self, request, pk):
#         # Delete (hard delete in this version)
#         task = self.get_object(pk)
#         task.delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)


class TaskListAPIView(APIView):
    """
    Single view handling all operations for TaskList:
    • GET    /tasks/          → list current user's tasks (with filters)
    • POST   /tasks/          → create new task
    • GET    /tasks/<pk>/     → retrieve single task
    • PUT    /tasks/<pk>/     → full update
    • DELETE /tasks/<pk>/     → delete task
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TaskListSerializer
    lookup_field = 'pk'

    def get_queryset(self):
        return (
            TaskList.objects
            .filter(user=self.request.user)
            .select_related('platform', 'task', 'subtask', 'status')
            .order_by('-date', 'task__name')
        )

    def get_object(self, pk):
        task = get_object_or_404(TaskList, pk=pk)
        if task.user != self.request.user:
            self.permission_denied(self.request)
        return task

    def apply_filters(self, request, queryset):
        """
        Common filters for list API
        """
        start_date = request.query_params.get('start_date')
        end_date   = request.query_params.get('end_date')
        platform   = request.query_params.get('platform')
        task       = request.query_params.get('task')
        status     = request.query_params.get('status')
        search     = request.query_params.get('search')

        if start_date:
            queryset = queryset.filter(date__gte=start_date)

        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        if platform:
            queryset = queryset.filter(platform_id=platform)

        if task:
            queryset = queryset.filter(task_id=task)

        if status:
            queryset = queryset.filter(status_id=status)

        if search:
            queryset = queryset.filter(
                Q(description__icontains=search) |
                Q(bitrix_id__icontains=search) |
                Q(task__name__icontains=search) |
                Q(subtask__name__icontains=search)
            )

        return queryset

    def get(self, request, pk=None):
        if pk is not None:
            task = self.get_object(pk)
            serializer = TaskListSerializer(task)
            return Response(serializer.data)

        queryset = TaskList.objects.filter(
            user=request.user
        ).select_related(
            'platform', 'task', 'subtask', 'status'
        )

        queryset = self.apply_filters(request, queryset)

        queryset = queryset.order_by('-date', 'task__name')

        serializer = TaskListSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = TaskListSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        task = self.get_object(pk)
        serializer = TaskListSerializer(
            task,
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        task = self.get_object(pk)
        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
