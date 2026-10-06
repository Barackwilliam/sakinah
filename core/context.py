from .models import SiteSetting
def site(request):
    return {"site": SiteSetting.load(), "current": request.resolver_match.url_name if request.resolver_match else ""}
