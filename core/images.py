"""Shrink uploaded photos before they are stored, so pages never download multi-megabyte phone pictures."""
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps

MAX_SIDE = 1600          # pixels; enough for the largest place a photo is shown
MIN_BYTES = 300 * 1024   # smaller files are left exactly as uploaded

def shrink(file):
    """Return a smaller JPEG/PNG copy of an uploaded image, or None to keep the original."""
    try:
        if file.size <= MIN_BYTES: return None
        file.seek(0)
        img = Image.open(file)
        if img.format not in ("JPEG", "PNG", "WEBP", "MPO"): return None   # leave GIFs and anything unusual alone
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        img = ImageOps.exif_transpose(img)    # keep phone photos the right way up
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        out = BytesIO()
        if has_alpha:
            img.save(out, "PNG", optimize=True); ext, ctype = "png", "image/png"
        else:
            img.convert("RGB").save(out, "JPEG", quality=82, optimize=True, progressive=True); ext, ctype = "jpg", "image/jpeg"
        if out.tell() >= file.size: return None
        name = file.name.rsplit("/", 1)[-1].rsplit(".", 1)[0] + "." + ext
        out.seek(0)
        return InMemoryUploadedFile(out, None, name, ctype, out.getbuffer().nbytes, None)
    except Exception:
        return None   # never block an upload because of resizing
    finally:
        try: file.seek(0)
        except Exception: pass

def shrink_uploads(sender, instance, **kwargs):
    """pre_save hook: replace every newly uploaded image on the instance with a smaller copy."""
    from django.db.models import ImageField
    for field in sender._meta.fields:
        if not isinstance(field, ImageField): continue
        f = getattr(instance, field.attname)
        if not f or getattr(f, "_committed", True): continue
        small = shrink(f.file)
        if small is not None: f.file, f.name = small, small.name
