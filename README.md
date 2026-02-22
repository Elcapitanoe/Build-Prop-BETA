# Pixel Prop Builder: Streamlined OTA to Build.prop Conversion

This automation suite efficiently extracts and manages system properties from Pixel OTA updates. Designed for developers and system administrators, it simplifies the process of accessing and customizing Android build properties.

## Quick Start

### Prerequisites

* **Environment**: A Unix-like operating system running Linux or macOS with Bash.
* **Core Utilities**: Ensure the installation of `dos2unix`, `aria2`, `zip`, `unzip`, `p7zip`, and `curl`.
* **Python Runtime**: Python 3.8 or higher is required.

```bash
sudo apt-get update -y
sudo apt-get install python3 python3-pip python3-venv -y

```

## Installation

1. **Clone the repository**: Download the source code along with its submodules.

```bash
git clone --recurse https://github.com/Elcapitanoe/Build-Prop-BETA && cd Build-Prop-BETA

```

2. **Configure virtual environment**: It is recommended to isolate dependencies using a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate

```

3. **Install dependencies**: Install the required Python packages.

```bash
python3 -m pip install payload_dumper --break-system-packages

```

## Usage

1. **Obtain Firmware Images**: Identify the required factory or OTA images from the official Google Android Images repository, Android 15, Android 16, or Android 17 release channels.
2. **Fetch Latest Builds**: Execute the download script using the specific device codenames and their target branch suffixes.
* Example command: `./download_latest_ota_build.sh komodo komodo_beta15 komodo_beta16 komodo_beta17`

3. **Extract System Images**: Place the downloaded archive files within the project workspace. Run `./extract_images.sh` to automatically extract the images and parse their build properties into the `result/` directory.
4. **Compile Magisk Module**: Run `./build_module.sh` to aggregate the extracted data and compile the final module from the generated results.

## Key Features

* **Automated Payload Acquisition**: Downloads the latest stable and beta builds directly from Google's official developer servers.
* **Unified Image Extraction**: Processes and extracts system images from both full factory images and incremental OTA updates.
* **Automated Prop Generation**: Parses extracted system components to systematically generate accurate `build.prop` files.
* **Core Module System (service.sh)**: Implements a Safe Mode to prevent critical system configuration conflicts. It integrates Sensitive Props Mod features securely and utilizes PIHooks for dynamic, module-based property spoofing. PIHooks automatically deactivates if a properly configured Play Integrity Fix module is detected.
* **Ancillary Module System (action.sh)**: Automates the compilation of `PIF.json` configurations specifically for Beta OTA builds. It also manages TrickyStore target application lists and handles broken TEE status automatically.
* **Continuous Integration**: Leverages GitHub Actions for scheduled build pipelines, intelligent duplicate release prevention, and automated deployment notifications via Telegram.
* **Extensibility**: Framework ready for future integrations, including the compilation of Pixel-specific features such as `sysconfigs`.

## Responsible Usage Guidelines

This project is published strictly for educational and experimental purposes. Operators must utilize this tool responsibly.

* **Code Auditing**: Thoroughly review the codebase before executing scripts in any production or personal environment.
* **Security Compliance**: Adhere to established industry standards regarding system security and device integrity.

The maintainers of this repository assume no liability for system instability, data loss, or any damages resulting from the use of these tools.

## Credit & Support

-   **Core Logic:** [@0x11DFE](https://github.com/0x11DFE)
-   **Feedback:** Found a bug? Open a ticket on the [Issues Page](https://github.com/Elcapitanoe/Build-Prop-BETA/issues).
