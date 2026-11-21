"""Forms for Advertise with us: the vendor's advert request and their mobile-money payment."""
from django import forms
from django.utils.translation import gettext_lazy as _l
from .forms import CITY
from .models import AdOrder, AdPackage, Payment, ServiceCategory

PRICE_UNITS = [("Per Event / Day", _l("Per event / day")), ("Per Person", _l("Per person")), ("Per Hour", _l("Per hour")),
               ("Per Package", _l("Per package")), ("Starting price", _l("Starting price"))]
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
        widgets = {
            "business_name": forms.TextInput(attrs={"placeholder": _l("e.g. Al-Noor Events"), "autocomplete": "organization"}),
            "contact_name": forms.TextInput(attrs={"placeholder": _l("e.g. Amina Hassan"), "autocomplete": "name"}),
            "phone": forms.TextInput(attrs={"placeholder": _l("e.g. 0712 345 678"), "autocomplete": "tel", "inputmode": "tel"}),
            "email": forms.EmailInput(attrs={"placeholder": _l("you@example.com"), "autocomplete": "email"}),
            "title": forms.TextInput(attrs={"placeholder": _l("e.g. Elegant wedding hall for 300 guests"), "maxlength": 120}),
            "description": forms.Textarea(attrs={"rows": 6, "maxlength": 2000,
                                                 "placeholder": _l("What you offer, what is included, where you work and why couples choose you.")}),
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
