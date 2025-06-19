from venv import logger
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from accounts.models import FreelancerProfile, Profile
from core.forms import CreateJobForm, ResponseForm
from core.models import *
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.core.mail import send_mail
from django.http import HttpResponseRedirect, FileResponse
from django.urls import reverse
import json
from freelance import settings
from payment.views import initiate_payment
from django.db.models import F, Count
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
import os
from .forms import ReviewForm
from django.db.models import Prefetch
from itertools import groupby
from operator import attrgetter
from django.views.decorators.http import require_http_methods
from .matching import match_freelancers_to_job, recommend_jobs_to_freelancer
from django.contrib.auth import get_user_model
from django.http import FileResponse, Http404

User = get_user_model()

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
        jobs = Job.objects.prefetch_related('trainings') \
            .annotate(num_responses=Count('responses')) \
            .exclude(responses__user=request.user) \
            .exclude(status='completed') \
            .exclude(num_responses__gte=F('max_freelancers'))
        
        if category:
            jobs = jobs.filter(category=category)
        
        for job in jobs:
            job.remaining_slots = job.max_freelancers - job.responses.count()
        
        # Add recommended jobs for freelancers
        recommended_jobs = []
        try:
            # Check if user has a profile and is a freelancer
            if (hasattr(request.user, 'profile') and 
                request.user.profile.user_type == 'freelancer'):
                
                # Try to get the freelancer profile
                freelancer_profile = getattr(request.user.profile, 'freelancer_profile', None)
                if freelancer_profile:
                    recommended_jobs = recommend_jobs_to_freelancer(freelancer_profile)
                    
        except (AttributeError, Exception) as e:
            # Handle any profile-related errors gracefully
            recommended_jobs = []
        
        categories = dict(Job.CATEGORY_CHOICES)
        return render(request, 'jobs.html', {
            'jobs': jobs,
            'categories': categories,
            'selected_category': category,
            'recommended_jobs': recommended_jobs
        })
    
    return redirect('accounts:login')

@login_required
def singlejob(request, job_id):
    job = get_object_or_404(Job.objects.annotate(num_responses=Count('responses')), pk=job_id)
    
    if job.num_responses >= job.max_freelancers:
        messages.error(request, 'This job has reached the maximum number of freelancers.')
        return redirect('core:jobs')
    
    if job.responses.filter(user=request.user).exists():
        messages.warning(request, 'You have already submitted a response for this job.')
        return redirect('core:jobs')
    
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
    return render(request, 'single-job.html', {
        'job': job,
        'form': form,
        'responses': responses
    })

@login_required
def freelancer_jobs(request):
    try:
        freelancer_profile = Profile.objects.get(user=request.user, user_type='freelancer')
    except Profile.DoesNotExist:
        # If no freelancer profile exists, redirect to profile creation
        return redirect('accounts:profile_creation')  # Adjust URL name as needed
    
    freelancer_jobs = Job.objects.filter(responses__user=request.user)
    
    # Add recommended jobs only if freelancer profile exists
    recommended_jobs = []
    if hasattr(freelancer_profile, 'freelancer_profile'):
        try:
            # Check if the freelancer_profile actually exists
            freelancer_detail = freelancer_profile.freelancer_profile
            recommended_jobs = recommend_jobs_to_freelancer(freelancer_detail)
        except Profile.freelancer_profile.RelatedObjectDoesNotExist:
            # FreelancerProfile doesn't exist yet
            recommended_jobs = []
    
    # Add review status for each job
    jobs_with_review_status = []
    for job in freelancer_jobs:
        has_rated = job.client.user.reviews_received.filter(reviewer=request.user).exists()
        jobs_with_review_status.append({
            'job': job,
            'has_rated': has_rated
        })
    
    context = {
        'freelancer_jobs': jobs_with_review_status,
        'recommended_jobs': recommended_jobs,
        'user': request.user,
        'profile_incomplete': not hasattr(freelancer_profile, 'freelancer_profile') if 'freelancer_profile' in locals() else True
    }
    
    return render(request, 'freelancer_jobs.html', context)
    
@login_required
def about(request):
    return render(request, 'about.html')

@login_required
def contact(request):
    if request.method == "POST":
        name = request.POST.get('name')
        message_email = request.POST.get('message_email')
        message = request.POST.get('message')

        send_mail(
            'Contact Form Submission from {}'.format(name),
            'From: {}\n{}'.format(message_email, message),
            'info@nilltechsolutions.com',  
            ['info@nilltechsolutions.com'],  
            fail_silently=False,
        )
        messages.success(request, 'Your message has been sent. Thank you!')
        return HttpResponseRedirect(reverse('core:contact'))  
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

        try:
            send_mail(
                'Contact Form Submission', 
                f'Name: {name}\nEmail: {email}\n\nMessage: {message}', 
                'info@nilltechsolutions.com',  
                ['info@nilltechsolutions.com'],  
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
    return redirect('accounts:login')

@login_required
@user_passes_test(is_client)
def create_job(request):
    if request.method == 'POST':
        form = CreateJobForm(request.POST)
        if form.is_valid():
            # Save the job without payment verification
            job = form.save(commit=False)
            job.client = request.user.profile
            job.status = 'open'  # Ensure status is set to open
            job.save()
            
            messages.success(request, 'Job posted successfully!')
            return redirect('core:client_posted_jobs')
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
    
    # Remove payment verification filter
    client_jobs = client_profile.jobs.all()
    
    if category:
        client_jobs = client_jobs.filter(category=category)
    
    # Add matched freelancers (only those who responded) for each job
    for job in client_jobs:
        job.matched_freelancers = match_freelancers_to_job(job)
    
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
    
    # Add review status for each response
    responses_with_review_status = []
    for response in responses:
        has_rated = response.user.reviews_received.filter(reviewer=request.user).exists() if response.user else False
        responses_with_review_status.append({
            'response': response,
            'has_rated': has_rated
        })
    
    # Pass responses with extra_data to the template
    context = {
        'job': job,
        'responses': responses_with_review_status,
        'user': request.user  # Ensure user is passed for template checks
    }
    return render(request, 'job_responses.html', context)

@login_required
@user_passes_test(lambda u: u.profile.user_type == 'client')
def client_responses(request):
    client_profile = Profile.objects.get(user=request.user, user_type='client')
    client_jobs = client_profile.jobs.all()
    responses = Response.objects.filter(job__in=client_jobs)
    
    # Add review status for each response
    responses_with_review_status = []
    for response in responses:
        has_rated = response.user.reviews_received.filter(reviewer=request.user).exists() if response.user else False
        responses_with_review_status.append({
            'response': response,
            'has_rated': has_rated
        })
    
    return render(request, 'job_responses.html', {
        'responses': responses_with_review_status,
        'user': request.user
    })

@login_required
@user_passes_test(lambda u: u.profile.user_type == 'client')
def accept_response(request, job_id, response_id):
    if request.method == 'POST':
        try:
            # Fetch the specific response and associated job
            response = get_object_or_404(Response, id=response_id, job_id=job_id)
            job = response.job
            
            # Check if this user is the job owner
            if job.client.user != request.user:
                return JsonResponse({
                    'status': 'error',
                    'message': 'You are not authorized to accept responses for this job.'
                })
            
            # Get the client and freelancer profiles
            client_profile = request.user.profile  # The logged-in client
            freelancer_profile = response.user.profile  # The freelancer who submitted the response
            
            # Create a new chat for communication
            chat = Chat.objects.create(
                job=job,
                client=client_profile,  # Set the client
                freelancer=freelancer_profile  # Set the freelancer
            )
            
            # Update job to mark selected freelancer
            job.selected_freelancer = response.user
            job.status = 'in_progress'
            job.save()
            
            return JsonResponse({
                'status': 'success',
                'chat_id': chat.id,
                'message': 'Response accepted successfully'
            })
            
        except Exception as e:
            # Log the error and return an error response
            logger.error(f"Error in accept_response: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'An unexpected error occurred. Please try again.'
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method.'
    })

@login_required
@user_passes_test(is_client)
def reject_response(request, job_id, response_id):
    """
    Handle rejection of a job response.
    This frees up a slot for another freelancer to apply.
    """
    # Check if request method is POST
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    job = get_object_or_404(Job, pk=job_id)
    response = get_object_or_404(Response, pk=response_id, job=job)
    
    # Ensure the user is the client who posted the job
    if job.client.user != request.user:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        # Delete the response to free up the slot
        response.delete()
        
        # Make sure to get the fresh count after deletion
        job.refresh_from_db()  # Refresh the job object to get the latest data
        remaining_slots = job.max_freelancers - job.responses.count()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Response rejected successfully',
            'remaining_slots': remaining_slots
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

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
    
@login_required
@user_passes_test(is_client)
def job_matches(request, job_id):
    job = get_object_or_404(Job, pk=job_id, client__user=request.user)
    matches = match_freelancers_to_job(job, max_matches=10)
    
    return render(request, 'job_matches.html', {
        'job': job,
        'matches': matches
    })


def download_response_file(request, response_id, filename):
    """
    View to handle downloading of response attachments
    """
    # Get the response object
    response = get_object_or_404(Response, id=response_id)
    
    # Get the associated job
    job = response.job
    
    # Check if user has permission to download
    # Allow access if user is:
    # 1. Staff member
    # 2. Freelancer who submitted the response
    # 3. Client who posted the job (through Profile)
    is_client = hasattr(request.user, 'profile') and request.user.profile == job.client
    
    if not (request.user.is_staff or 
            request.user == response.user or 
            is_client):
        raise Http404("You don't have permission to access this file")
    
    # Get file path from extra_data
    if 'sample_work' in response.extra_data and 'path' in response.extra_data['sample_work']:
        file_path = response.extra_data['sample_work']['path']
        
        # Security check to ensure the requested filename matches
        if os.path.basename(file_path) != filename:
            raise Http404("File not found")
        
        # Check if file exists
        if os.path.exists(file_path) and os.path.isfile(file_path):
            # Return the file
            return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
    
    # File not found
    raise Http404("File not found")


@login_required
def create_review(request, username):
    recipient = get_object_or_404(User, username=username)
    
    # Prevent users from reviewing themselves
    if request.user == recipient:
        messages.error(request, "You cannot review yourself.")
        return redirect('accounts:freelancer_portfolio', recipient.id)
    
    # Check if the reviewer and recipient have a completed job together
    if request.user.profile.user_type == 'client':
        # Client reviewing freelancer
        has_completed_job = Job.objects.filter(
            client=request.user.profile,
            selected_freelancer=recipient,
            status='completed'
        ).exists()
    else:
        # Freelancer reviewing client
        has_completed_job = Job.objects.filter(
            client=recipient.profile,
            selected_freelancer=request.user,
            status='completed'
        ).exists()
    
    if not has_completed_job:
        messages.error(request, "You can only review users you have completed a job with.")
        return redirect('core:freelancer_jobs', recipient.id)
    
    # Check if review already exists
    existing_review = Review.objects.filter(reviewer=request.user, recipient=recipient).first()
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=existing_review)
        if form.is_valid():
            review = form.save(commit=False)
            review.reviewer = request.user
            review.recipient = recipient
            review.save()
            messages.success(request, "Your review has been saved.")
            return redirect('core:freelancer_jobs', recipient.id)
    else:
        form = ReviewForm(instance=existing_review)
    
    return render(request, 'create_review.html', {
        'form': form,
        'recipient': recipient,
        'is_update': existing_review is not None
    })

def user_reviews(request, username):
    user = get_object_or_404(User, username=username)
    reviews = Review.objects.filter(recipient=user).order_by('-created_at')
    
    # Calculate average rating
    avg_rating = reviews.aggregate(models.Avg('rating'))['rating__avg'] or 0
    
    return render(request, 'user_reviews.html', {  # Fixed template path
        'user_profile': user,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'review_count': reviews.count()
    })

@login_required
def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id, reviewer=request.user)
    
    if request.method == 'POST':
        username = review.recipient.username
        review.delete()
        messages.success(request, "Your review has been deleted.")
        # Change this redirect
        return redirect('core:index', review.recipient.id)
    
    return render(request, 'delete_review.html', {'review': review})  # Fixed template path

def index_gen(request):
    return render(request, 'index_gen.html')

def about_gen(request):
    return render(request, 'about_gen.html')

def contact_gen(request):
    return render(request, 'contact_gen.html')

