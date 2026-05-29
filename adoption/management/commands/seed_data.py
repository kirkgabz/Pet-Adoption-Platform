import random
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker

from adoption.models import (
    AdopterProfile,
    AdoptionApplication,
    ConversationMessage,
    FavoritePet,
    PersonalityTag,
    Pet,
    Shelter,
)


User = get_user_model()
SEED_PASSWORD = "password123"


TAG_NAMES = [
    "Playful",
    "Calm",
    "Energetic",
    "Friendly",
    "Shy",
    "Loyal",
    "Curious",
    "Affectionate",
    "Good with kids",
    "Apartment friendly",
    "Special care",
    "Senior pet",
]


SHELTERS = [
    {
        "slug": "paws",
        "staff_username": "staff_paws",
        "name": "Philippine Animal Welfare Society (PAWS)",
        "email": "info@paws.org.ph",
        "phone": "+63 2 8373 9876",
        "address": "Aurora Boulevard, Quezon City",
        "city": "Quezon City",
        "latitude": 14.6534,
        "longitude": 121.0509,
        "description": "Metro Manila shelter focused on rescue, rehabilitation, and responsible adoption.",
    },
    {
        "slug": "caws",
        "staff_username": "staff_caws",
        "name": "Cebu Animal Welfare Society (CAWS)",
        "email": "info@caws.ph",
        "phone": "+63 32 123 4567",
        "address": "Banilad, Cebu City",
        "city": "Cebu City",
        "latitude": 10.3157,
        "longitude": 123.8854,
        "description": "Cebu-based rescue helping cats, dogs, birds, and small pets find stable homes.",
    },
    {
        "slug": "daws",
        "staff_username": "staff_daws",
        "name": "Davao Animal Welfare Society (DAWS)",
        "email": "contact@daws.ph",
        "phone": "+63 82 222 3333",
        "address": "Matina, Davao City",
        "city": "Davao City",
        "latitude": 7.1907,
        "longitude": 125.4553,
        "description": "Davao shelter coordinating adoption interviews and community rescue support.",
    },
    {
        "slug": "iloilo",
        "staff_username": "staff_iloilo",
        "name": "Iloilo Animal Rescue",
        "email": "info@iloiloanimalrescue.ph",
        "phone": "+63 33 321 0000",
        "address": "Jaro, Iloilo City",
        "city": "Iloilo City",
        "latitude": 10.7202,
        "longitude": 122.5621,
        "description": "Local rescue and adoption team for companion animals in Iloilo.",
    },
    {
        "slug": "bacolod",
        "staff_username": "staff_bacolod",
        "name": "Bacolod Animal Welfare",
        "email": "hello@bacolodanimal.ph",
        "phone": "+63 34 700 0000",
        "address": "Mandalagan, Bacolod City",
        "city": "Bacolod City",
        "latitude": 10.6760,
        "longitude": 122.9450,
        "description": "Bacolod shelter handling foster coordination and adoption screening.",
    },
]


ADOPTERS = [
    {
        "username": "adopter_chris",
        "email": "chris@example.com",
        "first_name": "Chris",
        "last_name": "Reyes",
        "city": "Cebu City",
        "preferred_species": Pet.Species.DOG,
        "home_type": "House with yard",
        "experience": "Grew up with two family dogs and can handle daily walks.",
    },
    {
        "username": "adopter_maya",
        "email": "maya@example.com",
        "first_name": "Maya",
        "last_name": "Santos",
        "city": "Quezon City",
        "preferred_species": Pet.Species.CAT,
        "home_type": "Apartment",
        "experience": "Has cared for indoor cats and understands litter training.",
    },
    {
        "username": "adopter_joel",
        "email": "joel@example.com",
        "first_name": "Joel",
        "last_name": "Dela Cruz",
        "city": "Davao City",
        "preferred_species": Pet.Species.BIRD,
        "home_type": "Townhouse",
        "experience": "Keeps a quiet home and has experience with small birds.",
    },
    {
        "username": "adopter_ana",
        "email": "ana@example.com",
        "first_name": "Ana",
        "last_name": "Villanueva",
        "city": "Iloilo City",
        "preferred_species": Pet.Species.RABBIT,
        "home_type": "Condo",
        "experience": "Prepared indoor space for small pets and understands grooming needs.",
    },
    {
        "username": "adopter_luis",
        "email": "luis@example.com",
        "first_name": "Luis",
        "last_name": "Garcia",
        "city": "Bacolod City",
        "preferred_species": Pet.Species.DOG,
        "home_type": "Family home",
        "experience": "Family has adopted before and can support training visits.",
    },
    {
        "username": "adopter_ella",
        "email": "ella@example.com",
        "first_name": "Ella",
        "last_name": "Ramos",
        "city": "Manila",
        "preferred_species": Pet.Species.CAT,
        "home_type": "Apartment",
        "experience": "First-time adopter with a flexible schedule and pet supplies ready.",
    },
]


PETS = [
    {
        "name": "Scott",
        "species": Pet.Species.DOG,
        "breed": "Labrador",
        "age": 3,
        "shelter": "bacolod",
        "status": Pet.Status.AVAILABLE,
        "tags": ["Friendly", "Loyal", "Good with kids"],
        "image_key": "labrador",
    },
    {
        "name": "Eric",
        "species": Pet.Species.BIRD,
        "breed": "Canary",
        "age": 1,
        "shelter": "daws",
        "status": Pet.Status.AVAILABLE,
        "tags": ["Curious", "Apartment friendly"],
        "image_key": "canary",
    },
    {
        "name": "Luna",
        "species": Pet.Species.CAT,
        "breed": "Siamese",
        "age": 2,
        "shelter": "caws",
        "status": Pet.Status.PENDING,
        "tags": ["Calm", "Affectionate", "Apartment friendly"],
        "image_key": "siamese",
    },
    {
        "name": "Milo",
        "species": Pet.Species.DOG,
        "breed": "Golden Retriever",
        "age": 4,
        "shelter": "paws",
        "status": Pet.Status.PENDING,
        "tags": ["Playful", "Good with kids", "Energetic"],
        "image_key": "golden",
    },
    {
        "name": "Nori",
        "species": Pet.Species.CAT,
        "breed": "Maine Coon",
        "age": 3,
        "shelter": "paws",
        "status": Pet.Status.AVAILABLE,
        "tags": ["Calm", "Affectionate"],
        "image_key": "mainecoon",
    },
    {
        "name": "Pip",
        "species": Pet.Species.RABBIT,
        "breed": "Dutch Rabbit",
        "age": 2,
        "shelter": "iloilo",
        "status": Pet.Status.AVAILABLE,
        "tags": ["Curious", "Apartment friendly"],
        "image_key": "dutch",
    },
    {
        "name": "Rio",
        "species": Pet.Species.BIRD,
        "breed": "Lovebird",
        "age": 1,
        "shelter": "caws",
        "status": Pet.Status.AVAILABLE,
        "tags": ["Social", "Curious"],
        "image_key": "lovebird",
    },
    {
        "name": "Bunbun",
        "species": Pet.Species.RABBIT,
        "breed": "Lionhead",
        "age": 4,
        "shelter": "bacolod",
        "status": Pet.Status.PENDING,
        "tags": ["Special care", "Calm"],
        "image_key": "lionhead",
    },
    {
        "name": "Mochi",
        "species": Pet.Species.CAT,
        "breed": "Siamese",
        "age": 1,
        "shelter": "daws",
        "status": Pet.Status.AVAILABLE,
        "tags": ["Playful", "Curious"],
        "image_key": "siamese",
    },
    {
        "name": "Buddy",
        "species": Pet.Species.DOG,
        "breed": "Shih Tzu",
        "age": 6,
        "shelter": "iloilo",
        "status": Pet.Status.ADOPTED,
        "tags": ["Senior pet", "Calm", "Friendly"],
        "image_key": "shih",
    },
    {
        "name": "Cloud",
        "species": Pet.Species.BIRD,
        "breed": "Budgerigar",
        "age": 2,
        "shelter": "paws",
        "status": Pet.Status.AVAILABLE,
        "tags": ["Energetic", "Curious"],
        "image_key": "budgerigar",
    },
    {
        "name": "Maple",
        "species": Pet.Species.RABBIT,
        "breed": "Flemish Giant",
        "age": 5,
        "shelter": "caws",
        "status": Pet.Status.ADOPTED,
        "tags": ["Gentle", "Senior pet"],
        "image_key": "flemish",
    },
    {
        "name": "Archived Test Pet",
        "species": Pet.Species.DOG,
        "breed": "Mixed",
        "age": 7,
        "shelter": "daws",
        "status": Pet.Status.ADOPTED,
        "tags": ["Calm"],
        "image_key": "labrador",
        "is_archived": True,
    },
]


APPLICATIONS = [
    {
        "pet": "Milo",
        "adopter": "adopter_chris",
        "status": AdoptionApplication.Status.SUBMITTED,
        "messages": [
            ("adopter", "Hi, I would like to meet Milo this weekend.", False),
        ],
    },
    {
        "pet": "Luna",
        "adopter": "adopter_maya",
        "status": AdoptionApplication.Status.REVIEWING,
        "messages": [
            ("adopter", "My apartment allows cats and I already bought basic supplies.", True),
            ("staff", "Thanks, Maya. Can you send your preferred visit schedule?", False),
        ],
    },
    {
        "pet": "Eric",
        "adopter": "adopter_joel",
        "status": AdoptionApplication.Status.APPROVED,
        "messages": [
            ("adopter", "I have a quiet room ready for Eric.", True),
            ("staff", "Your application is approved. Please confirm pickup details.", False),
        ],
    },
    {
        "pet": "Pip",
        "adopter": "adopter_ana",
        "status": AdoptionApplication.Status.SUBMITTED,
        "messages": [
            ("adopter", "I can provide indoor space and supervised exercise.", False),
        ],
    },
    {
        "pet": "Scott",
        "adopter": "adopter_luis",
        "status": AdoptionApplication.Status.DECLINED,
        "messages": [
            ("staff", "Thanks for applying. Scott needs a quieter home right now.", True),
        ],
    },
    {
        "pet": "Buddy",
        "adopter": "adopter_ella",
        "status": AdoptionApplication.Status.COMPLETED,
        "messages": [
            ("staff", "Buddy's adoption has been completed. Thank you for adopting.", True),
        ],
    },
]


def set_password_and_save(user):
    user.set_password(SEED_PASSWORD)
    user.save()
    return user


def find_image(root: Path, species: str, image_key: str | None = None) -> Path | None:
    if not root.exists():
        return None
    species_key = str(species).lower()
    wanted = (image_key or "").lower().replace(" ", "")
    candidates = []
    for image in sorted(root.iterdir()):
        if not image.is_file() or image.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        stem = image.stem.lower().replace(" ", "")
        if species_key in stem:
            candidates.append(image)
            if wanted and wanted in stem:
                return image
    return candidates[0] if candidates else None


def attach_image(instance, field_name: str, image_path: Path | None, filename: str):
    if not image_path or getattr(instance, field_name):
        return
    with image_path.open("rb") as image_file:
        getattr(instance, field_name).save(filename, File(image_file), save=True)


class Command(BaseCommand):
    help = "Seeds local development data for adopter and shelter staff workflows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear pets, shelters, applications, messages, favorites, tags, and seeded users before seeding.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed used for generated descriptions.",
        )

    def handle(self, *args, **options):
        fake = Faker()
        Faker.seed(options["seed"])
        random.seed(options["seed"])

        if options["reset"]:
            self.reset_seed_data()

        base = Path(settings.BASE_DIR)
        pet_image_root = base / "static" / "img" / "pet images"
        shelter_logo = base / "static" / "img" / "pet-adoption-logo-transparent.png"

        tags = self.create_tags()
        admin = self.create_admin()
        shelters, staff_users = self.create_shelters_and_staff(shelter_logo)
        adopters = self.create_adopters()
        pets = self.create_pets(fake, shelters, staff_users, tags, pet_image_root)
        self.create_applications(pets, adopters)
        self.create_favorites(pets, adopters)

        self.print_summary(admin, staff_users, adopters)

    def reset_seed_data(self):
        seeded_usernames = [
            "admin",
            *[shelter["staff_username"] for shelter in SHELTERS],
            *[adopter["username"] for adopter in ADOPTERS],
        ]
        ConversationMessage.objects.all().delete()
        FavoritePet.objects.all().delete()
        AdoptionApplication.objects.all().delete()
        Pet.objects.all().delete()
        PersonalityTag.objects.all().delete()
        Shelter.objects.all().delete()
        User.objects.filter(username__in=seeded_usernames).delete()
        self.stdout.write(self.style.WARNING("Cleared existing seeded development data."))

    def create_admin(self):
        admin, _ = User.objects.update_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "first_name": "Admin",
                "last_name": "User",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        return set_password_and_save(admin)

    def create_tags(self):
        tags = {}
        for name in sorted(set(TAG_NAMES + [tag for pet in PETS for tag in pet["tags"]])):
            tag, _ = PersonalityTag.objects.update_or_create(name=name)
            tags[name] = tag
        return tags

    def create_shelters_and_staff(self, shelter_logo: Path):
        shelters = {}
        staff_users = {}
        for shelter_data in SHELTERS:
            staff_user, _ = User.objects.update_or_create(
                username=shelter_data["staff_username"],
                defaults={
                    "email": shelter_data["email"],
                    "first_name": shelter_data["name"].split()[0],
                    "last_name": "Staff",
                    "is_staff": True,
                    "is_superuser": False,
                },
            )
            staff_users[shelter_data["slug"]] = set_password_and_save(staff_user)

            shelter, _ = Shelter.objects.update_or_create(
                email=shelter_data["email"],
                defaults={
                    "name": shelter_data["name"],
                    "phone": shelter_data["phone"],
                    "address": shelter_data["address"],
                    "city": shelter_data["city"],
                    "latitude": shelter_data["latitude"],
                    "longitude": shelter_data["longitude"],
                    "description": shelter_data["description"],
                },
            )
            attach_image(shelter, "photo", shelter_logo if shelter_logo.exists() else None, f"{shelter_data['slug']}_logo.png")
            shelters[shelter_data["slug"]] = shelter
        return shelters, staff_users

    def create_adopters(self):
        adopters = {}
        for adopter_data in ADOPTERS:
            user, _ = User.objects.update_or_create(
                username=adopter_data["username"],
                defaults={
                    "email": adopter_data["email"],
                    "first_name": adopter_data["first_name"],
                    "last_name": adopter_data["last_name"],
                    "is_staff": False,
                    "is_superuser": False,
                },
            )
            user = set_password_and_save(user)
            AdopterProfile.objects.update_or_create(
                user=user,
                defaults={
                    "city": adopter_data["city"],
                    "preferred_species": adopter_data["preferred_species"],
                    "home_type": adopter_data["home_type"],
                    "experience": adopter_data["experience"],
                },
            )
            adopters[adopter_data["username"]] = user
        return adopters

    def create_pets(self, fake, shelters, staff_users, tags, pet_image_root: Path):
        pets = {}
        for pet_data in PETS:
            shelter = shelters[pet_data["shelter"]]
            archived = pet_data.get("is_archived", False)
            pet, _ = Pet.objects.update_or_create(
                name=pet_data["name"],
                shelter=shelter,
                defaults={
                    "species": pet_data["species"],
                    "breed": pet_data["breed"],
                    "age": pet_data["age"],
                    "description": (
                        f"{pet_data['name']} is a {pet_data['age']}-year-old {pet_data['breed']} "
                        f"with a {fake.word()} personality. This profile is seeded for testing "
                        "browse, application, favorite, and staff management workflows."
                    ),
                    "status": pet_data["status"],
                    "posted_by": staff_users[pet_data["shelter"]],
                    "is_archived": archived,
                    "archived_at": timezone.now() if archived else None,
                },
            )
            image = find_image(pet_image_root, pet_data["species"], pet_data.get("image_key"))
            attach_image(pet, "photo", image, f"{pet_data['name'].lower()}_{pet_data['species']}{image.suffix if image else '.jpg'}")
            pet.personality_tags.set(tags[tag_name] for tag_name in pet_data["tags"])
            pets[pet_data["name"]] = pet
        return pets

    def create_applications(self, pets, adopters):
        for app_data in APPLICATIONS:
            pet = pets[app_data["pet"]]
            adopter = adopters[app_data["adopter"]]
            profile = adopter.adopter_profile
            application, _ = AdoptionApplication.objects.update_or_create(
                pet=pet,
                applicant=adopter,
                defaults={
                    "home_type": profile.home_type,
                    "has_yard": "yard" in profile.home_type.lower() or "home" in profile.home_type.lower(),
                    "experience": profile.experience,
                    "reason": f"I want to adopt {pet.name} because I can provide a stable home and daily care.",
                    "status": app_data["status"],
                },
            )
            ConversationMessage.objects.filter(application=application).delete()
            for sender_type, body, read in app_data["messages"]:
                sender = adopter if sender_type == "adopter" else pet.posted_by
                ConversationMessage.objects.create(
                    application=application,
                    sender=sender,
                    body=body,
                    read_at=timezone.now() if read else None,
                )

    def create_favorites(self, pets, adopters):
        favorite_pairs = [
            ("adopter_chris", "Scott"),
            ("adopter_chris", "Pip"),
            ("adopter_maya", "Nori"),
            ("adopter_maya", "Mochi"),
            ("adopter_ana", "Pip"),
            ("adopter_luis", "Milo"),
        ]
        for username, pet_name in favorite_pairs:
            FavoritePet.objects.get_or_create(user=adopters[username], pet=pets[pet_name])

    def print_summary(self, admin, staff_users, adopters):
        self.stdout.write(self.style.SUCCESS("Development data is ready."))
        self.stdout.write("")
        self.stdout.write("Login accounts:")
        self.stdout.write(f"  admin: {admin.username} / {SEED_PASSWORD}")
        self.stdout.write(f"  staff: {next(iter(staff_users.values())).username} / {SEED_PASSWORD}")
        self.stdout.write(f"  adopter: {next(iter(adopters.values())).username} / {SEED_PASSWORD}")
        self.stdout.write("")
        self.stdout.write("More staff accounts:")
        for staff_user in staff_users.values():
            self.stdout.write(f"  {staff_user.username} / {SEED_PASSWORD}")
        self.stdout.write("")
        self.stdout.write("Run again anytime:")
        self.stdout.write("  python manage.py seed_data")
        self.stdout.write("Clean reseed:")
        self.stdout.write("  python manage.py seed_data --reset")
