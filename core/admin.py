from django.contrib import admin
from core.models import *
from django.utils.html import format_html
from django.utils.text import slugify
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse, path


# Filters
class JobStatusFilter(admin.SimpleListFilter):
    title = "Job Status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return Job._meta.get_field('status').choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class FreelancerAssignedFilter(admin.SimpleListFilter):
    title = "Freelancers Assigned"
    parameter_name = "assigned"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(selected_freelancers__isnull=False)
        if self.value() == "no":
            return queryset.filter(selected_freelancers__isnull=True)
        return queryset


#Inline for Responses marked for review 
class ResponseInline(admin.TabularInline):
    model = Job.reviewed_responses.through
    extra = 0
    readonly_fields = ("response_link",)
    verbose_name = "Marked Response"
    verbose_name_plural = "Marked Responses"

    def response_link(self, obj):
        try:
            url = obj.job.get_absolute_url()
            return format_html('<a href="{}">{}</a>', url, str(obj))
        except Exception:
            return str(obj)
    response_link.short_description = "Response"


class ResponseInline(admin.TabularInline):
    model = Response
    extra = 0
    readonly_fields = (
        "slug",
        "submitted_at",
        "cv_size",
        "cover_letter_size",
        "portfolio_size",
        "cv_content_type",
        "cover_letter_content_type",
        "portfolio_content_type",
    )


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "status_colored",
        "client_link",
        "assigned_freelancers_count",
        "required_freelancers",
        "payment_verified",
        "price",
        "net_per_freelancer",
        "posted_date",
        "deadline_date",
        "assigned_at",
        "frontend_job_link",
    )

    search_fields = (
        "title",
        "slug",
        "client__user__username",
        "client__user__email",
    )

    list_filter = (
        "status",
        "preferred_freelancer_level",
        "skills_required",
        "payment_verified",
        "posted_date",
    )

    readonly_fields = (
        "slug",
        "posted_date",
        "assigned_at",
        "total_platform_fee",
        "net_per_freelancer",
        "gross_per_freelancer",
    )

    inlines = [ResponseInline]

    filter_horizontal = (
        "skills_required",
        "selected_freelancers",
        "reviewed_responses",
    )

    date_hierarchy = "posted_date"

    # Custom columns
    @admin.display(description="Client")
    def client_link(self, obj):
        if obj.client:
            try:
                url = reverse("admin:accounts_profile_change",
                              args=[obj.client.id])
                return format_html('<a href="{}">{}</a>', url, obj.client.user.username)
            except Exception:
                return obj.client.user.username
        return "-"

    @admin.display(description="Assigned Freelancers")
    def assigned_freelancers_count(self, obj):
        return obj.selected_freelancers.count()

    @admin.display(description="Frontend Job")
    def frontend_job_link(self, obj):
        url = f"{settings.FRONTEND_URL}/freelancer/jobs/{obj.slug}"
        return format_html('<a href="{}" target="_blank">View Job In Frontend</a>', url)

    @admin.display(description="Status")
    def status_colored(self, obj):
        color_map = {
            "open": "gray",
            "in_progress": "blue",
            "completed": "green",
        }
        color = color_map.get(obj.status, "black")
        return format_html('<strong><span style="color:{};">{}</span></strong>', color, obj.status)

    @admin.display(boolean=True, description="Max Freelancers Reached")
    def is_max_freelancers_reached_display(self, obj):
        return obj.is_max_freelancers_reached

    # Actions
    actions = ["mark_as_completed_action"]

    def mark_as_completed_action(self, request, queryset):
        updated = 0
        for job in queryset:
            if job.mark_as_completed(force=True):
                updated += 1
        self.message_user(
            request, f"{updated} job(s) marked as completed.", level=messages.SUCCESS
        )
    mark_as_completed_action.short_description = "Force mark selected jobs as completed"

    # Save override for slug
    def save_model(self, request, obj, form, change):
        if not obj.slug:
            base_slug = slugify(obj.title)
            unique_slug = base_slug
            num = 1
            while Job.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{num}"
                num += 1
            obj.slug = unique_slug
        super().save_model(request, obj, form, change)

    # Extra context
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["analytics_url"] = reverse("admin-analytics")
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(JobCategory)
class JobCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    ordering = ('name',)
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["analytics_url"] = reverse("admin-analytics")
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = (
        "user_link",
        "job_link",
        "status",
        "marked_for_review",
        "submitted_at",
    )
    search_fields = ("user__username", "user__email", "job__title", "slug")
    list_filter = ("status", "marked_for_review", "submitted_at")

    readonly_fields = (
        "slug",
        "submitted_at",
        "cv_size",
        "cover_letter_size",
        "portfolio_size",
        "cv_content_type",
        "cover_letter_content_type",
        "portfolio_content_type",
    )

    @admin.display(description="User")
    def user_link(self, obj):
        url = reverse("admin:auth_user_change", args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)

    @admin.display(description="Job")
    def job_link(self, obj):
        url = f"{settings.FRONTEND_URL}/freelancer/jobs/{obj.job.slug}"
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.job.title)

    def save_model(self, request, obj, form, change):
        # Ensure slug is set
        if not obj.slug:
            base_slug = slugify(f"{obj.job.title}-{obj.user.username}")
            unique_slug = base_slug
            num = 1
            while Response.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{num}"
                num += 1
            obj.slug = unique_slug
        super().save_model(request, obj, form, change)
        


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('job', 'client', 'freelancer', 'created_at', 'slug')
    search_fields = (
        'job__title',
        'client__user__username',
        'freelancer__user__username',
        'slug'
    )
    readonly_fields = ('created_at', 'slug')

    def save_model(self, request, obj, form, change):
        if not obj.slug:
            base = f"{obj.job.title}-{obj.client.user.username}-{obj.freelancer.user.username}"
            obj.slug = slugify(base)
        super().save_model(request, obj, form, change)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('chat', 'sender', 'timestamp', 'short_content')
    search_fields = ('sender__username', 'chat__job__title', 'content')
    readonly_fields = ('timestamp',)

    def short_content(self, obj):
        return (obj.content[:50] + '...') if len(obj.content) > 50 else obj.content
    short_content.short_description = 'Message Preview'


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ('message', 'filename', 'file_size_display',
                    'content_type', 'uploaded_at')
    search_fields = ('filename', 'message__sender__username')
    readonly_fields = ('uploaded_at', 'file_size', 'content_type')

    def file_size_display(self, obj):
        return f"{obj.file_size / 1024:.2f} KB"
    file_size_display.short_description = 'File Size'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('reviewer', 'recipient', 'rating',
                    'created_at', 'updated_at', 'short_comment')
    list_filter = ('rating', 'created_at')
    search_fields = ('reviewer__username', 'recipient__username', 'comment')
    readonly_fields = ('created_at', 'updated_at')

    def short_comment(self, obj):
        return (obj.comment[:50] + '...') if len(obj.comment) > 50 else obj.comment
    short_comment.short_description = 'Comment Preview'
