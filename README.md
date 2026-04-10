# Sensor Drift Test Tool

This is a ad-hoc **basic test version** for tracking IMU sensor drift and defects.  
It collects raw IMU data (gyro, accelerometer, barometer) via MSP from Betaflight-based flight controllers and performs simple health-checks:

- Mean bias analysis across reboot cycles  
- Noise evaluation (STD, RMS, peak-to-peak)  
- Temperature correlation with sensor drift  
- PASS/FAIL checks for gyro stability and accelerometer level  

The tool is intended as a **diagnostic aid** — use it as-is, adapt it, or extend it for your own needs.

---

### Notes
- This is not a polished release, but a starting point for sensor validation experiments.  
- Results highlight bias drift, noise stability, and temperature sensitivity.  
- Useful for comparing different flight controllers or IMU chips.

---

### Support
If you find this project useful, consider to supporting **Ukraine**.  
Freedom and resilience matter — in every contribution...