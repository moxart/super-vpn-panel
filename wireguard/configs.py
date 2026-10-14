"""Rendering of wg-quick config files, QR codes and profile archives from the database."""
import io
import ipaddress
import logging
import os
import tarfile

import segno
from django.conf import settings

logger = logging.getLogger(__name__)


def format_endpoint(host, port):
    host = host.strip('[]')
    try:
        if ipaddress.ip_address(host).version == 6:
            host = '[{}]'.format(host)
    except ValueError:
        pass
    return '{}:{}'.format(host, port)


def _section(title, entries):
    lines = ['[{}]'.format(title)]
    lines.extend('{} = {}'.format(key, value) for key, value in entries if value not in (None, ''))
    return '\n'.join(lines)


def render_server_config(server):
    interface = _section('Interface', [
        ('Address', server.address),
        ('ListenPort', server.listen_port),
        ('PrivateKey', server.private_key),
        ('SaveConfig', 'true' if server.save_config else 'false'),
        ('PostUp', server.post_up.strip()),
        ('PostDown', server.post_down.strip()),
    ])
    blocks = [interface]
    for peer in server.peers.filter(enabled=True).order_by('created_at'):
        blocks.append('# {}\n'.format(peer.profile_name) + _section('Peer', [
            ('PublicKey', peer.public_key),
            ('PresharedKey', peer.preshared_key),
            ('AllowedIPs', peer.host_network),
        ]))
    return '\n\n'.join(blocks) + '\n'


def render_peer_config(peer):
    server = peer.server
    interface = _section('Interface', [
        ('PrivateKey', peer.private_key),
        ('Address', peer.address),
        ('DNS', peer.dns),
    ])
    remote = _section('Peer', [
        ('PublicKey', server.public_key),
        ('PresharedKey', peer.preshared_key),
        ('AllowedIPs', peer.allowed_ips),
        ('Endpoint', format_endpoint(server.endpoint, server.listen_port)),
        ('PersistentKeepalive', peer.persistent_keepalive),
    ])
    return interface + '\n\n' + remote + '\n'


def peer_qr_png(peer, scale=6):
    buffer = io.BytesIO()
    segno.make(render_peer_config(peer), error='m').save(buffer, kind='png', scale=scale, border=2)
    return buffer.getvalue()


def peer_profile_archive(peer):
    """A .tar.gz holding the peer's .conf and QR code, matching the archive older versions produced."""
    files = {
        '{0}/{0}.conf'.format(peer.profile_name): render_peer_config(peer).encode(),
        '{0}/{0}-qrcode.png'.format(peer.profile_name): peer_qr_png(peer),
    }
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o600
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def server_config_path(interface):
    return os.path.join(settings.WIREGUARD_SERVER_CONF, '{}.conf'.format(interface))


def write_server_config(server):
    """Rewrite <interface>.conf from the database. Returns False (and logs) if the file can't be written."""
    path = server_config_path(server.interface)
    try:
        os.makedirs(settings.WIREGUARD_SERVER_CONF, mode=0o700, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(render_server_config(server))
    except OSError:
        logger.exception('Could not write WireGuard config %s', path)
        return False
    return True


def remove_server_config(interface):
    try:
        os.remove(server_config_path(interface))
    except FileNotFoundError:
        pass
    except OSError:
        logger.exception('Could not remove WireGuard config for %s', interface)
