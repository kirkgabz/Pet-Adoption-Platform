from urllib.parse import urlencode

from django.urls import reverse

from .models import AdopterProfile


def adopter_has_completed_onboarding(user):
    if not getattr(user, "is_authenticated", False) or user.is_staff:
        return True
    try:
        return user.adopter_profile.is_complete
    except AdopterProfile.DoesNotExist:
        return False


def adopter_onboarding_redirect_url(next_url=""):
    url = reverse("adopter-onboarding")
    if next_url:
        return f"{url}?{urlencode({'next': next_url})}"
    return url
