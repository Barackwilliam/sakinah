from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from .models import AdvertReview, ArticleComment, Booking, Inquiry, Member, PackageReview, Report

LOCATIONS = ["Dar es Salaam", "Arusha", "Mwanza", "Dodoma", "Zanzibar", "Mbeya", "Morogoro", "Tanga", "Kilimanjaro", "Iringa", "Kagera",
             "Mtwara", "Tabora", "Kigoma", "Shinyanga", "Singida", "Ruvuma", "Lindi", "Pwani", "Manyara", "Mara", "Rukwa", "Katavi",
             "Njombe", "Simiyu", "Geita", "Songwe", "Pemba"]
CITY = [(c, c) for c in LOCATIONS]

class SignupForm(UserCreationForm):
    name = forms.CharField(max_length=80, label="Full name")
    email = forms.EmailField()
    gender = forms.ChoiceField(choices=Member.GENDER, label="I am a")
    age = forms.IntegerField(min_value=18, max_value=99)
    city = forms.ChoiceField(choices=CITY)
    religion = forms.ChoiceField(choices=Member.RELIGION)
    occupation = forms.CharField(max_length=80)
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "name", "email", "gender", "age", "city", "religion", "occupation"]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = "Letters, numbers and @ . + - _ only."
        self.fields["password1"].help_text = "At least 8 characters, not only numbers."
        self.fields["password2"].help_text = ""
        for name, ph in {"username": "e.g. amina_28", "name": "Your full name", "email": "you@example.com", "age": "e.g. 28",
                         "occupation": "e.g. Teacher", "password1": "Create a password", "password2": "Repeat the password"}.items():
            self.fields[name].widget.attrs["placeholder"] = ph

    def clean_email(self):
        e = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=e).exists(): raise forms.ValidationError("An account with this email already exists.")
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
        ("Basic information", "user", ["name", "age", "gender", "city", "origin", "photo"]),
        ("About me", "msg-sq", ["bio", "goal"]),
        ("Quick info", "people", ["height_cm", "body_type", "languages", "marital_status", "smokes", "drinks"]),
        ("Education & career", "cap", ["education", "occupation", "workplace", "income_range"]),
        ("Lifestyle", "heart-f", ["willing_to_relocate", "food_preference", "hobbies", "exercise"]),
        ("Religion & values", "moon", ["religion", "prayer", "hijab", "quran_reading", "values"]),
        ("Family background", "home", ["father_status", "mother_status", "siblings", "family_type", "family_location", "about_family"]),
        ("Partner preferences", "heart", ["pref_age_min", "pref_age_max", "pref_marital", "pref_location", "pref_education",
                                          "pref_occupation", "pref_prayer", "pref_values", "pref_relocate", "pref_more"]),
        ("Contact", "wa-f", ["phone", "whatsapp_ok"]),
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
        labels = {"goal": "Lengo (your marriage goal)", "bio": "Kuhusu Mimi (about me)", "origin": "Asili / ethnicity"}
        widgets = {"bio": forms.Textarea(attrs={"rows": 4, "placeholder": "Tell others about yourself and what you are looking for."})}
    def clean(self):
        d = super().clean()
        if d.get("whatsapp_ok") and not d.get("phone"): self.add_error("phone", "Add your WhatsApp number or untick WhatsApp messages.")
        return d
    def sections(self):
        return [(title, icon, [self[f] for f in names]) for title, icon, names in self.SECTIONS]

VOICE_MAX_SECONDS, VOICE_MAX_BYTES = 120, 4 * 1024 * 1024
VOICE_TYPES = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/aac": "aac", "audio/mpeg": "mp3",
               "video/webm": "webm", "video/mp4": "m4a"}   # some browsers label recorded sound as video

class ConversationForm(forms.Form):
    """One chat message: text, a photo, or a voice note (used by both the public chat and the member area)."""
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


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email address or username"
        self.fields["username"].widget.attrs["placeholder"] = "Enter your email address"
        self.fields["password"].widget.attrs["placeholder"] = "Enter your password"


class InquiryForm(forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = ["kind", "name", "phone", "event_date", "guests", "message"]
        widgets = {"kind": forms.HiddenInput, "event_date": forms.DateInput(attrs={"type": "date"}),
                   "message": forms.Textarea(attrs={"rows": 3, "placeholder": "Tell the vendor about your event"})}
        labels = {"event_date": "Event date", "guests": "Number of guests"}

class ReviewForm(forms.ModelForm):
    class Meta:
        model = AdvertReview
        fields = ["rating", "comment"]
        widgets = {"rating": forms.RadioSelect, "comment": forms.Textarea(attrs={"rows": 3, "placeholder": "Share your experience"})}

class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "details"]
        widgets = {"details": forms.Textarea(attrs={"rows": 3, "placeholder": "Anything our team should know"})}

class CommentForm(forms.ModelForm):
    class Meta:
        model = ArticleComment
        fields = ["body"]
        labels = {"body": ""}
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Write a respectful comment"})}


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ["travel_date", "couples", "name", "phone", "email", "message"]
        widgets = {"travel_date": forms.DateInput(attrs={"type": "date"}), "couples": forms.Select(choices=[(i, i) for i in range(1, 7)]),
                   "message": forms.Textarea(attrs={"rows": 3, "placeholder": "Special requests, e.g. flights, extra nights or a surprise for your spouse"})}
        labels = {"travel_date": "Travel dates", "couples": "Number of couples", "name": "Your name", "phone": "Phone / WhatsApp", "email": "Email (optional)"}
    def clean_travel_date(self):
        from datetime import date
        d = self.cleaned_data.get("travel_date")
        if d and d < date.today(): raise forms.ValidationError("Choose a date in the future.")
        return d

class PackageReviewForm(forms.ModelForm):
    class Meta:
        model = PackageReview
        fields = ["rating", "comment"]
        widgets = {"rating": forms.RadioSelect, "comment": forms.Textarea(attrs={"rows": 3, "placeholder": "Share your honeymoon experience"})}


class FindAccountResetForm(forms.Form):
    """Forgot password: members may type their email, username or phone number; the link always goes to the account's email."""
    email = forms.CharField(label="Email, username or phone number", max_length=150,
                            widget=forms.TextInput(attrs={"autocomplete": "username", "placeholder": "e.g. amina@example.com or 0712 345 678"}))

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
