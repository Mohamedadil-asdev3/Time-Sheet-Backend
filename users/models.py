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



# class User(AbstractBaseUser):
#     name = models.CharField(max_length=255, unique=True, null=True, blank=True)
#     employee_id = models.CharField(max_length=50, unique=True)
#     email = models.EmailField(max_length=255, unique=True, null=True, blank=True) 
#     password = models.CharField(max_length=255, null=True, blank=True)
#     password_last_update = models.DateTimeField(null=True, blank=True)
#     phone = models.CharField(max_length=255, null=True, blank=True)
#     realname = models.CharField(max_length=255, null=True, blank=True)
#     firstname = models.CharField(max_length=255, null=True, blank=True)
#     entities_ids = models.JSONField(default=list, blank=True)
#     entity = models.ForeignKey(masterModels.Entity, on_delete=models.SET_NULL, null=True)
#     location = models.ForeignKey(masterModels.Location, on_delete=models.SET_NULL, null=True)
#     department = models.ForeignKey(masterModels.Department, on_delete=models.SET_NULL, null=True)
#     password_forget_token = models.CharField(max_length=40, null=True, blank=True)
#     password_forget_token_date = models.DateTimeField(null=True, blank=True)
#     force_password_change = models.BooleanField(default=False)
#     is_active = models.BooleanField(default=True)
#     is_deleted = models.BooleanField(default=False)
#     is_manager = models.BooleanField(default=False)
#     is_hod = models.BooleanField(default=False)
#     is_ldap_user = models.BooleanField(default=False, help_text="Flag indicating if user is authenticated via LDAP")
#     is_staff = models.BooleanField(default=False)
#     is_superuser = models.BooleanField(default=False)
#     created_by = models.IntegerField()
#     modified_by = models.IntegerField()
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)


#     objects = UserManager()

#     USERNAME_FIELD = "name"
#     REQUIRED_FIELDS = []

#     class Meta:
#         db_table = "users"
class User(AbstractBaseUser):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True, null=True, blank=True)
    email = models.EmailField(max_length=255, unique=True, null=True, blank=True) 
    password = models.CharField(max_length=255, null=True, blank=True)
    password_last_update = models.DateTimeField(null=True, blank=True)
    phone = models.CharField(max_length=255, null=True, blank=True)
    phone2 = models.CharField(max_length=255, null=True, blank=True)
    mobile = models.CharField(max_length=255, null=True, blank=True)
    realname = models.CharField(max_length=255, null=True, blank=True)
    firstname = models.CharField(max_length=255, null=True, blank=True)
    entities_ids = models.JSONField(default=list, blank=True)  # Array of entity IDs
    location = models.ForeignKey(masterModels.Location, on_delete=models.SET_NULL, null=True)
    roles_ids = models.JSONField(default=list, blank=True)  # Array of role IDs (from TicketsMasterConfiguration)
    force_password_change = models.BooleanField(default=False)
    department = models.ForeignKey(masterModels.Department, on_delete=models.SET_NULL, null=True)
    language = models.CharField(max_length=10, null=True, blank=True)
    use_mode = models.IntegerField(default=0)
    list_limit = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    comment = models.TextField(null=True, blank=True)
    auths_id = models.IntegerField(default=0)
    authtype = models.IntegerField(default=0)
    last_login = models.DateTimeField(null=True, blank=True)
    date_mod = models.DateTimeField(null=True, blank=True)
    date_sync = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    profiles_id = models.IntegerField(default=0)
    usertitles_id = models.IntegerField(default=0)
    usercategories_id = models.IntegerField(default=0)
    date_format = models.IntegerField(null=True, blank=True)
    number_format = models.IntegerField(null=True, blank=True)
    names_format = models.IntegerField(null=True, blank=True)
    csv_delimiter = models.CharField(max_length=1, null=True, blank=True)
    is_ids_visible = models.BooleanField(null=True, blank=True)
    use_flat_dropdowntree = models.BooleanField(null=True, blank=True)
    show_jobs_at_login = models.BooleanField(null=True, blank=True)
    priority_1 = models.CharField(max_length=20, null=True, blank=True)
    priority_2 = models.CharField(max_length=20, null=True, blank=True)
    priority_3 = models.CharField(max_length=20, null=True, blank=True)
    priority_4 = models.CharField(max_length=20, null=True, blank=True)
    priority_5 = models.CharField(max_length=20, null=True, blank=True)
    priority_6 = models.CharField(max_length=20, null=True, blank=True)
    followup_private = models.BooleanField(null=True, blank=True)
    task_private = models.BooleanField(null=True, blank=True)
    default_requesttypes_id = models.IntegerField(null=True, blank=True)
    password_forget_token = models.CharField(max_length=40, null=True, blank=True)
    password_forget_token_date = models.DateTimeField(null=True, blank=True)
    user_dn = models.TextField(null=True, blank=True)
    registration_number = models.CharField(max_length=255, null=True, blank=True)
    show_count_on_tabs = models.BooleanField(null=True, blank=True)
    refresh_views = models.IntegerField(null=True, blank=True)
    set_default_tech = models.BooleanField(null=True, blank=True)
    personal_token = models.CharField(max_length=255, null=True, blank=True)
    personal_token_date = models.DateTimeField(null=True, blank=True)
    api_token = models.CharField(max_length=255, null=True, blank=True)
    api_token_date = models.DateTimeField(null=True, blank=True)
    cookie_token = models.CharField(max_length=255, null=True, blank=True)
    cookie_token_date = models.DateTimeField(null=True, blank=True)
    display_count_on_home = models.IntegerField(null=True, blank=True)
    notification_to_myself = models.BooleanField(null=True, blank=True)
    duedateok_color = models.CharField(max_length=255, null=True, blank=True)
    duedatewarning_color = models.CharField(max_length=255, null=True, blank=True)
    duedatecritical_color = models.CharField(max_length=255, null=True, blank=True)
    duedatewarning_less = models.IntegerField(null=True, blank=True)
    duedatecritical_less = models.IntegerField(null=True, blank=True)
    duedatewarning_unit = models.CharField(max_length=255, null=True, blank=True)
    duedatecritical_unit = models.CharField(max_length=255, null=True, blank=True)
    display_options = models.TextField(null=True, blank=True)
    is_deleted_ldap = models.BooleanField(default=False)
    pdffont = models.CharField(max_length=255, null=True, blank=True)
    picture = models.CharField(max_length=255, null=True, blank=True)
    begin_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    keep_devices_when_purging_item = models.BooleanField(null=True, blank=True)
    privatebookmarkorder = models.TextField(null=True, blank=True)
    backcreated = models.BooleanField(null=True, blank=True)
    task_state = models.IntegerField(null=True, blank=True)
    layout = models.CharField(max_length=20, null=True, blank=True)
    palette = models.CharField(max_length=20, null=True, blank=True)
    set_default_requester = models.BooleanField(null=True, blank=True)
    lock_autolock_mode = models.BooleanField(null=True, blank=True)
    lock_directunlock_notification = models.BooleanField(null=True, blank=True)
    date_creation = models.DateTimeField(null=True, blank=True)
    highcontrast_css = models.BooleanField(default=False)
    plannings = models.TextField(null=True, blank=True)
    sync_field = models.CharField(max_length=255, null=True, blank=True)
    groups_id = models.IntegerField(default=0)
    users_id_supervisor = models.IntegerField(default=0)
    timezone = models.CharField(max_length=50, null=True, blank=True)
    default_dashboard_central = models.CharField(max_length=100, null=True, blank=True)
    default_dashboard_assets = models.CharField(max_length=100, null=True, blank=True)
    default_dashboard_helpdesk = models.CharField(max_length=100, null=True, blank=True)
    default_dashboard_mini_ticket = models.CharField(max_length=100, null=True, blank=True)
    player_id = models.TextField()  # required
    is_hod = models.BooleanField(default=False)
    is_ldap_user = models.BooleanField(default=False, help_text="Flag indicating if user is authenticated via LDAP")
#     reporting_manager = models.ForeignKey(
#     "self",
#     on_delete=models.SET_NULL,
#     null=True,
#     blank=True,
#     related_name="team_members"
# )
    # first_level_manager = models.ForeignKey(
    #     "self",
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name="first_level_team"
    # )

    # second_level_manager = models.ForeignKey(
    #     "self",
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name="second_level_team"
    # )

    # third_level_manager = models.ForeignKey(
    #     "self",
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name="third_level_team"
    # )

    # first_level_manager_designation = models.CharField(max_length=255, null=True, blank=True)
    # second_level_manager_designation = models.CharField(max_length=255, null=True, blank=True)
    # third_level_manager_designation = models.CharField(max_length=255, null=True, blank=True)
    first_level_manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        db_index=True
    )

    second_level_manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        db_index=True
    )

    third_level_manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        db_index=True
    )

    first_level_manager_designation = models.CharField(max_length=255, null=True, blank=True)
    second_level_manager_designation = models.CharField(max_length=255, null=True, blank=True)
    third_level_manager_designation = models.CharField(max_length=255, null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    no_entity_mail_sent = models.BooleanField(default=False)
    created_by = models.IntegerField(null=True, blank=True)
    modified_by = models.IntegerField(null=True, blank=True)
    is_manager = models.BooleanField(default=False)
    employee_id = models.CharField(max_length=50, null=True, blank=True)
    objects = UserManager()

    USERNAME_FIELD = "name"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
        managed = True  # ✅ tells Django not to create/alter this table

   
    # ✅ Prevent Django admin errors
    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

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

