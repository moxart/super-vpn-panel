import ipaddress
import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from .keys import decode_key

# Linux limits interface names to 15 characters; wg-quick accepts this character set.
validate_interface_name = RegexValidator(
    r'^[A-Za-z0-9_=+.-]{1,15}$',
    'Use up to 15 letters, digits or _=+.- characters (e.g. wg0).')

# Peer names end up in file names and download headers, so keep them plain.
validate_profile_name = RegexValidator(
    r'^[A-Za-z0-9_.-]{1,64}$',
    'Use up to 64 letters, digits or _.- characters.')

_HOSTNAME = re.compile(r'^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$')


def validate_single_line(value):
    if '\n' in value or '\r' in value:
        raise ValidationError('Must be a single line.')


def validate_wireguard_key(value):
    try:
        decode_key(value)
    except ValueError as exc:
        raise ValidationError(str(exc))


def validate_host(value):
    try:
        ipaddress.ip_address(value.strip('[]'))
        return
    except ValueError:
        pass
    if not _HOSTNAME.match(value):
        raise ValidationError('Enter a host name or IP address without a port.')


def split_list(value):
    return [item.strip() for item in value.split(',') if item.strip()]


def validate_network_list(value):
    items = split_list(value)
    if not items:
        raise ValidationError('Enter at least one network.')
    for item in items:
        try:
            ipaddress.ip_network(item, strict=False)
        except ValueError:
            raise ValidationError('"%(item)s" is not a valid IP network.', params={'item': item})


def validate_dns_list(value):
    for item in split_list(value):
        try:
            ipaddress.ip_address(item)
        except ValueError:
            # wg-quick treats non-IP entries as DNS search domains.
            if not _HOSTNAME.match(item):
                raise ValidationError('"%(item)s" is not an IP address or domain.', params={'item': item})


def parse_interface_address(value):
    """Parse "10.0.0.1/24" into an ip_interface that is usable as a host address in a subnet."""
    try:
        iface = ipaddress.ip_interface(value.strip())
    except ValueError:
        raise ValidationError('Enter an address with prefix, e.g. 10.0.0.1/24.')
    network = iface.network
    if network.num_addresses < 4:
        raise ValidationError('Use a subnet with room for peers (e.g. /24 or /64).')
    if iface.ip == network.network_address or (iface.version == 4 and iface.ip == network.broadcast_address):
        raise ValidationError('The address cannot be the network or broadcast address.')
    return iface
