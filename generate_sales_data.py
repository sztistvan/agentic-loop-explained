"""
Generate a synthetic sales dataset with a hidden story for the agent to discover.

The planted story:
  * The East region underperforms in Q3 2026.
  * Root cause: the "Pro" product line in East had a stockout from mid-July
    (units collapse, and there are many orders with status "backordered").
  * Meanwhile West ran a discount campaign in Q3, so its revenue grew
    but its margin dropped -- a nice secondary insight.
  * A little mess is added (duplicate rows, missing values, a typo'd region)
    so the agent has to clean before analysing.
"""
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

REGIONS = ["North", "South", "East", "West"]
PRODUCTS = {  # product line -> (base price, unit cost)
    "Basic": (49.0, 22.0),
    "Plus": (129.0, 61.0),
    "Pro": (349.0, 170.0),
}
CHANNELS = ["Online", "Retail", "Partner"]

rows = []
order_id = 100_000
for day in pd.date_range("2026-01-01", "2026-09-30", freq="D"):
    for region in REGIONS:
        n_orders = rng.poisson(14)
        for _ in range(n_orders):
            product = rng.choice(list(PRODUCTS), p=[0.5, 0.33, 0.17])
            price, cost = PRODUCTS[product]
            units = int(rng.integers(1, 6))
            discount = float(rng.choice([0, 0, 0, 0.05, 0.10]))
            status = "fulfilled"

            # Story 1: East "Pro" stockout from mid-July onward
            if region == "East" and product == "Pro" and day >= pd.Timestamp("2026-07-15"):
                if rng.random() < 0.9:
                    status = "backordered"
                    units = 0

            # Story 2: West discount campaign in Q3
            if region == "West" and day >= pd.Timestamp("2026-07-01"):
                discount = float(rng.choice([0.20, 0.25, 0.30]))
                units += int(rng.integers(0, 3))

            revenue = round(units * price * (1 - discount), 2)
            rows.append(
                {
                    "order_id": order_id,
                    "order_date": day.date().isoformat(),
                    "region": region,
                    "channel": rng.choice(CHANNELS, p=[0.55, 0.30, 0.15]),
                    "product_line": product,
                    "units": units,
                    "unit_price": price,
                    "discount": discount,
                    "revenue": revenue,
                    "cogs": round(units * cost, 2),
                    "status": status,
                }
            )
            order_id += 1

df = pd.DataFrame(rows)

# --- Add realistic mess -------------------------------------------------
dupes = df.sample(40, random_state=1)
df = pd.concat([df, dupes], ignore_index=True)                      # duplicates
df.loc[df.sample(25, random_state=2).index, "channel"] = np.nan      # missing values
df.loc[df.sample(15, random_state=3).index, "region"] = "east "      # dirty labels
df = df.sample(frac=1, random_state=4).reset_index(drop=True)        # shuffle

out = Path(__file__).parent / "data" / "sales.csv"
out.parent.mkdir(exist_ok=True)
df.to_csv(out, index=False)
print(f"Wrote {len(df):,} rows to {out}")
