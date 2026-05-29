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

## Seed Demo Data

Create realistic local data for testing both adopter and shelter staff flows:

```powershell
python manage.py migrate
python manage.py seed_data
```

Useful demo logins all use `password123`:

```text
admin / password123
staff_paws / password123
staff_caws / password123
adopter_chris / password123
adopter_maya / password123
```

The seeder creates shelters, staff accounts, adopter profiles, pets with
different statuses, favorites, applications, unread messages, and archived pet
data. To rebuild a clean demo database, run:

```powershell
python manage.py seed_data --reset
```

## Google Login

Google OAuth is wired through django-allauth. To enable the button locally, copy
`.env.example` to `.env` and fill in `GOOGLE_CLIENT_ID` and
`GOOGLE_CLIENT_SECRET`, or create a Google SocialApp in the Django admin. Use
this local callback URL in the Google console:

```text
http://127.0.0.1:8000/accounts/google/login/callback/
```

When configured, the landing login and signup tabs show a Google OAuth button
for both adopter and shelter staff accounts.

## Vercel Deployment

Set these environment variables in Vercel:

```text
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=pet-adoption-platform-woad.vercel.app
DJANGO_CSRF_TRUSTED_ORIGINS=https://pet-adoption-platform-woad.vercel.app
DATABASE_URL=postgres://...
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
```

Use Vercel Marketplace Postgres, such as Neon, for `DATABASE_URL`. After the
database is connected to the Vercel project, deployments run migrations during
the build step.

Also add this production callback URL to the Google OAuth client:

```text
https://pet-adoption-platform-woad.vercel.app/accounts/google/login/callback/
```
