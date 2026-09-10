"""Main entry point for Android Beta & QPR OTA tracker."""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from src.client import OTAClient
from src.parser import extract_fingerprint, is_valid_ota_page
from src.state import (
    ActiveTarget,
    get_current_utc_iso,
    load_state,
    save_state_atomic,
)


@dataclass
class TrackerResult:
    """Outcome of tracker probe run."""

    has_update: bool
    release_type: str
    build_id: str
    target_version: str


def set_github_output(name: str, value: str) -> None:
    """Write output key-value pair to GITHUB_OUTPUT file if present."""
    output_file = os.getenv("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def probe_and_sync(
    state_path: Path | str,
    client: OTAClient | None = None,
) -> TrackerResult:
    """Run forward-only probing and state verification."""
    state_path = Path(state_path)
    state = load_state(state_path)
    current_target = state.active_target

    should_close = False
    if client is None:
        client = OTAClient()
        should_close = True

    try:
        # Step 1: Forward Probe (+1 Step)
        # Probe Next QPR Candidate
        next_qpr = (current_target.qpr + 1) if current_target.qpr is not None else 1
        candidate_qpr_url = (
            f"https://developer.android.com/about/versions/{current_target.major}"
            f"/qpr{next_qpr}/download-ota"
        )
        print(f"[Probe] Checking next QPR candidate: {candidate_qpr_url}")
        res_qpr = client.fetch_page(candidate_qpr_url)

        if res_qpr.status_code == 200 and is_valid_ota_page(res_qpr.text, res_qpr.url):
            print(f"[Hit] Discovered new QPR release at: {candidate_qpr_url}")
            new_fingerprint = extract_fingerprint(res_qpr.text)
            new_target = ActiveTarget(
                major=current_target.major,
                qpr=next_qpr,
                url=candidate_qpr_url,
            )
            state.active_target = new_target
            state.fingerprint = new_fingerprint
            state.last_synced_at = get_current_utc_iso()
            save_state_atomic(state, state_path)

            return TrackerResult(
                has_update=True,
                release_type="NEW_QPR",
                build_id=new_fingerprint.build_id,
                target_version=new_target.target_version,
            )

        print(
            f"[Probe] QPR candidate returned status {res_qpr.status_code} or failed DOM assertion."
        )

        # Probe Next Major Candidate
        next_major = current_target.major + 1
        candidate_major_url = (
            f"https://developer.android.com/about/versions/{next_major}/download-ota"
        )
        print(f"[Probe] Checking next Major candidate: {candidate_major_url}")
        res_major = client.fetch_page(candidate_major_url)

        if res_major.status_code == 200 and is_valid_ota_page(
            res_major.text, res_major.url
        ):
            print(f"[Hit] Discovered new Major release at: {candidate_major_url}")
            new_fingerprint = extract_fingerprint(res_major.text)
            new_target = ActiveTarget(
                major=next_major,
                qpr=None,
                url=candidate_major_url,
            )
            state.active_target = new_target
            state.fingerprint = new_fingerprint
            state.last_synced_at = get_current_utc_iso()
            save_state_atomic(state, state_path)

            return TrackerResult(
                has_update=True,
                release_type="NEW_MAJOR",
                build_id=new_fingerprint.build_id,
                target_version=new_target.target_version,
            )

        print(
            f"[Probe] Major candidate returned status {res_major.status_code} or failed DOM assertion."
        )

        # Step 2: Current State Verification
        print(f"[Probe] Verifying current active target: {current_target.url}")
        res_current = client.fetch_page(current_target.url)
        if res_current.status_code != 200 or not is_valid_ota_page(
            res_current.text, res_current.url
        ):
            print(
                f"[Warn] Current target URL returned status {res_current.status_code} "
                "or failed DOM assertion. Preserving existing state."
            )
            return TrackerResult(
                has_update=False,
                release_type="",
                build_id=state.fingerprint.build_id,
                target_version=current_target.target_version,
            )

        current_fingerprint = extract_fingerprint(res_current.text)
        if (
            current_fingerprint.build_id != state.fingerprint.build_id
            or current_fingerprint.checksum_sha256 != state.fingerprint.checksum_sha256
        ):
            print(
                f"[Hit] Minor update detected on current target: "
                f"{state.fingerprint.build_id} -> {current_fingerprint.build_id}"
            )
            state.fingerprint = current_fingerprint
            state.last_synced_at = get_current_utc_iso()
            save_state_atomic(state, state_path)

            return TrackerResult(
                has_update=True,
                release_type="MINOR_UPDATE",
                build_id=current_fingerprint.build_id,
                target_version=current_target.target_version,
            )

        print(f"[Check] State is up to date: {state.fingerprint.build_id}")
        return TrackerResult(
            has_update=False,
            release_type="",
            build_id=state.fingerprint.build_id,
            target_version=current_target.target_version,
        )

    finally:
        if should_close:
            client.close()


def main() -> None:
    """CLI entry point for OTA Tracker."""
    parser = argparse.ArgumentParser(description="Android Beta & QPR OTA Tracker")
    parser.add_argument(
        "--state-file",
        default="data/state.json",
        help="Path to state.json file (default: data/state.json)",
    )
    args = parser.parse_args()

    state_path = Path(args.state_file)
    if not state_path.is_file():
        print(f"Error: state file does not exist at {state_path}", file=sys.stderr)
        sys.exit(1)

    result = probe_and_sync(state_path)

    # Export outputs for GitHub Actions
    set_github_output("has_update", "true" if result.has_update else "false")
    set_github_output("build_id", result.build_id)
    set_github_output("release_type", result.release_type)
    set_github_output("target_version", result.target_version)

    print("\n=== Tracker Summary ===")
    print(f"has_update:     {'true' if result.has_update else 'false'}")
    print(f"release_type:   {result.release_type or '(none)'}")
    print(f"target_version: {result.target_version}")
    print(f"build_id:       {result.build_id}")


if __name__ == "__main__":
    main()
