import io
import json
import os
import shutil
import tarfile
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from . import configs
from .backup import export_data, import_data
from .forms.PeerForm import PeerForm
from .forms.ServerForm import ServerForm
from .keys import decode_key, generate_keypair, generate_preshared_key, generate_private_key, public_key_for
from .models import Peer, Server

# RFC 7748 section 6.1 test vector (Alice), base64-encoded the way WireGuard prints keys.
RFC7748_PRIVATE = 'dwdtCnMYpX08FsFyUbJmRd9ML4frwJkqsXf7pR25LCo='
RFC7748_PUBLIC = 'hSDwCYkwp1R0i33ctD73Wg2/Og0mOBr066SpjqqbTmo='


def make_server(**overrides):
    private_key, public_key = generate_keypair()
    fields = dict(interface='wg0', private_key=private_key, public_key=public_key, address='10.0.0.1/24',
                  endpoint='vpn.example.com', listen_port=51820, post_up='', post_down='')
    fields.update(overrides)
    return Server.objects.create(**fields)


def make_peer(server, name='alice', address='10.0.0.2/24', **overrides):
    private_key, public_key = generate_keypair()
    fields = dict(server=server, profile_name=name, private_key=private_key, public_key=public_key,
                  preshared_key=generate_preshared_key(), address=address)
    fields.update(overrides)
    return Peer.objects.create(**fields)


class KeyTests(TestCase):
    def test_public_key_matches_rfc7748_vector(self):
        self.assertEqual(public_key_for(RFC7748_PRIVATE), RFC7748_PUBLIC)

    def test_generated_keys_are_32_bytes(self):
        for key in (generate_private_key(), generate_preshared_key(), *generate_keypair()):
            self.assertEqual(len(decode_key(key)), 32)

    def test_decode_rejects_bad_keys(self):
        for bad in ('not base64!', 'AAAA', ''):
            with self.assertRaises(ValueError):
                decode_key(bad)


class ServerModelTests(TestCase):
    def test_next_free_address_skips_server_and_used(self):
        server = make_server()
        self.assertEqual(server.next_free_address(), '10.0.0.2/24')
        make_peer(server, address='10.0.0.2/24')
        make_peer(server, name='bob', address='10.0.0.3/32')
        self.assertEqual(server.next_free_address(), '10.0.0.4/24')

    def test_next_free_address_when_full(self):
        server = make_server(address='10.0.0.1/30')
        make_peer(server, address='10.0.0.2/30')
        self.assertIsNone(server.next_free_address())


class ConfigRenderingTests(TestCase):
    def setUp(self):
        self.server = make_server(post_up='iptables -A FORWARD -i %i -j ACCEPT', save_config=False)
        self.peer = make_peer(self.server, persistent_keepalive=25)

    def test_server_config_includes_enabled_peers_as_host_routes(self):
        disabled = make_peer(self.server, name='bob', address='10.0.0.3/24', enabled=False)
        text = configs.render_server_config(self.server)
        self.assertIn('[Interface]\nAddress = 10.0.0.1/24\nListenPort = 51820\n', text)
        self.assertIn('SaveConfig = false', text)
        self.assertIn('PostUp = iptables -A FORWARD -i %i -j ACCEPT', text)
        self.assertNotIn('PostDown', text)
        self.assertIn('# alice\n[Peer]\nPublicKey = {}\n'.format(self.peer.public_key), text)
        self.assertIn('AllowedIPs = 10.0.0.2/32', text)
        self.assertNotIn(disabled.public_key, text)

    def test_peer_config(self):
        text = configs.render_peer_config(self.peer)
        self.assertEqual(text, (
            '[Interface]\n'
            'PrivateKey = {p.private_key}\n'
            'Address = 10.0.0.2/24\n'
            'DNS = 1.1.1.1, 1.0.0.1\n'
            '\n'
            '[Peer]\n'
            'PublicKey = {s.public_key}\n'
            'PresharedKey = {p.preshared_key}\n'
            'AllowedIPs = 0.0.0.0/0, ::/0\n'
            'Endpoint = vpn.example.com:51820\n'
            'PersistentKeepalive = 25\n'
        ).format(p=self.peer, s=self.server))

    def test_ipv6_endpoint_is_bracketed(self):
        self.assertEqual(configs.format_endpoint('2001:db8::1', 51820), '[2001:db8::1]:51820')
        self.assertEqual(configs.format_endpoint('203.0.113.5', 51820), '203.0.113.5:51820')

    def test_profile_archive_contents(self):
        archive = tarfile.open(fileobj=io.BytesIO(configs.peer_profile_archive(self.peer)))
        self.assertEqual(sorted(archive.getnames()), ['alice/alice-qrcode.png', 'alice/alice.conf'])
        conf = archive.extractfile('alice/alice.conf').read().decode()
        self.assertEqual(conf, configs.render_peer_config(self.peer))

    def test_qr_is_png(self):
        self.assertTrue(configs.peer_qr_png(self.peer).startswith(b'\x89PNG'))


class ServerFormTests(TestCase):
    def data(self, **overrides):
        data = dict(interface='wg0', private_key=generate_private_key(), address='10.0.0.1/24',
                    endpoint='vpn.example.com', listen_port=51820, post_up='', post_down='', save_config='on')
        data.update(overrides)
        return data

    def test_valid_form_derives_public_key(self):
        form = ServerForm(data=self.data(private_key=RFC7748_PRIVATE))
        self.assertTrue(form.is_valid(), form.errors)
        server = form.save()
        self.assertEqual(server.public_key, RFC7748_PUBLIC)
        self.assertTrue(server.save_config)

    def test_rejects_unsafe_input(self):
        cases = {
            'interface': 'wg0; rm -rf /',
            'private_key': 'not-a-key',
            'address': '10.0.0.0/24',
            'endpoint': 'host:51820',
            'post_up': 'echo a\n[Peer]',
        }
        for field, value in cases.items():
            form = ServerForm(data=self.data(**{field: value}))
            self.assertFalse(form.is_valid(), field)
            self.assertIn(field, form.errors)

    def test_rejects_overlapping_subnet(self):
        make_server()
        form = ServerForm(data=self.data(interface='wg1', address='10.0.0.129/25', listen_port=51821))
        self.assertFalse(form.is_valid())
        self.assertIn('address', form.errors)

    def test_edit_rejects_subnet_that_strands_peers(self):
        server = make_server()
        make_peer(server, address='10.0.0.200/24')
        form = ServerForm(instance=server, data=self.data(private_key=server.private_key, address='10.0.0.1/25'))
        self.assertFalse(form.is_valid())
        self.assertIn('address', form.errors)


class PeerFormTests(TestCase):
    def setUp(self):
        self.server = make_server()

    def data(self, **overrides):
        data = dict(server=self.server.pk, profile_name='alice', email='', address='', dns='1.1.1.1',
                    allowed_ips='0.0.0.0/0', enabled='on')
        data.update(overrides)
        return data

    def test_blank_address_is_auto_assigned(self):
        form = PeerForm(data=self.data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['address'], '10.0.0.2/24')

    def test_bare_ip_gets_server_prefix(self):
        form = PeerForm(data=self.data(address='10.0.0.9'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['address'], '10.0.0.9/24')

    def test_address_validation(self):
        make_peer(self.server, name='bob', address='10.0.0.2/24')
        for address in ('10.0.0.2', '10.0.0.1', '192.168.1.5', '10.0.0.255', 'nonsense'):
            form = PeerForm(data=self.data(address=address))
            self.assertFalse(form.is_valid(), address)
            self.assertIn('address', form.errors)

    def test_editing_keeps_own_address(self):
        peer = make_peer(self.server, address='10.0.0.2/24')
        form = PeerForm(instance=peer, data=self.data(address='10.0.0.2/24'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_bad_names_and_lists(self):
        for field, value in {'profile_name': '../etc', 'allowed_ips': '0.0.0.0/0, nope', 'dns': '1.1.1.1, bad host'}.items():
            form = PeerForm(data=self.data(**{field: value}))
            self.assertFalse(form.is_valid(), field)
            self.assertIn(field, form.errors)

    def test_duplicate_name_rejected(self):
        make_peer(self.server, name='alice', address='10.0.0.5/24')
        form = PeerForm(data=self.data())
        self.assertFalse(form.is_valid())
        self.assertIn('profile_name', form.errors)


class BackupTests(TestCase):
    def test_round_trip(self):
        server = make_server()
        make_peer(server, persistent_keepalive=25, enabled=False)
        data = json.loads(json.dumps(export_data()))
        Server.objects.all().delete()

        result = import_data(data)
        self.assertEqual(result, {'servers': 1, 'peers': 1, 'skipped_servers': 0, 'skipped_peers': 0})
        restored = Peer.objects.get()
        self.assertEqual(restored.server.interface, 'wg0')
        self.assertEqual(restored.persistent_keepalive, 25)
        self.assertFalse(restored.enabled)
        self.assertEqual(restored.public_key, public_key_for(restored.private_key))

        self.assertEqual(import_data(data)['skipped_peers'], 1)


class ViewTestCase(TestCase):
    def setUp(self):
        self.conf_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.conf_dir)
        override = override_settings(WIREGUARD_SERVER_CONF=self.conf_dir)
        override.enable()
        self.addCleanup(override.disable)
        self.user = User.objects.create_user('admin', password='pw')
        self.client.force_login(self.user)

    def conf_text(self, interface='wg0'):
        with open(os.path.join(self.conf_dir, interface + '.conf')) as handle:
            return handle.read()


class AccessTests(ViewTestCase):
    def test_pages_require_login(self):
        server = make_server()
        peer = make_peer(server)
        self.client.logout()
        urls = [
            reverse('wireguard:home'), reverse('wireguard:peer-list'), reverse('wireguard:server-list'),
            reverse('wireguard:server-subset', args=['wg0']), reverse('wireguard:server-config', args=[server.pk]),
            reverse('wireguard:peer-detail', args=[peer.pk]), reverse('wireguard:backup-export'),
            reverse('wireguard:peer-download', args=[peer.pk, 'conf']),
            reverse('wireguard:peer-download', args=[peer.pk, 'qr']),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertTrue(response['Location'].startswith(reverse('accounts:login')), url)

    def test_all_pages_render(self):
        server = make_server()
        peer = make_peer(server)
        urls = [
            reverse('wireguard:home'), reverse('wireguard:peer-list'), reverse('wireguard:server-list'),
            reverse('wireguard:server-new'), reverse('wireguard:peer-new'),
            reverse('wireguard:server-subset', args=['wg0']), reverse('wireguard:server-edit', args=[server.pk]),
            reverse('wireguard:server-delete', args=[server.pk]), reverse('wireguard:peer-detail', args=[peer.pk]),
            reverse('wireguard:peer-edit', args=[peer.pk]), reverse('wireguard:peer-delete', args=[peer.pk]),
            reverse('wireguard:backup'),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_unknown_server_is_404(self):
        self.assertEqual(self.client.get(reverse('wireguard:server-subset', args=['nope'])).status_code, 404)


class ServerViewTests(ViewTestCase):
    def test_new_server_form_prefills_free_values(self):
        make_server()
        initial = self.client.get(reverse('wireguard:server-new')).context['form'].initial
        self.assertEqual(initial['interface'], 'wg1')
        self.assertEqual(initial['address'], '10.0.1.1/24')
        self.assertNotEqual(initial['listen_port'], 51820)
        decode_key(initial['private_key'])

    def test_create_writes_config(self):
        response = self.client.post(reverse('wireguard:server-new'), {
            'interface': 'wg0', 'private_key': RFC7748_PRIVATE, 'address': '10.8.0.1/24',
            'endpoint': 'vpn.example.com', 'listen_port': 51820, 'post_up': '', 'post_down': '',
        })
        self.assertRedirects(response, reverse('wireguard:server-subset', args=['wg0']))
        self.assertEqual(Server.objects.get().public_key, RFC7748_PUBLIC)
        self.assertIn('Address = 10.8.0.1/24', self.conf_text())
        self.assertEqual(os.stat(os.path.join(self.conf_dir, 'wg0.conf')).st_mode & 0o777, 0o600)

    def test_rename_moves_config_file(self):
        server = make_server()
        configs.write_server_config(server)
        self.client.post(reverse('wireguard:server-edit', args=[server.pk]), {
            'interface': 'wg9', 'private_key': server.private_key, 'address': server.address,
            'endpoint': server.endpoint, 'listen_port': server.listen_port, 'post_up': '', 'post_down': '',
        })
        self.assertFalse(os.path.exists(os.path.join(self.conf_dir, 'wg0.conf')))
        self.assertTrue(os.path.exists(os.path.join(self.conf_dir, 'wg9.conf')))

    def test_delete_removes_peers_and_file(self):
        server = make_server()
        make_peer(server)
        configs.write_server_config(server)
        self.client.post(reverse('wireguard:server-delete', args=[server.pk]))
        self.assertFalse(Peer.objects.exists())
        self.assertFalse(os.path.exists(os.path.join(self.conf_dir, 'wg0.conf')))

    def test_config_download(self):
        server = make_server()
        response = self.client.get(reverse('wireguard:server-config', args=[server.pk]))
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="wg0.conf"')
        self.assertEqual(response.content.decode(), configs.render_server_config(server))


class PeerViewTests(ViewTestCase):
    def setUp(self):
        super().setUp()
        self.server = make_server()

    def create_peer(self, name='alice', **overrides):
        data = {'server': self.server.pk, 'profile_name': name, 'email': '', 'address': '',
                'dns': '1.1.1.1, 1.0.0.1', 'allowed_ips': '0.0.0.0/0, ::/0', 'enabled': 'on'}
        data.update(overrides)
        return self.client.post(reverse('wireguard:peer-new'), data)

    def test_create_peer_assigns_address_and_updates_server_config(self):
        response = self.create_peer()
        peer = Peer.objects.get()
        self.assertRedirects(response, reverse('wireguard:peer-detail', args=[peer.pk]))
        self.assertEqual(peer.address, '10.0.0.2/24')
        self.assertEqual(peer.public_key, public_key_for(peer.private_key))
        self.assertIn(peer.public_key, self.conf_text())

        self.create_peer('bob')
        self.assertEqual(Peer.objects.get(profile_name='bob').address, '10.0.0.3/24')

    def test_duplicate_name_shows_error_instead_of_crashing(self):
        self.create_peer()
        response = self.create_peer()
        self.assertEqual(response.status_code, 200)
        self.assertIn('profile_name', response.context['form'].errors)

    def test_downloads(self):
        self.create_peer()
        peer = Peer.objects.get()
        conf = self.client.get(reverse('wireguard:peer-download', args=[peer.pk, 'conf']))
        self.assertEqual(conf['Content-Disposition'], 'attachment; filename="alice.conf"')
        self.assertEqual(conf.content.decode(), configs.render_peer_config(peer))
        qr = self.client.get(reverse('wireguard:peer-download', args=[peer.pk, 'qr']))
        self.assertEqual(qr['Content-Type'], 'image/png')
        profile = self.client.get(reverse('wireguard:peer-download', args=[peer.pk, 'profile']))
        self.assertEqual(profile['Content-Type'], 'application/gzip')
        self.assertEqual(self.client.get(reverse('wireguard:peer-download', args=[peer.pk, 'x'])).status_code, 404)

    def test_toggle_removes_peer_from_server_config(self):
        self.create_peer()
        peer = Peer.objects.get()
        self.client.post(reverse('wireguard:peer-toggle', args=[peer.pk]))
        self.assertNotIn(peer.public_key, self.conf_text())
        self.client.post(reverse('wireguard:peer-toggle', args=[peer.pk]), {'next': 'https://evil.example/'})
        self.assertIn(peer.public_key, self.conf_text())

    def test_toggle_requires_post(self):
        peer = make_peer(self.server)
        self.assertEqual(self.client.get(reverse('wireguard:peer-toggle', args=[peer.pk])).status_code, 405)

    def test_delete_updates_server_config(self):
        self.create_peer()
        peer = Peer.objects.get()
        self.client.post(reverse('wireguard:peer-delete', args=[peer.pk]))
        self.assertFalse(Peer.objects.exists())
        self.assertNotIn(peer.public_key, self.conf_text())

    def test_moving_peer_updates_both_servers(self):
        other = make_server(interface='wg1', address='10.0.1.1/24', listen_port=51821)
        self.create_peer()
        peer = Peer.objects.get()
        self.client.post(reverse('wireguard:peer-edit', args=[peer.pk]), {
            'server': other.pk, 'profile_name': 'alice', 'address': '', 'dns': '', 'allowed_ips': '0.0.0.0/0',
            'enabled': 'on',
        })
        peer.refresh_from_db()
        self.assertEqual(peer.address, '10.0.1.2/24')
        self.assertNotIn(peer.public_key, self.conf_text('wg0'))
        self.assertIn(peer.public_key, self.conf_text('wg1'))


class BackupViewTests(ViewTestCase):
    def test_export_and_import(self):
        server = make_server()
        make_peer(server)
        exported = self.client.get(reverse('wireguard:backup-export'))
        self.assertEqual(exported['Content-Type'], 'application/json')
        Server.objects.all().delete()

        upload = SimpleUploadedFile('backup.json', exported.content, content_type='application/json')
        response = self.client.post(reverse('wireguard:backup'), {'file': upload})
        self.assertRedirects(response, reverse('wireguard:backup'))
        self.assertEqual(Peer.objects.count(), 1)
        self.assertIn(Peer.objects.get().public_key, self.conf_text())

    def test_invalid_file_shows_error(self):
        upload = SimpleUploadedFile('backup.json', b'{"version": 99}', content_type='application/json')
        response = self.client.post(reverse('wireguard:backup'), {'file': upload})
        self.assertEqual(response.status_code, 200)
        self.assertIn('file', response.context['form'].errors)
