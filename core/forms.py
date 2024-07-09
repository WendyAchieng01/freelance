from django import forms
from .models import Job, JobAttempt, Response

class ResponseForm(forms.ModelForm):
    class Meta:
        model = Response
        fields = ('email', 'password', 'security_answer', 'number_of_items', 'phone_number', 'device_used', 'screenshot')

class CreateJobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['title', 'description', 'price', 'deadline_date', 'max_freelancers']
        widgets = {
            'deadline_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        }

class JobAttemptForm(forms.ModelForm):
    class Meta:
        model = JobAttempt
        fields = ['freelancer',]