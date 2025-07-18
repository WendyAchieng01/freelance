from django.conf import settings
import requests


class Paystack:
    PAYSTACK_SK = settings.PAYSTACK_SECRET_KEY
    base_url = "https://api.paystack.co/"

    def verify_payment(self, ref, *args, **kwargs):
        path = f'transaction/verify/{ref}'
        headers = {
            "Authorization": f"Bearer {self.PAYSTACK_SK}",
            "Content-Type": "application/json",
        }
        url = self.base_url + path
        response = requests.get(url, headers=headers)

        print(
            f"\n\nTransaction with ref: {ref} has a response {response} and status_code of {response.status_code}\n\n")

        if response.status_code == 200:
            response_data = response.json()
            return response_data['status'], response_data['data']

        response_data = response.json()
        return response_data['status'], response_data['message']

    def initialize_transaction(self, email, amount, reference, callback_url):
        path = 'transaction/initialize'
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

        if response.status_code == 200:
            response_data = response.json()
            return response_data['status'], response_data['data']
        else:
            response_data = response.json()
            return response_data['status'], response_data['message']
