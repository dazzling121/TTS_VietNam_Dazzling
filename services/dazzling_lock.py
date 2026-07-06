from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


LOCK_OWNER = "Dazzling"
LOCK_BRAND = "TTS Studio"
LOCK_VERSION = 2
LOCK_ALGORITHM = "ed25519-sha256-file-manifest"
PRIVATE_KEY_PATH_HINT = "private/dazzling_private_key.pem"

PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAxvosiQMwuRUdBh6FEWn311dSErZM95xI/VFRwOKFnNg=
-----END PUBLIC KEY-----
"""


def load_public_key() -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("Dazzling lock public key is invalid.")
    return key
