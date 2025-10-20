from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import authenticate, login as auth_login

from core.models import Review
from .forms import ChangePasswordForm, ClientForm, FreelancerForm
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
import logging
from django.core.mail import EmailMultiAlternatives
from django.utils.html import format_html
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


def google_test_page(request):
    return render(request, "google.html")


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

            # HTML email content with a button
            subject = 'Verify Your Email Address'
            message_text = f'''
                Hi {username},
                Thank you for signing up! Please click the button below to verify your email address.
                {verification_link}
                If you didn't sign up for this account, you can ignore this email.
            '''
            message_html = format_html(f'''
                <div style="font-family: Arial, sans-serif; text-align: center;">
                    <h2>Welcome, {username}!</h2>
                    <p>Thank you for signing up! Please click the button below to verify your email address:</p>
                    <a href="{verification_link}" style="display: inline-block; background-color: #28a745; color: white; text-decoration: none; padding: 10px 20px; border-radius: 5px; font-size: 16px;">
                        Verify Email
                    </a>
                    <p>If you didn't sign up for this account, you can ignore this email.</p>
                    <p>This link will expire in 24 hours.</p>
                </div>
            ''')

            email = EmailMultiAlternatives(subject, message_text, 'info@nilltechsolutions.com', [email])
            email.attach_alternative(message_html, "text/html")
            email.send()

            return redirect('accounts:verification_pending')
    
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
    '''
    Display a page informing the user to check their email for verification
    '''
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
from django.core.mail import EmailMultiAlternatives
from django.utils.html import format_html

def resend_verification(request, user_id):
    
    #Resend the verification email to the user
    
    try:
        user = User.objects.get(pk=user_id, is_active=False)
        
        # Generate new verification token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Build verification URL
        current_site = get_current_site(request)
        verification_url = reverse('accounts:verify_email', kwargs={'uidb64': uid, 'token': token})
        verification_link = f'http://{current_site.domain}{verification_url}'
                
        # Email content
        subject = 'Verify Your Email Address'
        message_text = f'''
        Hi {user.username},
        
        You requested a new verification email. Please click the link below to verify your email address:
        
        {verification_link}
        
        This link will expire in 24 hours.
        
        If you didn't request this email, you can ignore it.
        '''
        
        message_html = format_html(f'''
        <div style="font-family: Arial, sans-serif; text-align: center;">
            <h2>Hi {user.username},</h2>
            <p>You requested a new verification email. Please click the button below to verify your email address:</p>
            <a href="{verification_link}" style="display: inline-block; background-color: #007bff; color: white; text-decoration: none; padding: 10px 20px; border-radius: 5px; font-size: 16px;">
                Verify Email
            </a>
            <p>This link will expire in 24 hours.</p>
            <p>If you didn't request this email, you can ignore it.</p>
        </div>
        ''')

        email = EmailMultiAlternatives(subject, message_text, 'info@nilltechsolutions.com', [user.email])
        email.attach_alternative(message_html, "text/html")
        email.send()
        
        messages.success(request, 'A new verification email has been sent to your email address.')
        
    except User.DoesNotExist:
        messages.error(request, 'User not found or already verified.')
    
    return redirect('accounts:verification_pending')


def update_email(request, user_id):
    
    #Update user's email and resend verification link
    
    if request.method == 'POST':
        try:
            user = User.objects.get(pk=user_id, is_active=False)
            new_email = request.POST.get('new_email')
            
            # Check if the new email is already taken
            if User.objects.filter(email=new_email).exclude(pk=user_id).exists():
                messages.error(request, 'This email is already taken by another user.')
                return redirect('accounts:verification_pending')
            
            # Update the user's email
            user.email = new_email
            user.save()
            
            # Update the email in session data
            if 'signup_data' in request.session:
                request.session['signup_data']['email'] = new_email
                request.session.modified = True
            
            # Generate new verification token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Build verification URL
            current_site = get_current_site(request)
            verification_url = reverse('accounts:verify_email', kwargs={'uidb64': uid, 'token': token})
            verification_link = f'http://{current_site.domain}{verification_url}'
            
            # Email content
            subject = 'Verify Your New Email Address'
            message_text = f'''
            Hi {user.username},
            
            Your email has been updated. Please click the link below to verify your new email address:
            
            {verification_link}
            
            This link will expire in 24 hours.
            
            If you didn't request this change, please contact us immediately.
            '''
            
            message_html = format_html(f'''
            <div style="font-family: Arial, sans-serif; text-align: center;">
                <h2>Hi {user.username},</h2>
                <p>Your email has been updated. Please click the button below to verify your new email address:</p>
                <a href="{verification_link}" style="display: inline-block; background-color: #28a745; color: white; text-decoration: none; padding: 10px 20px; border-radius: 5px; font-size: 16px;">
                    Verify New Email
                </a>
                <p>This link will expire in 24 hours.</p>
                <p>If you didn't request this change, please contact us immediately.</p>
            </div>
            ''')

            email = EmailMultiAlternatives(subject, message_text, 'info@nilltechsolutions.com', [new_email])
            email.attach_alternative(message_html, "text/html")
            email.send()
            
            messages.success(request, f'Your email has been updated to {new_email}. A new verification email has been sent.')
            
        except User.DoesNotExist:
            messages.error(request, 'User not found or already verified.')
        
    return redirect('accounts:verification_pending')

def profile_creation(request):
    
    #Display the profile creation page with buttons to redirect to appropriate form.
    
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
    user = get_object_or_404(User, pk=user_id)
    profile, created = Profile.objects.get_or_create(user=user)
    
    try:
        client_profile = ClientProfile.objects.get(profile=profile)
    except ClientProfile.DoesNotExist:
        client_profile = None

    if request.method == 'POST':
        form = ClientForm(request.POST, request.FILES)
        
        if form.is_valid():
            # Process form data
            profile.user_type = 'client'
            profile.phone = form.cleaned_data.get('phone_number', '')
            profile.location = form.cleaned_data.get('location', '')
            profile.profile_pic = form.cleaned_data.get('photo')
            profile.save()
            
            # Create or update the ClientProfile
            if not client_profile:
                client_profile = ClientProfile(profile=profile)
            
            # Use the company name from the form if provided, otherwise use the username
            client_profile.company_name = form.cleaned_data.get('company_name') or client_profile.profile.user.username
            client_profile.industry = form.cleaned_data.get('industry', '')
            client_profile.project_budget = form.cleaned_data.get('project_budget', 0)
            client_profile.preferred_freelancer_level = form.cleaned_data.get('preferred_freelancer_level', '')
            client_profile.company_website = form.cleaned_data.get('company_website', '')
            client_profile.save()
            
            # Handle languages (M2M relationship)
            if form.cleaned_data.get('languages'):
                client_profile.languages.set(form.cleaned_data['languages'])
            
            return redirect('core:client_index')
    else:
        # Pre-populate the form with existing data
        initial_data = {
            'name': user.get_full_name() or user.username,
            'email': user.email,
        }
        
        # Add profile data if it exists
        if profile:
            initial_data.update({
                'phone_number': profile.phone or '',
                'location': profile.location or '',
            })
        
        # Add client-specific data if it exists
        if client_profile:
            initial_data.update({
                'company_name': client_profile.profile.user.username or '',
                'industry': client_profile.industry or '',
                'project_budget': client_profile.project_budget or 0,
                'preferred_freelancer_level': client_profile.preferred_freelancer_level or '',
                'company_website': client_profile.company_website or '',
            })
            
            # For M2M field (languages)
            if client_profile.languages.exists():
                initial_data['languages'] = client_profile.languages.all()
        
        form = ClientForm(initial=initial_data)
    
    return render(request, 'registration/client_form.html', {'form': form})

def freelancer_form(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    profile, created = Profile.objects.get_or_create(user=user)
    
    try:
        freelancer_profile = FreelancerProfile.objects.get(profile=profile)
    except FreelancerProfile.DoesNotExist:
        freelancer_profile = None

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
            
            
            return redirect('core:index')
    else:
        # Pre-populate the form with existing data
        initial_data = {
            'name': user.get_full_name() or user.username,
            'email': user.email,
        }
        
        # Add profile data if it exists
        if profile:
            initial_data.update({
                'phone_number': profile.phone or '',
                'location': profile.location or '',
                'pay_id': profile.pay_id or '',
            })
        
        # Add freelancer-specific data if it exists
        if freelancer_profile:
            initial_data.update({
                'portfolio_link': freelancer_profile.portfolio_link or '',
                'experience_years': freelancer_profile.experience_years or 0,
                'hourly_rate': freelancer_profile.hourly_rate or 0,
                'availability': freelancer_profile.availability or '',
            })
            
            # For M2M fields, pre-select the existing values
            if freelancer_profile.skills.exists():
                initial_data['skills'] = freelancer_profile.skills.all()
            if freelancer_profile.languages.exists():
                initial_data['languages'] = freelancer_profile.languages.all()
        
        form = FreelancerForm(initial=initial_data)
    
    return render(request, 'registration/freelancer_form.html', {'form': form})

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
    

logger = logging.getLogger(__name__)

@login_required
def freelancer_portfolio(request, user_id):
    logger.debug(f"Request headers: {request.headers}")
    user = get_object_or_404(User, id=user_id)
    profile, created = Profile.objects.get_or_create(user=user)
    freelancer_profile, created = FreelancerProfile.objects.get_or_create(profile=profile)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        logger.debug("AJAX request detected")
        data = {
            'username': user.username,
            'skills': list(freelancer_profile.skills.values_list('name', flat=True)),
            'languages': list(freelancer_profile.languages.values_list('name', flat=True)),
            'experience_years': freelancer_profile.experience_years,
            'hourly_rate': float(freelancer_profile.hourly_rate),
            'availability': freelancer_profile.availability,
            'portfolio_link': freelancer_profile.portfolio_link if freelancer_profile.portfolio_link else None
        }
        return JsonResponse(data)
    
    has_rated_freelancer = False
    if request.user.is_authenticated and request.user != profile.user:
        has_rated_freelancer = Review.objects.filter(
            reviewer=request.user, 
            recipient=profile.user
        ).exists()

    logger.debug("Returning HTML response")
    return render(request, 'registration/freelancer_portfolio.html', {
        'profile': profile,
        'user_profile': user,
        'has_rated_freelancer': has_rated_freelancer,
    })


@login_required
def client_portfolio(request, user_id):
    user = get_object_or_404(User, id=user_id)
    profile, created = Profile.objects.get_or_create(user=user)
    
    try:
        client_profile = ClientProfile.objects.get(profile=profile)
    except ClientProfile.DoesNotExist:
        client_profile = None
    
    # Check if the current user has already rated this client
    has_rated_client = False
    if request.user.is_authenticated and request.user != user:
        has_rated_client = Review.objects.filter(
            reviewer=request.user, 
            recipient=user
        ).exists()
    
    return render(request, 'registration/client_portfolio.html', {
        'profile': client_profile, 
        'user_profile': user,
        'has_rated_client': has_rated_client
    })
    
    
def signup_gen(request):
    if request.method == 'POST':
        form_data = request.POST
        username = form_data['username']
        password1 = form_data['password']
        password2 = form_data['confirm_password']
        email = form_data['email']
        user_type = form_data.get('user_type', 'freelancer')

        if User.objects.filter(username=username).exists():
            messages.info(request, 'Username is already taken. Please choose a different username.')
            return redirect('accounts:signup1')
        if User.objects.filter(email=email).exists():
            messages.info(request, 'Email is already taken. Please use a different email.')
            return redirect('accounts:signup1')
        if password1 != password2:
            messages.info(request, 'Passwords do not match. Please ensure that the passwords are identical.')
            return redirect('accounts:signup1')

        with transaction.atomic():
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

            # HTML email content with a button
            subject = 'Verify Your Email Address'
            message_text = f'''
                Hi {username},
                Thank you for signing up! Please click the button below to verify your email address.
                {verification_link}
                If you didn't sign up for this account, you can ignore this email.
            '''
            message_html = format_html(f'''
                <div style="font-family: Arial, sans-serif; text-align: center;">
                    <h2>Welcome, {username}!</h2>
                    <p>Thank you for signing up! Please click the button below to verify your email address:</p>
                    <a href="{verification_link}" style="display: inline-block; background-color: #28a745; color: white; text-decoration: none; padding: 10px 20px; border-radius: 5px; font-size: 16px;">
                        Verify Email
                    </a>
                    <p>If you didn't sign up for this account, you can ignore this email.</p>
                    <p>This link will expire in 24 hours.</p>
                </div>
            ''')

            email = EmailMultiAlternatives(subject, message_text, 'info@nilltechsolutions.com', [email])
            email.attach_alternative(message_html, "text/html")
            email.send()

            return redirect('accounts:verification_pending')
    
    return render(request, "signup_gen.html")

def login_gen(request):
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
            return render(request, 'signup_gen.html')
    else:
        return render(request, 'login_gen.html')

