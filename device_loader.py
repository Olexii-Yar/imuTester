import time
import serial
import definitions as vars
import msp_helper as msp

def connect():
    global serr
    serr = serial.Serial(vars.SERIAL_PORT, vars.BAUD_RATE, timeout=1)

def disconnect():
    serr.close()

def reboot():
    msp.send_msp_request(serr, msp.MSP_REBOOT)
    #cmd_id, payload = msp.read_msp_response(serr)

    #if cmd_id is None or cmd_id != msp.MSP_REBOOT:
    #    raise RuntimeError("MSP_REBOOT failed: unexpected response")
    # FC може не встигнути відповісти перед перезавантаженням — ігноруємо
    try:
        msp.read_msp_response(serr)
    except Exception:
        pass

    disconnect()

    # Чекаємо поки COM-порт з'явиться знову (USB re-enumeration)
    max_wait = 8  # секунд максимум
    poll_interval = 2
    waited = 0
    while waited < max_wait:
        time.sleep(poll_interval)
        waited += poll_interval
        try:
            connect()
            return
        except serial.SerialException:
            pass

    raise RuntimeError(f"COM port {vars.SERIAL_PORT} did not reappear after {max_wait}s")