from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.db.models import Case, Count, IntegerField, Max, Prefetch, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from .forms import (
    AdopterProfileForm,
    AdoptionApplicationForm,
    ApplicationStatusForm,
    MessageForm,
    PersonalityTagForm,
    PetForm,
    ShelterForm,
    UserRegisterForm,
    UserUpdateForm,
)
import datetime
import os

from django.conf import settings
from django.core.cache import cache

try:
    import requests
except Exception:
    requests = None

from .models import AdopterProfile, AdoptionApplication, ConversationMessage, FavoritePet, Pet, PersonalityTag, Shelter
from .onboarding import adopter_has_completed_onboarding, adopter_onboarding_redirect_url


def is_google_login_configured(request):
    google_settings = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}).get("google", {})
    if google_settings.get("APP") or google_settings.get("APPS"):
        return True

    try:
        from allauth.socialaccount.models import SocialApp

        return SocialApp.objects.on_site(request).filter(provider="google").exists()
    except Exception:
        return False


def staff_shelters_for(user):
    if user.is_superuser:
        return Shelter.objects.all()
    if user.is_staff:
        return Shelter.objects.filter(email__iexact=user.email)
    return Shelter.objects.none()


def staff_pets_for(user):
    queryset = (
        Pet.objects.select_related("shelter", "posted_by")
        .prefetch_related("personality_tags")
        .annotate(application_count=Count("applications", distinct=True))
    )
    if user.is_superuser:
        return queryset
    if user.is_staff:
        return queryset.filter(Q(posted_by=user) | Q(shelter__email__iexact=user.email)).distinct()
    return queryset.none()


def staff_applications_for(user):
    queryset = AdoptionApplication.objects.select_related("pet", "applicant", "pet__shelter")
    if user.is_superuser:
        return queryset
    if user.is_staff:
        return queryset.filter(Q(pet__posted_by=user) | Q(pet__shelter__email__iexact=user.email)).distinct()
    return queryset.none()


def first_staff_shelter(user):
    return staff_shelters_for(user).order_by("name").first()


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = 'login'

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Shelter staff access is required for that page.")
            return redirect("pet-list")
        return super().handle_no_permission()


class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = "login"

    def test_func(self):
        return self.request.user.is_superuser


class LandingView(TemplateView):
    template_name = "adoption/landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["landing_pets"] = (
            Pet.objects.select_related("shelter")
            .prefetch_related("personality_tags")
            .filter(status=Pet.Status.AVAILABLE, is_archived=False)
            .order_by("-created_at")[:6]
        )
        return context


class RoleBasedLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = AuthenticationForm

    def form_valid(self, form):
        role = self.request.POST.get("login_role", "user")
        user = form.get_user()
        if role == "staff" and not user.is_staff:
            form.add_error(None, "Please log in with a shelter staff account.")
            return self.form_invalid(form)
        if role == "user" and user.is_staff:
            form.add_error(None, "This is a shelter staff account. Choose Shelter Staff Login.")
            return self.form_invalid(form)
        self.authenticated_user = user
        return super().form_valid(form)

    def get_success_url(self):
        success_url = super().get_success_url()
        user = getattr(self, "authenticated_user", self.request.user)
        if not adopter_has_completed_onboarding(user):
            return adopter_onboarding_redirect_url(success_url)
        return success_url

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        login_role = self.request.POST.get("login_role") or self.request.GET.get("role")
        if login_role not in {"user", "staff"}:
            login_role = None
        context["login_role"] = login_role
        context["google_login_configured"] = is_google_login_configured(self.request)
        context["show_google_login"] = context["google_login_configured"] and login_role == "user"
        return context


def google_login(request):
    if not is_google_login_configured(request):
        messages.error(request, "Google login is not configured yet. Use username and password to log in.")
        return redirect("login")

    from allauth.socialaccount.providers.google.views import oauth2_login

    return oauth2_login(request)


class PetListView(LoginRequiredMixin, ListView):
    model = Pet
    paginate_by = 9

    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and request.user.is_staff
            and not request.user.is_superuser
            and not staff_shelters_for(request.user).exists()
        ):
            messages.info(request, "Create or link your shelter profile before opening the dashboard.")
            return redirect("shelter-create")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        if self.request.user.is_staff:
            queryset = staff_pets_for(self.request.user)
        else:
            queryset = Pet.objects.select_related("shelter").prefetch_related("personality_tags").filter(is_archived=False)
        query = self.request.GET.get("q")
        species = self.request.GET.get("species")
        status = self.request.GET.get("status")
        tag = self.request.GET.get("tag")
        if self.request.user.is_staff and status == "archived":
            queryset = queryset.filter(is_archived=True)
            status = None
        elif self.request.user.is_staff:
            queryset = queryset.filter(is_archived=False)
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(breed__icontains=query) | Q(description__icontains=query)
            )
        if species:
            queryset = queryset.filter(species=species)
        if status:
            queryset = queryset.filter(status=status)
        if tag:
            queryset = queryset.filter(personality_tags__id=tag)
        # Randomize available pets order for the dashboard
        return queryset.distinct().order_by('?')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pet_scope = staff_pets_for(self.request.user) if self.request.user.is_staff else Pet.objects.all()
        active_pet_scope = pet_scope.filter(is_archived=False)
        application_scope = (
            staff_applications_for(self.request.user)
            if self.request.user.is_staff
            else AdoptionApplication.objects.filter(applicant=self.request.user)
        )
        context["species_choices"] = Pet.Species.choices
        context["status_choices"] = Pet.Status.choices
        context["tags"] = PersonalityTag.objects.all()
        context["featured_pet"] = (
            active_pet_scope.select_related("shelter")
            .prefetch_related("personality_tags")
            .filter(status__in=[Pet.Status.AVAILABLE, Pet.Status.PENDING])
            .order_by("-created_at")
            .first()
        )
        context["latest_pets"] = (
            active_pet_scope.select_related("shelter")
            .prefetch_related("personality_tags")
            .order_by("-created_at")[:4]
        )
        context["recent_applications"] = application_scope.order_by("-created_at")[:4]
        context["pet_counts"] = {
            "total": active_pet_scope.count(),
            "available": active_pet_scope.filter(status=Pet.Status.AVAILABLE).count(),
            "pending": active_pet_scope.filter(status=Pet.Status.PENDING).count(),
            "adopted": active_pet_scope.filter(status=Pet.Status.ADOPTED).count(),
            "archived": pet_scope.filter(is_archived=True).count() if self.request.user.is_staff else 0,
        }
        context["shelter_count"] = staff_shelters_for(self.request.user).count() if self.request.user.is_staff else Shelter.objects.count()
        context["application_counts"] = dict(
            application_scope.values_list("status").annotate(total=Count("id"))
        )
        context["dashboard_pet_title"] = "Your Posted Pets" if self.request.user.is_staff else "Available Pets"
        context["dashboard_tip_title"] = (
            "Review applications quickly." if self.request.user.is_staff else "Strong profiles get better matches."
        )
        context["dashboard_tip_text"] = (
            "Keep pet listings current and review new adoption applications so adopters get clear next steps."
            if self.request.user.is_staff
            else "Add clear photos, personality tags, and honest care notes so adopters know what life with each pet feels like."
        )
        if self.request.user.is_staff:
            context.update(self.get_staff_dashboard_context(pet_scope, application_scope))
            context["active_applications"] = []
            context["saved_pets"] = []
            context["recent_shelter_messages"] = []
            context["recommended_pets"] = []
        else:
            context.update(self.get_adopter_dashboard_context(application_scope))
        # Current date
        context["current_date"] = datetime.datetime.now()

        # Get temperature for today's location (use first shelter city if available)
        context["current_temp"] = None
        context["current_temp_f"] = None
        context["weather_icon"] = None
        context["weather_desc"] = None
        if self.request.user.is_staff:
            context["available_pets"] = active_pet_scope.order_by("-created_at")[:3]
        else:
            context["available_pets"] = (
                Pet.objects.select_related("shelter")
                .prefetch_related("personality_tags")
                .filter(status=Pet.Status.AVAILABLE, is_archived=False)
                .order_by("-created_at")[:3]
            )
        api_key = getattr(settings, "OPENWEATHER_API_KEY", None) or os.environ.get("OPENWEATHER_API_KEY")
        city = None
        first_shelter = Shelter.objects.first()
        if first_shelter and first_shelter.city:
            city = first_shelter.city
        else:
            city = getattr(settings, "DEFAULT_CITY", None) or "London"

        if api_key and requests:
            cache_key = f"weather_{city.lower()}"
            cached = cache.get(cache_key)
            data = None
            if cached:
                data = cached
            else:
                try:
                    url = f"https://api.openweathermap.org/data/2.5/weather"
                    params = {"q": city, "units": "metric", "appid": api_key}
                    res = requests.get(url, params=params, timeout=4)
                    if res.status_code == 200:
                        data = res.json()
                        # cache for 15 minutes
                        cache.set(cache_key, data, 900)
                except Exception:
                    data = None

            if data:
                temp = data.get("main", {}).get("temp")
                if temp is not None:
                    c = round(float(temp))
                    f = round((c * 9.0 / 5.0) + 32)
                    context["current_temp"] = c
                    context["current_temp_f"] = f
                weather = data.get("weather")
                if weather and isinstance(weather, list) and weather:
                    context["weather_icon"] = weather[0].get("icon")
                    context["weather_desc"] = weather[0].get("description")
        else:
            # No API key or requests unavailable — provide a deterministic fallback
            # based on city name so the dashboard always shows a temperature.
            try:
                base = (sum(ord(c) for c in (city or '')) % 12) + 12
                c = int(base)
                f = round((c * 9.0 / 5.0) + 32)
                context["current_temp"] = c
                context["current_temp_f"] = f
                context["weather_icon"] = '01d'
                context["weather_desc"] = 'clear sky'
            except Exception:
                context["current_temp"] = None
                context["current_temp_f"] = None
                context["weather_icon"] = None
                context["weather_desc"] = None

        return context

    def get_staff_dashboard_context(self, pet_scope, application_scope):
        staff_shelter = first_staff_shelter(self.request.user)
        missing_fields = staff_shelter.profile_missing_fields if staff_shelter else []
        profile_field_total = 7
        profile_completion = 0
        if staff_shelter:
            profile_completion = round(((profile_field_total - len(missing_fields)) / profile_field_total) * 100)
        unread_messages = (
            ConversationMessage.objects.select_related("application", "application__pet", "sender")
            .filter(application__in=application_scope, sender__is_staff=False, read_at__isnull=True)
            .order_by("-created_at")
        )
        new_applications = application_scope.filter(status=AdoptionApplication.Status.SUBMITTED)
        active_pet_scope = pet_scope.filter(is_archived=False)
        available_pets = active_pet_scope.filter(status=Pet.Status.AVAILABLE)
        pending_pets = active_pet_scope.filter(status=Pet.Status.PENDING)
        return {
            "staff_shelter": staff_shelter,
            "shelter_profile_missing_fields": missing_fields,
            "shelter_profile_completion": profile_completion,
            "staff_new_applications": new_applications.order_by("-created_at")[:5],
            "staff_available_pets": available_pets.order_by("-created_at")[:5],
            "staff_pending_pets": pending_pets.order_by("-created_at")[:5],
            "staff_unread_messages": unread_messages[:5],
            "staff_dashboard_summary": {
                "new_applications": new_applications.count(),
                "available_pets": available_pets.count(),
                "pending_pets": pending_pets.count(),
                "unread_messages": unread_messages.count(),
                "profile_completion": profile_completion,
                "archived_pets": pet_scope.filter(is_archived=True).count(),
            },
        }

    def get_adopter_dashboard_context(self, application_scope):
        active_statuses = [
            AdoptionApplication.Status.SUBMITTED,
            AdoptionApplication.Status.REVIEWING,
            AdoptionApplication.Status.APPROVED,
        ]
        active_applications = (
            application_scope.select_related("pet", "pet__shelter")
            .filter(status__in=active_statuses)
            .order_by("-created_at")[:4]
        )
        saved_pets = (
            Pet.objects.select_related("shelter")
            .prefetch_related("personality_tags")
            .filter(favorited_by__user=self.request.user)
            .order_by("-favorited_by__created_at")[:4]
        )
        recent_shelter_messages = (
            ConversationMessage.objects.select_related("application", "application__pet", "sender")
            .filter(application__applicant=self.request.user, sender__is_staff=True)
            .order_by("-created_at")[:4]
        )
        return {
            "active_applications": active_applications,
            "saved_pets": saved_pets,
            "recent_shelter_messages": recent_shelter_messages,
            "recommended_pets": self.get_recommended_pets(application_scope),
        }

    def get_recommended_pets(self, application_scope):
        queryset = (
            Pet.objects.select_related("shelter")
            .prefetch_related("personality_tags")
            .filter(status=Pet.Status.AVAILABLE, is_archived=False)
        )
        applied_pet_ids = application_scope.values_list("pet_id", flat=True)
        queryset = queryset.exclude(id__in=applied_pet_ids)

        try:
            profile = self.request.user.adopter_profile
        except AdopterProfile.DoesNotExist:
            profile = None

        if profile and profile.preferred_species:
            queryset = queryset.filter(species=profile.preferred_species)

        if profile and profile.city:
            city = profile.city.split(",")[0].strip()
            if city:
                queryset = queryset.annotate(
                    location_match=Case(
                        When(shelter__city__icontains=city, then=Value(0)),
                        default=Value(1),
                        output_field=IntegerField(),
                    )
                ).order_by("location_match", "-created_at")
                return queryset[:4]

        return queryset.order_by("-created_at")[:4]


class StaffPetManagementView(StaffRequiredMixin, ListView):
    model = Pet
    template_name = "adoption/staff_pet_management.html"
    paginate_by = 12

    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and request.user.is_staff
            and not request.user.is_superuser
            and not staff_shelters_for(request.user).exists()
        ):
            messages.info(request, "Create or link your shelter profile before managing pets.")
            return redirect("shelter-create")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = staff_pets_for(self.request.user)
        query = self.request.GET.get("q", "").strip()
        species = self.request.GET.get("species")
        status = self.request.GET.get("status") or "active"

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(breed__icontains=query)
                | Q(description__icontains=query)
                | Q(shelter__name__icontains=query)
                | Q(shelter__city__icontains=query)
            )
        if species:
            queryset = queryset.filter(species=species)
        if status == "archived":
            queryset = queryset.filter(is_archived=True)
        else:
            queryset = queryset.filter(is_archived=False)
            if status in Pet.Status.values:
                queryset = queryset.filter(status=status)

        return queryset.distinct().order_by("-updated_at", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pet_scope = staff_pets_for(self.request.user)
        active_pet_scope = pet_scope.filter(is_archived=False)
        context["species_choices"] = Pet.Species.choices
        context["status_choices"] = Pet.Status.choices
        context["selected_species"] = self.request.GET.get("species", "")
        context["selected_status"] = self.request.GET.get("status") or "active"
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["staff_pet_counts"] = {
            "active": active_pet_scope.count(),
            "available": active_pet_scope.filter(status=Pet.Status.AVAILABLE).count(),
            "pending": active_pet_scope.filter(status=Pet.Status.PENDING).count(),
            "adopted": active_pet_scope.filter(status=Pet.Status.ADOPTED).count(),
            "archived": pet_scope.filter(is_archived=True).count(),
        }
        context["staff_shelter"] = first_staff_shelter(self.request.user)
        return context


class PetDetailView(DetailView):
    model = Pet

    def get_queryset(self):
        queryset = (
            Pet.objects.select_related("shelter", "posted_by")
            .prefetch_related("personality_tags")
            .annotate(application_count=Count("applications", distinct=True))
        )
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return queryset
        return queryset.filter(is_archived=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["can_manage_pet"] = (
            user.is_authenticated
            and (
                user.is_superuser
                or (user.is_staff and staff_pets_for(user).filter(pk=self.object.pk).exists())
            )
        )
        context["is_favorite"] = (
            user.is_authenticated
            and not user.is_staff
            and FavoritePet.objects.filter(user=user, pet=self.object).exists()
        )
        return context


class AvailablePetsView(ListView):
    model = Pet
    template_name = "adoption/available_pets.html"
    paginate_by = 12
    context_object_name = "object_list"
    near_me_radius_km = 25.0
    age_choices = (
        ("0-1", "Up to 1 year"),
        ("2-3", "2 to 3 years"),
        ("4-7", "4 to 7 years"),
        ("8-plus", "8+ years"),
    )

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff:
            messages.info(request, "Shelter staff accounts manage pets from the Manage Pets page.")
            return redirect("staff-pet-list")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = (
            Pet.objects.select_related("shelter")
            .prefetch_related("personality_tags")
            .filter(status=Pet.Status.AVAILABLE, is_archived=False)
        )
        species = self.request.GET.get("species")
        location = self.request.GET.get("location")
        tag = self.request.GET.get("tag")
        shelter = self.request.GET.get("shelter")
        age = self.request.GET.get("age")
        latitude = self.request.GET.get("lat")
        longitude = self.request.GET.get("lng")
        if species:
            queryset = queryset.filter(species=species)
        if location:
            queryset = queryset.filter(
                Q(shelter__name__icontains=location)
                | Q(shelter__city__icontains=location)
                | Q(shelter__address__icontains=location)
            )
        if tag:
            queryset = queryset.filter(personality_tags__id=tag)
        if shelter and shelter.isdigit():
            queryset = queryset.filter(shelter_id=shelter)
        queryset = self.filter_by_age(queryset, age)
        queryset = queryset.distinct()
        if latitude and longitude:
            return self.get_nearby_pet_list(queryset, latitude, longitude)
        return queryset.order_by('?')

    def filter_by_age(self, queryset, age):
        if age == "0-1":
            return queryset.filter(age__lte=1)
        if age == "2-3":
            return queryset.filter(age__gte=2, age__lte=3)
        if age == "4-7":
            return queryset.filter(age__gte=4, age__lte=7)
        if age == "8-plus":
            return queryset.filter(age__gte=8)
        return queryset

    def get_radius(self):
        try:
            radius = float(self.request.GET.get("radius") or self.near_me_radius_km)
        except (TypeError, ValueError):
            radius = self.near_me_radius_km
        return max(radius, 1.0)

    def get_nearby_pet_list(self, queryset, latitude, longitude):
        try:
            latf = float(latitude)
            lngf = float(longitude)
        except (TypeError, ValueError):
            messages.error(self.request, "Could not use your current location. Please try again or type your city.")
            return queryset.none()

        radius = self.get_radius()
        shelter_ids = queryset.values_list("shelter_id", flat=True).distinct()
        shelters = (
            Shelter.objects.filter(id__in=shelter_ids)
            .exclude(latitude__isnull=True)
            .exclude(longitude__isnull=True)
        )
        distances = {}
        for shelter in shelters:
            distance = shelter.distance_to(latf, lngf)
            if distance is not None and distance <= radius:
                distances[shelter.id] = distance

        nearby_pets = list(queryset.filter(shelter_id__in=list(distances)))
        for pet in nearby_pets:
            pet.distance_km = distances.get(pet.shelter_id)
        nearby_pets.sort(key=lambda pet: (pet.distance_km if pet.distance_km is not None else radius, pet.name.lower()))
        return nearby_pets

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["species_choices"] = Pet.Species.choices
        context["tags"] = PersonalityTag.objects.all()
        context["shelters"] = (
            Shelter.objects.filter(pets__status=Pet.Status.AVAILABLE, pets__is_archived=False)
            .distinct()
            .order_by("name")
        )
        context["age_choices"] = self.age_choices
        application_initial = {}
        if self.request.user.is_authenticated and not self.request.user.is_staff:
            application_initial = adopter_profile_initial(self.request.user)
            context["favorite_pet_ids"] = set(
                FavoritePet.objects.filter(user=self.request.user).values_list("pet_id", flat=True)
            )
        else:
            context["favorite_pet_ids"] = set()
        context["application_form"] = AdoptionApplicationForm(initial=application_initial)
        context["near_me_active"] = bool(self.request.GET.get("lat") and self.request.GET.get("lng"))
        context["near_me_radius"] = self.get_radius()
        return context


class PetCreateView(StaffRequiredMixin, CreateView):
    model = Pet
    form_class = PetForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff and not request.user.is_superuser:
            if not staff_shelters_for(request.user).exists():
                messages.error(request, "Complete your shelter profile before posting pets.")
                return redirect("shelter-create")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["include_status"] = False
        return kwargs

    def form_valid(self, form):
        form.instance.posted_by = self.request.user
        form.instance.status = Pet.Status.AVAILABLE
        messages.success(self.request, "Pet posted for adoption.")
        return super().form_valid(form)


class PetOwnershipMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        pet = self.get_object()
        if self.request.user.is_superuser:
            return True
        if self.request.user.is_staff:
            return staff_pets_for(self.request.user).filter(pk=pet.pk).exists()
        return False


class PetUpdateView(StaffRequiredMixin, UpdateView):
    model = Pet
    form_class = PetForm

    def get_queryset(self):
        return staff_pets_for(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class PetDeleteView(PetOwnershipMixin, DeleteView):
    model = Pet
    success_url = reverse_lazy("staff-pet-list")


def update_pet_state(request, pk):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.path}")
    if not request.user.is_staff:
        messages.error(request, "Shelter staff access is required for that action.")
        return redirect("pet-list")
    if request.method != "POST":
        return redirect("pet-detail", pk=pk)

    pet = get_object_or_404(staff_pets_for(request.user), pk=pk)
    action = request.POST.get("action")
    status = request.POST.get("status")
    if action == "archive":
        pet.is_archived = True
        pet.archived_at = timezone.now()
        pet.save(update_fields=["is_archived", "archived_at", "updated_at"])
        messages.success(request, f"{pet.name} was archived.")
    elif action == "restore":
        pet.is_archived = False
        pet.archived_at = None
        pet.save(update_fields=["is_archived", "archived_at", "updated_at"])
        messages.success(request, f"{pet.name} was restored.")
    elif status in Pet.Status.values:
        pet.status = status
        pet.is_archived = False
        pet.archived_at = None
        pet.save(update_fields=["status", "is_archived", "archived_at", "updated_at"])
        messages.success(request, f"{pet.name} was marked {pet.get_status_display()}.")
    else:
        messages.error(request, "Choose a valid pet status.")

    return redirect(get_safe_redirect_url(request) or pet.get_absolute_url())


class ShelterListView(ListView):
    model = Shelter
    paginate_by = 10

    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            queryset = staff_shelters_for(self.request.user)
        else:
            queryset = Shelter.objects.all()
        query = self.request.GET.get("q")
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(city__icontains=query) | Q(address__icontains=query))
        return queryset.annotate(
            pet_total=Count("pets", filter=Q(pets__is_archived=False), distinct=True),
            available_pet_total=Count(
                "pets",
                filter=Q(pets__status=Pet.Status.AVAILABLE, pets__is_archived=False),
                distinct=True,
            ),
        ).order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["has_linked_shelter"] = True
        if self.request.user.is_authenticated and self.request.user.is_staff and not self.request.user.is_superuser:
            context["has_linked_shelter"] = staff_shelters_for(self.request.user).exists()
        return context


class ShelterDetailView(DetailView):
    model = Shelter

    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return staff_shelters_for(self.request.user)
        return Shelter.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        can_manage_shelter = (
            user.is_authenticated
            and user.is_staff
            and staff_shelters_for(user).filter(pk=self.object.pk).exists()
        )
        posted_pets = list(
            self.object.pets.filter(is_archived=False)
            .select_related("shelter")
            .prefetch_related("personality_tags")
        )
        context.update(
            {
                "available_pet_count": sum(1 for pet in posted_pets if pet.status == Pet.Status.AVAILABLE),
                "can_manage_shelter": can_manage_shelter,
                "posted_pet_count": len(posted_pets),
                "posted_pets": posted_pets,
            }
        )
        return context


class ShelterCreateView(StaffRequiredMixin, CreateView):
    model = Shelter
    form_class = ShelterForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff and not request.user.is_superuser:
            if staff_shelters_for(request.user).exists():
                messages.info(request, "Your shelter profile already exists. You can edit it from here.")
                return redirect("shelter-list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["shelter_setup_mode"] = self.request.user.is_staff and not self.request.user.is_superuser
        return context

    def form_valid(self, form):
        if not self.request.user.is_superuser:
            form.instance.email = self.request.user.email
            existing_shelter = Shelter.objects.filter(name__iexact=form.cleaned_data["name"]).first()
            if existing_shelter:
                update_fields = ["email", "phone", "address", "city", "latitude", "longitude", "description"]
                for field_name in update_fields:
                    setattr(existing_shelter, field_name, getattr(form.instance, field_name))
                if form.cleaned_data.get("photo"):
                    existing_shelter.photo = form.cleaned_data["photo"]
                    update_fields.append("photo")
                existing_shelter.save(update_fields=update_fields)
                self.object = existing_shelter
                messages.success(self.request, "Shelter profile linked.")
                return redirect(self.object)
        messages.success(self.request, "Shelter profile saved.")
        return super().form_valid(form)


class ShelterUpdateView(StaffRequiredMixin, UpdateView):
    model = Shelter
    form_class = ShelterForm

    def get_queryset(self):
        return staff_shelters_for(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        if not self.request.user.is_superuser:
            form.instance.email = self.request.user.email
        messages.success(self.request, "Shelter profile updated.")
        return super().form_valid(form)


class ShelterDeleteView(StaffRequiredMixin, DeleteView):
    model = Shelter
    success_url = reverse_lazy("shelter-list")

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Shelter.objects.all()
        return Shelter.objects.none()


class ApplicationListView(LoginRequiredMixin, ListView):
    model = AdoptionApplication
    template_name = "adoption/application_list.html"
    paginate_by = 10

    def get_base_queryset(self):
        if self.request.user.is_staff:
            return staff_applications_for(self.request.user).select_related("pet", "applicant", "pet__shelter")
        return (
            AdoptionApplication.objects.select_related("pet", "applicant", "pet__shelter")
            .filter(applicant=self.request.user)
        )

    def get_incoming_message_filter(self):
        if self.request.user.is_staff:
            return Q(messages__sender__is_staff=False)
        return Q(messages__sender__is_staff=True)

    def get_annotated_queryset(self):
        unread_filter = self.get_incoming_message_filter() & Q(messages__read_at__isnull=True)
        return (
            self.get_base_queryset()
            .prefetch_related("messages", "messages__sender")
            .annotate(
                message_count=Count("messages", distinct=True),
                unread_count=Count("messages", filter=unread_filter, distinct=True),
                last_message_at=Max("messages__created_at"),
            )
        )

    def get_queryset(self):
        queryset = self.get_annotated_queryset()
        if self.request.user.is_staff:
            pet_id = self.request.GET.get("pet")
            status = self.request.GET.get("status")
            sort = self.request.GET.get("sort") or "newest"
            if pet_id and pet_id.isdigit():
                queryset = queryset.filter(pet_id=pet_id)
            if status in AdoptionApplication.Status.values:
                queryset = queryset.filter(status=status)
            if sort == "oldest":
                return queryset.order_by("created_at", "pk")
            return queryset.order_by("-created_at", "-pk")
        return queryset.order_by("-created_at", "-pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application_scope = self.get_annotated_queryset()
        status_counts = dict(application_scope.values_list("status").annotate(total=Count("id")))
        active_statuses = [
            AdoptionApplication.Status.SUBMITTED,
            AdoptionApplication.Status.REVIEWING,
            AdoptionApplication.Status.APPROVED,
        ]
        message_count = 0
        if not self.request.user.is_staff:
            message_scope = ConversationMessage.objects.filter(
                application__in=application_scope,
                sender__is_staff=True,
            )
            message_count = message_scope.count()
        context["application_summary"] = {
            "total": application_scope.count(),
            "active": application_scope.filter(status__in=active_statuses).count(),
            "messages": message_count,
            "approved": status_counts.get(AdoptionApplication.Status.APPROVED, 0),
            "completed": status_counts.get(AdoptionApplication.Status.COMPLETED, 0),
        }
        context["queue_result_count"] = context["paginator"].count if context.get("paginator") else len(context["object_list"])
        if self.request.user.is_staff:
            selected_pet = self.request.GET.get("pet", "")
            context["queue_filters"] = {
                "pet": selected_pet if selected_pet.isdigit() else "",
                "status": self.request.GET.get("status", ""),
                "sort": self.request.GET.get("sort") or "newest",
            }
            context["queue_pet_choices"] = (
                staff_pets_for(self.request.user)
                .filter(applications__isnull=False)
                .distinct()
                .order_by("name")
            )
            context["status_choices"] = AdoptionApplication.Status.choices
        return context


class MessageListView(LoginRequiredMixin, ListView):
    model = AdoptionApplication
    template_name = "adoption/message_list.html"
    paginate_by = 12
    context_object_name = "threads"

    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and request.user.is_staff
            and not request.user.is_superuser
            and not staff_shelters_for(request.user).exists()
        ):
            messages.info(request, "Create or link your shelter profile before opening messages.")
            return redirect("shelter-create")
        return super().dispatch(request, *args, **kwargs)

    def get_base_queryset(self):
        if self.request.user.is_staff:
            return staff_applications_for(self.request.user).select_related("pet", "applicant", "pet__shelter")
        return AdoptionApplication.objects.select_related("pet", "applicant", "pet__shelter").filter(
            applicant=self.request.user
        )

    def get_incoming_message_filter(self):
        if self.request.user.is_staff:
            return Q(messages__sender__is_staff=False)
        return Q(messages__sender__is_staff=True)

    def get_annotated_queryset(self):
        unread_filter = self.get_incoming_message_filter() & Q(messages__read_at__isnull=True)
        return (
            self.get_base_queryset()
            .prefetch_related(
                Prefetch(
                    "messages",
                    queryset=ConversationMessage.objects.select_related("sender").order_by("-created_at"),
                    to_attr="latest_messages",
                )
            )
            .annotate(
                message_count=Count("messages", distinct=True),
                unread_count=Count("messages", filter=unread_filter, distinct=True),
                last_message_at=Max("messages__created_at"),
            )
        )

    def get_queryset(self):
        queryset = self.get_annotated_queryset()
        if self.request.GET.get("filter") == "unread":
            queryset = queryset.filter(unread_count__gt=0)
        return queryset.order_by("-unread_count", "-last_message_at", "-updated_at", "-created_at")

    def get_selected_thread(self):
        thread_id = self.request.POST.get("thread") or self.request.GET.get("thread")
        if not thread_id or not thread_id.isdigit():
            return None
        return self.get_base_queryset().filter(pk=thread_id).first()

    def post(self, request, *args, **kwargs):
        selected_thread = self.get_selected_thread()
        if selected_thread is None:
            messages.error(request, "Choose a conversation before sending a message.")
            return redirect("message-list")

        self.selected_thread = selected_thread
        self.message_form = MessageForm(request.POST)
        if self.message_form.is_valid():
            message = self.message_form.save(commit=False)
            message.application = selected_thread
            message.sender = request.user
            message.save()
            return redirect(f"{reverse('message-list')}?thread={selected_thread.pk}#message-inbox")

        self.object_list = self.get_queryset()
        context = self.get_context_data(object_list=self.object_list)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application_scope = self.get_base_queryset()
        annotated_scope = self.get_annotated_queryset()
        active_statuses = [
            AdoptionApplication.Status.SUBMITTED,
            AdoptionApplication.Status.REVIEWING,
            AdoptionApplication.Status.APPROVED,
        ]
        context["message_filter"] = "unread" if self.request.GET.get("filter") == "unread" else "all"
        context["message_summary"] = {
            "conversations": application_scope.count(),
            "unread": annotated_scope.filter(unread_count__gt=0).count(),
            "messages": ConversationMessage.objects.filter(application__in=application_scope).count(),
            "active": application_scope.filter(status__in=active_statuses).count(),
        }
        selected_thread = getattr(self, "selected_thread", None) or self.get_selected_thread()
        context["selected_thread"] = selected_thread
        context["message_form"] = getattr(self, "message_form", MessageForm())
        context["selected_conversation"] = ConversationMessage.objects.none()
        if selected_thread is not None:
            conversation = ConversationMessage.objects.filter(application=selected_thread).select_related("sender")
            if self.request.user.is_staff:
                conversation.filter(sender__is_staff=False, read_at__isnull=True).update(read_at=timezone.now())
            else:
                conversation.filter(sender__is_staff=True, read_at__isnull=True).update(read_at=timezone.now())
            context["selected_conversation"] = conversation
        return context


class ApplicationUpdateView(LoginRequiredMixin, UpdateView):
    model = AdoptionApplication
    form_class = ApplicationStatusForm

    def get_queryset(self):
        if self.request.user.is_staff:
            return staff_applications_for(self.request.user)
        return AdoptionApplication.objects.none()


class ApplicationDeleteView(LoginRequiredMixin, DeleteView):
    model = AdoptionApplication
    success_url = reverse_lazy("application-list")

    def get_queryset(self):
        if self.request.user.is_staff:
            return staff_applications_for(self.request.user)
        return AdoptionApplication.objects.filter(applicant=self.request.user)


class TagListView(StaffRequiredMixin, ListView):
    model = PersonalityTag


class TagCreateView(StaffRequiredMixin, CreateView):
    model = PersonalityTag
    form_class = PersonalityTagForm
    success_url = reverse_lazy("tag-list")


class TagUpdateView(StaffRequiredMixin, UpdateView):
    model = PersonalityTag
    form_class = PersonalityTagForm
    success_url = reverse_lazy("tag-list")


class TagDeleteView(StaffRequiredMixin, DeleteView):
    model = PersonalityTag
    success_url = reverse_lazy("tag-list")


class UserListView(SuperuserRequiredMixin, ListView):
    model = User
    template_name = "adoption/user_list.html"


class UserUpdateView(SuperuserRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "adoption/user_form.html"
    success_url = reverse_lazy("user-list")


class UserDeleteView(SuperuserRequiredMixin, DeleteView):
    model = User
    template_name = "adoption/user_confirm_delete.html"
    success_url = reverse_lazy("user-list")


def register(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            if user.is_staff:
                messages.success(request, "Welcome. Create or link your shelter profile before posting pets.")
                return redirect("shelter-create")
            else:
                AdopterProfile.objects.get_or_create(user=user)
                messages.success(request, "Welcome. Tell us a little about your adoption preferences.")
                return redirect("adopter-onboarding")
    else:
        form = UserRegisterForm()
    return render(
        request,
        "registration/register.html",
        {
            "form": form,
            "google_login_configured": is_google_login_configured(request),
        },
    )


def adopter_onboarding(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.path}")
    if request.user.is_staff:
        messages.info(request, "Shelter staff accounts do not need adopter onboarding.")
        return redirect("pet-list")

    profile, _ = AdopterProfile.objects.get_or_create(user=request.user)
    if request.method == "GET" and profile.is_complete and not request.GET.get("next"):
        return redirect("adopter-profile")

    next_url = get_safe_redirect_url(request)
    if request.method == "POST":
        form = AdopterProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your adopter profile has been saved.")
            if next_url:
                return redirect(next_url)
            return redirect("available-pets")
    else:
        form = AdopterProfileForm(instance=profile)

    return render(request, "adoption/adopter_onboarding.html", {"form": form, "next_url": next_url})


def adopter_profile(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.path}")
    if request.user.is_staff:
        messages.info(request, "Shelter staff accounts do not use adopter profiles.")
        return redirect("pet-list")

    profile, _ = AdopterProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = AdopterProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your adopter profile has been updated.")
            return redirect("adopter-profile")
    else:
        form = AdopterProfileForm(instance=profile)

    return render(
        request,
        "adoption/adopter_profile.html",
        {"form": form},
    )


def get_safe_redirect_url(request):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if not next_url:
        return ""
    if next_url == reverse("adopter-onboarding"):
        return ""
    if url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return ""


def adopter_profile_initial(user):
    try:
        profile = user.adopter_profile
    except AdopterProfile.DoesNotExist:
        return {}
    initial = {}
    if profile.home_type:
        initial["home_type"] = profile.home_type
    if profile.experience:
        initial["experience"] = profile.experience
    return initial


def apply_to_adopt(request, pk):
    pet = get_object_or_404(Pet, pk=pk, is_archived=False)
    if not request.user.is_authenticated:
        messages.info(request, "Please log in before applying to adopt.")
        return redirect(f"{reverse('login')}?next={request.path}")
    if request.user.is_staff:
        messages.error(request, "Shelter staff accounts cannot apply to adopt pets.")
        return redirect("pet-list")
    existing_application = AdoptionApplication.objects.filter(pet=pet, applicant=request.user).first()
    if pet.posted_by == request.user:
        messages.error(request, "You cannot apply to adopt your own listed pet.")
        return redirect(pet)
    if existing_application:
        messages.info(request, "You already have an application for this pet.")
        return redirect(existing_application)
    if request.method == "POST":
        form = AdoptionApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.pet = pet
            application.applicant = request.user
            application.save()
            if pet.status == Pet.Status.AVAILABLE:
                pet.status = Pet.Status.PENDING
                pet.save(update_fields=["status", "updated_at"])
            messages.success(request, "Application submitted.")
            return redirect(application)
    else:
        form = AdoptionApplicationForm(initial=adopter_profile_initial(request.user))
    return render(request, "adoption/application_form.html", {"form": form, "pet": pet})


def toggle_favorite_pet(request, pk):
    pet = get_object_or_404(Pet, pk=pk, is_archived=False)
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={pet.get_absolute_url()}")
    if request.user.is_staff:
        messages.error(request, "Shelter staff accounts cannot save favorite pets.")
        return redirect("pet-list")
    if request.method != "POST":
        return redirect(pet)

    favorite, created = FavoritePet.objects.get_or_create(user=request.user, pet=pet)
    if request.POST.get("action") == "remove" or not created:
        favorite.delete()
        messages.success(request, f"{pet.name} was removed from your saved pets.")
    else:
        messages.success(request, f"{pet.name} was saved to your dashboard.")

    return redirect(get_safe_redirect_url(request) or pet.get_absolute_url())


def application_detail(request, pk):
    application = get_object_or_404(
        AdoptionApplication.objects.select_related("pet", "applicant", "pet__shelter"),
        pk=pk,
    )
    if request.user.is_staff:
        has_access = staff_applications_for(request.user).filter(pk=application.pk).exists()
    else:
        has_access = application.applicant == request.user
    if not has_access:
        messages.error(request, "You do not have access to that application.")
        return redirect("application-list")

    status_form = ApplicationStatusForm(instance=application)
    message_form = MessageForm()
    opened_from_messages = (request.GET.get("from") or request.POST.get("from")) == "messages"
    redirect_url = f"{reverse('message-list')}?thread={application.pk}" if opened_from_messages else application
    if request.method == "POST":
        if "status" in request.POST and request.user.is_staff:
            status_form = ApplicationStatusForm(request.POST, instance=application)
            if status_form.is_valid():
                status_form.save()
                messages.success(request, "Application status updated.")
                return redirect(redirect_url)
        else:
            message_form = MessageForm(request.POST)
            if message_form.is_valid():
                message = message_form.save(commit=False)
                message.application = application
                message.sender = request.user
                message.save()
                return redirect(redirect_url)

    conversation = ConversationMessage.objects.filter(application=application).select_related("sender")
    if not request.user.is_staff:
        conversation.filter(sender__is_staff=True, read_at__isnull=True).update(read_at=timezone.now())
    under_review_statuses = {
        AdoptionApplication.Status.REVIEWING,
        AdoptionApplication.Status.APPROVED,
        AdoptionApplication.Status.DECLINED,
        AdoptionApplication.Status.COMPLETED,
    }
    decision_statuses = {
        AdoptionApplication.Status.APPROVED,
        AdoptionApplication.Status.DECLINED,
        AdoptionApplication.Status.COMPLETED,
    }
    decision_text = "Waiting for decision"
    if application.status == AdoptionApplication.Status.DECLINED:
        decision_text = "Declined"
    elif application.status in {AdoptionApplication.Status.APPROVED, AdoptionApplication.Status.COMPLETED}:
        decision_text = "Approved"

    return render(
        request,
        "adoption/application_detail.html",
        {
            "application": application,
            "status_form": status_form,
            "message_form": message_form,
            "conversation": conversation,
            "under_review_active": application.status in under_review_statuses,
            "decision_active": application.status in decision_statuses,
            "decision_text": decision_text,
            "application_back_url": reverse("message-list") if opened_from_messages else reverse("application-list"),
            "application_back_label": "Back to Messages" if opened_from_messages else "Back to Applications",
            "application_back_source": "messages" if opened_from_messages else "",
        },
    )


def nearby_shelters(request):
    if request.user.is_authenticated and request.user.is_staff:
        messages.info(request, "Shelter staff accounts manage shelter details from the Shelters page.")
        return redirect("shelter-list")
    latitude = request.GET.get("lat")
    longitude = request.GET.get("lng")
    try:
        radius = float(request.GET.get("radius") or 25)
    except (TypeError, ValueError):
        radius = 25.0
    shelters = Shelter.objects.prefetch_related("pets").exclude(latitude__isnull=True).exclude(longitude__isnull=True)
    results = []
    if latitude and longitude:
        try:
            latf = float(latitude)
            lngf = float(longitude)
        except (TypeError, ValueError):
            messages.error(request, "Invalid coordinates provided. Please enter numeric latitude and longitude.")
            return render(
                request,
                "adoption/nearby_shelters.html",
                {"results": [], "latitude": latitude, "longitude": longitude, "radius": radius},
            )

        for shelter in shelters:
            try:
                distance = shelter.distance_to(latf, lngf)
            except Exception:
                distance = None
            if distance is not None and distance <= radius:
                available_count = shelter.pets.filter(status=Pet.Status.AVAILABLE).count()
                results.append({"shelter": shelter, "distance": distance, "available_count": available_count})
        results.sort(key=lambda item: item["distance"])
    return render(
        request,
        "adoption/nearby_shelters.html",
        {"results": results, "latitude": latitude, "longitude": longitude, "radius": radius},
    )
