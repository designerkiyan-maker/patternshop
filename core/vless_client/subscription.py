import base64
import ipaddress
import json
import urllib.request
from urllib.parse import urlparse, parse_qs, unquote


def _is_safe_url(url: str) -> bool:
    """بررسی میکند که URL به آدرسهای داخلی/خصوصی اشاره نکند (ضد SSRF)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        # نام مستعار؛ باید resolve شود — برای سادگی فقط IPهای شناختهشده بلاک می‌شوند
        pass
    else:
        if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local:
            return False
    # بلاک کردن نامهای مستعار رایج
    blocked_hosts = {"localhost", "metadata.google.internal", "metadata.aws.internal"}
    if hostname.lower() in blocked_hosts:
        return False
    return True


def fetch_subscription(url: str, timeout: int = 30) -> str:
    if not _is_safe_url(url):
        raise ValueError("URL مجاز نیست. آدرسهای داخلی و خصوصی مسدود هستند.")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Patternshop-VLESS-Manager/1.0",
            "Accept": "*/*",
        },
    )

    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read()

    text = data.decode("utf-8", "ignore").strip()

    # Raw VLESS list
    if "vless://" in text.lower():
        return text

    # Base64 encoded subscription
    try:
        decoded = base64.b64decode(
            text + "=" * (-len(text) % 4)
        ).decode("utf-8", "ignore")

        if "vless://" in decoded.lower():
            return decoded
    except Exception:
        pass

    raise ValueError("Subscription format is not a valid VLESS/Base64 subscription")


def parse_vless(uri: str) -> dict:
    uri = uri.strip()

    if not uri.lower().startswith("vless://"):
        raise ValueError("Not a VLESS URI")

    parsed = urlparse(uri)

    if not parsed.hostname or not parsed.port:
        raise ValueError("VLESS URI has no host/port")

    query = parse_qs(parsed.query)

    def q(name, default=None):
        value = query.get(name)
        return unquote(value[0]) if value else default

    node = {
        "uri": uri,
        "uuid": parsed.username,
        "host": parsed.hostname,
        "port": parsed.port,
        "name": unquote(parsed.fragment) if parsed.fragment else "",
        "encryption": q("encryption", "none"),
        "network": q("type", "tcp"),
        "security": q("security", "none"),
        "sni": q("sni"),
        "host_header": q("host"),
        "path": q("path"),
        "service_name": q("serviceName"),
        "public_key": q("pbk") or q("publicKey"),
        "short_id": q("sid") or q("shortId"),
        "flow": q("flow"),
        "fp": q("fp"),
    }

    return node


def parse_subscription(text: str) -> list[dict]:
    result = []

    for line in text.splitlines():
        line = line.strip()

        if not line.lower().startswith("vless://"):
            continue

        try:
            result.append(parse_vless(line))
        except Exception:
            continue

    return result


def load_subscription(url: str) -> list[dict]:
    text = fetch_subscription(url)
    return parse_subscription(text)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python3 subscription.py <subscription-url>")
        raise SystemExit(1)

    nodes = load_subscription(sys.argv[1])

    print(json.dumps({
        "count": len(nodes),
        "nodes": nodes,
    }, ensure_ascii=False, indent=2))
