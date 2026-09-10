"""Unit and integration tests for Android Beta & QPR OTA Tracker."""

from pathlib import Path

from src.client import FetchResult, OTAClient
from src.devices import extract_device_codenames, resolve_devices
from src.main import probe_and_sync
from src.parser import (
    extract_fingerprint,
    is_valid_ota_page,
)
from src.state import (
    ActiveTarget,
    Fingerprint,
    TrackerState,
    load_state,
    save_state_atomic,
)

SAMPLE_VALID_OTA_HTML = """
<!doctype html>
<html>
<head><title>OTA images for Google Pixel</title></head>
<body>
<table class="responsive fixed">
  <tbody>
    <tr>
      <td><b>Release date</b></td>
      <td>August 28, 2026</td>
    </tr>
    <tr>
      <td><b>Builds</b></td>
      <td>CP41.260814.003.A2<br />CP41.260814.003.B1</td>
    </tr>
    <tr>
      <td><b>Security patch level</b></td>
      <td>2026-08-05</td>
    </tr>
  </tbody>
</table>
<table id="images">
  <tr>
    <th>Device</th>
    <th>Download Link and SHA-256 Checksum</th>
  </tr>
  <tr id="bluejay">
    <td>Pixel 6a</td>
    <td>
      <button>bluejay_beta-ota-cp41.260814.003.a2-db418a46.zip</button>
      <br /><code>db418a461245d61e0e9472e0c732b2f706fddc9758eda62aca562608c577cb2e</code>
    </td>
  </tr>
</table>
</body>
</html>
"""

SAMPLE_UPDATED_OTA_HTML = """
<!doctype html>
<html>
<head><title>OTA images for Google Pixel</title></head>
<body>
<table class="responsive fixed">
  <tbody>
    <tr>
      <td><b>Release date</b></td>
      <td>September 05, 2026</td>
    </tr>
    <tr>
      <td><b>Builds</b></td>
      <td>CP41.260901.001.A1</td>
    </tr>
    <tr>
      <td><b>Security patch level</b></td>
      <td>2026-09-05</td>
    </tr>
  </tbody>
</table>
<table id="images">
  <tr>
    <th>Device</th>
    <th>Download Link and SHA-256 Checksum</th>
  </tr>
  <tr id="bluejay">
    <td>Pixel 6a</td>
    <td>
      <button>bluejay_beta-ota-cp41.260901.001.a1-11112222.zip</button>
      <br /><code>1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff</code>
    </td>
  </tr>
</table>
</body>
</html>
"""

SAMPLE_QPR3_OTA_HTML = """
<!doctype html>
<html>
<head><title>OTA images for Google Pixel</title></head>
<body>
<table class="responsive fixed">
  <tbody>
    <tr>
      <td><b>Release date</b></td>
      <td>November 15, 2026</td>
    </tr>
    <tr>
      <td><b>Builds</b></td>
      <td>CP42.261101.002.A1</td>
    </tr>
    <tr>
      <td><b>Security patch level</b></td>
      <td>2026-11-05</td>
    </tr>
  </tbody>
</table>
<table id="images">
  <tr>
    <th>Device</th>
    <th>Download Link and SHA-256 Checksum</th>
  </tr>
  <tr id="bluejay">
    <td>Pixel 6a</td>
    <td>
      <button>bluejay_beta-ota-cp42.261101.002.a1-aabbccdd.zip</button>
      <br /><code>aabbccdd11223344556677889900aabbccdd11223344556677889900aabbccdd</code>
    </td>
  </tr>
</table>
</body>
</html>
"""

SAMPLE_MAJOR18_OTA_HTML = """
<!doctype html>
<html>
<head><title>OTA images for Google Pixel</title></head>
<body>
<table class="responsive fixed">
  <tbody>
    <tr>
      <td><b>Release date</b></td>
      <td>February 10, 2027</td>
    </tr>
    <tr>
      <td><b>Builds</b></td>
      <td>DP1A.270110.001</td>
    </tr>
    <tr>
      <td><b>Security patch level</b></td>
      <td>2027-02-05</td>
    </tr>
  </tbody>
</table>
<table id="images">
  <tr>
    <th>Device</th>
    <th>Download Link and SHA-256 Checksum</th>
  </tr>
  <tr id="shiba">
    <td>Pixel 8</td>
    <td>
      <button>shiba_beta-ota-dp1a.270110.001-ffff0000.zip</button>
      <br /><code>ffff00001111222233334444555566667777888899990000aaaabbbbccccdddd</code>
    </td>
  </tr>
</table>
</body>
</html>
"""


class MockOTAClient(OTAClient):
    """Mock client returning preconfigured responses for URLs."""

    def __init__(self, routes: dict[str, FetchResult]) -> None:
        self.routes = routes

    def fetch_page(self, url: str) -> FetchResult:
        if url in self.routes:
            return self.routes[url]
        return FetchResult(status_code=404, url=url, text="404 Not Found")

    def close(self) -> None:
        pass


def test_state_load_and_atomic_save(tmp_path: Path) -> None:
    state_file = tmp_path / "data" / "state.json"
    initial_state = TrackerState(
        last_synced_at="2026-09-10T12:00:00Z",
        active_target=ActiveTarget(
            major=17,
            qpr=2,
            url="https://developer.android.com/about/versions/17/qpr2/download-ota",
        ),
        fingerprint=Fingerprint(
            build_id="CP41.260814.003.A2",
            security_patch="2026-08-05",
            checksum_sha256="db418a461245d61e0e9472e0c732b2f706fddc9758eda62aca562608c577cb2e",
        ),
    )

    save_state_atomic(initial_state, state_file)
    assert state_file.is_file()

    loaded = load_state(state_file)
    assert loaded.schema_version == "1.0.0"
    assert loaded.active_target.major == 17
    assert loaded.active_target.qpr == 2
    assert loaded.active_target.target_version == "Android 17 QPR2"
    assert loaded.fingerprint.build_id == "CP41.260814.003.A2"


def test_dom_assertion_valid_page() -> None:
    url = "https://developer.android.com/about/versions/17/qpr2/download-ota"
    assert is_valid_ota_page(SAMPLE_VALID_OTA_HTML, url) is True


def test_dom_assertion_soft_404_redirect() -> None:
    # Google redirects old preview URLs to developers.google.com/android/ota
    redirected_url = "https://developers.google.com/android/ota"
    assert is_valid_ota_page(SAMPLE_VALID_OTA_HTML, redirected_url) is False


def test_dom_assertion_missing_pixel() -> None:
    html = "<html><body>Generic Android Documentation</body></html>"
    url = "https://developer.android.com/about/versions/17/download-ota"
    assert is_valid_ota_page(html, url) is False


def test_dom_assertion_missing_build_id() -> None:
    html = "<html><body>Google Pixel devices without builds table</body></html>"
    url = "https://developer.android.com/about/versions/17/download-ota"
    assert is_valid_ota_page(html, url) is False


def test_extract_fingerprint() -> None:
    fp = extract_fingerprint(SAMPLE_VALID_OTA_HTML)
    assert fp.build_id == "CP41.260814.003.A2"
    assert fp.security_patch == "2026-08-05"
    assert (
        fp.checksum_sha256
        == "db418a461245d61e0e9472e0c732b2f706fddc9758eda62aca562608c577cb2e"
    )


def test_probe_no_update(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state = TrackerState(
        last_synced_at="2026-09-10T12:00:00Z",
        active_target=ActiveTarget(
            major=17,
            qpr=2,
            url="https://developer.android.com/about/versions/17/qpr2/download-ota",
        ),
        fingerprint=Fingerprint(
            build_id="CP41.260814.003.A2",
            security_patch="2026-08-05",
            checksum_sha256="db418a461245d61e0e9472e0c732b2f706fddc9758eda62aca562608c577cb2e",
        ),
    )
    save_state_atomic(state, state_file)

    mock_client = MockOTAClient(
        {
            "https://developer.android.com/about/versions/17/qpr3/download-ota": FetchResult(
                status_code=404,
                url="https://developer.android.com/about/versions/17/qpr3/download-ota",
                text="Not found",
            ),
            "https://developer.android.com/about/versions/18/download-ota": FetchResult(
                status_code=404,
                url="https://developer.android.com/about/versions/18/download-ota",
                text="Not found",
            ),
            "https://developer.android.com/about/versions/17/qpr2/download-ota": FetchResult(
                status_code=200,
                url="https://developer.android.com/about/versions/17/qpr2/download-ota",
                text=SAMPLE_VALID_OTA_HTML,
            ),
        }
    )

    result = probe_and_sync(state_file, client=mock_client)
    assert result.has_update is False
    assert result.release_type == ""
    assert result.build_id == "CP41.260814.003.A2"


def test_probe_minor_update(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state = TrackerState(
        last_synced_at="2026-09-10T12:00:00Z",
        active_target=ActiveTarget(
            major=17,
            qpr=2,
            url="https://developer.android.com/about/versions/17/qpr2/download-ota",
        ),
        fingerprint=Fingerprint(
            build_id="CP41.260814.003.A2",
            security_patch="2026-08-05",
            checksum_sha256="db418a461245d61e0e9472e0c732b2f706fddc9758eda62aca562608c577cb2e",
        ),
    )
    save_state_atomic(state, state_file)

    mock_client = MockOTAClient(
        {
            "https://developer.android.com/about/versions/17/qpr3/download-ota": FetchResult(
                status_code=404,
                url="https://developer.android.com/about/versions/17/qpr3/download-ota",
                text="Not found",
            ),
            "https://developer.android.com/about/versions/18/download-ota": FetchResult(
                status_code=404,
                url="https://developer.android.com/about/versions/18/download-ota",
                text="Not found",
            ),
            "https://developer.android.com/about/versions/17/qpr2/download-ota": FetchResult(
                status_code=200,
                url="https://developer.android.com/about/versions/17/qpr2/download-ota",
                text=SAMPLE_UPDATED_OTA_HTML,
            ),
        }
    )

    result = probe_and_sync(state_file, client=mock_client)
    assert result.has_update is True
    assert result.release_type == "MINOR_UPDATE"
    assert result.build_id == "CP41.260901.001.A1"

    updated_state = load_state(state_file)
    assert updated_state.fingerprint.build_id == "CP41.260901.001.A1"
    assert updated_state.fingerprint.security_patch == "2026-09-05"


def test_probe_new_qpr(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state = TrackerState(
        last_synced_at="2026-09-10T12:00:00Z",
        active_target=ActiveTarget(
            major=17,
            qpr=2,
            url="https://developer.android.com/about/versions/17/qpr2/download-ota",
        ),
        fingerprint=Fingerprint(
            build_id="CP41.260814.003.A2",
            security_patch="2026-08-05",
            checksum_sha256="db418a461245d61e0e9472e0c732b2f706fddc9758eda62aca562608c577cb2e",
        ),
    )
    save_state_atomic(state, state_file)

    mock_client = MockOTAClient(
        {
            "https://developer.android.com/about/versions/17/qpr3/download-ota": FetchResult(
                status_code=200,
                url="https://developer.android.com/about/versions/17/qpr3/download-ota",
                text=SAMPLE_QPR3_OTA_HTML,
            ),
        }
    )

    result = probe_and_sync(state_file, client=mock_client)
    assert result.has_update is True
    assert result.release_type == "NEW_QPR"
    assert result.build_id == "CP42.261101.002.A1"
    assert result.target_version == "Android 17 QPR3"

    updated_state = load_state(state_file)
    assert updated_state.active_target.qpr == 3
    assert (
        updated_state.active_target.url
        == "https://developer.android.com/about/versions/17/qpr3/download-ota"
    )
    assert updated_state.fingerprint.build_id == "CP42.261101.002.A1"


def test_probe_new_major(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state = TrackerState(
        last_synced_at="2026-09-10T12:00:00Z",
        active_target=ActiveTarget(
            major=17,
            qpr=2,
            url="https://developer.android.com/about/versions/17/qpr2/download-ota",
        ),
        fingerprint=Fingerprint(
            build_id="CP41.260814.003.A2",
            security_patch="2026-08-05",
            checksum_sha256="db418a461245d61e0e9472e0c732b2f706fddc9758eda62aca562608c577cb2e",
        ),
    )
    save_state_atomic(state, state_file)

    mock_client = MockOTAClient(
        {
            "https://developer.android.com/about/versions/17/qpr3/download-ota": FetchResult(
                status_code=404,
                url="https://developer.android.com/about/versions/17/qpr3/download-ota",
                text="Not found",
            ),
            "https://developer.android.com/about/versions/18/download-ota": FetchResult(
                status_code=200,
                url="https://developer.android.com/about/versions/18/download-ota",
                text=SAMPLE_MAJOR18_OTA_HTML,
            ),
        }
    )

    result = probe_and_sync(state_file, client=mock_client)
    assert result.has_update is True
    assert result.release_type == "NEW_MAJOR"
    assert result.build_id == "DP1A.270110.001"
    assert result.target_version == "Android 18 Beta"

    updated_state = load_state(state_file)
    assert updated_state.active_target.major == 18
    assert updated_state.active_target.qpr is None
    assert (
        updated_state.active_target.url
        == "https://developer.android.com/about/versions/18/download-ota"
    )
    assert updated_state.fingerprint.build_id == "DP1A.270110.001"


def test_extract_device_codenames() -> None:
    devices = extract_device_codenames(SAMPLE_VALID_OTA_HTML)
    assert devices == ["bluejay"]


def test_resolve_devices_custom_input(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state = TrackerState(
        last_synced_at="2026-09-10T12:00:00Z",
        active_target=ActiveTarget(
            major=17,
            qpr=2,
            url="https://developer.android.com/about/versions/17/qpr2/download-ota",
        ),
        fingerprint=Fingerprint(
            build_id="CP41.260814.003.A2",
            security_patch="2026-08-05",
            checksum_sha256="db418a461245d61e0e9472e0c732b2f706fddc9758eda62aca562608c577cb2e",
        ),
    )
    save_state_atomic(state, state_file)

    devices = resolve_devices(state_file, "shiba husky akita_beta17q2")
    assert devices == ["shiba_beta17q2", "husky_beta17q2", "akita_beta17q2"]


def test_resolve_devices_major_version(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state = TrackerState(
        last_synced_at="2026-09-10T12:00:00Z",
        active_target=ActiveTarget(
            major=18,
            qpr=None,
            url="https://developer.android.com/about/versions/18/download-ota",
        ),
        fingerprint=Fingerprint(
            build_id="DP1A.270110.001",
            security_patch="2027-02-05",
            checksum_sha256="ffff00001111222233334444555566667777888899990000aaaabbbbccccdddd",
        ),
    )
    save_state_atomic(state, state_file)

    devices = resolve_devices(state_file, "shiba")
    assert devices == ["shiba_beta18"]


def test_resolve_devices_all_with_mock(monkeypatch, tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state = TrackerState(
        last_synced_at="2026-09-10T12:00:00Z",
        active_target=ActiveTarget(
            major=17,
            qpr=2,
            url="https://developer.android.com/about/versions/17/qpr2/download-ota",
        ),
        fingerprint=Fingerprint(
            build_id="CP41.260814.003.A2",
            security_patch="2026-08-05",
            checksum_sha256="db418a461245d61e0e9472e0c732b2f706fddc9758eda62aca562608c577cb2e",
        ),
    )
    save_state_atomic(state, state_file)

    monkeypatch.setattr(
        "src.devices.fetch_remote_devices",
        lambda url: ["shiba", "husky", "bluejay"],
    )

    devices = resolve_devices(state_file, "all")
    assert devices == ["shiba_beta17q2", "husky_beta17q2", "bluejay_beta17q2"]
