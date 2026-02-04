# from django.urls import path
# from . import views

# urlpatterns = [
#     path('', views.task_home, name='task-home'),
# ]
from django.urls import path
from .views import TaskListAPIView

app_name = 'tasks'

urlpatterns = [
    # List + Create
    path('createTask/', TaskListAPIView.as_view(), name='task-list'),
    path('taskslist/', TaskListAPIView.as_view(), name='task-list'),

    # Detail + Update + Delete
    path('taskslist/<int:pk>/', TaskListAPIView.as_view(), name='task-detail'),
    path('tasks/<int:pk>/', TaskListAPIView.as_view(), name='task-detail'),
    
]