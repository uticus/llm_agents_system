# training/fine_tuning

## Overview

The `training/fine_tuning` module orchestrates parameter-efficient fine-tuning (PEFT) runs
using LoRA / QLoRA adapters on top of HuggingFace base models.  It provides a configuration
dataclass for all training hyperparameters, a result dataclass that captures the output of a
completed run, and an orchestrator class (`FineTuner`) that sequences the full training
lifecycle: starting an experiment tracker run, building and invoking a trainer, saving the
adapter, logging metrics, registering the artifact in a model hub, and ending the tracker
run.

The module ships a production-ready default trainer factory (`peft_trainer_factory`) that
loads the tokenizer, base model, and PEFT adapter through HuggingFace Transformers + PEFT,
wrapping the resulting `Trainer` in a `PeftTrainer` adapter.  QLoRA (4-bit quantization via
`bitsandbytes`) is enabled by setting `config.use_4bit = True`.  All heavy dependencies
(`transformers`, `peft`) are deferred to the first call, so the module is importable without
the `training` extra installed.

---

## Public API

### Exported symbols

| Name | Kind | Description |
|---|---|---|
| `FineTuneConfig` | dataclass | All hyperparameters for a PEFT/LoRA/QLoRA fine-tuning run. |
| `FineTuneResult` | dataclass | Output of a completed `FineTuner.run` call. |
| `FineTuner` | class | Orchestrates train -> save -> log -> register pipeline. |
| `PeftTrainer` | class | HuggingFace `Trainer` wrapper; exposes the three-method trainer protocol. |
| `peft_trainer_factory` | function | Default `trainer_factory`; builds `PeftTrainer` from config + dataset. |

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
    use_4bit: bool = False,        # QLoRA — requires bitsandbytes
    extra: dict[str, Any] = {},    # provider-specific overrides
                                   #   lora_target_modules: list[str]
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
    trainer_factory: Any = None,   # Callable(config, dataset) -> trainer
                                   # defaults to peft_trainer_factory
    tracker: Any = None,           # Tracker protocol; None = skip tracking
    model_hub: Any = None,         # ModelHub; None = skip registration
)

run(dataset: Any) -> FineTuneResult
```

`run` executes the full training pipeline and always ends the tracker run even if an
exception occurs (via `try/finally`).

### PeftTrainer

```
PeftTrainer(hf_trainer: Any)

train()                     -> None         # delegates to hf_trainer.train()
save_model(path: str)       -> None         # delegates to hf_trainer.save_model(path)
get_metrics()               -> dict[str, float]
    # merges TrainOutput.metrics + scalar entries from Trainer.state.log_history
    # excludes step, epoch, learning_rate from log_history
    # returns {} if train() has not been called yet
```

### peft_trainer_factory

```
peft_trainer_factory(config: FineTuneConfig, dataset: Any) -> PeftTrainer
```

All heavy imports are deferred to this function.

Standard LoRA (default): loads the base model in full precision, applies a LoRA adapter
via `peft.get_peft_model`, and constructs a HuggingFace `Trainer`.

QLoRA (`config.use_4bit=True`): adds `BitsAndBytesConfig(load_in_4bit=True, nf4)` to
the model load call, then calls `peft.prepare_model_for_kbit_training` before applying the
LoRA adapter.  Requires `bitsandbytes` (`pip install bitsandbytes`).

Target modules: pass `config.extra["lora_target_modules"]` as a list of strings to restrict
LoRA to specific named layers (e.g. `["q_proj", "v_proj"]`).  If omitted, PEFT uses its
built-in defaults.

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
    |     (default: peft_trainer_factory)
    |             |
    |      AutoTokenizer.from_pretrained
    |      AutoModelForCausalLM.from_pretrained
    |      [BitsAndBytesConfig if use_4bit]
    |      [prepare_model_for_kbit_training if use_4bit]
    |      LoraConfig + get_peft_model
    |      TrainingArguments + HF Trainer
    |             |
    |         PeftTrainer
    |      .train()
    |      .save_model()
    |      .get_metrics()
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
2. If a tracker is configured, `tracker.start_run(name, config)` is called with a name
   derived from `config.base_model` and a dict of hyperparameters.  The returned `run_id`
   is stored for later calls.
3. The `trainer_factory(config, dataset)` callable is invoked (default:
   `peft_trainer_factory`).  It returns a `PeftTrainer` wrapping a fully configured
   HuggingFace `Trainer`.
4. `trainer.train()` executes the training loop.  Inside `PeftTrainer`, this delegates to
   `Trainer.train()` and stores the `TrainOutput`.
5. `trainer.save_model(config.output_dir)` writes the trained adapter or full model to
   disk via `Trainer.save_model`.
6. `trainer.get_metrics()` returns a `dict[str, float]` merged from `TrainOutput.metrics`
   and scalar entries in `Trainer.state.log_history`.
7. If a tracker is configured, `tracker.log_metrics(metrics, run_id=run_id)` records the
   metrics.
8. If a model hub is configured, `_register_artifact(model_hub, config, metrics)` is
   called.  The current stub returns a deterministic version string; a production
   implementation would call an MLflow or model registry API.
9. A `FineTuneResult` is constructed and returned.
10. Regardless of success or failure, the `finally` block calls `tracker.end_run(run_id)`
    to close the tracker run cleanly.

### Key abstractions

**FineTuneConfig** is a flat dataclass.  All LoRA parameters (`lora_r`, `lora_alpha`,
`lora_dropout`) and the QLoRA toggle (`use_4bit`) live at the top level.  The `extra` dict
provides an escape hatch for less common parameters such as `lora_target_modules`.

**PeftTrainer** is the concrete implementation of the trainer protocol shipped with the
module.  It wraps HuggingFace `Trainer` and merges training metrics from two sources:
`TrainOutput.metrics` (populated at the end of `train()`) and scalar entries from
`Trainer.state.log_history` (populated during training).  Non-metric keys (`step`, `epoch`,
`learning_rate`) are excluded from the merged dict.

**Trainer factory protocol** is duck-typed (`Any`).  The factory receives `(config,
dataset)` and returns any object with `train()`, `save_model(path)`, and `get_metrics()`
methods.  Lightweight stubs are used in tests; `peft_trainer_factory` is used in
production.  Custom factories can be injected at `FineTuner` construction time.

**Deferred imports**: `peft_trainer_factory` defers all `transformers`, `peft`, and
`bitsandbytes` imports to the body of the function.  The module is importable and
`PeftTrainer` is instantiable without those packages installed.  A missing-extra
`ImportError` is raised only when `peft_trainer_factory` is actually called.

**Tracker integration**: optional.  When `None`, all tracking calls are skipped.  The
`try/finally` ensures `end_run` is called even when `trainer.train()` raises.

**Model hub integration**: optional stub.  The current `_register_artifact` helper uses
`id(config)` as a version string.  A production implementation replaces this with a real
registry call.

---

## Design decisions and tradeoffs

- **Decision**: `FineTuner` accepts `trainer_factory` as a constructor argument; default is
  `peft_trainer_factory`. **Why**: The default covers real production use without extra
  configuration, while custom factories allow test stubs or alternative PEFT strategies to
  be injected without subclassing. **Tradeoff**: If the factory needs access to the dataset
  at construction time, it cannot do so until `run` is called; this is rarely needed for
  LoRA fine-tuning.

- **Decision**: `PeftTrainer.get_metrics()` merges `TrainOutput.metrics` with
  `state.log_history`. **Why**: HuggingFace `Trainer` exposes metrics in two places: the
  `TrainOutput` returned by `train()` and the per-step log history.  Merging both gives a
  complete picture without requiring callers to know about the internal HF API. **Tradeoff**:
  The last value for a key in `log_history` wins; callers wanting the full time-series must
  inspect the HF trainer state directly.

- **Decision**: QLoRA is enabled via `config.use_4bit` rather than a separate factory.
  **Why**: Standard LoRA and QLoRA share the same overall pipeline (tokenizer load, model
  load, PEFT adapter, Trainer).  A single flag avoids duplicating the factory for a one-step
  difference. **Tradeoff**: `bitsandbytes` is not in the `training` extra (its GPU
  dependencies are complex and platform-specific); callers must install it separately, and
  a clear `ImportError` is raised if it is missing.

- **Decision**: `FineTuneConfig.use_4bit` has a default of `False`, `lora_target_modules`
  lives in `extra`. **Why**: Both fields are backward-compatible additions; keeping
  `target_modules` in `extra` avoids polluting the config with model-architecture-specific
  details that vary per base model. **Tradeoff**: `extra` is untyped; callers rely on
  documentation for the recognised keys.

- **Decision**: `_register_artifact` silently returns `None` on exception. **Why**: Model
  hub registration is a post-training step; losing registration should not discard the
  training result. **Tradeoff**: Failures are invisible to the caller unless it checks
  `result.version_id is None`.

- **Decision**: `FineTuneConfig` includes LoRA-specific fields as first-class fields.
  **Why**: LoRA is the target PEFT method; first-class fields improve IDE autocomplete.
  **Tradeoff**: Configs for other PEFT methods (Prefix Tuning, IA3) require `extra`, which
  is untyped.

---

## Scaling concerns

The bottleneck is `trainer.train()`, which is entirely external to this module.  The
`FineTuner` itself adds negligible overhead.  Scaling to multi-GPU or distributed training
is entirely a responsibility of the injected `trainer_factory` and the trainer it returns.

Memory: `FineTuneConfig` and `FineTuneResult` are tiny in-memory objects.  QLoRA trades GPU
memory for quantisation overhead — with `use_4bit=True`, a 7B model fits on a single 24 GB
GPU; without it, you typically need 40–80 GB.

**What breaks first**: the injected trainer, not the orchestrator.  For very large models or
datasets, OOM errors and checkpoint management are trainer-level concerns.

---

## Future improvements

- **Typed trainer protocol**: define a formal `Trainer` Protocol with `train()`,
  `save_model(path)`, and `get_metrics()` signatures and use it in place of `Any` for the
  factory return type, enabling static type checking of custom trainer implementations.
- **Real artifact registration**: implement `_register_artifact` to call an actual MLflow or
  Weights & Biases model registry API, replacing the `id(config)` stub.
- **Resume from checkpoint**: add a `resume_from` field to `FineTuneConfig` and thread it
  through to the trainer factory.
- **Hyperparameter sweep**: add a `sweep` function that accepts a list of `FineTuneConfig`
  objects and runs them sequentially (or in parallel), returning results ranked by a
  specified metric.
- **Config serialization**: add `FineTuneConfig.to_dict()` / `from_dict()` methods and a
  JSON/YAML round-trip.

---

## Usage examples

Default factory — uses `peft_trainer_factory` (requires `uv sync --extra training`):

```python
from llm_agents.training.fine_tuning import FineTuneConfig, FineTuner

config = FineTuneConfig(
    base_model="meta-llama/Llama-2-7b-hf",
    output_dir="/tmp/my_adapter",
    num_epochs=3,
    lora_r=16,
    lora_alpha=32,
    batch_size=4,
    learning_rate=2e-4,
)

tuner = FineTuner(config=config)
result = tuner.run(dataset=my_hf_dataset)
print(result.model_path, result.metrics)
```

QLoRA (4-bit, requires `pip install bitsandbytes`):

```python
config = FineTuneConfig(
    base_model="mistralai/Mistral-7B-v0.1",
    output_dir="/tmp/mistral_qlora",
    use_4bit=True,
    lora_r=32,
    lora_alpha=64,
    lora_dropout=0.05,
    max_seq_length=2048,
    fp16=True,
    extra={"lora_target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"]},
)
tuner = FineTuner(config=config)
result = tuner.run(dataset=my_dataset)
print(result.metrics)
```

Stub trainer for testing (no HuggingFace packages needed):

```python
from llm_agents.training.fine_tuning import FineTuneConfig, FineTuner

class StubTrainer:
    def train(self): pass
    def save_model(self, path): pass
    def get_metrics(self): return {"train_loss": 0.35}

config = FineTuneConfig(base_model="gpt2", output_dir="/tmp/out")
tuner = FineTuner(config=config, trainer_factory=lambda cfg, ds: StubTrainer())
result = tuner.run(dataset=[])
print(result.model_path, result.metrics)
```

With experiment tracking and model hub:

```python
from llm_agents.training.experiment_tracking import InMemoryTracker
from llm_agents.training.fine_tuning import FineTuneConfig, FineTuner
from llm_agents.infra.model_hub import ModelHub

tracker = InMemoryTracker()
hub = ModelHub()

tuner = FineTuner(
    config=FineTuneConfig(base_model="gpt2", output_dir="/tmp/out"),
    trainer_factory=lambda cfg, ds: StubTrainer(),
    tracker=tracker,
    model_hub=hub,
)
result = tuner.run(dataset=[])
print(tracker.runs)     # [{"id": "run-1", "name": "finetune-gpt2", ...}]
print(result.version_id)
```
