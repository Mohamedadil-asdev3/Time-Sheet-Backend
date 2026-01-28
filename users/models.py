from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager 
from master import models as masterModels
from django.contrib.auth import get_user_model
from django.conf import settings  
from master.models import Entity
from django.utils import timezone
from datetime import datetime

# Create your models here.
class UserManager(BaseUserManager):
    def create_user(self, name, password=None, **extra_fields):
        if not name:
            raise ValueError("The Name field must be set")
        user = self.model(name=name, **extra_fields)
        if password:
            user.set_password(password)  # hashes password
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, name, password=None, **extra_fields):
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(name, password, **extra_fields)



class User(AbstractBaseUser):
    name = models.CharField(max_length=255, unique=True, null=True, blank=True)
    employee_id = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=255, unique=True, null=True, blank=True) 
    password = models.CharField(max_length=255, null=True, blank=True)
    password_last_update = models.DateTimeField(null=True, blank=True)
    phone = models.CharField(max_length=255, null=True, blank=True)
    realname = models.CharField(max_length=255, null=True, blank=True)
    firstname = models.CharField(max_length=255, null=True, blank=True)
    entities_ids = models.JSONField(default=list, blank=True)
    entity = models.ForeignKey(masterModels.Entity, on_delete=models.SET_NULL, null=True)
    location = models.ForeignKey(masterModels.Location, on_delete=models.SET_NULL, null=True)
    department = models.ForeignKey(masterModels.Department, on_delete=models.SET_NULL, null=True)
    password_forget_token = models.CharField(max_length=40, null=True, blank=True)
    password_forget_token_date = models.DateTimeField(null=True, blank=True)
    force_password_change = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    is_manager = models.BooleanField(default=False)
    is_hod = models.BooleanField(default=False)
    is_ldap_user = models.BooleanField(default=False, help_text="Flag indicating if user is authenticated via LDAP")
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_by = models.IntegerField()
    modified_by = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    objects = UserManager()

    USERNAME_FIELD = "name"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"

# class UsersGroup(models.Model):
#     id = models.AutoField(primary_key=True)
#     entities_id = models.IntegerField(default=0)
#     is_recursive = models.BooleanField(default=False)
#     name = models.CharField(max_length=255, null=True, blank=True)
#     comment = models.TextField(null=True, blank=True)
#     ldap_field = models.CharField(max_length=255, null=True, blank=True)
#     ldap_value = models.TextField(null=True, blank=True)
#     ldap_group_dn = models.TextField(null=True, blank=True)
#     date_mod = models.DateTimeField(null=True, blank=True)
#     groups_id = models.IntegerField(default=0)
#     completename = models.TextField(null=True, blank=True)
#     level = models.IntegerField(default=0)
#     ancestors_cache = models.TextField(null=True, blank=True)
#     sons_cache = models.TextField(null=True, blank=True)
#     is_requester = models.BooleanField(default=True)
#     is_watcher = models.BooleanField(default=True)
#     is_assign = models.BooleanField(default=True)
#     is_task = models.BooleanField(default=True)
#     is_notify = models.BooleanField(default=True)
#     is_itemgroup = models.BooleanField(default=True)
#     is_usergroup = models.BooleanField(default=True)
#     is_manager = models.BooleanField(default=True)
#     date_creation = models.DateTimeField(null=True, blank=True)
#     # created_date = models.DateTimeField(auto_now_add=True)
#     # updated_date = models.DateTimeField(auto_now=True)
#     # created_by = models.CharField(max_length=255, null=True, blank=True)
#     # updated_by = models.CharField(max_length=255, null=True, blank=True)

#     class Meta:
#         db_table = "users_groups"
#         managed = True
#         verbose_name = "Group"
#         verbose_name_plural = "Groups"

#     def get_users(self):
#         User = settings.AUTH_USER_MODEL
#         from django.apps import apps
#         UserModel = apps.get_model(*User.split('.'))
#         return UserModel.objects.filter(groups_id=self.id, is_active=True, is_deleted=False)

#     def __str__(self):
#         return self.name



# class UserLoginHistory(models.Model):
#     user = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name='login_history'
#     )
#     login_time = models.DateTimeField(default=timezone.now)
#     logout_time = models.DateTimeField(null=True, blank=True)
#     ip_address = models.GenericIPAddressField(null=True, blank=True)
    

#     class Meta:
#         db_table = 'user_login_history'

#     def __str__(self):
#         return f"{self.user.name} - {self.login_time}"

#     def duration_minutes(self):
#         if self.logout_time and self.login_time:
#             return int((self.logout_time - self.login_time).total_seconds() // 60)
#         return None



class UserRoleMapping(models.Model) :
    # userId = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    # roleId = models.ForeignKey(masterModels.Role, on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(masterModels.Role, on_delete=models.CASCADE)
    created_by = models.IntegerField()
    modified_by = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "user_role_mapping"

