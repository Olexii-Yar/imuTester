import time
import numpy as np
import definitions as vars

class IMUdefectDetector:

    # Constants Betaflight + stability check
    CALIBRATION_SAMPLES = vars.CALIBRATION_SAMPLES
    NOISE_THRESHOLD = vars.NOISE_THRESHOLD
    STABILITY_THRESHOLD = vars.STABILITY_THRESHOLD
    GYRO_SENSITIVITY = vars.GYRO_SENSITIVITY  # LSB per °/s
    NEEDS_CALIB_DPS = 0.5  # °/s - поріг для рекомендації калібрування
 
    def _lsb_to_dps(self, lsb_array):
        return np.round(lsb_array / self.GYRO_SENSITIVITY, 4)

    def test_single_boot(self, raw_samples):
        """
        Тест гіроскопа на одному boot циклі
        """
        mean_lsb = np.mean(raw_samples, axis=0).astype(int)
        min_xyz = np.min(raw_samples, axis=0)
        max_xyz = np.max(raw_samples, axis=0)
        noise_p2p_lsb = max_xyz - min_xyz
        std_lsb = np.std(raw_samples, axis=0)
        rms_lsb = np.sqrt(np.mean((raw_samples - mean_lsb)**2, axis=0))
        noise_ok = bool(np.all(noise_p2p_lsb <= self.NOISE_THRESHOLD))
        
        mean_dps = self._lsb_to_dps(mean_lsb)
        noise_p2p_dps = self._lsb_to_dps(noise_p2p_lsb)
        
        # ДОДАТИ:
        needs_calibration = bool(np.any(np.abs(mean_dps) > self.NEEDS_CALIB_DPS))
        
        return {
            'mean_lsb': np.round(mean_lsb).astype(int),
            'mean_dps': mean_dps,
            'noise_p2p_lsb': noise_p2p_lsb,
            'noise_p2p_dps': noise_p2p_dps,
            'std_lsb': std_lsb,
            'rms_lsb': rms_lsb,
            'noise_ok': noise_ok,
            'needs_calibration': needs_calibration,  # ← ВАЖЛИВО!
        }

    def check_orientation(self, mean_acc):
        """
        Перевірка орієнтації FC відносно очікуваної (з definitions.py)
        
        Returns:
            dict з результатами перевірки
        """
        axis_names = ['X', 'Y', 'Z']
        g_axis = vars.ACC_GRAVITY_AXIS
        g_dir = vars.ACC_GRAVITY_DIRECTION
        actual = mean_acc[g_axis]

        # Автодетект реальної орієнтації
        abs_acc = np.abs(mean_acc)
        dominant_idx = int(np.argmax(abs_acc))
        dominant_value = float(mean_acc[dominant_idx])
        direction = 'UP' if dominant_value > 0 else 'DOWN'
        detected = f"{axis_names[dominant_idx]}_{direction}"

        if abs(dominant_value) < vars.ACC_1G_LSB * 0.9:
            detected = 'UNKNOWN'

        expected_name = f"{axis_names[g_axis]}_{'UP' if g_dir > 0 else 'DOWN'}"
        matches_expected = (detected == expected_name)

        return {
            'expected': expected_name,
            'detected': detected,
            'matches': matches_expected,
            'gravity_axis': g_axis,
            'gravity_lsb': int(actual),
            'gravity_g': round(float(actual) / vars.ACC_1G_LSB, 3),
        }
    
    def test_acc_static(self, raw_samples):
        """
        Тест акселерометра в стані спокою
        """
        mean_acc = np.mean(raw_samples, axis=0)
        rms_acc = np.sqrt(np.mean(raw_samples.astype(np.float64)**2, axis=0))

        orientation_info = self.check_orientation(mean_acc)
        g_axis = vars.ACC_GRAVITY_AXIS

        if not orientation_info['matches']:
            print(f"  ⚠️  WARNING: FC orientation is {orientation_info['detected']}, "
                  f"expected {orientation_info['expected']}!")

        # Tilt: осі, які НЕ є gravity-віссю
        axis_names = ['X', 'Y', 'Z']
        non_gravity = [i for i in range(3) if i != g_axis]
        gravity_value = float(mean_acc[g_axis])
        tilt_details = []
        for i in non_gravity:
            lsb_val = float(mean_acc[i])
            deg_val = float(np.degrees(np.arctan2(lsb_val, gravity_value)))
            tilt_details.append({
                'axis': axis_names[i],
                'lsb': round(lsb_val, 2),
                'deg': round(deg_val, 2),
            })
        tilt_error = float(np.sqrt(mean_acc[non_gravity[0]]**2 + mean_acc[non_gravity[1]]**2))
        tilt_ok = bool(tilt_error <= vars.TILT_THRESHOLD)

        # Accuracy на gravity-осі
        g_error = float(abs(mean_acc[g_axis] - vars.ACC_EXPECTED_1G_VALUE))
        g_ok = bool(g_error <= vars.ACC_THRESHOLD)

        acc_ok = orientation_info['matches'] and tilt_ok and g_ok

        return {
            'mean_acc': np.round(mean_acc).astype(int),
            'rms_acc': rms_acc,
            'tilt_details': tilt_details,
            'tilt_error': round(tilt_error, 2),
            'g_error': round(g_error, 2),
            'tilt_ok': tilt_ok,
            'g_ok': g_ok,
            'acc_ok': acc_ok,
            'orientation': orientation_info,
        }