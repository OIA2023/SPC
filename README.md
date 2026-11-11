# Pallet Strategy Advisor — CHEP competition prototype

An interactive Streamlit app created from two uploaded student workbooks:

- `TCOv3.xlsx` — detailed bottom-up TCO for **current white exchange** and **CHEP pooling**, plus sponsor starting figures.
- `Pallet_Customer_Sustainability_V2.xlsx` — screening CO₂e calculations for **current white exchange**, **improved white exchange**, and **CHEP pooling**.

The deployed app runs independently of Excel. Original spreadsheets are **not included** in this package, to avoid publishing your team's source files by accident.

## What the app does

- Receives customer movements, cost drivers, route distances, and utilisation.
- Calculates three-option physical CO₂e and estimated timber mass per loaded movement.
- Calculates **two fully specified financial options** using the original TCO calculations (or the sponsor figures).
- Allows the user to supply an **improved-white TCO** or build an explicitly assumption-based improvement package.
- Plots annual TCO, tonnes CO₂e/year, per-trip break-even and one-way sensitivity charts.
- Provides low, typical, high and downside scenarios and a downloadable customer comparison CSV.
- Requires explicit feasibility confirmations and avoids claiming a final recommendation without evidence.

## For a beginner: simplest deployment route (no computer setup)

1. Unzip this folder.
2. Sign into [GitHub](https://github.com/) and create a **new repository**. Check whether the model inputs may be made public before using a public repository. Do not upload confidential customer figures or the original workbooks without permission.
3. Choose **Add file → Upload files**. Upload these files from the unzipped folder to the repository root: `app.py`, `model.py`, `model_defaults.json`, `requirements.txt` (and optionally `README.md` and `test_model.py`). The `.streamlit/config.toml` theme file is optional; you may skip it to simplify the process.
4. Open [Streamlit Community Cloud](https://share.streamlit.io/), sign in with GitHub and select **Create app**. Select your repository, main branch and `app.py` as the entrypoint. Select **Deploy**.
5. Open the resulting app URL. Change inputs and compare the output with the provided source spreadsheet under the same assumptions.

Official directions: [Deploy on Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

## To run on your own computer

Requirements: Python 3.10 or later.

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the local URL displayed in the terminal. To stop: press `Ctrl+C`.

## Run calculation parity tests

```bash
python test_model.py
```

Tests validate the saved workbook results:

| Source | Scenario | White annual TCO | Pooling annual TCO |
|---|---|---:|---:|
| TCOv3 | Low complexity | €541,050.75 | €889,292.50 |
| TCOv3 | Mixed/typical | €966,819.78 | €1,099,061.33 |
| TCOv3 | High complexity | €2,179,216.52 | €1,799,365.67 |
| TCOv3 | Downside | €1,021,388.49 | €1,106,731.90 |

| Source | CO₂e scenario | Current white | Improved white | Pooling |
|---|---|---:|---:|---:|
| Sustainability V2 | Low complexity | 0.597989 | 0.527402 | 0.771066 |
| Sustainability V2 | Mixed/typical | 1.468638 | 1.072072 | 0.927660 |
| Sustainability V2 | High complexity | 2.802342 | 1.716771 | 1.690391 |

CO₂e numbers are **kg CO₂e per loaded movement**, not verified CHEP lifecycle measurements.

## Important source reconciliation

**1. TCO financial mismatch.** The sponsor starting case provides **€843,003 white** versus **€909,439 pooling** at 265,000 movements. The team bottom-up base scenario gives **€966,819.78** versus **€1,099,061.33**. The tool presents them as **two alternatives**; it does not silently merge or calibrate them.

**2. Missing improved-white cost.** In the source sustainability workbook, `Customer Inputs!G25` is blank. The TCO workbook compares two options only. Consequently, improved white is **excluded from a financial ranking until a user supplies its annual cost or explicitly chooses a modelled improvement package**.

**3. Conflicting return-capacity assumptions.** TCOv3 uses 495 empties per truck. Sustainability V2 uses 26 floor positions × 15 empties/stack × 70% utilisation = 273 effectively allocated pallets. These need sponsor confirmation; don't equate them.

**4. CO₂e scope.** Sustainability V2 uses a Norwegian EPD proxy (production and end-of-life allocations), assumed repair process of 0.2 kg CO₂e/repair, 0.9 kg CO₂e/truck-km and a provisional 1 loaded movement per EPD loop. It excludes shared outbound freight. These are *scenario assumptions* — not a CHEP-verified LCA or ISO14083 transport inventory.

**5. Carbon price.** Defaults to **€0/t**. Optional price is a separate sensitivity, never an automatic cash saving or mandatory regulation cost.

**6. TCO scope.** The uploaded financial workbook sets working capital to zero and makes various proxy assumptions on losses, scraps, vouchers and downtime. Validate cost overlap and identify source/period for each input before using with a customer.

## Files

- `app.py` — Streamlit interface, input controls, charts and exports.
- `model.py` — auditable financial and environmental calculation formulas.
- `model_defaults.json` — the numerical scenario assumptions extracted from the two workbooks.
- `requirements.txt` — Python packages for the web app.
- `test_model.py` — quick verification against cached spreadsheet outputs.
- `.streamlit/config.toml` — optional theme settings.

## Notes for the competition presentation

The application is a **functioning, educational proof of concept**. Its strength is transparent comparative logic and sensitivity analysis. Claim neither that CO₂e outputs are independently verified CHEP results nor that it supplies legal, contractual or service-level advice. The final customer decision requires tested inputs, review of all three total costs, and suitability checks.
