from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from core.forms import CreateJobForm
from .models import Payment
from django.conf import settings
from core.models import Chat, Job, Response
from accounts.models import Profile
from django.contrib import messages


def initiate_response_payment(request, job_id, response_id):
    # Fetch the job and response
    job = get_object_or_404(Job, pk=job_id)
    response = get_object_or_404(Response, pk=response_id, job=job)
    
    # Check if the current user is the job owner
    if job.client.user != request.user:
        messages.error(request, "You are not authorized to accept this response.")
        return redirect('core:client_posted_jobs')
    
    # Calculate payment amount (using job budget)
    amount = job.price
    email = request.user.email
    
    # Create payment object
    payment = Payment(
        amount=amount, 
        email=email, 
        user=request.user,
        job=job,
        extra_data={'response_id': response_id}  # Store response ID in extra_data
    )
    payment.save()
    
    context = {
        'payment': payment,
        'paystack_pub_key': settings.PAYSTACK_PUBLIC_KEY,
        'amount_value': payment.amount_value(),
        'job_id': job.id,
        'response_id': response_id
    }
    return render(request, 'make_payment.html', context)

@login_required
def initiate_payment(request, amount, email, job_form):
    if request.method == "POST":
        payment = Payment(amount=amount, email=email, user=request.user)
        job = job_form.save(commit=False)  # Save job instance
        job.client = Profile.objects.get(user=request.user, user_type='client')  # Assign client
        job.save()
        
        payment.job = job
        payment.save()

        context = {
            'payment': payment,
            'paystack_pub_key': settings.PAYSTACK_PUBLIC_KEY,
            'amount_value': payment.amount_value(),
            'job_id': job.id,  # Add the job_id to the context
        }
        return render(request, 'make_payment.html', context)

    context = {
        'amount': amount,
        'email': email,
        'paystack_pub_key': settings.PAYSTACK_PUBLIC_KEY,
        'amount_value': amount * 100,
        'job_form': job_form,
    }
    return render(request, 'initiate_payment.html', context)

@login_required
def verify_payment(request, ref):
    payment = Payment.objects.get(ref=ref)
    verified = payment.verify_payment()

    if verified:
        print(f"{request.user.username} paid successfully")
        
        # Check if this is a payment for accepting a job response
        if payment.job and 'response_id' in payment.extra_data:
            response_id = payment.extra_data['response_id']
            job_id = payment.job.id
            
            # Call the accept_response view via an internal POST request
            from django.http import HttpRequest
            from django.middleware.csrf import get_token
            
            # Create a new request object
            post_request = HttpRequest()
            post_request.method = 'POST'
            post_request.user = request.user
            post_request.META = request.META.copy()
            
            # Add CSRF token
            post_request.META['CSRF_COOKIE'] = get_token(request)
            
            # Process the acceptance
            from core.views import accept_response
            response = accept_response(post_request, job_id, response_id)
            
            # Parse the response
            import json
            result = json.loads(response.content.decode('utf-8'))
            
            if result['status'] == 'success':
                messages.success(request, "Payment successful! You can now chat with the freelancer.")
                return redirect('core:chat_room', chat_id=result['chat_id'])
            else:
                messages.error(request, f"Payment successful but couldn't accept response: {result['message']}")
                return redirect('core:client_posted_jobs')
        
        # Default redirect for other payment types
        messages.success(request, "Payment successful!")
        return redirect('core:client_posted_jobs')
    
    messages.error(request, "Payment verification failed.")
    return render(request, "payment/payment_failed.html")