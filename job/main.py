
from google.cloud import storage
import logging
import os
import sys
import time

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oaklab.settings')
django.setup()

from kc_app.models import TaskSubmission  # Use actual app name
from kc_app.utils import download_from_gcs, upload_to_gcs
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from job.utils import convert_file_to_jsonl_data, call_kc_api, save_results_to_csv, save_jsonl_file

logger = logging.getLogger(__name__)

def process_kc_task(task_id):
    """
    Fast preparation work - can run in parallel
    """
    try:
        task = TaskSubmission.objects.get(id=task_id)
        task.status = 'uploaded'
        task.save()
        transaction.commit()
        
        
        # Convert file (fast operation)
        logger.info(f"Converting file for task {task_id}")

        # Step 2: Download from GCS
        local_path = download_from_gcs(task.gcs_input_blob, "/tmp")
        print("Local Path: ", local_path)

        # Step 3: Now use the file like normal
        jsonl_data = convert_file_to_jsonl_data(local_path)
        task.status = 'converted'
        print("Converted Successfully")
        task.save()
        transaction.commit()
        
        # Save JSONL file (fast operation)
        logger.info(f"Saving JSONL file for task {task_id}")
        jsonl_path = save_jsonl_file(jsonl_data, task_id)
        task.gcs_json_blob =  f"processed/task_{task_id}_processed.jsonl"
        task.save()
        upload_to_gcs(jsonl_path, task.gcs_json_blob)
        task.status = 'queued'  # Now queued for API processing
        task.save()
        transaction.commit()
        
        return jsonl_data

        
    except Exception as e:
        logger.error(f"Task {task_id} preparation failed: {str(e)}")
        task = TaskSubmission.objects.get(id=task_id)
        task.status = 'failed'
        task.error_message = str(e)
        task.save()
        transaction.commit()

        send_failure_email(task)

def process_kc_api(task_id, jsonl_data):
    """
    Slow API work - runs one at a time
    """
    try:
        task = TaskSubmission.objects.get(id=task_id)
        print("IN KC API PROCESSING")
        
        # This is when actual processing starts
        task.status = 'processing'
        task.save()
        transaction.commit()
        logger.info(f"Starting API call for task {task_id}")
        
        # The slow API call
        kc_results = call_kc_api(jsonl_data)
        task.gcs_output_blob = f"results/task_{task_id}_output.csv"
        task.save()
        
        # Save results
        logger.info(f"Saving results for task {task_id}")
        csv_path = save_results_to_csv(kc_results, task_id)
        upload_to_gcs(csv_path, task.gcs_output_blob)
        
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save()
        transaction.commit()
        
        send_completion_email(task)
        logger.info(f"Task {task_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Task {task_id} API processing failed: {str(e)}")
        task = TaskSubmission.objects.get(id=task_id)
        task.status = 'failed'
        task.error_message = str(e)
        task.save()
        transaction.commit()
        send_failure_email(task)
        raise e  # Re-raise so Celery knows it failed
    
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


def run():
    task_id = os.environ.get("TASK_ID")
    jsonl_data = process_kc_task(task_id)
    print("Converted to jsonl file successfully. Now calling API")
    process_kc_api(task_id, jsonl_data)
    print("API returned")
    
if __name__ == "__main__":
    run()
