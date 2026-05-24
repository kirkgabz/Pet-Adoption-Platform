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
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


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
        super().__init__(*args, **kwargs)
        self._style_fields()


class PersonalityTagForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PersonalityTag
        fields = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class PetForm(BootstrapFormMixin, forms.ModelForm):
    personality_tags = forms.ModelMultipleChoiceField(
        queryset=PersonalityTag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
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
            "personality_tags",
            "status",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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


class MessageForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ConversationMessage
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Write a message..."})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
