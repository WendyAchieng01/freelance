from django.contrib import admin
from django.conf import settings
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse, path
from django.utils.html import format_html
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.core.exceptions import PermissionDenied
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Profile, FreelancerProfile, ClientProfile,
    Skill, Language, PortfolioProject,ContactUs
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
            "fields": ("user_type", "id_card", "pay_id", "paystack_recipient", "mobile_money_provider", "device")
        }),
    )
    readonly_fields = ("paystack_recipient","mobile_money_provider",)


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


class ResponseFilter(admin.SimpleListFilter):
    title = 'response status'
    parameter_name = 'response_status'

    def lookups(self, request, model_admin):
        return (
            ('responded', 'Responded'),
            ('not_responded', 'Not Responded'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'responded':
            return queryset.filter(responded=True)
        if self.value() == 'not_responded':
            return queryset.filter(responded=False)


@admin.register(ContactUs)
class ContactUsAdmin(admin.ModelAdmin):

    list_display = [
        'name', 'email', 'subject', 'contact_type', 'priority_badge',
        'timestamp', 'status_badge', 'quick_actions'
    ]

    list_filter = [ResponseFilter, 'contact_type',
                   'priority', 'is_read', 'timestamp']

    # IF your model field is response_text, change below.
    search_fields = ['name', 'email', 'subject', 'message', 'response']

    readonly_fields = [
        'timestamp', 'submission_token', 'ip_address', 'user_agent',
        'referrer', 'response_sent', 'response_sent_at', 'responded_at',
        'status_display', 'response_preview', 'response_field', 'send_response_email'
    ]

    fieldsets = (
        ('Contact Information', {
            'fields': ('name', 'email', 'phone', 'subject', 'message', 'contact_type')
        }),
        ('Admin Management', {
            'fields': ('priority', 'is_read', 'is_archived', 'admin_notes')
        }),
        ('Response Management', {
            'fields': ('responded', 'responded_at', 'responded_by')
        }),
        ('Submission Details', {
            'fields': ('timestamp', 'ip_address', 'user_agent', 'referrer', 'submission_token'),
            'classes': ('collapse',)
        }),
        ('Status & Preview', {
            'fields': ('status_display', 'response_preview', 'send_response_email'),
            'classes': ('collapse',)
        }),
        ('Write Response (Admin Only)', {
            'fields': ('response_field',)
        }),
    )

    actions = [
        'mark_as_responded', 'mark_as_read', 'mark_as_unread',
        'archive_selected', 'set_priority_low', 'set_priority_normal',
        'set_priority_high', 'set_priority_urgent'
    ]

    # BADGES
    def priority_badge(self, obj):
        color = {
            'low': '#17a2b8',
            'normal': '#6c757d',
            'high': '#ffc107',
            'urgent': '#dc3545',
        }.get(obj.priority, '#6c757d')

        return format_html(
            '<span style="background-color:{};color:white;padding:4px 8px;'
            'border-radius:12px;font-size:11px;font-weight:bold;">{}</span>',
            color, obj.get_priority_display().upper()
        )

    def status_badge(self, obj):
        if obj.responded:
            color, text = '#28a745', 'RESPONDED'
        elif obj.is_read:
            color, text = '#17a2b8', 'READ'
        else:
            color, text = '#ffc107', 'NEW'

        return format_html(
            '<span style="background-color:{};color:white;padding:4px 8px;'
            'border-radius:12px;font-size:11px;font-weight:bold;">{}</span>',
            color, text
        )

    # QUICK ACTION BUTTONS
    def quick_actions(self, obj):

        buttons = []

        if not obj.is_read:
            url = reverse('admin:contactus_mark_read', args=[obj.id])
            buttons.append(
                f'<a href="{url}" style="background:#17a2b8;color:white;'
                f'padding:4px 8px;border-radius:4px;text-decoration:none;'
                f'margin-right:5px;">Mark Read</a>'
            )

        if not obj.responded:
            url = reverse('admin:contactus_respond', args=[obj.id])
            buttons.append(
                f'<a href="{url}" style="background:#28a745;color:white;'
                f'padding:4px 8px;border-radius:4px;text-decoration:none;">Respond</a>'
            )

        return format_html(' '.join(buttons)) if buttons else '-'

    quick_actions.short_description = "Actions"

    # CUSTOM DISPLAY FIELDS
    def response_field(self, obj):
        """HTML textarea for writing admin response"""
        return format_html(
            '<textarea name="response_text" '
            'style="width:100%;height:200px;padding:10px;border:2px solid #dee2e6;'
            'border-radius:6px;">{}</textarea>',
            obj.response or ""
        )

    def response_preview(self, obj):
        if obj.response:
            preview = obj.response[:100] + \
                "..." if len(obj.response) > 100 else obj.response
            return format_html(
                '<div style="background:#f8f9fa;padding:10px;border-radius:4px;'
                'border-left:4px solid #007bff;font-size:14px;">{}</div>',
                preview
            )
        return "-"

    def status_display(self, obj):
        return obj.get_status_display()

    def send_response_email(self, obj):
        if obj.responded and obj.response:
            stamp = obj.response_sent_at.strftime(
                '%Y-%m-%d %H:%M') if obj.response_sent_at else "Unknown"
            return format_html(
                '<div style="background:#d4edda;padding:10px;border-radius:4px;'
                'border:1px solid #c3e6cb;"><strong>Email Sent:</strong> {}<br>'
                '<small>Response was emailed to the user.</small></div>',
                stamp
            )
        return "-"

    # CUSTOM ADMIN URLS
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/mark-read/', self.admin_site.admin_view(self.mark_read_view),
                 name='contactus_mark_read'),
            path('<path:object_id>/respond/', self.admin_site.admin_view(self.respond_view),
                 name='contactus_respond'),
        ]
        return custom_urls + urls

    # ACTION VIEWS
    def mark_read_view(self, request, object_id):
        if not request.user.is_staff:
            raise PermissionDenied()

        contact = ContactUs.objects.get(id=object_id)
        contact.is_read = True
        contact.save()

        self.message_user(
            request, f'Marked "{contact.subject}" as read.', messages.SUCCESS)
        return redirect('admin:accounts_contactus_changelist')


    def respond_view(self, request, object_id):
        if not request.user.is_staff:
            raise PermissionDenied()

        contact = ContactUs.objects.get(id=object_id)

        if request.method == 'POST':
            response_text = request.POST.get('response_text', '')
            notes = request.POST.get('admin_notes', '')
            send_email = 'send_email' in request.POST

            if not response_text.strip():
                self.message_user(
                    request, 'Response text is required.', messages.ERROR)
                return redirect(request.path)

            contact.mark_as_responded(
                response_text=response_text,
                notes=notes,
                user=request.user,
                send_email=send_email
            )

            msg = f"Response sent to {contact.email}." if send_email else "Response saved."
            lvl = messages.SUCCESS if send_email else messages.WARNING
            self.message_user(request, msg, lvl)

            change_list_url = reverse('admin:%s_%s_changelist' % (
                self.model._meta.app_label,
                self.model._meta.model_name
            ))


            return redirect(change_list_url)

        # default email template
        default_response = f"""
                Dear {contact.name},
                Thank you for reaching out regarding your {contact.get_contact_type_display().lower()} inquiry.
                We have reviewed your message and would like to provide the following response:
                [Your detailed response here]
                Best regards,
                {getattr(settings, "PLATFORM_NAME", "Our Team")}"""

        context = {
            'contact': contact,
            'opts': self.model._meta,
            'title': f'Respond to: {contact.subject}',
            'default_response': default_response,
            'platform_name': getattr(settings, 'PLATFORM_NAME', 'Our Platform'),
        }
        return render(request, 'admin/contact/respond.html', context)

    # BULK ACTIONS
    def mark_as_responded(self, request, queryset):
        updated = queryset.update(
            responded=True,
            responded_at=timezone.now(),
            responded_by_id=request.user.id
        )
        self.message_user(
            request, f'{updated} submissions marked as responded.', messages.SUCCESS)

    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(
            request, f'{updated} submissions marked as read.', messages.SUCCESS)

    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(
            request, f'{updated} submissions marked as unread.', messages.SUCCESS)

    def archive_selected(self, request, queryset):
        updated = queryset.update(is_archived=True)
        self.message_user(
            request, f'{updated} submissions archived.', messages.SUCCESS)

    # PRIORITY
    def set_priority_low(self, request, queryset):
        updated = queryset.update(priority='low')
        self.message_user(
            request, f'{updated} submissions set to low priority.', messages.SUCCESS)

    def set_priority_normal(self, request, queryset):
        updated = queryset.update(priority='normal')
        self.message_user(
            request, f'{updated} submissions set to normal priority.', messages.SUCCESS)

    def set_priority_high(self, request, queryset):
        updated = queryset.update(priority='high')
        self.message_user(
            request, f'{updated} submissions set to high priority.', messages.SUCCESS)

    def set_priority_urgent(self, request, queryset):
        updated = queryset.update(priority='urgent')
        self.message_user(
            request, f'{updated} submissions set to urgent priority.', messages.SUCCESS)
