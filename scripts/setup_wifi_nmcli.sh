#!/usr/bin/env bash
set -euo pipefail

# Configure Wi-Fi using NetworkManager/nmcli on Ubuntu Server.
# Usage:
#   sudo ./scripts/setup_wifi_nmcli.sh "YourSSID" "YourWifiPassword"
#
# Warning: passing passwords on the command line can leave them in shell history.
# For a permanent setup, prefer editing a secure NetworkManager connection file
# or run this manually in a private shell.

if [[ $EUID -ne 0 ]]; then
  echo "Run as root, for example: sudo $0 <SSID> <PASSWORD>" >&2
  exit 1
fi

if [[ $# -ne 2 ]]; then
  echo "Usage: sudo $0 <SSID> <PASSWORD>" >&2
  exit 1
fi

SSID="$1"
PASSWORD="$2"

if ! command -v nmcli >/dev/null 2>&1; then
  echo "nmcli not found. Install NetworkManager first: sudo apt install network-manager" >&2
  exit 1
fi

systemctl enable --now NetworkManager

# List radios and networks for visibility.
nmcli radio wifi on
nmcli dev wifi list || true

# Create or update connection.
if nmcli -t -f NAME connection show | grep -Fxq "${SSID}"; then
  echo "Updating existing Wi-Fi connection '${SSID}'"
  nmcli connection modify "${SSID}" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "${PASSWORD}"
else
  echo "Creating Wi-Fi connection '${SSID}'"
  nmcli dev wifi connect "${SSID}" password "${PASSWORD}"
fi

nmcli connection up "${SSID}"

echo "Wi-Fi status:"
nmcli dev status
ip addr show wlan0 || true
