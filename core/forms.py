from django.utils.translation import gettext_lazy as _l
from django.utils.translation import gettext as _, ngettext
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from .models import AdvertReview, ArticleComment, Booking, Inquiry, Member, PackageReview, Report

LOCATIONS = ["Dar es Salaam", "Arusha", "Mwanza", "Dodoma", "Zanzibar", "Mbeya", "Morogoro", "Tanga", "Kilimanjaro", "Iringa", "Kagera",
             "Mtwara", "Tabora", "Kigoma", "Shinyanga", "Singida", "Ruvuma", "Lindi", "Pwani", "Manyara", "Mara", "Rukwa", "Katavi",
             "Njombe", "Simiyu", "Geita", "Songwe", "Pemba"]
CITY = [(c, c) for c in LOCATIONS]

class SignupForm(UserCreationForm):
    name = forms.CharField(max_length=80, label=_l("Full name"))
    email = forms.EmailField()
    gender = forms.ChoiceField(choices=Member.GENDER, label=_l("I am a"))
    age = forms.IntegerField(min_value=18, max_value=99)
    city = forms.ChoiceField(choices=CITY)
    religion = forms.ChoiceField(choices=Member.RELIGION)
    occupation = forms.CharField(max_length=80)
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "name", "email", "gender", "age", "city", "religion", "occupation"]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = _l("Letters, numbers and @ . + - _ only.")
        self.fields["password1"].help_text = _l("At least 8 characters, not only numbers.")
        self.fields["password2"].help_text = ""
        for name, ph in {"username": _l("e.g. amina_28"), "name": _l("Your full name"), "email": _l("you@example.com"), "age": _l("e.g. 28"),
                         "occupation": _l("e.g. Teacher"), "password1": _l("Create a password"), "password2": _l("Repeat the password")}.items():
            self.fields[name].widget.attrs["placeholder"] = ph

    def clean_email(self):
        e = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=e).exists(): raise forms.ValidationError(_("An account with this email already exists."))
        return e
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.save()
        d = self.cleaned_data
        Member.objects.create(user=user, name=d["name"], gender=d["gender"], age=d["age"], city=d["city"], religion=d["religion"], occupation=d["occupation"])
        return user

class ProfileForm(forms.ModelForm):
    SECTIONS = [
        (_l("Basic information"), "user", ["name", "age", "gender", "city", "origin", "photo"]),
        (_l("About me"), "msg-sq", ["bio", "goal"]),
        (_l("Quick info"), "people", ["height_cm", "body_type", "languages", "marital_status", "smokes", "drinks"]),
        (_l("Education & career"), "cap", ["education", "occupation", "workplace", "income_range"]),
        (_l("Lifestyle"), "heart-f", ["willing_to_relocate", "food_preference", "hobbies", "exercise"]),
        (_l("Religion & values"), "moon", ["religion", "prayer", "hijab", "quran_reading", "values"]),
        (_l("Family background"), "home", ["father_status", "mother_status", "siblings", "family_type", "family_location", "about_family"]),
        (_l("Partner preferences"), "heart", ["pref_age_min", "pref_age_max", "pref_marital", "pref_location", "pref_education",
                                          "pref_occupation", "pref_prayer", "pref_values", "pref_relocate", "pref_more"]),
        (_l("Contact"), "wa-f", ["phone", "whatsapp_ok"]),
    ]
    city = forms.ChoiceField(choices=CITY)
    age = forms.IntegerField(min_value=18, max_value=99)
    class Meta:
        model = Member
        fields = ["name", "age", "gender", "city", "origin", "photo", "bio", "goal", "height_cm", "body_type", "languages", "marital_status",
                  "smokes", "drinks", "education", "occupation", "workplace", "income_range", "willing_to_relocate", "food_preference",
                  "hobbies", "exercise", "religion", "prayer", "hijab", "quran_reading", "values", "father_status", "mother_status",
                  "siblings", "family_type", "family_location", "about_family", "pref_age_min", "pref_age_max", "pref_marital",
                  "pref_location", "pref_education", "pref_occupation", "pref_prayer", "pref_values", "pref_relocate", "pref_more",
                  "phone", "whatsapp_ok"]
        labels = {"goal": _l("Lengo (your marriage goal)"), "bio": _l("Kuhusu Mimi (about me)"), "origin": _l("Asili / ethnicity")}
        widgets = {"bio": forms.Textarea(attrs={"rows": 4, "placeholder": _l("Tell others about yourself and what you are looking for.")})}
    def clean(self):
        d = super().clean()
        if d.get("whatsapp_ok") and not d.get("phone"): self.add_error("phone", _("Add your WhatsApp number or untick WhatsApp messages."))
        return d
    def sections(self):
        return [(title, icon, [self[f] for f in names]) for title, icon, names in self.SECTIONS]

VOICE_MAX_SECONDS, VOICE_MAX_BYTES = 120, 4 * 1024 * 1024
VOICE_TYPES = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/aac": "aac", "audio/mpeg": "mp3",
               "video/webm": "webm", "video/mp4": "m4a"}   # some browsers label recorded sound as video

class ConversationForm(forms.Form):
    """One chat message: text, a photo, or a voice note (used by both the public chat and the member area)."""
    body = forms.CharField(max_length=1000, required=False, widget=forms.TextInput(attrs={"placeholder": _l("Andika ujumbe wako hapa..."), "autocomplete": "off"}))
    image = forms.ImageField(required=False)
    voice = forms.FileField(required=False)
    duration = forms.IntegerField(required=False, min_value=0, max_value=VOICE_MAX_SECONDS + 5)
    def clean_voice(self):
        v = self.cleaned_data.get("voice")
        if not v: return v
        ctype = (getattr(v, "content_type", "") or "").split(";")[0].strip().lower()
        if ctype not in VOICE_TYPES: raise forms.ValidationError(_("That voice note format is not supported."))
        if v.size > VOICE_MAX_BYTES: raise forms.ValidationError(_("Voice notes can be up to 2 minutes long."))
        v.name = f"voice.{VOICE_TYPES[ctype]}"   # never trust the uploaded file name
        return v
    def clean(self):
        d = super().clean()
        if not d.get("body") and not d.get("image") and not d.get("voice"): raise forms.ValidationError(_("Write a message, attach a photo or record a voice note."))
        return d


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = _l("Email address or username")
        self.fields["username"].widget.attrs["placeholder"] = _l("Enter your email address")
        self.fields["password"].widget.attrs["placeholder"] = _l("Enter your password")


class MemberLoginForm(LoginForm):
    """The member login. Advertiser accounts are separate and sign in on the advertiser page."""
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if hasattr(user, "advertiser") and not hasattr(user, "member") and not user.is_staff:
            raise forms.ValidationError(_("This is an advertiser account. Please use the advertiser login."), code="advertiser")


class InquiryForm(forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = ["kind", "name", "phone", "event_date", "guests", "message"]
        widgets = {"kind": forms.HiddenInput, "event_date": forms.DateInput(attrs={"type": "date"}),
                   "message": forms.Textarea(attrs={"rows": 3, "placeholder": _l("Tell the vendor about your event")})}
        labels = {"event_date": _l("Event date"), "guests": _l("Number of guests")}

class ReviewForm(forms.ModelForm):
    class Meta:
        model = AdvertReview
        fields = ["rating", "comment"]
        widgets = {"rating": forms.RadioSelect, "comment": forms.Textarea(attrs={"rows": 3, "placeholder": _l("Share your experience")})}

class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "details"]
        widgets = {"details": forms.Textarea(attrs={"rows": 3, "placeholder": _l("Anything our team should know")})}

class CommentForm(forms.ModelForm):
    class Meta:
        model = ArticleComment
        fields = ["body"]
        labels = {"body": ""}
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": _l("Write a respectful comment")})}


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ["travel_date", "couples", "name", "phone", "email", "message"]
        widgets = {"travel_date": forms.DateInput(attrs={"type": "date"}), "couples": forms.Select(choices=[(i, i) for i in range(1, 7)]),
                   "message": forms.Textarea(attrs={"rows": 3, "placeholder": _l("Special requests, e.g. flights, extra nights or a surprise for your spouse")})}
        labels = {"travel_date": _l("Travel dates"), "couples": _l("Number of couples"), "name": _l("Your name"), "phone": _l("Phone / WhatsApp"), "email": _l("Email (optional)")}
    def clean_travel_date(self):
        from datetime import date
        d = self.cleaned_data.get("travel_date")
        if d and d < date.today(): raise forms.ValidationError(_("Choose a date in the future."))
        return d

class PackageReviewForm(forms.ModelForm):
    class Meta:
        model = PackageReview
        fields = ["rating", "comment"]
        widgets = {"rating": forms.RadioSelect, "comment": forms.Textarea(attrs={"rows": 3, "placeholder": _l("Share your honeymoon experience")})}


class FindAccountResetForm(forms.Form):
    """Forgot password: members may type their email, username or phone number; the link always goes to the account's email."""
    email = forms.CharField(label=_l("Email, username or phone number"), max_length=150,
                            widget=forms.TextInput(attrs={"autocomplete": "username", "placeholder": _l("e.g. amina@example.com or 0712 345 678")}))

    def get_users(self, value):
        from django.contrib.auth import get_user_model
        from django.db.models import Q, Value
        from django.db.models.functions import Replace
        value = value.strip()
        digits = "".join(c for c in value if c.isdigit())
        q = Q(email__iexact=value) | Q(username__iexact=value)
        users = get_user_model().objects.filter(is_active=True)
        if len(digits) >= 9:   # 0712 345 678, +255712345678 and 255-712-345-678 all match on the last nine digits
            bare = Replace(Replace(Replace("member__phone", Value(" "), Value("")), Value("-"), Value("")), Value("+"), Value(""))
            users = users.annotate(bare_phone=bare)
            q |= Q(bare_phone__endswith=digits[-9:])
        return [u for u in users.filter(q).distinct() if u.has_usable_password()]
