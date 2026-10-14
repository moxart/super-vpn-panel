import ipaddress

from django.db import models
from django.utils.timezone import now


class Server(models.Model):
    interface = models.CharField(max_length=50, unique=True)
    private_key = models.CharField(max_length=255, unique=True)
    public_key = models.CharField(max_length=255, unique=True)
    address = models.CharField(max_length=255, unique=True, default='10.0.0.1/24')
    endpoint = models.CharField(max_length=255)
    listen_port = models.PositiveIntegerField(unique=True, default=51820)
    post_up = models.TextField(blank=True)
    post_down = models.TextField(blank=True)
    save_config = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.interface

    @property
    def ip_interface(self):
        return ipaddress.ip_interface(self.address)

    @property
    def network(self):
        return self.ip_interface.network

    def used_ips(self, exclude_peer=None):
        used = {self.ip_interface.ip}
        for peer in self.peers.all():
            if exclude_peer is not None and peer.pk == exclude_peer.pk:
                continue
            try:
                used.add(peer.ip_interface.ip)
            except ValueError:
                continue
        return used

    def next_free_address(self):
        """First unused host address in the server's subnet, with the subnet's prefix, or None if full."""
        used = self.used_ips()
        for host in self.network.hosts():
            if host not in used:
                return '{}/{}'.format(host, self.network.prefixlen)
        return None


class Peer(models.Model):
    # Nullable only so peers orphaned by older versions (which used SET_NULL) survive the migration.
    server = models.ForeignKey(Server, related_name='peers', on_delete=models.CASCADE, null=True)

    profile_name = models.CharField(max_length=255, unique=True)
    email = models.EmailField(blank=True, default='')
    private_key = models.CharField(max_length=255, unique=True)
    public_key = models.CharField(max_length=255, unique=True)
    preshared_key = models.CharField(max_length=255, blank=True, default='')
    address = models.CharField(max_length=255)
    allowed_ips = models.CharField(max_length=255, default='0.0.0.0/0, ::/0')
    dns = models.CharField(max_length=255, blank=True, default='1.1.1.1, 1.0.0.1')
    persistent_keepalive = models.PositiveIntegerField(null=True, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.profile_name

    @property
    def ip_interface(self):
        return ipaddress.ip_interface(self.address)

    @property
    def host_network(self):
        """The single-host network the server routes to this peer (e.g. 10.0.0.2/32)."""
        ip = self.ip_interface.ip
        return ipaddress.ip_network('{}/{}'.format(ip, ip.max_prefixlen))
