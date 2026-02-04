from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Entity, Department, Location, Task ,SubTask, Role, Platform, Status,Holiday,EmailTemplate

from .serializers import EntitySerializer,DepartmentSerializer, LocationSerializer, TaskSerializer, SubTaskSerializer, RoleSerializer, PlatformSerializer,StatusSerializer,HolidaySerializer,EmailTemplateSerializer

# Create your views here.
class EntityAPIView(APIView):

    def get(self, request, pk=None):
        """
        List all entities OR retrieve single entity
        """
        if pk:
            entity = get_object_or_404(Entity, pk=pk, is_active=True)
            serializer = EntitySerializer(entity)
            return Response(serializer.data)

        entities = Entity.objects.filter(is_active=True)
        serializer = EntitySerializer(entities, many=True)
        return Response(serializer.data)

    def post(self, request):
        """
        Create entity
        """
        serializer = EntitySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        """
        Update entity
        """
        entity = get_object_or_404(Entity, pk=pk, is_active=True)
        serializer = EntitySerializer(entity, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """
        Soft delete entity
        """
        entity = get_object_or_404(Entity, pk=pk, is_active=True)
        entity.is_active = False
        entity.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
class DepartmentAPIView(APIView):

    def get(self, request, pk=None):
        if pk:
            department = get_object_or_404(Department, pk=pk, is_active=True)
            serializer = DepartmentSerializer(department)
            return Response(serializer.data)

        departments = Department.objects.filter(is_active=True)
        serializer = DepartmentSerializer(departments, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = DepartmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        department = get_object_or_404(Department, pk=pk, is_active=True)
        serializer = DepartmentSerializer(department, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        department = get_object_or_404(Department, pk=pk, is_active=True)
        department.is_active = False
        department.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    

class LocationAPIView(APIView):

    def get(self, request, pk=None):
        if pk:
            location = get_object_or_404(Location, pk=pk, is_active=True)
            serializer = LocationSerializer(location)
            return Response(serializer.data)

        locations = Location.objects.filter(is_active=True)
        serializer = LocationSerializer(locations, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = LocationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        location = get_object_or_404(Location, pk=pk, is_active=True)
        serializer = LocationSerializer(location, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        location = get_object_or_404(Location, pk=pk, is_active=True)
        location.is_active = False
        location.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    

class TaskAPIView(APIView):

    def get(self, request, pk=None):
        if pk:
            task = get_object_or_404(Task, pk=pk, is_active=True)
            serializer = TaskSerializer(task)
            return Response(serializer.data)

        tasks = Task.objects.filter(is_active=True)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = TaskSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        task = get_object_or_404(Task, pk=pk, is_active=True)
        serializer = TaskSerializer(task, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        task = get_object_or_404(Task, pk=pk, is_active=True)
        task.is_active = False
        task.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
class SubTaskAPIView(APIView):

    def get(self, request, pk=None):
        if pk:
            subtask = get_object_or_404(SubTask, pk=pk, is_active=True)
            serializer = SubTaskSerializer(subtask)
            return Response(serializer.data)

        # Optional: filter by task_id
        task_id = request.query_params.get('task_id')
        queryset = SubTask.objects.filter(is_active=True)

        if task_id:
            queryset = queryset.filter(task_id=task_id)

        serializer = SubTaskSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = SubTaskSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        subtask = get_object_or_404(SubTask, pk=pk, is_active=True)
        serializer = SubTaskSerializer(subtask, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        subtask = get_object_or_404(SubTask, pk=pk, is_active=True)
        subtask.is_active = False  # soft delete
        subtask.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
class RoleAPIView(APIView):

    def get(self, request, pk=None):
        if pk:
            role = get_object_or_404(Role, pk=pk, is_active=True)
            serializer = RoleSerializer(role)
            return Response(serializer.data)

        roles = Role.objects.filter(is_active=True)
        serializer = RoleSerializer(roles, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = RoleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        role = get_object_or_404(Role, pk=pk, is_active=True)
        serializer = RoleSerializer(role, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_object_or_404(Role, pk=pk, is_active=True)
        role.is_active = False
        role.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

class PlatformAPIView(APIView):

    def get(self, request, pk=None):
        if pk:
            platform = get_object_or_404(Platform, pk=pk, is_active=True)
            serializer = PlatformSerializer(platform)
            return Response(serializer.data)

        platforms = Platform.objects.filter(is_active=True)
        serializer = PlatformSerializer(platforms, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = PlatformSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        platform = get_object_or_404(Platform, pk=pk, is_active=True)
        serializer = PlatformSerializer(platform, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        platform = get_object_or_404(Platform, pk=pk, is_active=True)
        platform.is_active = False
        platform.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
class StatusAPIView(APIView):

    def get(self, request, pk=None):
        if pk:
            status_obj = get_object_or_404(Status, pk=pk, is_active=True)
            serializer = StatusSerializer(status_obj)
            return Response(serializer.data)

        statuses = Status.objects.filter(is_active=True)
        serializer = StatusSerializer(statuses, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = StatusSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        status_obj = get_object_or_404(Status, pk=pk, is_active=True)
        serializer = StatusSerializer(status_obj, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        status_obj = get_object_or_404(Status, pk=pk, is_active=True)
        status_obj.is_active = False
        status_obj.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
class HolidayAPIView(APIView):
    """
    GET        /holidays/           → List
    GET        /holidays/<id>/       → Retrieve
    POST       /holidays/           → Create
    PUT        /holidays/<id>/       → Update
    """

    def get(self, request, pk=None):
        if pk:
            holiday = get_object_or_404(Holiday, pk=pk, status__in=[1, 2])
            serializer = HolidaySerializer(holiday)
            return Response(serializer.data)

        holidays = Holiday.objects.filter(status__in=[1, 2]).order_by('-date')
        serializer = HolidaySerializer(holidays, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = HolidaySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                created_by=request.user,
                created_ip=request.META.get('REMOTE_ADDR')
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Holiday ID is required for update"},
                status=status.HTTP_400_BAD_REQUEST
            )

        holiday = get_object_or_404(Holiday, pk=pk)
        serializer = HolidaySerializer(holiday, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save(
                modified_by=request.user,
                modified_ip=request.META.get('REMOTE_ADDR')
            )
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class EmailTemplateAPIView(APIView):
    """
    GET        /email-templates/           → List
    GET        /email-templates/<id>/       → Retrieve
    POST       /email-templates/           → Create
    PUT        /email-templates/<id>/       → Update
    """

    def get(self, request, pk=None):
        if pk:
            template = get_object_or_404(EmailTemplate, pk=pk)
            serializer = EmailTemplateSerializer(template)
            return Response(serializer.data)

        templates = EmailTemplate.objects.all().order_by('email_event')
        serializer = EmailTemplateSerializer(templates, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = EmailTemplateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Template ID is required for update"},
                status=status.HTTP_400_BAD_REQUEST
            )

        template = get_object_or_404(EmailTemplate, pk=pk)
        serializer = EmailTemplateSerializer(template, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


