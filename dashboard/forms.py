from django.utils.translation import gettext_lazy as _l
from django.utils.translation import gettext as _, ngettext
from django import forms
from core.forms import LOCATIONS
from core.models import Broadcast, Member, Payment, Plan

class BroadcastForm(forms.ModelForm):
    gender = forms.ChoiceField(required=False, choices=[("", _l("All")), ("F", _l("Women")), ("M", _l("Men"))])
    verified = forms.ChoiceField(required=False, choices=[("", _l("All")), ("yes", _l("Verified")), ("no", _l("Not verified"))])
    age_min = forms.IntegerField(required=False, min_value=18, max_value=99)
    age_max = forms.IntegerField(required=False, min_value=18, max_value=99)
    city = forms.ChoiceField(required=False, choices=[("", _l("All Locations"))] + [(c, c) for c in LOCATIONS])
    plan = forms.ChoiceField(required=False)
    class Meta:
        model = Broadcast
        fields = ["channel", "subject", "body"]
        widgets = {"channel": forms.HiddenInput, "body": forms.Textarea(attrs={"rows": 6, "placeholder": _l("Write your message here... Use {name} for the member's name.")}),
                   "subject": forms.TextInput(attrs={"placeholder": _l("Enter message subject")})}
        labels = {"body": _l("Message")}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].choices = [("", _l("All Plans")), ("free", _l("Free members")), ("premium", _l("Any paid plan"))] + \
            [(p.name, p.name) for p in Plan.objects.filter(price__gt=0)]
    def filters(self):
        d = self.cleaned_data
        return {k: d.get(k) or "" for k in ("gender", "verified", "age_min", "age_max", "city", "plan") if d.get(k)}

class PaymentForm(forms.ModelForm):
    member = forms.ModelChoiceField(queryset=Member.objects.filter(user__isnull=False).order_by("name"), required=False,
                                    help_text=_l("Choose a member to activate their plan automatically."))
    class Meta:
        model = Payment
        fields = ["member", "payer_name", "payer_phone", "kind", "plan", "months", "amount", "gateway", "reference", "status", "description"]
        labels = {"amount": _l("Amount (TSh)")}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payer_name"].required = False
        if self.instance.pk and self.instance.user_id:      # editing: show the member it already belongs to
            self.fields["member"].initial = getattr(self.instance.user, "member", None)
    def clean(self):
        d = super().clean()
        m = d.get("member")
        if m:
            self.instance.user = m.user
            if not d.get("payer_name"): d["payer_name"] = m.name; self.instance.payer_name = m.name
            if not d.get("payer_phone"): self.instance.payer_phone = m.phone
        if not d.get("payer_name") and not m: self.add_error("payer_name", _("Enter the payer's name or choose a member."))
        if d.get("kind") == "premium" and not d.get("plan"): self.add_error("plan", _("Choose the plan that was paid for."))
        return d
