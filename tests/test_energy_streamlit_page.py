from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_energy_page_initial_render_has_no_exception():
    project_root = Path(__file__).resolve().parents[1]
    page = AppTest.from_file(
        str(project_root / "pages" / "2_Energy_Optimisation.py")
    ).run(timeout=25)
    assert len(page.exception) == 0
    assert any(
        "Energy Optimisation" in title.value
        for title in page.title
    )
