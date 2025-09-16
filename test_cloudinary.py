import cloudinary
from cloudinary.uploader import upload
from django.conf import settings

# Ensure Django settings are loaded (important if using Django config)
import django
django.setup()

try:
    response = upload("pic.jpg", resource_type="image")  # local file in project folder
    print(response['secure_url'])
except Exception as e:
    print(f"❌ Cloudinary error: {e}")
