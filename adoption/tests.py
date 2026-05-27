import re
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.test import TestCase
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

    def test_staff_without_shelter_is_redirected_before_posting_pet(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("pet-create"))

        self.assertRedirects(response, reverse("shelter-create"))

    def test_staff_without_shelter_is_redirected_from_dashboard_to_setup(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("pet-list"))

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

    def test_shelter_setup_form_includes_photo_logo_upload(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("shelter-create"))

        self.assertContains(response, '<body class="auth-layout">')
        self.assertContains(response, "Required Step")
        self.assertContains(response, "Create shelter profile")
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

    def test_landing_browse_tab_is_closable_and_has_no_guest_card(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "data-open-browse-tab")
        self.assertContains(response, "data-close-browse-tab")
        self.assertNotContains(response, f'href="{self.pet.get_absolute_url()}"')
        self.assertNotContains(response, "data-open-landing-pet")
        self.assertNotContains(response, "data-pet-panel")
        self.assertNotContains(response, "landing-pet-card-action")
        self.assertNotContains(response, "View details")
        self.assertNotContains(response, "Open Full Browse Page")
        self.assertNotContains(response, "Create Account")
        self.assertContains(response, "Login to Browse All Pets")
        self.assertNotContains(response, "Login to Apply")
        content = response.content.decode()
        for action_block in re.findall(r'<div class="landing-(?:browse|pet-detail)-actions">.*?</div>', content, flags=re.S):
            self.assertNotIn("Create Account", action_block)
            self.assertNotIn(reverse("register"), action_block)
        self.assertNotContains(response, "Guest User")
        self.assertNotContains(response, "Visitor")

    def test_public_can_view_pet_details_before_login(self):
        detail_response = self.client.get(self.pet.get_absolute_url())

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Apply to Adopt")
        self.assertContains(detail_response, "Contact Shelter")
        self.assertContains(detail_response, "View Shelter")
        self.assertContains(detail_response, f'href="mailto:{self.shelter.email}"')

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

    def test_adopter_sidebar_shows_browse_pets_link(self):
        self.client.force_login(self.adopter)

        response = self.client.get(reverse("pet-list"))

        self.assertContains(response, f'href="{reverse("available-pets")}"')
        self.assertContains(response, "Browse Pets")
        self.assertContains(response, f'class="sidebar-card sidebar-card-link" href="{reverse("adopter-profile")}"')
        self.assertContains(response, "Adopter")
        self.assertNotContains(response, "Adopter Profile")
        sidebar_nav = re.search(r'<nav class="side-nav">.*?</nav>', response.content.decode(), flags=re.S).group(0)
        self.assertNotIn(reverse("nearby-shelters"), sidebar_nav)
        self.assertNotIn("Nearby Shelters", sidebar_nav)

    def test_staff_sidebar_does_not_show_adopter_browse_link(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("pet-list"))

        self.assertNotContains(response, f'href="{reverse("available-pets")}"')

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

    def test_incomplete_adopter_is_redirected_to_onboarding(self):
        user = User.objects.create_user(
            username="incomplete",
            email="incomplete@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("pet-list"))

        expected = f"{reverse('adopter-onboarding')}?{urlencode({'next': reverse('pet-list')})}"
        self.assertRedirects(response, expected)

    def test_onboarding_page_uses_auth_layout_and_has_no_skip_button(self):
        user = User.objects.create_user(
            username="needsprofile",
            email="needsprofile@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("adopter-onboarding"))

        self.assertContains(response, '<body class="auth-layout">')
        self.assertContains(response, "Required Step")
        self.assertNotContains(response, "Skip for now")
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
        self.assertContains(response, "Shelter Contacted You")
        self.assertContains(response, "Approved / Declined")
        self.assertContains(response, "Completed")
        self.assertContains(response, "Message received")
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
            (reverse("pet-create"), "Back to Dashboard"),
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
