"""Device discovery module for Android Beta & QPR OTA releases."""

import argparse
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

FALLBACK_BASE_DEVICES = [
    "bluejay",
    "panther",
    "cheetah",
    "lynx",
    "felix",
    "tangorpro",
    "shiba",
    "husky",
    "akita",
    "tokay",
    "caiman",
    "komodo",
    "comet",
    "tegu",
    "frankel",
    "blazer",
    "mustang",
    "rango",
    "stallion",
    "cubs",
    "grizzly",
    "kodiak",
    "yogi",
]


class _DeviceTableParser(HTMLParser):
    """HTML parser extracting device codenames from table#images."""

    def __init__(self) -> None:
        super().__init__()
        self.in_images = False
        self.devices: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "table" and attrs_dict.get("id") == "images":
            self.in_images = True
        elif self.in_images and tag == "tr":
            row_id = attrs_dict.get("id")
            if row_id and row_id not in self.devices:
                self.devices.append(row_id)

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self.in_images:
            self.in_images = False


def extract_device_codenames(html: str) -> list[str]:
    """Parse HTML and extract device codenames from OTA images table."""
    parser = _DeviceTableParser()
    parser.feed(html)
    return parser.devices


def fetch_remote_devices(url: str, timeout: float = 15.0) -> list[str]:
    """Fetch OTA page and return discovered device codenames."""
    jar = http.cookiejar.CookieJar()
    tos_cookie = http.cookiejar.Cookie(
        version=0,
        name="devsite_wall_acks",
        value="nexus-ota-tos",
        port=None,
        port_specified=False,
        domain=".developer.android.com",
        domain_specified=True,
        domain_initial_dot=True,
        path="/",
        path_specified=True,
        secure=True,
        expires=None,
        discard=False,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )
    jar.set_cookie(tos_cookie)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
        },
    )
    try:
        with opener.open(req, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="ignore")
        devices = extract_device_codenames(html)
        if devices:
            return devices
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        print(
            f"[Warn] Failed to scrape devices dynamically ({err}). Using fallback.",
            file=sys.stderr,
        )

    return FALLBACK_BASE_DEVICES


def resolve_devices(
    state_path: Path | str, raw_devices_input: str = "all"
) -> list[str]:
    """Resolve full device tags (e.g. shiba_beta17q2) based on state and inputs."""
    state_file = Path(state_path)
    with open(state_file, "r", encoding="utf-8") as f:
        state = json.load(f)

    target = state["active_target"]
    major = target["major"]
    qpr = target.get("qpr")
    url = target.get("url")

    suffix = f"_beta{major}q{qpr}" if qpr is not None else f"_beta{major}"

    raw_cleaned = (raw_devices_input or "").strip()
    if raw_cleaned and raw_cleaned.lower() != "all":
        devices = []
        for item in raw_cleaned.split():
            clean = item.strip()
            if not clean:
                continue
            if "_beta" in clean:
                devices.append(clean)
            else:
                devices.append(f"{clean}{suffix}")
        return devices

    discovered = fetch_remote_devices(url) if url else FALLBACK_BASE_DEVICES
    return [f"{codenm}{suffix}" for codenm in discovered]


def main() -> None:
    """CLI entrypoint for dynamic device resolution."""
    parser = argparse.ArgumentParser(
        description="Resolve target Pixel OTA devices dynamically."
    )
    parser.add_argument(
        "--state-file", default="data/state.json", help="Path to state.json"
    )
    parser.add_argument(
        "--devices", default="all", help="Manual device codenames or 'all'"
    )
    args = parser.parse_args()

    result = resolve_devices(args.state_file, args.devices)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
