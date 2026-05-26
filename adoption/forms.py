from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import AdoptionApplication, ConversationMessage, Pet, PersonalityTag, Shelter


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
        help_text="Choose Shelter Staff if you manage pet listings for a shelter.",
        widget=forms.RadioSelect(attrs={"class": "account-type-options"}),
    )
    shelter_name = forms.CharField(
        required=False,
        label="Shelter name",
        widget=forms.TextInput(attrs={"placeholder": "Shelter or rescue organization name"}),
    )
    shelter_phone = forms.CharField(
        required=False,
        label="Shelter contact number",
        widget=forms.TextInput(attrs={"placeholder": "Phone number"}),
    )
    shelter_address = forms.CharField(
        required=False,
        label="Shelter address",
        widget=forms.TextInput(attrs={"placeholder": "Street address"}),
    )
    shelter_city = forms.CharField(
        required=False,
        label="Shelter city",
        widget=forms.TextInput(attrs={"placeholder": "City"}),
    )

    class Meta:
        model = User
        fields = [
            "account_type",
            "username",
            "email",
            "first_name",
            "last_name",
            "shelter_name",
            "shelter_phone",
            "shelter_address",
            "shelter_city",
            "password1",
            "password2",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("account_type") == self.STAFF:
            required_fields = {
                "shelter_name": "Enter the shelter name.",
                "shelter_phone": "Enter the shelter contact number.",
                "shelter_address": "Enter the shelter address.",
                "shelter_city": "Enter the shelter city.",
            }
            for field_name, message in required_fields.items():
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, message)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = self.cleaned_data.get("account_type") == self.STAFF
        if commit:
            user.save()
            if user.is_staff:
                shelter_name = self.cleaned_data["shelter_name"]
                shelter = Shelter.objects.filter(name__iexact=shelter_name).first()
                shelter_data = {
                    "email": user.email,
                    "phone": self.cleaned_data["shelter_phone"],
                    "address": self.cleaned_data["shelter_address"],
                    "city": self.cleaned_data["shelter_city"],
                }
                if shelter:
                    for field_name, value in shelter_data.items():
                        setattr(shelter, field_name, value)
                    shelter.save(update_fields=[*shelter_data.keys()])
                else:
                    Shelter.objects.create(name=shelter_name, **shelter_data)
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
        fields = ["name", "email", "phone", "address", "city", "latitude", "longitude", "description"]

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
            "age",
            "description",
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


class MessageForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ConversationMessage
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Write a message..."})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
