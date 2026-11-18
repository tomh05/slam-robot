#!/usr/bin/env bash
set -euo pipefail

MAP_NAME="${1:-map-$(date +%Y%m%d-%H%M%S)}"
MAP_DIR="${MAP_DIR:-$HOME/maps}"

if [[ "$MAP_NAME" == */* ]]; then
    echo "Map name must not contain '/': $MAP_NAME" >&2
    exit 1
fi

mkdir -p "$MAP_DIR"
MAP_PATH="$MAP_DIR/$MAP_NAME"

echo "Saving map to ${MAP_PATH}.yaml and ${MAP_PATH}.pgm"
ros2 run nav2_map_server map_saver_cli -f "$MAP_PATH"
