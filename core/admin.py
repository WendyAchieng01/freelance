from django.contrib import admin

from core.models import *

# Register your models here.
admin.site.register(Job)
admin.site.register(Response)
admin.site.register(Chat)
admin.site.register(Message)
admin.site.register(MessageAttachment)