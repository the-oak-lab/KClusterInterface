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
    # FILE_FORMAT_CHOICES = [
    #     ('csv', 'CSV'),
    #     ('excel', 'Excel (XLSX/XLS)'),
    #     ('json', 'JSON'),
    #     ('jsonl', 'JSONL (JSON Lines)'),
    # ]
    
    # file_format = forms.ChoiceField(
    #     choices=FILE_FORMAT_CHOICES,
    #     widget=forms.RadioSelect,
    #     required=True,
    #     help_text="Select the format of your uploaded file"
    # )
    
    class Meta:
        model = TaskSubmission
        fields = ['uploaded_file']
        widgets = {
            'uploaded_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.csv,.xlsx,.xls,.json,.jsonl'
            })
        }
        help_texts = {
            'uploaded_file': 'Upload a CSV, Excel, JSON, or JSONL file containing your questions'
        }
