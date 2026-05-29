"""SSRF guard for user-supplied URLs (URL capture).

Captured URLs are fetched by n8n from *inside* the Docker network, so without
a guard an attacker could point Mnemo at internal services (``http://postgres``,
``http://qdrant:6333``) or the cloud metadata endpoint
(``http://169.254.169.254``) and exfiltrate the response. We resolve the host
and reject any URL that targets a private/loopback/link-local/reserved address
or a known internal hostname, at the API edge before a note is created.

This cannot fully close a DNS-rebinding (TOCTOU) gap against the later fetch,
but it blocks the overwhelming majority of SSRF attempts and all the static
internal targets.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

from mnemo_api.exceptions import ValidationError

# Docker-compose service names + obvious internal aliases.
_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "api",
        "bot",
        "workers",
        "dispatcher",
        "scheduler",
        "webapp",
        "caddy",
        "n8n",
        "postgres",
        "redis",
        "qdrant",
        "minio",
    }
)

_IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def _is_blocked_ip(ip: _IPAddress) -> bool:
    # Unwrap IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) so the v4 checks apply.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local  # 169.254.0.0/16 incl. the 169.254.169.254 metadata IP
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


async def assert_public_url(url: str) -> None:
    """Raise ``ValidationError`` (HTTP 422) unless ``url`` targets a public host."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValidationError(f"Only http(s) URLs are allowed (got scheme {parts.scheme!r}).")
    host = parts.hostname
    if not host:
        raise ValidationError("URL has no host.")
    if host.lower() in _BLOCKED_HOSTNAMES:
        raise ValidationError("URL points at an internal host.")

    # Literal IP — check directly, no DNS needed.
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if _is_blocked_ip(literal):
            raise ValidationError("URL points at a private or reserved address.")
        return

    # Resolve and check every address the host maps to.
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None, 0, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValidationError(f"Could not resolve host {host!r}.") from exc

    for info in infos:
        raw = str(info[4][0]).split("%", 1)[0]  # drop any IPv6 zone id
        try:
            resolved = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if _is_blocked_ip(resolved):
            raise ValidationError("URL resolves to a private or reserved address.")
