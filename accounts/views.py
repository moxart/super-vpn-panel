from django.views.generic import RedirectView
from django.contrib.auth.models import User
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.http import HttpResponseRedirect

from django.urls import reverse_lazy
from django.conf import settings
from django.views import generic

from .forms.UserLoginForm import UserLoginForm

class LoginView(generic.FormView):
    template_name = 'accounts/layouts/login.html'
    form_class = UserLoginForm

    def form_valid(self, form):
        login(self.request, form.get_user())
        return HttpResponseRedirect('/svp/wireguard/home/')


class LogoutView(RedirectView):
    url = '/svp/login/'

    def get(self, request, *args, **kwargs):
        logout(request)
        return super(LogoutView, self).get(request, *args, **kwargs)