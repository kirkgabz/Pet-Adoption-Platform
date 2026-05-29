from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .models import AdopterProfile


class PetAdoptionSocialAccountAdapter(DefaultSocialAccountAdapter):
    role_session_key = "google_account_role"

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        self.apply_google_role(request, user)
        return user

    def pre_social_login(self, request, sociallogin):
        user = getattr(sociallogin, "user", None)
        if user and getattr(user, "pk", None):
            self.apply_google_role(request, user)

    def apply_google_role(self, request, user):
        role = request.session.pop(self.role_session_key, "user")
        if role == "staff" and not user.is_staff:
            user.is_staff = True
            user.save(update_fields=["is_staff"])
        if not user.is_staff:
            AdopterProfile.objects.get_or_create(user=user)
