from django.contrib import admin
from django.contrib.auth.models import User

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import *


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

admin.site.register(FreelancerProfile)
admin.site.register(ClientProfile)

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('name',)