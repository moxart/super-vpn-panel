"""WireGuard key handling (Curve25519), done in-process instead of shelling out to `wg`."""
import base64
import binascii
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

KEY_LENGTH = 32

_RAW = serialization.Encoding.Raw


def _encode(raw):
    return base64.b64encode(raw).decode('ascii')


def decode_key(value):
    """Return the 32 raw bytes of a base64 WireGuard key, or raise ValueError."""
    try:
        raw = base64.b64decode(value.strip(), validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('Key is not valid base64.')
    if len(raw) != KEY_LENGTH:
        raise ValueError('Key must decode to exactly 32 bytes.')
    return raw


def generate_private_key():
    private = X25519PrivateKey.generate()
    return _encode(private.private_bytes(_RAW, serialization.PrivateFormat.Raw, serialization.NoEncryption()))


def public_key_for(private_key):
    private = X25519PrivateKey.from_private_bytes(decode_key(private_key))
    return _encode(private.public_key().public_bytes(_RAW, serialization.PublicFormat.Raw))


def generate_keypair():
    private_key = generate_private_key()
    return private_key, public_key_for(private_key)


def generate_preshared_key():
    return _encode(os.urandom(KEY_LENGTH))
