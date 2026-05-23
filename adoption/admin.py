from django.contrib import admin

from .models import AdoptionApplication, ConversationMessage, Pet, PersonalityTag, Shelter


@admin.register(Shelter)
class ShelterAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "email", "phone")
    search_fields = ("name", "city", "address")


@admin.register(PersonalityTag)
class PersonalityTagAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ("name", "species", "shelter", "status", "created_at")
    list_filter = ("species", "status", "personality_tags")
    search_fields = ("name", "breed", "description")
    filter_horizontal = ("personality_tags",)


class MessageInline(admin.TabularInline):
    model = ConversationMessage
    extra = 0


@admin.register(AdoptionApplication)
class AdoptionApplicationAdmin(admin.ModelAdmin):
    list_display = ("pet", "applicant", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("pet__name", "applicant__username")
    inlines = [MessageInline]
