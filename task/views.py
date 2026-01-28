# from django.shortcuts import render

# # Create your views here.
# from django.http import HttpResponse

# def task_home(request):
#     return HttpResponse("Task app is working 🚀")
# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from .models import TaskList
from .serializers import TaskListSerializer


class TaskListAPIView(APIView):
    """
    Single view handling all operations for TaskList:
    • GET    /tasks/          → list current user's tasks
    • POST   /tasks/          → create new task
    • GET    /tasks/<pk>/     → retrieve single task
    • PUT    /tasks/<pk>/     → full update
    • DELETE /tasks/<pk>/     → delete task
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk):
        """
        Helper: get task by pk — only if it belongs to the current user
        """
        task = get_object_or_404(TaskList, pk=pk)
        if task.user != self.request.user:
            self.permission_denied(self.request)
        return task

    def get(self, request, pk=None):
        if pk is not None:
            # Retrieve single task
            task = self.get_object(pk)
            serializer = TaskListSerializer(task)
            return Response(serializer.data)

        # List all tasks of current user
        tasks = TaskList.objects.filter(
            user=request.user
        ).select_related(
            'platform', 'task', 'subtask', 'status'
        ).order_by('-date', 'task__name')

        serializer = TaskListSerializer(tasks, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Create new task
        serializer = TaskListSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            serializer.save()  # calls create() → sets user
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        # Full update
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
        # Delete (hard delete in this version)
        task = self.get_object(pk)
        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)