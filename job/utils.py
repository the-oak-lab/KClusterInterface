import json
import pandas as pd
import requests
from django.conf import settings
import os
from typing import List, Dict, Any, Union

class FileValidationError(Exception):
    """Custom exception for file validation errors"""
    pass

def validate_required_columns(data: List[Dict], required_columns: List[str], file_format: str):
    """Validate that required columns exist in the data"""
    if not data:
        raise FileValidationError(f"File is empty or contains no valid data")
    
    # Check first record for required columns
    first_record = data[0]
    missing_columns = []
    
    for col in required_columns:
        if col not in first_record:
            missing_columns.append(col)
    
    if missing_columns:
        raise FileValidationError(
            f"{file_format.upper()} file missing required columns: {', '.join(missing_columns)}. "
            f"Required columns are: {', '.join(required_columns)}"
        )

def validate_json_structure(data: List[Dict]):
    """Validate JSON/JSONL specific structure requirements"""
    for i, record in enumerate(data):
        # Check if 'question' field exists and is properly structured
        if 'question' not in record:
            raise FileValidationError(f"Record {i+1}: Missing required 'question' field")
        
        question_data = record['question']
        
        # Question should be an object with 'stem' field
        if not isinstance(question_data, dict):
            raise FileValidationError(
                f"Record {i+1}: 'question' field must be an object, not {type(question_data).__name__}"
            )
        
        if 'stem' not in question_data:
            raise FileValidationError(f"Record {i+1}: 'question' object missing required 'stem' field")
        
        # For Multiple Choice questions, validate choices structure
        if record.get('type') == 'Multiple Choice':
            if 'choices' not in question_data:
                raise FileValidationError(
                    f"Record {i+1}: Multiple Choice question missing 'choices' array"
                )
            
            choices = question_data['choices']
            if not isinstance(choices, list) or len(choices) == 0:
                raise FileValidationError(
                    f"Record {i+1}: 'choices' must be a non-empty array for Multiple Choice questions"
                )
            elif len(choices) == 1:
                raise FileValidationError(
                    f"Record {i+1}: 'choices' for Multiple Choice questions must have more than one option"
                )
            
            # Validate choice structure
            for j, choice in enumerate(choices):
                if not isinstance(choice, dict):
                    raise FileValidationError(
                        f"Record {i+1}, Choice {j+1}: Each choice must be an object"
                    )
                if 'label' not in choice or 'text' not in choice:
                    raise FileValidationError(
                        f"Record {i+1}, Choice {j+1}: Each choice must have 'label' and 'text' fields"
                    )

def validate_csv_excel_structure(data: List[Dict], file_format: str):
    """Validate CSV/Excel specific structure requirements"""
    for i, record in enumerate(data):
        # Check for choice columns pattern for Multiple Choice questions
        if record.get('type') == 'Multiple Choice':
            choice_columns = [col for col in record.keys() if col.startswith('choice_')]
            if not choice_columns:
                raise FileValidationError(
                    f"Record {i+1}: Multiple Choice question missing choice columns (columns starting with 'choice_')"
                )
            
            # Check that at least one choice has content
            has_choices = any(record.get(col) and str(record.get(col)).strip() for col in choice_columns)
            if not has_choices:
                raise FileValidationError(
                    f"Record {i+1}: Multiple Choice question has no populated choice columns"
                )

def transform_csv_excel_to_json_structure(data: List[Dict]) -> List[Dict]:
    """Transform flat CSV/Excel structure to nested JSON structure"""
    import pandas as pd
    import numpy as np
    
    transformed_data = []
    
    for record in data:
        # Create new record with transformed structure
        new_record = {}
        
        # Copy basic fields
        new_record['id'] = record['id']
        new_record['type'] = record['type']
        
        # Transform question field
        question_obj = {
            'stem': record['question']
        }
        
        # Handle Multiple Choice questions
        if record.get('type') == 'Multiple Choice':
            choices = []
            choice_columns = [col for col in record.keys() if col.startswith('choice_')]
            choice_columns.sort()  # Ensure consistent ordering
            
            for col in choice_columns:
                choice_value = record.get(col)
                # Only include non-empty choices (skip NaN, None, empty strings)
                if (choice_value is not None and 
                    not (isinstance(choice_value, float) and pd.isna(choice_value)) and
                    str(choice_value).strip()):
                    
                    # Extract label from column name (e.g., 'choice_a' -> 'a')
                    label = col.replace('choice_', '')
                    choices.append({
                        'label': label,
                        'text': str(choice_value).strip()
                    })
            
            if choices:  # Only add choices if we have any
                question_obj['choices'] = choices
        
        new_record['question'] = question_obj
        
        # Copy all other fields (excluding choice columns and the original question)
        excluded_fields = {'question'} | {col for col in record.keys() if col.startswith('choice_')}
        for key, value in record.items():
            if key not in excluded_fields and key not in new_record:
                # Skip NaN values
                if not (isinstance(value, float) and pd.isna(value)):
                    new_record[key] = value
        
        transformed_data.append(new_record)
    
    return transformed_data

def validate_common_requirements(data: List[Dict]):
    """Validate requirements common to all formats"""
    for i, record in enumerate(data):
        # Validate required fields exist and are not empty
        if not record.get('id') or str(record.get('id')).strip() == '':
            raise FileValidationError(f"Record {i+1}: 'id' field is required and cannot be empty")
        
        if not record.get('type') or str(record.get('type')).strip() == '':
            raise FileValidationError(f"Record {i+1}: 'type' field is required and cannot be empty")
        
        # For CSV/Excel, question should be a string
        # For JSON/JSONL, question should be an object (validated separately)
        question_field = record.get('question')
        if not question_field:
            raise FileValidationError(f"Record {i+1}: 'question' field is required and cannot be empty")

def convert_file_to_jsonl_data(file_path: str) -> List[Dict[str, Any]]:
    """
    Convert uploaded file to JSONL-ready data with validation against format requirements
    
    Args:
        file_path: Path to the uploaded file
        
    Returns:
        List of dictionaries ready for JSONL conversion
        
    Raises:
        FileValidationError: If file doesn't meet format requirements
        ValueError: If file format is unsupported
    """
    if not os.path.exists(file_path):
        raise FileValidationError(f"File not found: {file_path}")
    
    file_extension = file_path.split(".")[-1].lower()
    
    # Map file extensions to formats
    format_mapping = {
        'jsonl': 'jsonl',
        'json': 'json', 
        'csv': 'csv',
        'xlsx': 'excel',
        'xls': 'excel'
    }
    
    if file_extension not in format_mapping:
        raise ValueError(f"Unsupported file format: {file_extension}")
    
    file_format = format_mapping[file_extension]
    required_columns = ['id', 'type', 'question']
    
    try:
        # Load data based on format
        if file_format == 'jsonl':
            data = []
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:  # Skip empty lines
                        try:
                            data.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            raise FileValidationError(f"Invalid JSON on line {line_num}: {str(e)}")
        
        elif file_format == 'json':
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    json_data = json.load(f)
                except json.JSONDecodeError as e:
                    raise FileValidationError(f"Invalid JSON format: {str(e)}")
                
                # Ensure it's a list of objects
                if isinstance(json_data, dict):
                    data = [json_data]  # Single object -> list
                elif isinstance(json_data, list):
                    data = json_data    # Already a list
                else:
                    raise FileValidationError("JSON root element must be an object or array of objects")
        
        elif file_format == 'csv':
            try:
                # Read CSV with error handling
                df = pd.read_csv(file_path, encoding='utf-8')
                if df.empty:
                    raise FileValidationError("CSV file is empty")
                
                # Strip whitespace from column names
                df.columns = df.columns.str.strip()
                data = df.to_dict('records')
                
            except pd.errors.EmptyDataError:
                raise FileValidationError("CSV file is empty or contains no data")
            except pd.errors.ParserError as e:
                raise FileValidationError(f"CSV parsing error: {str(e)}")
            except UnicodeDecodeError:
                # Try with different encoding
                try:
                    df = pd.read_csv(file_path, encoding='latin-1')
                    df.columns = df.columns.str.strip()
                    data = df.to_dict('records')
                except Exception as e:
                    raise FileValidationError(f"CSV encoding error: {str(e)}")
        
        elif file_format == 'excel':
            try:
                # Read only the first sheet
                df = pd.read_excel(file_path, sheet_name=0)
                if df.empty:
                    raise FileValidationError("Excel file is empty")
                
                # Strip whitespace from column names
                df.columns = df.columns.str.strip()
                data = df.to_dict('records')
                
            except Exception as e:
                raise FileValidationError(f"Excel reading error: {str(e)}")
        
        # Validate common requirements
        validate_common_requirements(data)
        
        # Validate required columns exist
        validate_required_columns(data, required_columns, file_format)
        
        # Format-specific validation
        if file_format in ['json', 'jsonl']:
            validate_json_structure(data)
        elif file_format in ['csv', 'excel']:
            validate_csv_excel_structure(data, file_format)
            # Transform CSV/Excel data to proper JSON structure
            data = transform_csv_excel_to_json_structure(data)
        
        return data
        
    except FileValidationError:
        # Re-raise validation errors as-is
        raise
    except Exception as e:
        # Convert other exceptions to validation errors with context
        raise FileValidationError(f"Error processing {file_format.upper()} file: {str(e)}")
    

def call_kc_api_old(jsonl_data):
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
    total_delay = min(total_delay, 1000)
    
    print(f"🧠 Mock KC API: Processing {num_questions} questions...")
    print(f"⏱️  Estimated processing time: {total_delay:.1f} seconds")
    
    # Sleep to simulate processing
    # DELETE THIS IN PRODUCTION
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


def save_jsonl_file(data, task_id, output_dir="/tmp/"):
    """Save data as JSONL file for processing records"""
    # Create full file path
    filename = f'questions_{task_id}.jsonl'
    jsonl_path = os.path.join(output_dir, filename)
    
    # Save directly to the path
    with open(jsonl_path, 'w') as f:
        for item in data:
            f.write(json.dumps(item) + '\n')
    
    return jsonl_path

def save_results_to_csv(kc_results, task_id, output_dir="/tmp/"):
    """Save KC results to CSV file in specified directory"""
    # Create DataFrame from results
    df = pd.DataFrame(kc_results.get('data', []))
    
    # Create full file path
    filename = f'kc_results_{task_id}.csv'
    csv_path = os.path.join(output_dir, filename)
    
    # Save directly to the path
    df.to_csv(csv_path, index=False)
    
    return csv_path