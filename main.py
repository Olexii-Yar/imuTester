import time

import numpy as np

import definitions as vars
import device_loader as dl
import msp_helper as msp
from math_logic import IMUdefectDetector


def ask_yes_no(prompt_text):
    while True:
        try:
            answer = input(prompt_text).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return False
        if answer in {"y", "yes", "т", "так"}:
            return True
        if answer in {"n", "no", "н", "ні"}:
            return False
        print("Введіть Y або N.")

def collect_acc_samples(sample_count):
    acc_samples = []
    
    consecutive_timeouts = 0
    max_consecutive_timeouts = vars.CONNECTION_ATTEMPTS

    while len(acc_samples) < sample_count:

        msp.send_msp_request(dl.serr, msp.MSP_RAW_IMU)
        cmd_id, payload = msp.read_msp_response(dl.serr)

        if cmd_id is None:
            consecutive_timeouts += 1
            if consecutive_timeouts >= max_consecutive_timeouts:
                raise RuntimeError("Too many MSP timeouts")
            continue

        if cmd_id != msp.MSP_RAW_IMU:
            consecutive_timeouts += 1
            if consecutive_timeouts >= max_consecutive_timeouts:
                raise RuntimeError("Too many MSP timeouts")
            continue

        parsed_imu = msp.parse_msp_raw_imu(payload)
        if not parsed_imu:
            consecutive_timeouts += 1
            if consecutive_timeouts >= max_consecutive_timeouts:
                raise RuntimeError("Too many MSP timeouts")
            continue

        consecutive_timeouts = 0

        acc_samples.append(parsed_imu["acc"])
    
    return (
        np.asarray(acc_samples, dtype=np.int16)
    )

def collect_imu_samples(sample_count):
    gyro_samples = []
    acc_samples = []
    baro_samples = []
    mcu_stata = []
    
    consecutive_timeouts = 0
    max_consecutive_timeouts = vars.CONNECTION_ATTEMPTS

    while len(gyro_samples) < sample_count:

        # --- 0. MCU ---
        msp.send_msp_request(dl.serr, msp.MSP_STATUS)
        cmd_id, payload = msp.read_msp_response(dl.serr)
        
        if cmd_id is None:
            consecutive_timeouts += 1
            if consecutive_timeouts >= max_consecutive_timeouts:
                raise RuntimeError("Too many MSP timeouts")
            continue

        if cmd_id != msp.MSP_STATUS:
            consecutive_timeouts += 1
            if consecutive_timeouts >= max_consecutive_timeouts:
                raise RuntimeError("Too many MSP timeouts")
            continue

        parsed_stata = msp.parse_msp_status(payload)
        if not parsed_stata:
            consecutive_timeouts += 1
            if consecutive_timeouts >= max_consecutive_timeouts:
                raise RuntimeError("Too many MSP timeouts")
            continue

        # --- 1. Барометр ---
        msp.send_msp_request(dl.serr, msp.MSP_ALTITUDE)
        cmd_id, payload = msp.read_msp_response(dl.serr)
        
        if cmd_id is None:
            consecutive_timeouts += 1
            if consecutive_timeouts >= max_consecutive_timeouts:
                raise RuntimeError("Too many MSP timeouts")
            continue

        if cmd_id != msp.MSP_ALTITUDE:
            consecutive_timeouts += 1
            if consecutive_timeouts >= max_consecutive_timeouts:
                raise RuntimeError("Too many MSP timeouts")
            continue

        parsed_baro = msp.parse_msp_altitude(payload)
        if not parsed_baro:
            consecutive_timeouts += 1
            if consecutive_timeouts >= max_consecutive_timeouts:
                raise RuntimeError("Too many MSP timeouts")
            continue

        # --- 2. IMU ---
        msp.send_msp_request(dl.serr, msp.MSP_RAW_IMU)
        cmd_id, payload = msp.read_msp_response(dl.serr)

        if cmd_id is None:
            consecutive_timeouts += 1
            if consecutive_timeouts >= max_consecutive_timeouts:
                raise RuntimeError("Too many MSP timeouts")
            continue

        if cmd_id != msp.MSP_RAW_IMU:
            consecutive_timeouts += 1
            if consecutive_timeouts >= max_consecutive_timeouts:
                raise RuntimeError("Too many MSP timeouts")
            continue

        parsed_imu = msp.parse_msp_raw_imu(payload)
        if not parsed_imu:
            consecutive_timeouts += 1
            if consecutive_timeouts >= max_consecutive_timeouts:
                raise RuntimeError("Too many MSP timeouts")
            continue

        consecutive_timeouts = 0

        # --- 3. Обидві відповіді валідні: зберігаємо один синхронний семпл ---
        baro_samples.append(parsed_baro["altitude_m"])
        gyro_samples.append(parsed_imu["gyro"])
        acc_samples.append(parsed_imu["acc"])
        mcu_stata.append(parsed_stata)

        # Звіт кожні 100 зразків
        count = len(gyro_samples)
        if count % 20 == 0 or count == sample_count:
            print(f"  Collected {count}/{sample_count} samples")

    return (
        np.asarray(gyro_samples, dtype=np.int16),
        np.asarray(acc_samples, dtype=np.int16),
        float(np.mean(baro_samples)),
        mcu_stata
    )


def maybe_reboot(cycle_index):
    if cycle_index == 0:
        return True

    if vars.manual_reboot_init:
        ready = ask_yes_no(
            f"\nCycle {cycle_index + 1}/{vars.num_reboots}. "
            "Готові перезапустити контролер? (Y/N): "
        )
        if not ready:
            return False

    print("  Rebooting flight controller...")
    dl.reboot()
    return True


def _fmt_dps(arr):
    return "({:.2f}, {:.2f}, {:.2f} °/s)".format(*arr)

def print_cycle_report(cycle_index, gyro_result, acc_result, acc_delta, baro_sample, mcu_samples):
    baro_avg_m = baro_sample
    mean_lsb = gyro_result["mean_lsb"]  # Було "offset_lsb"
    mean_dps = gyro_result["mean_dps"]  # Було "offset_dps"
    n_lsb = gyro_result["noise_p2p_lsb"]
    n_dps = gyro_result["noise_p2p_dps"]
    std   = gyro_result["std_lsb"]
    noise_ok = bool(gyro_result["noise_ok"])
    needs_cal = bool(gyro_result["needs_calibration"])
    fuzzy = bool(np.any(std > vars.NOISE_THRESHOLD))

    print(f"\nCycle {cycle_index + 1} report:")
    print(f"  [GYRO]")
    print(f"    Mean (residual) X/Y/Z: {mean_lsb.tolist()} LSB {_fmt_dps(mean_dps)}")
    print(f"    ^ Should be ≈[0,0,0] - shows quality of internal calibration")
    print(f"    Noise P2P X/Y/Z: {n_lsb.tolist()} LSB {_fmt_dps(n_dps)}")
    print(f"    Noise STD X/Y/Z: [{std[0]:.2f}, {std[1]:.2f}, {std[2]:.2f}] LSB"
          f"{' ⚠ Fuzzy Signal' if fuzzy else ''}")
    print(f"    Noise P2P check (<= {vars.NOISE_THRESHOLD} LSB): {'PASS' if noise_ok else 'FAIL'}")
    if needs_cal:
        print(f"    ⚠ Needs Calibration (offset > 0.5 °/s)")


    # --- ACC ---
    ma = acc_result["mean_acc"]
    ra = acc_result["rms_acc"]
    orient = acc_result["orientation"]
    axis_names = ['X', 'Y', 'Z']
    
    print(f"  [ACC]")
    print(f"    Mean ACC X/Y/Z:  {ma.tolist()} LSB")
    print(f"    Orientation:     {orient['detected']} "
          f"(gravity on {axis_names[orient['gravity_axis']]}: "
          f"{orient['gravity_lsb']} LSB = {orient['gravity_g']} g)")
    
    if not orient['matches']:
        print(f"    \u26a0\ufe0f  Expected {orient['expected']}!")
    
    print(f"    ACC RMS Noise:   [{ra[0]:.2f}, {ra[1]:.2f}, {ra[2]:.2f}] LSB")

    td = acc_result['tilt_details']
    tilt_thresh_deg = float(np.degrees(np.arctan2(vars.TILT_THRESHOLD, vars.ACC_1G_LSB)))
    print(f"    Tilt Error {'PASS' if acc_result['tilt_ok'] else 'FAIL'} (<= {vars.TILT_THRESHOLD} LSB [~{tilt_thresh_deg:.2f}°]): ")
    print(f"                     X: {td[0]['lsb']:.0f} LSB ({td[0]['deg']:.2f}°),  Y: {td[1]['lsb']:.0f} LSB ({td[1]['deg']:.2f}°)")

    print(f"    G-Accuracy:      {acc_result['g_error']} LSB "
          f"(<= {vars.ACC_THRESHOLD}): {'PASS' if acc_result['g_ok'] else 'FAIL'}")
    print(f"    ACC level: {'OK' if acc_result['acc_ok'] else 'FAIL'}")
    print(f"    ACC Δ from ref:  [{acc_delta[0]:.0f}, {acc_delta[1]:.0f}, {acc_delta[2]:.0f}] LSB"
          f"{'  (=after extract baseline from mean)' if cycle_index == 0 else ''}")
    # === BARO ===
    print(f"  [BARO]")
    print(f"    Average Height:  {baro_avg_m:.3f} m")
    # === MCU ===
    print(f"  [MCU]")
    if mcu_samples:
        last = mcu_samples[-1]
        print(f"    I2C Errors: {last['i2c_err']}")
        print(f"    CPU Load:   {last['cpu_load']} %")
        print(f"    Cycle Time: {last['cycle_t']} µs")
        print(f"    CPU Temp:   {last['cpu_cels']} °C")
    else:
        print(f"    No MCU data collected")
    # if cycle_index == 0:
    #     print(f"    ^ This is the baseline altitude for this test")

def analyze_final_data(offsets, acc_means, cycle_data):
    sensitivity = vars.GYRO_SENSITIVITY

    # --- GYRO ---
    offsets_array = np.asarray(offsets, dtype=float)
    drift_lsb = np.ptp(offsets_array, axis=0) if len(offsets_array) > 1 else np.zeros(3)
    drift_dps = np.round(drift_lsb / sensitivity, 4)
    drift_ok = bool(np.all(drift_lsb <= vars.STABILITY_THRESHOLD))
    noise_ok_all = all(bool(d["gyro"]["noise_ok"]) for d in cycle_data)
    any_needs_cal = any(bool(d["gyro"]["needs_calibration"]) for d in cycle_data)
    imu_stable = drift_ok and noise_ok_all

    all_mean_dps = np.array([d["gyro"]["mean_dps"] for d in cycle_data])
    worst_gyro_dps = float(np.max(np.abs(all_mean_dps)))

    # --- ACC ---
    acc_ok_all = all(bool(d["acc"]["acc_ok"]) for d in cycle_data)
    acc_means_arr = np.asarray(acc_means, dtype=float)

    if len(acc_means_arr) > 2:
        acc_anti_drift = np.ptp(acc_means_arr[1:], axis=0)
    elif len(acc_means_arr) == 2:
        acc_anti_drift = np.abs(acc_means_arr[1] - acc_means_arr[0])
    else:
        acc_anti_drift = np.zeros(3)

    worst_acc_delta = float(np.max(acc_anti_drift))

    # --- TEMP кореляція ---
    temps = []
    for d in cycle_data:
        mcu = d.get("mcu")
        if mcu:
            temps.append(float(mcu[-1]["cpu_cels"]))
        else:
            temps.append(None)

    temps_valid = [t for t in temps if t is not None]
    temp_delta = max(temps_valid) - min(temps_valid) if len(temps_valid) >= 2 else 0.0
    temp_reliable = temp_delta >= vars.TEMP_DELTA_MIN

    if temp_reliable and len(temps_valid) == len(cycle_data):
        gyro_scalars = [float(np.max(np.abs(d["gyro"]["mean_dps"]))) for d in cycle_data]
        delta_t = np.diff(np.array(temps_valid))
        delta_g = np.diff(np.array(gyro_scalars))
        valid = np.abs(delta_t) >= 1.0
        if np.any(valid):
            temp_coef = float(np.mean(delta_g[valid] / delta_t[valid]))
        else:
            temp_coef = vars.GYRO_TEMP_COEF_DEFAULT
    else:
        temp_coef = vars.GYRO_TEMP_COEF_DEFAULT  # datasheet fallback

    # --- Прогноз похибки ---
    flight_min = vars.FLIGHT_MINUTES
    gyro_error_deg = worst_gyro_dps * flight_min * 60
    acc_error_g = worst_acc_delta / vars.ACC_1G_LSB

    # worst case temp rise: реальна дельта або TEMP_RISE_PER_MIN * хвилини польоту
    flight_temp_rise = temp_delta if temp_reliable else vars.TEMP_RISE_PER_MIN * flight_min
    temp_correction = abs(temp_coef) * flight_temp_rise

    return {
        # gyro
        "drift_lsb": drift_lsb,
        "drift_dps": drift_dps,
        "drift_ok": drift_ok,
        "noise_ok_all": noise_ok_all,
        "imu_stable": imu_stable,
        "any_needs_cal": any_needs_cal,
        "worst_gyro_dps": worst_gyro_dps,
        # acc
        "acc_ok_all": acc_ok_all,
        "acc_anti_drift": acc_anti_drift,
        "worst_acc_delta": worst_acc_delta,
        # temp
        "temps": temps,
        "temp_delta": temp_delta,
        "temp_reliable": temp_reliable,
        "temp_coef": temp_coef,
        # forecast
        "flight_min": flight_min,
        "flight_temp_rise": flight_temp_rise, 
        "gyro_error_deg": gyro_error_deg,
        "acc_error_g": acc_error_g,
        "temp_correction": temp_correction,
    }
    
def print_final_report(offsets, acc_means, cycle_data, title="FINAL REPORT"):
    a = analyze_final_data(offsets, acc_means, cycle_data)

    print(f"\n{'='*70}")
    print(f"{title:^70}")
    print(f"{'='*70}")

    # --- CYCLES RESULTS ---
    print(f"\n=== CYCLES RESULTS ===")
    baro_values = []
    tilt_thresh_deg = float(np.degrees(np.arctan2(vars.TILT_THRESHOLD, vars.ACC_1G_LSB)))
    for idx, d in enumerate(cycle_data):
        gr = d["gyro"]
        ar = d["acc"]
        temp = a["temps"][idx]
        temp_str = f"{temp:.0f}°C" if temp is not None else "N/A"

        baro_sample = d.get("baro")
        if baro_sample is not None:
            baro_values.append(float(baro_sample))

        fuzzy_str = "FUZZY " if bool(np.any(gr["rms_lsb"] > vars.NOISE_THRESHOLD)) else "NORMAL"
        noise_str = "PASS" if gr["noise_ok"] else "FAIL"
        acc_str   = "PASS" if ar["acc_ok"]   else "FAIL"

        print(
            f"Cycle {idx + 1} // T={temp_str} | "
            f"GYRO: mean {'PASS' if not gr['needs_calibration'] else 'FAIL'},  "
            f"STD: {fuzzy_str},  p2p: {noise_str}  | "
            f"ACC: {acc_str} (<= {vars.TILT_THRESHOLD} LSB [<{tilt_thresh_deg:.1f}°])"
        )

    # --- BARO ---
    print(f"\n=== BARO ===")
    if baro_values:
        print(f"  Values:  [{', '.join(f'{v:.3f}' for v in baro_values)}] m   "
              f"Average: {np.mean(baro_values):.3f} m")
    else:
        print("  No baro data collected")

    print(f"{'-'*70}")

    # --- GYRO ---
    print(f"=== GYRO ===")
    print(f"  Drift p2p X/Y/Z: {a['drift_lsb'].astype(int).tolist()} LSB  "
          f"{_fmt_dps(a['drift_dps'])}  "
          f"(<= {vars.STABILITY_THRESHOLD} LSB): {'PASS' if a['drift_ok'] else 'FAIL'}")
    print(f"  Worst scalar mean:     {a['worst_gyro_dps']:.4f} °/s")
    print(f"  Noise OK all cycles:   {'YES' if a['noise_ok_all'] else 'NO'}")
    print(f"  Stable across reboots: {'YES' if a['imu_stable'] else 'NO'}")
    if a["any_needs_cal"]:
        print(f"  ⚠ Needs calibration (mean > 1.0 °/s on at least one cycle)")

    # --- ACC ---
    print(f"\n=== ACC ===")
    print(f"  Anti-drift X/Y/Z (ex. baseline): {a['acc_anti_drift'].astype(int).tolist()} LSB")
    print(f"  Worst ACC delta: {a['worst_acc_delta']:.1f} LSB "
          f"({a['worst_acc_delta'] / vars.ACC_1G_LSB * 1000:.2f} mg)")
    print(f"  ACC OK all cycles: {'YES' if a['acc_ok_all'] else 'NO'}")

    # --- TEMP ---
    print(f"\n=== TEMPERATURE ===")
    temps_str = ", ".join(f"{t:.0f}°C" if t is not None else "N/A" for t in a["temps"])
    print(f"  Per cycle:  [{temps_str}]")
    print(f"  Delta:      {a['temp_delta']:.1f}°C  ", end="")
    if a["temp_reliable"]:
        print(f"Coef: {a['temp_coef']:+.4f} °/s per °C  (measured)")
    else:
        print(f"(< {vars.TEMP_DELTA_MIN}°C — using datasheet: "
              f"{a['temp_coef']:+.4f} °/s per °C, "
              f"assumed rise: {a['flight_temp_rise']:.1f}°C over {a['flight_min']} min)")

    # --- FORECAST ---
    print(f"\n=== FLIGHT ERROR FORECAST ({a['flight_min']} min) ===")
    print(f"  Gyro drift:  {a['gyro_error_deg']:.2f}°  "
          f"(worst {a['worst_gyro_dps']:.4f} °/s x {a['flight_min']*60}s)")
    print(f"  ACC bias:    {a['acc_error_g']*1000:.2f} mg  ({a['worst_acc_delta']:.1f} LSB)")
    print(f"  Temp corr:   {a['temp_correction']:+.4f}°  "
          f"(coef {a['temp_coef']:+.4f} x {a['flight_temp_rise']:.1f}°C rise)")

    # --- ASCII GRAPH ---
    print(f"\n=== ACCUMULATED GYRO ERROR vs FLIGHT TIME ===")
    width    = 50
    max_time = a["flight_min"] * 60
    max_err  = a["worst_gyro_dps"] * max_time + a["temp_correction"]
    if max_err == 0:
        max_err = 1.0

    steps = 10
    print(f"  {'Time':>6}  {'Error':>7}")
    print(f"  {'(min)':>6}  {'(deg)':>7}")
    print(f"  {'-'*6}  {'-'*7}  {'-'*width}")
    for i in range(steps + 1):
        t_sec  = max_time * i / steps
        t_min  = t_sec / 60
        # температура росте лінійно з часом польоту
        temp_rise_at_t = a["flight_temp_rise"] * (i / steps)
        err = a["worst_gyro_dps"] * t_sec + abs(a["temp_coef"]) * temp_rise_at_t
        bar_len = int(err / max_err * width) if max_err > 0 else 0
        print(f"  {t_min:>6.1f}  {err:>7.2f}°  |{'█' * bar_len}")

    print(f"\n{'-'*70}")
    print(f"{'='*70}\n")

def main():
    detector = IMUdefectDetector()
    cycle_data = []
    offsets = []
    acc_global_offset = None
    acc_means = []
    is_connected = False

    try:
        print("Connecting to flight controller...")
        dl.connect()
        is_connected = True
        print("Connected.")
        time.sleep(vars.duration_after_start/1000)
        
        start_test = ask_yes_no(f"\nГотові почати збір даних? (Y/N): ")
        if not start_test:
            print("Збір даних скасовано. Відключаюсь.")
            return
        
        first_acc_samples = collect_acc_samples(vars.CALIBRATION_SAMPLES)
        base_acc_result = detector.test_acc_static(first_acc_samples)
        acc_global_offset = base_acc_result["mean_acc"].astype(float)
        print(f"\n+++ Current first ACC baseline mean {acc_global_offset.astype(int).tolist()}\n") # :.2f

        for cycle_index in range(vars.num_reboots):
            print(f"\n=== Boot cycle {cycle_index + 1}/{vars.num_reboots} ===")
            print("  Waiting for stabilization...")
            time.sleep(vars.duration_after_start/1000)

            should_continue = maybe_reboot(cycle_index)
            if not should_continue:
                print("Користувач скасував наступний reboot. Завершую тест.")
                break

            gyro_samples, acc_samples, baro_sample, mcu_result = collect_imu_samples(vars.CALIBRATION_SAMPLES)
            gyro_result = detector.test_single_boot(gyro_samples)
            acc_result = detector.test_acc_static(acc_samples)

            cycle_data.append({
                "gyro": gyro_result, 
                "acc": acc_result,
                "baro": baro_sample,
                "mcu": mcu_result
            })
            offsets.append(gyro_result["mean_lsb"])

            raw_acc_mean = acc_result["mean_acc"].astype(float)

            acc_delta = raw_acc_mean - acc_global_offset
            acc_means.append(raw_acc_mean)

            print_cycle_report(cycle_index, gyro_result, acc_result, acc_delta, baro_sample, mcu_result)

        if cycle_data:
            report_title = "FINAL REPORT" if len(cycle_data) == vars.num_reboots else "INTERMEDIATE REPORT"
            print_final_report(offsets, acc_means, cycle_data, title=report_title)
        else:
            print("Жодного повного циклу не завершено.")

    except KeyboardInterrupt:
        print("\nТест скасовано користувачем")
        if cycle_data:
            print_final_report(offsets, acc_means, cycle_data, title="INTERMEDIATE REPORT")
        else:
            print("Повних циклів ще не зібрано, проміжна статистика відсутня.")
    except Exception as exc:
        print(f"\n[ERROR] {exc}")
    finally:
        if is_connected:
            try:
                dl.disconnect()
                print("Disconnected.")
            except Exception:
                pass


if __name__ == "__main__":
    main()