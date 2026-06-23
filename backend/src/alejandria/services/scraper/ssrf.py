"""SSRF protection for the web scraper.

Blocks all schemes except http(s), and all destinations that resolve to
private / loopback / link-local / CGNAT / IPv6 ULA addresses. The blocklist
is exhaustive; we deliberately do NOT add public-domain allowlists because
the scraper is meant to handle arbitrary user-supplied book sites.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

# Precomputed network blocks we will never contact.
_BLOCKED_IPV4_NETWORKS: list[ipaddress.IPv4Network] = [
    ipaddress.IPv4Network("0.0.0.0/8"),  # current network
    ipaddress.IPv4Network("10.0.0.0/8"),  # private
    ipaddress.IPv4Network("100.64.0.0/10"),  # CGNAT
    ipaddress.IPv4Network("127.0.0.0/8"),  # loopback
    ipaddress.IPv4Network("169.254.0.0/16"),  # link-local (AWS metadata)
    ipaddress.IPv4Network("172.16.0.0/12"),  # private
    ipaddress.IPv4Network("192.0.0.0/24"),  # IETF protocol assignments
    ipaddress.IPv4Network("192.0.2.0/24"),  # TEST-NET-1
    ipaddress.IPv4Network("192.88.99.0/24"),  # 6to4 anycast
    ipaddress.IPv4Network("192.168.0.0/16"),  # private
    ipaddress.IPv4Network("198.18.0.0/15"),  # benchmarking
    ipaddress.IPv4Network("198.51.100.0/24"),  # TEST-NET-2
    ipaddress.IPv4Network("203.0.113.0/24"),  # TEST-NET-3
    ipaddress.IPv4Network("224.0.0.0/4"),  # multicast
    ipaddress.IPv4Network("240.0.0.0/4"),  # reserved
    ipaddress.IPv4Network("255.255.255.255/32"),  # broadcast
]

_BLOCKED_IPV6_NETWORKS: list[ipaddress.IPv6Network] = [
    ipaddress.IPv6Network("::1/128"),  # loopback
    ipaddress.IPv6Network("::/128"),  # unspecified
    ipaddress.IPv6Network("::ffff:127.0.0.0/104"),  # IPv4-mapped loopback
    ipaddress.IPv6Network("::ffff:10.0.0.0/104"),  # IPv4-mapped private
    ipaddress.IPv6Network("::ffff:172.16.0.0/108"),  # IPv4-mapped private
    ipaddress.IPv6Network("::ffff:192.168.0.0/112"),  # IPv4-mapped private
    ipaddress.IPv6Network("64:ff9b::/96"),  # IPv4-IPv6 translation
    ipaddress.IPv6Network("100::/64"),  # discard
    ipaddress.IPv6Network("2001::/32"),  # Teredo
    ipaddress.IPv6Network("2001:db8::/32"),  # documentation
    ipaddress.IPv6Network("fc00::/7"),  # ULA
    ipaddress.IPv6Network("fe80::/10"),  # link-local
    ipaddress.IPv6Network("ff00::/8"),  # multicast
]

_ALLOWED_SCHEMES = {"http", "https"}


def _ip_is_blocked(ip: ipaddress._BaseAddress) -> bool:
    """Return True if `ip` is in any blocked network."""
    if isinstance(ip, ipaddress.IPv4Address):
        nets: list[ipaddress._BaseNetwork] = list(_BLOCKED_IPV4_NETWORKS)
    else:
        nets = list(_BLOCKED_IPV6_NETWORKS)
    for net in nets:
        if ip.version != net.version:
            continue
        if ip in net:
            return True
    return False


def validate_url(url: str, *, allow_loopback: bool = False) -> str:
    """Validate a URL against the SSRF blocklist.

    Returns the canonical URL (scheme + lowercased host + path) on success.
    Raises ``ValueError`` with a user-friendly message on rejection.

    Args:
        url: The user-supplied URL.
        allow_loopback: When True (used by tests that spin up a local
            aiohttp fixture on 127.0.0.1), 127.0.0.0/8 and ::1 are
            permitted. All other private/loopback/link-local/CGNAT/etc.
            ranges remain blocked. Production code MUST keep this False.
    """
    if not url:
        raise ValueError("URL is empty")

    try:
        parts = urlsplit(url.strip())
    except Exception as e:
        raise ValueError(f"Invalid URL: {e}") from e

    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"URL scheme '{parts.scheme or '(empty)'}' is not allowed; "
            f"only http(s) is permitted"
        )

    host = (parts.hostname or "").strip()
    if not host:
        raise ValueError("URL has no host")

    def _is_loopback(ip_obj: ipaddress._BaseAddress) -> bool:
        return (
            isinstance(ip_obj, ipaddress.IPv4Address)
            and ip_obj in ipaddress.IPv4Network("127.0.0.0/8")
        ) or (
            isinstance(ip_obj, ipaddress.IPv6Address)
            and ip_obj in ipaddress.IPv6Network("::1/128")
        )

    # If the host is already an IP literal, we can evaluate it directly
    # without DNS resolution.
    try:
        ip = ipaddress.ip_address(host)
        # When allow_loopback is True, only loopback is exempt; all other
        # private ranges still block.
        if _ip_is_blocked(ip) and not (allow_loopback and _is_loopback(ip)):
            raise ValueError("URL targets a private or loopback address")
    except ValueError as e:
        msg = str(e)
        if "private or loopback" in msg:
            raise
        # Not an IP literal — fall through to DNS resolution.
        ip = None

    if ip is None:
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror as e:
            raise ValueError(f"Could not resolve host '{host}': {e}") from e
        for info in infos:
            sockaddr = info[4]
            addr_str = sockaddr[0]
            try:
                resolved = ipaddress.ip_address(addr_str)
            except ValueError:
                continue
            if _ip_is_blocked(resolved) and not (allow_loopback and _is_loopback(resolved)):
                raise ValueError(
                    f"URL resolves to a blocked address ({resolved})"
                )

    canonical = f"{parts.scheme.lower()}://{host.lower()}"
    if parts.port is not None:
        canonical += f":{parts.port}"
    canonical += parts.path or ""
    if parts.query:
        canonical += f"?{parts.query}"
    if parts.fragment:
        canonical += f"#{parts.fragment}"
    return canonical
