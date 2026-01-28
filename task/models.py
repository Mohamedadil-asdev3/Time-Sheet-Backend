from django.db import models
from django.conf import settings
from master.models import Platform, Status, Task, SubTask
from users.models import User
from django.utils import timezone


class BaseModel(models.Model):
    created_by = models.IntegerField()
    modified_by = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True

class TaskList(models.Model):
    date = models.DateField()

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_tasks",
        db_index=True,
    )

    platform = models.ForeignKey(Platform, on_delete=models.CASCADE)

    task = models.ForeignKey(
        Task,
        on_delete=models.PROTECT,
        related_name="task_entries",
    )

    subtask = models.ForeignKey(
        SubTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subtask_entries",
    )

    bitrix_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        help_text="External Bitrix ID"
    )

    duration = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        help_text="Hours spent (e.g. 4.50)"
    )

    description = models.TextField(blank=True, null=True)

    status = models.ForeignKey(
        Status,
        on_delete=models.PROTECT,
        related_name="task_entries",
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "task_list"
        ordering = ["-date", "task__name"]          # ← now valid because Task has 'name'
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["platform", "status"]),
            models.Index(fields=["bitrix_id"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        subtask_part = f" → {self.subtask.name}" if self.subtask else ""
        return f"{self.user.username} – {self.task.name}{subtask_part} ({self.date}) [{self.status.name}]"
# class TaskList(BaseModel):

#     STATUS_CHOICES = [
#         ('draft', 'Draft'),
#         ('submitted', 'Submitted'),
#         ('approved', 'Approved'),
#         ('rejected', 'Rejected'),
#     ]

#     date = models.DateField()
#     user = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name="tasks"
#     )
#     platform = models.CharField(max_length=100)
#     task = models.CharField(max_length=255)
#     subtask = models.CharField(max_length=255, blank=True, null=True)
#     bitrix_id = models.CharField(max_length=50, blank=True, null=True)
#     duration = models.DecimalField(max_digits=5, decimal_places=2)
#     description = models.TextField(blank=True, null=True)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

#     class Meta:
#         db_table = "task_list"

#     def __str__(self):
#         return f"{self.user} - {self.task} ({self.date})"
