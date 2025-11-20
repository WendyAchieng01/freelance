# analytics/views.py
import json
from decimal import Decimal
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from django.contrib.auth import get_user_model
from accounts.models import Profile, Skill
from core.models import Job
from payment.models import Payment
from wallet.models import WalletTransaction

User = get_user_model()

# Custom JSON encoder to handle Decimal


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


@staff_member_required
def analytics_dashboard(request):
    now = timezone.now()



    context = {
        now : 'now'
    }

    return render(request, 'admin/analytics_dashboard.html', context)
