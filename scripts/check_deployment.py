"""Read-only smoke check for the container or an HTTPS preview; no credentials."""
import json
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


def check(base_url):
    deadline = time.monotonic() + 60
    while True:
        try:
            with urlopen(base_url.rstrip("/") + "/health", timeout=3) as response:
                assert response.status == 200
                assert json.load(response) == {"status": "ok"}
            break
        except (URLError, TimeoutError, AssertionError):
            if time.monotonic() >= deadline:
                raise RuntimeError("Healthcheck nach 60 Sekunden nicht erfolgreich.") from None
            time.sleep(1)
    with urlopen(base_url.rstrip("/") + "/login", timeout=5) as response:
        html = response.read().decode("utf-8")
        assert response.status == 200 and 'name="csrf_token"' in html
        assert response.headers.get("Cache-Control") == "no-store"
        assert "frame-ancestors 'none'" in response.headers.get("Content-Security-Policy", "")
        assert response.headers.get("Strict-Transport-Security") == "max-age=31536000"
        cookies = response.headers.get_all("Set-Cookie") or []
        assert any(all(flag in cookie for flag in ("Secure", "HttpOnly", "SameSite=Lax")) for cookie in cookies)
    print("Health, Anmeldeseite, CSRF und Produktionsheader erfolgreich geprueft.")


if __name__ == "__main__":
    check(sys.argv[1])
