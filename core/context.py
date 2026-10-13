from django.utils.functional import SimpleLazyObject
from .forms import LoginForm, SignupForm
from .models import Message, SiteSetting

def site(request):
    ctx = {"site": SiteSetting.load(), "current": request.resolver_match.url_name if request.resolver_match else ""}
    user = getattr(request, "user", None)
    if user is None: return ctx
    if user.is_authenticated:
        # counted only if a template actually shows them (the dashboards supply their own)
        ctx["unread"] = SimpleLazyObject(lambda: Message.objects.filter(to__user=user, read=False).count())
        ctx["n_notes"] = SimpleLazyObject(lambda: user.notifications.filter(read=False).count())
    else:
        ctx["modal_login"] = SimpleLazyObject(lambda: LoginForm(request, auto_id="li_%s"))
        ctx["modal_signup"] = SimpleLazyObject(lambda: SignupForm(auto_id="su_%s"))
    return ctx
