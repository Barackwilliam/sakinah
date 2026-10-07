from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from .models import AdvertReview, ArticleComment, Inquiry, Member, Report

LOCATIONS = ["Dar es Salaam", "Arusha", "Mwanza", "Dodoma", "Zanzibar"]
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

class MessageForm(forms.Form):
    body = forms.CharField(max_length=1000, label="", widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Andika ujumbe wako..."}))


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
