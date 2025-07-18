import os
from django import forms
from .models import Job, Response, Review,JobCategory

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
                max_length=50, 
                required=True, 
                label='Source Language',
                widget=forms.TextInput(attrs={'placeholder': 'e.g., English, Spanish, French'})
            )
            self.fields['target_language'] = forms.CharField(
                max_length=50, 
                required=True, 
                label='Target Language',
                widget=forms.TextInput(attrs={'placeholder': 'e.g., German, Chinese, Japanese'})
            )
            self.fields['specialized_areas'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'Specify areas of expertise: legal, medical, technical, etc.'}),
                required=False,
                label='Specialized Areas'
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
                required=False, 
                label='Portfolio Link',
                help_text='Provide a link to your portfolio if available',
                widget=forms.URLInput(attrs={'placeholder': 'https://your-portfolio-site.com'})
            )
        elif job_category == 'writing':
            self.fields['writing_style'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'Specify the type of writing: blogs, articles, copywriting, etc'}),
                required=True,
                label='Writing Style'
            )
            self.fields['sample_work'] = forms.FileField(
                required=False, 
                label='Sample Work',
                help_text='Attach sample work if available (PDF, DOCX, or TXT format)',
                widget=forms.ClearableFileInput(attrs={
                    'accept': '.pdf,.docx,.txt'
                })
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
            self.fields['development_tools'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'List development tools, IDEs, or version control systems you use'}),
                required=False,
                label='Development Tools'
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
            self.fields['tools_experience'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'List tools you are familiar with (e.g., MS Office, CRM software)'}),
                required=False,
                label='Tools Experience'
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
            self.fields['analytics_tools'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'List analytics tools you are proficient with'}),
                required=False,
                label='Analytics Tools'
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
            self.fields['specialization'] = forms.CharField(
                widget=forms.Textarea(attrs={'placeholder': 'Specify your AI specialization areas (NLP, computer vision, etc.)'}),
                required=False,
                label='Specialization'
            )
        else:
            self.fields['extra_data'] = forms.JSONField(
                widget=forms.Textarea(attrs={'placeholder': 'Provide any additional details in JSON format'}),
                required=False,
                help_text="Specify any other relevant information in JSON format."
            )

    def clean_sample_work(self):
        sample_work = self.cleaned_data.get('sample_work')
        if sample_work:
            # Check file extension to ensure proper file type
            file_ext = os.path.splitext(sample_work.name)[1].lower()
            allowed_extensions = ['.pdf', '.docx', '.txt']
            if file_ext not in allowed_extensions:
                raise forms.ValidationError("Only PDF, DOCX, or TXT files are allowed.")
        return sample_work

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Extract extra data from form fields
        extra_data = {}
        for field_name, field in self.fields.items():
            if field_name not in ['user', 'job', 'submitted_at']:
                # Handle file field separately
                if field_name == 'sample_work' and self.cleaned_data.get(field_name):
                    # Store file name instead of the file object
                    uploaded_file = self.cleaned_data.get(field_name)
                    extra_data[field_name] = {
                        'filename': uploaded_file.name,
                        'content_type': uploaded_file.content_type,
                        'size': uploaded_file.size
                    }
                    
                    # Save the file to appropriate location
                    if hasattr(instance, 'id') and instance.id:
                        # If the instance already has an ID, use it for the filename
                        file_dir = os.path.join('uploads', 'responses', str(instance.id))
                    else:
                        # If no ID yet, create a temporary directory with timestamp
                        import uuid
                        temp_id = uuid.uuid4().hex
                        file_dir = os.path.join('uploads', 'responses', 'temp', temp_id)
                    
                    # Create directory if it doesn't exist
                    os.makedirs(file_dir, exist_ok=True)
                    
                    # Save the file
                    file_path = os.path.join(file_dir, uploaded_file.name)
                    with open(file_path, 'wb+') as destination:
                        for chunk in uploaded_file.chunks():
                            destination.write(chunk)
                    
                    # Store file path in extra_data
                    extra_data[field_name]['path'] = file_path
                else:
                    # Handle all other fields normally
                    extra_data[field_name] = self.cleaned_data.get(field_name)

        instance.extra_data = extra_data

        if commit:
            instance.save()
            
            # If we created a temporary directory for files before saving, move files to final location
            if 'sample_work' in extra_data and 'path' in extra_data['sample_work']:
                if '/temp/' in extra_data['sample_work']['path']:
                    # Get the old path
                    old_path = extra_data['sample_work']['path']
                    
                    # Create new directory with actual instance ID
                    new_dir = os.path.join('uploads', 'responses', str(instance.id))
                    os.makedirs(new_dir, exist_ok=True)
                    
                    # Create new path
                    filename = os.path.basename(old_path)
                    new_path = os.path.join(new_dir, filename)
                    
                    # Move the file
                    import shutil
                    shutil.move(old_path, new_path)
                    
                    # Update the path in extra_data
                    extra_data['sample_work']['path'] = new_path
                    instance.extra_data = extra_data
                    instance.save(update_fields=['extra_data'])
                    
                    # Clean up empty temporary directory if possible
                    temp_dir = os.path.dirname(old_path)
                    if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                        os.rmdir(temp_dir)
        
        return instance

class CreateJobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['title', 'category', 'description', 'price', 'deadline_date', 'max_freelancers']
        widgets = {
            'deadline_date': forms.DateInput(attrs={'type': 'date'}),
            #'category': forms.Select(choices=JobCategory.name)
        }

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 5}),
        }