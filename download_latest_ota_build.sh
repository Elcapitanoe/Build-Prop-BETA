#!/bin/bash
set -euo pipefail

[ -f "util_functions.sh" ] && . ./util_functions.sh || { echo "Error: util_functions.sh dependency missing."; exit 1; }
[ $# -eq 0 ] && { print_message "Error: No device arguments provided." error; exit 1; }

IFS=,
print_message "Initializing OTA payload acquisition for target devices: $*" info
unset IFS

mkdir -p "dl"
BUILD_URL_LIST=()
declare -A HTML_CACHE

for input_device_name in "$@"; do
    if [[ "$input_device_name" =~ ^(.*)_beta([0-9]+)q([0-9]+)$ ]]; then
        mode="beta_qpr"
        clean_device_name="${BASH_REMATCH[1]//[^a-zA-Z_]/}"
        target_url="https://developer.android.com/about/versions/${BASH_REMATCH[2]}/qpr${BASH_REMATCH[3]}/download-ota"
    elif [[ "$input_device_name" =~ ^(.*)_beta([0-9]+)$ ]]; then
        mode="beta_main"
        clean_device_name="${BASH_REMATCH[1]//[^a-zA-Z_]/}"
        target_url="https://developer.android.com/about/versions/${BASH_REMATCH[2]}/download-ota"
    elif [[ "$input_device_name" == *"_beta"* ]]; then
        mode="beta_legacy"
        clean_device_name="${input_device_name%%_beta*}"
        clean_device_name="${clean_device_name//[^a-zA-Z_]/}"
        target_url="https://developer.android.com/about/versions/15/download-ota"
    else
        mode="standard"
        clean_device_name="${input_device_name//[^a-zA-Z_]/}"
        target_url="https://developers.google.com/android/ota"
    fi

    if [[ -z "${HTML_CACHE[$target_url]:-}" ]]; then
        HTML_CACHE[$target_url]=$(curl -b "devsite_wall_acks=nexus-ota-tos" -Ls "${target_url}?partial=1" || true)
    fi

    last_build_url=""

    if [[ "$mode" == "standard" ]]; then
        last_build_url=$(echo "${HTML_CACHE[$target_url]}" | grep -oP "\d+(\.\d+)+ \([^)]+\).*?https://\S+${clean_device_name}\S+zip" | sed -n 's/\\u003c\/td\\u003e\\n\s*\\u003ctd\\u003e\\u003ca href=\\"/ /p' | awk -F',' 'NF<=2' | tail -1 | grep -Eo "(https\S+)" || true)
    else
        last_build_url=$(echo "${HTML_CACHE[$target_url]}" | grep -oP "https://\S+${clean_device_name}\S+\.zip" | tail -1 || true)
    fi

    if [[ -n "$last_build_url" ]]; then
        print_message "Acquiring OTA payload for ${clean_device_name^} [Mode: $mode] via ($last_build_url)…" debug
        BUILD_URL_LIST+=("$last_build_url")
    else
        print_message "Payload Unresolved: OTA URL for '$input_device_name' not found. The upstream server likely has not published this build yet." warning
    fi
done

if [[ ${#BUILD_URL_LIST[@]} -eq 0 ]]; then
    print_message "Execution Aborted: No valid download targets resolved. Please verify if Google has updated their repository." error
    exit 1
fi

aria2c -Z -m0 -x16 -s16 -j16 --file-allocation=none --enable-rpc=false --optimize-concurrent-downloads=true --disable-ipv6=true --allow-overwrite=true --remove-control-file=true --always-resume=true --download-result=full --summary-interval=0 -d ./dl "${BUILD_URL_LIST[@]}"

print_message "OTA payload acquisition sequence completed successfully." info
