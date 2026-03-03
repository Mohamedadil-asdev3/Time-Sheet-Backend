from django.shortcuts import render

# Create your views here.
# accounts/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from .models import User,UserRoleMapping
from .serializers import UserSerializer,UserRoleMappingSerializer
from django.utils import timezone


class UserListCreateAPIView(APIView):
    """
    List all users (non-deleted) or create a new user
    """
    permission_classes = [permissions.IsAdminUser]  # ← change to your needs

    def get(self, request):
        users = User.objects.filter(is_deleted=False).order_by('-created_at')
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            # You can set created_by here if you want
            # serializer.validated_data['created_by'] = request.user.id
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserDetailAPIView(APIView):
    """
    Retrieve, update or soft-delete a user
    """
    permission_classes = [permissions.IsAdminUser]  # ← change to your needs

    def get_object(self, pk):
        user = get_object_or_404(User, pk=pk)
        if user.is_deleted:
            raise PermissionDenied("This user has been deleted.")
        return user

    def get(self, request, pk):
        user = self.get_object(pk)
        serializer = UserSerializer(user)
        return Response(serializer.data)

    def put(self, request, pk):
        user = self.get_object(pk)
        serializer = UserSerializer(user, data=request.data)
        if serializer.is_valid():
            # You can set modified_by here
            # serializer.validated_data['modified_by'] = request.user.id
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        user = self.get_object(pk)
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        user = self.get_object(pk)
        user.is_deleted = True
        user.is_active = False
        user.save(update_fields=['is_deleted', 'is_active'])
        return Response({"detail": "User soft-deleted"}, status=status.HTTP_200_OK)
    

class UserRoleMappingAPIView(APIView):
    """
    Single APIView for UserRoleMapping
    - GET /user-role-mappings/          → list all
    - POST /user-role-mappings/         → create new
    - GET /user-role-mappings/<pk>/     → retrieve single
    - PUT / PATCH / DELETE /user-role-mappings/<pk>/ → update or delete
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, pk=None):
        if pk:
            # Retrieve single
            mapping = get_object_or_404(UserRoleMapping, pk=pk)
            serializer = UserRoleMappingSerializer(mapping)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            # List all
            mappings = UserRoleMapping.objects.select_related('user', 'role').all().order_by('id')
            serializer = UserRoleMappingSerializer(mappings, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = UserRoleMappingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        if not pk:
            return Response({"error": "ID is required for update"}, status=status.HTTP_400_BAD_REQUEST)
        mapping = get_object_or_404(UserRoleMapping, pk=pk)
        serializer = UserRoleMappingSerializer(mapping, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk=None):
        if not pk:
            return Response({"error": "ID is required for patch"}, status=status.HTTP_400_BAD_REQUEST)
        mapping = get_object_or_404(UserRoleMapping, pk=pk)
        serializer = UserRoleMappingSerializer(mapping, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        if not pk:
            return Response({"error": "ID is required for delete"}, status=status.HTTP_400_BAD_REQUEST)
        mapping = get_object_or_404(UserRoleMapping, pk=pk)
        mapping.delete()
        return Response({"detail": "Mapping deleted"}, status=status.HTTP_204_NO_CONTENT)
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
import ldap
import binascii
from django.core.mail import send_mail
import random
import string
from django.utils import timezone
from .models import User,UserRoleMapping
from master.models import Entity,Role
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import UntypedToken

User = get_user_model()

# Assuming your User model has a 'force_password_change' field. Add this to your model if not:
# force_password_change = models.BooleanField(default=False)

# Helper: Generate random password
def generate_random_password(length=8):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

# Helper: Ensure domain for AD login
def ensure_domain_in_username(username):
    domain = "@qatarmedicalcenter.com"
    if domain not in username:
        username += domain
    return username

# Helper: Decode LDAP data
def decode_ldap_data(data):
    decoded_data = {}
    for key, value in data.items():
        if isinstance(value, list):
            new_values = []
            for v in value:
                if isinstance(v, bytes):
                    try:
                        new_values.append(v.decode("utf-8"))
                    except UnicodeDecodeError:
                        new_values.append(binascii.hexlify(v).decode("utf-8"))
                else:
                    new_values.append(v)
            decoded_data[key] = new_values
        elif isinstance(value, bytes):
            try:
                decoded_data[key] = value.decode("utf-8")
            except UnicodeDecodeError:
                decoded_data[key] = binascii.hexlify(value).decode("utf-8")
        else:
            decoded_data[key] = value
    return decoded_data

# ---------------- LOGIN ----------------
import logging

logger = logging.getLogger(__name__)

def safe_fk_id(obj):
    return obj.id if obj else None

# class LoginView(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request):
#         username = request.data.get("username")
#         password = request.data.get("password")
#         ip_address = request.META.get("REMOTE_ADDR")

#         if not username or not password:
#             return Response({"error": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST)

#         username_ad = ensure_domain_in_username(username)

#         # --- LDAP Authentication ---
#         try:
#             if getattr(settings, "LDAP_AUTH", True):
#                 ldap_server = "ldap://172.31.46.129:389"
#                 base_dn = "dc=qatarmedicalcenter,dc=com"
#                 ldap_client = ldap.initialize(ldap_server)
#                 ldap_client.set_option(ldap.OPT_REFERRALS, 0)
#                 ldap_client.simple_bind_s(username_ad, password)

#                 search_filter = f"(&(objectClass=user)(userPrincipalName={username_ad}))"
#                 attrs = ["displayName", "mail", "userPrincipalName", "employeeID"]
#                 result = ldap_client.search_s(base_dn, ldap.SCOPE_SUBTREE, search_filter, attrs)
#                 user_info = result[0][1] if result else {}
#                 user_info = decode_ldap_data(user_info)

#                 display_name = user_info.get("displayName", [username.split("@")[0]])[0]
#                 email = user_info.get("mail", [username_ad])[0]

#                 # Handle employee_id
#                 employee_id = user_info.get("employeeID")
#                 if employee_id:
#                     employee_id = employee_id[0] if isinstance(employee_id, list) else employee_id
#                 else:
#                     # Generate a unique employee_id for LDAP users
#                     employee_id = f"LDAP_{username}_{int(timezone.now().timestamp())}"

#                 ldap_client.unbind_s()

#                 # Create or get user
#                 user, created = User.objects.get_or_create(
#                     name=username_ad,
#                     defaults={
#                         "email": email,
#                         "firstname": display_name,
#                         "password": make_password(password),
#                         "force_password_change": False,
#                         "created_by": request.user.id if request.user.is_authenticated else 1,
#                         "modified_by": request.user.id if request.user.is_authenticated else 1,
#                         "employee_id": employee_id,
#                     },
#                 )
#                 if created:
#                     user.email = email
#                     user.firstname = display_name
#                     user.save(update_fields=["email", "firstname"])

#                 # Fetch entities
#                 entities = []
#                 entity_data = None
#                 if hasattr(user, "entities_ids") and user.entities_ids:
#                     for eid in user.entities_ids:
#                         try:
#                             ent = Entity.objects.get(id=eid)
#                             entities.append({
#                                 "id": ent.id,
#                                 "name": ent.name,
#                                 "display_name": getattr(ent, "display_name", ent.name),
#                                 "logo": ent.logo.url if ent.logo else None,
#                             })
#                         except Entity.DoesNotExist:
#                             continue
#                     entity_data = entities[0] if entities else None

#                 # Fetch roles
#                 roles = []
#                 if hasattr(user, "roles_ids") and user.roles_ids:
#                     for rid in user.roles_ids:
#                         try:
#                             rol = Role.objects.get(id=rid)
#                             roles.append({"id": rol.id, "name": rol.name})
#                         except Role.DoesNotExist:
#                             continue
#                 else:
#                     roles = [{"id": None, "name": "user"}]

#                 # UserRoleMapping
#                 mappings = UserRoleMapping.objects.filter(user=user).select_related("role", "user")
#                 role_mappings = [
#                     {
#                         "id": m.id,
#                         "role_id": m.role.id,
#                         "role_name": m.role.name,
#                         "user_id": m.user.id,
#                         "created_at": m.created_at,
#                         "updated_at": m.updated_at,
#                     }
#                     for m in mappings
#                 ]

#                 refresh = RefreshToken.for_user(user)
#                 response_data = {
#                     "message": "Login successful (AD Authenticated)",
#                     "user": {
#                         "id": user.id,
#                         "name": user.name,
#                         "email": user.email,
#                         "firstname": user.firstname or display_name,
#                         "entities": entities,
#                         "roles": roles,
#                         "entities_ids": getattr(user, "entities_ids", []) or [],
#                         "roles_ids": getattr(user, "roles_ids", []) or [],
#                         "entity_data": entity_data,
#                         "department_id": safe_fk_id(getattr(user, "department_id", None)),
#                         "location_id": safe_fk_id(getattr(user, "locations", None)),
#                         "role_mappings": role_mappings,
#                         "employee_id": user.employee_id,
#                     },
#                     "refresh": str(refresh),
#                     "access": str(refresh.access_token),
#                     "force_change": user.force_password_change,
#                 }
#                 return Response(response_data, status=status.HTTP_200_OK)

#         except ldap.INVALID_CREDENTIALS:
#             pass
#         except ldap.SERVER_DOWN:
#             pass
#         except Exception as e:
#             logger.error(f"LDAP error: {e}")

#         # --- Local DB Authentication ---
#         try:
#             user = User.objects.get(email=username) if "@" in username else User.objects.get(name=username)
#         except User.DoesNotExist:
#             return Response({"error": "Invalid username or password"}, status=status.HTTP_400_BAD_REQUEST)

#         valid_password = check_password(password, user.password) if user.password.startswith("pbkdf2_sha256$") else user.password == password

#         if valid_password:
#             if not user.password.startswith("pbkdf2_sha256$"):
#                 user.password = make_password(password)
#                 user.save(update_fields=["password"])

#             # Entities
#             entities = []
#             entity_data = None
#             if hasattr(user, "entities_ids") and user.entities_ids:
#                 for eid in user.entities_ids:
#                     try:
#                         ent = Entity.objects.get(id=eid)
#                         entities.append({
#                             "id": ent.id,
#                             "name": ent.name,
#                             "display_name": getattr(ent, "display_name", ent.name),
#                         })
#                     except Entity.DoesNotExist:
#                         continue
#                 entity_data = entities[0] if entities else None

#             # Roles
#             roles = []
#             if hasattr(user, "roles_ids") and user.roles_ids:
#                 for rid in user.roles_ids:
#                     try:
#                         rol = Role.objects.get(id=rid)
#                         roles.append({"id": rol.id, "name": rol.name})
#                     except Role.DoesNotExist:
#                         continue
#             else:
#                 roles = [{"id": None, "name": "user"}]

#             # UserRoleMapping
#             mappings = UserRoleMapping.objects.filter(user=user).select_related("role", "user")
#             role_mappings = [
#                 {
#                     "id": m.id,
#                     "role_id": m.role.id,
#                     "role_name": m.role.field_name,
#                     "user_id": m.user.id,
#                     "created_at": m.created_at,
#                     "updated_at": m.updated_at,
#                 }
#                 for m in mappings
#             ]

#             refresh = RefreshToken.for_user(user)
#             response_data = {
#                 "message": "Login successful (Local DB Authenticated)",
#                 "user": {
#                     "id": user.id,
#                     "name": user.name,
#                     "email": user.email,
#                     "firstname": user.firstname or "",
#                     "entities": entities,
#                     "roles": roles,
#                     "entities_ids": getattr(user, "entities_ids", []) or [],
#                     "roles_ids": getattr(user, "roles_ids", []) or [],
#                     "entity_data": entity_data,
#                     "department_id": safe_fk_id(getattr(user, "department_id", None)),
#                     "location_id": safe_fk_id(getattr(user, "locations", None)),
#                     "role_mappings": role_mappings,
#                     "employee_id": user.employee_id,
#                 },
#                 "refresh": str(refresh),
#                 "access": str(refresh.access_token),
#                 "force_change": user.force_password_change,
#             }
#             return Response(response_data, status=status.HTTP_200_OK)

#         return Response({"error": "Invalid username or password"}, status=status.HTTP_400_BAD_REQUEST)


def ensure_domain_in_username(username):
    if "@" not in username:
        return f"{username}@qatarmedicalcenter.com"
    return username

def decode_ldap_data(data):
    decoded = {}
    for key, values in data.items():
        decoded[key] = [v.decode('utf-8') if isinstance(v, bytes) else v for v in values]
    return decoded

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({"error": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST)

        username_ad = ensure_domain_in_username(username)

        ldap_authenticated = False
        ad_raw = {}

        # LDAP Authentication + Fetch Rich Profile
        if getattr(settings, "LDAP_AUTH", True):
            try:
                ldap_server = "ldap://172.31.46.129:389"
                base_dn = "dc=qatarmedicalcenter,dc=com"

                ldap_client = ldap.initialize(ldap_server)
                ldap_client.set_option(ldap.OPT_REFERRALS, 0)
                ldap_client.simple_bind_s(username_ad, password)

                search_filter = f"(&(objectClass=user)(userPrincipalName={username_ad}))"
                attrs = [
                    "displayName", "givenName", "sn", "mail", "userPrincipalName",
                    "employeeID", "department", "title", "telephoneNumber", "mobile",
                    "company", "manager", "memberOf", "distinguishedName", "description",
                    "whenCreated", "lastLogon", "accountExpires", "userAccountControl"
                ]
                result = ldap_client.search_s(base_dn, ldap.SCOPE_SUBTREE, search_filter, attrs)

                if result:
                    ldap_authenticated = True
                    _, user_info_raw = result[0]
                    ad_raw = decode_ldap_data(user_info_raw)
                    print(f"AD Data for {username_ad}: {ad_raw}")  # your debug print

                    display_name = ad_raw.get("displayName", [username.split("@")[0]])[0]
                    email = ad_raw.get("mail", [username_ad])[0]
                    first_name = ad_raw.get("givenName", [""])[0]
                    last_name = ad_raw.get("sn", [""])[0]
                    department_name = ad_raw.get("department", [""])[0]
                    job_title = ad_raw.get("title", [""])[0]
                    phone = ad_raw.get("telephoneNumber", [""])[0] or ad_raw.get("mobile", [""])[0] or ""

                    # Employer number (employeeID)
                    employee_id_raw = ad_raw.get("employeeID")
                    employee_id = employee_id_raw[0] if employee_id_raw else f"LDAP_{username}_{int(timezone.now().timestamp())}"

                    member_of = ad_raw.get("memberOf", [])
                    ad_groups_json = json.dumps(member_of) if member_of else ""

                ldap_client.unbind_s()

            except ldap.INVALID_CREDENTIALS:
                pass
            except ldap.SERVER_DOWN:
                logger.error("LDAP server unreachable")
            except Exception as e:
                logger.error(f"LDAP error: {str(e)}")

        # Find or Create/Update Local User
        try:
            user = None

            if ldap_authenticated and email:
                user = User.objects.filter(email=email).first()

            if not user:
                user = User.objects.filter(name=username_ad).first()

            if user:
                if ldap_authenticated:
                    user.email = email
                    user.firstname = first_name or display_name.split()[0] if display_name else user.firstname
                    user.realname = display_name or getattr(user, 'realname', '')
                    user.phone = phone or getattr(user, 'phone', '')
                    user.mobile = phone or getattr(user, 'mobile', '')
                    user.department = department_name or getattr(user, 'department', None)
                    user.is_ldap_user = True
                    user.employee_id = employee_id  # Employer number saved
                    user.force_password_change = False
                    if password:
                        user.password = make_password(password)
                    user.date_mod = timezone.now()
                    user.date_sync = timezone.now()
                    user.save()
            else:
                user = User.objects.create(
                    name=username_ad,
                    email=email if ldap_authenticated else username,
                    firstname=first_name if ldap_authenticated else "",
                    realname=display_name if ldap_authenticated else "",
                    phone=phone if ldap_authenticated else "",
                    mobile=phone if ldap_authenticated else "",
                    department=department_name if ldap_authenticated else None,
                    employee_id=employee_id,
                    password=make_password(password),
                    is_ldap_user=ldap_authenticated,
                    force_password_change=False,
                    date_creation=timezone.now(),
                    date_mod=timezone.now(),
                    date_sync=timezone.now(),
                )

            # ────────────────────────────────────────────────
            # Build SAFE response – show ALL data
            # ────────────────────────────────────────────────
            entities = []
            entity_data = None
            if getattr(user, 'entities_ids', []):
                for eid in user.entities_ids:
                    try:
                        ent = Entity.objects.get(id=eid)
                        entities.append({
                            "id": ent.id,
                            "name": ent.name,
                            "display_name": getattr(ent, "display_name", ent.name),
                            "logo": getattr(ent, 'logo', None).url if hasattr(ent, 'logo') and ent.logo else None,
                        })
                    except Entity.DoesNotExist:
                        continue
                entity_data = entities[0] if entities else None

            roles = []
            if getattr(user, 'roles_ids', []):
                for rid in user.roles_ids:
                    try:
                        rol = Role.objects.get(id=rid)
                        roles.append({"id": rol.id, "name": rol.name})
                    except Role.DoesNotExist:
                        continue
            else:
                roles = [{"id": None, "name": "user"}]

            mappings = UserRoleMapping.objects.filter(user=user).select_related("role")
            role_mappings = [
                {
                    "id": m.id,
                    "role_id": m.role.id,
                    "role_name": m.role.name,
                    "user_id": m.user.id,
                    "created_at": m.created_at,
                    "updated_at": m.updated_at,
                }
                for m in mappings
            ]

            refresh = RefreshToken.for_user(user)

            # Build full, safe user_data
            user_data = {
                "id": user.id,
                "name": user.name,
                "employee_id": getattr(user, 'employee_id', None),           # Employer number from AD
                "email": user.email,
                "firstname": getattr(user, 'firstname', ""),
                "realname": getattr(user, 'realname', ""),
                "phone": getattr(user, 'phone', ""),                         # Phone from AD
                "phone2": getattr(user, 'phone2', ""),
                "mobile": getattr(user, 'mobile', ""),                       # Mobile from AD
                "department": getattr(user, 'department', {}).name if getattr(user, 'department', None) else "",
                "location": getattr(user, 'location', {}).name if getattr(user, 'location', None) else "",
                "entities_ids": getattr(user, 'entities_ids', []),
                "roles_ids": getattr(user, 'roles_ids', []),
                "entities": entities,
                "roles": roles,
                "role_mappings": role_mappings,
                "force_password_change": getattr(user, 'force_password_change', False),
                "is_active": getattr(user, 'is_active', True),
                "is_deleted": getattr(user, 'is_deleted', False),
                "is_ldap_user": getattr(user, 'is_ldap_user', False),
                "is_staff": getattr(user, 'is_staff', False),
                "is_superuser": getattr(user, 'is_superuser', False),

                # Safe defaults for all other fields in your model
                "language": getattr(user, 'language', ""),
                "use_mode": getattr(user, 'use_mode', 0),
                "list_limit": getattr(user, 'list_limit', None),
                "comment": getattr(user, 'comment', ""),
                "auths_id": getattr(user, 'auths_id', 0),
                "authtype": getattr(user, 'authtype', 0),
                "last_login": getattr(user, 'last_login', None),
                "date_mod": getattr(user, 'date_mod', None),
                "date_sync": getattr(user, 'date_sync', None),
                "profiles_id": getattr(user, 'profiles_id', 0),
                "usertitles_id": getattr(user, 'usertitles_id', 0),
                "usercategories_id": getattr(user, 'usercategories_id', 0),
                "date_format": getattr(user, 'date_format', None),
                "number_format": getattr(user, 'number_format', None),
                "names_format": getattr(user, 'names_format', None),
                "csv_delimiter": getattr(user, 'csv_delimiter', ""),
                "is_ids_visible": getattr(user, 'is_ids_visible', None),
                "use_flat_dropdowntree": getattr(user, 'use_flat_dropdowntree', None),
                "show_jobs_at_login": getattr(user, 'show_jobs_at_login', None),
                "priority_1": getattr(user, 'priority_1', ""),
                "priority_2": getattr(user, 'priority_2', ""),
                "priority_3": getattr(user, 'priority_3', ""),
                "priority_4": getattr(user, 'priority_4', ""),
                "priority_5": getattr(user, 'priority_5', ""),
                "priority_6": getattr(user, 'priority_6', ""),
                "followup_private": getattr(user, 'followup_private', None),
                "task_private": getattr(user, 'task_private', None),
                "default_requesttypes_id": getattr(user, 'default_requesttypes_id', None),
                "password_forget_token": getattr(user, 'password_forget_token', ""),
                "password_forget_token_date": getattr(user, 'password_forget_token_date', None),
                "user_dn": getattr(user, 'user_dn', ""),
                "registration_number": getattr(user, 'registration_number', ""),
                "show_count_on_tabs": getattr(user, 'show_count_on_tabs', None),
                "refresh_views": getattr(user, 'refresh_views', None),
                "set_default_tech": getattr(user, 'set_default_tech', None),
                "personal_token": getattr(user, 'personal_token', ""),
                "personal_token_date": getattr(user, 'personal_token_date', None),
                "api_token": getattr(user, 'api_token', ""),
                "api_token_date": getattr(user, 'api_token_date', None),
                "cookie_token": getattr(user, 'cookie_token', ""),
                "cookie_token_date": getattr(user, 'cookie_token_date', None),
                "display_count_on_home": getattr(user, 'display_count_on_home', None),
                "notification_to_myself": getattr(user, 'notification_to_myself', None),
                "duedateok_color": getattr(user, 'duedateok_color', ""),
                "duedatewarning_color": getattr(user, 'duedatewarning_color', ""),
                "duedatecritical_color": getattr(user, 'duedatecritical_color', ""),
                "duedatewarning_less": getattr(user, 'duedatewarning_less', None),
                "duedatecritical_less": getattr(user, 'duedatecritical_less', None),
                "duedatewarning_unit": getattr(user, 'duedatewarning_unit', ""),
                "duedatecritical_unit": getattr(user, 'duedatecritical_unit', ""),
                "display_options": getattr(user, 'display_options', ""),
                "is_deleted_ldap": getattr(user, 'is_deleted_ldap', False),
                "pdffont": getattr(user, 'pdffont', ""),
                "picture": getattr(user, 'picture', ""),
                "begin_date": getattr(user, 'begin_date', None),
                "end_date": getattr(user, 'end_date', None),
                "keep_devices_when_purging_item": getattr(user, 'keep_devices_when_purging_item', None),
                "privatebookmarkorder": getattr(user, 'privatebookmarkorder', ""),
                "backcreated": getattr(user, 'backcreated', None),
                "task_state": getattr(user, 'task_state', None),
                "layout": getattr(user, 'layout', ""),
                "palette": getattr(user, 'palette', ""),
                "set_default_requester": getattr(user, 'set_default_requester', None),
                "lock_autolock_mode": getattr(user, 'lock_autolock_mode', None),
                "lock_directunlock_notification": getattr(user, 'lock_directunlock_notification', None),
                "date_creation": getattr(user, 'date_creation', None),
                "highcontrast_css": getattr(user, 'highcontrast_css', False),
                "plannings": getattr(user, 'plannings', ""),
                "sync_field": getattr(user, 'sync_field', ""),
                "groups_id": getattr(user, 'groups_id', 0),
                "users_id_supervisor": getattr(user, 'users_id_supervisor', 0),
                "timezone": getattr(user, 'timezone', ""),
                "default_dashboard_central": getattr(user, 'default_dashboard_central', ""),
                "default_dashboard_assets": getattr(user, 'default_dashboard_assets', ""),
                "default_dashboard_helpdesk": getattr(user, 'default_dashboard_helpdesk', ""),
                "default_dashboard_mini_ticket": getattr(user, 'default_dashboard_mini_ticket', ""),
                "player_id": getattr(user, 'player_id', ""),
                "no_entity_mail_sent": getattr(user, 'no_entity_mail_sent', False),
            }

            response_data = {
                "message": f"Login successful ({'AD/LDAP' if ldap_authenticated else 'Local DB'} Authenticated)",
                "user": user_data,
                "ad_raw": ad_raw if ldap_authenticated else None,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Critical error in login process")
            return Response({"error": f"Server error: {str(e)}"}, status=500)

        return Response({"error": "Invalid username or password"}, status=status.HTTP_400_BAD_REQUEST)
class LogoutView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response({"error": "Refresh token is required"}, status=400)

        user_id = None

        # Step 1: Try to extract user_id EVEN from expired/invalid tokens
        try:
            # This works even if token is expired
            
            untyped = UntypedToken(refresh_token)
            user_id = untyped.payload.get("user_id")
        except Exception as e:
            print(f"Could not extract user_id from token: {e}")

        # Step 2: ALWAYS save logout_time if we know the user
        # if user_id:
        #     latest_login = UserLoginHistory.objects.filter(
        #         user_id=user_id,
        #         logout_time__isnull=True
        #     ).order_by('-login_time').first()

            # if latest_login:
            #     latest_login.logout_time = timezone.now()
            #     latest_login.save(update_fields=['logout_time'])
            #     print(f"Logout time saved for user {user_id}: {latest_login.logout_time}")

        # Step 3: Try to blacklist (but NEVER fail the logout because of it)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            print(f"Refresh token blacklisted for user {user_id or 'unknown'}")
        except (TokenError, InvalidToken, Exception) as e:
            print(f"Blacklist failed (not critical): {e}")

        # ALWAYS return success — user is logged out locally anyway
        return Response({"message": "Logged out successfully"}, status=200)

    
# ---------------- FORGOT PASSWORD ----------------
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "No user found with this email"}, status=status.HTTP_404_NOT_FOUND)

        new_password = generate_random_password()
        user.password = make_password(new_password)
        user.force_password_change = True  # Set flag to force change on next login
        user.save(update_fields=["password", "force_password_change"])

        try:
            send_mail(
                subject="Your New Password",
                message=f"Hello {user.firstname or user.name},\n\nYour temporary password is: {new_password}\nPlease login and change it immediately for security.",
                from_email="no-reply@qatarmedicalcenter.com",
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception as e:
            return Response({"error": f"Failed to send email: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"message": "A new temporary password has been sent to your email. Please change it after login."}, status=status.HTTP_200_OK)
    


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        
        # Handle both snake_case and camelCase
        old_password = request.data.get("old_password") or request.data.get("oldPassword")
        new_password = request.data.get("new_password") or request.data.get("newPassword")
        confirm_password = request.data.get("confirm_password") or request.data.get("confirmPassword")

        if not all([old_password, new_password, confirm_password]):
            missing = []
            if not old_password: missing.append("old_password")
            if not new_password: missing.append("new_password")
            if not confirm_password: missing.append("confirm_password")
            return Response(
                {"error": f"Missing fields: {', '.join(missing)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_password != confirm_password:
            return Response(
                {"error": "New passwords do not match"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify old password
        if not check_password(old_password, user.password):
            return Response(
                {"error": "Old password is incorrect"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update password and reset force flag
        user.password = make_password(new_password)
        user.force_password_change = False
        user.save(update_fields=["password", "force_password_change"])

        return Response(
            {"message": "Password changed successfully"}, 
            status=status.HTTP_200_OK
        )