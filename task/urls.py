# from django.urls import path
# from . import views

# urlpatterns = [
#     path('', views.task_home, name='task-home'),
# ]
from django.urls import path
from .views import TaskListAPIView,TaskListAuditLogAPIView,SimpleTimeLogView,TimeLogStatsAPIView,WorkHoursOverviewAPIView

app_name = 'tasks'

urlpatterns = [
    # List + Create
    path('createTask/', TaskListAPIView.as_view(), name='task-list'),
    path('taskslist/', TaskListAPIView.as_view(), name='task-list'),

    # Detail + Update + Delete
    path('taskslist/<int:pk>/', TaskListAPIView.as_view(), name='task-detail'),
    path('tasks/<int:pk>/', TaskListAPIView.as_view(), name='task-detail'),
     path('tasks/audit-logs/', TaskListAuditLogAPIView.as_view(), name='task-audit-logs'),
    path('tasks/<int:task_id>/audit-logs/', TaskListAuditLogAPIView.as_view(), name='task-specific-audit-logs'),
    path('simple-time-logs/', SimpleTimeLogView.as_view(), name='simple-time-logs'),
    path('simple-time-logs/<int:pk>/', SimpleTimeLogView.as_view(), name='simple-time-log-detail'),
    path('time-logs/stats/', TimeLogStatsAPIView.as_view(), name='time-logs-stats'),
    path('work-hours/', WorkHoursOverviewAPIView.as_view(), name='work-hours'),
]