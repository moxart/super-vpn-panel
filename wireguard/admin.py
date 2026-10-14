from django.contrib import admin

from . import configs
from .models import Peer, Server


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = ('interface', 'address', 'endpoint', 'listen_port', 'created_at')
    search_fields = ('interface', 'endpoint')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        configs.write_server_config(obj)

    def delete_model(self, request, obj):
        interface = obj.interface
        super().delete_model(request, obj)
        configs.remove_server_config(interface)


@admin.register(Peer)
class PeerAdmin(admin.ModelAdmin):
    list_display = ('profile_name', 'server', 'address', 'email', 'enabled', 'created_at')
    list_filter = ('server', 'enabled')
    search_fields = ('profile_name', 'email', 'address')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.server:
            configs.write_server_config(obj.server)

    def delete_model(self, request, obj):
        server = obj.server
        super().delete_model(request, obj)
        if server:
            configs.write_server_config(server)
