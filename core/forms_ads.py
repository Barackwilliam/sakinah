"""Forms for Advertise with us: the vendor's advert request and their mobile-money payment."""
from django import forms
from django.utils.translation import gettext_lazy as _l
from .forms import CITY
from .models import AdOrder, AdPackage, Payment, ServiceCategory

PRICE_UNITS = [("Starting price", _l("Starting price")), ("Fixed price", _l("Fixed price")), ("Per Item", _l("Per item")),
               ("Per Month", _l("Per month")), ("Per Event / Day", _l("Per event / day")), ("Per Person", _l("Per person")),
               ("Per Hour", _l("Per hour")), ("Per Package", _l("Per package"))]
MAX_PHOTO_MB = 8


class AdOrderForm(forms.ModelForm):
    package = forms.ModelChoiceField(queryset=AdPackage.objects.filter(active=True), widget=forms.RadioSelect, empty_label=None,
                                     label=_l("Choose your package"))
    city = forms.ChoiceField(choices=CITY, label=_l("City"))
    price_unit = forms.ChoiceField(choices=PRICE_UNITS, label=_l("Price is per"))
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))   # bots fill this

    class Meta:
        model = AdOrder
        fields = ["package", "business_name", "contact_name", "phone", "email", "category", "city", "title", "description",
                  "price", "price_unit", "negotiable", "image", "photo2", "photo3", "photo4"]
        labels = {"category": _l("Category"), "description": _l("Describe your advert"), "price": _l("Price (TSh)")}
        widgets = {
            "business_name": forms.TextInput(attrs={"placeholder": _l("e.g. Al-Noor Events"), "autocomplete": "organization"}),
            "contact_name": forms.TextInput(attrs={"placeholder": _l("e.g. Amina Hassan"), "autocomplete": "name"}),
            "phone": forms.TextInput(attrs={"placeholder": _l("e.g. 0712 345 678"), "autocomplete": "tel", "inputmode": "tel"}),
            "email": forms.EmailInput(attrs={"placeholder": _l("you@example.com"), "autocomplete": "email"}),
            "title": forms.TextInput(attrs={"placeholder": _l("e.g. Two-bedroom house for rent in Mbezi"), "maxlength": 120}),
            "description": forms.Textarea(attrs={"rows": 6, "maxlength": 2000,
                                                 "placeholder": _l("What you offer, what is included, where you are and why customers choose you.")}),
            "price": forms.NumberInput(attrs={"placeholder": _l("e.g. 500000"), "min": 0, "inputmode": "numeric"}),
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}), "photo2": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "photo3": forms.ClearableFileInput(attrs={"accept": "image/*"}), "photo4": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["category"].queryset = ServiceCategory.objects.order_by("order", "pk")
        self.fields["category"].empty_label = _l("Choose a category")
        if not self.is_bound: self.initial.setdefault("price", None)   # an empty box with an example, not a 0

    def clean_website(self):
        if self.cleaned_data.get("website"): raise forms.ValidationError("")
        return ""

    def clean(self):
        d = super().clean()
        for f in ("image", "photo2", "photo3", "photo4"):
            p = d.get(f)
            if p and getattr(p, "size", 0) > MAX_PHOTO_MB * 1024 * 1024:
                self.add_error(f, _l("Photos can be up to 8 MB each."))
        pkg = d.get("package")
        if pkg:   # photos beyond what the package allows are simply not kept
            for i, f in enumerate(("photo2", "photo3", "photo4"), start=2):
                if i > pkg.max_photos: d[f] = None
        return d


class AdPaymentForm(forms.Form):
    gateway = forms.ChoiceField(choices=[(k, v) for k, v in Payment.GATEWAYS if k in ("mpesa", "mixx", "airtel", "bank")],
                                widget=forms.RadioSelect, initial="mpesa", label=_l("Paid with"))
    phone = forms.CharField(max_length=20, label=_l("Phone number used"), widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"}))
    reference = forms.CharField(max_length=60, label=_l("Transaction reference"),
                                widget=forms.TextInput(attrs={"placeholder": _l("e.g. QK71ABC2XY"), "autocapitalize": "characters"}))

    def clean_reference(self):
        ref = self.cleaned_data["reference"].strip().upper()
        if Payment.objects.filter(reference__iexact=ref).exclude(status__in=["failed", "refunded"]).exists():
            raise forms.ValidationError(_l("This transaction reference has already been used."))
        return ref


# ---------- advertiser accounts (separate from members') ----------
import re
from django.contrib.auth import get_user_model, password_validation
from django.utils.crypto import get_random_string
from django.utils.translation import gettext as _
from .forms import LoginForm
from .models import Advertiser

PHONE_RE = re.compile(r"^\+?[0-9][0-9 ]{8,18}$")


def clean_phone(value):
    value = (value or "").strip()
    if not PHONE_RE.match(value): raise forms.ValidationError(_("Enter a valid phone number, e.g. 0712 345 678."))
    return value


class AdvertiserSignupForm(forms.Form):
    name = forms.CharField(max_length=100, label=_l("Full name"),
                           widget=forms.TextInput(attrs={"placeholder": _l("e.g. Amina Hassan"), "autocomplete": "name"}))
    phone = forms.CharField(max_length=20, label=_l("Phone number"),
                            widget=forms.TextInput(attrs={"placeholder": _l("e.g. 0712 345 678"), "autocomplete": "tel", "inputmode": "tel"}))
    email = forms.EmailField(label=_l("Email address"), widget=forms.EmailInput(attrs={"placeholder": _l("you@example.com"), "autocomplete": "email"}))
    password = forms.CharField(label=_l("Password"), strip=False, help_text=_l("At least 8 characters, not only numbers."),
                               widget=forms.PasswordInput(attrs={"placeholder": _l("Create a password"), "autocomplete": "new-password"}))
    agree = forms.BooleanField(label=_l("I agree to the advertising policy"),
                               error_messages={"required": _l("Please read and accept the advertising policy to continue.")})

    def clean_phone(self): return clean_phone(self.cleaned_data["phone"])

    def clean_email(self):
        e = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=e).exists():
            raise forms.ValidationError(_("An account with this email already exists. Sign in instead."))
        return e

    def clean(self):
        d = super().clean()
        if d.get("password"):
            user = get_user_model()(username=d.get("email", ""), email=d.get("email", ""), first_name=d.get("name", "")[:150])
            try: password_validation.validate_password(d["password"], user)
            except forms.ValidationError as e: self.add_error("password", e)
        return d

    def save(self):
        d, User = self.cleaned_data, get_user_model()
        base = re.sub(r"[^\w.@+-]", "", d["email"].split("@")[0])[:120] or "advertiser"
        username = base
        while User.objects.filter(username__iexact=username).exists(): username = f"{base}{get_random_string(4, '0123456789')}"
        first, _sp, last = d["name"].strip().partition(" ")
        user = User.objects.create_user(username=username, email=d["email"], password=d["password"], first_name=first[:150], last_name=last[:150])
        Advertiser.objects.create(user=user, name=d["name"].strip(), phone=d["phone"])
        return user


class AdvertiserLoginForm(LoginForm):
    """Advertisers sign in with their email (or username). Member accounts are sent to the member login."""
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not hasattr(user, "advertiser") and not user.is_staff:
            raise forms.ValidationError(_("This is a Sakinah member account. Use the member login, or create an advertiser account."),
                                        code="not_advertiser")


class AdvertiserAccountForm(forms.ModelForm):
    class Meta:
        model = Advertiser
        fields = ["name", "phone"]
        widgets = {"phone": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"})}
    def clean_phone(self): return clean_phone(self.cleaned_data["phone"])


# ---------- banners ----------
from .models import BannerOrder, BannerSlot


def fit_banner(upload, size):
    """Crop the picture to the place's shape and size, so every banner looks right whatever was uploaded."""
    from io import BytesIO
    from pathlib import Path
    from PIL import Image, ImageOps
    from django.core.files.base import ContentFile
    img = ImageOps.exif_transpose(Image.open(upload))
    has_alpha = img.mode in ("RGBA", "LA", "P")
    img = ImageOps.fit(img.convert("RGBA" if has_alpha else "RGB"), size, Image.LANCZOS)
    buf = BytesIO()
    if has_alpha: img.save(buf, "PNG", optimize=True); ext = "png"
    else: img.save(buf, "JPEG", quality=88, optimize=True, progressive=True); ext = "jpg"
    return ContentFile(buf.getvalue(), name=f"{Path(upload.name).stem[:40] or 'banner'}.{ext}")


class BannerOrderForm(forms.ModelForm):
    slot = forms.ModelChoiceField(queryset=BannerSlot.objects.filter(active=True), widget=forms.RadioSelect, empty_label=None,
                                  label=_l("Choose a place"))
    class Meta:
        model = BannerOrder
        fields = ["slot", "business_name", "title", "link", "image"]
        widgets = {
            "business_name": forms.TextInput(attrs={"placeholder": _l("e.g. Al-Noor Events"), "autocomplete": "organization"}),
            "title": forms.TextInput(attrs={"placeholder": _l("e.g. Big discounts on all phones this month"), "maxlength": 80}),
            "link": forms.TextInput(attrs={"placeholder": _l("e.g. https://yourshop.co.tz or 0712 345 678")}),
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def clean_slot(self):
        slot = self.cleaned_data["slot"]
        if slot.free <= 0: raise forms.ValidationError(_("This place is fully booked right now. Please choose another one or try again later."))
        return slot

    def clean_link(self):
        l = self.cleaned_data["link"].strip()
        digits = "".join(c for c in l if c.isdigit())
        if l.lower().startswith(("http://", "https://")) or "." in l: return l
        if 9 <= len(digits) <= 15: return l
        raise forms.ValidationError(_("Enter a website address or a WhatsApp number."))

    def clean_image(self):
        f = self.cleaned_data.get("image")
        if f and getattr(f, "size", 0) > MAX_PHOTO_MB * 1024 * 1024:
            raise forms.ValidationError(_("The picture is too big. Please use one under %(mb)s MB.") % {"mb": MAX_PHOTO_MB})
        return f

    def save(self, commit=True):
        obj = super().save(commit=False)
        if "image" in self.changed_data and self.cleaned_data.get("image"):
            obj.image = fit_banner(self.cleaned_data["image"], self.cleaned_data["slot"].size)
        if commit: obj.save()
        return obj
