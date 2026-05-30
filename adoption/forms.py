from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import AdopterProfile, AdoptionApplication, ConversationMessage, Pet, PersonalityTag, Shelter


class BootstrapFormMixin:
    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "checkbox")
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                widget.attrs.setdefault("class", "choice-list")
            else:
                widget.attrs.setdefault("class", "field")


class UserRegisterForm(BootstrapFormMixin, UserCreationForm):
    ADOPTER = "adopter"
    STAFF = "staff"
    email = forms.EmailField(required=True)
    account_type = forms.ChoiceField(
        choices=((ADOPTER, "Adopter"), (STAFF, "Shelter Staff")),
        initial=ADOPTER,
        label="Account type",
        help_text="Shelter Staff accounts complete shelter setup after signup.",
        widget=forms.RadioSelect(attrs={"class": "account-type-options"}),
    )

    class Meta:
        model = User
        fields = [
            "account_type",
            "username",
            "email",
            "first_name",
            "last_name",
            "password1",
            "password2",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = self.cleaned_data.get("account_type") == self.STAFF
        if commit:
            user.save()
        return user


class UserUpdateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ShelterForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Shelter
        fields = ["name", "email", "phone", "address", "city", "latitude", "longitude", "description", "photo"]
        labels = {"photo": "Photo/logo"}

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user and user.is_staff and not user.is_superuser:
            self.fields["email"].initial = user.email
            self.fields["email"].disabled = True
            self.fields["email"].help_text = "This uses your staff account email."
        self._style_fields()


class PersonalityTagForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PersonalityTag
        fields = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class PetForm(BootstrapFormMixin, forms.ModelForm):
    personality_tag_names = forms.CharField(
        required=False,
        label="Personality tags",
        help_text="Separate tags with commas.",
        widget=forms.TextInput(attrs={"placeholder": "Friendly, playful, calm"}),
    )

    class Meta:
        model = Pet
        fields = [
            "name",
            "species",
            "breed",
            "gender",
            "age",
            "weight",
            "color",
            "vaccination_status",
            "adoption_fee",
            "description",
            "medical_history",
            "requirements",
            "photo",
            "shelter",
            "personality_tag_names",
            "status",
        ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        include_status = kwargs.pop("include_status", True)
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.is_bound:
            tag_names = self.instance.personality_tags.values_list("name", flat=True)
            self.fields["personality_tag_names"].initial = ", ".join(tag_names)
        if not include_status:
            self.fields.pop("status", None)
        if user and user.is_staff and not user.is_superuser:
            shelters = Shelter.objects.filter(email__iexact=user.email)
            self.fields["shelter"].queryset = shelters
            if shelters.count() == 1:
                self.fields["shelter"].initial = shelters.first()
                self.fields["shelter"].disabled = True
        self._style_fields()

    @staticmethod
    def _parse_tag_names(value):
        tag_names = []
        seen = set()
        for raw_name in value.replace(";", ",").split(","):
            tag_name = raw_name.strip()
            normalized = tag_name.lower()
            if tag_name and normalized not in seen:
                tag_names.append(tag_name)
                seen.add(normalized)
        return tag_names

    def clean_personality_tag_names(self):
        value = self.cleaned_data["personality_tag_names"]
        tag_names = self._parse_tag_names(value)
        too_long = [tag_name for tag_name in tag_names if len(tag_name) > 40]
        if too_long:
            raise forms.ValidationError("Each personality tag must be 40 characters or fewer.")
        return ", ".join(tag_names)

    def save(self, commit=True):
        pet = super().save(commit=commit)
        if commit:
            self._save_personality_tags(pet)
        else:
            original_save_m2m = self.save_m2m

            def save_m2m():
                original_save_m2m()
                self._save_personality_tags(pet)

            self.save_m2m = save_m2m
        return pet

    def _save_personality_tags(self, pet):
        tag_names = self._parse_tag_names(self.cleaned_data.get("personality_tag_names", ""))
        tags = []
        for tag_name in tag_names:
            tag = PersonalityTag.objects.filter(name__iexact=tag_name).first()
            if tag is None:
                tag = PersonalityTag.objects.create(name=tag_name)
            tags.append(tag)
        pet.personality_tags.set(tags)


class AdopterProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AdopterProfile
        fields = ["city", "preferred_species", "home_type", "experience"]
        labels = {
            "city": "City or location",
            "preferred_species": "Preferred species",
            "home_type": "Home type",
            "experience": "Pet care experience",
        }
        widgets = {
            "city": forms.TextInput(attrs={"placeholder": "City, barangay, or nearby area"}),
            "home_type": forms.TextInput(attrs={"placeholder": "Apartment, house, condo, townhouse..."}),
            "experience": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Tell shelters about pets you have cared for before.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True
        self.fields["preferred_species"].choices = [("", "Choose a preferred species")] + list(Pet.Species.choices)
        self._style_fields()


class AdoptionApplicationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AdoptionApplication
        fields = ["home_type", "has_yard", "experience", "reason"]
        labels = {
            "home_type": "Home type",
            "has_yard": "Yard or outdoor space",
            "experience": "Pet care experience",
            "reason": "Why this pet is a good fit",
        }
        widgets = {
            "home_type": forms.TextInput(attrs={"placeholder": "Apartment, house, condo, townhouse..."}),
            "experience": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Tell the shelter about your previous pet care experience.",
                }
            ),
            "reason": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Share why you want to adopt this pet and how you will care for them.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ApplicationStatusForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AdoptionApplication
        fields = ["status"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def save(self, commit=True):
        application = super().save(commit=commit)
        if commit:
            application.sync_pet_status()
        return application


class MessageForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ConversationMessage
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Write a message..."})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class CareTipsForm(BootstrapFormMixin, forms.Form):
    SPECIES_CHOICES = [
        ("", "Select Species"),
        ("dog", "Dog"),
        ("cat", "Cat"),
        ("bird", "Bird"),
        ("rabbit", "Rabbit"),
    ]
    species = forms.ChoiceField(choices=SPECIES_CHOICES, required=True)
    breed = forms.CharField(max_length=100, required=False, label="Breed (optional)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
