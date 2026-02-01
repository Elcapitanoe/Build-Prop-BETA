#!/bin/bash

# Initialize utility functions dependency
[ -f "util_functions.sh" ] && . ./util_functions.sh || { echo "Error: util_functions.sh dependency missing." && exit 1; }

# Validate that at least one argument (device codename) is supplied
[ -z "$1" ] && print_message "Error: No device arguments provided. Please specify at least one OTA device codename." error

print_message "Initializing OTA payload acquisition for target devices: $(
  IFS=,
  echo "${*:1}"
)…" info
unset IFS

# Ensure the existence of the download directory artifact
mkdir -p "dl"

# Initialize array to store valid build URLs
BUILD_URL_LIST=()

# Iterate through provided arguments to process each device individually
for input_device_name in "$@"; do

  # Determine the operation mode based on specific suffix requirements.
  # Prioritize specific beta revisions (beta3, beta2) before falling back to standard processing.
  if [[ $input_device_name == *"_beta3"* ]]; then
      mode="beta3"
      # Sanitize input to retrieve base device identifier
      current_device_name=${input_device_name//_beta3/}
  elif [[ $input_device_name == *"_beta2"* ]]; then
      mode="beta2"
      current_device_name=${input_device_name//_beta2/}
  else
      mode="standard"
      current_device_name=$input_device_name
  fi

  # Extract Android version integer from the device identifier string
  android_version=$(echo "$current_device_name" | grep -oP '\K\d+')

  # Validate Android version compatibility (Target range: 14-16).
  # Conditional execution bypasses validation if version is undetectable or implicit in beta modes.
  if [[ -n $android_version ]]; then
    [[ $android_version -ge 14 && $android_version -le 16 ]] || print_message "Warning: Detected Android version is outside the optimized range (14-16). Proceeding with extraction..." warning
  fi

  # Set default version to 15 if extraction yielded null
  android_version="${android_version:-15}"

  # Sanitize the device identifier by stripping numeric characters to isolate the hardware codename
  clean_device_name=${current_device_name//[^[:alpha:]_]/}

  # --- UPSTREAM SOURCE SELECTION LOGIC ---
  
  if [[ $mode == "beta3" ]]; then
    # LOGIC: Android 16 QPR3 Beta
    # Targets the specific developer preview URL for QPR3
    target_url="https://developer.android.com/about/versions/16/qpr3/download-ota"
    
    # Parse the upstream page for the ZIP file corresponding to the codename
    last_build_url=$(curl -b "devsite_wall_acks=nexus-ota-tos" -Ls "$target_url?partial=1" | grep -oP "https://\S+${clean_device_name}\S+\.zip" | tail -1)

  elif [[ $mode == "beta2" ]]; then
    # LOGIC: Android 16 QPR2 Beta
    # Targets the specific developer preview URL for QPR2
    target_url="https://developer.android.com/about/versions/16/qpr2/download-ota"
    
    last_build_url=$(curl -b "devsite_wall_acks=nexus-ota-tos" -Ls "$target_url?partial=1" | grep -oP "https://\S+${clean_device_name}\S+\.zip" | tail -1)

  elif [[ $clean_device_name == *_beta* ]]; then
    # LOGIC: Generic Beta Program
    # Dynamic URL generation based on detected Android version
    last_build_url=$(curl -b "devsite_wall_acks=nexus-ota-tos" -Ls "https://developer.android.com/about/versions/$android_version/download-ota?partial=1" | grep -oP "https://\S+${clean_device_name}\S+\.zip" | tail -1)
  else
    # LOGIC: Stable Release Channel
    # Scrapes the official Google API/Developers page for the latest stable OTA package
    last_build_url=$(curl -b "devsite_wall_acks=nexus-ota-tos" -Ls 'https://developers.google.com/android/ota?partial=1' | grep -oP "\d+(\.\d+)+ \([^)]+\).*?https://\S+${clean_device_name}\S+zip" | sed -n 's/\\u003c\/td\\u003e\\n    \\u003ctd\\u003e\\u003ca href=\\"/ /p' | awk -F',' 'NF<=2' | tail -1 | grep -Eo "(https\S+)")
  fi

  # Validate URL retrieval success
  if [[ -n $last_build_url ]]; then
    print_message "Acquiring OTA payload for ${clean_device_name^} [Mode: $mode] via ($last_build_url)…" debug
    BUILD_URL_LIST+=("$last_build_url")
  else
    print_message "Critical: Failed to resolve download URL for device: $input_device_name (Codename used: $clean_device_name)" warning
  fi
done

# Verify that the build list contains valid targets before invoking the download engine
[ ${#BUILD_URL_LIST[@]} -lt 1 ] && print_message "Error: No valid download targets resolved for the specified parameters." error

# Execute multi-threaded download sequence via aria2c
aria2c -Z -m0 -x16 -s16 -j16 --file-allocation=none --enable-rpc=false --optimize-concurrent-downloads=true --disable-ipv6=true --allow-overwrite=true --remove-control-file=true --always-resume=true --download-result=full --summary-interval=0 -d ./dl "${BUILD_URL_LIST[@]}"

print_message "OTA payload acquisition sequence completed successfully." info
