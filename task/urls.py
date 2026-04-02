# from django.urls import path
# from . import views

# urlpatterns = [
#     path('', views.task_home, name='task-home'),
# ]
from django.urls import path
from .views import (
TaskListAPIView,TaskListAuditLogAPIView,SimpleTimeLogView,TimeLogStatsAPIView,DailyTimelineAPIView,WorkHoursOverviewAPIView,TopMembersAPIView,TaskApprovalAPIView,
TimeDistributionAPIView,RecentTasksAPIView,TopUsedTasksAPIView,TopPlatformsAPIView,PlatformPerformanceAPIView,ProfileAPIView,ApprovalTableAPIView,
 RecentRequestAPIView,ApprovalStatusOverviewAPIView,TaskCountsAPIView,TaskStatusOverviewAPIView,TimeDistributionByMembersAPIView,TaskCompletionSimpleAPIView

)

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
    path('tasks/counts/', TaskCountsAPIView.as_view(), name='task-counts'),
    path('tasks/daily-timeline/', DailyTimelineAPIView.as_view(), name='daily-timeline'),
    path('tasks/status-overview/', TaskStatusOverviewAPIView.as_view(), name='task-status-overview'),
    path('work-hours/', WorkHoursOverviewAPIView.as_view(), name='work-hours'),
    path('tasks/time-distribution/',TimeDistributionAPIView.as_view(), name='time-distribution-user'),
    path('tasks/recent-tasks/',RecentTasksAPIView.as_view(), name='recent-tasks-user'),
    path("tasks/top-tasks/", TopUsedTasksAPIView.as_view(), name="top-tasks-user"),
    path('top-members/', TopMembersAPIView.as_view(), name='top-members'),
    path('tasks/approvals/', TaskApprovalAPIView.as_view(), name='task-approvals-approver'),
    path('tasks/approval-status-overview/', ApprovalStatusOverviewAPIView.as_view(), name='approval-status-overview'),
    path('tasks/member/time-distribution/', TimeDistributionByMembersAPIView.as_view(), name='time-distribution'),
    path('tasks/today/completed/', TaskCompletionSimpleAPIView.as_view(), name='today-completed-tasks'),
    path("tasks/top-platforms/", TopPlatformsAPIView.as_view(), name="top-platforms"),
    path("tasks/platform-performance/", PlatformPerformanceAPIView.as_view(), name="platform-performance"),
    path("profile/", ProfileAPIView.as_view(), name="profile"),
    path("approval-table/", ApprovalTableAPIView.as_view(), name="approval-table"),
    # path("approval-table/throw/", ApprovalTablethrowAPIView.as_view(), name="approval-table"),
    path("recent-apprpoval-request/",RecentRequestAPIView.as_view(),name="recent-approval"),
    

    
]