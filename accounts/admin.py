from django.contrib import admin
from django.contrib.auth.models import User
from .models import Profile
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin


admin.site.register(Profile)

# Mix Profile Info and User Info
class ProfileInline(admin.StackedInline):
    model = Profile

# Extend User Model
class CustomUserAdmin(BaseUserAdmin):
    model = User
    inlines = [ProfileInline]

# Unregister the old UserAdmin
admin.site.unregister(User)
# Register the new CustomUserAdmin
admin.site.register(User, CustomUserAdmin)