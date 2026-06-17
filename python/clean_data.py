import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"

df = pd.read_csv(DATA / "nvda_calls_raw.csv")

df["Volume"] = df["Volume"].astype(str).str.replace(",", "").astype(float)
df["Open Interest"] = df["Open Interest"].astype(str).str.replace(",", "").astype(float)

df.to_csv(DATA / "nvda_calls_clean.csv", index=False)