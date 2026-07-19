from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_initial_page_has_no_exception():
    project_root = Path(__file__).resolve().parents[1]
    app = AppTest.from_file(
        str(project_root / "streamlit_app.py")
    ).run(timeout=20)
    assert len(app.exception) == 0
    assert any(
        "FlexiLeaf Urban Solar Explorer" in title.value
        for title in app.title
    )
