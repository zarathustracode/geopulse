"""Training and evaluation tooling for the GeoPulse road-damage detector.

Lives separately from the deployable inference CLI in src/geopulse_ml/.
This module is offline tooling — runs on Modal, produces weights + metrics,
hands off via files to the inference path.
"""
