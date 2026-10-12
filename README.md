# UVR Predictor V6

V6 adds a calibration/sanity layer on top of V5:
- Poisson model plus deterministic 50,000-run Monte Carlo cross-check.
- Bookmaker no-vig probabilities when both sides of a market are supplied (and all 1X2 odds for 1X2).
- Reliability-weighted probability calibration: adjusted = market + reliability × (raw model - market).
- Raw Model, Market No-Vig, Adjusted Probability, Raw Fair, Adjusted Fair, Raw EV and Adjusted EV shown separately.
- Signal and 1/4 Kelly use **Adjusted EV**, not Raw EV.
- Model/market divergence of 10 percentage points or more is flagged REVIEW.
- Port 8765, separate from the crypto app on 8000.

Run `run.bat` on Windows. Use `STOP_APP.bat` to stop the server.
