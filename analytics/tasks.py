from django.utils import timezone
from analytics.models import ComprehensiveAnalytics

def run_daily_analytics_update():
    """
    A task function that Django-Q can call to update the daily analytics snapshots.
    """
    today = timezone.now().date()
    print(f"Running daily analytics update for {today}...")
    try:
        ComprehensiveAnalytics.update_all_analytics(date=today)
        print("Successfully updated analytics.")
    except Exception as e:
        print(f"An error occurred during the analytics update: {e}")
        # Depending on desired behavior, you might want to log this error
        # to a more persistent logging service.
