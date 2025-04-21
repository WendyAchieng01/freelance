from django.db import models
from django.contrib.auth.models import User
import secrets
from .paystack import Paystack
from core.models import Job 

class Payment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    amount = models.PositiveIntegerField()
    ref = models.CharField(max_length=200)
    email = models.EmailField()
    verified = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='payment') 
    extra_data = models.JSONField(default=dict, blank=True, null=True)

    class Meta:
        ordering = ('-date_created',)

    def __str__(self):
        return f"Payment of {self.amount} for {self.job.title} by {self.user.username}"

    def save(self, *args, **kwargs):
        while not self.ref:
            ref = secrets.token_urlsafe(50)
            object_with_similar_ref = Payment.objects.filter(ref=ref)
            if not object_with_similar_ref:
                self.ref = ref

        super().save(*args, **kwargs)
    
    def amount_value(self):
        return int(self.amount) * 100

    def verify_payment(self):
        paystack = Paystack()
        status, result = paystack.verify_payment(self.ref, self.amount)
        if status:
            if result['amount'] / 100 == self.amount:
                self.verified = True
                # Add job reference if payment is verified
                if self.job:
                    self.job.status = 'open'
                    self.job.save()
            self.save()
        if self.verified:
            return True
        return False
