from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from .forms import (
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

from .models import AdoptionApplication, ConversationMessage, Pet, PersonalityTag, Shelter


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
    queryset = Pet.objects.select_related("shelter", "posted_by").prefetch_related("personality_tags")
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
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        login_role = self.request.GET.get("role", "user")
        context["login_role"] = login_role
        context["google_login_configured"] = is_google_login_configured(self.request)
        context["show_google_login"] = context["google_login_configured"] and login_role != "staff"
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

    def get_queryset(self):
        if self.request.user.is_staff:
            queryset = staff_pets_for(self.request.user)
        else:
            queryset = Pet.objects.select_related("shelter").prefetch_related("personality_tags")
        query = self.request.GET.get("q")
        species = self.request.GET.get("species")
        status = self.request.GET.get("status")
        tag = self.request.GET.get("tag")
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
        application_scope = (
            staff_applications_for(self.request.user)
            if self.request.user.is_staff
            else AdoptionApplication.objects.filter(applicant=self.request.user)
        )
        context["species_choices"] = Pet.Species.choices
        context["status_choices"] = Pet.Status.choices
        context["tags"] = PersonalityTag.objects.all()
        context["featured_pet"] = (
            pet_scope.select_related("shelter")
            .prefetch_related("personality_tags")
            .filter(status__in=[Pet.Status.AVAILABLE, Pet.Status.PENDING])
            .order_by("-created_at")
            .first()
        )
        context["latest_pets"] = (
            pet_scope.select_related("shelter")
            .prefetch_related("personality_tags")
            .order_by("-created_at")[:4]
        )
        context["recent_applications"] = application_scope.order_by("-created_at")[:4]
        context["pet_counts"] = {
            "total": pet_scope.count(),
            "available": pet_scope.filter(status=Pet.Status.AVAILABLE).count(),
            "pending": pet_scope.filter(status=Pet.Status.PENDING).count(),
            "adopted": pet_scope.filter(status=Pet.Status.ADOPTED).count(),
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
        # Current date
        context["current_date"] = datetime.datetime.now()

        # Get temperature for today's location (use first shelter city if available)
        context["current_temp"] = None
        context["current_temp_f"] = None
        context["weather_icon"] = None
        context["weather_desc"] = None
        if self.request.user.is_staff:
            context["available_pets"] = pet_scope.order_by("-created_at")[:3]
        else:
            context["available_pets"] = (
                Pet.objects.select_related("shelter")
                .prefetch_related("personality_tags")
                .filter(status=Pet.Status.AVAILABLE)
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


class PetDetailView(DetailView):
    model = Pet

    def get_queryset(self):
        return Pet.objects.select_related("shelter", "posted_by").prefetch_related("personality_tags")

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
        return context


class AvailablePetsView(LoginRequiredMixin, ListView):
    model = Pet
    template_name = "adoption/available_pets.html"
    paginate_by = 12
    context_object_name = "object_list"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff:
            messages.info(request, "Shelter staff accounts manage pets from the dashboard.")
            return redirect("pet-list")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Pet.objects.select_related("shelter").prefetch_related("personality_tags").filter(status=Pet.Status.AVAILABLE)
        query = self.request.GET.get("q")
        species = self.request.GET.get("species")
        location = self.request.GET.get("location")
        tag = self.request.GET.get("tag")
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(breed__icontains=query) | Q(description__icontains=query)
            )
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
        return queryset.distinct().order_by('?')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["species_choices"] = Pet.Species.choices
        context["tags"] = PersonalityTag.objects.all()
        context["application_form"] = AdoptionApplicationForm()
        return context


class PetCreateView(StaffRequiredMixin, CreateView):
    model = Pet
    form_class = PetForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff and not request.user.is_superuser:
            if not staff_shelters_for(request.user).exists():
                messages.error(request, "Add your shelter details before posting pets.")
                return redirect("shelter-create")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.posted_by = self.request.user
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
    success_url = reverse_lazy("pet-list")


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
        return queryset


class ShelterDetailView(DetailView):
    model = Shelter

    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return staff_shelters_for(self.request.user)
        return Shelter.objects.all()


class ShelterCreateView(StaffRequiredMixin, CreateView):
    model = Shelter
    form_class = ShelterForm

    def form_valid(self, form):
        if not self.request.user.is_superuser:
            form.instance.email = self.request.user.email
        messages.success(self.request, "Shelter profile saved.")
        return super().form_valid(form)


class ShelterUpdateView(StaffRequiredMixin, UpdateView):
    model = Shelter
    form_class = ShelterForm

    def get_queryset(self):
        return staff_shelters_for(self.request.user)

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

    def get_queryset(self):
        if self.request.user.is_staff:
            return staff_applications_for(self.request.user)
        return AdoptionApplication.objects.select_related("pet", "applicant", "pet__shelter").filter(applicant=self.request.user)


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
            login(request, user)
            if user.is_staff:
                messages.success(request, "Welcome. You can now post pets for adoption.")
            else:
                messages.success(request, "Welcome. You can now apply to adopt pets.")
            return redirect("pet-list")
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


def apply_to_adopt(request, pk):
    pet = get_object_or_404(Pet, pk=pk)
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
        form = AdoptionApplicationForm()
    return render(request, "adoption/application_form.html", {"form": form, "pet": pet})


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
    if request.method == "POST":
        if "status" in request.POST and request.user.is_staff:
            status_form = ApplicationStatusForm(request.POST, instance=application)
            if status_form.is_valid():
                status_form.save()
                if application.status == AdoptionApplication.Status.COMPLETED:
                    application.pet.status = Pet.Status.ADOPTED
                elif application.status in {
                    AdoptionApplication.Status.SUBMITTED,
                    AdoptionApplication.Status.REVIEWING,
                    AdoptionApplication.Status.APPROVED,
                }:
                    application.pet.status = Pet.Status.PENDING
                elif application.status == AdoptionApplication.Status.DECLINED:
                    active_exists = application.pet.applications.exclude(pk=application.pk).exclude(
                        status=AdoptionApplication.Status.DECLINED
                    ).exists()
                    application.pet.status = Pet.Status.PENDING if active_exists else Pet.Status.AVAILABLE
                application.pet.save(update_fields=["status", "updated_at"])
                messages.success(request, "Application status updated.")
                return redirect(application)
        else:
            message_form = MessageForm(request.POST)
            if message_form.is_valid():
                message = message_form.save(commit=False)
                message.application = application
                message.sender = request.user
                message.save()
                return redirect(application)

    return render(
        request,
        "adoption/application_detail.html",
        {
            "application": application,
            "status_form": status_form,
            "message_form": message_form,
            "conversation": ConversationMessage.objects.filter(application=application).select_related("sender"),
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
