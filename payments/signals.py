from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PaypalPayments
from paypal.standard.ipn.signals import valid_ipn_received
from paypal.standard.models import ST_PP_COMPLETED
from core.models import Job, Response as CoreResponse, Chat


@receiver(post_save, sender=PaypalPayments)
def log_payment_creation(sender, instance, created, **kwargs):
    print(
        f"PaypalPayments post_save: created={created}, invoice={instance.invoice}")


@receiver(valid_ipn_received)
def handle_ipn(sender, **kwargs):
    ipn_obj = sender
    print(
        f"Received IPN: invoice={ipn_obj.invoice}, status={ipn_obj.payment_status}")
    invoice = ipn_obj.invoice
    try:
        payment = PaypalPayments.objects.get(invoice=invoice)
    except PaypalPayments.DoesNotExist:
        print(f"No payment found for invoice={invoice}")
        return

    if ipn_obj.payment_status == ST_PP_COMPLETED:
        print(f"Processing completed payment for invoice={invoice}")
        payment.status = 'completed'
        payment.verified = True
        payment.save()

        # Update job status
        job = payment.job
        response_id = payment.extra_data.get('response_id')
        if response_id:
            try:
                response = CoreResponse.objects.get(id=response_id, job=job)
                job.status = 'open'
                job.payment_verified = True
                #job.selected_freelancer = response.user
                job.save()

                print(f"Updated job {job.id} to payment verified, created chat")
            except CoreResponse.DoesNotExist:
                print(f"No valid CoreResponse for response_id={response_id}")
    elif ipn_obj.payment_status == 'Failed':
        print(f"Processing failed payment for invoice={invoice}")
        payment.status = 'failed'
        payment.save()
    else:
        print(f"Unhandled IPN status: {ipn_obj.payment_status}")
