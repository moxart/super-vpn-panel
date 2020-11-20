from django import forms
from wireguard.models import *


class ServerNewForm(forms.Form):
    interface = forms.CharField(label='Interface', widget=forms.TextInput(attrs={'class': 'input is-primary', 'autocomplete': 'off'}))
    private_key = forms.CharField(label='Private Key', widget=forms.TextInput(attrs={'class': 'input is-primary', 'autocomplete': 'off'}))
    public_key = forms.CharField(label='Public Key', widget=forms.TextInput(attrs={'class': 'input is-primary', 'autocomplete': 'off'}))
    address = forms.CharField(label='Address (eg. 10.0.0.1/24)', widget=forms.TextInput(attrs={'class': 'input is-primary', 'autocomplete': 'off'}))
    endpoint = forms.CharField(label='EndPoint', widget=forms.TextInput(attrs={'class': 'input is-primary', 'autocomplete': 'off'}))
    listen_port = forms.IntegerField(label='Listen Port', widget=forms.NumberInput(attrs={'min': '49152', 'max': '65535', 'class': 'input', 'autocomplete': 'off'}))
    post_up = forms.CharField(label='Post Up', widget=forms.Textarea(attrs={'rows': 4, 'class': 'textarea', 'autocomplete': 'off'}))
    post_down = forms.CharField(label='Post Down', widget=forms.Textarea(attrs={'rows': 4, 'class': 'textarea', 'autocomplete': 'off'}))
    save_config = forms.CharField(label='Save Config', widget=forms.CheckboxInput(), required=False)
