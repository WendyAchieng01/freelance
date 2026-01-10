# payments/gateways/base.py
from abc import ABC, abstractmethod


class BaseGateway(ABC):

    provider_name: str

    @abstractmethod
    def payout(self, wallet_tx, idempotency_key: str = None):
        """
        Execute a single payout for wallet_tx (WalletTransaction instance).
        Should return a dict with at least:
            { "success": bool, "provider_ref": str|null, "raw": {...}, "error": str|null }
        """
        raise NotImplementedError()

    @abstractmethod
    def verify_webhook(self, headers, body) -> bool:
        """Verify webhook authenticity for this provider."""
        raise NotImplementedError()



