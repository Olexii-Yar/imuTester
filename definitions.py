SERIAL_PORT = 'COM18' # /dev/ttyACM0 (for Linux)
BAUD_RATE = 115200	
CONNECTION_ATTEMPTS = 5
CALIBRATION_SAMPLES = 100 # Було 1000 зразків, поставив для швидкості.
duration_after_start = 1250  # Час для стабілізації після reboot в мс.
num_reboots = 3
manual_reboot_init = True # True

# IMU ICM42688P
GYRO_SENSITIVITY = 16.4  # LSB/°/s for ±2000°/s range
ACC_1G_LSB = 2048            # ✓ Правильно для ±16g

NOISE_THRESHOLD = 15       # Жорсткіше за BF=48, але реалістично
STABILITY_THRESHOLD = 5    # Дозволяє 0.3°/s drift
ACC_THRESHOLD = 10         # ~0,5% від 1g
TILT_THRESHOLD = 25       # ~0.7° (ручна установка)

FLIGHT_MINUTES = 10  # константа для прогнозу похибки
TEMP_DELTA_MIN = 3.0       # мінімальна дельта для надійної кореляції
TEMP_RISE_PER_MIN = 3.0    # assumed °C/min для worst case прогнозу
GYRO_TEMP_COEF_DEFAULT = 0.008  # °/s per °C — ICM42688P datasheet typical

# ══════════════════════════════════════════════════════════════
# ACC ORIENTATION
# ══════════════════════════════════════════════════════════════

# Expected gravity direction (стандартна орієнтація для Betaflight)
ACC_GRAVITY_AXIS = 2        # 0=X, 1=Y, 2=Z
ACC_GRAVITY_DIRECTION = +1  # +1=UP, -1=DOWN

# Розрахункове значення 1g:
ACC_EXPECTED_1G_VALUE = ACC_1G_LSB * ACC_GRAVITY_DIRECTION  # +2048 для Z_UP

# Z_UP (standard):   gravity_axis=2, direction=+1 → expect Z≈+2048
# Z_DOWN (inverted): gravity_axis=2, direction=-1 → expect Z≈-2048
# X_UP (vertical):   gravity_axis=0, direction=+1 → expect X≈+2048



# just in case for future use^
# GYRO_UPDATE_HZ = 8000
# GYRO_DPS = 2000
# gyro_calib_duration = 125  # milliseconds
# logger_name = 'IMU-UA507'
# logger_directory = '/home/olexii/Desktop/autobee_fly/logs'  # ./logs (for Windows) 
# default_axis_rotation = NED
# default_adc_scale = 10