#!/usr/bin/env bash
set -euo pipefail

ros2 daemon stop
ros2 daemon start
