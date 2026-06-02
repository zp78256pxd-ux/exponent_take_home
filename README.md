 Bus Charging Scheduler (Exponent Take‑Home)
A small fleet scheduler for electric buses traveling **Bengaluru ↔ Kochi** with four charging stations (**A, B, C, D**). Each station has **one charger** and each charge is a **25 minute full charge** (per the assignment spec).
The app lets you run a fast baseline scheduler and an optional fleet optimization pass, then inspect:
- per‑bus timelines (travel / wait / charge / arrive)
- per‑station utilization (who charged when)
- total fleet wait and compute cost
---
## Quick start
```bash
pip install -r requirements.txt
streamlit run app.py
\
