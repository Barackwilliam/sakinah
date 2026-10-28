"""Every picture saved to the media storage is resized (no multi-megabyte phone photos) and stamped with the site
watermark, e.g. "sakinah.co.tz". The work happens in the storage class (core/storage.py), so it covers member uploads,
dashboard uploads, starter images and anything else that stores a picture."""
from io import BytesIO
from pathlib import Path
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont, ImageOps, PngImagePlugin

MAX_SIDE = 1600          # pixels; enough for the largest place a photo is shown
MIN_SIDE = 60            # only tiny thumbnails and icons are left alone
MARK = "sakinah-watermark"   # written into the file so a picture is never stamped twice
FONT = Path(__file__).parent / "fonts" / "DejaVuSans-Bold.ttf"
SKIP = ("plans/", "vendors/", "support/", "site/logo")   # plan icons, vendor logos, support attachments and the site logo

def wants_mark(name):
    return bool(getattr(settings, "WATERMARK_TEXT", "")) and not str(name).replace("\\", "/").startswith(SKIP)

def is_marked(img):
    return MARK in str(img.info.get("comment", b"")) or img.info.get("Comment") == MARK

def stamp(img, text):
    """Draw the text a little below the centre of the picture (clear of name bars and badges that cards lay over photos): soft white letters with a dark shadow, readable on any photo."""
    w, h = img.size
    size = max(9, min(64, int(w * 0.055)))
    font = ImageFont.truetype(str(FONT), size)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    box = draw.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    x, y = (w - tw) // 2, int(h * 0.62) - th // 2
    shadow = max(1, size // 18)
    draw.text((x + shadow, y + shadow), text, font=font, fill=(0, 0, 0, 95))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 165))
    return Image.alpha_composite(img.convert("RGBA"), layer)

THUMB_SIDE = 500         # pixels; cards, avatars and conversation rows never show a photo larger than this

def thumbnail(data, side=THUMB_SIDE):
    """A small copy of an already-processed picture, for the places that show it the size of a stamp."""
    try:
        img = Image.open(BytesIO(data))
        if img.format not in ("JPEG", "PNG", "WEBP", "MPO"): return None
        img = ImageOps.exif_transpose(img)
        if max(img.size) <= side: return None        # already small enough to send as it is
        img.thumbnail((side, side))
        out = BytesIO()
        img.convert("RGB").save(out, "JPEG", quality=78, optimize=True, progressive=True)
        return out.getvalue()
    except Exception:
        return None

def process(data, name, keep_format=False):
    """Return (bytes, name) of the resized and watermarked picture, or None to store the original unchanged."""
    try:
        img = Image.open(BytesIO(data))
        fmt = img.format
        if fmt not in ("JPEG", "PNG", "WEBP", "MPO"): return None   # leave GIFs, SVGs and anything unusual alone
        if is_marked(img): return None
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        img = ImageOps.exif_transpose(img)    # keep phone photos the right way up
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        marked = wants_mark(name) and min(img.size) >= MIN_SIDE and img.size[0] >= 110
        if marked: img = stamp(img, settings.WATERMARK_TEXT)
        elif len(data) <= 300 * 1024: return None   # small and not watermarked: keep exactly as uploaded
        out = BytesIO()
        as_png = has_alpha or (keep_format and fmt == "PNG")
        if as_png:
            info = PngImagePlugin.PngInfo()
            if marked: info.add_text("Comment", MARK)
            img.save(out, "PNG", optimize=True, pnginfo=info); ext = "png"
        else:
            img.convert("RGB").save(out, "JPEG", quality=84, optimize=True, progressive=True, comment=MARK.encode() if marked else b""); ext = "jpg"
        if not marked and out.tell() >= len(data): return None
        stem, _, old_ext = str(name).rpartition(".")
        if keep_format or old_ext.lower() in (("png",) if as_png else ("jpg", "jpeg")): new_name = name
        else: new_name = f"{stem or name}.{ext}"
        return out.getvalue(), new_name
    except Exception:
        return None   # never block an upload because of image processing
