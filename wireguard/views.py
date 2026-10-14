import ipaddress
import json
import random

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View, generic

from . import configs
from .backup import BackupError, export_data, import_data
from .forms.BackupImportForm import BackupImportForm
from .forms.PeerForm import PeerForm
from .forms.ServerForm import ServerForm
from .keys import generate_keypair, generate_preshared_key, generate_private_key
from .models import Peer, Server
from .topology import server_cluster

DEFAULT_POST_UP = 'iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE'
DEFAULT_POST_DOWN = 'iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE'


def sync_server_config(request, server):
    if server is not None and not configs.write_server_config(server):
        messages.warning(request, 'Saved, but %s could not be written to disk. Check the server logs.'
                         % configs.server_config_path(server.interface))


def attachment(content, filename, content_type):
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
    response['Cache-Control'] = 'no-store'
    return response


def unused_listen_port():
    taken = set(Server.objects.values_list('listen_port', flat=True))
    free = [port for port in range(49152, 65536) if port not in taken]
    return random.choice(free) if free else 51820


def unused_server_address():
    networks = []
    for server in Server.objects.all():
        try:
            networks.append(server.network)
        except ValueError:
            continue
    for third in range(256):
        candidate = ipaddress.ip_network('10.0.{}.0/24'.format(third))
        if not any(candidate.overlaps(n) for n in networks):
            return '10.0.{}.1/24'.format(third)
    return '10.0.0.1/24'


class HomeView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'layouts/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['clusters'] = [server_cluster(server) for server in Server.objects.order_by('interface')]
        context['peers'] = Peer.objects.select_related('server')[:6]
        context['peer_count'] = Peer.objects.count()
        context['enabled_count'] = Peer.objects.filter(enabled=True).count()
        context['server_count'] = Server.objects.count()
        return context


# Servers

class ServerNewView(LoginRequiredMixin, generic.CreateView):
    model = Server
    form_class = ServerForm
    template_name = 'layouts/server/server-new.html'

    def get_initial(self):
        initial = super().get_initial()
        interface = 'wg0'
        n = 0
        while Server.objects.filter(interface=interface).exists():
            n += 1
            interface = 'wg{}'.format(n)
        initial.update({
            'interface': interface,
            'private_key': generate_private_key(),
            'address': unused_server_address(),
            'endpoint': self.request.get_host().rsplit(':', 1)[0].strip('[]'),
            'listen_port': unused_listen_port(),
            'post_up': DEFAULT_POST_UP,
            'post_down': DEFAULT_POST_DOWN,
            'save_config': True,
        })
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        sync_server_config(self.request, self.object)
        messages.success(self.request, 'Server %s created.' % self.object.interface)
        return response

    def get_success_url(self):
        return reverse('wireguard:server-subset', args=[self.object.interface])


class ServerEditView(LoginRequiredMixin, generic.UpdateView):
    model = Server
    form_class = ServerForm
    template_name = 'layouts/server/server-new.html'

    def form_valid(self, form):
        old_interface = Server.objects.get(pk=self.object.pk).interface
        response = super().form_valid(form)
        if old_interface != self.object.interface:
            configs.remove_server_config(old_interface)
        sync_server_config(self.request, self.object)
        messages.success(self.request, 'Server %s updated. Re-download peer configs if the endpoint or port changed.'
                         % self.object.interface)
        return response

    def get_success_url(self):
        return reverse('wireguard:server-subset', args=[self.object.interface])


class ServerListView(LoginRequiredMixin, generic.ListView):
    model = Server
    template_name = 'layouts/server/servers.html'
    context_object_name = 'servers'


class ServerSubsetView(LoginRequiredMixin, generic.DetailView):
    model = Server
    template_name = 'layouts/server/server-subset.html'
    slug_field = 'interface'
    slug_url_kwarg = 'interface'
    context_object_name = 'server'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['peers'] = self.object.peers.all()
        context['server_config'] = configs.render_server_config(self.object)
        return context


class ServerConfigDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        server = get_object_or_404(Server, pk=pk)
        return attachment(configs.render_server_config(server), '{}.conf'.format(server.interface), 'text/plain')


class ServerDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = Server
    template_name = 'layouts/server/server-delete.html'
    success_url = reverse_lazy('wireguard:server-list')

    def form_valid(self, form):
        interface = self.object.interface
        response = super().form_valid(form)
        configs.remove_server_config(interface)
        messages.success(self.request, 'Server %s and its peers were deleted.' % interface)
        return response


# Peers

class PeerNewView(LoginRequiredMixin, generic.CreateView):
    model = Peer
    form_class = PeerForm
    template_name = 'layouts/peer/peer-new.html'

    def get_initial(self):
        initial = super().get_initial()
        initial.update({'dns': '1.1.1.1, 1.0.0.1', 'allowed_ips': '0.0.0.0/0, ::/0', 'enabled': True})
        server_id = self.request.GET.get('server')
        if server_id and server_id.isdigit():
            initial['server'] = server_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['interfaces'] = Server.objects.all()
        return context

    def form_valid(self, form):
        form.instance.private_key, form.instance.public_key = generate_keypair()
        form.instance.preshared_key = generate_preshared_key()
        response = super().form_valid(form)
        sync_server_config(self.request, self.object.server)
        messages.success(self.request, 'Peer %s created with address %s.'
                         % (self.object.profile_name, self.object.address))
        return response

    def get_success_url(self):
        return reverse('wireguard:peer-detail', args=[self.object.pk])


class PeerEditView(LoginRequiredMixin, generic.UpdateView):
    model = Peer
    form_class = PeerForm
    template_name = 'layouts/peer/peer-new.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['interfaces'] = Server.objects.all()
        return context

    def form_valid(self, form):
        old_server = Peer.objects.get(pk=self.object.pk).server
        response = super().form_valid(form)
        if old_server is not None and old_server.pk != self.object.server_id:
            sync_server_config(self.request, old_server)
        sync_server_config(self.request, self.object.server)
        messages.success(self.request, 'Peer %s updated.' % self.object.profile_name)
        return response

    def get_success_url(self):
        return reverse('wireguard:peer-detail', args=[self.object.pk])


class PeerToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        peer = get_object_or_404(Peer, pk=pk)
        peer.enabled = not peer.enabled
        peer.save(update_fields=['enabled'])
        sync_server_config(request, peer.server)
        messages.success(request, 'Peer %s %s.' % (peer.profile_name, 'enabled' if peer.enabled else 'disabled'))
        next_url = request.POST.get('next')
        if not next_url or not url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
            next_url = reverse('wireguard:peer-detail', args=[peer.pk])
        return redirect(next_url)


class PeerDetailView(LoginRequiredMixin, generic.DetailView):
    model = Peer
    template_name = 'layouts/peer/peer-detail.html'


class PeerListView(LoginRequiredMixin, generic.ListView):
    model = Peer
    template_name = 'layouts/peer/peers.html'
    context_object_name = 'peers'

    def get_queryset(self):
        return Peer.objects.select_related('server')


class PeerDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = Peer
    template_name = 'layouts/peer/peer-delete.html'
    success_url = reverse_lazy('wireguard:peer-list')

    def form_valid(self, form):
        server = self.object.server
        name = self.object.profile_name
        response = super().form_valid(form)
        sync_server_config(self.request, server)
        messages.success(self.request, 'Peer %s deleted.' % name)
        return response


class PeerDownloadView(LoginRequiredMixin, View):
    """Serves a peer's .conf, QR code or profile archive. These contain the private key, so never via /static/."""

    def get(self, request, pk, kind):
        peer = get_object_or_404(Peer.objects.select_related('server'), pk=pk)
        if peer.server is None:
            raise Http404('This peer has no server.')
        name = peer.profile_name
        if kind == 'conf':
            return attachment(configs.render_peer_config(peer), '{}.conf'.format(name), 'text/plain')
        if kind == 'qr':
            response = HttpResponse(configs.peer_qr_png(peer), content_type='image/png')
            response['Cache-Control'] = 'no-store'
            return response
        if kind == 'profile':
            return attachment(configs.peer_profile_archive(peer), '{}.tar.gz'.format(name), 'application/gzip')
        raise Http404


# Backup

class BackupView(LoginRequiredMixin, generic.FormView):
    template_name = 'layouts/backup.html'
    form_class = BackupImportForm
    success_url = reverse_lazy('wireguard:backup')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['server_count'] = Server.objects.count()
        context['peer_count'] = Peer.objects.count()
        return context

    def form_valid(self, form):
        try:
            result = import_data(form.cleaned_data['data'])
        except BackupError as exc:
            form.add_error('file', str(exc))
            return self.form_invalid(form)
        for server in Server.objects.all():
            sync_server_config(self.request, server)
        messages.success(self.request,
                         'Imported {servers} servers and {peers} peers; skipped {skipped_servers} existing servers '
                         'and {skipped_peers} existing peers.'.format(**result))
        return HttpResponseRedirect(self.get_success_url())


class BackupExportView(LoginRequiredMixin, View):
    def get(self, request):
        filename = 'super-vpn-panel-backup-{}.json'.format(timezone.now().strftime('%Y%m%d-%H%M%S'))
        return attachment(json.dumps(export_data(), indent=2), filename, 'application/json')
