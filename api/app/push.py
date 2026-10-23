"""Web Push (browser and phone notifications), free and without a third-party account.

The server signs its messages with a VAPID key pair that it generates on first use and keeps
in the data directory (backed up with the uploads, never served).
"""

import base64
import os
from functools import cache
from pathlib import Path
from urllib.parse import urlparse

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid02

from app.config import get_settings

# The push services browsers use. Subscriptions pointing anywhere else are refused, so the
# server can never be made to send requests to arbitrary addresses.
PUSH_HOSTS = (
    "fcm.googleapis.com",  # Chrome, Edge on Android, Samsung Internet
    "push.services.mozilla.com",  # Firefox
    "push.apple.com",  # Safari on macOS and iPhone
    "notify.windows.com",  # Edge on Windows
)


def is_push_endpoint(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and len(url) <= 1024
        and any(host == h or host.endswith(f".{h}") for h in PUSH_HOSTS)
    )


def _key_file() -> Path:
    return get_settings().data_dir / "vapid_private.pem"


@cache
def _vapid(path: Path) -> Vapid02:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        key = Vapid02()
        key.generate_keys()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key.private_pem())
    return Vapid02.from_file(str(path))


def vapid() -> Vapid02:
    return _vapid(_key_file())


def public_key() -> str:
    """The key browsers need to subscribe (applicationServerKey), base64url."""
    raw = vapid().public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def claims() -> dict[str, str]:
    """VAPID contact: push services reach out to this address if something goes wrong."""
    return {"sub": get_settings().public_base_url}
