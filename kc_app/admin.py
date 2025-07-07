from django.contrib import admin
from .models import TeacherUser, TaskSubmission, KCModel

@admin.register(TeacherUser)
class TeacherUserAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'institution', 'created_at']
    search_fields = ['first_name', 'last_name', 'email']
    list_filter = ['institution', 'created_at']

@admin.register(TaskSubmission)
class TaskSubmissionAdmin(admin.ModelAdmin):
    list_display = ['id', 'teacher', 'filename', 'status', 'created_at', 'completed_at']
    list_filter = ['status', 'created_at']
    search_fields = ['teacher__email', 'teacher__first_name', 'teacher__last_name']
    readonly_fields = ['created_at', 'completed_at']

@admin.register(KCModel)
class KCModelAdmin(admin.ModelAdmin):
    list_display = ['task_submission', 'created_at']
    list_filter = ['created_at']