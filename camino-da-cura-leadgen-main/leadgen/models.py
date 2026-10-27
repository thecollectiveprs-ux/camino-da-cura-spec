from dataclasses import dataclass
from urllib.parse import urlsplit
import ipaddress

@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    description: str = ""

def canonical_domain(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Expected a public HTTP(S) business URL")
    host = parsed.hostname.lower().rstrip(".").encode("idna").decode("ascii")
    if host.startswith("www."):
        host = host[4:]
    if "." not in host or host.endswith((".local", ".localhost")):
        raise ValueError("Invalid public domain")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    raise ValueError("IP addresses are not business domains")
