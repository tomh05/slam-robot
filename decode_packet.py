import serial, struct, math

ser = serial.Serial('/dev/ttyUSB0', 153600, timeout=0.5)
ser.reset_input_buffer()
data = ser.read(8192)
ser.close()

i = 0
packets = 0
while i < len(data)-1 and packets < 5:
    if data[i] == 0xAA and i+1 < len(data) and data[i+1] == 0x55:
        if i+9 > len(data):
            break
        CT = data[i+2]
        LSN = data[i+3]
        FSA = struct.unpack('<H', data[i+4:i+6])[0]
        LSA = struct.unpack('<H', data[i+6:i+8])[0]
        CS = data[i+8]
        samp_start = i+9
        needed = samp_start + LSN*3
        if needed > len(data):
            break
        # angles
        fsa_deg = (FSA>>1)/64.0
        lsa_deg = (LSA>>1)/64.0
        if lsa_deg < fsa_deg:
            lsa_deg += 360.0
        step = (lsa_deg - fsa_deg)/(LSN-1) if LSN>1 else 0.0
        print(f"Packet {packets}: CT=0x{CT:02x} LSN={LSN} FSA={fsa_deg:.2f}° LSA={lsa_deg:.2f}° step={step:.3f}°")
        # show first 3 samples
        for n in range(min(3, LSN)):
            off = samp_start + n*3
            dlo = data[off]
            dhi = data[off+1]
            intensity = data[off+2]
            dist = dlo | (dhi<<8)
            print(f"  sample {n}: dist={dist}mm intensity={intensity}")
        packets += 1
        i = needed
    else:
        i += 1
