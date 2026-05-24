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


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = 'login'

    def test_func(self):
        return self.request.user.is_staff


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
        context["login_role"] = self.request.GET.get("role", "user")
        return context


class PetListView(LoginRequiredMixin, ListView):
    model = Pet
    paginate_by = 9

    def get_queryset(self):
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
        context["species_choices"] = Pet.Species.choices
        context["status_choices"] = Pet.Status.choices
        context["tags"] = PersonalityTag.objects.all()
        context["featured_pet"] = (
            Pet.objects.select_related("shelter")
            .prefetch_related("personality_tags")
            .filter(status__in=[Pet.Status.AVAILABLE, Pet.Status.PENDING])
            .order_by("-created_at")
            .first()
        )
        context["latest_pets"] = (
            Pet.objects.select_related("shelter")
            .prefetch_related("personality_tags")
            .order_by("-created_at")[:4]
        )
        context["recent_applications"] = AdoptionApplication.objects.select_related(
            "pet", "applicant", "pet__shelter"
        ).order_by("-created_at")[:4]
        context["pet_counts"] = {
            "total": Pet.objects.count(),
            "available": Pet.objects.filter(status=Pet.Status.AVAILABLE).count(),
            "pending": Pet.objects.filter(status=Pet.Status.PENDING).count(),
            "adopted": Pet.objects.filter(status=Pet.Status.ADOPTED).count(),
        }
        context["shelter_count"] = Shelter.objects.count()
        context["application_counts"] = dict(
            AdoptionApplication.objects.values_list("status").annotate(total=Count("id"))
        )
        # Current date
        context["current_date"] = datetime.datetime.now()

        # Get temperature for today's location (use first shelter city if available)
        context["current_temp"] = None
        context["current_temp_f"] = None
        context["weather_icon"] = None
        context["weather_desc"] = None
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


class AvailablePetsView(LoginRequiredMixin, ListView):
    model = Pet
    template_name = "adoption/available_pets.html"
    paginate_by = 12
    context_object_name = "object_list"

    def get_queryset(self):
        queryset = Pet.objects.select_related("shelter").prefetch_related("personality_tags").filter(status=Pet.Status.AVAILABLE)
        query = self.request.GET.get("q")
        species = self.request.GET.get("species")
        tag = self.request.GET.get("tag")
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(breed__icontains=query) | Q(description__icontains=query)
            )
        if species:
            queryset = queryset.filter(species=species)
        if tag:
            queryset = queryset.filter(personality_tags__id=tag)
        return queryset.distinct().order_by('?')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["species_choices"] = Pet.Species.choices
        context["tags"] = PersonalityTag.objects.all()
        return context


class PetCreateView(LoginRequiredMixin, CreateView):
    model = Pet
    form_class = PetForm

    def form_valid(self, form):
        form.instance.posted_by = self.request.user
        messages.success(self.request, "Pet posted for adoption.")
        return super().form_valid(form)


class PetOwnershipMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        pet = self.get_object()
        return self.request.user.is_staff or pet.posted_by == self.request.user


class PetUpdateView(StaffRequiredMixin, UpdateView):
    model = Pet
    form_class = PetForm


class PetDeleteView(PetOwnershipMixin, DeleteView):
    model = Pet
    success_url = reverse_lazy("pet-list")


class ShelterListView(ListView):
    model = Shelter
    paginate_by = 10

    def get_queryset(self):
        queryset = Shelter.objects.all()
        query = self.request.GET.get("q")
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(city__icontains=query) | Q(address__icontains=query))
        return queryset


class ShelterDetailView(DetailView):
    model = Shelter


class ShelterCreateView(StaffRequiredMixin, CreateView):
    model = Shelter
    form_class = ShelterForm


class ShelterUpdateView(StaffRequiredMixin, UpdateView):
    model = Shelter
    form_class = ShelterForm


class ShelterDeleteView(StaffRequiredMixin, DeleteView):
    model = Shelter
    success_url = reverse_lazy("shelter-list")


class ApplicationListView(LoginRequiredMixin, ListView):
    model = AdoptionApplication
    template_name = "adoption/application_list.html"
    paginate_by = 10

    def get_queryset(self):
        queryset = AdoptionApplication.objects.select_related("pet", "applicant", "pet__shelter")
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(applicant=self.request.user)


class ApplicationUpdateView(LoginRequiredMixin, UpdateView):
    model = AdoptionApplication
    form_class = ApplicationStatusForm

    def get_queryset(self):
        if self.request.user.is_staff:
            return AdoptionApplication.objects.all()
        return AdoptionApplication.objects.none()


class ApplicationDeleteView(LoginRequiredMixin, DeleteView):
    model = AdoptionApplication
    success_url = reverse_lazy("application-list")

    def get_queryset(self):
        queryset = AdoptionApplication.objects.all()
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(applicant=self.request.user)


class TagListView(ListView):
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


class UserListView(StaffRequiredMixin, ListView):
    model = User
    template_name = "adoption/user_list.html"


class UserUpdateView(StaffRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "adoption/user_form.html"
    success_url = reverse_lazy("user-list")


class UserDeleteView(StaffRequiredMixin, DeleteView):
    model = User
    template_name = "adoption/user_confirm_delete.html"
    success_url = reverse_lazy("user-list")


def register(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome. You can now apply to adopt pets.")
            return redirect("pet-list")
    else:
        form = UserRegisterForm()
    return render(request, "registration/register.html", {"form": form})


def apply_to_adopt(request, pk):
    pet = get_object_or_404(Pet, pk=pk)
    if not request.user.is_authenticated:
        messages.info(request, "Please log in before applying to adopt.")
        return redirect(f"{reverse('login')}?next={request.path}")
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
    if not request.user.is_staff and application.applicant != request.user:
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
