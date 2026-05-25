from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from adoption.views import RoleBasedLoginView, google_login

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", RoleBasedLoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/google/login/", google_login, name="google_login"),
    path("accounts/", include("allauth.urls")),
    path("", include("adoption.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
