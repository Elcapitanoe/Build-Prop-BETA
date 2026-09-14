#!/bin/bash

# Only run requirements check once per shell session
[ -n "$PIXEL_PROPS_REQS_DONE" ] && return 0
PIXEL_PROPS_REQS_DONE=1

# Those are the only partitions we need for building properties
declare PARTITIONS2EXTRACT=("product" "vendor" "vendor_dlkm" "system" "system_ext" "system_dlkm" "init_boot")

[[ $(type -t "print_message") != function ]] && . ./util_functions.sh

# Install required packages and libs
install_packages "zip" "p7zip-full" "erofs-utils" "lz4" "cpio" "dos2unix" "aria2"

# Check whethever python was installed, TODO: Improve install_packages function.
if ! command -v python3 >/dev/null 2>&1; then
	install_packages "python3"
fi

# Check if python3 pip module installed
python3 -m pip -V &>/dev/null || print_message "Could not find pip module in python3, To fix this issue simply aria2c and install https://bootstrap.pypa.io/get-pip.py from python3" error

# Check if payload_dumper is available
if ! command -v payload_dumper >/dev/null 2>&1; then
	if [ -d "./payload_dumper" ]; then
		print_message "Could not find payload_dumper executable in PATH. Install it from the submodule using: pip install ./payload_dumper" error
	else
		print_message "Could not find payload_dumper. Run 'git submodule update --init' and install via 'pip install ./payload_dumper'" error
	fi
fi

# Install unpack_bootimg if not already installed
if [ ! -f "./unpack_bootimg.py" ]; then
	print_message "./unpack_bootimg.py not found. installing…" info
	aria2c -q "https://android.googlesource.com/platform/system/tools/mkbootimg/+/refs/heads/master/unpack_bootimg.py?format=TEXT" -o unpack.b64 \
		&& base64 -d unpack.b64 > unpack_bootimg.py \
		&& rm -f unpack.b64 \
		&& chmod +x unpack_bootimg.py \
		|| { print_message "Failed to download unpack_bootimg.py" error; exit 1; }
fi
