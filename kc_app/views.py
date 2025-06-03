from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, FileResponse, Http404
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone
from .models import TeacherUser, TaskSubmission, KCModel
from .forms import TeacherRegistrationForm, FileUploadForm
from .tasks import process_kc_task
import os

def home(request):
    """Welcome page"""
    return render(request, 'home.html')

def register(request):
    """Teacher registration"""
    if request.method == 'POST':
        form = TeacherRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful! Welcome to the KC Analysis Platform.')
            return redirect('dashboard')
    else:
        form = TeacherRegistrationForm()
    
    return render(request, 'register.html', {'form': form})

@login_required
def dashboard(request):
    """Dashboard showing user's task submissions"""
    teacher = get_object_or_404(TeacherUser, user=request.user)
    tasks = TaskSubmission.objects.filter(teacher=teacher)
    
    # Pagination
    paginator = Paginator(tasks, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_tasks': tasks.count(),
        'completed_tasks': tasks.filter(status='completed').count(),
        'processing_tasks': tasks.filter(status='processing').count(),
        'failed_tasks': tasks.filter(status='failed').count(),
    }
    
    return render(request, 'dashboard.html', context)

@login_required
def upload_questions(request):
    """Upload questions file"""
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            teacher = get_object_or_404(TeacherUser, user=request.user)
            task = form.save(commit=False)
            task.teacher = teacher
            task.save()
            
            # Start Celery task
            celery_task = process_kc_task.delay(task.id)
            task.celery_task_id = celery_task.id
            task.save()
            
            messages.success(request, f'File "{task.filename}" uploaded successfully! Processing has begun.')
            return redirect('task_status', task_id=task.id)
    else:
        form = FileUploadForm()
    
    return render(request, 'upload.html', {'form': form})

@login_required
def task_status(request, task_id):
    """View specific task status"""
    teacher = get_object_or_404(TeacherUser, user=request.user)
    task = get_object_or_404(TaskSubmission, id=task_id, teacher=teacher)
    
    return render(request, 'task_status.html', {'task': task})

@login_required
def download_results(request, task_id):
    """Download the results CSV file"""
    teacher = get_object_or_404(TeacherUser, user=request.user)
    task = get_object_or_404(TaskSubmission, id=task_id, teacher=teacher)
    
    if task.status != 'completed' or not task.output_csv:
        messages.error(request, 'Results are not available for download.')
        return redirect('task_status', task_id=task_id)
    
    try:
        response = FileResponse(
            task.output_csv.open('rb'),
            as_attachment=True,
            filename=f'kc_results_{task_id}.csv'
        )
        return response
    except FileNotFoundError:
        messages.error(request, 'Result file not found.')
        return redirect('task_status', task_id=task_id)

@login_required
def next_steps(request, task_id):
    """Next steps page for completed tasks"""
    teacher = get_object_or_404(TeacherUser, user=request.user)
    task = get_object_or_404(TaskSubmission, id=task_id, teacher=teacher)
    
    if task.status != 'completed':
        messages.error(request, 'Task must be completed to view next steps.')
        return redirect('task_status', task_id=task_id)
    
    # Get or create KC model
    kc_model, created = KCModel.objects.get_or_create(task_submission=task)
    
    return render(request, 'next_steps.html', {
        'task': task,
        'kc_model': kc_model
    })

@login_required
def ajax_task_status(request, task_id):
    """AJAX endpoint for task status updates"""
    teacher = get_object_or_404(TeacherUser, user=request.user)
    task = get_object_or_404(TaskSubmission, id=task_id, teacher=teacher)
    
    return JsonResponse({
        'status': task.status,
        'error_message': task.error_message,
        'completed_at': task.completed_at.isoformat() if task.completed_at else None,
        'has_results': bool(task.output_csv),
    })