# accounts/serializers.py
from rest_framework import serializers
from .models import User  # adjust import path as needed
from django.utils import timezone
from .models import User,UserRoleMapping
from master.models import Entity
from django.contrib.auth.hashers import make_password


class WatcherUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'realname', 'email', 'groups_id']


# class UsersGroupSerializer(serializers.ModelSerializer):
#     entity_name = serializers.SerializerMethodField()
#     user_ids = serializers.ListField(
#         child=serializers.IntegerField(),
#         required=False,
#         write_only=True
#     )
#     users = WatcherUserSerializer(many=True, read_only=True, source='get_users')

#     class Meta:
#         model = UsersGroup
#         fields = [
#             'id', 'name', 'comment', 'entities_id', 'entity_name',
#             'is_recursive',
#             'user_ids', 'users'
#         ]

#     # ✅ Readable Entity name
#     def get_entity_name(self, obj):
#         if obj.entities_id:
#             entity = Entity.objects.filter(id=obj.entities_id).first()
#             return entity.name if entity else None
#         return None

#     # ✅ When creating a group, assign users if provided
#     def create(self, validated_data):
#         user_ids = validated_data.pop('user_ids', [])
#         group = UsersGroup.objects.create(**validated_data)

#         if user_ids:
#             User.objects.filter(id__in=user_ids).update(groups_id=group.id)

#         return group

#     # ✅ When updating, reassign users
#     def update(self, instance, validated_data):
#         user_ids = validated_data.pop('user_ids', None)

#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()

#         if user_ids is not None:
#             # Unassign old users safely (set to 0 instead of NULL)
#             User.objects.filter(groups_id=instance.id).update(groups_id=0)
#             # Assign new users
#             User.objects.filter(id__in=user_ids).update(groups_id=instance.id)

#         return instance


   


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = [ 'id', 'name', 'employee_id', 'email', 'password', 'phone', 'realname', 'firstname', 'entities_ids', 'entity',
            'location', 'department', 'is_active', 'is_manager', 'is_hod', 'is_ldap_user', 'is_staff', 'is_superuser', 'created_at', 'updated_at', ]
        read_only_fields = [ 'id', 'created_at', 'updated_at', 'is_ldap_user', 'is_staff', 'is_superuser', ]
        extra_kwargs = {
            'name': {'required': False},
            'employee_id': {'required': True},
            'email': {'required': False},
        }

    def validate(self, attrs):
        # Optional: add more business rules
        if not attrs.get('name') and not attrs.get('email'):
            raise serializers.ValidationError("At least name or email is required.")
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)

        if password:
            user.password = make_password(password)
            user.password_last_update = timezone.now()
            user.save(update_fields=['password', 'password_last_update'])

        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)

        # Update normal fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Special handling for password
        if password:
            instance.password = make_password(password)
            instance.password_last_update = timezone.now()

        instance.save()
        return instance
    
class UserRoleMappingSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    role_name = serializers.CharField(source='role.field_name', read_only=True)

    class Meta:
        model = UserRoleMapping
        fields = [
            'id',
            'user', 'user_name',
            'role', 'role_name',
            'created_by', 'modified_by',
            'created_at', 'updated_at',
            'is_active',
        ]