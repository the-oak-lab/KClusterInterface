document.addEventListener('DOMContentLoaded', function() {
    const taskId = JSON.parse(document.getElementById('task-id').textContent);
    const currentStatus = JSON.parse(document.getElementById('task-status').textContent);
    
    function updateStatus() {
        fetch(`/ajax/task/${taskId}/status/`)
            .then(response => response.json())
            .then(data => {
                const statusContainer = document.getElementById('statusContainer');
                let alertClass, icon, message;
                
                switch(data.status) {
                    case 'completed':
                        alertClass = 'alert-success';
                        icon = 'fas fa-check-circle';
                        message = 'Completed! Your KC analysis is ready.';
                        // Reload page to show download buttons
                        setTimeout(() => location.reload(), 1000);
                        break;
                    case 'processing':
                        alertClass = 'alert-warning';
                        icon = 'fas fa-spinner fa-spin';
                        message = 'Processing... Your file is being analyzed.';
                        break;
                    case 'queued':
                        alertClass = 'alert-info';
                        message = 'Queued: Your task is waiting to be processed.';
                        break;
                    case 'converted':
                        alertClass = 'alert-info';
                        message = 'Converted: Your file was converted successfully and will be queued for analysis.';
                        break;
                    case 'failed':
                        alertClass = 'alert-danger';
                        icon = 'fas fa-exclamation-triangle';
                        message = 'Failed: An error occurred during processing.';
                        // Reload page to show error details
                        setTimeout(() => location.reload(), 1000);
                        break;
                    default:
                        alertClass = 'alert-info';
                        icon = 'fas fa-clock';
                        message = 'Uploaded: Your file was uploaded successfully';
                }
                
                statusContainer.innerHTML = `
                    <div class="alert ${alertClass}">
                        <i class="${icon} me-2"></i>
                        <strong>${message}</strong>
                    </div>
                `;
            })
            .catch(error => console.error('Error updating status:', error));
    }
    
    // Check if task is still processing
    if (currentStatus === 'processing' || currentStatus === 'queued' || currentStatus === "uploaded" || currentStatus === "converted") {
        // Update every 5 seconds
        const interval = setInterval(() => {
            updateStatus();
        }, 5000);
        
        // Stop polling after 10 minutes
        setTimeout(() => {
            clearInterval(interval);
        }, 600000);
    }
});