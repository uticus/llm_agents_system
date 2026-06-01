"""Unit tests for training/experiment_tracking: Tracker, NoOpTracker, InMemoryTracker."""

from __future__ import annotations

from llm_agents.training.experiment_tracking import InMemoryTracker, NoOpTracker, Tracker

# ---------------------------------------------------------------------------
# Tracker protocol
# ---------------------------------------------------------------------------


class TestTrackerProtocol:
    def test_noop_satisfies_protocol(self) -> None:
        assert isinstance(NoOpTracker(), Tracker)

    def test_in_memory_satisfies_protocol(self) -> None:
        assert isinstance(InMemoryTracker(), Tracker)

    def test_plain_class_satisfies_protocol(self) -> None:
        class MyTracker:
            def start_run(self, name, config=None) -> str:
                return "r1"

            def log_metrics(self, metrics, *, run_id=None, step=None) -> None:
                pass

            def log_params(self, params, *, run_id=None) -> None:
                pass

            def end_run(self, run_id: str) -> None:
                pass

        assert isinstance(MyTracker(), Tracker)

    def test_missing_method_fails_protocol(self) -> None:
        class Bad:
            def start_run(self, name, config=None) -> str:
                return "r"

        assert not isinstance(Bad(), Tracker)


# ---------------------------------------------------------------------------
# NoOpTracker
# ---------------------------------------------------------------------------


class TestNoOpTracker:
    def test_start_run_returns_string(self) -> None:
        tracker = NoOpTracker()
        run_id = tracker.start_run("run1")
        assert isinstance(run_id, str)
        assert len(run_id) > 0

    def test_each_run_unique_id(self) -> None:
        tracker = NoOpTracker()
        id1 = tracker.start_run("r1")
        id2 = tracker.start_run("r2")
        assert id1 != id2

    def test_log_metrics_no_error(self) -> None:
        tracker = NoOpTracker()
        run_id = tracker.start_run("r")
        tracker.log_metrics({"loss": 0.5}, run_id=run_id)  # should not raise

    def test_log_params_no_error(self) -> None:
        tracker = NoOpTracker()
        run_id = tracker.start_run("r")
        tracker.log_params({"lr": 1e-3}, run_id=run_id)

    def test_end_run_no_error(self) -> None:
        tracker = NoOpTracker()
        run_id = tracker.start_run("r")
        tracker.end_run(run_id)

    def test_log_metrics_without_run_id(self) -> None:
        tracker = NoOpTracker()
        tracker.log_metrics({"x": 1.0})

    def test_log_metrics_with_step(self) -> None:
        tracker = NoOpTracker()
        tracker.log_metrics({"loss": 0.3}, step=5)


# ---------------------------------------------------------------------------
# InMemoryTracker
# ---------------------------------------------------------------------------


class TestInMemoryTracker:
    def test_start_run_records_run(self) -> None:
        tracker = InMemoryTracker()
        tracker.start_run("myrun", config={"lr": 1e-3})
        assert len(tracker.runs) == 1
        assert tracker.runs[0]["name"] == "myrun"

    def test_start_run_returns_sequential_id(self) -> None:
        tracker = InMemoryTracker()
        id1 = tracker.start_run("r1")
        id2 = tracker.start_run("r2")
        assert id1 == "run-1"
        assert id2 == "run-2"

    def test_run_count(self) -> None:
        tracker = InMemoryTracker()
        assert tracker.run_count == 0
        tracker.start_run("r1")
        tracker.start_run("r2")
        assert tracker.run_count == 2

    def test_start_run_with_config(self) -> None:
        tracker = InMemoryTracker()
        tracker.start_run("r", config={"epochs": 3})
        assert tracker.runs[0]["config"] == {"epochs": 3}

    def test_start_run_no_config(self) -> None:
        tracker = InMemoryTracker()
        tracker.start_run("r")
        assert tracker.runs[0]["config"] == {}

    def test_log_metrics_recorded(self) -> None:
        tracker = InMemoryTracker()
        run_id = tracker.start_run("r")
        tracker.log_metrics({"loss": 0.5, "acc": 0.9}, run_id=run_id)
        assert len(tracker.metrics) == 1
        assert tracker.metrics[0]["metrics"]["loss"] == 0.5

    def test_log_metrics_with_step(self) -> None:
        tracker = InMemoryTracker()
        tracker.log_metrics({"loss": 0.3}, step=10)
        assert tracker.metrics[0]["step"] == 10

    def test_log_params_recorded(self) -> None:
        tracker = InMemoryTracker()
        run_id = tracker.start_run("r")
        tracker.log_params({"lr": 1e-4}, run_id=run_id)
        assert len(tracker.params) == 1
        assert tracker.params[0]["params"]["lr"] == 1e-4

    def test_end_run_recorded(self) -> None:
        tracker = InMemoryTracker()
        run_id = tracker.start_run("r")
        tracker.end_run(run_id)
        assert run_id in tracker.ended

    def test_multiple_runs(self) -> None:
        tracker = InMemoryTracker()
        id1 = tracker.start_run("r1")
        id2 = tracker.start_run("r2")
        tracker.log_metrics({"loss": 0.4}, run_id=id1)
        tracker.log_metrics({"loss": 0.3}, run_id=id2)
        tracker.end_run(id1)
        tracker.end_run(id2)
        assert tracker.run_count == 2
        assert len(tracker.metrics) == 2
        assert len(tracker.ended) == 2
