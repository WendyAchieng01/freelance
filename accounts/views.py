from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import authenticate, login as auth_login
from .forms import UpdateUserForm, ChangePasswordForm, ClientForm, FreelancerForm, UserInfoForm
from django.contrib import messages
from django.contrib.auth.models import User, auth 
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Profile, FreelancerProfile, ClientProfile
from .forms import ProfileForm
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse

def login(request):
    if request.method == 'POST':
        identifier = request.POST['username']
        password = request.POST['password']

        # Check if the identifier is an email or username
        try:
            user = User.objects.get(Q(username=identifier) | Q(email=identifier))
        except User.DoesNotExist:
            user = None

        if user is not None:
            # Authenticate using username
            user = authenticate(username=user.username, password=password)

        if user is not None:
            auth_login(request, user)
            user_profile = Profile.objects.get(user=user)
            if user_profile.user_type == 'freelancer':
                return redirect('core:index')
            else:
                return redirect('core:client_index')
        else:
            messages.info(request, 'Invalid credentials. Please check your username/email and password.')
            # Render the same template with an error message
            return render(request, 'registration/signup.html')
    else:
        return render(request, 'registration/signup.html')

def signup(request):
    if request.method == 'POST':
        form_data = request.POST
        username = form_data['username']
        password1 = form_data['password1']
        password2 = form_data['password2']
        email = form_data['email']
        user_type = form_data.get('user_type', 'freelancer')
        
        if User.objects.filter(username=username).exists():
            messages.info(request, 'Username is already taken. Please choose a different username.')
            return redirect('accounts:signup')
            
        if User.objects.filter(email=email).exists():
            messages.info(request, 'Email is already taken. Please use a different email.')
            return redirect('accounts:signup')
            
        if password1 != password2:
            messages.info(request, 'Passwords do not match. Please ensure that the passwords are identical.')
            return redirect('accounts:signup')
            
        with transaction.atomic():
            # Create user but set is_active to False until email verification
            user = User.objects.create_user(
                username=username, 
                password=password1, 
                email=email,
                is_active=False  # User won't be able to log in until activated
            )
            
            user.profile, _ = Profile.objects.get_or_create(user=user)
            user.profile.user_type = user_type
            user.profile.save(update_fields=['user_type'])
            
            # Store user data in the session
            request.session['signup_data'] = {
                'username': username,
                'email': email,
                'user_type': user_type
            }
            
            # Generate verification token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Build verification URL
            current_site = get_current_site(request)
            verification_url = reverse('accounts:verify_email', kwargs={'uidb64': uid, 'token': token})
            verification_link = f'http://{current_site.domain}{verification_url}'
            
            # Send verification email
            subject = 'Verify your email address'
            message = f'''
            Hi {username},
            
            Thank you for signing up! Please click the link below to verify your email address:
            
            {verification_link}
            
            This link will expire in 24 hours.
            
            If you didn't sign up for this account, you can ignore this email.
            '''
            
            send_mail(
                subject,
                message,
                'info@nilltechsolutions.com',  
                [email],  # Fix: Add recipient list
                fail_silently=False,
            )
            
            # Redirect to verification pending page
            return redirect('accounts:verification_pending')
    else:
        return render(request, "registration/signup.html")

def verify_email(request, uidb64, token):
    try:
        # Decode the user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
        
        # Check if the token is valid
        if default_token_generator.check_token(user, token):
            # Activate the user
            user.is_active = True
            user.save()
            
            # Log the user in automatically
            auth_login(request, user)
            
            messages.success(request, 'Your email has been verified! You can now create your profile.')
            
            # Redirect to profile creation page
            return redirect('accounts:profile_creation')
        else:
            messages.error(request, 'The verification link is invalid or has expired.')
            return redirect('accounts:signup')  # Use 'signup' instead of 'login'
            
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        messages.error(request, 'The verification link is malformed.')
        return redirect('accounts:signup')  # Use 'signup' instead of 'login'
    except User.DoesNotExist:
        messages.error(request, 'The user associated with this verification link does not exist.')
        return redirect('accounts:signup')
    


def verification_pending(request):
    """
    Display a page informing the user to check their email for verification
    """
    # Get the signup data from session
    signup_data = request.session.get('signup_data', {})
    
    username = signup_data.get('username', '')
    email = signup_data.get('email', '')
    user_id = None
    
    # Get user ID if available (for resend functionality)
    if username:
        try:
            user = User.objects.get(username=username)
            user_id = user.id
        except User.DoesNotExist:
            pass
    
    context = {
        'username': username,
        'email': email,
        'user_id': user_id
    }
    
    return render(request, 'registration/verification_pending.html', context)

# For the resend functionality mentioned in the template
def resend_verification(request, user_id):
    """
    Resend the verification email to the user
    """
    try:
        user = User.objects.get(pk=user_id, is_active=False)
        
        # Generate new verification token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Build verification URL
        current_site = get_current_site(request)
        verification_url = reverse('accounts:verify_email', kwargs={'uidb64': uid, 'token': token})
        verification_link = f'http://{current_site.domain}{verification_url}'
                
        # Send verification email
        subject = 'Verify your email address'
        message = f'''
        Hi {user.username},
        
        You requested a new verification email. Please click the link below to verify your email address:
        
        {verification_link}
        
        This link will expire in 24 hours.
        
        If you didn't request this email, you can ignore it.
        '''
        
        send_mail(
            subject,
            message,
            'info@nilltechsolutions.com',  # Replace with your email
            [user.email],
            fail_silently=False,
        )
        
        messages.success(request, 'A new verification email has been sent to your email address.')
        
    except User.DoesNotExist:
        messages.error(request, 'User not found or already verified.')
    
    return redirect('accounts:verification_pending')

def profile_creation(request):
    """
    Display the profile creation page with buttons to redirect to appropriate form.
    """
    if not request.user.is_authenticated:
        return redirect('accounts:signup')

    user = request.user
    user_type = user.profile.user_type  # Get the user's type from profile
    
    context = {
        'user': user,
        'user_type': user_type,  # Pass user_type to the template
        'user_id': user.id  # Pass user_id for the form URLs
    }
    
    return render(request, 'registration/profile_creation.html', context)


def client_form(request, user_id):
    user = User.objects.get(pk=user_id)

    if request.method == 'POST':
        form = ClientForm(request.POST)
        
        if form.is_valid():
            # Process form data
            # First, ensure user profile exists
            profile, created = Profile.objects.get_or_create(user=user)
            
            # Update profile fields
            profile.user_type = 'client'
            profile.phone = form.cleaned_data['phone_number']
            profile.location = form.cleaned_data['location']
            profile.pay_id = form.cleaned_data['pay_id']
            profile.pay_id_no = form.cleaned_data['pay_id_no']
            profile.save()
            
            # Now create or update the ClientProfile
            client_profile, created = ClientProfile.objects.get_or_create(profile=profile)
            client_profile.company_name = form.cleaned_data['company_name']
            client_profile.company_website = form.cleaned_data['company_website']
            client_profile.industry = form.cleaned_data['industry']
            client_profile.project_budget = form.cleaned_data['project_budget']
            client_profile.preferred_freelancer_level = form.cleaned_data['preferred_freelancer_level']
            client_profile.save()
            
            # Handle M2M relationship for languages after saving
            if form.cleaned_data['languages']:
                client_profile.languages.set(form.cleaned_data['languages'])
            
            # Redirect to the index page
            return redirect('core:client_index')
    else:
        # Pre-populate the form with the user's data from the session
        signup_data = request.session.get('signup_data', {})
        form = ClientForm(initial={
            'email': signup_data.get('email', ''),
            'company_name': signup_data.get('company_name', ''),  # Add this line
        })
    
    return render(request, 'registration/client_form.html', {'form': form})

def freelancer_form(request, user_id):
    user = User.objects.get(pk=user_id)

    if request.method == 'POST':
        form = FreelancerForm(request.POST, request.FILES)
        
        if form.is_valid():
            # Process form data
            profile, created = Profile.objects.get_or_create(user=user)
            
            # Update profile fields
            profile.user_type = 'freelancer'
            profile.phone = form.cleaned_data['phone_number']
            profile.location = form.cleaned_data['location']
            profile.profile_pic = form.cleaned_data['photo']
            profile.pay_id = form.cleaned_data['pay_id']
            profile.pay_id_no = form.cleaned_data['pay_id_no']
            profile.save()
            
            # Create or update the FreelancerProfile
            freelancer_profile, created = FreelancerProfile.objects.get_or_create(profile=profile)
            freelancer_profile.portfolio_link = form.cleaned_data['portfolio_link']
            freelancer_profile.experience_years = form.cleaned_data['experience_years']
            freelancer_profile.hourly_rate = form.cleaned_data['hourly_rate']
            freelancer_profile.availability = form.cleaned_data['availability']
            freelancer_profile.save()
            
            # Handle M2M relationships
            if form.cleaned_data['skills']:
                freelancer_profile.skills.set(form.cleaned_data['skills'])
            if form.cleaned_data['languages']:
                freelancer_profile.languages.set(form.cleaned_data['languages'])
            
            # Redirect to the index page
            return redirect('core:index')
    else:
        # Pre-populate the form with the user's data from the session
        signup_data = request.session.get('signup_data', {})
        form = FreelancerForm(initial={
            'name': signup_data.get('username', ''),
            'email': signup_data.get('email', ''),
        })
    
    return render(request, 'registration/freelancer_form.html', {'form': form})

def update_user(request):
    if request.user.is_authenticated:
        current_user = User.objects.get(id=request.user.id)
        user_form = UpdateUserForm(request.POST or None, instance=current_user)

        if user_form.is_valid():
            user_form.save()

            messages.success(request, "User Has Been Updated")
            return redirect('core:index')
        return render(request, 'registration/update_user.html', {'user_form':user_form})
    
    else: 
        messages.success(request, "You Must Be Logged In To Access This Page!!")
        return redirect('accounts:login')

@login_required
def update_password(request):
    current_user = request.user

    if request.method == 'POST':
        form = ChangePasswordForm(current_user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Your password has been updated successfully.")
            return redirect('accounts:update_user')  
        else:
            for error in form.errors.values():
                messages.error(request, error)

    else:
        form = ChangePasswordForm(current_user)

    return render(request, "registration/update_password.html", {'form': form})

def update_info(request):
    if request.user.is_authenticated:
        current_user = Profile.objects.get(user__id=request.user.id)
        form = UserInfoForm(request.POST or None, request.FILES or None, instance=current_user)

        if form.is_valid():
            form.save()
            messages.success(request, "Your Info Has Been Updated")
            return redirect('core:index')
        else:
            # You can remove or modify the logger.error line if you want
            print("Form is not valid: ", form.errors)

    else:
        messages.success(request, "You Must Be Logged In To Access This Page!!")
        return redirect('accounts:login')

    return render(request, 'registration/update_info.html', {'form': form})

@csrf_exempt
@login_required
def update_profile_pic(request):
    if request.method == 'POST':
        profile = Profile.objects.get(user=request.user)
        profile_pic = request.FILES.get('profile_pic')
        if profile_pic:
            profile.profile_pic = profile_pic
            profile.save()
            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'})

def client_update_user(request):
    if request.user.is_authenticated:
        current_user = User.objects.get(id=request.user.id)
        user_form = UpdateUserForm(request.POST or None, instance=current_user)

        if user_form.is_valid():
            user_form.save()

            messages.success(request, "User Has Been Updated")
            return redirect('core:index')
        return render(request, 'client/client_update_user.html', {'user_form':user_form})
    
    else: 
        messages.success(request, "You Must Be Logged In To Access This Page!!")
        return redirect('accounts:login')

def client_update_password(request):
    if request.user.is_authenticated:
        current_user = request.user
        #Did they fill out the form
        if request.method == 'POST':
            form = ChangePasswordForm(current_user, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Your Password Has Been Updated...")
                #login(request, current_user)
                return redirect('accounts:update_user')
            else:
                for error in list(form.errors.values()):
                    messages.error(request, error)
                    return redirect('accounts:client_update_password')
        else:
            form = ChangePasswordForm(current_user)
            return render(request, "client/client_update_password.html", {'form':form})
        
    else: 
        messages.success(request, "You Must Be Logged In To View That Page!!!")
        return redirect('core:index')
    
def client_update_info(request):
    if request.user.is_authenticated:
        current_user = Profile.objects.get(user__id=request.user.id)
        form = UserInfoForm(request.POST or None, request.FILES or None, instance=current_user)

        if form.is_valid():
            form.save()
            messages.success(request, "Your Info Has Been Updated")
            return redirect('core:index')
        else:
            # You can remove or modify the logger.error line if you want
            print("Form is not valid: ", form.errors)

    else:
        messages.success(request, "You Must Be Logged In To Access This Page!!")
        return redirect('accounts:login')

    return render(request, 'client/client_update_info.html', {'form': form})


@login_required
def edit_profile(request, user_id):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if profile.user_type == 'freelancer':
        freelancer_profile, created = FreelancerProfile.objects.get_or_create(profile=profile)
        form = FreelancerForm(instance=freelancer_profile)
    else:
        client_profile, created = ClientProfile.objects.get_or_create(profile=profile)
        form = ClientForm(instance=client_profile)

    if request.method == "POST":
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
        user_form = form.__class__(request.POST, instance=form.instance)

        if profile_form.is_valid() and user_form.is_valid():
            profile_form.save()
            user_form.save()
            return redirect('core:index')  

    profile_form = ProfileForm(instance=profile)
    return render(request, 'registration/edit_portfolio.html', {
        'profile_form': profile_form,
        'user_form': form
    })

@login_required
def freelancer_portfolio(request, user_id):
    user = get_object_or_404(User, id=user_id)
    profile, created = Profile.objects.get_or_create(user=user)
    freelancer_profile, created = FreelancerProfile.objects.get_or_create(profile=profile)
    return render(request, 'registration/freelancer_portfolio.html', {'profile': freelancer_profile})

@login_required
def client_portfolio(request, user_id):
    user = get_object_or_404(User, id=user_id)
    profile, created = Profile.objects.get_or_create(user=user)
    client_profile, created = ClientProfile.objects.get_or_create(profile=profile)
    return render(request, 'registration/client_portfolio.html', {'profile': client_profile})