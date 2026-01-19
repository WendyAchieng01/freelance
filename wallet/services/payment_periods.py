from datetime import timedelta
from wallet.models import PaymentPeriod


def get_or_create_payment_period_for_date(date):
    """
    Weekly payment period (Monday → Sunday)
    """
    start = date - timedelta(days=date.weekday())
    end = start + timedelta(days=6)

    period, _ = PaymentPeriod.objects.get_or_create(
        start_date=start,
        end_date=end,
        defaults={
            "name": f"Week {start.isocalendar()[1]} ({start} → {end})"
        }
    )
    return period
