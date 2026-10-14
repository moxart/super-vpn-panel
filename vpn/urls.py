from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='wireguard:home')),
    path('svp/', RedirectView.as_view(pattern_name='wireguard:home')),
    path('svp/wireguard/', include('wireguard.urls')),
    path('svp/', include('accounts.urls')),
    path('svp/admin/', admin.site.urls),
]
