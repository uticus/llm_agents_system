# training/experiment_tracking

## Overview

The `training/experiment_tracking` module defines the interface and lightweight implementations for experiment tracking in ML training workflows. It provides a structural `Tracker` Protocol that abstracts away any specific tracking backend (MLflow, Weights & Biases, DVC, or custom), a `NoOpTracker` that silently discards all calls for use when tracking is not needed, an `InMemoryTracker` that records all calls in plain Python lists for use in unit tests and local debugging, and `MLflowTracker` — a production-ready adapter for the MLflow experiment tracking platform. The module exists to give the `FineTuner` (and any other training component) a stable, backend-agnostic interface for recording hyperparameters and metrics, without forcing a dependency on any specific tracking library. Because the `Tracker` is structural (`@runtime_checkable`), any existing MLflow or W&B wrapper that happens to expose matching method signatures qualifies automatically.

`MLflowTracker` requires the `training` extra (`pip install 'llm-agents-system[training]'`); the rest of the module imports cleanly with no extras installed.

---

## Public API

### Exported symbols

| Name | Kind | Description |
|---|---|---|
| `Tracker` | Protocol | Structural interface for experiment trackers. |
| `NoOpTracker` | class | Silent no-operation tracker; safe default when tracking is not needed. |
| `InMemoryTracker` | class | In-memory tracker that records all calls for test assertions. |
| `MLflowTracker` | class | Production MLflow adapter using the fluent API (requires `training` extra). |

### Tracker Protocol

```
start_run(
    name: str,
    config: dict[str, Any] | None = None,
) -> str                            # returns opaque run_id

log_metrics(
    metrics: dict[str, float],
    *,
    run_id: str | None = None,
    step: int | None = None,
) -> None

log_params(
    params: dict[str, Any],
    *,
    run_id: str | None = None,
) -> None

end_run(run_id: str) -> None
```

Any object implementing all four methods satisfies the `Tracker` protocol without inheriting. `@runtime_checkable` enables `isinstance` checks.

### NoOpTracker

All four methods are implemented. `start_run` returns `str(uuid.uuid4())` so callers receive a usable run ID even though nothing is recorded. The other three methods are no-ops.

```
NoOpTracker()

start_run(name, config=None) -> str
log_metrics(metrics, *, run_id=None, step=None) -> None
log_params(params, *, run_id=None) -> None
end_run(run_id) -> None
```

### InMemoryTracker

```
InMemoryTracker()

# Attributes populated by calls:
runs:    list[dict]   # [{id, name, config}, ...]
metrics: list[dict]   # [{run_id, step, metrics}, ...]
params:  list[dict]   # [{run_id, params}, ...]
ended:   list[str]    # [run_id, ...]

# Property:
run_count -> int      # len(self.runs)

# Methods:
start_run(name, config=None) -> str   # returns "run-{counter}"
log_metrics(metrics, *, run_id=None, step=None) -> None
log_params(params, *, run_id=None) -> None
end_run(run_id) -> None
```

`start_run` uses a monotonic integer counter to generate predictable run IDs (`"run-1"`, `"run-2"`, ...) for deterministic test assertions.

### MLflowTracker

```
MLflowTracker(
    tracking_uri: str | None = None,   # MLflow tracking server URI; None = local default
    experiment_name: str = "default",  # MLflow experiment to log runs into
)

# Private helper (called by every public method):
_get_mlflow() -> mlflow_module   # imports mlflow, sets URI + experiment, returns module

# Methods:
start_run(name: str, config: dict[str, Any] | None = None) -> str
    # Calls mlflow.start_run(run_name=name).
    # If config is non-empty, calls mlflow.log_params with stringified values.
    # Returns run.info.run_id.

log_metrics(metrics: dict[str, float], *, run_id: str | None = None, step: int | None = None) -> None
    # Calls mlflow.log_metrics(metrics, step=step).  step omitted if None.
    # run_id is accepted for protocol compatibility but not forwarded (MLflow uses active run).

log_params(params: dict[str, Any], *, run_id: str | None = None) -> None
    # Calls mlflow.log_params with all values stringified.
    # run_id accepted for protocol compatibility; not forwarded.

end_run(run_id: str) -> None
    # Calls mlflow.end_run() with no arguments (MLflow closes the active run).
    # run_id is accepted for protocol compatibility but not forwarded.
```

**Import error**: if `mlflow` is not installed and any method is called, an `ImportError` is raised with an actionable install message.

**Tracking URI**: set on every `_get_mlflow()` call if `tracking_uri` is not `None`. For a local tracking server this is typically `http://localhost:5000`. For `None`, MLflow uses its default local filesystem store.

**Experiment**: `mlflow.set_experiment(experiment_name)` is called on every `_get_mlflow()` invocation, ensuring the experiment context is set before any MLflow API call.

**Param stringification**: all values in `config` (passed to `start_run`) and `params` (passed to `log_params`) are converted to `str` before being sent to MLflow. MLflow requires string values; this conversion prevents `TypeError` for numeric hyperparameters.

---

## Architecture

### Conceptual view

```
     Training orchestration (FineTuner, etc.)
                  |
                  |  uses
                  v
           Tracker (Protocol)
          /        |         \          \
   NoOpTracker  InMemory-  MLflow-      Custom adapter
                Tracker    Tracker      (user-defined)
                           (this module)
```

The protocol layer decouples training logic from tracking implementation. Training orchestrators code against `Tracker`; concrete backends are injected at construction time.

### Data flow — MLflowTracker

1. **Construction**: `MLflowTracker(tracking_uri=..., experiment_name=...)` stores both values but does not import or call MLflow.
2. **`_get_mlflow()`**: lazily imports `mlflow`, optionally calls `set_tracking_uri`, always calls `set_experiment`, returns the module. Called by every public method — any method can be the first to trigger the import.
3. **`start_run(name, config)`**: calls `mlflow.start_run(run_name=name)`, extracts `run.info.run_id`, calls `mlflow.log_params({k: str(v) for k, v in config.items()})` if `config` is non-empty, returns `run_id`.
4. **`log_metrics(metrics, step=step)`**: calls `mlflow.log_metrics(metrics)` or `mlflow.log_metrics(metrics, step=step)` depending on whether `step` is provided.
5. **`log_params(params)`**: stringifies values, calls `mlflow.log_params(...)`.
6. **`end_run(run_id)`**: calls `mlflow.end_run()` with no arguments (MLflow fluent API closes the currently active run).

### Data flow — InMemoryTracker

1. `start_run(name, config)` increments `_counter`, constructs run ID `"run-{counter}"`, appends `{"id": run_id, "name": name, "config": config or {}}` to `self.runs`, and returns the run ID.
2. `log_metrics(metrics, run_id=run_id, step=step)` appends `{"run_id": run_id, "step": step, "metrics": dict(metrics)}` to `self.metrics`. Both `run_id` and `step` may be `None`.
3. `log_params(params, run_id=run_id)` appends `{"run_id": run_id, "params": dict(params)}` to `self.params`.
4. `end_run(run_id)` appends `run_id` to `self.ended`.

All recorded data is accessible directly through the public list attributes for inspection in test assertions.

### Key abstractions

**Tracker as a Protocol** rather than an abstract base class has two consequences. First, external adapters (MLflow `MlflowClient`, W&B `wandb.run` wrappers) can satisfy the interface without modification, as long as their method signatures match. Second, `isinstance(obj, Tracker)` works at runtime thanks to `@runtime_checkable`, allowing training orchestrators to validate injected dependencies.

**Separation of concerns**: the protocol separates `log_metrics` (for scalar training metrics at a specific step) from `log_params` (for hyperparameters that are set once per run). Many tracking backends treat these differently: metrics are time-series, params are run-level constants.

**MLflow fluent API vs. client API**: `MLflowTracker` uses the fluent (global) API (`mlflow.start_run`, `mlflow.log_metrics`, etc.) rather than `MlflowClient`. The fluent API is the idiomatic way to log to a single active run within a process, which matches the `FineTuner` use case. Callers that need multiple concurrent runs should use separate `MLflowTracker` instances or a direct `MlflowClient` adapter.

**NoOpTracker vs None**: the `FineTuner` could accept `None` as "no tracking" (and does, via a `if self._tracker is not None` guard). However, having `NoOpTracker` available means callers can also explicitly pass a no-op tracker without needing to know about the null-check pattern. Both approaches are supported.

**InMemoryTracker for tests**: the design choice to expose raw lists (`runs`, `metrics`, `params`, `ended`) rather than providing query methods keeps the test tracker simple and flexible. Test assertions can use standard Python list operations and comprehensions to verify any aspect of the recorded tracking calls.

---

## Design decisions and tradeoffs

- **Decision**: The `Tracker` Protocol uses keyword-only arguments (`*`) for `run_id` and `step` in `log_metrics` and `log_params`. **Why**: Makes call sites readable and prevents positional-argument mistakes when mixing metrics with run IDs. **Tradeoff**: Protocol implementors must also use keyword-only syntax in their signatures, which adds a minor constraint.

- **Decision**: `NoOpTracker.start_run` returns a real UUID rather than a constant or empty string. **Why**: Callers that store the run ID and pass it to subsequent calls (e.g., `log_metrics(metrics, run_id=run_id)`) should receive a valid non-empty string, even in no-op mode. A constant like `""` would make it harder to distinguish between "tracking is disabled" and "tracking errored". **Tradeoff**: A new UUID is generated on every call, which is slightly more work than returning a constant.

- **Decision**: `InMemoryTracker` uses a sequential integer counter (`"run-1"`, `"run-2"`) rather than UUIDs for run IDs. **Why**: Predictable run IDs make test assertions cleaner: `assert tracker.runs[0]["id"] == "run-1"` is clearer than asserting on a UUID. **Tradeoff**: IDs are only unique within a single `InMemoryTracker` instance; across test runs a fresh instance must be constructed.

- **Decision**: `metrics` dicts passed to `log_metrics` and `params` dicts passed to `log_params` are copied via `dict(metrics)` before storing. **Why**: If the caller mutates the dict after the call, the stored copy is not affected, preventing subtle test failures caused by shared mutable state. **Tradeoff**: Shallow copy; nested mutable values (e.g., a list inside a metrics dict) are still shared.

- **Decision**: `MLflowTracker` uses the MLflow fluent API (`mlflow.start_run` / `mlflow.log_*` / `mlflow.end_run`) rather than `MlflowClient`. **Why**: The fluent API is the idiomatic way to log a single training run per process, which covers the overwhelming majority of `FineTuner` use cases. It requires significantly less boilerplate than the object-based client API. **Tradeoff**: Only one run can be active at a time per process; callers that need concurrent multi-run tracking need separate instances or a `MlflowClient`-based adapter.

- **Decision**: `MLflowTracker` accepts `run_id` in `log_metrics`, `log_params`, and `end_run` but does not forward it to MLflow. **Why**: The `Tracker` protocol requires those keyword arguments for compatibility with trackers that manage run context by ID (e.g., `InMemoryTracker`). MLflow's fluent API tracks run context implicitly; passing a `run_id` to `log_metrics` would require switching to the client API and restructuring all method signatures. **Tradeoff**: If a caller passes a `run_id` to `MLflowTracker.log_metrics` expecting MLflow to log to a specific run, the argument is silently ignored and the active run is used instead.

- **Decision**: `MLflowTracker` always calls `mlflow.set_experiment(experiment_name)` on every `_get_mlflow()` call, not just once. **Why**: Simplifies state management; calling `set_experiment` multiple times with the same name is idempotent in MLflow. **Tradeoff**: Slightly redundant MLflow API calls if the same tracker is used for many runs.

---

## Scaling concerns

`NoOpTracker` has negligible cost: one UUID generation per `start_run`. All other methods are literal no-ops.

`InMemoryTracker` stores all records in Python lists. For a training run with 1000 epochs logging metrics per epoch, this produces 1000 entries in `self.metrics`, which is a tiny memory footprint. It is not intended for production use with millions of metric points.

`MLflowTracker` delegates all storage to the MLflow tracking server (local filesystem or remote). Scaling concerns are entirely those of the MLflow backend being used. For large-scale distributed training, a remote MLflow server with a database backend (PostgreSQL) and artifact store (S3) is recommended. The `MLflowTracker` itself adds only the overhead of the MLflow fluent API calls.

**What breaks first**: `InMemoryTracker` memory, for very long training runs logging metrics at very high frequency. For `MLflowTracker`, the bottleneck is the MLflow server's throughput, not this module.

---

## Future improvements

- **Weights & Biases adapter**: analogous `WandBTracker` for W&B integration.
- **Step-level validation**: add a `log_metrics` implementation in `InMemoryTracker` that validates that `step` is monotonically increasing within a run, catching common training loop bugs.
- **Run context manager**: add a `contextlib.contextmanager`-style helper `tracker.run(name, config)` that calls `start_run` on enter and `end_run` on exit, reducing boilerplate in training orchestrators.
- **Metric retrieval**: add a `get_metrics(run_id) -> dict` method to `InMemoryTracker` that aggregates all logged metrics for a run, enabling assertions like `tracker.get_metrics("run-1")["train_loss"]`.

---

## Usage examples

Using `NoOpTracker` as a default when tracking is not needed:

```python
from llm_agents.training.experiment_tracking import NoOpTracker
from llm_agents.training.fine_tuning import FineTuner, FineTuneConfig

tuner = FineTuner(
    config=FineTuneConfig(base_model="gpt2"),
    trainer_factory=my_factory,
    tracker=NoOpTracker(),
)
result = tuner.run(dataset)
```

Using `InMemoryTracker` in a unit test:

```python
from llm_agents.training.experiment_tracking import InMemoryTracker

tracker = InMemoryTracker()
run_id = tracker.start_run("test-run", config={"lr": 0.001})
tracker.log_params({"batch_size": 4}, run_id=run_id)
tracker.log_metrics({"train_loss": 0.5}, run_id=run_id, step=1)
tracker.log_metrics({"train_loss": 0.3}, run_id=run_id, step=2)
tracker.end_run(run_id)

assert tracker.run_count == 1
assert tracker.runs[0]["name"] == "test-run"
assert len(tracker.metrics) == 2
assert run_id in tracker.ended
```

Using `MLflowTracker` with the `FineTuner` for production experiment logging:

```python
# requires: uv sync --extra training
from llm_agents.training.experiment_tracking import MLflowTracker
from llm_agents.training.fine_tuning import FineTuner, FineTuneConfig

tracker = MLflowTracker(
    tracking_uri="http://mlflow.internal:5000",
    experiment_name="llama-finetune",
)
config = FineTuneConfig(
    base_model="meta-llama/Llama-2-7b-hf",
    output_dir="/checkpoints/run1",
    num_epochs=3,
    learning_rate=2e-4,
    lora_r=16,
    lora_alpha=32,
)
tuner = FineTuner(config=config, tracker=tracker)
result = tuner.run(dataset=my_dataset)
# Metrics and params are visible in the MLflow UI at http://mlflow.internal:5000
print(result.run_id)       # MLflow run ID (e.g. "a3b5c7d9...")
print(result.metrics)      # {"train_loss": 0.21, ...}
```

Using `MLflowTracker` standalone — log any training metrics manually:

```python
from llm_agents.training.experiment_tracking import MLflowTracker

tracker = MLflowTracker(experiment_name="manual-experiments")

run_id = tracker.start_run("baseline-sweep", config={"lr": 1e-3, "epochs": 5, "batch": 32})
for step, loss in enumerate([0.8, 0.6, 0.45, 0.31, 0.22]):
    tracker.log_metrics({"train_loss": loss}, step=step)
tracker.log_params({"architecture": "gpt2", "tokenizer": "bpe"})
tracker.end_run(run_id)
```

Implementing a custom tracker adapter (e.g., for a console logger):

```python
from llm_agents.training.experiment_tracking import Tracker
import uuid

class ConsoleTracker:
    def start_run(self, name, config=None):
        run_id = str(uuid.uuid4())
        print(f"[RUN START] {name} ({run_id})")
        return run_id

    def log_metrics(self, metrics, *, run_id=None, step=None):
        print(f"[METRICS] step={step} {metrics}")

    def log_params(self, params, *, run_id=None):
        print(f"[PARAMS] {params}")

    def end_run(self, run_id):
        print(f"[RUN END] {run_id}")

assert isinstance(ConsoleTracker(), Tracker)  # True — protocol satisfied
```
