"""Unit tests for training/fine_tuning: FineTuneConfig, FineTuneResult, FineTuner."""

from __future__ import annotations

import pytest

from llm_agents.training.fine_tuning import FineTuneConfig, FineTuner, FineTuneResult

# ---------------------------------------------------------------------------
# Helpers — fake trainer
# ---------------------------------------------------------------------------


class _FakeTrainer:
    """Minimal fake trainer for tests."""

    def __init__(self, metrics: dict | None = None) -> None:
        self._metrics = metrics or {"train_loss": 0.42, "eval_loss": 0.50}
        self.trained = False
        self.saved_to: str | None = None

    def train(self) -> None:
        self.trained = True

    def save_model(self, path: str) -> None:
        self.saved_to = path

    def get_metrics(self) -> dict:
        return dict(self._metrics)


def _fake_factory(metrics: dict | None = None):
    """Return a factory callable that creates a _FakeTrainer."""
    created: list[_FakeTrainer] = []

    def factory(config, dataset):
        t = _FakeTrainer(metrics)
        created.append(t)
        return t

    factory.created = created  # type: ignore[attr-defined]
    return factory


class _FakeTracker:
    """Minimal fake experiment tracker."""

    def __init__(self) -> None:
        self.runs: list[dict] = []
        self.logged: list[dict] = []
        self.ended: list[str] = []
        self._run_counter = 0

    def start_run(self, name: str, config: dict) -> str:
        self._run_counter += 1
        run_id = f"run-{self._run_counter}"
        self.runs.append({"id": run_id, "name": name, "config": config})
        return run_id

    def log_metrics(self, metrics: dict, *, run_id: str | None = None) -> None:
        self.logged.append({"run_id": run_id, "metrics": metrics})

    def end_run(self, run_id: str) -> None:
        self.ended.append(run_id)


class _FakeModelHub:
    """Minimal fake model hub."""

    def __init__(self) -> None:
        self.registered: list[dict] = []

    def register(self, name: str, path: str, metadata: dict | None = None) -> str:
        version = f"v{len(self.registered) + 1}"
        self.registered.append({"name": name, "path": path, "version": version})
        return version


# ---------------------------------------------------------------------------
# FineTuneConfig
# ---------------------------------------------------------------------------


class TestFineTuneConfig:
    def test_required_fields(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2")
        assert cfg.base_model == "gpt2"

    def test_defaults(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2")
        assert cfg.num_epochs == 1
        assert cfg.batch_size == 4
        assert cfg.lora_r == 8
        assert cfg.output_dir == "output"
        assert cfg.fp16 is False
        assert cfg.extra == {}

    def test_full_construction(self) -> None:
        cfg = FineTuneConfig(
            base_model="llama-7b",
            output_dir="/tmp/run1",
            num_epochs=3,
            batch_size=8,
            learning_rate=1e-4,
            lora_r=16,
            fp16=True,
        )
        assert cfg.num_epochs == 3
        assert cfg.lora_r == 16
        assert cfg.fp16 is True


# ---------------------------------------------------------------------------
# FineTuneResult
# ---------------------------------------------------------------------------


class TestFineTuneResult:
    def test_defaults(self) -> None:
        r = FineTuneResult(model_path="/tmp/out")
        assert r.version_id is None
        assert r.metrics == {}
        assert r.config is None

    def test_full_construction(self) -> None:
        cfg = FineTuneConfig(base_model="x")
        r = FineTuneResult(
            model_path="/tmp/out",
            version_id="v1",
            metrics={"loss": 0.3},
            config=cfg,
        )
        assert r.version_id == "v1"
        assert r.metrics["loss"] == 0.3
        assert r.config is cfg


# ---------------------------------------------------------------------------
# FineTuner — basic flow
# ---------------------------------------------------------------------------


class TestFineTunerBasic:
    def test_run_returns_result(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2", output_dir="/tmp/out")
        factory = _fake_factory()
        tuner = FineTuner(cfg, trainer_factory=factory)
        result = tuner.run(dataset=["a", "b"])
        assert isinstance(result, FineTuneResult)

    def test_trainer_train_called(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2", output_dir="/tmp/out")
        factory = _fake_factory()
        tuner = FineTuner(cfg, trainer_factory=factory)
        tuner.run(dataset=[])
        assert factory.created[0].trained is True

    def test_trainer_save_model_called_with_output_dir(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2", output_dir="/tmp/myout")
        factory = _fake_factory()
        tuner = FineTuner(cfg, trainer_factory=factory)
        tuner.run(dataset=[])
        assert factory.created[0].saved_to == "/tmp/myout"

    def test_result_model_path_matches_output_dir(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2", output_dir="/tmp/out")
        tuner = FineTuner(cfg, trainer_factory=_fake_factory())
        result = tuner.run(dataset=[])
        assert result.model_path == "/tmp/out"

    def test_result_metrics_from_trainer(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2")
        factory = _fake_factory(metrics={"loss": 0.25})
        tuner = FineTuner(cfg, trainer_factory=factory)
        result = tuner.run(dataset=[])
        assert result.metrics["loss"] == 0.25

    def test_result_config_attached(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2")
        tuner = FineTuner(cfg, trainer_factory=_fake_factory())
        result = tuner.run(dataset=[])
        assert result.config is cfg

    def test_no_tracker_no_version_id(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2")
        tuner = FineTuner(cfg, trainer_factory=_fake_factory())
        result = tuner.run(dataset=[])
        assert result.version_id is None


# ---------------------------------------------------------------------------
# FineTuner — with tracker
# ---------------------------------------------------------------------------


class TestFineTunerWithTracker:
    def test_tracker_start_run_called(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2")
        tracker = _FakeTracker()
        tuner = FineTuner(cfg, trainer_factory=_fake_factory(), tracker=tracker)
        tuner.run(dataset=[])
        assert len(tracker.runs) == 1

    def test_tracker_run_name_contains_model(self) -> None:
        cfg = FineTuneConfig(base_model="llama-7b")
        tracker = _FakeTracker()
        tuner = FineTuner(cfg, trainer_factory=_fake_factory(), tracker=tracker)
        tuner.run(dataset=[])
        assert "llama-7b" in tracker.runs[0]["name"]

    def test_tracker_log_metrics_called(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2")
        tracker = _FakeTracker()
        factory = _fake_factory(metrics={"loss": 0.5})
        tuner = FineTuner(cfg, trainer_factory=factory, tracker=tracker)
        tuner.run(dataset=[])
        assert len(tracker.logged) == 1
        assert tracker.logged[0]["metrics"]["loss"] == 0.5

    def test_tracker_end_run_called(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2")
        tracker = _FakeTracker()
        tuner = FineTuner(cfg, trainer_factory=_fake_factory(), tracker=tracker)
        tuner.run(dataset=[])
        assert len(tracker.ended) == 1

    def test_tracker_end_run_called_even_on_error(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2")
        tracker = _FakeTracker()

        def failing_factory(config, dataset):
            class BadTrainer:
                def train(self):
                    raise RuntimeError("boom")

                def save_model(self, path):
                    pass

                def get_metrics(self):
                    return {}

            return BadTrainer()

        tuner = FineTuner(cfg, trainer_factory=failing_factory, tracker=tracker)
        with pytest.raises(RuntimeError):
            tuner.run(dataset=[])
        # end_run is called in finally block
        assert len(tracker.ended) == 1


# ---------------------------------------------------------------------------
# FineTuner — with model hub
# ---------------------------------------------------------------------------


class TestFineTunerWithModelHub:
    def test_version_id_not_none_when_hub_provided(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2")
        hub = _FakeModelHub()
        tuner = FineTuner(cfg, trainer_factory=_fake_factory(), model_hub=hub)
        result = tuner.run(dataset=[])
        assert result.version_id is not None


# ---------------------------------------------------------------------------
# FineTuner — default factory requires extras
# ---------------------------------------------------------------------------


class TestFineTunerDefaultFactory:
    def test_default_factory_raises_import_error_without_extras(self) -> None:
        cfg = FineTuneConfig(base_model="gpt2")
        tuner = FineTuner(cfg)  # no trainer_factory; uses default stub
        with pytest.raises((ImportError, NotImplementedError)):
            tuner.run(dataset=[])
