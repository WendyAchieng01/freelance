from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from accounts.models import Profile
from core.forms import CreateJobForm, JobAttemptForm, ResponseForm
from core.models import *
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.core.mail import send_mail
from django.http import HttpResponseRedirect
from django.urls import reverse

from payment.views import initiate_payment


# Create your views here.
@login_required
def freelancer_index(request):
    if request.user.is_authenticated:
        jobs = Job.objects.all()
        return render(request, 'index.html', {'jobs': jobs})
    else:
        return redirect('login')

@login_required
def jobs(request):
    if request.user.is_authenticated:
        # Get the jobs where the freelancer has not submitted a response and the status is not 'completed'
        jobs = Job.objects.prefetch_related('trainings').exclude(responses__user=request.user).exclude(status='completed')

        return render(request, 'jobs.html', {'jobs': jobs})
    else:
        return redirect('accounts:login')
    
@login_required
def bid_on_job(request, job_id):
    if request.method == 'POST':
        job = Job.objects.get(id=job_id)
        user = request.user

        # Check if the freelancer has already bid on this job
        existing_notification = Notification.objects.filter(
            recipient=job.client.user,
            message__contains=f"{user.username} has bid on your job: {job.title}",
            job=job,
            freelancer=user
        ).exists()

        if existing_notification:
            # Freelancer has already bid on this job
            return JsonResponse({
                'success': False,
                'message': 'You have already bid on this job.'
            })

        # Create a new notification instance
        notification = Notification.objects.create(
            recipient=job.client.user,
            message=f"{user.username} has bid on your job: {job.title}",
            job=job,
            freelancer=user  # Store the freelancer who bid on the job
        )

        return JsonResponse({'success': True, 'message': 'Bid submitted successfully.'})
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})

@login_required
def singlejob(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    form = ResponseForm(request.POST or None, request.FILES or None)

    # Check if the user has already submitted a response for this job
    user_response = job.responses.filter(user=request.user).first()
    if user_response:
        messages.warning(request, 'You have already submitted a response for this job.')
        return redirect('core:jobs')

    if request.method == 'POST':
        if form.is_valid():
            response = form.save(commit=False)
            response.user = request.user
            response.job = job
            response.save()

            messages.success(request, 'Task has been uploaded.')
            # Redirect to the list of jobs
            return redirect('core:jobs')

    responses = job.responses.all()
    return render(request, 'single-job.html', {'job': job, 'form': form, 'responses': responses})


@login_required
def freelancer_jobs(request):
    # Get the current freelancer's profile
    freelancer_profile = Profile.objects.get(user=request.user, user_type='freelancer')

    # Get the jobs where the freelancer has submitted a response
    freelancer_jobs = Job.objects.filter(responses__user=request.user)

    return render(request, 'freelancer_jobs.html', {'freelancer_jobs': freelancer_jobs})

    
@login_required
def about(request):
    return render(request, 'about.html')

@login_required
def contact(request):
    if request.method == "POST":
        name = request.POST.get('name')
        message_email = request.POST.get('message_email')
        message = request.POST.get('message')

        # Send email using django-anymail and Mailgun
        send_mail(
            'Contact Form Submission from {}'.format(name),
            'From: {}\n{}'.format(message_email, message),
            message_email,  # Sender's email
            ['wendyachieng98@gmail.com'],  # Recipient's email
            fail_silently=False,
        )
        messages.success(request, 'Your message has been sent. Thank you!')
        return HttpResponseRedirect(reverse('core:contact'))  # Redirect to a success page
    else:
        return render(request, 'contact.html')
    

def is_client(user):
    if user.is_authenticated:
        client_profile = Profile.objects.filter(user=user, user_type='client')
        return client_profile.exists()
    return False

@login_required
@user_passes_test(is_client)
def client_index(request):
    if request.user.is_authenticated:
        jobs = Job.objects.all()
        return render(request, 'client_index.html', {'jobs': jobs})
    else:
        return redirect('accounts:login')

@login_required
@user_passes_test(is_client)
def create_job(request):
    if request.method == 'POST':
        form = CreateJobForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['price']
            email = request.user.email

            # Redirect to the payment initiation view with the required data
            return initiate_payment(request, amount=amount, email=email, job_form=form)
    else:
        form = CreateJobForm()

    return render(request, 'create_job.html', {'form': form})

@login_required 
@user_passes_test(is_client) 
def client_posted_jobs(request): 
    client_profile = Profile.objects.get(user=request.user, user_type='client') 
    client_jobs = client_profile.jobs.filter(payment__verified=True)  # Filter out jobs with verified payments
    return render(request, 'client_posted_jobs.html', {'client_jobs': client_jobs})

@login_required
@user_passes_test(is_client)
def edit_job(request, job_id):
    job = get_object_or_404(Job, id=job_id, client=request.user.profile)

    if request.method == 'POST':
        form = CreateJobForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            return redirect('core:client_posted_jobs')
    else:
        form = CreateJobForm(instance=job)

    return render(request, 'edit_job.html', {'form': form, 'job': job})

@login_required
@user_passes_test(is_client)
def delete_job(request, job_id):
    job = get_object_or_404(Job, id=job_id, client__user=request.user)
    if request.method == 'POST':
        job.delete()
        return redirect('core:client_posted_jobs')
    return render(request, 'delete_job.html', {'job': job})

@login_required
@user_passes_test(is_client)
def job_responses(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    responses = job.responses.all()
    context = {
        'job': job,
        'responses': responses,
    }
    return render(request, 'job_responses.html', context)


@login_required
@user_passes_test(lambda u: u.profile.user_type == 'client')
def client_responses(request):
    client_profile = Profile.objects.get(user=request.user, user_type='client')
    client_jobs = client_profile.jobs.all()
    responses = Response.objects.filter(job__in=client_jobs)
    return render(request, 'job_responses.html', {'responses': responses})

@login_required
@user_passes_test(lambda u: u.profile.user_type == 'freelancer')
def freelancer_job_attempt(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    if job.is_max_freelancers_reached:
        return JsonResponse({'status': 'error', 'message': 'Maximum number of freelancers reached.'})

    if request.method == 'POST':
        form = JobAttemptForm(request.POST)
        if form.is_valid():
            attempt = form.save(commit=False)
            attempt.freelancer = request.user.profile
            attempt.job = job
            attempt.save()
            return JsonResponse({'status': 'success'})
    else:
        form = JobAttemptForm()

    return render(request, 'freelancer_job_attempt.html', {'form': form, 'job': job})

@login_required
@user_passes_test(is_client)
def mark_response_as_done(request):
    job_id = request.POST.get('job_id')

    try:
        job = Job.objects.get(pk=job_id)
        job.status = 'completed'
        job.save()
        
        return JsonResponse({'status': 'success'})
    except Job.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Job not found'})


@login_required
@user_passes_test(is_client)
def view_notifications(request):
    user = request.user
    notifications = Notification.objects.filter(recipient=user).order_by('-created_at')
    context = {
        'notifications': notifications
    }
    return render(request, 'notification.html', context)


@login_required
@user_passes_test(is_client)
def client_about(request):
    return render(request, 'client_about.html')


@login_required
@user_passes_test(is_client)
def client_contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')

        # Send the email
        try:
            send_mail(
                'Contact Form Submission', # Subject
                f'Name: {name}\nEmail: {email}\n\nMessage: {message}', # Message
                email, # From email
                ['wendyachieng98@gmail.com'], # To email(s)
                fail_silently=False,
            )
            messages.success(request, 'Your message has been sent. Thank you!')
        except Exception as e:
            messages.error(request, 'An error occurred while sending the email.')
            print(e)

    return render(request, 'client_contact.html')
