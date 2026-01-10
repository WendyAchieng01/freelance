from django.core.management.base import BaseCommand
from django.utils import timezone
from analytics.models import ComprehensiveAnalytics

class Command(BaseCommand):
    help = 'Updates all analytics models with the latest data for the current day.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting analytics update process...'))
        
        try:
            today = timezone.now().date()
            ComprehensiveAnalytics.update_all_analytics(date=today)
            self.stdout.write(self.style.SUCCESS(f'Successfully updated analytics for {today}.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred during the analytics update: {e}'))
            # Optionally re-raise the exception if you want the command to fail explicitly
            # raise e
