#!/usr/bin/env bash
set -euo pipefail

# Flash Ubuntu Server for Raspberry Pi to an SD card on macOS.
#
# DESTRUCTIVE: this overwrites the target disk completely.
#
# Default image is Ubuntu 24.04.4 LTS Server arm64 preinstalled for Raspberry Pi.
# Run from repo root:
#   ./scripts/flash_ubuntu_rpi_sd_macos.sh /dev/disk5
#
# This script requires sudo for dd. It is intended to be run in your own terminal,
# not from a non-interactive agent session.

DISK="${1:-}"
IMAGE="${2:-images/ubuntu-24.04.4-preinstalled-server-arm64+raspi.img.xz}"
SHA256SUMS="$(dirname "$IMAGE")/SHA256SUMS"

if [[ -z "$DISK" ]]; then
  echo "Usage: $0 /dev/diskN [path/to/ubuntu-raspi.img.xz]" >&2
  exit 2
fi

if [[ ! "$DISK" =~ ^/dev/disk[0-9]+$ ]]; then
  echo "Refusing suspicious disk path: $DISK" >&2
  echo "Expected something like /dev/disk5" >&2
  exit 2
fi

if [[ ! -f "$IMAGE" ]]; then
  echo "Image not found: $IMAGE" >&2
  exit 1
fi

if ! command -v xzcat >/dev/null 2>&1; then
  echo "xzcat not found. Install xz, for example: brew install xz" >&2
  exit 1
fi

if [[ -f "$SHA256SUMS" ]]; then
  image_base="$(basename "$IMAGE")"
  echo "Verifying checksum for $image_base"
  # The Ubuntu SHA256SUMS file contains many images. Checking the whole file
  # fails when only one image has been downloaded, especially with pipefail set.
  expected_line="$(grep -F " *${image_base}" "$SHA256SUMS" || true)"
  if [[ -z "$expected_line" ]]; then
    expected_line="$(grep -F " ${image_base}" "$SHA256SUMS" || true)"
  fi
  if [[ -z "$expected_line" ]]; then
    echo "Could not find $image_base in $SHA256SUMS" >&2
    exit 1
  fi
  (cd "$(dirname "$IMAGE")" && printf '%s\n' "$expected_line" | shasum -a 256 -c -)
fi

echo
CURRENT_INFO="$(diskutil info "$DISK" 2>/dev/null || true)"
if [[ -z "$CURRENT_INFO" ]]; then
  echo "Could not read disk info for $DISK" >&2
  exit 1
fi

echo "Target disk info:"
echo "$CURRENT_INFO" | egrep 'Device Identifier|Device Node|Whole|Part of Whole|Device / Media Name|Protocol|Disk Size|Internal|Removable|Solid State|Mounted|Volume Name' || true

echo
if echo "$CURRENT_INFO" | grep -q 'Internal:.*Yes'; then
  echo "REFUSING: $DISK appears to be an internal disk." >&2
  exit 1
fi

if ! echo "$CURRENT_INFO" | grep -q 'Whole:.*Yes'; then
  echo "REFUSING: $DISK is not a whole disk. Use /dev/diskN, not /dev/diskNsM." >&2
  exit 1
fi

RAW_DISK="/dev/r$(basename "$DISK")"

echo "About to overwrite: $DISK ($RAW_DISK)"
echo "With image:         $IMAGE"
echo
printf "Type the exact disk path '%s' to continue: " "$DISK"
read -r CONFIRM
if [[ "$CONFIRM" != "$DISK" ]]; then
  echo "Confirmation did not match. Aborting."
  exit 1
fi

echo "Unmounting $DISK"
diskutil unmountDisk "$DISK"

echo "Writing image. This can take several minutes."
echo "You may be prompted for your macOS password for sudo."
# Do not use conv=sync here: when reading from a pipe, BSD/macOS dd may
# receive short input reads and pad each one to bs=4m, corrupting the image.
xzcat "$IMAGE" | sudo dd of="$RAW_DISK" bs=4m status=progress

echo "Flushing writes"
sync
sleep 2

echo "Ejecting $DISK"
diskutil eject "$DISK" || true

echo
echo "Done. Insert the SD card into the Raspberry Pi 4 and boot."
echo "Ubuntu Raspberry Pi Server images commonly use initial login ubuntu/ubuntu, then force a password change."
