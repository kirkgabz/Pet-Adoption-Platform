from .models import Shelter


def staff_sidebar_profile(request):
    user = getattr(request, "user", None)
    shelter = None

    if getattr(user, "is_authenticated", False) and user.is_staff:
        if user.is_superuser:
            shelter = Shelter.objects.order_by("name").first()
        else:
            shelter = Shelter.objects.filter(email__iexact=user.email).order_by("name").first()

    return {"staff_sidebar_shelter": shelter}
