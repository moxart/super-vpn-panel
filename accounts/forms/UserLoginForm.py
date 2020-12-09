from django import forms
from django.contrib.auth.forms import AuthenticationForm


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={'class': 'input is-medium mb-3', 'autocomplete': 'off'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={'class': 'input is-medium', 'autocomplete': 'off'})
    )
