from django.db import transaction
from paypal.standard.ipn.signals import valid_ipn_received
from django.dispatch import receiver
from payments.models import PaypalPayments
from core.models import Job, Response as CoreResponse
from paypal.standard.models import ST_PP_COMPLETED


@receiver(valid_ipn_received)
def handle_ipn(sender, **kwargs):
    ipn_obj = kwargs.get('ipn')
    if not ipn_obj:
        print("No IPN object received")
        return

    print(
        f"[IPN] Received: invoice={ipn_obj.invoice}, status={ipn_obj.payment_status}")

    try:
        payment = PaypalPayments.objects.get(invoice=ipn_obj.invoice)
    except PaypalPayments.DoesNotExist:
        print(f"[IPN] No payment found for invoice={ipn_obj.invoice}")
        return

    extra_data = payment.extra_data or {}
    extra_data.update({
        "paypal_txn_id": getattr(ipn_obj, "txn_id", ""),
        "payer_email": getattr(ipn_obj, "payer_email", ""),
        "payment_status": ipn_obj.payment_status
    })

    # Begin atomic transaction to ensure consistency
    with transaction.atomic():
        if ipn_obj.payment_status.lower() == ST_PP_COMPLETED.lower():
            payment.status = "completed"
            payment.verified = True
            payment.extra_data = extra_data
            payment.save()

            job = payment.job
            response_id = extra_data.get("response_id")

            if response_id:
                try:
                    response = CoreResponse.objects.get(
                        id=response_id, job=job)
                    job.status = "open"
                    job.payment_verified = True
                    # job.selected_freelancer = response.user  # uncomment if needed
                    job.save()
                    print(
                        f"[IPN] Job {job.id} updated: payment verified, status open")
                except CoreResponse.DoesNotExist:
                    print(
                        f"[IPN] No CoreResponse found for response_id={response_id}")

            else:
                # Mark payment verified even without response_id
                job = payment.job
                job.payment_verified = True
                job.save()
                print(
                    f"[IPN] Job {job.id} updated: payment verified without response_id")

        elif ipn_obj.payment_status.lower() in ["failed", "denied", "canceled_reversal"]:
            payment.status = "failed"
            payment.verified = False
            payment.extra_data = extra_data
            payment.save()
            print(f"[IPN] Payment failed for invoice={payment.invoice}")

        else:
            # PayPal status
            payment.status = ipn_obj.payment_status.lower()
            payment.extra_data = extra_data
            payment.save()
            print(
                f"[IPN] Unhandled status: {ipn_obj.payment_status} for invoice={payment.invoice}")

