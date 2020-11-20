from django.utils.timezone import now

from django.db import models


class Server(models.Model):
    interface = models.CharField(max_length=50, unique=True)
    private_key = models.CharField(max_length=255, unique=True)
    public_key = models.CharField(max_length=255, unique=True)
    address = models.CharField(max_length=255, unique=True, default='10.0.0.1/24')
    endpoint = models.CharField(max_length=255)
    listen_port = models.BigIntegerField(unique=True, null=True, default=51820)
    post_up = models.TextField(max_length=255)
    post_down = models.TextField(max_length=255)
    save_config = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=now)

    def __str__(self):
        return self.interface


class Peer(models.Model):
    server = models.ForeignKey(Server, related_name='peers', on_delete=models.SET_NULL, null=True)

    profile_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    private_key = models.CharField(max_length=255, unique=True)
    public_key = models.CharField(max_length=255, unique=True)
    preshared_key = models.CharField(max_length=255, null=True, blank=True)
    address = models.CharField(max_length=255, unique=True)
    endpoint = models.CharField(max_length=255, null=True, blank=True)
    listen_port = models.BigIntegerField(null=True, default=51820)
    allowed_ips = models.CharField(max_length=255, default='0.0.0.0/0, ::/0')
    dns = models.CharField(max_length=255, default='1.1.1.1, 1.0.0.1')
    created_at = models.DateTimeField(default=now)

    def __str__(self):
        return self.profile_name
