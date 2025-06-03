from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import TaskSubmission
from .utils import convert_file_to_jsonl_data, call_kc_api, save_results_to_csv, save_jsonl_file
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_kc_task(task_id):
    """
    Celery task to process KC generation
    """
    try:
        task = TaskSubmission.objects.get(id=task_id)
        task.status = 'processing'
        task.save()
        
        # Step 1: Convert file to JSONL-ready data
        logger.info(f"Converting file to JSONL data for task {task_id}")
        jsonl_data = convert_file_to_jsonl_data(task.uploaded_file.path)
        
        # Step 2: Save as JSONL file for records (optional)
        logger.info(f"Saving JSONL file for task {task_id}")
        jsonl_path = save_jsonl_file(jsonl_data, task_id)
        task.json_file.name = jsonl_path
        task.save()
        
        # Step 3: Call KC API with JSONL data
        logger.info(f"Calling KC API for task {task_id}")
        kc_results = call_kc_api(jsonl_data)
        
        # Step 4: Save results to CSV
        logger.info(f"Saving results for task {task_id}")
        csv_path = save_results_to_csv(kc_results, task_id)
        
        # Update task
        task.output_csv.name = csv_path
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save()
        
        # Send notification email
        send_completion_email(task)
        
        logger.info(f"Task {task_id} completed successfully")
        return f"Task {task_id} completed successfully"
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {str(e)}")
        task = TaskSubmission.objects.get(id=task_id)
        task.status = 'failed'
        task.error_message = str(e)
        task.save()
        
        # Send failure notification
        send_failure_email(task)
        
        raise e

def send_completion_email(task):
    """Send email notification when task is completed"""
    try:
        subject = 'KC Analysis Complete - Results Ready'
        message = f"""
        Hello {task.teacher.first_name},
        
        Your Knowledge Component analysis is complete!
        
        File: {task.filename}
        Completed: {task.completed_at.strftime('%Y-%m-%d %H:%M:%S')}
        
        You can download your results at: {settings.SITE_URL}/task/{task.id}/
        
        Best regards,
        KC Analysis Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [task.teacher.email],
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Failed to send completion email for task {task.id}: {str(e)}")

def send_failure_email(task):
    """Send email notification when task fails"""
    try:
        subject = 'KC Analysis Failed'
        message = f"""
        Hello {task.teacher.first_name},
        
        Unfortunately, your Knowledge Component analysis failed to complete.
        
        File: {task.filename}
        Error: {task.error_message}
        
        Please try uploading your file again or contact support if the issue persists.
        
        Best regards,
        KC Analysis Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [task.teacher.email],
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Failed to send failure email for task {task.id}: {str(e)}")