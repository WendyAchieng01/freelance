from .paystack import PaystackGateway
from .paypal import PayPalGateway


def get_payout_gateway(provider: str):
    if provider == "paystack":
        return PaystackGateway()
    raise ValueError("Unknown payout provider")
