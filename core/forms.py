from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from .models import Member

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
    city = forms.ChoiceField(choices=CITY)
    age = forms.IntegerField(min_value=18, max_value=99)
    class Meta:
        model = Member
        fields = ["name", "age", "gender", "city", "religion", "education", "occupation", "marital_status", "origin", "goal", "bio", "photo", "phone", "whatsapp_ok"]
        labels = {"goal": "Lengo (your marriage goal)", "bio": "Kuhusu Mimi (about me)", "origin": "Asili"}
        widgets = {"bio": forms.Textarea(attrs={"rows": 4, "placeholder": "Tell others about yourself and what you are looking for."})}
    def clean(self):
        d = super().clean()
        if d.get("whatsapp_ok") and not d.get("phone"): self.add_error("phone", "Add your WhatsApp number or untick WhatsApp messages.")
        return d

class MessageForm(forms.Form):
    body = forms.CharField(max_length=1000, label="", widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Andika ujumbe wako..."}))


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Username or email"
        self.fields["username"].widget.attrs["placeholder"] = "Username or email"
        self.fields["password"].widget.attrs["placeholder"] = "Your password"
