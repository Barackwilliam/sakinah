from django import forms
from django.contrib.auth.forms import UserCreationForm
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
    occupation = forms.CharField(max_length=80)
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "name", "email", "gender", "age", "city", "occupation"]
    def clean_email(self):
        e = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=e).exists(): raise forms.ValidationError("An account with this email already exists.")
        return e
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.save()
        d = self.cleaned_data
        Member.objects.create(user=user, name=d["name"], gender=d["gender"], age=d["age"], city=d["city"], occupation=d["occupation"])
        return user

class ProfileForm(forms.ModelForm):
    city = forms.ChoiceField(choices=CITY)
    age = forms.IntegerField(min_value=18, max_value=99)
    class Meta:
        model = Member
        fields = ["name", "age", "gender", "city", "occupation", "intention", "religion", "bio", "photo"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 4, "placeholder": "Tell others about yourself and what you are looking for."})}
