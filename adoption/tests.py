from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import AdoptionApplication, Pet, PersonalityTag, Shelter


class ShelterStaffWorkflowTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="shelterstaff",
            email="staff@example.com",
            password="password",
            is_staff=True,
        )

    def test_staff_without_shelter_is_prompted_to_create_profile(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("shelter-list"))

        self.assertContains(response, "Create Shelter Profile")
        self.assertContains(response, "Complete your shelter profile before posting pets.")

    def test_staff_without_shelter_is_redirected_before_posting_pet(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("pet-create"))

        self.assertRedirects(response, reverse("shelter-create"))

    def test_staff_can_create_one_linked_shelter_profile(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("shelter-create"),
            {
                "name": "Happy Tails Shelter",
                "phone": "555-0100",
                "address": "123 Rescue Lane",
                "city": "Cebu",
                "latitude": "",
                "longitude": "",
                "description": "Local rescue shelter.",
            },
        )

        shelter = Shelter.objects.get()
        self.assertEqual(shelter.email, self.staff.email)
        self.assertRedirects(response, shelter.get_absolute_url())

    def test_staff_with_shelter_cannot_create_another_shelter(self):
        Shelter.objects.create(
            name="Happy Tails Shelter",
            email=self.staff.email,
            phone="555-0100",
            address="123 Rescue Lane",
            city="Cebu",
        )
        self.client.force_login(self.staff)

        response = self.client.get(reverse("shelter-create"))

        self.assertRedirects(response, reverse("shelter-list"))


class FrontendRenderTests(TestCase):
    def setUp(self):
        self.adopter = User.objects.create_user(
            username="adopter",
            email="adopter@example.com",
            password="password",
        )
        self.staff = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password="password",
            is_staff=True,
        )
        self.shelter = Shelter.objects.create(
            name="Happy Tails Shelter",
            email=self.staff.email,
            phone="555-0100",
            address="123 Rescue Lane",
            city="Cebu",
        )
        self.tag = PersonalityTag.objects.create(name="Gentle")
        self.pet = Pet.objects.create(
            name="Milo",
            species=Pet.Species.DOG,
            breed="Mixed",
            age=2,
            description="Friendly and ready for a home.",
            shelter=self.shelter,
            posted_by=self.staff,
        )
        self.pet.personality_tags.add(self.tag)
        self.new_pet = Pet.objects.create(
            name="Luna",
            species=Pet.Species.CAT,
            breed="Domestic Shorthair",
            age=1,
            description="Calm and curious.",
            shelter=self.shelter,
            posted_by=self.staff,
        )
        self.application = AdoptionApplication.objects.create(
            pet=self.pet,
            applicant=self.adopter,
            home_type="House",
            has_yard=True,
            experience="Family pets before.",
            reason="A good fit for our home.",
        )

    def test_public_auth_pages_render(self):
        for url_name in ["home", "login", "register"]:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)

    def test_adopter_pages_render(self):
        self.client.force_login(self.adopter)
        urls = [
            reverse("pet-list"),
            reverse("available-pets"),
            self.pet.get_absolute_url(),
            reverse("application-create", args=[self.new_pet.pk]),
            self.application.get_absolute_url(),
            reverse("application-list"),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_staff_pages_render(self):
        self.client.force_login(self.staff)
        urls = [
            reverse("pet-list"),
            reverse("pet-create"),
            self.shelter.get_absolute_url(),
            self.application.get_absolute_url(),
            reverse("application-list"),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
