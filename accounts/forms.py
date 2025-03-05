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
        label="Languages Spoken",
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
    pay_id_no = forms.CharField(
        label="Pay ID Number", 
        max_length=20, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Skills"
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
            ('marketing', 'Marketing'),
            ('finance', 'Finance'),
            ('healthcare', 'Healthcare'),
            ('education', 'Education'),
            ('retail', 'Retail'),
            ('other', 'Other')
        ),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    languages = forms.ModelMultipleChoiceField(
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
    pay_id_no = forms.CharField(
        label="",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Pay ID Number (Optional)'})
    )
    company_website = forms.URLField(
        label="",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Website (Optional)'})
    )
    project_budget = forms.DecimalField(
        label="",
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
    
class UpdateUserForm(UserChangeForm):
	password = None
	email = forms.EmailField(label="", widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'Email Address'}), required=False)
	first_name = forms.CharField(label="", max_length=100, widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'First Name'}), required=False)
	last_name = forms.CharField(label="", max_length=100, widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'Last Name'}), required=False)

	class Meta:
		model = User
		fields = ('username', 'first_name', 'last_name', 'email')

	def __init__(self, *args, **kwargs):
		super(UpdateUserForm, self).__init__(*args, **kwargs)

		self.fields['username'].widget.attrs['class'] = 'form-control'
		self.fields['username'].widget.attrs['placeholder'] = 'User Name'
		self.fields['username'].label = ''
		self.fields['username'].help_text = '<span class="form-text text-muted"><small>Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.</small></span>'


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
            

class UserInfoForm(forms.ModelForm):
    pay_id = forms.ChoiceField(label="", choices=(('M-Pesa', 'M-Pesa'), ('Binance', 'Binance')), widget=forms.Select(attrs={'class':'form-control'}))
    pay_id_no = forms.CharField(label="", max_length=20, widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'Pay ID Number'}))
    profile_pic = forms.ImageField(label="Profile Picture", required=False, widget=forms.FileInput(attrs={'class': 'form-control'}))

    def clean_profile_pic(self):
            profile_pic = self.cleaned_data.get('profile_pic')
            if profile_pic and not profile_pic.name:
                self.add_error('profile_pic', 'Please select a profile picture.')
            return profile_pic

    class Meta:
        model = Profile
        fields = ('phone', 'location', 'bio', 'profile_pic', 'pay_id', 'pay_id_no', 'id_card')
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Location'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Bio'}),
            'id_card': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'National ID'}),
        }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['phone', 'location', 'bio', 'profile_pic', 'pay_id', 'pay_id_no', 'id_card']

