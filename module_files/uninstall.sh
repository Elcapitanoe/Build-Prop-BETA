#!/system/bin/sh

MODDIR="${0%/*}"
PIF_DIRS="/data/adb/modules/playintegrityfix/pif.json"

if [ -d "/data/adb/modules/playintegrityfix" ]; then
  # Loop through each PIF dir
  for PIF_DIR in $PIF_DIRS; do
    # If has backup restore it
    if [ -f "${PIF_DIR}.old" ]; then
      mv "${PIF_DIR}.old" "$PIF_DIR"
    elif [ ! -f "$PIF_DIR" ]; then
      # Restore fallback config from bundled file or repository
      ui_print " -+ Missing $PIF_DIR, restoring fallback config..."
      if [ -f "$MODDIR/pif.json" ]; then
        cp -f "$MODDIR/pif.json" "$PIF_DIR"
      else
        wget -q -O "$PIF_DIR" "https://raw.githubusercontent.com/Elcapitanoe/Build-Prop-BETA/main/module_files/pif.json" 2>/dev/null || \
        wget -q -O "$PIF_DIR" "https://raw.githubusercontent.com/Elcapitanoe/Build-Prop-BETA/dev/module_files/pif.json"
      fi
    fi
  done
fi

# Find install-recovery.sh and set permissions back to default
find /vendor/bin /system/bin -name install-recovery.sh -exec chmod 755 {} \;

# Revert permissions for other files/directories
chmod 644 /proc/cmdline
chmod 644 /proc/net/unix
chmod 755 /system/addon.d
chmod 755 /sdcard/TWRP
