from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views

app_name = 'accounts'
urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
]
