# Pet Adoption Platform

A Django app for posting pets for adoption, applying to adopt, messaging about applications, tracking adoption status, and managing pets, shelters, applications, users, and personality tags.

## Features

- Pet CRUD with image uploads and personality tags
- Shelter CRUD with latitude and longitude for nearby shelter search
- Adoption applications with status tracking
- Application messaging between applicants and staff
- Staff-only user management
- Login, logout, and registration

## Run Locally

```powershell
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

Uploaded pet images are stored in `media/pets/` during local development.
