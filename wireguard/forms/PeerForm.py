import ipaddress

from django import forms

from wireguard.models import Peer, Server
from wireguard.validators import validate_dns_list, validate_network_list, validate_profile_name


class PeerForm(forms.ModelForm):
    server = forms.ModelChoiceField(
        label='Server', queryset=Server.objects.all(), empty_label=None,
        widget=forms.Select())
    profile_name = forms.CharField(
        label='Name', validators=[validate_profile_name],
        help_text='Letters, digits, dots, dashes and underscores. For example maria-phone.',
        widget=forms.TextInput(attrs={'class': 'input', 'autocomplete': 'off'}))
    email = forms.EmailField(
        label='Email', required=False, help_text='Optional, to remember who the device belongs to.',
        widget=forms.EmailInput(attrs={'class': 'input', 'autocomplete': 'off'}))
    address = forms.CharField(
        label='Address', help_text='Leave empty to use the next free address.', required=False,
        widget=forms.TextInput(attrs={'class': 'input is-code', 'spellcheck': 'false', 'autocomplete': 'off', 'placeholder': 'auto'}))
    dns = forms.CharField(
        label='DNS', required=False, validators=[validate_dns_list],
        widget=forms.TextInput(attrs={'class': 'input is-code', 'spellcheck': 'false', 'autocomplete': 'off'}))
    allowed_ips = forms.CharField(
        label='Allowed IPs', validators=[validate_network_list],
        widget=forms.TextInput(attrs={'class': 'input is-code', 'spellcheck': 'false', 'autocomplete': 'off'}))
    persistent_keepalive = forms.IntegerField(
        label='Persistent keepalive', help_text='Seconds. Optional.', required=False, min_value=1, max_value=65535,
        widget=forms.NumberInput(attrs={'class': 'input', 'autocomplete': 'off', 'placeholder': 'e.g. 25'}))
    enabled = forms.BooleanField(label='Enabled, so the server accepts this peer', required=False, initial=True)

    class Meta:
        model = Peer
        fields = ['server', 'profile_name', 'email', 'address', 'dns', 'allowed_ips', 'persistent_keepalive',
                  'enabled']

    def clean_dns(self):
        return ', '.join(item.strip() for item in self.cleaned_data['dns'].split(',') if item.strip())

    def clean_allowed_ips(self):
        return ', '.join(item.strip() for item in self.cleaned_data['allowed_ips'].split(',') if item.strip())

    def clean(self):
        cleaned = super().clean()
        server = cleaned.get('server')
        if server is None or self.has_error('address'):
            return cleaned

        raw = (cleaned.get('address') or '').strip()
        network = server.network

        if not raw:
            if self.instance.pk and self.instance.server_id == server.pk and self.instance.address:
                cleaned['address'] = self.instance.address
                return cleaned
            address = server.next_free_address()
            if address is None:
                self.add_error('address', 'Server %s has no free addresses left.' % server.interface)
            else:
                cleaned['address'] = address
            return cleaned

        try:
            if '/' in raw:
                iface = ipaddress.ip_interface(raw)
            else:
                iface = ipaddress.ip_interface('{}/{}'.format(raw, network.prefixlen))
        except ValueError:
            self.add_error('address', 'Enter an IP address such as 10.0.0.2 or 10.0.0.2/24.')
            return cleaned

        ip = iface.ip
        if ip.version != network.version or ip not in network:
            self.add_error('address', 'The address must be inside %s.' % network)
        elif ip == network.network_address or (ip.version == 4 and ip == network.broadcast_address):
            self.add_error('address', 'The address cannot be the network or broadcast address.')
        elif ip in server.used_ips(exclude_peer=self.instance if self.instance.pk else None):
            self.add_error('address', '%s is already used on %s.' % (ip, server.interface))
        else:
            cleaned['address'] = str(iface)
        return cleaned
