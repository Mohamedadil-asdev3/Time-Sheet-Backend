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


class TaskListAPIView(generics.ListCreateAPIView, generics.RetrieveDestroyAPIView):
    """
    List (grouped by date), Create (single/bulk), Retrieve, Delete tasks
    - Delete allowed ONLY when status is "draft"
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

    def get_serializer(self, *args, **kwargs):
        if isinstance(self.request.data, list):
            kwargs['many'] = True
        return super().get_serializer(*args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        grouped = defaultdict(list)
        for item in serializer.data:
            grouped[item["date"]].append(item)

        response_data = [
            {"date": date, "tasks": tasks}
            for date, tasks in sorted(grouped.items(), reverse=True)
        ]

        return Response(response_data, status=status.HTTP_200_OK)

    def get_object(self):
        """
        Retrieve task and check ownership
        """
        pk = self.kwargs.get('pk')
        task = get_object_or_404(TaskList, pk=pk)
        if task.user != self.request.user:
            self.permission_denied(self.request)
        return task

    def destroy(self, request, *args, **kwargs):
        """
        DELETE allowed ONLY if status is "draft"
        """
        task = self.get_object()

        # Check status before allowing delete
        if task.status and task.status.name.lower() == "draft":
            task.delete()
            return Response({'message': 'Task Deleted Successfully'},status=status.HTTP_200_OK)
        else:
            return Response(
                {
                    "detail": "Only tasks in 'draft' status can be deleted. "
                              "Other statuses are protected."
                },
                status=status.HTTP_403_FORBIDDEN
            )