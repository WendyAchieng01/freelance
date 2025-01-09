from django.contrib import admin

from core.models import *

# Register your models here.
admin.site.register(Job)
admin.site.register(Response)
admin.site.register(JobAttempt)
admin.site.register(Chat)
admin.site.register(Message)