from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Profile, FreelancerProfile, ClientProfile,
    Skill, Language, PortfolioProject
)

# INLINE PROFILES FOR USER ADMIN


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Profile Information"
    fk_name = 'user'
    extra = 0
    fieldsets = (
        ("Basic Info", {
            "fields": ("phone", "location", "bio", "profile_pic", "email_verified")
        }),
        ("Account Details", {
            "fields": ("user_type", "id_card", "pay_id", "device")
        }),
    )


# Attach profile information inside the Django User admin
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)

    list_display = (
        "username", "email", "first_name", "last_name",
        "get_user_type", "get_phone", "get_location",
        "is_staff", "is_active",
    )

    list_select_related = ("profile",)

    search_fields = ("username", "email",
                     "profile__phone", "profile__location")
    list_filter = ("profile__user_type", "is_staff",
                   "is_superuser", "profile__email_verified")

    def get_user_type(self, obj):
        return obj.profile.user_type
    get_user_type.short_description = "User Type"

    def get_phone(self, obj):
        return obj.profile.phone
    get_phone.short_description = "Phone"

    def get_location(self, obj):
        return obj.profile.location
    get_location.short_description = "Location"


admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# SKILL & LANGUAGE ADMIN


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


# FREELANCER PROFILE

class FreelancerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "profile",
        "hourly_rate",
        "availability",
        "is_visible",
        "slug",
    )
    search_fields = (
        "profile__user__username",
        "profile__user__first_name",
        "profile__user__last_name",
    )
    list_filter = ("availability", "is_visible")
    readonly_fields = ("slug", "portfolio_link")

    filter_horizontal = ("skills", "languages")

    fieldsets = (
        ("Basic Info", {
            "fields": ("profile", "slug", "portfolio_link")
        }),
        ("Professional Details", {
            "fields": (
                "skills", "languages", "experience_years",
                "hourly_rate", "availability"
            )
        }),
        ("Visibility", {
            "fields": ("is_visible",)
        })
    )


admin.site.register(FreelancerProfile, FreelancerProfileAdmin)


# CLIENT PROFILE

class ClientProfileAdmin(admin.ModelAdmin):
    list_display = (
        "profile",
        "company_name",
        "industry",
        "is_verified",
        "slug",
    )
    search_fields = (
        "profile__user__username",
        "company_name",
        "industry",
    )
    list_filter = ("industry", "is_verified")
    readonly_fields = ("slug",)

    filter_horizontal = ("languages",)

    fieldsets = (
        ("Basic Info", {
            "fields": ("profile", "company_name", "company_website", "industry")
        }),
        ("Preferences", {
            "fields": ("project_budget", "preferred_freelancer_level", "languages")
        }),
        ("Verification", {
            "fields": ("is_verified", "slug")
        }),
    )


admin.site.register(ClientProfile, ClientProfileAdmin)


# PORTFOLIO PROJECT ADMIN

class PortfolioProjectAdmin(admin.ModelAdmin):
    list_display = (
        "project_title",
        "user",
        "role",
        "created_at",
        "slug",
    )
    search_fields = ("project_title", "user__username")
    list_filter = ("created_at",)

    readonly_fields = ("slug",)

    fieldsets = (
        ("Project Info", {
            "fields": ("user", "freelancer", "project_title", "role", "description")
        }),
        ("Media", {
            "fields": ("project_media", "link")
        }),
        ("System", {
            "fields": ("slug",)
        })
    )


admin.site.register(PortfolioProject, PortfolioProjectAdmin)
