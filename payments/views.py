from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from paypal.standard.forms import PayPalPaymentsForm
from django.dispatch import receiver
from paypal.standard.ipn.signals import valid_ipn_received
from core.models import Job
from paypal.standard.models import ST_PP_COMPLETED
from payment.models import Payment
from django.http import HttpResponseRedirect


def job_purchase(request, job_id):
    job = get_object_or_404(Job, id=job_id)

    # Create the PayPal form
    paypal_dict = {
        'business': 'sampleapp@gmail.com',
        'amount': job.price,
        'item_name': job.title,
        'invoice': f"invoice1-{job_id}",
        'currency_code': 'USD',
        'notify_url': request.build_absolute_uri(reverse('payments:paypal-ipn')),
        'return_url': request.build_absolute_uri(reverse('payments:successful', args=[job_id])),
        'cancel_return': request.build_absolute_uri(reverse('payments:cancelled', args=[job_id])),
    }

    form = PayPalPaymentsForm(initial=paypal_dict)

    # Render the form in the template
    return render(request, 'purchase.html', {'job': job, 'form': form.render()})

def successful(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    return render(request, 'successful.html', {'job': job, 'job_id': job_id})

def cancelled(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    return render(request, 'cancelled.html', {'job': job, 'job_id': job_id})

@receiver(valid_ipn_received)
def payment_successful(sender, **kwargs):
    ipn_obj = sender
    if ipn_obj.payment_status == ST_PP_COMPLETED:
        # Payment was successful, mark the job as open
        job = get_object_or_404(Job, id=ipn_obj.invoice.split('-')[-1])
        payment = Payment.objects.create(job=job, amount=job.price, verified=True)
        job.status = 'open'
        job.save()



def verify_payment(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    payments = Payment.objects.filter(job=job)
    if payments.exists():
        payment = payments.first()
        print(payment.verified)  # Check the initial value of verified
        payment.verified = True
        payment.save(update_fields=['verified'])
        print(payment.verified)  # Check the updated value of verified
    return redirect(reverse('core:client_posted_jobs'))
