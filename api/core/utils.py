from rest_framework import serializers
from core.models import Response, Job

MAX_FILE_SIZE_MB = 3


def validate_file(file, allowed_extensions):
    import os
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_extensions:
        raise serializers.ValidationError(
            f"Unsupported file type: {ext}. Allowed: {', '.join(allowed_extensions)}")
    if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise serializers.ValidationError(
            f"File size must be under {MAX_FILE_SIZE_MB}MB")


