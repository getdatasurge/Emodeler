"""IDF generation + run pipeline (spec Ch 5). Builds one IDF per scenario
(baseline + N candidate films), submits to EnergyPlus, harvests output. When the
EnergyPlus binary is unavailable the runner falls back to a labeled analytical
estimate (engine/estimate.py) so the platform is demonstrable end-to-end."""
