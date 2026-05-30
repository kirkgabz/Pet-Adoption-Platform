import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from adoption.models import Shelter, Pet, PersonalityTag, AdoptionApplication, ConversationMessage

User = get_user_model()

class Command(BaseCommand):
    help = 'Generate realistic seed data for Pet Adoption Platform'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting to seed database...")

        # Create dummy users
        admin_user, _ = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com', 'is_staff': True, 'is_superuser': True})
        if admin_user.password == '':
            admin_user.set_password('adminpassword')
            admin_user.save()
            
        adopter_user, _ = User.objects.get_or_create(username='adopter', defaults={'email': 'adopter@example.com'})
        if adopter_user.password == '':
            adopter_user.set_password('adopterpassword')
            adopter_user.save()
        
        # Create personality tags
        tags = ["Friendly", "Playful", "Calm", "Energetic", "Good with Kids", "Good with Cats", "Good with Dogs", "Shy", "Affectionate", "Independent", "Loyal", "Protective", "Goofy", "Cuddly", "Quiet"]
        tag_objects = []
        for tag in tags:
            obj, _ = PersonalityTag.objects.get_or_create(name=tag)
            tag_objects.append(obj)

        # Create 10 shelters
        shelters_data = [
            {"name": "Palawan Animal Rescue Center", "city": "Puerto Princesa", "address": "123 Rescue Road", "lat": 9.75, "lng": 118.75},
            {"name": "Puerto Princesa Pet Haven", "city": "Puerto Princesa", "address": "45 Haven Avenue", "lat": 9.76, "lng": 118.74},
            {"name": "Happy Paws Shelter", "city": "Puerto Princesa", "address": "78 Paws Street", "lat": 9.73, "lng": 118.76},
            {"name": "El Nido Animal Welfare", "city": "El Nido", "address": "10 Beachfront Road", "lat": 11.18, "lng": 119.38},
            {"name": "Coron Stray Rescue", "city": "Coron", "address": "5 Island Way", "lat": 11.99, "lng": 120.20},
            {"name": "San Vicente Paws", "city": "San Vicente", "address": "90 Long Beach St", "lat": 10.51, "lng": 119.26},
            {"name": "Roxas Pet Care", "city": "Roxas", "address": "12 Highway", "lat": 10.32, "lng": 119.35},
            {"name": "Brooke's Point Animal Sanctuary", "city": "Brooke's Point", "address": "34 Rural Rd", "lat": 8.76, "lng": 117.82},
            {"name": "Bataraza Stray Help", "city": "Bataraza", "address": "56 South Rd", "lat": 8.64, "lng": 117.62},
            {"name": "Taytay Rescue Center", "city": "Taytay", "address": "100 Fort St", "lat": 10.82, "lng": 119.51},
        ]

        shelter_objs = []
        for i, s_data in enumerate(shelters_data):
            shelter, _ = Shelter.objects.get_or_create(
                name=s_data["name"], 
                defaults={
                    "email": f"contact{i}@example.com",
                    "phone": f"+6391234567{i:02d}",
                    "address": s_data["address"],
                    "city": s_data["city"],
                    "barangay": "Centro",
                    "is_verified": random.choice([True, True, False]),
                    "latitude": s_data["lat"],
                    "longitude": s_data["lng"],
                    "description": f"A dedicated shelter in {s_data['city']} helping local animals in need."
                }
            )
            shelter_objs.append(shelter)

        # Create 20 pets
        pet_names = ["Bella", "Max", "Luna", "Charlie", "Lucy", "Cooper", "Daisy", "Milo", "Zoe", "Rocky", "Sadie", "Bear", "Molly", "Tucker", "Stella", "Oliver", "Chloe", "Duke", "Penny", "Leo", "Lola", "Jack", "Lily", "Buster", "Ruby"]
        breeds_dogs = ["Aspin", "Golden Retriever Mix", "Labrador Mix", "Shih Tzu Mix", "Poodle Mix", "German Shepherd Mix"]
        breeds_cats = ["Puspin", "Siamese Mix", "Persian Mix", "Domestic Shorthair", "Calico"]
        colors = ["Black", "White", "Brown", "Golden", "Tricolor", "Tabby", "Calico", "Orange", "Gray"]

        pet_objs = []
        for i in range(20):
            species = random.choice(["dog", "cat"])
            breed = random.choice(breeds_dogs) if species == "dog" else random.choice(breeds_cats)
            gender = random.choice(["male", "female"])
            name = random.choice(pet_names) + f" {i}"
            
            p_data = {
                "name": name,
                "species": species,
                "breed": breed,
                "gender": gender,
                "age": random.randint(1, 10),
                "weight": round(random.uniform(2.0, 25.0), 1),
                "color": random.choice(colors),
                "vaccination_status": random.choice(["Fully Vaccinated", "Partially Vaccinated", "Not Vaccinated"]),
                "adoption_fee": round(random.uniform(0.0, 1500.0), 2),
                "description": f"{name} is a wonderful {breed} looking for a loving home.",
                "medical_history": "Generally healthy. " + random.choice(["Spayed/Neutered.", "Needs spay/neuter.", "Recent checkup completed."]),
                "requirements": random.choice(["Needs a yard.", "Good for apartments.", "Indoor only.", "Active owner needed.", "Quiet home preferred."]),
                "status": random.choice([Pet.Status.AVAILABLE, Pet.Status.AVAILABLE, Pet.Status.AVAILABLE, Pet.Status.PENDING, Pet.Status.ADOPTED]),
                "shelter": random.choice(shelter_objs),
                "posted_by": admin_user
            }
            
            pet, created = Pet.objects.get_or_create(name=p_data["name"], defaults=p_data)
            if created:
                pet.personality_tags.set(random.sample(tag_objects, k=random.randint(2, 4)))
            pet_objs.append(pet)

        # Create Adoption Applications for all non-staff users
        available_pets = [p for p in pet_objs if p.status != Pet.Status.ADOPTED]
        
        non_staff_users = User.objects.filter(is_staff=False)
        if not non_staff_users.exists():
            non_staff_users = [adopter_user]
            
        statuses = [AdoptionApplication.Status.SUBMITTED, AdoptionApplication.Status.REVIEWING, AdoptionApplication.Status.APPROVED, AdoptionApplication.Status.DECLINED, AdoptionApplication.Status.COMPLETED]
        
        apps = []
        # Give each non-staff user 2 applications
        for user in non_staff_users:
            user_pets = random.sample(available_pets, min(2, len(available_pets)))
            for i, pet in enumerate(user_pets):
                status = random.choice(statuses)
                app, created = AdoptionApplication.objects.get_or_create(
                    pet=pet,
                    applicant=user,
                    defaults={
                        "home_type": random.choice(["House", "Apartment", "Condo"]),
                        "has_yard": random.choice([True, False]),
                        "experience": "Have had pets before and know how to care for them.",
                        "reason": "Looking to expand our family and give a pet a loving home.",
                        "status": status
                    }
                )
                apps.append(app)
                app.sync_pet_status()

        # Create Messages across the applications
        message_templates = [
            ("applicant", "Hi, I just submitted my application. Please let me know if you need more info!"),
            ("admin", "Thank you! We have received your application and are reviewing it."),
            ("applicant", "Great, thanks! When can I expect to hear back?"),
            ("admin", "Usually within 2-3 business days. We will keep you updated."),
            ("admin", "Could you provide a bit more detail about your yard? Is it fully fenced?"),
            ("applicant", "Yes, it is fully fenced with a 6-foot wooden fence."),
            ("admin", "Perfect, that's great to hear. We'll be in touch soon."),
            ("admin", "Good news! Your application has been approved. When would you like to schedule a meet and greet?"),
            ("applicant", "That's wonderful! I can come by this Saturday at 10 AM."),
            ("admin", "Saturday at 10 AM works for us. See you then!"),
        ]

        # Distribute messages across applications
        for app in apps:
            num_messages = random.randint(2, 6)
            convo = random.sample(message_templates, num_messages)
            for role, text in convo:
                sender = app.applicant if role == "applicant" else admin_user
                ConversationMessage.objects.create(
                    application=app,
                    sender=sender,
                    body=text
                )

        self.stdout.write(self.style.SUCCESS("Successfully seeded database with 10 Shelters, 20 Pets, and assigned Applications/Messages to your users!"))
