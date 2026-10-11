"""Generic list / add / edit / delete pages for every Resource, plus staff accounts and site settings.
Every change is written to the audit log (Django's LogEntry) so the Super Admin can see who did what."""
from django import forms
from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import select_template
from django.urls import reverse
from django.views.decorators.http import require_POST
from core.models import SiteSetting
from .resources import REGISTRY, SIDEBAR
from .views import OWNER_GROUP, is_owner, owner_required, page, staff_required

def audit(request, objs, flag, msg=""):
    objs = [o for o in objs if o is not None and o.pk is not None]
    if objs:
        LogEntry.objects.log_actions(request.user.pk, objs, flag, change_message=msg, single_object=len(objs) == 1)

def resource_or_404(request, key):
    r = REGISTRY.get(key)
    if r is None: raise Http404
    if r.owner_only and not is_owner(request.user):
        raise Http404
    return r

def safe_back(request, default):
    back = request.POST.get("back") or request.GET.get("back") or ""
    return back if back.startswith("/") and not back.startswith("//") else default

def section_links(r):
    from .resources import REGISTRY as R
    return [(k, R[k].title) for k in SIDEBAR.get(r.nav, [])]

@staff_required
def manage_list(request, key):
    r = resource_or_404(request, key)
    if key == "members": return redirect("dash_members")
    g = request.GET
    pg = Paginator(r.filtered(g), r.per_page).get_page(g.get("page"))
    rows = [{"obj": o, "cells": [fn(o) for _, fn in r.columns], "link": r.row_link(o) if r.row_link else None} for o in pg.object_list]
    params = g.copy(); params.pop("page", None)
    return page(request, "dashboard/res_list.html", {"nav": r.nav, "sub": key, "r": r, "rows": rows, "pg": pg, "f": g, "qs": params.urlencode(),
        "filters": [(k, label, choices()) for k, label, choices, _ in r.filters], "section": section_links(r),
        "page_range": pg.paginator.get_elided_page_range(pg.number, on_each_side=2, on_ends=1)})

def edit_page(request, r, obj):
    created = obj is None
    if (created and not r.can_add) or (not created and not r.can_edit) or r.form is None: raise Http404
    form = r.form(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        r.after_save(obj, request, created)
        audit(request, [obj], ADDITION if created else CHANGE, "Added from the dashboard" if created else
              ("Changed " + ", ".join(form.changed_data) if form.changed_data else "Saved without changes"))
        messages.success(request, f"{obj} {'added' if created else 'saved'}.")
        if "another" in request.POST: return redirect(reverse("dash_manage_add", args=[r.key]))
        return redirect(safe_back(request, reverse("dash_members") if r.key == "members" else reverse("dash_manage", args=[r.key])))
    detail = select_template([f"dashboard/res_detail_{r.key}.html", "dashboard/res_detail_none.html"]).template.name
    return page(request, "dashboard/res_form.html", {"nav": r.nav, "sub": r.key, "r": r, "form": form, "obj": obj, "created": created,
        "detail": detail, "section": section_links(r), "back": safe_back(request, "")})

@staff_required
def manage_add(request, key):
    return edit_page(request, resource_or_404(request, key), None)

@staff_required
def manage_edit(request, key, pk):
    r = resource_or_404(request, key)
    return edit_page(request, r, get_object_or_404(r.queryset(), pk=pk))

@staff_required
@require_POST
def manage_delete(request, key, pk):
    r = resource_or_404(request, key)
    if not r.can_delete: raise Http404
    obj = get_object_or_404(r.model, pk=pk)
    if key == "members" and obj.user_id and (obj.user.is_staff or obj.user == request.user):
        messages.error(request, "Staff accounts can't be deleted here."); return redirect(safe_back(request, reverse("dash_members")))
    label = str(obj)
    audit(request, [obj], DELETION, "Deleted from the dashboard")
    try:
        if key == "members" and obj.user_id: obj.user.delete()
        else: obj.delete()
        messages.success(request, f"{label} deleted.")
    except ProtectedError:
        messages.error(request, f"{label} is still in use, so it can't be deleted.")
    return redirect(safe_back(request, reverse("dash_members") if key == "members" else reverse("dash_manage", args=[key])))

@staff_required
@require_POST
def manage_action(request, key, pk):
    r = resource_or_404(request, key)
    act = r.actions.get(request.POST.get("act"))
    if not act: raise Http404
    obj = get_object_or_404(r.queryset(), pk=pk)
    result = act[2](obj, request)
    audit(request, [obj], CHANGE, f"{act[0]}: {result}")
    messages.success(request, f"{obj} {result}.")
    return redirect(safe_back(request, reverse("dash_manage", args=[key])))

# ---------- staff accounts (Super Admin only) ----------
ROLES = [("admin", "Administrator"), ("owner", "Super Admin")]

class StaffForm(forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150, required=False, label="First name")
    last_name = forms.CharField(max_length=150, required=False, label="Last name")
    email = forms.EmailField()
    role = forms.ChoiceField(choices=ROLES, help_text="A Super Admin can also manage staff accounts, site settings and the audit log.")
    is_active = forms.BooleanField(required=False, initial=True, label="Account active", help_text="Untick to block this person from signing in.")
    password = forms.CharField(widget=forms.PasswordInput(render_value=False), required=False,
                               help_text="Required for a new account. Leave empty to keep the current password.")
    def __init__(self, *a, instance=None, **kw):
        self.instance = instance; super().__init__(*a, **kw)
        if instance is None: self.fields["password"].required = True
    def clean_username(self):
        u = self.cleaned_data["username"].strip()
        if get_user_model().objects.filter(username__iexact=u).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise ValidationError("This username is taken.")
        return u
    def clean_email(self):
        e = self.cleaned_data["email"].lower()
        if get_user_model().objects.filter(email__iexact=e).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise ValidationError("Another account uses this email.")
        return e
    def clean_password(self):
        p = self.cleaned_data.get("password")
        if p: validate_password(p, self.instance)
        return p

@owner_required
def staff_list(request):
    User = get_user_model()
    rows = User.objects.filter(is_staff=True, is_superuser=False).order_by("-is_active", "username")
    for u in rows: u.role = "Super Admin" if u.groups.filter(name=OWNER_GROUP).exists() else "Administrator"
    return page(request, "dashboard/staff_list.html", {"nav": "users", "sub": "staff", "rows": rows})

@owner_required
def staff_edit(request, pk=None):
    User = get_user_model()
    user = get_object_or_404(User, pk=pk, is_staff=True, is_superuser=False) if pk else None
    initial = {"username": user.username, "first_name": user.first_name, "last_name": user.last_name, "email": user.email, "is_active": user.is_active,
               "role": "owner" if user.groups.filter(name=OWNER_GROUP).exists() else "admin"} if user else {"is_active": True}
    form = StaffForm(request.POST or None, instance=user, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        if user == request.user and (d["role"] != "owner" or not d["is_active"]):
            form.add_error(None, "You can't remove your own Super Admin role or block your own account.")
        else:
            created = user is None
            user = user or User(is_staff=True)
            user.username, user.first_name, user.last_name, user.email, user.is_active = d["username"], d["first_name"], d["last_name"], d["email"], d["is_active"]
            if d["password"]: user.set_password(d["password"])
            user.save()
            owners, _ = Group.objects.get_or_create(name=OWNER_GROUP)
            if d["role"] == "owner": user.groups.add(owners)
            else: user.groups.remove(owners)
            audit(request, [user], ADDITION if created else CHANGE, f"Staff account {'created' if created else 'updated'} ({dict(ROLES)[d['role']]})")
            messages.success(request, f"{user.username} {'created' if created else 'saved'}.")
            return redirect("dash_staff")
    return page(request, "dashboard/staff_form.html", {"nav": "users", "sub": "staff", "form": form, "obj": user})

@owner_required
@require_POST
def staff_delete(request, pk):
    user = get_object_or_404(get_user_model(), pk=pk, is_staff=True, is_superuser=False)
    if user == request.user:
        messages.error(request, "You can't delete your own account."); return redirect("dash_staff")
    audit(request, [user], DELETION, "Staff account deleted")
    name = user.username; user.delete()
    messages.success(request, f"{name} deleted.")
    return redirect("dash_staff")

# ---------- site settings (Super Admin only) ----------
class SettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSetting
        fields = ["brand", "tagline", "currency", "contact_email", "contact_whatsapp", "payment_instructions", "hero_title_1", "hero_title_2",
                  "hero_text", "hero_quote", "offer_text", "logo", "hero_image", "premium_image", "advert_image"]
        widgets = {"payment_instructions": forms.Textarea(attrs={"rows": 4}), "hero_text": forms.Textarea(attrs={"rows": 3}), "hero_quote": forms.Textarea(attrs={"rows": 2})}

from .resources import pretty_files
pretty_files(SettingsForm)

SETTINGS_SECTIONS = [("Business details", ["brand", "tagline", "currency", "contact_email", "contact_whatsapp"]),
                     ("Payments", ["payment_instructions"]),
                     ("Home page", ["hero_title_1", "hero_title_2", "hero_text", "hero_quote", "offer_text"]),
                     ("Images", ["logo", "hero_image", "premium_image", "advert_image"])]

@owner_required
def site_settings(request):
    obj = SiteSetting.load()
    form = SettingsForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save(); audit(request, [obj], CHANGE, "Changed " + ", ".join(form.changed_data) if form.changed_data else "Saved")
        messages.success(request, "Settings saved."); return redirect("dash_settings")
    sections = [(title, [form[f] for f in names]) for title, names in SETTINGS_SECTIONS]
    return page(request, "dashboard/settings.html", {"nav": "settings", "sub": "settings", "form": form, "sections": sections})

# ---------- own password ----------
@staff_required
def password(request):
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.forms import PasswordChangeForm
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        update_session_auth_hash(request, form.save()); messages.success(request, "Password changed.")
        return redirect("dashboard")
    return page(request, "dashboard/password.html", {"nav": "", "form": form})
