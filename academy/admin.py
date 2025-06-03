from django.contrib import admin
from .models import Training


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'client_display',
        'job',
        'has_pdf',
        'has_video',
        'slug'
    )
    search_fields = ('title', 'client__username', 'job__title')
    list_filter = ('job',)
    readonly_fields = ('slug',)
    ordering = ('title',)

    fieldsets = (
        (None, {
            'fields': (
                'title',
                'texts',
                'pdf_document',
                'video_url',
                'job',
                'client',
                'slug'
            )
        }),
    )

    def client_display(self, obj):
        return obj.client.username if obj.client else "None"
    client_display.short_description = 'Client'

    def has_pdf(self, obj):
        return bool(obj.pdf_document)
    has_pdf.boolean = True
    has_pdf.short_description = 'PDF Uploaded'

    def has_video(self, obj):
        return bool(obj.video_url)
    has_video.boolean = True
    has_video.short_description = 'Has Video URL'
