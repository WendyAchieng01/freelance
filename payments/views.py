from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from paypal.standard.forms import PayPalPaymentsForm
from django.dispatch import receiver
from paypal.standard.ipn.signals import valid_ipn_received
from paypal.standard.models import ST_PP_COMPLETED
from payment.models import Payment
from core.models import Job, Response, Chat
from django.http import HttpResponseRedirect
import logging
from django.contrib.auth.decorators import login_required

logger = logging.getLogger(__name__)

# View to initiate PayPal payment for accepting a response
def initiate_response_payment(request, job_id, response_id):
    job = get_object_or_404(Job, pk=job_id)
    response = get_object_or_404(Response, pk=response_id, job=job)

    # Check if the current user is the job owner
    if job.client.user != request.user:
        messages.error(request, "You are not authorized to accept this response.")
        return redirect('core:client_posted_jobs')

    # Create the PayPal form
    paypal_dict = {
        'business': 'sampleapp@gmail.com',
        'amount': job.price,
        'item_name': f"Accepting response for {job.title}",
        'invoice': f"response-{job_id}-{response_id}",
        'currency_code': 'USD',
        'notify_url': request.build_absolute_uri(reverse('payments:paypal-ipn')),
        'return_url': request.build_absolute_uri(reverse('payments:successful_response', args=[job_id, response_id])),
        'cancel_return': request.build_absolute_uri(reverse('payments:cancelled_response', args=[job_id, response_id])),
        'custom': str(response_id),  # Pass response_id in custom field for IPN
    }

    form = PayPalPaymentsForm(initial=paypal_dict)

    return render(request, 'purchase.html', {'job': job, 'form': form.render(), 'response_id': response_id})

# Success page after PayPal payment for response acceptance
@login_required
def successful_response(request, job_id, response_id):
    job = get_object_or_404(Job, id=job_id)
    response = get_object_or_404(Response, id=response_id, job=job)

    # Check if payment exists and is verified
    payments = Payment.objects.filter(job=job, extra_data={'response_id': str(response_id)})
    if payments.exists() and payments.first().verified:
        chat = Chat.objects.filter(job=job, freelancer=response.user.profile).first()
        if chat:
            messages.success(request, "Payment successful! You can now chat with the freelancer.")
            return redirect('core:chat_room', chat_id=chat.id)
        else:
            # Create chat if it doesn't exist (fallback in case IPN hasn't run yet)
            chat = Chat.objects.create(
                job=job,
                client=job.client,
                freelancer=response.user.profile
            )
            job.selected_freelancer = response.user
            job.status = 'in_progress'
            job.save()
            messages.success(request, "Payment successful! Chat created.")
            return redirect('core:chat_room', chat_id=chat.id)
    
    # If payment isn't verified yet, show a "processing" message
    messages.info(request, "Payment is being processed. Please wait a moment or click 'Verify Payment' to check again.")
    return render(request, 'successful.html', {
        'job': job,
        'job_id': job_id,
        'response_id': response_id
    })

# Cancelled page after PayPal payment
def cancelled_response(request, job_id, response_id):
    job = get_object_or_404(Job, id=job_id)
    return render(request, 'cancelled.html', {'job': job, 'job_id': job_id, 'response_id': response_id})

@receiver(valid_ipn_received)
def payment_successful(sender, **kwargs):
    ipn_obj = sender
    logger.debug(f"IPN received: payment_status={ipn_obj.payment_status}, invoice={ipn_obj.invoice}")
    
    if ipn_obj.payment_status == ST_PP_COMPLETED:
        try:
            invoice_parts = ipn_obj.invoice.split('-')
            if len(invoice_parts) != 3 or invoice_parts[0] != 'response':
                logger.debug(f"Invalid invoice format: {ipn_obj.invoice}")
                return
            
            job_id = invoice_parts[1]
            response_id = invoice_parts[2]
            
            job = get_object_or_404(Job, id=job_id)
            response = get_object_or_404(Response, id=response_id, job=job)
            
            # Create or update payment
            payment, created = Payment.objects.get_or_create(
                job=job,
                invoice=ipn_obj.invoice,
                defaults={
                    'amount': job.price,
                    'email': ipn_obj.payer_email,
                    'user': job.client.user,
                    'verified': True,
                    'extra_data': {'response_id': response_id}
                }
            )
            if not created:
                payment.verified = True
                payment.save()
            
            logger.debug(f"Payment {'created' if created else 'updated'}: id={payment.id}, verified={payment.verified}, extra_data={payment.extra_data}")
            
            # Create chat
            chat, chat_created = Chat.objects.get_or_create(
                job=job,
                client=job.client,
                freelancer=response.user.profile
            )
            
            job.selected_freelancer = response.user
            job.status = 'in_progress'
            job.save()
            
            logger.info(f"Payment successful for job {job_id}, response {response_id}. Chat {'created' if chat_created else 'already existed'} with ID {chat.id}")
        
        except Exception as e:
            logger.error(f"Error processing PayPal IPN: {str(e)}")
            raise
    else:
        logger.debug(f"IPN not completed: status={ipn_obj.payment_status}")

@login_required
def verify_payment(request, job_id, response_id):
    job = get_object_or_404(Job, id=job_id)
    response = get_object_or_404(Response, id=response_id, job=job)
    
    # Ensure the user is the job owner
    if job.client.user != request.user:
        messages.error(request, "You are not authorized to verify this payment.")
        return redirect('core:client_posted_jobs')
    
    if request.method == 'POST':
        # Check for payment
        payments = Payment.objects.filter(job=job, extra_data={'response_id': str(response_id)})
        if not payments.exists():
            logger.error(f"No payment found for job {job_id}, response {response_id}")
            messages.error(request, "No payment found for this job and response. Please try again later.")
            return redirect('payments:successful_response', job_id=job_id, response_id=response_id)
        
        payment = payments.first()
        if payment.verified:
            # Payment is verified, ensure chat exists
            chat, created = Chat.objects.get_or_create(
                job=job,
                client=job.client,
                freelancer=response.user.profile
            )
            if created:
                job.selected_freelancer = response.user
                job.status = 'in_progress'
                job.save()
                logger.info(f"Chat created for job {job_id}, response {response_id}, chat_id {chat.id}")
            
            messages.success(request, "Payment verified! You can now chat with the freelancer.")
            return redirect('core:chat_room', chat_id=chat.id)
        else:
            logger.info(f"Payment for job {job_id}, response {response_id} exists but not verified yet")
            messages.info(request, "Payment is still being processed. Please wait a moment.")
            return redirect('payments:successful_response', job_id=job_id, response_id=response_id)
    
    # If GET request, redirect to success page to show status
    return redirect('payments:successful_response', job_id=job_id, response_id=response_id)