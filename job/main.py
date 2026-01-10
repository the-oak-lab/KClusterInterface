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
from job.utils import convert_file_to_jsonl_data, save_results_to_csv, save_jsonl_file
# New code for launching api call
from external.kcluster.launch import launch_batch_job, wait_for_job_completion, get_existing_batch_job
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
        logger.info(f"Attempting to access task {task_id} from database")
        flush_logs()
        task = TaskSubmission.objects.get(id=task_id)
        logger.info(f"Task {task_id} accessed successfully")
        flush_logs()        

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

def process_kc_api(task_id, jsonl_data, resume=False, job=None):
    """
    Make calls to phi api to process questions
    """
    try:
        task = TaskSubmission.objects.get(id=task_id)
        print("IN KC API PROCESSING")

        if not resume:
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

            # Launch a new Vertex AI batch job
            job, _ = launch_batch_job(
                questions,
                job_id=task_id,  # Ensure this is unique to the task
                batch_size=8,
                completion_time_in_mins=60,
                secs_per_batch=0.1
            )
            task.job_handle = job.resource_name.split("/")[-1]
            print("JOB HANDLE: ", task.job_handle)
            task.save()
            launched_jobs = [{"job_id": task_id, "job_obj": job, "num_questions": len(questions)}]

        else:
            questions = [Question(item) for item in jsonl_data]
            logger.info(f"Resuming existing job for task {task_id}")
            launched_jobs = [{"job_id": task_id, "job_obj": job, "num_questions": len(questions)}]

        # Wait for job completion (whether new or resumed)
        wait_for_job_completion(launched_jobs=launched_jobs, poll_interval_seconds=300)

        # Run KCluster
        questions = [Question(item) for item in jsonl_data]
        kcluster = KCluster(questions, task_id)
        concept_df, kcluster_df = kcluster.create_new_kc()

        task.gcs_output_concept_blob = f"concepts/task_{task_id}_concepts.csv"
        task.gcs_output_kc_blob = f"kclusters/task_{task_id}_kcluster.csv"

        logger.info(f"Saving results for task {task_id}")
        flush_logs()
        concept_path = save_results_to_csv(concept_df, task_id)
        upload_to_gcs(concept_path, task.gcs_output_concept_blob)
        pmi_path = save_results_to_csv(kcluster_df, task_id)
        upload_to_gcs(pmi_path, task.gcs_output_kc_blob)

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
        Perspicacious Team
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
    logger.info(f"Starting processing for task {task_id}")
    flush_logs()

    task = TaskSubmission.objects.get(id=task_id)

    # Avoid duplicate processing
    if task.status == 'completed':
        logger.info(f"Task {task_id} is already completed. Skipping.")
        return
    elif task.status == 'failed':
        logger.info(f"Task {task_id} previously failed. Skipping duplicate run.")
        return
    elif task.status == 'processing':
        logger.info(f"Task {task_id} is already processing. Attempting to resume. WE DID IT JOE")
        flush_logs()

        # Try to reattach to the existing Vertex AI job
        if task_id == "27":
            job_id = "8075544930396667904" 
        elif task_id == "28":
            job_id = "6841558632497152000"
        else:
            raise KeyError("No job id found rn")
        job = get_existing_batch_job(job_id)
        if not job:
            logger.warning(f"No existing Vertex AI job found for task {job_id}. Cannot resume, starting fresh.")
            # jsonl_data = process_kc_task(task_id)
            # process_kc_api(task_id, jsonl_data, resume=False)
            return

        # If job is still running or pending, just wait for it
        if job.state.name in ("JOB_STATE_PENDING", "JOB_STATE_RUNNING"):
            logger.info(f"Job {job_id} still running on Vertex AI, waiting for completion.")
            # Continue post-processing after the existing job finishes
            jsonl_data = process_kc_task(task_id)
            process_kc_api(task_id, jsonl_data, resume=True, job= job)
        else:
            logger.info(f"Job {task_id} already completed on Vertex AI. Proceeding to post-processing.")
            jsonl_data = process_kc_task(task_id)
            process_kc_api(task_id, jsonl_data, resume=True, job= job)
    else:
        # If we get here, status is new/pending, so we can start fresh
        jsonl_data = process_kc_task(task_id)
        if jsonl_data is None:
            logger.warning(f"Task {task_id} produced no jsonl data. Skipping.")
            return

        logger.info("Converted to jsonl file successfully. Now calling API")
        flush_logs()
        process_kc_api(task_id, jsonl_data, resume=False)
        logger.info("API returned")

    
if __name__ == "__main__":
    run()
