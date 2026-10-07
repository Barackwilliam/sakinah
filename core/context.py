from .forms import LoginForm, SignupForm
from .models import Message, SiteSetting

def site(request):
    ctx = {"site": SiteSetting.load(), "current": request.resolver_match.url_name if request.resolver_match else ""}
    user = getattr(request, "user", None)
    if user is None: return ctx
    if user.is_authenticated:
        ctx["unread"] = Message.objects.filter(to__user=user, read=False).count()
        ctx["n_notes"] = user.notifications.filter(read=False).count()
    else:
        ctx["modal_login"], ctx["modal_signup"] = LoginForm(request, auto_id="li_%s"), SignupForm(auto_id="su_%s")
    return ctx
