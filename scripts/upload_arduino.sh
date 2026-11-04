set -e
SKETCH="../firmware/arduino_nano_base_controller/arduino_nano_base_controller.ino"
FQBN="arduino:avr:nano:cpu=atmega328old"
PORT="/dev/arduino"
echo "[1/2] Compiling $SKETCH for $FQBN..."
arduino-cli compile --fqbn "$FQBN" "$SKETCH"
echo "[2/2] Uploading to $PORT..."
arduino-cli upload -v --fqbn "$FQBN" -p "$PORT" "$SKETCH"
echo "Done."
