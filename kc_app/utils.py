import json
import pandas as pd
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import os
import tempfile
def convert_file_to_jsonl_data(file_path):
    file_format = file_path.split(".")[-1]
    """Convert uploaded file directly to JSONL-ready data (list of objects)"""
    if file_format == 'jsonl':
        # Read JSONL file (one JSON object per line)
        data = []
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:  # Skip empty lines
                    data.append(json.loads(line))
        return data
    
    elif file_format == 'json':
        with open(file_path, 'r') as f:
            json_data = json.load(f)
            # Ensure it's a list of objects
            if isinstance(json_data, dict):
                return [json_data]  # Single object -> list
            elif isinstance(json_data, list):
                return json_data    # Already a list
            else:
                raise ValueError("JSON must be an object or array of objects")
    
    elif file_format == 'csv':
        df = pd.read_csv(file_path)
        return df.to_dict('records')
    
    elif file_format == 'excel':
        df = pd.read_excel(file_path)
        return df.to_dict('records')
    
    else:
        raise ValueError(f"Unsupported file format: {file_format}")

def call_kc_api(jsonl_data):
    """Call the KC identification API with JSONL data"""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {settings.KC_API_TOKEN}' if settings.KC_API_TOKEN else ''
    }
    
    # Send the data - adjust this based on what your API expects
    # Option 1: Send as JSON array
    response = requests.post(
        settings.KC_API_URL,
        json={'questions': jsonl_data},
        headers=headers,
        timeout=300
    )
    
    # Option 2: If API expects raw JSONL string, use this instead:
    # headers['Content-Type'] = 'application/x-jsonlines'
    # jsonl_string = '\n'.join(json.dumps(item) for item in jsonl_data)
    # response = requests.post(
    #     settings.KC_API_URL,
    #     data=jsonl_string,
    #     headers=headers,
    #     timeout=300
    # )
    
    if response.status_code != 200:
        raise Exception(f"API request failed: {response.status_code} - {response.text}")
    
    return response.json()

def call_kc_api(jsonl_data):
    """
    Mock KC API call - returns your existing CSV data
    Replace this with real API call when ready
    """
    import pandas as pd
    import os
    import time
    import random
    from django.conf import settings
    
    # Simulate realistic processing time
    num_questions = len(jsonl_data)
    
    # Base processing time (10-30 seconds) + time per question (2-5 seconds each)
    base_delay = random.uniform(10, 30)
    per_question_delay = random.uniform(2, 5) * num_questions
    total_delay = base_delay + per_question_delay
    
    # Cap the delay at 2 minutes for demo purposes
    total_delay = min(total_delay, 100)
    
    print(f"🧠 Mock KC API: Processing {num_questions} questions...")
    print(f"⏱️  Estimated processing time: {total_delay:.1f} seconds")
    
    # Sleep to simulate processing
    time.sleep(total_delay)
    num = random.random()
    print("Random number: ", num)
    if num > .75:
        assert(False)
    
    
    # Path to your existing CSV file with KC results
    # Put your CSV file in the project root or media folder
    mock_csv_path = os.path.join(settings.BASE_DIR, 'mock_kc_results.csv')
    
    # Alternative: if you put it in media folder
    # mock_csv_path = os.path.join(settings.MEDIA_ROOT, 'mock_kc_results.csv')
    
    if not os.path.exists(mock_csv_path):
        raise FileNotFoundError(f"Mock CSV file not found at: {mock_csv_path}")
    # Read your existing CSV file
    df = pd.read_csv(mock_csv_path)
    
    # Convert to the expected format (list of dictionaries)
    mock_results = df.to_dict('records')
    
    # Return in the expected API response format
    return {
        'data': mock_results,
        'metadata': {
            'total_questions': len(mock_results),
            'processing_time': 'mocked',
            'source': 'mock_csv_file'
        }
    }


def save_jsonl_file(data, task_id):
    """Save data as JSONL file for processing records"""
    filename = f'questions_{task_id}.jsonl'
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as temp_file:
        for item in data:
            temp_file.write(json.dumps(item) + '\n')
        temp_path = temp_file.name
    
    # Save to Django storage
    with open(temp_path, 'rb') as f:
        file_content = ContentFile(f.read())
        saved_path = default_storage.save(f'processed/{filename}', file_content)
    
    # Clean up temp file
    os.unlink(temp_path)
    
    return saved_path

def save_results_to_csv(kc_results, task_id):
    """Save KC results to CSV file"""
    # Assuming kc_results contains the processed data with KC information
    df = pd.DataFrame(kc_results.get('data', []))
    
    # Create filename
    filename = f'kc_results_{task_id}.csv'
    
    # Save to temporary file first
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
        df.to_csv(temp_file, index=False)
        temp_path = temp_file.name
    
    # Save to Django storage
    with open(temp_path, 'rb') as f:
        file_content = ContentFile(f.read())
        saved_path = default_storage.save(f'results/{filename}', file_content)
    
    # Clean up temp file
    os.unlink(temp_path)
    
    return saved_path