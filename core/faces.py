"""Hide faces in member photos: find each face (YuNet detector, bundled in core/ml) and cover it with a soft frosted
"cloud" so the person cannot be recognised. Members choose this themselves when they upload a photo."""
from io import BytesIO
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

MODEL = Path(__file__).parent / "ml" / "face_detection_yunet_2023mar.onnx"
DETECT_SIDE = 1280      # faces are found on a copy no larger than this, which is fast and plenty accurate
_detector = None

def _cv2():
    import cv2   # imported lazily: only needed when a member asks to hide a face
    return cv2

def find_faces(rgb):
    """[(x, y, w, h)] of every face in an RGB numpy image."""
    global _detector
    cv2 = _cv2()
    h, w = rgb.shape[:2]
    scale = min(1.0, DETECT_SIDE / max(h, w))
    small = cv2.resize(rgb, (max(1, int(w * scale)), max(1, int(h * scale)))) if scale < 1 else rgb
    if _detector is None:
        _detector = cv2.FaceDetectorYN.create(str(MODEL), "", (320, 320), 0.6, 0.3, 5000)
    _detector.setInputSize((small.shape[1], small.shape[0]))
    _, found = _detector.detect(cv2.cvtColor(small, cv2.COLOR_RGB2BGR))
    if found is None: return []
    return [tuple(int(v / scale) for v in f[:4]) for f in found]

def cloud(rgb, faces):
    """Cover each face (with some margin for hair, hijab and chin) with a heavily blurred, slightly misty patch with soft edges."""
    cv2 = _cv2()
    h, w = rgb.shape[:2]
    out = rgb.astype(np.float32)
    for x, y, fw, fh in faces:
        cx, cy = x + fw / 2, y + fh / 2
        ax, ay = fw * 0.85, fh * 0.85                      # half-axes of the cloud, bigger than the face itself
        x0, x1 = int(max(0, cx - ax * 1.4)), int(min(w, cx + ax * 1.4))
        y0, y1 = int(max(0, cy - ay * 1.4)), int(min(h, cy + ay * 1.4))
        if x1 <= x0 or y1 <= y0: continue
        patch = rgb[y0:y1, x0:x1]
        ph, pw = patch.shape[:2]
        tiny = cv2.resize(patch, (6, 6), interpolation=cv2.INTER_AREA)   # keep only a few colours: no eyes, nose or mouth survive
        k = int(max(fw, fh) * 0.5) | 1
        blurred = cv2.GaussianBlur(cv2.resize(tiny, (pw, ph), interpolation=cv2.INTER_CUBIC), (k, k), 0).astype(np.float32)
        blurred = blurred * 0.7 + 255 * 0.3                 # a soft white mist, like a cloud
        yy, xx = np.mgrid[y0:y1, x0:x1]
        d = ((xx - cx) / ax) ** 2 + ((yy - cy) / ay) ** 2
        mask = np.clip((1.45 - d) / 0.45, 0, 1)[..., None]  # fully covered inside the face, fading out at the edge
        out[y0:y1, x0:x1] = out[y0:y1, x0:x1] * (1 - mask) + blurred * mask
    return out.clip(0, 255).astype(np.uint8)

def hide_faces(data):
    """Return (jpeg bytes, number of faces) with every face clouded, or (None, 0) when no face was found.
    A photo that already carries the site watermark keeps its marker, so it is not stamped a second time."""
    from .images import MARK, is_marked
    src = Image.open(BytesIO(data))
    marked = is_marked(src)
    rgb = np.array(ImageOps.exif_transpose(src).convert("RGB"))
    faces = find_faces(rgb)
    if not faces: return None, 0
    buf = BytesIO()
    Image.fromarray(cloud(rgb, faces)).save(buf, "JPEG", quality=92, comment=MARK.encode() if marked else b"")
    return buf.getvalue(), len(faces)

NO_FACE = "We could not find a face in this photo, so it was not saved. Use a clear photo of your face, or switch off \"Hide my face\"."

class HideFaceMixin:
    """Adds a "Hide my face" switch to a form with a photo upload; when it is on, faces in the new photo are clouded."""
    face_field = "photo"
    def add_hide_face(self, initial=False):
        from django import forms
        self.fields["hide_face"] = forms.BooleanField(required=False, initial=initial, label="Hide my face",
                                                      help_text="Cover your face with a soft blur so only people you choose can recognise you.")
    def clean(self):
        from django.core.files.uploadedfile import SimpleUploadedFile, UploadedFile
        data = super().clean()
        f = data.get(self.face_field)
        if data.get("hide_face") and isinstance(f, UploadedFile):
            f.seek(0)
            try: hidden, _ = hide_faces(f.read())
            except Exception: hidden = None
            if not hidden: self.add_error(self.face_field, NO_FACE)
            else:
                stem = f.name.rsplit(".", 1)[0]
                data[self.face_field] = SimpleUploadedFile(f"{stem}.jpg", hidden, "image/jpeg")
        return data
