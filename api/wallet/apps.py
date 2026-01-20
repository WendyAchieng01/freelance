from django.apps import AppConfig


class WalletConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.wallet'

    def ready(self):
        pass
        #import api.wallet.signals  # Connect signals
