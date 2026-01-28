from django.urls import path
from .views import (
    EntityAPIView,
    DepartmentAPIView,
    LocationAPIView,
    TaskAPIView,
    SubTaskAPIView,
    RoleAPIView,
    PlatformAPIView,
    StatusAPIView
)

urlpatterns = [
   
    path('entity/', EntityAPIView.as_view()),          # GET(list), POST
    path('entity/<int:pk>/', EntityAPIView.as_view()),
    path('department/', DepartmentAPIView.as_view() ),
    path('department/<int:pk>', DepartmentAPIView.as_view()),
    path('location/', LocationAPIView.as_view()),
    path('location/<int:pk>', LocationAPIView.as_view()),
    path('task/', TaskAPIView.as_view()),
    path('task/<int:pk>/', TaskAPIView.as_view()),
    path('subtask/', SubTaskAPIView.as_view()),
    path('subtask/<int:pk>/', SubTaskAPIView.as_view()),
    path('role/', RoleAPIView.as_view()),
    path('role/<int:pk>/', RoleAPIView.as_view()),
    path('platform/',PlatformAPIView.as_view() ),
    path('platform/<int:pk>/',PlatformAPIView.as_view() ),
     path('status/',StatusAPIView.as_view() ),
    path('status/<int:pk>/',StatusAPIView.as_view() )

   
]
