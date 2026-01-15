from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import TeacherUser, TaskSubmission

class TeacherRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    institution = forms.CharField(max_length=200, required=False)
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            TeacherUser.objects.create(
                user=user,
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                email=self.cleaned_data['email'],
                institution=self.cleaned_data.get('institution', '')
            )
        return user

class FileUploadForm(forms.ModelForm):
    # TASK_TYPE_CHOICES = [
    #     ('', '-- Select an option --'),
    #     ('questions-to-kcs', 'Upload questions and receive KCs'),
    #     ('kcs-to-questions', 'Upload Learning Objectives and receive questions'),
    # ]
    
    # task_type = forms.ChoiceField(
    #     choices=TASK_TYPE_CHOICES,
    #     required=True,
    #     widget=forms.Select(attrs={
    #         'class': 'form-select form-select-lg',
    #         'id': 'id_task_type'
    #     }),
    #     label='What would you like to do?'
    # )
    
    class Meta:
        model = TaskSubmission
        fields = ['task_type', 'uploaded_file']
        widgets = {
            'task_type': forms.Select(attrs={
            'class': 'form-select form-select-lg',
            'id': 'id_task_type',
            }),
            'uploaded_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.csv,.xlsx,.xls,.json,.jsonl'
            })
        }
        labels = {
            'task_type': 'What would you like to do?',
        }

        help_texts = {
            'uploaded_file': 'Upload a CSV, Excel, JSON, or JSONL file containing your questions'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Check if we have POST data with an task_type
        if args and 'task_type' in args[0]:
            task_type = args[0].get('task_type')
            self._customize_for_mode(task_type)
    
    def _customize_for_mode(self, task_type):
        """Customize the form based on the selected upload mode"""
        if task_type == 'questions-to-kcs':
            # Questions mode - keep defaults
            self.fields['uploaded_file'].widget.attrs['accept'] = '.csv,.xlsx,.xls,.json,.jsonl'
            self.fields['uploaded_file'].help_text = 'Upload a CSV, Excel, JSON, or JSONL file containing your questions'
            
        elif task_type == 'kcs-to-questions':
            # KCs mode - customize for KC files
            self.fields['uploaded_file'].widget.attrs['accept'] = '.txt'
            self.fields['uploaded_file'].help_text = 'Upload a txt file containing your Learning Objectives (LOs)'
    
    def clean(self):
        cleaned_data = super().clean()
        task_type = cleaned_data.get('task_type')
        uploaded_file = cleaned_data.get('uploaded_file')
        
        if task_type and uploaded_file:
            file_extension = uploaded_file.name.split('.')[-1].lower()
            print("TASK TYPE IS: ", task_type)
            
            # Validate file types based on mode
            if task_type == 'questions-to-kcs':
                allowed_extensions = ['csv', 'xlsx', 'xls', 'json', 'jsonl']
                if file_extension not in allowed_extensions:
                    raise forms.ValidationError(
                        f'Invalid file type for questions upload. '
                        f'Please upload a CSV, Excel, JSON, or JSONL file.'
                    )
                    
            elif task_type == 'kcs-to-questions':
                allowed_extensions = ['txt']
                if file_extension not in allowed_extensions:
                    raise forms.ValidationError(
                        f'Invalid file type for learning objective upload. '
                        f'Please upload a .txt file.'
                    )
        
        return cleaned_data
