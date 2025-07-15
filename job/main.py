import logging
import os
import sys

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oaklab.settings')
django.setup()

from kc_app.models import TaskSubmission  # Use actual app name
from kc_app.utils import download_from_gcs, upload_to_gcs
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from job.utils import convert_file_to_jsonl_data, save_results_to_csv, save_jsonl_file
# New code for launching api call
from external.kcluster.launch import launch_batch_job, wait_for_job_completion
from external.kcluster.question import Question
from external.kcluster.pmi import KCluster

logger = logging.getLogger()
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Optional: remove duplicate handlers
if logger.hasHandlers():
    logger.handlers.clear()
    logger.addHandler(handler)

logger = logging.getLogger(__name__)
def flush_logs():
    for handler in logging.getLogger().handlers:
        handler.flush()

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
        flush_logs()
        
        # Save JSONL file (fast operation)
        logger.info(f"Saving JSONL file for task {task_id}")
        jsonl_path = save_jsonl_file(jsonl_data, task_id)
        task.gcs_json_blob =  f"processed/task_{task_id}_processed.jsonl"
        task.save()
        upload_to_gcs(jsonl_path, task.gcs_json_blob)
        task.status = 'queued'  # Now queued for API processing
        task.save()
        transaction.commit()
        flush_logs()
        
        return jsonl_data

        
    except Exception as e:
        logger.error(f"Task {task_id} preparation failed: {str(e)}")
        task = TaskSubmission.objects.get(id=task_id)
        task.status = 'failed'
        task.error_message = str(e)
        task.save()
        transaction.commit()
        flush_logs()

        send_failure_email(task)

def process_kc_api(task_id, jsonl_data):
    """
    Make calls to phi api to process questions
    """
    try:
        task = TaskSubmission.objects.get(id=task_id)
        print("IN KC API PROCESSING")
        
        # This is when actual processing starts
        task.status = 'processing'
        task.save()
        transaction.commit()
        logger.info(f"Starting API call for task {task_id}")
        flush_logs()
        
        # Start KCluster alg for questions
        questions = [Question(item) for item in jsonl_data]

        logger.info(f"Loaded {len(questions)} questions from {task.gcs_json_blob}")

        logger.info(f"Launching job '{task_id}'...")
        flush_logs()

        job, _ = launch_batch_job(questions, job_id=task_id, batch_size=8,
                                completion_time_in_mins=60, secs_per_batch=0.1)
        
        launched_jobs = [{"job_id": task_id, "job_obj": job, "num_questions": len(questions)}]

        # job.name -> job.name to get Vertex AI Job ID

        # Wait for job to be done
        wait_for_job_completion(launched_jobs=launched_jobs)

        # Call KCluster
        kcluster = KCluster(questions, task_id)
        concept_df, kcluster_df = kcluster.create_new_kc() # what is kcluster df again?

        task.gcs_output_concept_blob= f"concepts/task_{task_id}_concepts.csv"
        task.gcs_output_pmi_blob= f"kclusters/task_{task_id}_kcluster.csv"

        # Save results
        logger.info(f"Saving results for task {task_id}")
        flush_logs()
        concept_path = save_results_to_csv(concept_df, task_id)
        pmi_path = save_results_to_csv(kcluster_df, task_id)
        upload_to_gcs(concept_path, task.gcs_output_concept_blob)
        upload_to_gcs(pmi_path, task.gcs_output_pmi_blob)
        
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save()
        transaction.commit()
        
        send_completion_email(task)
        logger.info(f"Task {task_id} completed successfully")
        flush_logs()
        
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
    print("Converted to jsonl file successfully. Now calling API", flush=True)
    process_kc_api(task_id, jsonl_data)
    print("API returned")
    
if __name__ == "__main__":
    run()
