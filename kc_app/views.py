from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, FileResponse, Http404
from django.core.paginator import Paginator
from .models import TeacherUser, TaskSubmission, KCModel
from .forms import TeacherRegistrationForm, FileUploadForm
from .utils import upload_to_gcs, download_from_gcs
from django.conf import settings
import subprocess
from google.cloud import storage
from datetime import datetime, timedelta, timezone

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
        'processing_tasks': tasks.filter(status__in=['processing', 'queued', 'uploaded']).count(),
        'failed_tasks': tasks.filter(status='failed').count(),
    }
    
    return render(request, 'dashboard.html', context)

def process_file(task_id: int):
    # gcs_input_path: user_uploads/filename.?
    # gcs_intermediate_path: converted/filename_converted.jsonl
    # gcs_output_path: pmi/filename.?
    # gcs_output_2: concepts/filename.?
    job_name = "process-question-file"
    region = "us-central1"
    cmd = [
        "gcloud", "run", "jobs", "execute", job_name,
        "--region", region,
        "--wait",
        f"--set-env-vars=GCS_BUCKET={settings.GCS_BUCKET_NAME},TASK_ID={task_id}",
    ]
    subprocess.Popen(cmd)

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
            
            # Save file in GCS
            local_path = task.uploaded_file.path
            gcs_filename = f"uploads/task_{task.id}_{task.filename}" # type: ignore[attr-defined]
            upload_to_gcs(local_path, gcs_filename)

            task.gcs_input_blob = gcs_filename
            task.gcs_json_blob =  f"processed/task_{task.id}_processed.jsonl"
            # task.gcs_output_blob = f"results/task_{task.id}_output.csv" # type: ignore[attr-defined]
            task.save()
            
            # Start Job
            process_file(task.id)
            
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
    
    if task.status != 'completed' or not task.gcs_output_blob:
        messages.error(request, 'Results are not available for download.')
        return redirect('task_status', task_id=task_id)
    
    try:
        # Create GCS client and get the blob
        client = storage.Client()
        bucket = client.bucket(settings.GCS_BUCKET_NAME)
        blob = bucket.blob(task.gcs_output_blob)
        
        # Generate signed URL with timezone-aware datetime
        signed_url = blob.generate_signed_url(
            expiration=datetime.now(timezone.utc) + timedelta(hours=1),
            method='GET'
        )
        return redirect(signed_url)
    except Exception as e:
        messages.error(request, 'Could not generate download link.')
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
        'has_results': bool(task.gcs_output_blob),
    })


