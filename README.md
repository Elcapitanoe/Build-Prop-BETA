# Build Prop BETA Builder

Automated toolchain to fetch, extract, and build Magisk/KernelSU/APatch modules containing system properties from Google Pixel Beta and QPR OTA images.

## Architecture & Pipeline

```
[OTA Tracker] -> [OTA Acquisition] -> [Image Extraction] -> [Property Synthesis] -> [Module Packaging] -> [CI & Release]
```

### 1. OTA Acquisition (`download_latest_ota_build.sh`, `src/devices.py`)
- Target argument resolution:
  - Standard builds: `<codename>` (queries `developers.google.com/android/ota`)
  - Beta main builds: `<codename>_beta<version>` (queries `developer.android.com/about/versions/<version>/download-ota`)
  - Beta QPR builds: `<codename>_beta<version>q<qpr>` (queries `developer.android.com/about/versions/<version>/qpr<qpr>/download-ota`)
  - Beta latest alias: `<codename>_beta` (queries highest available version number from developer endpoint)
  - Target discovery (`all`): scraped via `src.devices` against Google OTA tables, covering Pixel phones and Pixel Watch models
- Queries Google Developer endpoints with required session cookies.
- Parallel download engine using `aria2c` with multi-connection chunks into `./dl/`.

### 2. Image Extraction (`extract_images.sh`, `util_functions.sh`)
- Processes payload archives (`payload.bin` from OTA zip or raw factory zip).
- Target partitions: `product`, `vendor`, `vendor_dlkm`, `system`, `system_ext`, `system_dlkm`, `init_boot`.
- Partition extraction via `payload_dumper` (`5ec1cff/payload-dumper`) supporting concurrent multithreaded partition dumping or direct module execution via `python3 -m payload_dumper`.
- Filesystem detection and unpacking:
  - **EROFS**: extracted via `fsck.erofs --extract`
  - **ext4**: extracted via `7z` (single-threaded mode)
  - **Android Sparse**: decompressed to raw image via `simg2img` prior to extraction
  - **Boot / Ramdisk (`init_boot`, `boot`)**: unpacked via `unpack_bootimg.py`, decompressed using `lz4`, `gzip`, or `cpio`
- Traverses extracted partitions to locate all `build.prop` files.

### 3. Property Synthesis (`build_props.sh`, `build_sysconfig.sh`)
- Parses property keys from extracted files and builds target outputs:
  - `system.prop`: spoofed fingerprints, build IDs, incremental versions, security patch levels, and UUID properties across all partitions.
  - `system/etc/ramdisk/build.prop`: dedicated bootimage properties extracted from ramdisk.
  - `module.prop`: Magisk module metadata with patch-date-derived versioning and naming.
- Fallback attestation logic: checks `product.*` and `system.*` properties if `vendor.*` values are missing.
- Sysconfig XML extraction: copies Pixel experience XMLs (`pixel_experience_*.xml`, `google.xml`, `adaptivecharging.xml`, `quick_tap.xml`, etc.) into `system/product/etc/sysconfig/`.

### 4. Module Packaging (`build_module.sh`)
- Assembles properties, extracted sysconfig files, and template scripts (`module_files/`) into `result/<Codename>_<BuildID>/`.
- Includes runtime module scripts:
  - `service.sh`: boot-time property application with safe mode and TrickyStore integration.
  - `post-fs-data.sh`: early boot property overrides.
  - `customize.sh`: Magisk / KernelSU / APatch installation logic.
  - `webroot/`: WebUI dashboard support.
- Generates SHA256 integrity checksums for all executable shell scripts.
- Compresses the directory into a flashable module zip at repository root (`<Codename>_<BuildID>.zip`).

### 5. Continuous Integration & Tracker (`.github/workflows/`)
- **Automated OTA Tracker (`tracker.yml`)**:
  - Runs on a cron schedule every 4 hours (`0 */4 * * *`) or via manual trigger.
  - Probes Google OTA download endpoints forward-only (`src/main.py`) for new major and QPR releases.
  - Commits updated state to `data/state.json` on release discovery and triggers the build workflow.
- **Build Pipeline (`build.yml`)**:
  - Operates as a standalone workflow (`workflow_dispatch`) or reusable workflow (`workflow_call`) consumable by downstream device modules.
  - 3-stage execution:
    1. `prepare`: Resolves target devices via `src.devices` and evaluates release channel flags.
    2. `build`: Matrix parallel jobs per device (downloads OTA, unpacks images, synthesizes properties, packages module, and verifies duplicate status against existing releases).
    3. `release`: Aggregates module zips, creates/updates GitHub Release, appends artifacts to `CHANGELOG.md` via `update_changelog.py`, and posts notifications to Telegram.
- **Tag Conventions**:
  - Standard / Scheduled runs: `beta-YYYYMMDD` (Release)
  - Pre-release manual runs: `alpha-YYYYMMDD` (Pre-Release)
- **Duplicate Prevention**: Queries existing release assets via GitHub CLI (`gh`) to skip rebuilding already-published versions.
- **Telegram Notifications**: Sends release summaries with direct asset download links and formatted device lists.

---

## Directory Structure

```
.
├── .github/workflows/
│   ├── build.yml                # 3-stage matrix build and release pipeline (reusable)
│   └── tracker.yml              # Scheduled OTA probe and state synchronization
├── data/
│   └── state.json               # Persistent OTA version and build tracking registry
├── module_files/                # Magisk/KernelSU module templates and scripts
│   ├── customize.sh
│   ├── service.sh
│   ├── post-fs-data.sh
│   ├── gms_doze.sh
│   ├── pif.json
│   └── webroot/
├── src/                         # OTA tracking and device discovery package
│   ├── client.py                # HTTP client with rate-limiting and session cookies
│   ├── devices.py               # Scrapes and filters Pixel and Pixel Watch build targets
│   ├── main.py                  # Forward-probing tracker orchestrator
│   ├── parser.py                # HTML scraper for Google OTA tables
│   └── state.py                 # Schema and atomic persistence for tracking state
├── tests/                       # Test suite for tracker and parser components
│   └── test_tracker.py
├── build_bootanimation.sh       # Bootanimation packaging utility (optional)
├── build_module.sh              # Magisk zip packager
├── build_props.sh               # Property generator
├── build_sysconfig.sh           # Sysconfig XML parser
├── download_latest_ota_build.sh # OTA fetcher
├── extract_images.sh            # Main extraction orchestrator
├── requirements.sh              # Runtime shell dependency checker
├── requirements.txt             # Python dependencies for tracker and discovery
├── update_changelog.py          # Automated release notes injector for CHANGELOG.md
└── util_functions.sh            # Core extraction & utility library
```

---

## Prerequisites

- **Environment**: Linux (Debian, Ubuntu, Arch, Fedora, Alpine) or macOS
- **System Binaries**: `bash`, `coreutils`, `p7zip-full` (or `p7zip`), `erofs-utils`, `lz4`, `cpio`, `dos2unix`, `aria2`, `curl`, `xxd`, `jq`
- **Python**: Python 3.10+ with `payload_dumper` (`5ec1cff/payload-dumper`) and project dependencies

### Dependency Installation

Debian / Ubuntu:
```bash
sudo apt-get update
sudo apt-get install -y p7zip-full e2fsprogs erofs-utils lz4 cpio \
  dos2unix aria2 curl xxd python3 python3-pip jq
pip3 install -r requirements.txt
pip3 install --break-system-packages ./payload_dumper
```

Arch Linux:
```bash
sudo pacman -S --needed p7zip erofs-utils lz4 cpio dos2unix aria2 curl xxd jq python python-pip
pip install -r requirements.txt
pip install ./payload_dumper
```

Fedora:
```bash
sudo dnf install -y p7zip p7zip-plugins erofs-utils lz4 cpio dos2unix aria2 curl python3 python3-pip jq
pip3 install -r requirements.txt
pip3 install ./payload_dumper
```

## Installation & Setup

1. Clone the repository with submodules:
```bash
git clone --recurse-submodules https://github.com/Elcapitanoe/Build-Prop-BETA.git
cd Build-Prop-BETA
```

2. Make scripts executable:
```bash
chmod +x *.sh
```

---

## Local Usage

### Step 1: Download OTA Images
Pass one or more device identifiers, or discover targets automatically:
```bash
# Standard Beta
./download_latest_ota_build.sh husky_beta17

# Specific QPR Beta
./download_latest_ota_build.sh felix_beta17q2 tokay_beta17q2

# Pixel Watch and phone targets
./download_latest_ota_build.sh marlin stallion_beta17q2 cubs_beta17q2

# Resolve active targets via Python scraper
python3 -m src.devices --devices "all"
```

### Step 2: Extract & Build Modules
```bash
./extract_images.sh
```
This triggers image extraction, property resolution (`build_props.sh`), sysconfig extraction (`build_sysconfig.sh`), and zip packaging (`build_module.sh`).

Output module zips are placed at the repository root:
```
./Felix_UP2A.260805.003.zip
```

### Step 3: Run Tracker & Tests Locally (Optional)
Run the OTA tracker check:
```bash
python3 -m src.main
```

Execute unit tests:
```bash
pytest
```

---

## GitHub Actions Secrets

Configure these repository secrets in GitHub (`Settings -> Secrets and variables -> Actions`):

| Secret | Description |
|---|---|
| `GITHUB_TOKEN` | Automatically provided by GitHub Actions (requires `contents: write`) |
| `TELEGRAM_BOT_TOKEN` | Bot API token from `@BotFather` |
| `TELEGRAM_CHAT_ID` | Telegram chat, channel, or group ID for release notifications |
