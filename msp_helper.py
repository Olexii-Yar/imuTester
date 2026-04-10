import struct

# MSP command IDs
MSP_ANALOG = 110
MSP_ATTITUDE = 108
MSP_ALTITUDE = 109
MSP_RAW_IMU = 102

MSP_SENSOR_ALIGNMENT = 126
MSP_SET_SENSOR_ALIGNMENT = 220

MSP_ACC_CALIBRATION = 205
MSP_MAG_CALIBRATION = 206
MSP_RESET_CONF = 208
MSP_REBOOT = 68
MSP_STATUS = 101

MSP_SET_ACC_TRIM = 239
MSP_ACC_TRIM = 240
MSP_ESC_SENSOR_DATA = 134

MSP_SENSOR_CONFIG = 96
MSP_SET_SENSOR_CONFIG = 97

#command_target_ids = {
#    "MSP_ANALOG": MSP_ANALOG,
#    "MSP_ALTITUDE": MSP_ALTITUDE,
#    "MSP_RAW_IMU": MSP_RAW_IMU,
#}


def get_checksum(msp_command_id, payload):
    checksum = 0
    length = len(payload)
    for byte in bytes([length, msp_command_id]) + payload:
        checksum ^= byte
    return checksum & 0xFF


def send_msp_command(sock_port, msp_command_id, data):
    payload = bytearray()
    for value in data:
        payload += struct.pack("<1H", value)

    packet = b"$M<" + bytes([len(payload), msp_command_id]) + payload
    packet += bytes([get_checksum(msp_command_id, payload)])
    sock_port.write(packet)


def send_msp_request(sock_port, msp_command_id):
    payload = b""
    packet = b"$M<" + struct.pack("<BB", 0, msp_command_id)
    packet += bytes([get_checksum(msp_command_id, payload)])
    sock_port.write(packet)


def _read_exact(sock_port, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock_port.read(size - len(data))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def read_msp_response(sock_port):
    """Read one MSP response frame.

    Returns (None, b"") on timeout/incomplete frame/checksum mismatch.
    """
    header = bytearray()
    while True:
        byte = sock_port.read(1)
        if not byte:
            return None, b""
        header += byte
        if len(header) > 3:
            header = header[-3:]
        if bytes(header) == b"$M>":
            break

    length_and_cmd = _read_exact(sock_port, 2)
    if len(length_and_cmd) < 2:
        return None, b""

    payload_length = length_and_cmd[0]
    msp_command_id = length_and_cmd[1]

    payload_and_checksum = _read_exact(sock_port, payload_length + 1)
    if len(payload_and_checksum) < payload_length + 1:
        return None, b""

    payload = payload_and_checksum[:payload_length]
    checksum = payload_and_checksum[payload_length]
    if checksum != get_checksum(msp_command_id, payload):
        return None, b""

    return msp_command_id, payload

def parse_msp_status(payload):
    if len(payload) < 13:
        return None
    cycle_time = int.from_bytes(payload[0:2], byteorder='little', signed=False)
    i2c_errors = int.from_bytes(payload[2:4], byteorder='little', signed=False)
    cpu_usage = int.from_bytes(payload[11:13], byteorder='little', signed=False)
    cpu_temp = 0

    btf_offset = 13

    # gyro_cycle_time (uint16)
    if len(payload) >= btf_offset + 2:
        btf_offset += 2

    # extra_flags (variable length)
    if len(payload) > btf_offset:
        extra_flags_count = payload[btf_offset] & 0x0F
        btf_offset += 1
        btf_offset += extra_flags_count

    # arming_disable_count (uint8) + arming_flags (uint32)
    if len(payload) >= btf_offset + 5:
        btf_offset += 5

    # config_state (uint8)
    if len(payload) >= btf_offset + 1:
        btf_offset += 1

    # cpu_temp (int16)
    if len(payload) >= btf_offset + 2:
        cpu_temp = int.from_bytes(payload[btf_offset:btf_offset + 2], byteorder='little', signed=True)

    return {
        "cycle_t": cycle_time,
        "i2c_err": i2c_errors,
        "cpu_load": cpu_usage,
        "cpu_cels": cpu_temp
    }

def parse_msp_altitude(payload):
    """Parse MSP_ALTITUDE payload (6 x int16)."""
    if len(payload) < 6:
        return None
    # < (little-endian), i (int32, 4 байти), h (int16, 2 байти)
    alt_cm, vario_cms = struct.unpack("<ih", payload[:6])

    return {
        "altitude_m": alt_cm / 100.0,
        "vario_cms": vario_cms
    }

def parse_msp_raw_imu(payload):
    """Parse MSP_RAW_IMU payload (9 x int16)."""
    if len(payload) < 18:
        return None

    values = struct.unpack("<9h", payload[:18])
    return {
        "acc": values[0:3],
        "gyro": values[3:6],
        "mag": values[6:9]
    }

def parse_cli_status(payload):
                                   
            ser.write(b'#\n')
            time.sleep(0.5)
            ser.reset_input_buffer()

            ser.write(b'status\n')
 
            start_time = time.time()
            buffer = ""

            while True:
                if ser.in_waiting > 0:
                    chunk = ser.read(ser.in_waiting).decode("utf-8", errors="ignore")
                    buffer += chunk
                    # stream to right panel
                    self.root.after(0, lambda c=chunk: self._append_editor(self.dl_text, c))

                    if "save" in chunk.lower() or chunk.strip().endswith("#"):
                        break

                if time.time() - start_time > 25:
                    self.root.after(0, lambda: self._log("Timeout after 25s.", "warn"))
                    break

                time.sleep(0.05)

            self.downloaded_text = buffer