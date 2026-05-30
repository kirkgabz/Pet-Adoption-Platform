import re
from types import SimpleNamespace
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AdopterProfile, AdoptionApplication, ConversationMessage, FavoritePet, Pet, PersonalityTag, Shelter


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
        self.assertContains(
            response,
            f'class="sidebar-card sidebar-card-link" href="{reverse("shelter-create")}" aria-label="Set up your shelter profile"',
        )
        self.assertContains(response, "Set up shelter profile")

    def test_staff_without_shelter_is_redirected_before_posting_pet(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("pet-create"))

        self.assertRedirects(response, reverse("shelter-create"))

    def test_staff_without_shelter_cannot_post_pet_after_skipping_setup(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("pet-create"),
            {
                "name": "Skipped Setup Pup",
                "species": Pet.Species.DOG,
                "breed": "Mixed",
                "age": 2,
                "description": "Should not be posted yet.",
            },
            follow=True,
        )

        self.assertFalse(Pet.objects.filter(name="Skipped Setup Pup").exists())
        self.assertContains(response, "landing-auth-overlay show landing-auth-required")
        self.assertContains(response, 'data-auth-start-view="shelter"')
        self.assertContains(response, "Create shelter profile")
        self.assertContains(response, "Skip for now")

    def test_staff_without_shelter_is_redirected_from_dashboard_to_setup(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("pet-list"))

        self.assertRedirects(response, reverse("shelter-create"))

    def test_staff_without_shelter_is_redirected_before_managing_pets(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("staff-pet-list"))

        self.assertRedirects(response, reverse("shelter-create"))

    def test_staff_without_shelter_is_redirected_before_opening_messages(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("message-list"))

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

    def test_staff_signup_redirects_to_shelter_setup(self):
        response = self.client.post(
            reverse("register"),
            {
                "account_type": "staff",
                "username": "newstaff",
                "email": "newstaff@example.com",
                "first_name": "New",
                "last_name": "Staff",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        user = User.objects.get(username="newstaff")
        self.assertTrue(user.is_staff)
        self.assertFalse(Shelter.objects.filter(email=user.email).exists())
        self.assertRedirects(response, reverse("shelter-create"))

    def test_shelter_setup_form_uses_landing_required_step_tab(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("shelter-create"))

        self.assertContains(response, '<body class="landing-layout">')
        self.assertContains(response, "landing-auth-overlay show")
        self.assertContains(response, 'data-auth-start-view="shelter"')
        self.assertContains(response, "Required Step")
        self.assertContains(response, "Create shelter profile")
        self.assertContains(response, "Skip for now")
        self.assertNotContains(response, 'action="/accounts/logout/"')
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, "Photo/logo")
        self.assertContains(response, 'name="photo"')
        self.assertNotContains(response, 'class="side-nav"')

    def test_staff_can_link_existing_shelter_profile_by_name(self):
        shelter = Shelter.objects.create(
            name="Happy Tails Shelter",
            email="old@example.com",
            phone="555-0000",
            address="Old Rescue Lane",
            city="Old City",
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("shelter-create"),
            {
                "name": shelter.name,
                "phone": "555-0199",
                "address": "123 Rescue Lane",
                "city": "Cebu",
                "latitude": "",
                "longitude": "",
                "description": "Linked shelter profile.",
            },
        )

        self.assertEqual(Shelter.objects.count(), 1)
        shelter.refresh_from_db()
        self.assertEqual(shelter.email, self.staff.email)
        self.assertEqual(shelter.phone, "555-0199")
        self.assertEqual(shelter.description, "Linked shelter profile.")
        self.assertRedirects(response, shelter.get_absolute_url())

    def test_staff_dashboard_reminds_when_shelter_profile_is_incomplete(self):
        Shelter.objects.create(
            name="Happy Tails Shelter",
            email=self.staff.email,
            phone="",
            address="123 Rescue Lane",
            city="Cebu",
        )
        self.client.force_login(self.staff)

        response = self.client.get(reverse("pet-list"))

        self.assertContains(response, "Complete your shelter profile")
        self.assertContains(response, "Phone")
        self.assertContains(response, "Description")
        self.assertContains(response, "Photo/logo")

    def test_staff_can_edit_linked_shelter_profile(self):
        shelter = Shelter.objects.create(
            name="Happy Tails Shelter",
            email=self.staff.email,
            phone="555-0100",
            address="123 Rescue Lane",
            city="Cebu",
            description="Original rescue info.",
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("shelter-update", args=[shelter.pk]),
            {
                "name": "Happy Tails Shelter",
                "email": "changed@example.com",
                "phone": "555-0199",
                "address": "456 Adoption Avenue",
                "city": "Mandaue",
                "latitude": "",
                "longitude": "",
                "description": "Updated rescue info for adopters.",
            },
        )

        shelter.refresh_from_db()
        self.assertEqual(shelter.email, self.staff.email)
        self.assertEqual(shelter.phone, "555-0199")
        self.assertEqual(shelter.address, "456 Adoption Avenue")
        self.assertEqual(shelter.city, "Mandaue")
        self.assertEqual(shelter.description, "Updated rescue info for adopters.")
        self.assertRedirects(response, shelter.get_absolute_url())

        detail_response = self.client.get(shelter.get_absolute_url())
        self.assertContains(detail_response, "Edit Shelter")
        self.assertContains(detail_response, "Updated rescue info for adopters.")


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
        AdopterProfile.objects.create(
            user=self.adopter,
            city="Cebu City",
            preferred_species=Pet.Species.DOG,
            home_type="House",
            experience="Family pets before.",
        )

    def test_public_auth_pages_render(self):
        for url_name in ["home", "login", "register"]:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)

    def test_adopter_sidebar_does_not_show_care_tips(self):
        self.client.force_login(self.adopter)

        response = self.client.get(reverse("pet-list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'href="{reverse("care-tips")}"')
        self.assertNotContains(response, "Care Tips")

    @override_settings(SOCIALACCOUNT_PROVIDERS={"google": {"APPS": [{"client_id": "test-id", "secret": "test-secret", "key": ""}]}})
    def test_landing_browse_tab_is_closable_and_has_no_guest_card(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "Features")
        self.assertContains(response, "How It Works")
        self.assertContains(response, "Adopt with clarity")
        self.assertContains(response, "data-open-browse-tab")
        self.assertContains(response, "data-close-browse-tab")
        self.assertContains(response, "data-open-auth-tab")
        self.assertContains(response, "data-close-auth-tab")
        self.assertContains(response, f'action="{reverse("home")}"')
        self.assertContains(response, 'name="landing_auth_action" value="login"')
        self.assertContains(response, 'name="landing_auth_action" value="register"')
        self.assertContains(response, f'action="{reverse("google_login")}"')
        self.assertContains(response, "Continue with Google Account")
        self.assertContains(response, "data-google-login-role-input")
        self.assertContains(response, "data-google-register-role-input")
        self.assertNotContains(response, f'href="{self.pet.get_absolute_url()}"')
        self.assertNotContains(response, "data-open-landing-pet")
        self.assertNotContains(response, "data-pet-panel")
        self.assertNotContains(response, "landing-pet-card-action")
        self.assertNotContains(response, "View details")
        self.assertNotContains(response, "Open Full Browse Page")
        self.assertContains(response, "Create a profile to save applications and message shelters.")
        self.assertContains(response, "Create Account")
        self.assertContains(response, "Login to Browse All Pets")
        self.assertNotContains(response, "Login to Apply")
        content = response.content.decode()
        for action_block in re.findall(r'<div class="landing-(?:browse|pet-detail)-actions">.*?</div>', content, flags=re.S):
            self.assertNotIn("Create Account", action_block)
            self.assertNotIn(reverse("register"), action_block)
        self.assertNotContains(response, "Guest User")
        self.assertNotContains(response, "Visitor")

    @override_settings(SOCIALACCOUNT_PROVIDERS={"google": {}})
    def test_landing_hides_google_login_when_not_configured(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'action="{reverse("google_login")}"')
        self.assertNotContains(response, "Continue with Google Account")

    @override_settings(SOCIALACCOUNT_PROVIDERS={"google": {}})
    def test_google_login_start_stores_selected_role(self):
        response = self.client.get(f'{reverse("google_login")}?role=staff')

        self.assertRedirects(response, reverse("login"))
        self.assertEqual(self.client.session["google_account_role"], "staff")

    def test_google_social_adapter_applies_selected_staff_role(self):
        from .adapters import PetAdoptionSocialAccountAdapter

        user = User.objects.create_user(username="googlestaff", email="googlestaff@example.com")
        request = SimpleNamespace(session={"google_account_role": "staff"})

        PetAdoptionSocialAccountAdapter().apply_google_role(request, user)

        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertFalse(AdopterProfile.objects.filter(user=user).exists())

    def test_google_social_adapter_defaults_to_adopter_profile(self):
        from .adapters import PetAdoptionSocialAccountAdapter

        user = User.objects.create_user(username="googleadopter", email="googleadopter@example.com")
        request = SimpleNamespace(session={"google_account_role": "user"})

        PetAdoptionSocialAccountAdapter().apply_google_role(request, user)

        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertTrue(AdopterProfile.objects.filter(user=user).exists())

    def test_landing_login_errors_stay_in_auth_tab(self):
        response = self.client.post(
            reverse("home"),
            {
                "landing_auth_action": "login",
                "login_role": "staff",
                "username": "wrong",
                "password": "bad-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pet Adoption Platform")
        self.assertContains(response, 'data-auth-start-view="login"')
        self.assertContains(response, 'data-auth-start-role="staff"')
        self.assertContains(response, "Please enter a correct username and password")
        self.assertContains(response, "landing-auth-overlay show")

    def test_landing_register_errors_stay_in_auth_tab(self):
        response = self.client.post(
            reverse("home"),
            {
                "landing_auth_action": "register",
                "account_type": "adopter",
                "username": "new-user",
                "email": "new@example.com",
                "first_name": "New",
                "last_name": "User",
                "password1": "password123",
                "password2": "different123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pet Adoption Platform")
        self.assertContains(response, 'data-auth-start-view="register"')
        self.assertContains(response, "The two password fields")
        self.assertContains(response, "landing-auth-overlay show")

    def test_landing_adopter_signup_opens_required_profile_tab(self):
        response = self.client.post(
            reverse("home"),
            {
                "landing_auth_action": "register",
                "account_type": "adopter",
                "username": "landingadopter",
                "email": "landingadopter@example.com",
                "first_name": "Landing",
                "last_name": "Adopter",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        user = User.objects.get(username="landingadopter")
        self.assertFalse(user.is_staff)
        self.assertTrue(AdopterProfile.objects.filter(user=user).exists())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "landing-auth-overlay show landing-auth-required")
        self.assertContains(response, 'data-auth-start-view="adopter"')
        self.assertContains(response, "Complete your adopter profile")

    def test_landing_staff_signup_opens_required_shelter_tab(self):
        response = self.client.post(
            reverse("home"),
            {
                "landing_auth_action": "register",
                "account_type": "staff",
                "username": "landingstaff",
                "email": "landingstaff@example.com",
                "first_name": "Landing",
                "last_name": "Staff",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        user = User.objects.get(username="landingstaff")
        self.assertTrue(user.is_staff)
        self.assertFalse(Shelter.objects.filter(email=user.email).exists())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "landing-auth-overlay show landing-auth-required")
        self.assertContains(response, 'data-auth-start-view="shelter"')
        self.assertContains(response, "Create shelter profile")

    def test_landing_incomplete_adopter_login_opens_required_profile_tab(self):
        user = User.objects.create_user(
            username="landingfresh",
            email="landingfresh@example.com",
            password="StrongPass123!",
        )

        response = self.client.post(
            reverse("home"),
            {
                "landing_auth_action": "login",
                "login_role": "user",
                "username": user.username,
                "password": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "landing-auth-overlay show landing-auth-required")
        self.assertContains(response, 'data-auth-start-view="adopter"')
        self.assertContains(response, "Complete your adopter profile")

    def test_incomplete_logged_in_accounts_do_not_auto_open_required_tab_on_home(self):
        incomplete_adopter = User.objects.create_user(
            username="homeadopter",
            email="homeadopter@example.com",
            password="password",
        )
        self.client.force_login(incomplete_adopter)

        adopter_response = self.client.get(reverse("home"))

        self.assertEqual(adopter_response.status_code, 200)
        self.assertContains(adopter_response, "Pet Adoption Platform")
        self.assertNotContains(adopter_response, "landing-auth-overlay show")
        self.assertNotContains(adopter_response, 'data-auth-start-view="adopter"')

        self.client.logout()
        staff_without_shelter = User.objects.create_user(
            username="homestaff",
            email="homestaff@example.com",
            password="password",
            is_staff=True,
        )
        self.client.force_login(staff_without_shelter)

        staff_response = self.client.get(reverse("home"))

        self.assertEqual(staff_response.status_code, 200)
        self.assertContains(staff_response, "Pet Adoption Platform")
        self.assertNotContains(staff_response, "landing-auth-overlay show")
        self.assertNotContains(staff_response, 'data-auth-start-view="shelter"')

    def test_public_can_view_pet_details_before_login(self):
        detail_response = self.client.get(self.pet.get_absolute_url())

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Apply to Adopt")
        self.assertContains(detail_response, "Contact Shelter")
        self.assertContains(detail_response, "View Shelter")
        self.assertContains(detail_response, f'href="mailto:{self.shelter.email}"')

    def test_public_can_view_shelter_profile_contact_and_posted_pets(self):
        archived_pet = Pet.objects.create(
            name="Hidden Pup",
            species=Pet.Species.DOG,
            breed="Mixed",
            age=4,
            description="Archived listing.",
            shelter=self.shelter,
            posted_by=self.staff,
            is_archived=True,
        )

        response = self.client.get(self.shelter.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.shelter.name)
        self.assertContains(response, "Contact Information")
        self.assertContains(response, "Posted Pets")
        self.assertContains(response, self.shelter.address)
        self.assertContains(response, self.shelter.city)
        self.assertContains(response, f'href="mailto:{self.shelter.email}"')
        self.assertContains(response, f'href="tel:{self.shelter.phone}"')
        self.assertContains(response, self.pet.name)
        self.assertContains(response, self.new_pet.name)
        self.assertNotContains(response, archived_pet.name)
        self.assertNotContains(response, "Edit Shelter")

    def test_standalone_browse_pets_url_is_removed(self):
        response = self.client.get("/browse-pets/")

        self.assertEqual(response.status_code, 404)

    def test_old_available_pets_url_still_works(self):
        response = self.client.get(reverse("available-pets"))

        self.assertEqual(response.status_code, 200)

    def test_available_pets_filters_use_clear_labels(self):
        response = self.client.get(
            reverse("available-pets"),
            {
                "species": Pet.Species.DOG,
                "location": "Cebu",
                "tag": str(self.tag.pk),
                "shelter": str(self.shelter.pk),
                "age": "2-3",
            },
        )

        self.assertContains(response, "Species")
        self.assertContains(response, "Location")
        self.assertContains(response, "Personality")
        self.assertContains(response, "Shelter")
        self.assertContains(response, "Age")
        self.assertContains(response, "City, barangay, or shelter")
        self.assertContains(response, "All shelters")
        self.assertContains(response, "Any age")
        self.assertContains(response, "Near me")
        self.assertContains(response, "Use your current location or type an area.")
        self.assertContains(response, 'data-location-api-ready="true"')
        self.assertContains(response, "petAdoptionLocationProvider")
        self.assertContains(response, 'name="location_source"')
        self.assertContains(response, "Apply Filters")
        self.assertContains(response, "Clear")
        self.assertNotContains(response, "Search pets, breeds, notes")
        filter_form = re.search(
            r'<form class="filters dashboard-filters pet-filter-bar".*?</form>',
            response.content.decode(),
            flags=re.S,
        ).group(0)
        self.assertNotIn('name="q"', filter_form)
        self.assertNotIn("Show me the pawfect", filter_form)
        self.assertNotIn("Located near", filter_form)
        self.assertNotIn("City, barangay, shelter, or address", filter_form)

    def test_available_pets_filters_by_shelter_and_age(self):
        other_shelter = Shelter.objects.create(
            name="Other Rescue",
            email="other@example.com",
            phone="555-0400",
            address="Other Street",
            city="Manila",
        )
        Pet.objects.create(
            name="Senior Dog",
            species=Pet.Species.DOG,
            breed="Mixed",
            age=9,
            description="Older and calm.",
            shelter=self.shelter,
            posted_by=self.staff,
        )
        Pet.objects.create(
            name="Other Shelter Pup",
            species=Pet.Species.DOG,
            breed="Mixed",
            age=2,
            description="Listed elsewhere.",
            shelter=other_shelter,
            posted_by=self.staff,
        )

        response = self.client.get(
            reverse("available-pets"),
            {"species": Pet.Species.DOG, "shelter": str(self.shelter.pk), "age": "2-3"},
        )

        self.assertContains(response, "Milo")
        self.assertNotContains(response, "Senior Dog")
        self.assertNotContains(response, "Other Shelter Pup")

    def test_available_pet_cards_show_required_summary_fields(self):
        response = self.client.get(reverse("available-pets"))

        self.assertContains(response, "Milo")
        self.assertContains(response, "Dog")
        self.assertContains(response, self.shelter.name)
        self.assertContains(response, self.shelter.city)
        self.assertContains(response, self.tag.name)
        self.assertContains(response, "Available")

    def test_available_pets_near_me_filters_by_shelter_distance(self):
        near_shelter = Shelter.objects.create(
            name="Near Shelter",
            email="near@example.com",
            phone="555-0200",
            address="Near Street",
            city="Manila",
            latitude="14.599500",
            longitude="120.984200",
        )
        far_shelter = Shelter.objects.create(
            name="Far Shelter",
            email="far@example.com",
            phone="555-0300",
            address="Far Street",
            city="Cebu",
            latitude="10.315700",
            longitude="123.885400",
        )
        Pet.objects.create(
            name="Nearby Match",
            species=Pet.Species.CAT,
            breed="Domestic",
            age=3,
            description="Close to the adopter.",
            shelter=near_shelter,
            posted_by=self.staff,
        )
        Pet.objects.create(
            name="Far Match",
            species=Pet.Species.CAT,
            breed="Domestic",
            age=4,
            description="Outside the radius.",
            shelter=far_shelter,
            posted_by=self.staff,
        )

        response = self.client.get(
            reverse("available-pets"),
            {"lat": "14.5995", "lng": "120.9842", "radius": "5"},
        )

        self.assertContains(response, "Nearby Match")
        self.assertNotContains(response, "Far Match")
        self.assertContains(response, "Showing pets within 5 km of you.")
        self.assertContains(response, "km away")

    def test_available_pets_near_me_accepts_api_coordinate_names(self):
        near_shelter = Shelter.objects.create(
            name="API Near Shelter",
            email="api-near@example.com",
            phone="555-0500",
            address="Near API Street",
            city="Manila",
            latitude="14.599500",
            longitude="120.984200",
        )
        far_shelter = Shelter.objects.create(
            name="API Far Shelter",
            email="api-far@example.com",
            phone="555-0600",
            address="Far API Street",
            city="Cebu",
            latitude="10.315700",
            longitude="123.885400",
        )
        Pet.objects.create(
            name="API Nearby Match",
            species=Pet.Species.DOG,
            breed="Mixed",
            age=2,
            description="Close from an API-style coordinate payload.",
            shelter=near_shelter,
            posted_by=self.staff,
        )
        Pet.objects.create(
            name="API Far Match",
            species=Pet.Species.DOG,
            breed="Mixed",
            age=2,
            description="Too far from the API-style coordinate payload.",
            shelter=far_shelter,
            posted_by=self.staff,
        )

        response = self.client.get(
            reverse("available-pets"),
            {
                "latitude": "14.5995",
                "longitude": "120.9842",
                "location_source": "test-api",
                "location_label": "Manila",
            },
        )

        self.assertContains(response, "API Nearby Match")
        self.assertNotContains(response, "API Far Match")
        self.assertContains(response, "Showing pets within 25 km of Manila.")
        self.assertContains(response, 'name="lat" value="14.5995"')
        self.assertContains(response, 'name="lng" value="120.9842"')

    def test_adopter_sidebar_shows_browse_pets_link(self):
        self.client.force_login(self.adopter)

        response = self.client.get(reverse("pet-list"))

        self.assertContains(response, f'href="{reverse("available-pets")}"')
        self.assertContains(response, "Browse Pets")
        self.assertContains(response, f'href="{reverse("message-list")}"')
        self.assertContains(response, "Messages")
        self.assertContains(response, f'class="sidebar-card sidebar-card-link" href="{reverse("adopter-profile")}"')
        self.assertContains(response, "Adopter")
        self.assertNotContains(response, "Adopter Profile")
        sidebar_nav = re.search(r'<nav class="side-nav">.*?</nav>', response.content.decode(), flags=re.S).group(0)
        self.assertNotIn(reverse("shelter-list"), sidebar_nav)
        self.assertNotIn("Shelters", sidebar_nav)
        self.assertNotIn(reverse("nearby-shelters"), sidebar_nav)
        self.assertNotIn("Nearby Shelters", sidebar_nav)

    def test_staff_sidebar_does_not_show_adopter_browse_link(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("pet-list"))

        self.assertNotContains(response, f'href="{reverse("available-pets")}"')
        self.assertContains(response, f'href="{reverse("staff-pet-list")}"')
        self.assertContains(response, "Manage Pets")
        self.assertContains(response, f'href="{reverse("message-list")}"')
        self.assertContains(response, "Messages")
        sidebar_nav = re.search(r'<nav class="side-nav">.*?</nav>', response.content.decode(), flags=re.S).group(0)
        self.assertNotIn(reverse("shelter-list"), sidebar_nav)
        self.assertNotIn("Shelters", sidebar_nav)

    def test_staff_sidebar_profile_card_links_to_shelter_profile(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("pet-list"))

        self.assertContains(
            response,
            f'class="sidebar-card sidebar-card-link" href="{self.shelter.get_absolute_url()}" aria-label="Open {self.shelter.name} shelter profile"',
        )
        self.assertContains(response, self.shelter.name)

    def test_staff_dashboard_prioritizes_work_queues(self):
        pending_pet = Pet.objects.create(
            name="Pending Pup",
            species=Pet.Species.DOG,
            breed="Mixed",
            age=4,
            description="Waiting on final adoption steps.",
            shelter=self.shelter,
            posted_by=self.staff,
            status=Pet.Status.PENDING,
        )
        message = ConversationMessage.objects.create(
            application=self.application,
            sender=self.adopter,
            body="Can we schedule a shelter visit?",
        )
        self.client.force_login(self.staff)

        response = self.client.get(reverse("pet-list"))
        content = response.content.decode()

        self.assertContains(response, 'class="staff-work-overview"')
        self.assertContains(response, "New Applications")
        self.assertContains(response, "Pets Currently Available")
        self.assertContains(response, "Pets Pending Adoption")
        self.assertContains(response, "Unread Messages")
        self.assertContains(response, "Shelter Profile Completeness")
        self.assertContains(response, self.application.pet.name)
        self.assertContains(response, self.new_pet.name)
        self.assertContains(response, pending_pet.name)
        self.assertContains(response, "<strong>1</strong> application", html=False)
        self.assertContains(response, "Updated")
        self.assertContains(response, 'name="status" value="available"')
        self.assertContains(response, 'name="status" value="pending"')
        self.assertContains(response, 'name="status" value="adopted"')
        self.assertContains(response, 'name="action" value="archive"')
        self.assertContains(response, "Can we schedule a shelter visit?")
        self.assertNotContains(response, "Shelter listing")
        self.assertLess(content.index("New Applications"), content.index("Pets Currently Available"))
        self.assertLess(content.index("Pets Currently Available"), content.index("Pets Pending Adoption"))
        self.assertLess(content.index("Pets Pending Adoption"), content.index("Unread Messages"))
        self.assertLess(content.index("Unread Messages"), content.index("Shelter Profile Completeness"))

        self.client.get(f'{reverse("message-list")}?thread={self.application.pk}')
        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)

    def test_staff_can_archive_pet_and_status_update_restores_it(self):
        self.client.force_login(self.staff)

        archive_response = self.client.post(
            reverse("pet-state", args=[self.new_pet.pk]),
            {"action": "archive", "next": reverse("pet-list")},
        )

        self.assertRedirects(archive_response, reverse("pet-list"))
        self.new_pet.refresh_from_db()
        self.assertTrue(self.new_pet.is_archived)
        self.assertIsNotNone(self.new_pet.archived_at)

        self.client.logout()
        public_response = self.client.get(reverse("available-pets"))
        self.assertNotContains(public_response, self.new_pet.name)

        self.client.force_login(self.staff)
        status_response = self.client.post(
            reverse("pet-state", args=[self.new_pet.pk]),
            {"status": Pet.Status.ADOPTED, "next": self.new_pet.get_absolute_url()},
        )

        self.assertRedirects(status_response, self.new_pet.get_absolute_url())
        self.new_pet.refresh_from_db()
        self.assertFalse(self.new_pet.is_archived)
        self.assertIsNone(self.new_pet.archived_at)
        self.assertEqual(self.new_pet.status, Pet.Status.ADOPTED)

    def test_staff_manage_pets_page_has_pet_workflow_controls(self):
        ConversationMessage.objects.create(
            application=self.application,
            sender=self.adopter,
            body="Can we meet Milo?",
        )
        self.client.force_login(self.staff)

        response = self.client.get(reverse("staff-pet-list"))

        self.assertContains(response, "Manage Pets")
        self.assertContains(response, f'href="{reverse("pet-create")}"')
        self.assertContains(response, self.pet.name)
        self.assertContains(response, self.new_pet.name)
        self.assertContains(response, f'href="{reverse("pet-update", args=[self.pet.pk])}"')
        self.assertContains(response, "<strong>1</strong> application", html=False)
        self.assertContains(response, "Updated")
        self.assertContains(response, 'name="status" value="available"')
        self.assertContains(response, 'name="status" value="pending"')
        self.assertContains(response, 'name="status" value="adopted"')
        self.assertContains(response, 'name="action" value="archive"')

        filtered_response = self.client.get(f'{reverse("staff-pet-list")}?status=available')
        self.assertContains(filtered_response, self.new_pet.name)

    def test_adopter_dashboard_quick_actions_are_removed(self):
        self.client.force_login(self.adopter)

        response = self.client.get(reverse("pet-list"))

        self.assertNotContains(response, 'class="quick-actions dashboard-actions"')
        self.assertNotContains(response, "Track Status")
        self.assertNotContains(response, "Nearby Shelters")
        self.assertNotContains(response, "Meet Shelters")

    def test_adopter_dashboard_shows_applications_saved_messages_and_recommendations(self):
        FavoritePet.objects.create(user=self.adopter, pet=self.new_pet)
        ConversationMessage.objects.create(
            application=self.application,
            sender=self.staff,
            body="Please visit the shelter this weekend.",
        )
        recommended_pet = Pet.objects.create(
            name="Buddy",
            species=Pet.Species.DOG,
            breed="Retriever",
            age=3,
            description="Friendly and active.",
            shelter=self.shelter,
            posted_by=self.staff,
        )
        self.client.force_login(self.adopter)

        response = self.client.get(reverse("pet-list"))

        self.assertContains(response, "Active Applications")
        self.assertContains(response, self.application.pet.name)
        self.assertContains(response, "Saved Pets")
        self.assertContains(response, self.new_pet.name)
        self.assertContains(response, "Recent Shelter Messages")
        self.assertContains(response, "Please visit the shelter this weekend.")
        self.assertContains(response, "Recommended Pets")
        self.assertContains(response, recommended_pet.name)

    def test_adopter_can_save_and_remove_favorite_pet(self):
        self.client.force_login(self.adopter)

        save_response = self.client.post(
            reverse("pet-favorite", args=[self.new_pet.pk]),
            {"next": reverse("pet-list")},
        )

        self.assertRedirects(save_response, reverse("pet-list"))
        self.assertTrue(FavoritePet.objects.filter(user=self.adopter, pet=self.new_pet).exists())

        remove_response = self.client.post(
            reverse("pet-favorite", args=[self.new_pet.pk]),
            {"next": reverse("pet-list"), "action": "remove"},
        )

        self.assertRedirects(remove_response, reverse("pet-list"))
        self.assertFalse(FavoritePet.objects.filter(user=self.adopter, pet=self.new_pet).exists())

    def test_public_apply_redirects_to_user_login(self):
        response = self.client.get(reverse("application-create", args=[self.pet.pk]))

        expected = f"{reverse('login')}?next={reverse('application-create', args=[self.pet.pk])}"
        self.assertRedirects(response, expected)

    def test_incomplete_adopter_cannot_apply_after_skipping_profile(self):
        user = User.objects.create_user(
            username="skippedprofile",
            email="skippedprofile@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("application-create", args=[self.new_pet.pk]),
            {
                "home_type": "Apartment",
                "has_yard": "off",
                "experience": "Some experience.",
                "reason": "I can care for this pet.",
            },
            follow=True,
        )

        self.assertFalse(AdoptionApplication.objects.filter(applicant=user, pet=self.new_pet).exists())
        self.assertContains(response, "landing-auth-overlay show landing-auth-required")
        self.assertContains(response, 'data-auth-start-view="adopter"')
        self.assertContains(response, "Complete your adopter profile")
        self.assertContains(response, "Skip for now")

    def test_adopter_signup_redirects_to_onboarding(self):
        response = self.client.post(
            reverse("register"),
            {
                "account_type": "adopter",
                "username": "newadopter",
                "email": "newadopter@example.com",
                "first_name": "New",
                "last_name": "Adopter",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        user = User.objects.get(username="newadopter")
        self.assertFalse(user.is_staff)
        self.assertTrue(AdopterProfile.objects.filter(user=user).exists())
        self.assertRedirects(response, reverse("adopter-onboarding"))

    def test_user_login_redirects_incomplete_adopter_to_onboarding(self):
        user = User.objects.create_user(
            username="freshadopter",
            email="fresh@example.com",
            password="StrongPass123!",
        )

        response = self.client.post(
            f"{reverse('login')}?role=user",
            {
                "username": user.username,
                "password": "StrongPass123!",
                "login_role": "user",
            },
        )

        expected = f"{reverse('adopter-onboarding')}?{urlencode({'next': reverse('pet-list')})}"
        self.assertRedirects(response, expected)

    def test_incomplete_adopter_can_open_dashboard_with_profile_reminder(self):
        user = User.objects.create_user(
            username="incomplete",
            email="incomplete@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("pet-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Complete your adopter profile")
        self.assertContains(response, f"{reverse('adopter-onboarding')}?next={reverse('pet-list')}")

    def test_incomplete_adopter_is_redirected_to_onboarding_for_protected_pages(self):
        user = User.objects.create_user(
            username="incompleteapply",
            email="incompleteapply@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("available-pets"))

        expected = f"{reverse('adopter-onboarding')}?{urlencode({'next': reverse('available-pets')})}"
        self.assertRedirects(response, expected)

    def test_onboarding_page_uses_landing_required_step_tab(self):
        user = User.objects.create_user(
            username="needsprofile",
            email="needsprofile@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("adopter-onboarding"))

        self.assertContains(response, '<body class="landing-layout">')
        self.assertContains(response, "landing-auth-overlay show")
        self.assertContains(response, 'data-auth-start-view="adopter"')
        self.assertContains(response, "Required Step")
        self.assertContains(response, "Complete your adopter profile")
        self.assertContains(response, "Skip for now")
        self.assertNotContains(response, 'action="/accounts/logout/"')
        self.assertNotContains(response, 'class="side-nav"')

    def test_completed_adopter_onboarding_url_redirects_to_profile_editor(self):
        self.client.force_login(self.adopter)

        response = self.client.get(reverse("adopter-onboarding"))

        self.assertRedirects(response, reverse("adopter-profile"))

    def test_adopter_profile_page_updates_existing_profile(self):
        self.client.force_login(self.adopter)

        get_response = self.client.get(reverse("adopter-profile"))
        self.assertEqual(get_response.status_code, 200)
        self.assertContains(get_response, "Your Profile")
        self.assertNotContains(get_response, '<body class="auth-layout">')
        self.assertContains(get_response, 'class="side-nav"')

        response = self.client.post(
            reverse("adopter-profile"),
            {
                "city": "Manila",
                "preferred_species": Pet.Species.RABBIT,
                "home_type": "Condo",
                "experience": "I have cared for rabbits before.",
            },
        )

        self.assertRedirects(response, reverse("adopter-profile"))
        profile = AdopterProfile.objects.get(user=self.adopter)
        self.assertEqual(profile.city, "Manila")
        self.assertEqual(profile.preferred_species, Pet.Species.RABBIT)
        self.assertEqual(profile.home_type, "Condo")
        self.assertEqual(profile.experience, "I have cared for rabbits before.")

    def test_adopter_onboarding_requires_profile_details(self):
        user = User.objects.create_user(
            username="blankprofile",
            email="blankprofile@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("adopter-onboarding"),
            {
                "city": "",
                "preferred_species": "",
                "home_type": "",
                "experience": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertFalse(user.adopter_profile.is_complete)

    def test_adopter_onboarding_saves_profile(self):
        self.client.force_login(self.adopter)

        response = self.client.post(
            reverse("adopter-onboarding"),
            {
                "city": "Cebu City",
                "preferred_species": Pet.Species.CAT,
                "home_type": "Townhouse",
                "experience": "I cared for family pets for five years.",
            },
        )

        profile = AdopterProfile.objects.get(user=self.adopter)
        self.assertEqual(profile.city, "Cebu City")
        self.assertEqual(profile.preferred_species, Pet.Species.CAT)
        self.assertEqual(profile.home_type, "Townhouse")
        self.assertEqual(profile.experience, "I cared for family pets for five years.")
        self.assertRedirects(response, reverse("available-pets"))

    def test_application_form_prefills_from_adopter_profile(self):
        AdopterProfile.objects.update_or_create(
            user=self.adopter,
            defaults={
                "city": "Cebu City",
                "preferred_species": Pet.Species.DOG,
                "home_type": "Townhouse",
                "experience": "I cared for family pets for five years.",
            },
        )
        self.client.force_login(self.adopter)

        response = self.client.get(reverse("application-create", args=[self.new_pet.pk]))

        self.assertContains(response, 'value="Townhouse"')
        self.assertContains(response, "I cared for family pets for five years.")

    def test_application_submit_redirects_to_tracking_page(self):
        self.client.force_login(self.adopter)

        response = self.client.post(
            reverse("application-create", args=[self.new_pet.pk]),
            {
                "home_type": "House",
                "has_yard": "on",
                "experience": "Family pets before.",
                "reason": "Luna fits our quiet home.",
            },
        )

        application = AdoptionApplication.objects.get(pet=self.new_pet, applicant=self.adopter)
        self.assertRedirects(response, application.get_absolute_url())

        tracking_response = self.client.get(application.get_absolute_url())
        self.assertContains(tracking_response, "Application Tracker")
        self.assertContains(tracking_response, "Submitted")
        self.assertContains(tracking_response, "Messages")

    def test_application_tracker_shows_stages_and_shelter_messages(self):
        ConversationMessage.objects.create(
            application=self.application,
            sender=self.staff,
            body="Please visit the shelter this weekend.",
        )
        self.client.force_login(self.adopter)

        response = self.client.get(self.application.get_absolute_url())

        self.assertContains(response, "Submitted")
        self.assertContains(response, "Under Review")
        self.assertContains(response, "Approved / Declined")
        self.assertContains(response, "Completed")
        self.assertNotContains(response, "Shelter Contacted You")
        self.assertNotContains(response, "Message received")
        self.assertContains(response, "Please visit the shelter this weekend.")
        self.assertContains(response, "Shelter Staff")

    def test_application_list_uses_visual_tracker_layout(self):
        ConversationMessage.objects.create(
            application=self.application,
            sender=self.staff,
            body="Please visit the shelter this weekend.",
        )
        self.client.force_login(self.adopter)

        response = self.client.get(reverse("application-list"))

        self.assertContains(response, 'class="application-list-hero"')
        self.assertContains(response, 'class="application-summary-grid"')
        self.assertContains(response, 'class="application-card"')
        self.assertContains(response, "Application Tracker")
        self.assertContains(response, "Shelter Messages")
        self.assertContains(response, "Milo")
        self.assertContains(response, self.shelter.name)
        self.assertContains(response, "Submitted")
        self.assertContains(response, "Review")
        self.assertContains(response, "Decision")
        self.assertContains(response, "Complete")
        self.assertContains(response, "1 message")
        self.assertContains(response, "View Tracker")
        self.assertNotContains(response, "View Status")

    def test_staff_application_queue_has_filters_without_message_buttons(self):
        second_application = AdoptionApplication.objects.create(
            pet=self.new_pet,
            applicant=self.adopter,
            home_type="Townhouse",
            has_yard=False,
            experience="Quiet home with previous cat experience.",
            reason="Luna matches our household.",
            status=AdoptionApplication.Status.APPROVED,
        )
        ConversationMessage.objects.create(
            application=second_application,
            sender=self.adopter,
            body="I can visit tomorrow.",
        )
        self.client.force_login(self.staff)

        response = self.client.get(reverse("application-list"))

        self.assertContains(response, "Application Queue")
        self.assertContains(response, "application-queue-filters")
        self.assertContains(response, 'name="pet"')
        self.assertContains(response, 'name="status"')
        self.assertContains(response, 'name="sort"')
        self.assertContains(response, "Newest first")
        self.assertContains(response, "Oldest first")
        self.assertContains(response, "Manage Pets")
        self.assertNotContains(response, 'name="unread"')
        self.assertNotContains(response, "Unread first")
        self.assertNotContains(response, "1 unread")
        self.assertNotContains(response, "Adopter Messages")
        application_cards = response.content.decode().split('<div class="application-card-list">', 1)[1]
        self.assertNotIn('href="' + reverse("message-list"), application_cards)
        self.assertNotIn(">Messages<", application_cards)

        pet_response = self.client.get(f'{reverse("application-list")}?pet={self.pet.pk}')
        pet_cards = pet_response.content.decode().split('<div class="application-card-list">', 1)[1]
        self.assertIn(self.pet.name, pet_cards)
        self.assertNotIn(self.new_pet.name, pet_cards)

        status_response = self.client.get(f'{reverse("application-list")}?status=approved')
        status_cards = status_response.content.decode().split('<div class="application-card-list">', 1)[1]
        self.assertIn(self.new_pet.name, status_cards)
        self.assertNotIn(self.pet.name, status_cards)

    def test_staff_application_detail_shows_review_sections(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.application.get_absolute_url())

        self.assertContains(response, "Applicant Info")
        self.assertContains(response, "Home Details")
        self.assertContains(response, "Reason for Adoption")
        self.assertContains(response, "Status Controls")
        self.assertContains(response, self.adopter.email)
        self.assertContains(response, "Request More Info")
        self.assertContains(response, "Approve")
        self.assertContains(response, "Decline")
        self.assertContains(response, "Mark Adoption Completed")
        self.assertContains(response, "Set detailed status")
        self.assertContains(response, "staff-application-layout")
        self.assertNotContains(response, f'href="{reverse("message-list")}?thread={self.application.pk}"')
        self.assertNotContains(response, "Messages / Questions")
        self.assertNotContains(response, "Message Thread")

    def test_staff_decision_actions_update_application_and_pet_status(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            self.application.get_absolute_url(),
            {"status": AdoptionApplication.Status.REVIEWING},
        )
        self.assertRedirects(response, self.application.get_absolute_url())
        self.application.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.application.status, AdoptionApplication.Status.REVIEWING)
        self.assertEqual(self.pet.status, Pet.Status.PENDING)

        response = self.client.post(
            self.application.get_absolute_url(),
            {"status": AdoptionApplication.Status.DECLINED},
        )
        self.assertRedirects(response, self.application.get_absolute_url())
        self.application.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.application.status, AdoptionApplication.Status.DECLINED)
        self.assertEqual(self.pet.status, Pet.Status.AVAILABLE)

        response = self.client.post(
            self.application.get_absolute_url(),
            {"status": AdoptionApplication.Status.APPROVED},
        )
        self.assertRedirects(response, self.application.get_absolute_url())
        self.application.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.application.status, AdoptionApplication.Status.APPROVED)
        self.assertEqual(self.pet.status, Pet.Status.PENDING)

        response = self.client.post(
            self.application.get_absolute_url(),
            {"status": AdoptionApplication.Status.COMPLETED},
        )
        self.assertRedirects(response, self.application.get_absolute_url())
        self.application.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.application.status, AdoptionApplication.Status.COMPLETED)
        self.assertEqual(self.pet.status, Pet.Status.ADOPTED)

    def test_adopter_messages_page_links_conversations_to_tracker(self):
        message = ConversationMessage.objects.create(
            application=self.application,
            sender=self.staff,
            body="Please visit the shelter this weekend.",
        )
        self.client.force_login(self.adopter)

        response = self.client.get(reverse("message-list"))

        self.assertContains(response, "Shelter Messages")
        self.assertContains(response, "Conversation Inbox")
        self.assertContains(response, "message-inbox-layout")
        self.assertContains(response, "data-message-inbox")
        self.assertContains(response, "history.pushState")
        self.assertContains(response, "message-thread-sidebar")
        self.assertContains(response, "Select a conversation")
        self.assertContains(response, "1 unread")
        self.assertContains(response, "Please visit the shelter this weekend.")
        self.assertContains(response, '<a class="message-thread-card')
        self.assertContains(response, f'{reverse("message-list")}?thread={self.application.pk}')
        self.assertContains(response, f'{reverse("message-list")}?thread={self.application.pk}#message-inbox')
        self.assertContains(response, "Open Conversation")

        detail_response = self.client.get(f'{reverse("message-list")}?thread={self.application.pk}')
        self.assertContains(detail_response, "selected-thread-summary")
        self.assertContains(detail_response, "Questions with")
        self.assertContains(detail_response, "Please visit the shelter this weekend.")
        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)

    def test_staff_messages_page_prioritizes_adopter_replies(self):
        ConversationMessage.objects.create(
            application=self.application,
            sender=self.adopter,
            body="Can we schedule a shelter visit?",
        )
        self.client.force_login(self.staff)

        response = self.client.get(reverse("message-list"))

        self.assertContains(response, "Adopter Messages")
        self.assertContains(response, "message-inbox-layout")
        self.assertContains(response, "message-thread-sidebar")
        self.assertContains(response, "1 unread")
        self.assertContains(response, "Can we schedule a shelter visit?")
        self.assertContains(response, self.adopter.username)
        self.assertContains(response, '<a class="message-thread-card')
        self.assertContains(response, f'{reverse("message-list")}?thread={self.application.pk}')
        self.assertContains(response, f'{reverse("message-list")}?thread={self.application.pk}#message-inbox')
        self.assertContains(response, "Open Conversation")

        unread_response = self.client.get(f'{reverse("message-list")}?filter=unread')
        self.assertContains(unread_response, self.pet.name)

        thread_response = self.client.get(f'{reverse("message-list")}?thread={self.application.pk}')
        self.assertContains(thread_response, "selected-thread-summary")
        self.assertContains(thread_response, "Questions with")
        self.assertContains(thread_response, "Can we schedule a shelter visit?")

    def test_action_pages_use_consistent_back_link(self):
        self.client.force_login(self.adopter)
        adopter_pages = [
            (self.pet.get_absolute_url(), "Back to Browse Pets"),
            (reverse("application-create", args=[self.new_pet.pk]), "Back to Pet"),
            (self.application.get_absolute_url(), "Back to Applications"),
            (reverse("adopter-profile"), "Back to Dashboard"),
        ]
        for url, label in adopter_pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'class="page-back-link"')
                self.assertContains(response, label)

        self.client.force_login(self.staff)
        staff_pages = [
            (reverse("pet-create"), "Back to Manage Pets"),
            (self.shelter.get_absolute_url(), "Back to Shelters"),
        ]
        for url, label in staff_pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'class="page-back-link"')
                self.assertContains(response, label)

    def test_adopter_pages_render(self):
        self.client.force_login(self.adopter)
        urls = [
            reverse("pet-list"),
            reverse("available-pets"),
            self.pet.get_absolute_url(),
            reverse("application-create", args=[self.new_pet.pk]),
            self.application.get_absolute_url(),
            reverse("application-list"),
            reverse("message-list"),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_staff_pages_render(self):
        self.client.force_login(self.staff)
        urls = [
            reverse("pet-list"),
            reverse("staff-pet-list"),
            reverse("pet-create"),
            self.shelter.get_absolute_url(),
            self.application.get_absolute_url(),
            reverse("application-list"),
            reverse("message-list"),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
