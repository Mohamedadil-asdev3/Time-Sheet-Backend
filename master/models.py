from django.db import models

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
    
