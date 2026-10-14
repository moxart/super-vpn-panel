from django import forms

from wireguard.keys import public_key_for
from wireguard.models import Server
from wireguard.validators import (
    parse_interface_address, validate_host, validate_interface_name, validate_single_line, validate_wireguard_key,
)


class ServerForm(forms.ModelForm):
    interface = forms.CharField(
        label='Interface', validators=[validate_interface_name],
        widget=forms.TextInput(attrs={'class': 'input is-code', 'spellcheck': 'false', 'autocomplete': 'off'}))
    private_key = forms.CharField(
        label='Private key', validators=[validate_wireguard_key],
        help_text='The public key is derived from this automatically.',
        widget=forms.TextInput(attrs={'class': 'input is-code', 'spellcheck': 'false', 'autocomplete': 'off'}))
    address = forms.CharField(
        label='Address and subnet', help_text='For example 10.0.0.1/24.',
        widget=forms.TextInput(attrs={'class': 'input is-code', 'spellcheck': 'false', 'autocomplete': 'off'}))
    endpoint = forms.CharField(
        label='Endpoint', help_text='Public host name or IP address, without the port.', validators=[validate_host],
        widget=forms.TextInput(attrs={'class': 'input is-code', 'spellcheck': 'false', 'autocomplete': 'off'}))
    listen_port = forms.IntegerField(
        label='Listen port', min_value=1, max_value=65535,
        widget=forms.NumberInput(attrs={'min': '1', 'max': '65535', 'class': 'input', 'autocomplete': 'off'}))
    post_up = forms.CharField(
        label='Post up', required=False, validators=[validate_single_line],
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'textarea', 'autocomplete': 'off'}))
    post_down = forms.CharField(
        label='Post down', required=False, validators=[validate_single_line],
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'textarea', 'autocomplete': 'off'}))
    save_config = forms.BooleanField(label='Let wg-quick save runtime changes (SaveConfig)', required=False)

    class Meta:
        model = Server
        fields = ['interface', 'private_key', 'address', 'endpoint', 'listen_port', 'post_up', 'post_down',
                  'save_config']

    def clean_private_key(self):
        return self.cleaned_data['private_key'].strip()

    def clean_address(self):
        iface = parse_interface_address(self.cleaned_data['address'])
        network = iface.network

        others = Server.objects.exclude(pk=self.instance.pk)
        for other in others:
            try:
                overlaps = other.network.overlaps(network)
            except (ValueError, TypeError):
                continue
            if overlaps:
                raise forms.ValidationError('This subnet overlaps with server %(other)s (%(address)s).',
                                            params={'other': other.interface, 'address': other.address})

        if self.instance.pk:
            outside = [p.profile_name for p in self.instance.peers.all() if p.ip_interface.ip not in network]
            if outside:
                raise forms.ValidationError('Peers outside this subnet: %(names)s. Move or delete them first.',
                                            params={'names': ', '.join(outside)})
            if any(p.ip_interface.ip == iface.ip for p in self.instance.peers.all()):
                raise forms.ValidationError('A peer already uses this address.')

        return str(iface)

    def save(self, commit=True):
        self.instance.public_key = public_key_for(self.cleaned_data['private_key'])
        return super().save(commit=commit)
