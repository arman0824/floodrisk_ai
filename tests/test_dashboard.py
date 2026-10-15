from streamlit.testing.v1 import AppTest


def test_dashboard_renders_without_streamlit_runtime_exception() -> None:
    dashboard = AppTest.from_file("src/flood_command_center/app.py", default_timeout=30)
    dashboard.run()

    assert not dashboard.exception
