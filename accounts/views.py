from django.contrib.auth import views as auth_views

from .forms.UserLoginForm import UserLoginForm


class LoginView(auth_views.LoginView):
    template_name = 'accounts/layouts/login.html'
    authentication_form = UserLoginForm
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    """POST-only in Django 5, so a link on another site can't log the user out."""
