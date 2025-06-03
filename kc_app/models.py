# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
import os

class TeacherUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    institution = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

class TaskSubmission(models.Model):
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('converted', 'Converted'),
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    teacher = models.ForeignKey(TeacherUser, on_delete=models.CASCADE)
    uploaded_file = models.FileField(
        upload_to='uploads/',
        validators=[FileExtensionValidator(allowed_extensions=['csv', 'xlsx', 'xls', 'json', 'jsonl'])]
    )
    json_file = models.FileField(upload_to='processed/', blank=True, null=True)
    output_csv = models.FileField(upload_to='results/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Task {self.id} - {self.teacher.email} - {self.status}"
    
    @property
    def filename(self):
        return os.path.basename(self.uploaded_file.name) if self.uploaded_file else "Unknown"

class KCModel(models.Model):
    task_submission = models.OneToOneField(TaskSubmission, on_delete=models.CASCADE)
    model_file = models.FileField(upload_to='kc_models/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"KC Model for Task {self.task_submission.id}"