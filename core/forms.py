from django import forms
from .models import Job, JobAttempt, Response

class ResponseForm(forms.ModelForm):
    class Meta:
        model = Response
        fields = []

    def __init__(self, *args, **kwargs):
        job_category = kwargs.pop('job_category', None)
        super().__init__(*args, **kwargs)

        if job_category == 'data_entry':
            self.fields['tools_required'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'Enter required tools or platforms'}),
                required=True,
                label='Tools and Platforms'
            )
            self.fields['platforms_used'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'List the platforms you are proficient with'}),
                required=True,
                label='Platforms Used'
            )
        elif job_category == 'translation':
            self.fields['source_language'] = forms.CharField(
                max_length=50, required=True, label='Source Language'
            )
            self.fields['target_language'] = forms.CharField(
                max_length=50, required=True, label='Target Language'
            )
        elif job_category == 'transcription':
            self.fields['software_used'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'List transcription tools or software you use'}),
                required=False,
                label='Transcription Software'
            )
            self.fields['languages_known'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'Specify the languages you can transcribe'}),
                required=True,
                label='Languages Known'
            )
        elif job_category == 'graphics':
            self.fields['design_tools'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'Specify tools like Photoshop, Illustrator'}),
                required=True,
                label='Design Tools'
            )
            self.fields['portfolio_link'] = forms.URLField(
                required=False, label='Portfolio Link',
                help_text='Provide a link to your portfolio if available'
            )
        elif job_category == 'writing':
            self.fields['writing_style'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'Specify the type of writing: blogs, articles, copywriting'}),
                required=True,
                label='Writing Style'
            )
            self.fields['sample_work'] = forms.FileField(
                required=False, label='Sample Work',
                help_text='Attach sample work if available'
            )
        elif job_category == 'web_dev':
            self.fields['programming_languages'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'List programming languages you are proficient in'}),
                required=True,
                label='Programming Languages'
            )
            self.fields['frameworks_used'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'Specify frameworks you have experience with'}),
                required=True,
                label='Frameworks'
            )
        elif job_category == 'project_mgmt':
            self.fields['project_experience'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'Describe your project management experience'}),
                required=True,
                label='Project Management Experience'
            )
            self.fields['certifications'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'List certifications like PMP, Agile, etc.'}),
                required=False,
                label='Certifications'
            )
        elif job_category == 'testing':
            self.fields['testing_tools'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'Mention tools like Selenium, JIRA'}),
                required=True,
                label='Testing Tools'
            )
            self.fields['testing_methodologies'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'List testing methodologies you follow'}),
                required=False,
                label='Testing Methodologies'
            )
        elif job_category == 'virtual_assist':
            self.fields['tasks'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'List tasks you can handle, e.g., scheduling, data entry'}),
                required=False,
                label='Tasks You Can Handle'
            )
        elif job_category == 'social_media':
            self.fields['platforms_managed'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'List social media platforms you manage'}),
                required=True,
                label='Platforms Managed'
            )
            self.fields['campaign_experience'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'Describe your experience with campaigns'}),
                required=False,
                label='Campaign Experience'
            )
        elif job_category == 'ai_training':
            self.fields['tools_used'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'Specify tools like TensorFlow, PyTorch'}),
                required=True,
                label='AI Tools Used'
            )
            self.fields['projects'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'Describe AI training projects you have worked on'}),
                required=False,
                label='Projects'
            )
        else:
            self.fields['extra_data'] = forms.JSONField(
                widget=forms.Textarea(attrs={'placeholder': 'Provide any additional details'}),
                required=False,
                help_text="Specify any other relevant information."
            )

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Extract extra data from form fields
        extra_data = {}
        for field_name, field in self.fields.items():
            if field_name not in ['user', 'job', 'submitted_at']:
                extra_data[field_name] = self.cleaned_data.get(field_name)

        instance.extra_data = extra_data

        if commit:
            instance.save()
        return instance
            

class CreateJobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['title', 'category', 'description', 'price', 'deadline_date', 'max_freelancers']
        widgets = {
            'deadline_date': forms.DateInput(attrs={'type': 'date'}),
            'category': forms.Select(choices=Job.CATEGORY_CHOICES)
        }

class JobAttemptForm(forms.ModelForm):
    class Meta:
        model = JobAttempt
        fields = ['freelancer',]


