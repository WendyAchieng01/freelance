from django.contrib import admin
from django.urls import path
from .views import analytics_dashboard


def register_admin_analytics():
    def get_urls(original_get_urls):
        def inner():
            urls = original_get_urls()
            custom = [
                path("analytics/", admin.site.admin_view(analytics_dashboard),
                     name="admin-analytics")
            ]
            return custom + urls
        return inner

    admin.site.get_urls = get_urls(admin.site.get_urls)


register_admin_analytics()
