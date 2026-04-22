# BTS7960 Motor Control

This folder contains a Raspberry Pi script to control a DC motor through a BTS7960 driver.

## File

- `bts7960_motor_cycle.py`: Runs the motor in a loop with:
  - ON for 1 second
  - OFF for 1 second
  - Total interval of 2 seconds

## GPIO Pins Used (BCM)

- `GPIO 18` -> `RPWM`
- `GPIO 19` -> `LPWM`
- `GPIO 23` -> `R_EN`
- `GPIO 24` -> `L_EN`
- `GND`     -> BTS7960 `GND` (common ground)

## Run

```bash
python3 motor/bts7960_motor_cycle.py
```

## Important

- Use an external power source for the motor connected to BTS7960 `B+` and `B-`.
- Share ground between Raspberry Pi and BTS7960.
- Do not power the motor from Raspberry Pi GPIO/5V rail.
