from django import forms
from core.faces import HideFaceMixin
from core.forms import ProfileForm, CITY
from core.models import Member, Payment, Plan, SupportTicket

class MemberProfileForm(ProfileForm):
    """The public profile form plus the member-area extras (headline, religiosity, interests, lifestyle)."""
    SECTIONS = [
        ("Basic information", "user", ["name", "age", "gender", "city", "origin", "headline"]),
        ("About me", "doc", ["bio", "goal"]),
        ("Interests & lifestyle", "star", ["interests", "lifestyle"]),
        ("Quick info", "people", ["height_cm", "body_type", "languages", "marital_status", "smokes", "drinks"]),
        ("Education & career", "cap", ["education", "occupation", "workplace", "income_range"]),
        ("Lifestyle", "heart-o", ["willing_to_relocate", "food_preference", "hobbies", "exercise"]),
        ("Religion & values", "pray", ["religion", "practice", "prayer", "hijab", "quran_reading", "values"]),
        ("Family background", "home", ["father_status", "mother_status", "siblings", "family_type", "family_location", "about_family"]),
        ("Contact", "phone", ["phone", "whatsapp_ok"]),
    ]
    class Meta(ProfileForm.Meta):
        fields = [f for f in ProfileForm.Meta.fields if f != "photo" and not f.startswith("pref_")] + ["headline", "practice", "interests", "lifestyle"]

VOICE_MAX_SECONDS, VOICE_MAX_BYTES = 120, 4 * 1024 * 1024
VOICE_TYPES = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/aac": "aac", "audio/mpeg": "mp3",
               "video/webm": "webm", "video/mp4": "m4a"}   # some browsers label recorded sound as video

class ConversationForm(forms.Form):
    body = forms.CharField(max_length=1000, required=False, widget=forms.TextInput(attrs={"placeholder": "Andika ujumbe wako hapa...", "autocomplete": "off"}))
    image = forms.ImageField(required=False)
    voice = forms.FileField(required=False)
    duration = forms.IntegerField(required=False, min_value=0, max_value=VOICE_MAX_SECONDS + 5)
    def clean_voice(self):
        v = self.cleaned_data.get("voice")
        if not v: return v
        ctype = (getattr(v, "content_type", "") or "").split(";")[0].strip().lower()
        if ctype not in VOICE_TYPES: raise forms.ValidationError("That voice note format is not supported.")
        if v.size > VOICE_MAX_BYTES: raise forms.ValidationError("Voice notes can be up to 2 minutes long.")
        v.name = f"voice.{VOICE_TYPES[ctype]}"   # never trust the uploaded file name
        return v
    def clean(self):
        d = super().clean()
        if not d.get("body") and not d.get("image") and not d.get("voice"): raise forms.ValidationError("Write a message, attach a photo or record a voice note.")
        return d

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
        labels = {"pref_age_min": "Preferred age from", "pref_age_max": "to", "pref_location": "Preferred Location", "pref_education": "Preferred Education Level",
                  "pref_marital": "Preferred Marital Status", "pref_prayer": "Religious Practice", "pref_occupation": "Preferred occupation",
                  "pref_values": "Values", "pref_relocate": "Partner willing to relocate", "pref_more": "Additional preferences"}

class PrivacyForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["profile_visibility", "photo_visibility", "show_online", "show_age", "location_display", "allow_messages_from", "show_in_search"]

class AccountForm(HideFaceMixin, forms.ModelForm):
    email = forms.EmailField()
    city = forms.ChoiceField(choices=CITY, label="Location")
    class Meta:
        model = Member
        fields = ["name", "birth_date", "gender", "city", "photo"]
        labels = {"name": "Full Name", "birth_date": "Date of Birth"}
        widgets = {"birth_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        if self.instance.user_id: self.fields["email"].initial = self.instance.user.email
        self.fields["photo"].required = False
        self.add_hide_face(self.instance.hide_face)
    def save(self, commit=True):
        self.instance.hide_face = self.cleaned_data.get("hide_face", False)   # remembered for the next upload too
        return super().save(commit)
    def clean_email(self):
        from django.contrib.auth.models import User
        e = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=e).exclude(pk=self.instance.user_id).exists(): raise forms.ValidationError("Another account uses this email.")
        return e
    def save(self, commit=True):
        m = super().save(commit)
        if self.instance.user_id:
            self.instance.user.email = self.cleaned_data["email"]; self.instance.user.save(update_fields=["email"])
        return m

class ProfileSettingsForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["headline", "bio", "education", "occupation", "marital_status"]
        labels = {"bio": "About Me", "occupation": "Profession"}
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
        if lo and hi and lo > hi: self.add_error("pref_age_max", "Must be greater than the minimum age.")
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
    months = forms.TypedChoiceField(coerce=int, choices=[(1, "1 month"), (3, "3 months"), (6, "6 months"), (12, "12 months")], initial=1)
    gateway = forms.ChoiceField(choices=[(k, v) for k, v in Payment.GATEWAYS if k in ("mpesa", "mixx", "airtel", "bank")], label="Paid with")
    phone = forms.CharField(max_length=20, label="Phone number used")
    reference = forms.CharField(max_length=60, label="Transaction reference")
    def __init__(self, *a, plans=None, **kw): super().__init__(*a, **kw)
