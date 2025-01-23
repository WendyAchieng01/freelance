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
import json
from freelance import settings
from payment.views import initiate_payment
from django.db.models import F, Count
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.core.files.storage import default_storage
import os
from django.db.models import Prefetch
from itertools import groupby
from operator import attrgetter
from django.views.decorators.http import require_http_methods

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
        category = request.GET.get('category')

        # Exclude jobs that have reached their max freelancers
        jobs = Job.objects.prefetch_related('trainings') \
            .annotate(num_responses=Count('responses')) \
            .exclude(responses__user=request.user) \
            .exclude(status='completed') \
            .exclude(num_responses__gte=F('max_freelancers'))  # Exclude jobs with max responses reached

        if category:
            jobs = jobs.filter(category=category)

        # Calculate remaining slots for each job
        for job in jobs:
            job.remaining_slots = job.max_freelancers - job.responses.count()

        categories = dict(Job.CATEGORY_CHOICES)
        
        return render(request, 'jobs.html', {
            'jobs': jobs,
            'categories': categories,
            'selected_category': category
        })
    else:
        return redirect('accounts:login')


@login_required
def singlejob(request, job_id):
    job = get_object_or_404(Job.objects.annotate(num_responses=Count('responses')), pk=job_id)

    # Prevent further responses if max freelancers reached
    if job.num_responses >= job.max_freelancers:
        messages.error(request, 'This job has reached the maximum number of freelancers.')
        return redirect('core:jobs')

    # Check if the user already responded
    if job.responses.filter(user=request.user).exists():
        messages.warning(request, 'You have already submitted a response for this job.')
        return redirect('core:jobs')

    # Instantiate form with job category
    form = ResponseForm(request.POST or None, request.FILES or None, job_category=job.category)

    if request.method == 'POST':
        if form.is_valid():
            response = form.save(commit=False)
            response.user = request.user
            response.job = job
            response.save()
            messages.success(request, 'Response submitted successfully.')
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
            return initiate_payment(request, amount=amount, email=email, job_form=form)
    else:
        form = CreateJobForm()

    categories = dict(Job.CATEGORY_CHOICES)
    return render(request, 'create_job.html', {
        'form': form,
        'categories': categories
    })

@login_required
@user_passes_test(is_client)
def client_posted_jobs(request):
    client_profile = Profile.objects.get(user=request.user, user_type='client')
    category = request.GET.get('category')
    
    client_jobs = client_profile.jobs.filter(payment__verified=True)
    
    if category:
        client_jobs = client_jobs.filter(category=category)
    
    categories = dict(Job.CATEGORY_CHOICES)
    
    return render(request, 'client_posted_jobs.html', {
        'client_jobs': client_jobs,
        'categories': categories,
        'selected_category': category
    })

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
    
    # Pass responses with extra_data to the template
    context = {
        'job': job,
        'responses': responses,
    }
    return render(request, 'job_responses.html', context)




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
@user_passes_test(lambda u: u.profile.user_type == 'client')
def mark_response_as_done(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)  # Parse the JSON payload
            job_id = data.get("job_id")  # Retrieve job_id from the parsed JSON

            if not job_id:
                return JsonResponse({"status": "error", "message": "Job ID not provided."})

            # Verify job ownership and update status
            job = Job.objects.get(pk=job_id, client=request.user.profile)
            job.status = "completed"
            job.save()

            return JsonResponse({"status": "success"})
        except Job.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Job not found or you are not authorized."})
        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "Invalid JSON payload."})

    return JsonResponse({"status": "error", "message": "Invalid request method."})



@login_required
@user_passes_test(lambda u: u.profile.user_type == 'client')
def client_responses(request):
    client_profile = Profile.objects.get(user=request.user, user_type='client')
    client_jobs = client_profile.jobs.all()
    responses = Response.objects.filter(job__in=client_jobs)
    return render(request, 'job_responses.html', {'responses': responses})

@login_required
@user_passes_test(lambda u: u.profile.user_type == 'client')
def accept_response(request, job_id, response_id):
    if request.method == 'POST':
        response = get_object_or_404(Response, id=response_id, job_id=job_id)
        freelancer = response.user.profile

        # Check if a chat already exists
        chat, created = Chat.objects.get_or_create(
            job=response.job,
            client=request.user.profile,
            freelancer=freelancer
        )

        return JsonResponse({
            'status': 'success',
            'chat_id': chat.id,
            'message': 'Chat initiated successfully.',
        })
    
@login_required
def my_chats(request):
    """View for listing all chats grouped by jobs for the current user"""
    if request.user.profile.user_type == 'freelancer':
        chats = Chat.objects.filter(
            freelancer=request.user.profile
        ).select_related(
            'job', 'client__user', 'freelancer__user'
        ).order_by('job_id')
    else:
        chats = Chat.objects.filter(
            client=request.user.profile
        ).select_related(
            'job', 'client__user', 'freelancer__user'
        ).order_by('job_id')
    
    # Group chats by job
    grouped_chats = []
    for job_id, chats_in_job in groupby(chats, key=attrgetter('job_id')):
        chats_list = list(chats_in_job)
        if chats_list:
            # Get the job object from the first chat
            job = chats_list[0].job
            grouped_chats.append({
                'job': job,  # This includes all job fields including status
                'chats': chats_list
            })
    
    return render(request, 'my_chats.html', {
        'grouped_chats': grouped_chats
    })

@login_required
def chat_room(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id)
    
    if request.user.profile not in [chat.client, chat.freelancer]:
        raise PermissionDenied
    
    if request.method == 'POST':
        content = request.POST.get('message', '').strip()
        files = request.FILES.getlist('attachments')
        
        if content or files:
            message = Message.objects.create(
                chat=chat,
                sender=request.user,
                content=content
            )
            
            for file in files:
                MessageAttachment.objects.create(
                    message=message,
                    file=file,
                    filename=file.name,
                    file_size=file.size,
                    content_type=file.content_type
                )
    
    messages = chat.messages.all().order_by('timestamp')
    return render(request, 'chat_room.html', {
        'chat': chat,
        'messages': messages,
        'in_chat_room': True
    })

@login_required
def download_attachment(request, attachment_id):
    attachment = get_object_or_404(MessageAttachment, id=attachment_id)
    
    # Security check - only chat participants can download
    if request.user.profile not in [attachment.message.chat.client, attachment.message.chat.freelancer]:
        raise PermissionDenied
    
    response = FileResponse(attachment.file)
    response['Content-Disposition'] = f'attachment; filename="{attachment.filename}"'
    response['Content-Type'] = attachment.content_type
    return response



@login_required
@require_http_methods(["POST"])
def mark_job_completed(request, job_id):
    try:
        # Add debug logging
        print(f"Attempting to mark job {job_id} as completed")
        print(f"Request user: {request.user.username}")
        
        job = get_object_or_404(Job, id=job_id)
        print(f"Found job: {job.title}")
        print(f"Job client: {job.client}")
        print(f"User profile: {request.user.profile}")
        
        # Check if the user is the client of the job
        if request.user.profile != job.client:
            print("Permission denied: User is not the job client")
            return JsonResponse(
                {'error': 'Permission denied: Only the job client can mark it as completed'},
                status=403
            )
            
        print(f"Current job status: {job.status}")
        job.status = 'completed'
        job.save()
        print(f"Job saved with new status: {job.status}")
        
        # Send email to admin
        admin_email = "info@nilltechsolutions.com"
        subject = f"Job Marked as Completed: {job.title}"
        message = (
            f"Dear Admin,\n\n"
            f"The following job has been marked as completed by the client:\n\n"
            f"Job Title: {job.title}\n"
            f"Client: {request.user.username} ({request.user.email})\n\n"
            f"Please review the job status.\n\n"
            f"Best regards,\n"
            f"NillTech Solutions"
        )
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [admin_email],
            fail_silently=False,
        )
        print("Admin email sent successfully")
        
        return JsonResponse({
            'message': 'Job marked as completed successfully.',
            'job_id': job_id,
            'status': 'completed'
        })
    except Job.DoesNotExist:
        print(f"Job {job_id} not found")
        return JsonResponse({
            'error': f'Job {job_id} not found'
        }, status=404)
    except Exception as e:
        import traceback
        print(f"Error marking job as completed: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'error': str(e)
        }, status=400)