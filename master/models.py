from django.db import models
USER = 'users.User'

# Create your models here.
class BaseModel(models.Model):
    created_by = models.IntegerField()
    modified_by = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        abstract = True

class Entity(BaseModel) : 
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    displayName = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'master_entity'

    def __str__(self):
        return self.name
    

class Department(BaseModel) :
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    displayName = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'master_deparment'

    def __str__(self):
        return self.name
    

class Location(BaseModel) :
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    displayName = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'master_location'

    def __str__(self):
        return self.name
    

class Task(BaseModel) : 
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    displayName = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'master_task'

    def __str__(self):
        return self.name
    

# class SubTask(BaseModel) : 
#     name = models.CharField(max_length=255)
#     description = models.TextField(blank=True, null=True)
#     displayName = models.TextField(blank=True, null=True)

#     class Meta:
#         db_table = 'master_subTask'

#     def __str__(self):
#         return self.name
class SubTask(BaseModel):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='subtasks'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    displayName = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'master_subTask'

    def __str__(self):
        return f"{self.task.name} - {self.name}"    

class Role(BaseModel) :
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    displayName = models.TextField(blank=True, null=True)
    entity = models.ForeignKey(Entity, on_delete=models.SET_NULL, null=True, blank=True)
    class Meta:
        db_table = 'master_role'

    def __str__(self):
        return self.name
    
class Platform(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    displayName = models.CharField(max_length=255, blank=True, null=True)
    

    class Meta:
        db_table = 'master_platform'

    def __str__(self):
        return self.name


class Status(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    displayName = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'master_status'

    def __str__(self):
        return self.name
    
class Holiday(models.Model):
    # entity_ids for multiple entities (JSONField for MySQL)
    entity_ids = models.JSONField(
        default=list,
        blank=True,
        null=True,
        db_column='entity_ids'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='holiday_departments'  
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='holiday_locations' 
    )
    # Removed single entity FK; use entity_ids instead
    name = models.CharField(max_length=100, null=True, blank=True)  
    date = models.DateField()  
    description = models.TextField(blank=True, null=True)  
    status = models.SmallIntegerField(choices=((1, 'Active'), (2, 'Inactive'), (3, 'Delete')))  
    created_on = models.DateTimeField(auto_now_add=True)  
    created_by = models.ForeignKey(USER, on_delete=models.CASCADE, blank=True, null=True, related_name='%(class)s_created_by') 
    created_ip = models.GenericIPAddressField(null=True) 
    modified_on = models.DateTimeField(auto_now=True)  
    modified_by = models.ForeignKey(USER, on_delete=models.CASCADE, blank=True, null=True, related_name='%(class)s_modified_by') 
    modified_ip = models.GenericIPAddressField(blank=True, null=True)  
    code = models.CharField(max_length=15, db_index=True, null=True)  
    
    def __str__(self):
        return self.name  # Returning the holiday name for representation

    @property
    def entity_names(self):
        if self.entity_ids:
            entities = Entity.objects.filter(id__in=self.entity_ids)
            return [entity.name for entity in entities if entity.name]
        return ["No Entity"]

    class Meta:
        db_table = 'master_holiday'  # Specifying the database table name
        verbose_name = 'Holiday'  # Singular representation in admin
        verbose_name_plural = 'Holidays'  # Plural representation in admin
        
        
class EmailTemplate(models.Model):
    id = models.AutoField(primary_key=True)
    email_event = models.CharField(max_length=45)
    email_template = models.TextField()  # longtext → TextField in Django
    is_active = models.CharField(max_length=25, default='Y')

    class Meta:
        db_table = 'email_templates'
        verbose_name = 'Email Template'
        verbose_name_plural = 'Email Templates'

    def __str__(self):
        return f"{self.email_event} ({'Active' if self.is_active == 'Y' else 'Inactive'})"
    
