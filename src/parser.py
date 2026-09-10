"""HTML parser and DOM assertion logic for Android OTA pages."""

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.state import Fingerprint

# Android Build ID pattern (e.g., AP2A.240805.005, CP41.260814.003.A2, BP31.250610.009)
BUILD_ID_PATTERN = r"\b[A-Z0-9]{4}\.[0-9]{6}\.[0-9]{3}(?:\.[A-Z0-9]{1,4})?\b"
BUILD_ID_REGEX = re.compile(BUILD_ID_PATTERN, re.IGNORECASE)

# SHA-256 Checksum pattern (64 hex characters)
SHA256_PATTERN = r"\b[a-f0-9]{64}\b"
SHA256_REGEX = re.compile(SHA256_PATTERN, re.IGNORECASE)

# Date patterns for security patch fallback
DATE_ISO_REGEX = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
DATE_MONTH_YEAR_REGEX = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
    re.IGNORECASE,
)


def is_valid_ota_page(html: str, final_url: str) -> bool:
    """Validate that the fetched page is an authentic Pixel Beta OTA download page.

    Protects against soft-404s, generic landing pages, or redirects to stable OTA.
    """
    if not html or not final_url:
        return False

    parsed = urlparse(final_url)
    # Must remain on developer.android.com under /about/versions/
    if parsed.netloc != "developer.android.com":
        return False
    if not parsed.path.startswith("/about/versions/"):
        return False

    soup = BeautifulSoup(html, "html.parser")

    # 1. Header & text check: Must mention Pixel
    text = soup.get_text(separator=" ", strip=True)
    if "pixel" not in text.lower():
        return False

    # 2. Device table / images table presence
    has_images_table = soup.find("table", id="images") is not None
    has_device_table = any(
        any(
            "device" in c.get_text(strip=True).lower()
            for c in tr.find_all(["th", "td"])
        )
        for tr in soup.find_all("tr")
    )
    if not (has_images_table or has_device_table):
        return False

    # 3. Android Build ID pattern match
    if not BUILD_ID_REGEX.search(text):
        return False

    # 4. SHA-256 Checksum (64 hex chars) pattern match
    return bool(SHA256_REGEX.search(text))


def extract_fingerprint(html: str) -> Fingerprint:
    """Extract the latest Build ID, Security Patch level, and SHA-256 checksum."""
    soup = BeautifulSoup(html, "html.parser")

    # 1. Extract Build ID
    build_id: str | None = None
    for tr in soup.find_all("tr"):
        cells = [
            c.get_text(separator=" ", strip=True) for c in tr.find_all(["td", "th"])
        ]
        if len(cells) >= 2 and any(
            label in cells[0].lower() for label in ["build", "builds"]
        ):
            match = BUILD_ID_REGEX.search(cells[1])
            if match:
                build_id = match.group(0).upper()
                break

    if not build_id:
        images_table = soup.find("table", id="images")
        if images_table:
            match = BUILD_ID_REGEX.search(
                images_table.get_text(separator=" ", strip=True)
            )
            if match:
                build_id = match.group(0).upper()

    if not build_id:
        match = BUILD_ID_REGEX.search(soup.get_text(separator=" ", strip=True))
        if match:
            build_id = match.group(0).upper()

    if not build_id:
        raise ValueError("Could not extract Build ID from OTA page.")

    # 2. Extract Security Patch level
    security_patch: str | None = None
    for tr in soup.find_all("tr"):
        cells = [
            c.get_text(separator=" ", strip=True) for c in tr.find_all(["td", "th"])
        ]
        if len(cells) >= 2 and any(
            label in cells[0].lower() for label in ["security patch", "patch level"]
        ):
            security_patch = cells[1]
            break

    if not security_patch:
        text = soup.get_text(separator=" ", strip=True)
        date_iso = DATE_ISO_REGEX.search(text)
        if date_iso:
            security_patch = date_iso.group(0)
        else:
            date_my = DATE_MONTH_YEAR_REGEX.search(text)
            if date_my:
                security_patch = date_my.group(0)

    if not security_patch:
        security_patch = "Unknown"

    # 3. Extract SHA-256 checksum
    checksum_sha256: str | None = None
    images_table = soup.find("table", id="images")
    if images_table:
        for code_elem in images_table.find_all("code"):
            code_text = code_elem.get_text(strip=True)
            if SHA256_REGEX.fullmatch(code_text):
                checksum_sha256 = code_text.lower()
                break

    if not checksum_sha256:
        match = SHA256_REGEX.search(soup.get_text(separator=" ", strip=True))
        if match:
            checksum_sha256 = match.group(0).lower()

    if not checksum_sha256:
        raise ValueError("Could not extract SHA-256 checksum from OTA page.")

    return Fingerprint(
        build_id=build_id,
        security_patch=security_patch,
        checksum_sha256=checksum_sha256,
    )
