# training/fine_tuning

## Overview

The `training/fine_tuning` module orchestrates parameter-efficient fine-tuning (PEFT) runs using LoRA adapters on top of HuggingFace base models. It provides a configuration dataclass for all training hyperparameters, a result dataclass that captures the output of a completed run, and an orchestrator class (`FineTuner`) that sequences the full training lifecycle: starting an experiment tracker run, building and invoking a trainer, saving the adapter, logging metrics, registering the artifact in a model hub, and ending the tracker run. The module is designed for testability and extensibility: the actual training implementation is injected through a `trainer_factory` callable, which means real Transformers/PEFT trainers and lightweight test stubs can be swapped in without changing the orchestration logic. Heavy dependencies (`transformers`, `peft`) are behind the `training` optional extra and are only required at the point where the default trainer factory is invoked.

---

## Public API

### Exported symbols

| Name | Kind | Description |
|---|---|---|
| `FineTuneConfig` | dataclass | All hyperparameters for a PEFT/LoRA fine-tuning run. |
| `FineTuneResult` | dataclass | Output of a completed `FineTuner.run` call. |
| `FineTuner` | class | Orchestrates train -> save -> log -> register pipeline. |

### FineTuneConfig

```
FineTuneConfig(
    base_model: str,               # HuggingFace hub name or local path (required)
    output_dir: str = "output",
    num_epochs: int = 1,
    batch_size: int = 4,
    learning_rate: float = 2e-4,
    lora_r: int = 8,               # LoRA rank
    lora_alpha: int = 32,          # LoRA scaling factor
    lora_dropout: float = 0.1,
    max_seq_length: int = 512,
    fp16: bool = False,
    extra: dict[str, Any] = {},    # provider-specific overrides
)
```

### FineTuneResult

```
FineTuneResult(
    model_path: str,               # path to saved adapter / model directory
    version_id: str | None,        # artifact version from model hub, or None
    metrics: dict[str, Any],       # training metrics (e.g. train_loss, eval_loss)
    config: Any,                   # FineTuneConfig used for this run
)
```

### FineTuner

```
FineTuner(
    config: FineTuneConfig,
    trainer_factory: Any = None,       # Callable(config, dataset) -> trainer; defaults to transformers+peft
    tracker: Any = None,               # Tracker protocol; None = skip tracking
    model_hub: Any = None,             # ModelHub; None = skip registration
)

run(dataset: Any) -> FineTuneResult
```

`run` executes the full training pipeline and always ends the tracker run, even if an exception occurs (via `try/finally`).

---

## Architecture

### Conceptual view

```
  FineTuneConfig + Dataset
          |
          v
       FineTuner.run()
          |
    +-----+-------+-----------+
    |             |           |
  Tracker      Trainer    ModelHub
  .start_run() factory    (optional)
    |             |
    |     trainer.train()
    |     trainer.save_model()
    |     trainer.get_metrics()
    |             |
  .log_metrics()  |
  .end_run()      |
    |             |
    +------+------+
           |
      FineTuneResult
```

### Data flow

1. `FineTuner.run(dataset)` is called.
2. If a tracker is configured, `tracker.start_run(name, config)` is called with a name derived from `config.base_model` and a dict of hyperparameters. The returned `run_id` is stored for later calls.
3. The `trainer_factory(config, dataset)` callable is invoked. It must return a trainer object with `train()`, `save_model(path)`, and `get_metrics()` methods.
4. `trainer.train()` executes the training loop. This is the long-running step; it may take minutes to hours depending on dataset size, model size, and hardware.
5. `trainer.save_model(config.output_dir)` writes the trained adapter or full model to disk.
6. `trainer.get_metrics()` returns a `dict[str, float]` with training statistics (e.g., `train_loss`, `eval_loss`).
7. If a tracker is configured, `tracker.log_metrics(metrics, run_id=run_id)` records the metrics.
8. If a model hub is configured, `_register_artifact(model_hub, config, metrics)` is called. In the current implementation this generates a deterministic version string from `id(config)` and returns it. A production implementation would call an MLflow or model registry API.
9. A `FineTuneResult` is constructed and returned.
10. Regardless of success or failure, the `finally` block calls `tracker.end_run(run_id)` to close the tracker run cleanly.

### Key abstractions

**FineTuneConfig** is a flat dataclass rather than a nested hierarchy. All LoRA parameters (`lora_r`, `lora_alpha`, `lora_dropout`) live at the top level for easy access. The `extra` dict provides an escape hatch for provider-specific parameters that do not have first-class fields.

**Trainer factory protocol** is implicit (duck-typed via `Any`). The factory callable receives `(config, dataset)` and must return an object with three methods. This pattern keeps the module decoupled from a specific Transformers version: trainers from different library versions or entirely custom training loops can be injected as long as they satisfy the protocol.

**Tracker integration**: the tracker is optional. When `None`, all tracking calls are skipped with a simple `if self._tracker is not None` guard. This avoids requiring callers to provide a `NoOpTracker` explicitly. The `try/finally` ensures `end_run` is called even when `trainer.train()` raises, which prevents dangling open runs in tracking backends.

**Model hub integration**: similarly optional. The current `_register_artifact` helper is a stub that uses `id(config)` as a version string. The comment in the source explicitly notes that a real implementation would call an MLflow or model hub API. This is a placeholder that allows the pipeline structure to be tested end-to-end without a live registry.

---

## Design decisions and tradeoffs

- **Decision**: `FineTuner` accepts `trainer_factory` as a constructor argument rather than a method argument or a subclass hook. **Why**: Constructor injection makes the dependency explicit at the point of construction and allows simple lambda or function objects to serve as factories without subclassing. **Tradeoff**: If the factory needs access to the dataset at construction time (e.g., to compute vocabulary size), it cannot do so until `run` is called; this is rarely a problem for LoRA fine-tuning.

- **Decision**: `FineTuneConfig` includes LoRA-specific fields (`lora_r`, `lora_alpha`, `lora_dropout`) as first-class fields. **Why**: LoRA is the target PEFT method and its parameters are the most commonly tuned. Making them first-class improves IDE autocomplete and documentation. **Tradeoff**: Configs for other PEFT methods (Prefix Tuning, IA3) require using the `extra` dict, which is untyped.

- **Decision**: `_register_artifact` silently returns `None` on exception. **Why**: Model hub registration is a post-training step that should not cause the training result to be discarded. Artifact registration failures are best handled by logging and retry rather than crashing the caller. **Tradeoff**: Failures are invisible to the caller unless it checks `result.version_id is None`.

- **Decision**: The default `_default_trainer_factory` raises `ImportError` if `transformers`/`peft` are missing, and `NotImplementedError` if they are present. **Why**: This makes the missing-extra error message actionable (it tells the user what to install). The `NotImplementedError` signals that a real factory must be provided explicitly, preventing silent no-ops. **Tradeoff**: This means the module cannot be used out of the box without either providing a `trainer_factory` or installing the extra; the factory injection pattern is therefore mandatory in practice.

---

## Scaling concerns

The bottleneck is `trainer.train()`, which is entirely external to this module. The `FineTuner` itself adds negligible overhead (a few dict copies, some conditional checks). Scaling fine-tuning to multi-GPU or distributed training is entirely a responsibility of the injected `trainer_factory` and the trainer it returns. The module has no opinion on parallelism strategy.

Memory: `FineTuneConfig` and `FineTuneResult` are tiny in-memory objects. The dataset is passed by reference and its size is the caller's concern.

**What breaks first**: the injected trainer, not the orchestrator. For very large models or datasets, OOM errors and checkpoint management are trainer-level concerns.

---

## Future improvements

- **Real artifact registration**: implement `_register_artifact` to call an actual MLflow or Weights & Biases model registry API, replacing the `id(config)` stub with a real artifact URI and version.
- **Typed trainer protocol**: define a formal `Trainer` Protocol with `train()`, `save_model(path)`, and `get_metrics()` signatures and use it in place of `Any` for the factory return type, enabling static type checking of custom trainer implementations.
- **Resume from checkpoint**: add a `resume_from` field to `FineTuneConfig` and thread it through to the trainer factory, enabling training runs to be resumed after interruption.
- **Hyperparameter sweep**: add a `sweep` function that accepts a list of `FineTuneConfig` objects and runs them sequentially (or in parallel), returning a list of `FineTuneResult` objects ranked by a specified metric.
- **Config serialization**: add `FineTuneConfig.to_dict()` / `from_dict()` methods and a `save(path)` / `load(path)` round-trip using JSON or YAML.

---

## Usage examples

Basic fine-tuning run with a stub trainer (for testing):

```python
from llm_agents.training.fine_tuning import FineTuneConfig, FineTuner

class StubTrainer:
    def train(self): pass
    def save_model(self, path): pass
    def get_metrics(self): return {"train_loss": 0.35}

config = FineTuneConfig(
    base_model="meta-llama/Llama-2-7b-hf",
    output_dir="/tmp/my_adapter",
    num_epochs=3,
    lora_r=16,
)

tuner = FineTuner(
    config=config,
    trainer_factory=lambda cfg, ds: StubTrainer(),
)
result = tuner.run(dataset=my_dataset)
print(result.model_path, result.metrics)
```

With experiment tracking:

```python
from llm_agents.training.experiment_tracking import InMemoryTracker
from llm_agents.training.fine_tuning import FineTuneConfig, FineTuner

tracker = InMemoryTracker()
tuner = FineTuner(
    config=FineTuneConfig(base_model="gpt2", output_dir="/tmp/out"),
    trainer_factory=lambda cfg, ds: StubTrainer(),
    tracker=tracker,
)
result = tuner.run(dataset=my_dataset)
print(tracker.runs)    # [{"id": "run-1", "name": "finetune-gpt2", ...}]
print(tracker.metrics) # [{"run_id": "run-1", "metrics": {"train_loss": 0.35}}]
```

LoRA configuration:

```python
config = FineTuneConfig(
    base_model="mistralai/Mistral-7B-v0.1",
    lora_r=32,
    lora_alpha=64,
    lora_dropout=0.05,
    max_seq_length=2048,
    fp16=True,
    batch_size=8,
    num_epochs=5,
    learning_rate=1e-4,
)
```
