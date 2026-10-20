"""HTTPS-only, allowlisted transport with public-IP pinning at connection time."""
import http.client
import ipaddress
import socket
import ssl
import urllib.request
from urllib.parse import urlsplit

from .youtube_service import IngestionError


ALLOWED_DOMAINS = ("youtube.com", "youtu.be", "googlevideo.com", "ytimg.com",
                   "youtubei.googleapis.com", "youtube-nocookie.com")


def validate_network_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if (parsed.scheme != "https" or parsed.port not in (None, 443)
                or parsed.username is not None or parsed.password is not None
                or any(c.isspace() or ord(c) < 32 for c in url)
                or "\\" in url or not any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)):
            raise ValueError("blocked destination")
    except ValueError as exc:
        raise IngestionError("unsafe_destination", "The source requested a blocked network destination.") from exc
    return host


def public_addresses(host: str, port: int):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    def is_public(address):
        ip = ipaddress.ip_address(address)
        return ip.is_global and not (ip.is_multicast or ip.is_reserved or ip.is_unspecified)
    if not addresses or any(not is_public(item[4][0]) for item in addresses):
        raise IngestionError("unsafe_destination", "The source resolved to a non-public network address.")
    return addresses


class PublicHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        validate_network_url(f"https://{self.host}:{self.port}/")
        last_error = None
        for family, socktype, proto, _, address in public_addresses(self.host, self.port):
            connection = socket.socket(family, socktype, proto)
            connection.settimeout(self.timeout)
            try:
                # Connect to this exact validated address: no second DNS resolution.
                connection.connect(address)
                self.sock = self._context.wrap_socket(connection, server_hostname=self.host)
                return
            except OSError as exc:
                connection.close()
                last_error = exc
        raise last_error or OSError("No public address available")


class PublicHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, request):
        validate_network_url(request.full_url)
        return self.do_open(PublicHTTPSConnection, request, context=ssl.create_default_context())


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        validate_network_url(new_url)
        return super().redirect_request(request, response, code, message, headers, new_url)


def build_public_opener(cookiejar):
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}), PublicHTTPSHandler(), SafeRedirectHandler(),
        urllib.request.HTTPCookieProcessor(cookiejar),
    )
