"""Media storages that resize and watermark every picture before it is stored (see core/images.py)."""
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from .images import process

class WatermarkMixin:
    def save(self, name, content, max_length=None):
        if name and str(name).lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp"):
            content.seek(0) if hasattr(content, "seek") else None
            result = process(content.read(), name)
            if result:
                data, name = result
                content = ContentFile(data, name=name)
            elif hasattr(content, "seek"):
                content.seek(0)
        return super().save(name, content, max_length=max_length)

class WatermarkFileSystemStorage(WatermarkMixin, FileSystemStorage):
    pass

try:
    from storages.backends.s3 import S3Storage

    class WatermarkS3Storage(WatermarkMixin, S3Storage):
        pass
except ImportError:   # django-storages is only needed with Supabase Storage
    pass
