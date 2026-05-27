import math

from django.conf import settings
from django.db import models
from django.urls import reverse


class Shelter(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=80)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to="shelters/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("shelter-detail", kwargs={"pk": self.pk})

    @property
    def profile_missing_fields(self):
        missing_fields = []
        checks = [
            ("Shelter name", self.name),
            ("Address", self.address),
            ("City", self.city),
            ("Email", self.email),
            ("Phone", self.phone),
            ("Description", self.description),
            ("Photo/logo", self.photo),
        ]
        for label, value in checks:
            if not value:
                missing_fields.append(label)
        return missing_fields

    @property
    def is_complete(self):
        return not self.profile_missing_fields

    def distance_to(self, latitude, longitude):
        if self.latitude is None or self.longitude is None:
            return None
        earth_radius_km = 6371
        lat1 = math.radians(float(latitude))
        lon1 = math.radians(float(longitude))
        lat2 = math.radians(float(self.latitude))
        lon2 = math.radians(float(self.longitude))
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class PersonalityTag(models.Model):
    name = models.CharField(max_length=40, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Pet(models.Model):
    class Species(models.TextChoices):
        DOG = "dog", "Dog"
        CAT = "cat", "Cat"
        BIRD = "bird", "Bird"
        RABBIT = "rabbit", "Rabbit"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        PENDING = "pending", "Pending"
        ADOPTED = "adopted", "Adopted"

    name = models.CharField(max_length=100)
    species = models.CharField(max_length=20, choices=Species.choices)
    breed = models.CharField(max_length=100, blank=True)
    age = models.PositiveIntegerField(help_text="Age in years")
    description = models.TextField()
    photo = models.ImageField(upload_to="pets/", blank=True, null=True)
    shelter = models.ForeignKey(Shelter, on_delete=models.CASCADE, related_name="pets")
    personality_tags = models.ManyToManyField(PersonalityTag, blank=True, related_name="pets")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("pet-detail", kwargs={"pk": self.pk})


class AdopterProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="adopter_profile")
    city = models.CharField(max_length=80, blank=True)
    preferred_species = models.CharField(max_length=20, choices=Pet.Species.choices, blank=True)
    home_type = models.CharField(max_length=80, blank=True)
    experience = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_complete(self):
        return all([self.city, self.preferred_species, self.home_type, self.experience])

    def __str__(self):
        return f"{self.user} adopter profile"


class FavoritePet(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorite_pets")
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("user", "pet")

    def __str__(self):
        return f"{self.user} saved {self.pet}"


class AdoptionApplication(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEWING = "reviewing", "Under Review"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"
        COMPLETED = "completed", "Completed"

    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications")
    home_type = models.CharField(max_length=80)
    has_yard = models.BooleanField(default=False)
    experience = models.TextField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("pet", "applicant")

    def __str__(self):
        return f"{self.applicant} applying for {self.pet}"

    def get_absolute_url(self):
        return reverse("application-detail", kwargs={"pk": self.pk})


class ConversationMessage(models.Model):
    application = models.ForeignKey(AdoptionApplication, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message from {self.sender} on {self.created_at:%Y-%m-%d}"
