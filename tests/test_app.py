from streamlit.testing.v1 import AppTest
from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"

def load_app():
    return AppTest.from_file(APP_PATH).run(timeout=30)

def test_app_loads_without_exception():
    app = load_app()

    assert not app.exception
    assert len(app.slider) == 1
    assert app.slider[0].value == 0.25
    assert len(app.multiselect) == 1
    assert len(app.metric) >= 4

    metric_labels = {
        metric.label
        for metric in app.metric
    }
    assert {
        "Total maneuver fuel",
        "Reserve score",
        "Valid plans",
        "Current objective",
    } <= metric_labels


def test_fuel_only_slider_updates_recommendation():
    app = load_app()

    app.slider[0].set_value(0.0)
    app.run(timeout=30)

    assert not app.exception

    metrics = {
        metric.label: metric.value
        for metric in app.metric
    }
    assert metrics["Total maneuver fuel"] == "3.00"


def test_infeasible_availability_is_reported():
    app = load_app()

    app.multiselect[0].set_value(["A1", "B1"])
    app.run(timeout=30)

    assert not app.exception
    assert app.error
    assert "No feasible agreement" in app.error[0].value