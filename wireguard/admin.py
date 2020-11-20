from django.contrib import admin

from .models import Server, Peer

admin.site.register(Server)
admin.site.register(Peer)
