from django.urls import path

from . import views

urlpatterns = [
    path("", views.LandingView.as_view(), name="home"),
    path("dashboard/", views.PetListView.as_view(), name="pet-list"),
    path("pets/new/", views.PetCreateView.as_view(), name="pet-create"),
    path("pets/<int:pk>/", views.PetDetailView.as_view(), name="pet-detail"),
    path("pets/<int:pk>/edit/", views.PetUpdateView.as_view(), name="pet-update"),
    path("pets/<int:pk>/delete/", views.PetDeleteView.as_view(), name="pet-delete"),
    path("pets/<int:pk>/apply/", views.apply_to_adopt, name="application-create"),
    path("shelters/", views.ShelterListView.as_view(), name="shelter-list"),
    path("shelters/nearby/", views.nearby_shelters, name="nearby-shelters"),
    path("shelters/new/", views.ShelterCreateView.as_view(), name="shelter-create"),
    path("shelters/<int:pk>/", views.ShelterDetailView.as_view(), name="shelter-detail"),
    path("shelters/<int:pk>/edit/", views.ShelterUpdateView.as_view(), name="shelter-update"),
    path("shelters/<int:pk>/delete/", views.ShelterDeleteView.as_view(), name="shelter-delete"),
    path("applications/", views.ApplicationListView.as_view(), name="application-list"),
    path("applications/<int:pk>/", views.application_detail, name="application-detail"),
    path("applications/<int:pk>/edit/", views.ApplicationUpdateView.as_view(), name="application-update"),
    path("applications/<int:pk>/delete/", views.ApplicationDeleteView.as_view(), name="application-delete"),
    path("tags/", views.TagListView.as_view(), name="tag-list"),
    path("tags/new/", views.TagCreateView.as_view(), name="tag-create"),
    path("tags/<int:pk>/edit/", views.TagUpdateView.as_view(), name="tag-update"),
    path("tags/<int:pk>/delete/", views.TagDeleteView.as_view(), name="tag-delete"),
    path("users/register/", views.register, name="register"),
    path("users/", views.UserListView.as_view(), name="user-list"),
    path("users/<int:pk>/edit/", views.UserUpdateView.as_view(), name="user-update"),
    path("users/<int:pk>/delete/", views.UserDeleteView.as_view(), name="user-delete"),
]
