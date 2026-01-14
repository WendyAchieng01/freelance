from cloudinary.forms import CloudinaryFileField
from .models import ContactUs
from django import forms
from django.contrib.auth.forms import UserChangeForm, SetPasswordForm
from django.contrib.auth.models import User
from .models import Profile, Skill, Language

class FreelancerForm(forms.Form):
    # Required Personal Information
    name = forms.CharField(
        label="First & Last Name*", 
        max_length=100, 
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        label="Email Address*", 
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    phone_number = forms.CharField(
        label="Phone Number*", 
        max_length=20, 
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    # Required Professional Information
    experience_years = forms.IntegerField(
        label="Years of Experience*",
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    hourly_rate = forms.DecimalField(
        label="Hourly Rate (USD)*",
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    languages = forms.ModelMultipleChoiceField(
        queryset=Language.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Languages Spoken*",
        required=True,
    )
    
    # Optional Fields
    photo = forms.ImageField(required=False, label="Profile Photo")
    id_number = forms.CharField(
        label="ID Number (Optional)", 
        max_length=20, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    location = forms.CharField(
        label="Current Location (Optional)", 
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    pay_id = forms.ChoiceField(
        label="Payment Method", 
        required=False,
        choices=(('M-Pesa', 'M-Pesa'), ('Binance', 'Binance')), 
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Skills*"
    )
    portfolio_link = forms.URLField(
        label="Portfolio URL (Optional)",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    availability = forms.ChoiceField(
        label="Availability",
        required=False,
        choices=(
            ('full_time', 'Full Time'),
            ('part_time', 'Part Time'),
            ('weekends', 'Weekends Only'),
            ('custom', 'Custom Schedule')
        ),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def save(self, user=None):
        # Save basic user information
        data = self.cleaned_data
        
        # Create or update FreelancerProfile
        freelancer_profile_data = {
            'portfolio_link': data.get('portfolio_link', ''),
            'experience_years': data.get('experience_years', 0),
            'hourly_rate': data.get('hourly_rate', 0),
            'availability': data.get('availability', '')
        }
        
        if user and hasattr(user, 'freelancerprofile'):
            profile = user.freelancerprofile
            for key, value in freelancer_profile_data.items():
                setattr(profile, key, value)
            profile.save()
        else:
            # Handle creating new profile if needed
            # This depends on your user model structure
            pass
        
        # Handle M2M relationships
        if hasattr(user, 'freelancerprofile'):
            profile = user.freelancerprofile
            profile.skills.set(data.get('skills', []))
            profile.languages.set(data.get('languages', []))
        
        return user


class ClientForm(forms.Form):
    # Required Personal/Company Information
    company_name = forms.CharField(
        label="",
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name/Company Name*'})
    )
    email = forms.EmailField(
        label="",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Email Address*'})
    )
    phone_number = forms.CharField(
        label="",
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number*'})
    )
    
    industry = forms.ChoiceField(
        label="",
        choices=(
            ('technology', 'Technology'),
            ('finance', 'Finance'),
            ('healthcare', 'Healthcare'),
            ('education', 'Education'),
            ('retail', 'Retail'),
            ('manufacturing', 'Manufacturing'),
            ('entertainment', 'Entertainment'),
            ('marketing', 'Marketing'),
            ('consulting', 'Consulting'),
            ('non_profit', 'Non-Profit'),
            ('government', 'Government'),
            ('legal', 'Legal Services'),
            ('real_estate', 'Real Estate'),
            ('hospitality', 'Hospitality'),
            ('transportation', 'Transportation'),
            ('agriculture', 'Agriculture'),
            ('energy', 'Energy'),
            ('telecom', 'Telecommunications'),
            ('media', 'Media'),
            ('other', 'Other'),
        ),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    languages = forms.ModelMultipleChoiceField(
        label="Languages Spoken*",
        queryset=Language.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True, 
    )
    
    # Optional Fields
    location = forms.CharField(
        label="",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Current Location (Optional)'})
    )
    pay_id = forms.ChoiceField(
        label="",
        required=False,
        choices=(('M-Pesa', 'M-Pesa'), ('Binance', 'Binance')),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    company_website = forms.URLField(
        label="",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': ''})
    )
    project_budget = forms.DecimalField(
        label="Budget*",
        min_value=0,
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Project Budget (USD)'})
    )
    preferred_freelancer_level = forms.ChoiceField(
        label="",
        required=False,
        choices=(
            ('entry', 'Entry Level'),
            ('intermediate', 'Intermediate'),
            ('expert', 'Expert')
        ),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def save(self, user=None):
        # Save basic user information
        data = self.cleaned_data
        
        # Create or update ClientProfile
        client_profile_data = {
            'company_name': data.get('company_name', ''),
            'company_website': data.get('company_website', ''),
            'industry': data.get('industry', ''),
            'project_budget': data.get('project_budget', 0),
            'preferred_freelancer_level': data.get('preferred_freelancer_level', '')
        }
        
        if user and hasattr(user, 'clientprofile'):
            profile = user.clientprofile
            for key, value in client_profile_data.items():
                setattr(profile, key, value)
            profile.save()
        else:
            # Handle creating new profile if needed
            # This depends on your user model structure
            pass
        
        # Handle M2M relationships
        if hasattr(user, 'clientprofile'):
            profile = user.clientprofile
            profile.languages.set(data.get('languages', []))
        
        return user
    

class ChangePasswordForm(SetPasswordForm):
	class Meta:
		model = User
		fields = ['new_password1', 'new_password2']
	
	def __init__(self, *args, **kwargs):
		super(ChangePasswordForm, self).__init__(*args, **kwargs)

		self.fields['new_password1'].widget.attrs['class'] = 'form-control'
		self.fields['new_password1'].widget.attrs['placeholder'] = 'Password'
		self.fields['new_password1'].label = ''
		self.fields['new_password1'].help_text = '<ul class="form-text text-muted small"><li>Your password can\'t be too similar to your other personal information.</li><li>Your password must contain at least 8 characters.</li><li>Your password can\'t be a commonly used password.</li><li>Your password can\'t be entirely numeric.</li></ul>'

		self.fields['new_password2'].widget.attrs['class'] = 'form-control'
		self.fields['new_password2'].widget.attrs['placeholder'] = 'Confirm Password'
		self.fields['new_password2'].label = ''
		self.fields['new_password2'].help_text = '<span class="form-text text-muted"><small>Enter the same password as before, for verification.</small></span>'
            

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['phone', 'location', 'bio', 'profile_pic', 'pay_id', 'id_card']


class ContactUsAdminForm(forms.ModelForm):
    attachment = CloudinaryFileField(
        required=False,
        options={
            "folder": "freelance/contactus/",
            "resource_type": "raw"
        }
    )

    class Meta:
        model = ContactUs
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        if "timestamp" in self.fields:
            cleaned_data.pop("timestamp", None)
        return cleaned_data


class SkillAdminForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = '__all__'
        widgets = {
            'name': forms.Select(attrs={
                'class': 'admin-autocomplete',
                'data-placeholder': 'Start typing to filter skills...',
                'style': 'width: 100%;',
            }),
        }
