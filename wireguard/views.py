import os
import tarfile
import random

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from django.urls import reverse_lazy
from django.conf import settings
from django.views import generic

from .models import Server, Peer

from .forms.PeerNewForm import PeerNewForm
from .forms.ServerNewForm import ServerNewForm
from django.views.generic.edit import FormView, DeleteView


@method_decorator(login_required, name='dispatch')
class HomeView(generic.ListView):
    model = Server
    template_name = 'layouts/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['peers'] = Peer.objects.all()[:5]
        context['servers'] = Server.objects.all()[:5]
        context['peer_count'] = Peer.objects.all().count()
        context['server_count'] = Server.objects.all().count()

        return context


@method_decorator(login_required, name='dispatch')
class ServerNewView(FormView):
    template_name = 'layouts/server/server-new.html'
    form_class = ServerNewForm
    success_url = '/svp/wireguard/servers'

    def get_initial(self):
        initial = super().get_initial()

        os.system("mkdir -p {} && umask 077 {}"
                  .format(settings.WIREUGARD_TMP, settings.WIREUGARD_TMP))
        os.system("wg genkey | tee {}/server_private_key | wg pubkey | tee {}/server_public_key"
                  .format(settings.WIREUGARD_TMP, settings.WIREUGARD_TMP))

        private_key = os.popen(
            'cat {}/server_private_key'.format(settings.WIREUGARD_TMP)).read()
        public_key = os.popen(
            'cat {}/server_public_key'.format(settings.WIREUGARD_TMP)).read()

        initial['interface'] = "wg0"
        initial['post_up'] = "iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE"
        initial[
            'post_down'] = "iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE"
        initial['private_key'] = private_key.strip()
        initial['public_key'] = public_key.strip()
        initial['address'] = '10.0.0.1/24'
        initial['listen_port'] = random.randint(49152, 65535)

        return initial

    def form_valid(self, form):
        interface = form.cleaned_data['interface']
        private_key = form.cleaned_data['private_key']
        public_key = form.cleaned_data['public_key']
        address = form.cleaned_data['address']
        endpoint = form.cleaned_data['endpoint']
        listen_port = form.cleaned_data['listen_port']
        post_up = form.cleaned_data['post_up'].strip()
        post_down = form.cleaned_data['post_down'].strip()
        save_config = form.cleaned_data['save_config']

        server = Server.objects.create(
            interface=interface, private_key=private_key, public_key=public_key,
            address=address, endpoint=endpoint, listen_port=listen_port, post_up=post_up, post_down=post_down,
            save_config=save_config)

        server.save()

        os.system('echo {} >> {}server.{}.key'.format(
            private_key, settings.WIREGUARD_SERVER_KEYS, interface))
        os.system('echo {} >> {}server.{}.pub'.format(
            public_key, settings.WIREGUARD_SERVER_KEYS, interface))

        os.system('echo [Interface] "\n"Address = {} "\n"PrivateKey = {} "\n"ListenPort = {} "\n"PostUp = "{}" '
                  '"\n"PostDown = "{}" "\n"SaveConfig = {} >> {}{}.conf'.format(address, private_key, listen_port,
                                                                                str(post_up), str(
                post_down),
                                                                                save_config, settings.WIREGUARD_SERVER_CONF,
                                                                                interface))

        os.system('rm -rf {}private_key'.format(settings.WIREGUARD_SERVER_KEYS))
        os.system('rm -rf {}public_key'.format(settings.WIREGUARD_SERVER_KEYS))

        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class ServerListView(generic.ListView):
    model = Server
    template_name = 'layouts/server/servers.html'
    context_object_name = 'servers'


@method_decorator(login_required, name='dispatch')
class ServerSubsetView(generic.ListView):
    model = Server
    template_name = 'layouts/server/server-subset.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['peers'] = Peer.objects.filter(
            server__interface=self.kwargs['interface'])
        context['server'] = Server.objects.get(
            interface=self.kwargs['interface'])
        return context


@method_decorator(login_required, name='dispatch')
class ServerDeleteView(generic.DeleteView):
    model = Server
    template_name = 'layouts/server/server-delete.html'
    success_url = reverse_lazy('wireguard:server-list')


@method_decorator(login_required, name='dispatch')
class PeerNewView(FormView):
    template_name = 'layouts/peer/peer-new.html'
    form_class = PeerNewForm
    success_url = 'home'

    def get_initial(self):
        initial = super().get_initial()
        initial['dns'] = '1.1.1.1, 1.0.0.1'
        initial['address'] = '10.0.0.2/24'
        initial['allowed_ips'] = '0.0.0.0/0, ::/0'

        return initial

    def form_valid(self, form):
        server = Server.objects.get(interface=form.cleaned_data['server'])

        peer = form.cleaned_data['peer']

        os.system('mkdir -p {}{}'.format(settings.WG_PROFILES, peer))

        peer_path = os.path.join(settings.WG_PROFILES, peer)

        os.system("wg genkey | tee {}-private | wg pubkey > {}-public".format(
            peer_path + "/" + peer, peer_path + "/" + peer))
        os.system("wg genpsk > {}-preshared".format(peer_path + "/" + peer))

        private_key = os.popen(
            'cat {}-private'.format(peer_path + "/" + peer)).read()
        public_key = os.popen(
            'cat {}-public'.format(peer_path + "/" + peer)).read()
        preshared_key = os.popen(
            'cat {}-preshared'.format(peer_path + "/" + peer)).read()

        os.system('echo [Interface] "\n"Address = {} "\n"PrivateKey = {} "\n"DNS = {} "\n\n"[Peer] "\n"PublicKey = {} '
                  '"\n"PresharedKey = {} "\n"AllowedIPs = {} "\n"Endpoint = {}:{} >> {}.conf'.format(
            form.cleaned_data['address'], private_key.strip(
            ), form.cleaned_data['dns'], public_key.strip(),
            preshared_key.strip(), form.cleaned_data['allowed_ips'].strip(
            ), server.endpoint, server.listen_port,
            peer_path + "/" + peer))

        os.system("qrencode --foreground=111111 --background=896A67 -o {}-qrcode-dark.png < {}.conf".format(
            peer_path + "/" + peer, peer_path + "/" + peer))
        os.system("qrencode -o {}-qrcode-light.png < {}.conf".format(peer_path +
                                                                     "/" + peer, peer_path + "/" + peer))

        with tarfile.open(peer + ".tar.gz", "w:gz") as tar:
            tar.add(peer_path, arcname=os.path.basename(peer_path))

        os.system("mv {} {}".format(peer + ".tar.gz", settings.WIREGUARD_TARS))

        obj = Peer()

        obj.profile_name = form.cleaned_data['peer']
        obj.email = form.cleaned_data['email']
        obj.private_key = private_key
        obj.public_key = public_key
        obj.preshared_key = preshared_key
        obj.address = form.cleaned_data['address']
        obj.endpoint = server.endpoint
        obj.listen_port = server.listen_port
        obj.dns = form.cleaned_data['dns']
        obj.allowed_ips = form.cleaned_data['allowed_ips']
        obj.server = form.cleaned_data['server']

        obj.save()

        os.system('echo {} >> {}peer.{}.key'.format(
            private_key.strip(), settings.WIREGUARD_PEER_KEYS, peer))
        os.system('echo {} >> {}peer.{}.pub'.format(
            public_key.strip(), settings.WIREGUARD_PEER_KEYS, peer))
        os.system('echo {} >> {}peer.{}.pre'.format(
            preshared_key.strip(), settings.WIREGUARD_PEER_KEYS, peer))

        os.system('echo [Interface] "\n"Address = {} "\n"PrivateKey = {} "\n"DNS = {} "\n\n"[Peer] "\n"PublicKey = {} '
                  '"\n"PresharedKey = {} "\n"AllowedIPs = {} "\n"Endpoint = {}:{} >> {}{}.conf'.format(
            form.cleaned_data['address'], private_key.strip(
            ), form.cleaned_data['dns'], public_key.strip(),
            preshared_key.strip(), form.cleaned_data['allowed_ips'].strip(
            ), server.endpoint, server.listen_port, settings.WIREGUARD_PEER_CONF, peer))

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['interfaces'] = Server.objects.all()
        return context


@method_decorator(login_required, name='dispatch')
class PeerDetailView(generic.DetailView):
    model = Peer
    template_name = 'layouts/peer/peer-detail.html'


@method_decorator(login_required, name='dispatch')
class PeerListView(generic.ListView):
    model = Peer
    template_name = 'layouts/peer/peers.html'

    def get_context_data(self, **kwargs):
        context = super(PeerListView, self).get_context_data(**kwargs)
        context['peers'] = Peer.objects.all()

        return context


@method_decorator(login_required, name='dispatch')
class PeerDeleteView(generic.DeleteView):
    model = Peer
    template_name = 'layouts/peer/peer-delete.html'
    success_url = reverse_lazy('wireguard:home')
