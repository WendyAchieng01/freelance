from django.contrib import admin
from django.contrib.auth.models import User
from django.urls import reverse
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
    

@admin.register(PortfolioProject)
class PortfolioProjectAdmin(admin.ModelAdmin):
    list_display = ("project_title", "role", "user", "created_at")
    list_filter = ("created_at", "role", "user")
    search_fields = ("project_title", "role", "description", "user__username")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Project Details", {
            "fields": ("user", "project_title", "role", "description", "link", "project_media")
        }),
        ("Metadata", {
            "fields": ("created_at",),
        }),
    )
