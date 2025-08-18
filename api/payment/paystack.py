from django.conf import settings
import requests


class Paystack:
    PAYSTACK_SK = settings.PAYSTACK_SECRET_KEY
    base_url = "https://api.paystack.co/"

    def verify_payment(self, ref, *args, **kwargs):
        path = f"transaction/verify/{ref}"
        headers = {
            "Authorization": f"Bearer {self.PAYSTACK_SK}",
            "Content-Type": "application/json",
        }
        url = self.base_url + path
        response = requests.get(url, headers=headers)

        response_data = response.json()

        if response.status_code == 200 and response_data.get("status"):
            # Successful API call
            return True, response_data.get("data", {})
        else:
            # Failed API call
            return False, {
                "message": response_data.get("message", "Verification failed"),
                "data": response_data.get("data", {}),
            }

    def initialize_transaction(self, email, amount, reference, callback_url):
        path = "transaction/initialize"
        headers = {
            "Authorization": f"Bearer {self.PAYSTACK_SK}",
            "Content-Type": "application/json",
        }
        data = {
            "email": email,
            "amount": amount,
            "reference": reference,
            "callback_url": callback_url,
        }
        url = self.base_url + path
        response = requests.post(url, headers=headers, json=data)

        response_data = response.json()

        if response.status_code == 200 and response_data.get("status"):
            return True, response_data.get("data", {})
        else:
            return False, {
                "message": response_data.get("message", "Initialization failed"),
                "data": response_data.get("data", {}),
            }
