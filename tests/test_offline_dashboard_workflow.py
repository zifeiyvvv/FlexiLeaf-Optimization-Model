from pathlib import Path

from flexileaf.dashboard.artifacts import load_run_artifacts
from flexileaf.site_analysis.offline import run_offline_site_analysis


def test_offline_workflow_writes_dashboard_contract(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    summary = run_offline_site_analysis(
        project_root=project_root,
        output_root=tmp_path,
    )
    assert summary["mode"] == "offline_demo"

    artifacts = load_run_artifacts(summary["output_directory"])
    assert not artifacts["buildings"].empty
    assert not artifacts["top_buildings"].empty
    assert artifacts["geojson"]["type"] == "FeatureCollection"
