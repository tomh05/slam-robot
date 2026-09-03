#!/usr/bin/env bash
# Scan one or more /24 subnets for the robot by attempting SSH as <user>@<ip>.
# Usage:
#   ./scripts/find_robot_ip.sh [subnet1 [subnet2 ...]]
#   ./scripts/find_robot_ip.sh --test <ip>
# Example:
#   ./scripts/find_robot_ip.sh 172.16.0 172.16.1
#   ./scripts/find_robot_ip.sh --test 172.16.0.42

set -euo pipefail

USER="${FIND_ROBOT_USER:-ubuntu}"
CONCURRENCY="${FIND_ROBOT_CONCURRENCY:-20}"
TIMEOUT="${FIND_ROBOT_TIMEOUT:-2}"
PORT="${FIND_ROBOT_PORT:-22}"
PROGRESS_EVERY="${FIND_ROBOT_PROGRESS_EVERY:-10}"

test_mode=0
TEST_IP=""
SUBNETS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --test)
      test_mode=1
      shift
      TEST_IP="${1:-}"
      if [[ -z "${TEST_IP}" ]]; then
        echo "Usage: $0 --test <ip>" >&2
        exit 1
      fi
      shift
      ;;
    *)
      if [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        TEST_IP="$1"
        test_mode=1
        shift
      elif [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        SUBNETS+=("$1")
        shift
      elif [[ "$1" != "${USER}" ]]; then
        SUBNETS+=("$1")
        shift
      else
        shift
      fi
      ;;
  esac
done

if [[ "${test_mode}" -eq 1 && -n "${TEST_IP}" ]]; then
  echo "Testing SSH to ${USER}@${TEST_IP}:${PORT}..." >&2
  ssh \
    -o BatchMode=yes \
    -o ConnectTimeout="${TIMEOUT}" \
    -o StrictHostKeyChecking=no \
    -o LogLevel=VERBOSE \
    -o PreferredAuthentications=publickey \
    -p "${PORT}" \
    "${USER}@${TEST_IP}" \
    exit
  echo "SSH test returned: $?" >&2
  exit $?
fi

if [[ ${#SUBNETS[@]} -eq 0 ]]; then
  SUBNETS=(172.16.0 172.16.1)
fi

TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT

found=0

scan_subnet() {
  local subnet="$1"
  local found_in_subnet=0
  local attempted=0

  echo "Scanning ${subnet}.0/24..." >&2

  for i in $(seq 1 254); do
    ip="${subnet}.${i}"

    while [[ "$(jobs -rp | wc -l)" -ge "${CONCURRENCY}" ]]; do
      wait -n 2>/dev/null || true
    done

    (
      if ssh \
        -o BatchMode=yes \
        -o ConnectTimeout="${TIMEOUT}" \
        -o StrictHostKeyChecking=no \
        -o LogLevel=ERROR \
        -o PreferredAuthentications=publickey \
        -p "${PORT}" \
        "${USER}@${ip}" \
        exit 2>/dev/null; then
        echo "${ip}"
      fi
    ) > "${TMPDIR}/${subnet}__${ip}" 2>/dev/null &

    attempted=$((attempted + 1))
    if (( attempted % PROGRESS_EVERY == 0 )); then
      echo "  ... tried ${attempted}/254 addresses in ${subnet}.0/24" >&2
    fi
  done

  echo "  Waiting for remaining probes in ${subnet}.0/24..." >&2
  wait || true

  for f in "${TMPDIR}/${subnet}__"*; do
    [[ -s "$f" ]] || continue
    ip="$(basename "$f" | sed "s/^${subnet}__//")"
    echo "Found robot at: ssh ${USER}@${ip}"
    found_in_subnet=$((found_in_subnet + 1))
  done
  echo "Finished scanning ${subnet}.0/24 (${attempted} probes)" >&2
  return ${found_in_subnet}
}

echo "Scanning subnets: ${SUBNETS[*]}" >&2
for subnet in "${SUBNETS[@]}"; do
  if scan_subnet "${subnet}"; then
    found=$((found + 1))
  fi
done

if [[ "${found}" -eq 0 ]]; then
  echo "No reachable ${USER}@ host found on scanned subnets" >&2
  echo "Tip: run '$0 --test <ip>' to debug SSH to a specific address." >&2
  exit 1
fi

echo "Done scanning subnets: ${SUBNETS[*]}" >&2
exit 0
