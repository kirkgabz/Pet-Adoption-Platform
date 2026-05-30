from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from .onboarding import adopter_has_completed_onboarding, adopter_onboarding_redirect_url


class AdopterOnboardingRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._requires_onboarding(request):
            return redirect(adopter_onboarding_redirect_url(request.get_full_path()))
        return self.get_response(request)

    def _requires_onboarding(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or user.is_staff:
            return False

        path = request.path_info
        if path in {
            reverse("home"),
            reverse("pet-list"),
            reverse("adopter-onboarding"),
            reverse("logout"),
            reverse("login"),
        }:
            return False

        if self._is_asset_path(path):
            return False

        return not adopter_has_completed_onboarding(user)

    @staticmethod
    def _is_asset_path(path):
        for url in (getattr(settings, "STATIC_URL", ""), getattr(settings, "MEDIA_URL", "")):
            if not url:
                continue
            asset_path = "/" + url.lstrip("/")
            if path.startswith(asset_path):
                return True
        return False
