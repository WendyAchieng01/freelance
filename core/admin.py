from django.contrib import admin
from core.models import *
from django.utils.html import format_html
from django.utils.text import slugify


class JobAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'category',
        'status',
        'client',
        'selected_freelancer',
        'price',
        'deadline_date',
        'payment_verified',
        'is_max_freelancers_reached_display'
        
    )
    list_filter = (
        'category',
        'status',
        'preferred_freelancer_level',
        'payment_verified',
        'deadline_date'
    )
    search_fields = ('title', 'description',
                     'client__user__username', 'selected_freelancer__username')
    ordering = ('-posted_date',)
    #date_hierarchy = 'posted_date'
    readonly_fields = ('posted_date', 'slug',
                       'is_max_freelancers_reached_display')
    fieldsets = (
        (None, {
            'fields': (
                'title',
                'category',
                'description',
                'price',
                'deadline_date',
                'status',
                'client',
                'selected_freelancer',
                'max_freelancers',
                'required_freelancers',
                'preferred_freelancer_level',
                'payment_verified',
                'slug',
                'is_max_freelancers_reached_display'
            )
        }),
    )

    def is_max_freelancers_reached_display(self, obj):
        return obj.is_max_freelancers_reached
    is_max_freelancers_reached_display.boolean = True
    is_max_freelancers_reached_display.short_description = "Max Freelancers Reached"

    def save_model(self, request, obj, form, change):
        # Ensure slug is generated if not already set
        if not obj.slug:
            base_slug = slugify(obj.title)
            unique_slug = base_slug
            num = 1
            while Job.objects.filter(slug=unique_slug).exists():
                unique_slug = f'{base_slug}-{num}'
                num += 1
            obj.slug = unique_slug
        super().save_model(request, obj, form, change)


admin.site.register(Job, JobAdmin)


@admin.register(JobCategory)
class JobCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ('user', 'job', 'submitted_at', 'slug')
    search_fields = ('user__username', 'job__title', 'slug')
    readonly_fields = ('submitted_at', 'slug')
    ordering = ('-submitted_at',)

    def save_model(self, request, obj, form, change):
        if not obj.slug:
            base_slug = slugify(f'{obj.job.title}-{obj.user.username}')
            unique_slug = base_slug
            num = 1
            while Response.objects.filter(slug=unique_slug).exists():
                unique_slug = f'{base_slug}-{num}'
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
