"""
Generate a synthetic factory sensor dataset (a time series) with a hidden story.

Eight machines on two production lines report every 5 minutes for three weeks
(2026-03-02 to 2026-03-22): temperature, vibration, pressure, power draw and
units produced. About 48,000 rows.

The planted story:
  * Machine M06 (Line 2) has a failing bearing. From 12 March its vibration creeps
    up, from 15 March its temperature follows, and it stops on 18 March at 14:35
    (status "fault") until the repair on 19 March at 06:00.
  * The night shift (22:00-06:00) produces about 18% fewer units than the others.
  * Machines idle for planned maintenance on Sundays 06:00-08:00.

The mess a careful analyst should notice:
  * All machines have a gap with no rows from 14 March 22:00 to 15 March 02:30
    (a network outage).
  * M03's pressure sensor is stuck at a constant 6.02 for two days (9-11 March).
  * From 20 March M08 reports temperature in Fahrenheit although the column
    is named temperature_c.
  * About 0.5% of M05's temperature readings are missing, 30 vibration readings
    are one-off spikes, and 40 rows are duplicated.

Usage:
    python generate_factory_data.py              # writes data/factory_sensors.csv
    python generate_factory_data.py --out my.csv --seed 3
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

MACHINES = [  # id, line, temperature offset, vibration offset, speed factor
    ("M01", "Line 1", 0.0, 0.00, 1.00),
    ("M02", "Line 1", 1.5, 0.05, 0.95),
    ("M03", "Line 1", -1.0, -0.05, 1.05),
    ("M04", "Line 1", 0.5, 0.10, 1.00),
    ("M05", "Line 2", 2.0, 0.00, 0.90),
    ("M06", "Line 2", 0.0, 0.05, 1.00),
    ("M07", "Line 2", -0.5, -0.10, 1.10),
    ("M08", "Line 2", 1.0, 0.00, 1.00),
]


def ts(text: str) -> pd.Timestamp:
    return pd.Timestamp(text)


def machine_frame(rng, times, machine_id, line, temp_off, vib_off, speed) -> pd.DataFrame:
    n = len(times)
    hour = times.hour + times.minute / 60
    shift = np.where((hour >= 6) & (hour < 14), "Day", np.where((hour >= 14) & (hour < 22), "Evening", "Night"))

    temp = 62 + temp_off + 1.5 * np.sin(2 * np.pi * hour / 24) + rng.normal(0, 1.0, n)
    vib = 2.0 + vib_off + rng.normal(0, 0.12, n)
    pressure = 6.0 + rng.normal(0, 0.08, n)
    rate = 22 * speed * np.where(shift == "Night", 0.82, 1.0)  # story: weaker night shift
    status = np.full(n, "running", dtype=object)
    status[(times.day_of_week == 6) & (hour >= 6) & (hour < 8)] = "maintenance"

    if machine_id == "M06":  # story: failing bearing
        start, fail, repaired, hot = ts("2026-03-12"), ts("2026-03-18 14:35"), ts("2026-03-19 06:00"), ts("2026-03-15")
        wear = np.clip((times - start) / (fail - start), 0, 1)
        wear = np.where(times >= fail, 0, wear)
        heat = np.where(times >= fail, 0, np.clip((times - hot) / (fail - hot), 0, 1))
        vib = vib + 4.5 * wear**1.5
        temp = temp + 14 * heat
        rate = rate * (1 - 0.12 * wear)
        status[(times >= fail) & (times < repaired)] = "fault"

    running = status == "running"
    units = np.where(running, rng.poisson(rate), 0)
    power = np.where(running, 18 + 0.08 * (temp - 62) + rng.normal(0, 0.6, n),
                     np.where(status == "maintenance", 2.5, 1.0) + rng.normal(0, 0.1, n))
    temp = np.where(running, temp, 30 + rng.normal(0, 1.0, n))   # idle machines cool down
    vib = np.where(running, vib, 0.3 + rng.normal(0, 0.05, n))
    pressure = np.where(running, pressure, 0.5 + rng.normal(0, 0.05, n))

    if machine_id == "M03":  # mess: stuck pressure sensor (a constant value, no noise)
        stuck = (times >= ts("2026-03-09 10:00")) & (times < ts("2026-03-11 10:00")) & running
        pressure = np.where(stuck, 6.02, pressure)

    if machine_id == "M08":  # mess: Fahrenheit after a "configuration change"
        temp = np.where(times >= ts("2026-03-20"), temp * 9 / 5 + 32, temp)

    return pd.DataFrame({
        "timestamp": times, "machine_id": machine_id, "line": line, "shift": shift,
        "temperature_c": temp.round(2), "vibration_mm_s": vib.round(3), "pressure_bar": pressure.round(3),
        "power_kw": power.round(2), "units_produced": units, "status": status,
    })


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic factory sensor dataset")
    parser.add_argument("--out", default=str(Path(__file__).parent / "data" / "factory_sensors.csv"))
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    times = pd.date_range("2026-03-02 00:00", "2026-03-22 23:55", freq="5min")
    df = pd.concat([machine_frame(rng, times, *m) for m in MACHINES], ignore_index=True)

    # --- Add realistic mess -------------------------------------------------
    outage = (df["timestamp"] >= ts("2026-03-14 22:00")) & (df["timestamp"] < ts("2026-03-15 02:30"))
    df = df[~outage].reset_index(drop=True)                                        # network outage
    m05 = df.index[df["machine_id"] == "M05"]
    df.loc[rng.choice(m05, size=int(len(m05) * 0.005), replace=False), "temperature_c"] = np.nan
    running = df.index[df["status"] == "running"]
    df.loc[rng.choice(running, size=30, replace=False), "vibration_mm_s"] *= 3     # one-off spikes
    df = pd.concat([df, df.sample(40, random_state=1)], ignore_index=True)         # duplicates
    df = df.sort_values(["timestamp", "machine_id"], kind="stable").reset_index(drop=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Wrote {len(df):,} rows to {out}")


if __name__ == "__main__":
    main()
