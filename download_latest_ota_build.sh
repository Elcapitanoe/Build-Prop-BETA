#!/bin/bash

# Using util_functions.sh
[ -f "util_functions.sh" ] && . ./util_functions.sh || { echo "util_functions.sh not found" && exit 1; }

# At least one argument has to be provided
[ -z "$1" ] && print_message "Please provide at least one argument (OTA device codename) !" error

print_message "Downloading OTA builds for the following devices: $(
  IFS=,
  echo "${*:1}"
)…" info
unset IFS

# Make sure download directory exists
mkdir -p "dl"

# Build a list of URL to be downloaded
BUILD_URL_LIST=()

# This script downloads the latest OTA build for a list of devices.
# The device names are passed as arguments to the script.
for input_device_name in "$@"; do # Loop over each argument (device name)

  # 1. Check for specific beta2 suffix FIRST (Custom Request)
  if [[ $input_device_name == *"_beta2"* ]]; then
      mode="beta2"
      # Remove _beta2 to ensure clean codename extraction
      current_device_name=${input_device_name//_beta2/}
  else
      mode="standard"
      current_device_name=$input_device_name
  fi

  # Extract any possible Android version from the device name
  android_version=$(echo "$current_device_name" | grep -oP '\K\d+')

  # Check if the Android version is between 14 and 16, otherwise print warning
  # Only check if version is detected and we are not in beta2 mode (which implies v16)
  if [[ -n $android_version ]]; then
    [[ $android_version -ge 14 && $android_version -le 16 ]] || print_message "Android version isn't between 14 and 16, Trying anyway…" warning
  fi

  # Assign android_version, defaulting to 15 if not set
  android_version="${android_version:-15}"

  # Remove any numbers from the device name to get pure codename
  clean_device_name=${current_device_name//[^[:alpha:]_]/}

  # --- LOGIC SELECTION ---
  
  if [[ $mode == "beta2" ]]; then
    # CUSTOM: Android 16 QPR3 Logic
    # Fetches from the specific URL requested
    target_url="https://developer.android.com/about/versions/16/qpr3/download"
    
    # We grep the ZIP file for the clean codename (e.g., 'komodo')
    last_build_url=$(curl -b "devsite_wall_acks=nexus-ota-tos" -Ls "$target_url?partial=1" | grep -oP "https://\S+${clean_device_name}\S+\.zip" | tail -1)

  elif [[ $clean_device_name == *_beta* ]]; then
    # STANDARD BETA LOGIC
    # If it does, fetch the URL of the latest beta build for the device from the beta builds page
    last_build_url=$(curl -b "devsite_wall_acks=nexus-ota-tos" -Ls "https://developer.android.com/about/versions/$android_version/download-ota?partial=1" | grep -oP "https://\S+${clean_device_name}\S+\.zip" | tail -1)
  else
    # STABLE LOGIC
    # If the device name does not contain "_beta", fetch the URL of the latest non-beta build
    last_build_url=$(curl -b "devsite_wall_acks=nexus-ota-tos" -Ls 'https://developers.google.com/android/ota?partial=1' | grep -oP "\d+(\.\d+)+ \([^)]+\).*?https://\S+${clean_device_name}\S+zip" | sed -n 's/\\u003c\/td\\u003e\\n    \\u003ctd\\u003e\\u003ca href=\\"/ /p' | awk -F',' 'NF<=2' | tail -1 | grep -Eo "(https\S+)")
  fi

  if [[ -n $last_build_url ]]; then
    # Print a message indicating that the download is starting
    print_message "Downloading OTA build for ${clean_device_name^} ($mode) (\"$last_build_url\")…" debug

    # Add the URL to the list.
    BUILD_URL_LIST+=("$last_build_url")
  else
    print_message "Could not find URL for device: $input_device_name (Codenamed checked: $clean_device_name)" warning
  fi
done

# Check if the URL list has at least one item
[ ${#BUILD_URL_LIST[@]} -lt 1 ] && print_message "No download were found for the specified model or version." error

# Download the build using aria2
aria2c -Z -m0 -x16 -s16 -j16 --file-allocation=none --enable-rpc=false --optimize-concurrent-downloads=true --disable-ipv6=true --allow-overwrite=true --remove-control-file=true --always-resume=true --download-result=full --summary-interval=0 -d ./dl "${BUILD_URL_LIST[@]}"
print_message "Download complete" info
