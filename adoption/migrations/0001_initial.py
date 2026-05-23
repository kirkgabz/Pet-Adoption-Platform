# Generated for the pet adoption platform scaffold.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PersonalityTag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=40, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Shelter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("address", models.CharField(max_length=255)),
                ("city", models.CharField(max_length=80)),
                ("latitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Pet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("species", models.CharField(choices=[("dog", "Dog"), ("cat", "Cat"), ("bird", "Bird"), ("rabbit", "Rabbit"), ("other", "Other")], max_length=20)),
                ("breed", models.CharField(blank=True, max_length=100)),
                ("age", models.PositiveIntegerField(help_text="Age in years")),
                ("description", models.TextField()),
                ("photo", models.ImageField(blank=True, null=True, upload_to="pets/")),
                ("status", models.CharField(choices=[("available", "Available"), ("pending", "Pending"), ("adopted", "Adopted")], default="available", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("personality_tags", models.ManyToManyField(blank=True, related_name="pets", to="adoption.personalitytag")),
                ("posted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("shelter", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pets", to="adoption.shelter")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="AdoptionApplication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("home_type", models.CharField(max_length=80)),
                ("has_yard", models.BooleanField(default=False)),
                ("experience", models.TextField()),
                ("reason", models.TextField()),
                ("status", models.CharField(choices=[("submitted", "Submitted"), ("reviewing", "Reviewing"), ("approved", "Approved"), ("declined", "Declined"), ("completed", "Completed")], default="submitted", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("applicant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="applications", to=settings.AUTH_USER_MODEL)),
                ("pet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="applications", to="adoption.pet")),
            ],
            options={"ordering": ["-created_at"], "unique_together": {("pet", "applicant")}},
        ),
        migrations.CreateModel(
            name="ConversationMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("application", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="adoption.adoptionapplication")),
                ("sender", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sent_messages", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at"]},
        ),
    ]
