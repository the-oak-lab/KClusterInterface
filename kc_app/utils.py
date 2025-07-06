import json
import pandas as pd
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import os
import tempfile
from typing import List, Dict, Any, Union
from google.cloud import storage

def download_from_gcs(gcs_output_blob, dest_path):
    client = storage.Client()
    bucket = client.bucket(settings.GCS_BUCKET_NAME)
    blob = bucket.blob(gcs_output_blob)
    blob.download_to_filename(dest_path)
    return blob.public_url

def upload_to_gcs(local_path, gcs_filename):
    client = storage.Client()
    bucket = client.bucket(settings.GCS_BUCKET_NAME)
    blob = bucket.blob(gcs_filename)
    blob.upload_from_filename(local_path)
    return blob.public_url
# Example usage and testing
if __name__ == "__main__":
    # Test the function
    # try:
    #     data = convert_file_to_jsonl_data("/Users/yaboi/Desktop/Oaklab/KClusterInterface/kc_app/static/kc_app/files/example.jsonl")
    #     print(f"Successfully converted {len(data)} records")
    #     print(data)
    #     # pass
    # except FileValidationError as e:
    #     print(f"Validation Error: {e}")
    # except ValueError as e:
        # print(f"Format Error: {e}")
    pass