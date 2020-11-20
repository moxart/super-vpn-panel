from django import forms
from wireguard.models import *


class PeerNewForm(forms.Form):
    server = forms.ModelChoiceField(label='Server', queryset=Server.objects.all(), empty_label=None, widget=forms.Select(attrs={'class': 'select', 'style': 'min-width:150px'}))
    peer = forms.CharField(label='Peer Name', widget=forms.TextInput(attrs={'class': 'input is-primary', 'autocomplete': 'off'}))
    email = forms.EmailField(widget=forms.TextInput(attrs={'class': 'input is-primary', 'autocomplete': 'off'}))
    dns = forms.CharField(label='DNS', widget=forms.TextInput(attrs={'class': 'input', 'autocomplete': 'off'}))
    address = forms.CharField(label='Address (eg. 10.0.0.2/24)', widget=forms.TextInput(attrs={'class': 'input', 'autocomplete': 'off'}))
    allowed_ips = forms.CharField(label='Allowed IPs (eg. 0.0.0.0/0, ::/0)', widget=forms.TextInput(attrs={'class': 'input', 'autocomplete': 'off'}))