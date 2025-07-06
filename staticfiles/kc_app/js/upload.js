"use strict"

document.addEventListener('DOMContentLoaded', function() {
    const fileUploadArea = document.getElementById('fileUploadArea');
    const fileInput = document.getElementById('id_uploaded_file');
    const uploadPlaceholder = document.getElementById('uploadPlaceholder');
    const fileInfo = document.getElementById('fileInfo');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const removeFileBtn = document.getElementById('removeFileBtn');
    const submitBtn = document.getElementById('submitBtn');
    const errorAlert = document.getElementById('errorAlert');
    const errorMessage = document.getElementById('errorMessage');

    // Handle file selection (both click and drag-drop)
    function handleFileSelect(file) {
        if (!file) return;

        // Validate file type
        const allowedTypes = ['.csv', '.xlsx', '.xls', '.json', '.jsonl'];
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!allowedTypes.includes(fileExtension)) {
            showError('Please select a valid file format (CSV, Excel, JSON, or JSONL)');
            return;
        }

        // Update UI to show file info
        fileName.textContent = file.name;
        fileSize.textContent = `Size: ${(file.size / (1024 * 1024)).toFixed(2)} MB`;
        
        uploadPlaceholder.classList.add('hide');
        fileInfo.classList.add('show');
        fileUploadArea.classList.add('has-file');
        
        hideError();
        
        console.log('File selected:', file.name, 'Size:', file.size);
    }

    // Handle file removal
    function removeFile() {
        fileInput.value = '';
        uploadPlaceholder.classList.remove('hide');
        fileInfo.classList.remove('show');
        fileUploadArea.classList.remove('has-file');
        hideError();
    }

    // Show error message
    function showError(message) {
        errorMessage.textContent = message;
        errorAlert.style.display = 'block';
    }

    // Hide error message
    function hideError() {
        errorAlert.style.display = 'none';
    }

    // Click to upload
    fileUploadArea.addEventListener('click', function(e) {
        if (e.target !== removeFileBtn && !removeFileBtn.contains(e.target)) {
            fileInput.click();
        }
    });

    // File input change handler
    fileInput.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    // Remove file button
    removeFileBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        removeFile();
    });

    // Drag and drop handlers
    fileUploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        fileUploadArea.classList.add('dragover');
    });

    fileUploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        fileUploadArea.classList.remove('dragover');
    });

    fileUploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        fileUploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            // Manually set the files to the input
            fileInput.files = files;
            handleFileSelect(files[0]);
        }
    });

    // Form submission handler
    document.getElementById('uploadForm').addEventListener('submit', function(e) {
        
        // Check if file is selected
        if (!fileInput.files || fileInput.files.length === 0) {
            showError('Please select a file to upload');
            return;
        }

        // Check if file format is selected
        // const fileFormat = document.querySelector('input[name="file_format"]:checked');
        // if (!fileFormat) {
        //     showError('Please select a file format');
        //     return;
        // }

        // If we get here, everything is valid
        alert('Form is ready to submit! File: ' + fileInput.files[0].name);
        
        // In real Django app, remove the e.preventDefault() above to allow actual submission
    });
});