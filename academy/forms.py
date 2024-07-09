from django import forms
from .models import Training
from django import forms
from django.contrib.auth import get_user_model
from .models import Training
from core.models import Job

User = get_user_model()

class TrainingForm(forms.ModelForm):
    class Meta:
        model = Training
        fields = ['job', 'title', 'texts', 'pdf_document', 'video_url']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Filter the jobs based on the current client
        if user:
            client_profile = user.profile
            client_jobs = Job.objects.filter(client=client_profile)
            self.fields['job'].queryset = client_jobs