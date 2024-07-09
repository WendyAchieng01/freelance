from django.contrib import admin
from .models import Invoice, InvoiceLineItem

# Register your models here.
admin.site.register(Invoice)
admin.site.register(InvoiceLineItem)