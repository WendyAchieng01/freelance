from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import authenticate, login
from .forms import UpdateUserForm, ChangePasswordForm, ClientForm, FreelancerForm, UserInfoForm
from django.contrib import messages
from django.contrib.auth.models import User, auth 
from .models import Profile
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required


def login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = auth.authenticate(username=username, password=password)

        if user is not None:
            auth.login(request, user)
            user_profile = Profile.objects.get(user=user)
            if user_profile.user_type == 'freelancer':
                return redirect('core:index')
            else:
                return redirect('core:client_index')
        else:
            messages.info(request, 'Invalid Credentials')
            return redirect('accounts:signup')
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
            user = User.objects.create_user(username=username, password=password1, email=email)
            user.profile, _ = Profile.objects.get_or_create(user=user)
            user.profile.user_type = user_type
            user.profile.save(update_fields=['user_type'])
            messages.success(request, 'Account created successfully! Welcome...')

            # Store user data in the session
            request.session['signup_data'] = {
                'username': username,
                'email': email,
                'user_type': user_type
            }

            # Redirect to the respective form based on user_type
            if user_type == 'freelancer':
                return redirect('accounts:freelancer_form', user_id=user.id)
            else:
                return redirect('accounts:client_form', user_id=user.id)
    else:
        return render(request, "registration/signup.html")

def client_form(request, user_id):
    user = User.objects.get(pk=user_id)

    # Retrieve user data from the session
    signup_data = request.session.get('signup_data', {})

    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            # Process form data
            profile = user.profile
            profile.is_freelancer = False  # Marking as a client
            profile.save()

            # Populate and save additional profile fields
            profile_data = form.cleaned_data
            profile.phone = profile_data['phone_number']
            profile.location = profile_data['location']
            profile.pay_id = form.cleaned_data['pay_id']
            profile.pay_id_no = form.cleaned_data['pay_id_no']
            profile.save()

            # Redirect to login page
            return redirect('accounts:signup')
    else:
        # Pre-populate the form with the user's data from the session
        form = ClientForm(initial={
            'name': signup_data.get('username', ''),
            'email': signup_data.get('email', ''),
        })
    return render(request, 'registration/client_form.html', {'form': form})

def freelancer_form(request, user_id):
    user = User.objects.get(pk=user_id)

    # Retrieve user data from the session
    signup_data = request.session.get('signup_data', {})

    if request.method == 'POST':
        form = FreelancerForm(request.POST, request.FILES)
        if form.is_valid():
            # Process form data
            profile = user.profile
            profile.is_freelancer = True  # Marking as a freelancer
            profile.save()

            # Populate and save additional profile fields
            profile_data = form.cleaned_data
            profile.phone = profile_data['phone_number']
            profile.location = profile_data['location']
            profile.device_used = profile_data['device']
            profile.profile_pic = profile_data['photo']
            profile.pay_id = profile_data['pay_id']
            profile.save()

            # Redirect to login page
            return redirect('accounts:signup')
    else:
        # Pre-populate the form with the user's data from the session
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

def update_password(request):
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
                    return redirect('accounts:update_password')
        else:
            form = ChangePasswordForm(current_user)
            return render(request, "registration/update_password.html", {'form':form})
        
    else: 
        messages.success(request, "You Must Be Logged In To View That Page!!!")
        return redirect('core:index')
    
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
