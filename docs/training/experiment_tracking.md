# training/experiment_tracking

## Overview

The `training/experiment_tracking` module defines the interface and lightweight implementations for experiment tracking in ML training workflows. It provides a structural `Tracker` Protocol that abstracts away any specific tracking backend (MLflow, Weights & Biases, DVC, or custom), a `NoOpTracker` that silently discards all calls for use when tracking is not needed, and an `InMemoryTracker` that records all calls in plain Python lists for use in unit tests and local debugging. The module exists to give the `FineTuner` (and any other training component) a stable, backend-agnostic interface for recording hyperparameters and metrics, without forcing a dependency on any specific tracking library. Because the `Tracker` is structural (`@runtime_checkable`), any existing MLflow or W&B wrapper that happens to expose matching method signatures qualifies automatically.

---

## Public API

### Exported symbols

| Name | Kind | Description |
|---|---|---|
| `Tracker` | Protocol | Structural interface for experiment trackers. |
| `NoOpTracker` | class | Silent no-operation tracker; safe default when tracking is not needed. |
| `InMemoryTracker` | class | In-memory tracker that records all calls for test assertions. |

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

---

## Architecture

### Conceptual view

```
     Training orchestration (FineTuner, etc.)
                  |
                  |  uses
                  v
           Tracker (Protocol)
          /        |         \
   NoOpTracker  InMemory-  MLflow/W&B adapter
                Tracker     (external, not in module)
```

The protocol layer decouples training logic from tracking implementation. Training orchestrators code against `Tracker`; concrete backends are injected at construction time.

### Data flow — InMemoryTracker

1. `start_run(name, config)` increments `_counter`, constructs run ID `"run-{counter}"`, appends `{"id": run_id, "name": name, "config": config or {}}` to `self.runs`, and returns the run ID.
2. `log_metrics(metrics, run_id=run_id, step=step)` appends `{"run_id": run_id, "step": step, "metrics": dict(metrics)}` to `self.metrics`. Both `run_id` and `step` may be `None`.
3. `log_params(params, run_id=run_id)` appends `{"run_id": run_id, "params": dict(params)}` to `self.params`.
4. `end_run(run_id)` appends `run_id` to `self.ended`.

All recorded data is accessible directly through the public list attributes for inspection in test assertions.

### Key abstractions

**Tracker as a Protocol** rather than an abstract base class has two consequences. First, external adapters (MLflow `MlflowClient`, W&B `wandb.run` wrappers) can satisfy the interface without modification, as long as their method signatures match. Second, `isinstance(obj, Tracker)` works at runtime thanks to `@runtime_checkable`, allowing training orchestrators to validate injected dependencies.

**Separation of concerns**: the protocol separates `log_metrics` (for scalar training metrics at a specific step) from `log_params` (for hyperparameters that are set once per run). Many tracking backends treat these differently: metrics are time-series, params are run-level constants.

**NoOpTracker vs None**: the `FineTuner` could accept `None` as "no tracking" (and does, via a `if self._tracker is not None` guard). However, having `NoOpTracker` available means callers can also explicitly pass a no-op tracker without needing to know about the null-check pattern. Both approaches are supported.

**InMemoryTracker for tests**: the design choice to expose raw lists (`runs`, `metrics`, `params`, `ended`) rather than providing query methods keeps the test tracker simple and flexible. Test assertions can use standard Python list operations and comprehensions to verify any aspect of the recorded tracking calls.

---

## Design decisions and tradeoffs

- **Decision**: The `Tracker` Protocol uses keyword-only arguments (`*`) for `run_id` and `step` in `log_metrics` and `log_params`. **Why**: Makes call sites readable and prevents positional-argument mistakes when mixing metrics with run IDs. **Tradeoff**: Protocol implementors must also use keyword-only syntax in their signatures, which adds a minor constraint.

- **Decision**: `NoOpTracker.start_run` returns a real UUID rather than a constant or empty string. **Why**: Callers that store the run ID and pass it to subsequent calls (e.g., `log_metrics(metrics, run_id=run_id)`) should receive a valid non-empty string, even in no-op mode. A constant like `""` would make it harder to distinguish between "tracking is disabled" and "tracking errored". **Tradeoff**: A new UUID is generated on every call, which is slightly more work than returning a constant.

- **Decision**: `InMemoryTracker` uses a sequential integer counter (`"run-1"`, `"run-2"`) rather than UUIDs for run IDs. **Why**: Predictable run IDs make test assertions cleaner: `assert tracker.runs[0]["id"] == "run-1"` is clearer than asserting on a UUID. **Tradeoff**: IDs are only unique within a single `InMemoryTracker` instance; across test runs a fresh instance must be constructed.

- **Decision**: `metrics` dicts passed to `log_metrics` and `params` dicts passed to `log_params` are copied via `dict(metrics)` before storing. **Why**: If the caller mutates the dict after the call, the stored copy is not affected, preventing subtle test failures caused by shared mutable state. **Tradeoff**: Shallow copy; nested mutable values (e.g., a list inside a metrics dict) are still shared.

- **Decision**: The module does not include a concrete MLflow or W&B adapter. **Why**: Keeping the module focused on the protocol and test implementations avoids adding optional heavy dependencies to the core module. Adapters live in user code or in future optional extras. **Tradeoff**: There is no turnkey "use MLflow" option; users must write or import a thin adapter.

---

## Scaling concerns

`NoOpTracker` has negligible cost: one UUID generation per `start_run`. All other methods are literal no-ops.

`InMemoryTracker` stores all records in Python lists. For a training run with 1000 epochs logging metrics per epoch, this produces 1000 entries in `self.metrics`, which is a tiny memory footprint. It is not intended for production use with millions of metric points.

External tracking backends (MLflow, W&B) have their own scaling properties that are outside the scope of this module. The `Tracker` interface does not expose batching or buffering methods; backends that require them would need to implement internal buffering inside their adapter's `log_metrics` method.

**What breaks first**: `InMemoryTracker` memory, for very long training runs logging metrics at very high frequency.

---

## Future improvements

- **MLflow adapter**: provide a `MlflowTracker` class in an optional extras module that wraps `mlflow.start_run`, `mlflow.log_metrics`, `mlflow.log_params`, and `mlflow.end_run`, satisfying the `Tracker` protocol and enabling drop-in MLflow integration.
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
