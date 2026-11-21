from django.utils.translation import gettext_lazy as _l
from django.utils.translation import gettext as _, ngettext
from django import forms
from core.faces import HideFaceMixin
from core.forms import ProfileForm, CITY
from core.models import Member, Payment, Plan, SupportTicket

class MemberProfileForm(ProfileForm):
    """The public profile form plus the member-area extras (headline, religiosity, interests, lifestyle)."""
    SECTIONS = [
        (_l("Basic information"), "user", ["name", "age", "gender", "city", "origin", "headline"]),
        (_l("About me"), "doc", ["bio", "goal"]),
        (_l("Interests & lifestyle"), "star", ["interests", "lifestyle"]),
        (_l("Quick info"), "people", ["height_cm", "body_type", "languages", "marital_status", "smokes", "drinks"]),
        (_l("Education & career"), "cap", ["education", "occupation", "workplace", "income_range"]),
        (_l("Lifestyle"), "heart-o", ["willing_to_relocate", "food_preference", "hobbies", "exercise"]),
        (_l("Religion & values"), "pray", ["religion", "practice", "prayer", "hijab", "quran_reading", "values"]),
        (_l("Family background"), "home", ["father_status", "mother_status", "siblings", "family_type", "family_location", "about_family"]),
        (_l("Contact"), "phone", ["phone", "whatsapp_ok"]),
    ]
    class Meta(ProfileForm.Meta):
        fields = [f for f in ProfileForm.Meta.fields if f != "photo" and not f.startswith("pref_")] + ["headline", "practice", "interests", "lifestyle"]

class PhotoForm(HideFaceMixin, forms.Form):
    face_field = "image"
    image = forms.ImageField()
    def __init__(self, *a, hide_face=False, **kw):
        super().__init__(*a, **kw); self.add_hide_face(hide_face)

class PreferencesForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["pref_age_min", "pref_age_max", "pref_location", "pref_education", "pref_marital", "pref_prayer", "pref_occupation",
                  "pref_values", "pref_relocate", "pref_more"]
        labels = {"pref_age_min": _l("Preferred age from"), "pref_age_max": "to", "pref_location": _l("Preferred Location"), "pref_education": _l("Preferred Education Level"),
                  "pref_marital": _l("Preferred Marital Status"), "pref_prayer": _l("Religious Practice"), "pref_occupation": _l("Preferred occupation"),
                  "pref_values": _l("Values"), "pref_relocate": _l("Partner willing to relocate"), "pref_more": _l("Additional preferences")}

class PrivacyForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["profile_visibility", "photo_visibility", "show_online", "show_age", "location_display", "allow_messages_from", "show_in_search"]

class AccountForm(HideFaceMixin, forms.ModelForm):
    email = forms.EmailField()
    city = forms.ChoiceField(choices=CITY, label=_l("Location"))
    class Meta:
        model = Member
        fields = ["name", "birth_date", "gender", "city", "photo"]
        labels = {"name": _l("Full Name"), "birth_date": _l("Date of Birth")}
        widgets = {"birth_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        if self.instance.user_id: self.fields["email"].initial = self.instance.user.email
        self.fields["photo"].required = False
        self.add_hide_face(self.instance.hide_face)
    def clean_email(self):
        from django.contrib.auth.models import User
        e = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=e).exclude(pk=self.instance.user_id).exists(): raise forms.ValidationError(_("Another account uses this email."))
        return e
    def save(self, commit=True):
        self.instance.hide_face = self.cleaned_data.get("hide_face", False)   # the switch is remembered for later uploads too
        m = super().save(commit)
        if self.instance.user_id:
            self.instance.user.email = self.cleaned_data["email"]; self.instance.user.save(update_fields=["email"])
        return m

class ProfileSettingsForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["headline", "bio", "education", "occupation", "marital_status"]
        labels = {"bio": _l("About Me"), "occupation": _l("Profession")}
        widgets = {"bio": forms.Textarea(attrs={"rows": 3})}

class NotifyForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["notify_messages", "notify_likes", "notify_matches", "notify_events", "notify_system"]

class SettingsPrefsForm(forms.ModelForm):
    """The short preferences card on the Settings page; the full list lives under My Profile > Preferences."""
    class Meta:
        model = Member
        fields = ["pref_age_min", "pref_age_max", "pref_location", "pref_education", "pref_marital", "pref_prayer"]
    def clean(self):
        d = super().clean()
        lo, hi = d.get("pref_age_min"), d.get("pref_age_max")
        if lo and hi and lo > hi: self.add_error("pref_age_max", _("Must be greater than the minimum age."))
        return d

class AppearanceForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["ui_language", "ui_theme"]

class TicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ["subject", "message", "attachment"]
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}

class PaymentRequestForm(forms.Form):
    plan = forms.ModelChoiceField(queryset=Plan.objects.filter(price__gt=0))
    months = forms.TypedChoiceField(coerce=int, choices=[(1, _l("1 month")), (3, _l("3 months")), (6, _l("6 months")), (12, _l("12 months"))], initial=1)
    gateway = forms.ChoiceField(choices=[(k, v) for k, v in Payment.GATEWAYS if k in ("mpesa", "mixx", "airtel", "bank")], label=_l("Paid with"))
    phone = forms.CharField(max_length=20, label=_l("Phone number used"))
    reference = forms.CharField(max_length=60, label=_l("Transaction reference"))
    def __init__(self, *a, plans=None, **kw): super().__init__(*a, **kw)
