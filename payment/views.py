from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from core.forms import CreateJobForm
from .models import Payment
from django.conf import settings
from core.models import Job
from accounts.models import Profile

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
        print(request.user.username, " funded wallet successfully")
        return redirect('core:client_posted_jobs')
    return render(request, "success.html")
