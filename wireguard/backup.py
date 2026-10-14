"""JSON backup export and import of servers and their peers."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .forms.PeerForm import PeerForm
from .forms.ServerForm import ServerForm
from .keys import public_key_for
from .models import Peer, Server
from .validators import validate_wireguard_key

BACKUP_VERSION = 1

SERVER_FIELDS = ['interface', 'private_key', 'address', 'endpoint', 'listen_port', 'post_up', 'post_down',
                 'save_config']
PEER_FIELDS = ['profile_name', 'email', 'address', 'dns', 'allowed_ips', 'persistent_keepalive', 'enabled']


def export_data():
    servers = []
    for server in Server.objects.order_by('created_at').prefetch_related('peers'):
        entry = {field: getattr(server, field) for field in SERVER_FIELDS}
        entry['peers'] = [
            dict({field: getattr(peer, field) for field in PEER_FIELDS},
                 private_key=peer.private_key, preshared_key=peer.preshared_key)
            for peer in server.peers.order_by('created_at')
        ]
        servers.append(entry)
    return {'version': BACKUP_VERSION, 'exported_at': timezone.now().isoformat(), 'servers': servers}


class BackupError(Exception):
    pass


def _errors(form):
    return '; '.join('{}: {}'.format(field, ' '.join(msgs)) for field, msgs in form.errors.items())


@transaction.atomic
def import_data(data):
    """Create servers and peers from a backup. Existing interfaces and peer names are skipped, not overwritten.

    Returns a dict of counts. Raises BackupError (and rolls back) if the file is malformed.
    """
    if not isinstance(data, dict) or data.get('version') != BACKUP_VERSION or not isinstance(data.get('servers'), list):
        raise BackupError('This is not a Super VPN Panel backup file (version %s).' % BACKUP_VERSION)

    result = {'servers': 0, 'peers': 0, 'skipped_servers': 0, 'skipped_peers': 0}
    for entry in data['servers']:
        if not isinstance(entry, dict):
            raise BackupError('Malformed server entry.')
        server = Server.objects.filter(interface=entry.get('interface')).first()
        if server is not None:
            result['skipped_servers'] += 1
        else:
            form = ServerForm(data={field: entry.get(field) for field in SERVER_FIELDS if entry.get(field) is not None})
            if not form.is_valid():
                raise BackupError('Server %s: %s' % (entry.get('interface'), _errors(form)))
            server = form.save()
            result['servers'] += 1

        for peer_entry in entry.get('peers') or []:
            if not isinstance(peer_entry, dict):
                raise BackupError('Malformed peer entry.')
            name = peer_entry.get('profile_name')
            key = (peer_entry.get('private_key') or '').strip()
            if Peer.objects.filter(profile_name=name).exists() or Peer.objects.filter(private_key=key).exists():
                result['skipped_peers'] += 1
                continue
            fields = {field: peer_entry.get(field) for field in PEER_FIELDS if peer_entry.get(field) is not None}
            fields['server'] = server.pk
            form = PeerForm(data=fields)
            if not form.is_valid():
                raise BackupError('Peer %s: %s' % (name, _errors(form)))
            try:
                validate_wireguard_key(key)
                if peer_entry.get('preshared_key'):
                    validate_wireguard_key(peer_entry['preshared_key'])
            except ValidationError as exc:
                raise BackupError('Peer %s: %s' % (name, ' '.join(exc.messages)))
            peer = form.save(commit=False)
            peer.private_key = key
            peer.public_key = public_key_for(peer.private_key)
            peer.preshared_key = (peer_entry.get('preshared_key') or '').strip()
            peer.save()
            result['peers'] += 1
    return result
