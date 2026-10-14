from django.db import migrations, models
import django.db.models.deletion


def clean_existing_rows(apps, schema_editor):
    """Normalise data written by earlier versions so the tightened constraints below can apply.

    Older code stored keys read from `wg genkey` with a trailing newline, allowed duplicate or
    missing peer names, and left several columns NULL.
    """
    Server = apps.get_model('wireguard', 'Server')
    Peer = apps.get_model('wireguard', 'Peer')

    used_ports = set(Server.objects.exclude(listen_port=None).values_list('listen_port', flat=True))
    next_port = 51820
    for server in Server.objects.all():
        server.private_key = server.private_key.strip()
        server.public_key = server.public_key.strip()
        if server.listen_port is None:
            while next_port in used_ports:
                next_port += 1
            server.listen_port = next_port
            used_ports.add(next_port)
        server.save()

    seen_names = set()
    for peer in Peer.objects.order_by('id'):
        peer.private_key = peer.private_key.strip()
        peer.public_key = peer.public_key.strip()
        peer.preshared_key = (peer.preshared_key or '').strip()
        peer.email = peer.email or ''
        peer.dns = peer.dns or ''
        name = (peer.profile_name or '').strip() or 'peer-{}'.format(peer.id)
        if name in seen_names:
            name = '{}-{}'.format(name, peer.id)
        seen_names.add(name)
        peer.profile_name = name
        peer.save()


class Migration(migrations.Migration):

    dependencies = [
        ('wireguard', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(clean_existing_rows, migrations.RunPython.noop),

        migrations.AlterModelOptions(name='server', options={'ordering': ['-created_at']}),
        migrations.AlterModelOptions(name='peer', options={'ordering': ['-created_at']}),

        migrations.AlterField(
            model_name='server',
            name='listen_port',
            field=models.PositiveIntegerField(default=51820, unique=True),
        ),
        migrations.AlterField(
            model_name='server',
            name='post_up',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='server',
            name='post_down',
            field=models.TextField(blank=True),
        ),

        migrations.RemoveField(model_name='peer', name='endpoint'),
        migrations.RemoveField(model_name='peer', name='listen_port'),
        migrations.AlterField(
            model_name='peer',
            name='server',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name='peers', to='wireguard.server'),
        ),
        migrations.AlterField(
            model_name='peer',
            name='profile_name',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name='peer',
            name='email',
            field=models.EmailField(blank=True, default='', max_length=254),
        ),
        migrations.AlterField(
            model_name='peer',
            name='preshared_key',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='peer',
            name='address',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='peer',
            name='dns',
            field=models.CharField(blank=True, default='1.1.1.1, 1.0.0.1', max_length=255),
        ),
        migrations.AddField(
            model_name='peer',
            name='persistent_keepalive',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='peer',
            name='enabled',
            field=models.BooleanField(default=True),
        ),
    ]
