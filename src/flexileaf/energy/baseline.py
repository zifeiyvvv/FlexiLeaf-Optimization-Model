"""No-storage baseline calculation."""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_no_storage_baseline(
    profile: pd.DataFrame,
) -> pd.DataFrame:
    required = {"load_kw", "pv_generation_kw"}
    missing = required.difference(profile.columns)
    if missing:
        raise ValueError(
            f"Energy profile is missing columns: {sorted(missing)}"
        )

    result = profile.copy()
    net_load_kw = (
        result["load_kw"].to_numpy(dtype=float)
        - result["pv_generation_kw"].to_numpy(dtype=float)
    )
    result["grid_import_kw"] = np.maximum(net_load_kw, 0.0)
    result["grid_export_kw"] = np.maximum(-net_load_kw, 0.0)
    result["battery_charge_kw"] = 0.0
    result["battery_discharge_kw"] = 0.0
    result["battery_soc_kwh"] = 0.0
    result["battery_mode"] = 0
    return result
