from django.conf import settings
from django.db import models

from core.models import Job


# Create your models here.
class Training(models.Model):
    title = models.CharField(max_length=100)
    texts = models.TextField()
    pdf_document = models.FileField(upload_to='pdf_documents/', null=True, blank=True)
    video_url = models.URLField(max_length=200, null=True, blank=True)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='trainings')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trainings', default=None, null=True, blank=True)

    def __str__(self):
        return self.title