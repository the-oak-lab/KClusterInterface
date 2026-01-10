from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upload/', views.upload_questions, name='upload_questions'),
    path('task/<int:task_id>/', views.task_status, name='task_status'),
    path('task/<int:task_id>/download/<str:result_type>/', views.download_results, name='download_results'),
    path('task/<int:task_id>/next-steps/', views.next_steps, name='next_steps'),
    path('ajax/task/<int:task_id>/status/', views.ajax_task_status, name='ajax_task_status'),
    path('kill-task/<int:task_id>', views.kill_task, name="kill_task"),
    path('reprocess-task/<int:task_id>', views.reprocess_task, name="reprocess_task"),
    path('mark-failed/<int:task_id>', views.mark_failed, name="mark_failed")
]