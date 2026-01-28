from django.urls import path
from .views import UserListCreateAPIView, UserDetailAPIView
from .views import  LoginView,ForgotPasswordView,ChangePasswordView,LogoutView,UserRoleMappingAPIView
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView
urlpatterns = [
    path('users/',          UserListCreateAPIView.as_view(),   name='user-list-create'),
    path('users/<int:pk>/', UserDetailAPIView.as_view(),       name='user-detail'),
    path('user-role-mappings/', UserRoleMappingAPIView.as_view(), name='user-role-mappings'),
    # Retrieve, update, delete
    path('user-role-mappings/<int:pk>/', UserRoleMappingAPIView.as_view(), name='user-role-mapping-detail'),   
      path("login/", LoginView.as_view(), name="login"),
    path("logout/",LogoutView.as_view(), name="logout"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
]