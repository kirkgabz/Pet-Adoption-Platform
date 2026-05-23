import random
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from faker import Faker

from adoption.models import Shelter, PersonalityTag, Pet, AdoptionApplication, ConversationMessage

User = get_user_model()

# ─────────────────────────────────────────────────────────────────────────────
# FIXED PET DISTRIBUTION — edit counts here if you want more/less of each
# ─────────────────────────────────────────────────────────────────────────────
SPECIES_PLAN = {
    'dog':    3,
    'cat':    3,
    'bird':   3,
    'rabbit': 3,
}

# Realistic breeds per species
BREEDS = {
    'dog':    ['Golden Retriever', 'Labrador', 'Beagle', 'Poodle', 'Shih Tzu'],
    'cat':    ['Persian', 'Siamese', 'Maine Coon', 'Ragdoll', 'Tabby'],
    'bird':   ['Budgerigar', 'Cockatiel', 'Lovebird', 'Canary', 'Parrotlet'],
    'rabbit': ['Holland Lop', 'Mini Rex', 'Dutch Rabbit', 'Lionhead', 'Flemish Giant'],
}


def _pick_image(folder: Path) -> Path | None:
    """Return the first image found in folder, or None if folder is empty."""
    for ext in ('*.jpg', '*.jpeg', '*.png', '*.webp'):
        files = sorted(folder.glob(ext))
        if files:
            return files[0]
    return None


def _get_breed_image(species: str, breed: str, pet_images_dir: Path) -> Path | None:
    """Return image matching the breed name, or None if not found."""
    breed_lower = breed.lower().replace(' ', '')
    for ext in ('jpg', 'jpeg', 'png', 'webp'):
        for f in pet_images_dir.iterdir():
            if f.suffix.lower() == f'.{ext}':
                if breed_lower in f.stem.lower().replace(' ', ''):
                    return f
    return None


class Command(BaseCommand):
    help = (
        'Seeds the database with realistic fake data.\n\n'
        'Drop your own images into:\n'
        '  static/seed_images/shelters/  — 1 image (for all 3 shelters)\n'
        '  static/seed_images/dogs/      — 1 image (used for 3 dogs)\n'
        '  static/seed_images/cats/      — 1 image (used for 3 cats)\n'
        '  static/seed_images/birds/     — 1 image (used for 3 birds)\n'
        '  static/seed_images/rabbits/   — 1 image (used for 3 rabbits)\n'
    )

    def handle(self, *args, **kwargs):
        fake = Faker()
        base = Path(settings.BASE_DIR)

        # Image folder paths
        img_root = base / 'static' / 'seed_images'
        pet_images_dir = base / 'static' / 'img' / 'pet images'
        species_img_dirs = {
            'dog':    img_root / 'dogs',
            'cat':    img_root / 'cats',
            'bird':   img_root / 'birds',
            'rabbit': img_root / 'rabbits',
        }
        shelter_img_dir = img_root / 'shelters'

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== PET & SHELTER SEEDER ==='))
        self.stdout.write(f'Image root: {img_root}\n')

        # ── 1. Users ──────────────────────────────────────────────────────────
        User.objects.all().delete()
        admin = User.objects.create_superuser('admin', 'admin@example.com', 'admin')
        users = [
            User.objects.create_user(fake.user_name(), fake.email(), 'password123')
            for _ in range(5)
        ]
        self.stdout.write(self.style.SUCCESS('✔ Users created (admin + 5 users)'))

        # ── 2. Personality Tags ───────────────────────────────────────────────
        PersonalityTag.objects.all().delete()
        tags_raw = ['Playful', 'Calm', 'Energetic', 'Friendly', 'Shy', 'Loyal', 'Curious', 'Affectionate']
        tag_objects = [PersonalityTag.objects.create(name=t) for t in tags_raw]
        self.stdout.write(self.style.SUCCESS(f'✔ {len(tag_objects)} personality tags created'))

        # ── 3. Shelters (curated Philippine shelters) ─────────────────────────
        Shelter.objects.all().delete()
        shelters = []
        shelter_img = _pick_image(shelter_img_dir)
        if not shelter_img:
            self.stdout.write(self.style.WARNING(
                f'  ⚠ No shelter image found in {shelter_img_dir}. Shelters will have no photo.'
            ))

        PH_SHELTERS = [
            {
                'name': 'Philippine Animal Welfare Society (PAWS)',
                'email': 'info@paws.org.ph',
                'phone': '+63 2 8373 9876',
                'address': 'Quezon City',
                'city': 'Quezon City',
                'latitude': 14.6534,
                'longitude': 121.0509,
                'description': 'PAWS protects and promotes the welfare of animals in the Philippines.'
            },
            {
                'name': 'Cebu Animal Welfare Society (CAWS)',
                'email': 'info@caws.ph',
                'phone': '+63 32 123 4567',
                'address': 'Cebu City',
                'city': 'Cebu City',
                'latitude': 10.3157,
                'longitude': 123.8854,
                'description': 'CAWS provides shelter, rescue, and adoption services in Cebu.'
            },
            {
                'name': 'Davao Animal Welfare Society (DAWS)',
                'email': 'contact@daws.ph',
                'phone': '+63 82 222 3333',
                'address': 'Davao City',
                'city': 'Davao City',
                'latitude': 7.1907,
                'longitude': 125.4553,
                'description': 'DAWS supports animal welfare and sheltering programs in Davao.'
            },
            {
                'name': 'Iloilo Animal Rescue',
                'email': 'info@iloiloanimalrescue.ph',
                'phone': '+63 33 321 0000',
                'address': 'Iloilo City',
                'city': 'Iloilo City',
                'latitude': 10.7202,
                'longitude': 122.5621,
                'description': 'Local rescue and adoption services in Iloilo.'
            },
            {
                'name': 'Bacolod Animal Welfare',
                'email': 'hello@bacolodanimal.ph',
                'phone': '+63 34 700 0000',
                'address': 'Bacolod City',
                'city': 'Bacolod City',
                'latitude': 10.6760,
                'longitude': 122.9450,
                'description': 'Bacolod-based shelter and rescue operations.'
            },
            {
                'name': 'Manila Animal Rescue Center',
                'email': 'info@manilaanimals.ph',
                'phone': '+63 2 7654 3210',
                'address': 'Manila',
                'city': 'Manila',
                'latitude': 14.5995,
                'longitude': 120.9842,
                'description': 'Rescue and shelter services serving the Metro Manila area.'
            },
        ]

        for i, sdata in enumerate(PH_SHELTERS):
            s = Shelter(
                name=sdata['name'],
                email=sdata['email'],
                phone=sdata['phone'],
                address=sdata['address'],
                city=sdata['city'],
                latitude=sdata['latitude'],
                longitude=sdata['longitude'],
                description=sdata['description'],
            )
            if shelter_img:
                with shelter_img.open('rb') as f:
                    s.photo.save(f'shelter_{i}{shelter_img.suffix}', File(f), save=False)
            s.save()
            shelters.append(s)

        self.stdout.write(self.style.SUCCESS(f'✔ {len(shelters)} Philippine shelters created'))

        # ── 4. Pets (fixed per-species count) ────────────────────────────────
        Pet.objects.all().delete()
        pets = []
        pet_counter = 0
        # Build a mapping of images present in `static/img/pet images`
        pet_images_map: dict[str, list[Path]] = {k: [] for k in SPECIES_PLAN}
        if pet_images_dir.exists():
            for f in sorted(pet_images_dir.iterdir()):
                if not f.is_file():
                    continue
                if f.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
                    continue
                # Expect filename format: "<species> <breed>.<ext>" e.g. "cat siamese.jpg"
                parts = f.stem.split()
                if not parts:
                    continue
                sp = parts[0].lower()
                if sp in pet_images_map:
                    pet_images_map[sp].append(f)

        # Track per-species index to cycle through images deterministically
        species_index: dict[str, int] = {k: 0 for k in SPECIES_PLAN}

        for species, count in SPECIES_PLAN.items():
            for j in range(count):
                breed = random.choice(BREEDS[species])
                pet = Pet(
                    name=fake.first_name(),
                    species=species,
                    breed=breed,
                    age=random.randint(1, 10),
                    description=(
                        f'Meet {fake.first_name()}, a wonderful {species} looking for a forever home. '
                        f'{fake.text()}'
                    ),
                    shelter=random.choice(shelters),
                    status=random.choice(['available', 'available', 'available', 'pending']),
                    posted_by=admin,
                )
                
                # Prefer images from `static/img/pet images/<species> <breed>.<ext>`
                species_images = pet_images_map.get(species, [])
                if species_images:
                    idx = species_index[species] % len(species_images)
                    img_path = species_images[idx]
                    species_index[species] += 1
                    with img_path.open('rb') as f:
                        pet.photo.save(
                            f'{species}_{pet_counter}{img_path.suffix}',
                            File(f),
                            save=False,
                        )
                
                pet.save()
                pet.personality_tags.set(random.sample(tag_objects, k=random.randint(1, 3)))
                pets.append(pet)
                pet_counter += 1

            self.stdout.write(self.style.SUCCESS(f'  ✔ {count} {species}(s) created'))

        # Randomize pet order
        random.shuffle(pets)
        
        self.stdout.write(self.style.SUCCESS(f'✔ {len(pets)} pets total (randomized)'))

        # ── 5. Adoption Applications & Messages ───────────────────────────────
        AdoptionApplication.objects.all().delete()
        for i in range(5):
            try:
                app = AdoptionApplication.objects.create(
                    pet=random.choice(pets),
                    applicant=random.choice(users),
                    home_type=random.choice(['House', 'Apartment', 'Condo', 'Townhouse']),
                    has_yard=fake.boolean(),
                    experience=fake.text(),
                    reason=f'I have always wanted a pet and I believe I can give this animal a loving home. {fake.text()}',
                    status='submitted',
                )
                ConversationMessage.objects.create(
                    application=app,
                    sender=app.applicant,
                    body=fake.text(),
                )
            except Exception:
                # Ignore duplicate (pet, applicant) pairs
                pass

        self.stdout.write(self.style.SUCCESS('✔ Applications & messages created'))
        self.stdout.write(self.style.SUCCESS('\n🎉 Database seeded successfully!\n'))

        # ── Summary ───────────────────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('=== IMAGE CHECKLIST ==='))
        self.stdout.write('Drop 1 image (JPG/PNG) in each folder below:')
        self.stdout.write(f'  Shelters : static/seed_images/shelters/')
        for sp in SPECIES_PLAN:
            self.stdout.write(f'  {sp.capitalize():<8}: static/seed_images/{sp}s/')
        self.stdout.write('')
        self.stdout.write('Then re-run:  python manage.py seed_data\n')


