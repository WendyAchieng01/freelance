from django import forms
from django.contrib.auth.forms import UserChangeForm, SetPasswordForm
from django.contrib.auth.models import User
from .models import Profile


class ClientForm(forms.Form):
    name = forms.CharField(
        label="",
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Input Name'})
    )
    email = forms.EmailField(
        label="",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'})
    )
    phone_number = forms.CharField(
        label="",
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'})
    )
    location = forms.CharField(
        label="",
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Current Location'})
    )
    pay_id = forms.ChoiceField(
        label="",
        choices=(('M-Pesa', 'M-Pesa'), ('Binance', 'Binance')),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    pay_id_no = forms.CharField(
        label="",
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Pay ID Number'})
    )

class FreelancerForm(forms.Form):
    name = forms.CharField(label="", max_length=100, widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'First & Last Name'}))
    photo = forms.ImageField()
    id_number = forms.CharField(label="", max_length=20, widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'ID Number'}))
    phone_number = forms.CharField(label="", max_length=20, widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'Phone Number'}))
    device = forms.CharField(label="", max_length=100, widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'Device Used'}))
    location = forms.CharField(label="", max_length=100, widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'Current Location'}))
    email = forms.EmailField(label="", widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'Email Address'}), required=False)
    pay_id = forms.ChoiceField(label="", choices=(('M-Pesa', 'M-Pesa'), ('Binance', 'Binance')), widget=forms.Select(attrs={'class':'form-control'}))
    pay_id_no = forms.CharField(label="", max_length=20, widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'Pay ID Number'}))


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
        fields = ('phone', 'location', 'bio', 'device_used', 'profile_pic', 'pay_id', 'pay_id_no', 'id_card')
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Location'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Bio'}),
            'device_used': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Device used'}),
            'id_card': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'National ID'}),
        }
