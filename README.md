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

## Google Login

Google OAuth is wired through django-allauth. To enable the button locally, copy
`.env.example` to `.env` and fill in `GOOGLE_CLIENT_ID` and
`GOOGLE_CLIENT_SECRET`, or create a Google SocialApp in the Django admin. Use
this local callback URL in the Google console:

```text
http://127.0.0.1:8000/accounts/google/login/callback/
```

When configured, the adopter login and signup screens show a Google OAuth
button. Shelter staff accounts continue to use username and password login.
