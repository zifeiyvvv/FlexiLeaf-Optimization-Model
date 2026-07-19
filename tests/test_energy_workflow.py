from pathlib import Path

from flexileaf.energy.workflow import (
    EnergySimulationConfig,
    run_energy_simulation,
)
from flexileaf.site_analysis.offline import run_offline_site_analysis


def test_offline_site_to_energy_workflow(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    site = run_offline_site_analysis(
        project_root=project_root,
        output_root=tmp_path / "site",
    )
    result = run_energy_simulation(
        site_run_directory=site["output_directory"],
        building_rank=0,
        config=EnergySimulationConfig(
            peak_load_kw=350,
            daily_solar_mj_m2=18,
            battery_capacity_kwh=400,
            maximum_charge_kw=120,
            maximum_discharge_kw=120,
        ),
        output_root=tmp_path / "energy",
    )
    assert Path(result["dispatch_path"]).exists()
    assert Path(result["summary_path"]).exists()
    assert result["solver_diagnostics"][
        "maximum_balance_error_kw"
    ] < 1e-6
    assert result["optimised"]["objective_cost_hkd"] <= (
        result["baseline"]["objective_cost_hkd"] + 1e-6
    )
