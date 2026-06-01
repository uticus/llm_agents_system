"""Unit tests for PeftTrainer and peft_trainer_factory.

All tests run without a real ``transformers`` or ``peft`` installation.
The heavy packages are patched into ``sys.modules`` via ``MagicMock`` so that
deferred imports inside ``peft_trainer_factory`` resolve to controllable mocks.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from llm_agents.training.fine_tuning import FineTuneConfig, PeftTrainer, peft_trainer_factory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mocks() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Return (mock_transformers, mock_peft, mock_bitsandbytes).

    Configures return values that support the standard factory flow.
    """
    # ---- transformers -------------------------------------------------------
    trans = MagicMock()

    mock_tok = MagicMock()
    mock_tok.pad_token = None
    mock_tok.eos_token = "</s>"
    trans.AutoTokenizer.from_pretrained.return_value = mock_tok

    base_model = MagicMock()
    trans.AutoModelForCausalLM.from_pretrained.return_value = base_model

    train_output = MagicMock()
    train_output.metrics = {"train_loss": 0.42, "eval_loss": 0.50}

    trainer_state = MagicMock()
    trainer_state.log_history = [
        {"step": 10, "loss": 0.5, "epoch": 1.0},
        {"step": 20, "eval_loss": 0.4, "learning_rate": 2e-4},
    ]
    hf_trainer = MagicMock()
    hf_trainer.train.return_value = train_output
    hf_trainer.state = trainer_state
    trans.Trainer.return_value = hf_trainer
    trans.BitsAndBytesConfig.return_value = MagicMock()

    # ---- peft ---------------------------------------------------------------
    peft_mod = MagicMock()
    peft_model = MagicMock()
    peft_mod.get_peft_model.return_value = peft_model
    peft_mod.prepare_model_for_kbit_training.return_value = peft_model
    peft_mod.TaskType.CAUSAL_LM = "CAUSAL_LM"

    # ---- bitsandbytes -------------------------------------------------------
    bnb = MagicMock()

    return trans, peft_mod, bnb


def _modules(trans: MagicMock, peft_mod: MagicMock, bnb: MagicMock | None = None) -> dict:
    """Build a sys.modules patch dict from mock objects."""
    d = {"transformers": trans, "peft": peft_mod}
    if bnb is not None:
        d["bitsandbytes"] = bnb
    return d


# ---------------------------------------------------------------------------
# Module-level: no heavy imports at top of _peft_trainer
# ---------------------------------------------------------------------------


class TestPeftTrainerModuleLevel:
    def test_module_importable_without_heavy_deps(self) -> None:
        import importlib

        import llm_agents.training.fine_tuning._peft_trainer as mod

        saved_trans = sys.modules.pop("transformers", None)
        saved_peft = sys.modules.pop("peft", None)
        # Snapshot the module dict so reload side-effects can be undone.
        saved_dict = dict(mod.__dict__)
        try:
            importlib.reload(mod)
        except ImportError:
            pytest.fail("Module import must not require transformers or peft")
        finally:
            if saved_trans is not None:
                sys.modules["transformers"] = saved_trans
            if saved_peft is not None:
                sys.modules["peft"] = saved_peft
            # Restore the original module namespace to keep class identity intact.
            mod.__dict__.clear()
            mod.__dict__.update(saved_dict)

    def test_no_top_level_transformers_import(self) -> None:
        import ast
        import inspect

        from llm_agents.training.fine_tuning import _peft_trainer as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            is_trans = isinstance(node, ast.ImportFrom) and (
                (node.module or "").startswith("transformers")
            )
            if is_trans:
                assert node.col_offset != 0, "transformers must not be a top-level import"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "transformers" in alias.name:
                        assert node.col_offset != 0, "transformers must not be a top-level import"

    def test_no_top_level_peft_import(self) -> None:
        import ast
        import inspect

        from llm_agents.training.fine_tuning import _peft_trainer as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            is_peft = isinstance(node, ast.ImportFrom) and (
                (node.module or "").startswith("peft")
            )
            if is_peft:
                assert node.col_offset != 0, "peft must not be a top-level import"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "peft":
                        assert node.col_offset != 0, "peft must not be a top-level import"


# ---------------------------------------------------------------------------
# PeftTrainer — train()
# ---------------------------------------------------------------------------


class TestPeftTrainerTrain:
    def test_train_calls_hf_trainer_train(self) -> None:
        mock_hf = MagicMock()
        trainer = PeftTrainer(mock_hf)
        trainer.train()
        mock_hf.train.assert_called_once()

    def test_train_stores_output(self) -> None:
        mock_output = MagicMock()
        mock_hf = MagicMock()
        mock_hf.train.return_value = mock_output
        trainer = PeftTrainer(mock_hf)
        trainer.train()
        assert trainer._train_output is mock_output

    def test_train_output_none_before_train(self) -> None:
        trainer = PeftTrainer(MagicMock())
        assert trainer._train_output is None


# ---------------------------------------------------------------------------
# PeftTrainer — save_model()
# ---------------------------------------------------------------------------


class TestPeftTrainerSaveModel:
    def test_save_model_calls_hf_save(self) -> None:
        mock_hf = MagicMock()
        trainer = PeftTrainer(mock_hf)
        trainer.save_model("/tmp/out")
        mock_hf.save_model.assert_called_once_with("/tmp/out")

    def test_save_model_passes_path_exactly(self) -> None:
        mock_hf = MagicMock()
        trainer = PeftTrainer(mock_hf)
        trainer.save_model("/my/custom/path")
        args, _ = mock_hf.save_model.call_args
        assert args[0] == "/my/custom/path"


# ---------------------------------------------------------------------------
# PeftTrainer — get_metrics()
# ---------------------------------------------------------------------------


class TestPeftTrainerGetMetrics:
    def test_get_metrics_empty_before_train(self) -> None:
        trainer = PeftTrainer(MagicMock())
        assert trainer.get_metrics() == {}

    def test_get_metrics_from_train_output(self) -> None:
        mock_output = MagicMock()
        mock_output.metrics = {"train_loss": 0.35, "eval_loss": 0.40}
        mock_hf = MagicMock()
        mock_hf.state.log_history = []
        mock_hf.train.return_value = mock_output
        trainer = PeftTrainer(mock_hf)
        trainer.train()
        metrics = trainer.get_metrics()
        assert metrics["train_loss"] == pytest.approx(0.35)
        assert metrics["eval_loss"] == pytest.approx(0.40)

    def test_get_metrics_values_are_float(self) -> None:
        mock_output = MagicMock()
        mock_output.metrics = {"train_loss": 1}  # int input
        mock_hf = MagicMock()
        mock_hf.state.log_history = []
        mock_hf.train.return_value = mock_output
        trainer = PeftTrainer(mock_hf)
        trainer.train()
        metrics = trainer.get_metrics()
        assert isinstance(metrics["train_loss"], float)

    def test_get_metrics_from_log_history(self) -> None:
        mock_output = MagicMock()
        mock_output.metrics = {}
        mock_hf = MagicMock()
        mock_hf.state.log_history = [{"step": 10, "loss": 0.55}]
        mock_hf.train.return_value = mock_output
        trainer = PeftTrainer(mock_hf)
        trainer.train()
        metrics = trainer.get_metrics()
        assert "loss" in metrics
        assert metrics["loss"] == pytest.approx(0.55)

    def test_get_metrics_excludes_step_epoch_lr(self) -> None:
        mock_output = MagicMock()
        mock_output.metrics = {}
        mock_hf = MagicMock()
        mock_hf.state.log_history = [
            {"step": 10, "epoch": 1.0, "learning_rate": 2e-4, "loss": 0.3}
        ]
        mock_hf.train.return_value = mock_output
        trainer = PeftTrainer(mock_hf)
        trainer.train()
        metrics = trainer.get_metrics()
        assert "step" not in metrics
        assert "epoch" not in metrics
        assert "learning_rate" not in metrics
        assert "loss" in metrics

    def test_get_metrics_handles_missing_metrics_attr(self) -> None:
        mock_output = MagicMock(spec=[])  # no .metrics attribute
        mock_hf = MagicMock()
        mock_hf.state.log_history = []
        mock_hf.train.return_value = mock_output
        trainer = PeftTrainer(mock_hf)
        trainer.train()
        # Should not raise; returns {} or only log-history metrics
        metrics = trainer.get_metrics()
        assert isinstance(metrics, dict)

    def test_get_metrics_handles_missing_state(self) -> None:
        mock_output = MagicMock()
        mock_output.metrics = {"train_loss": 0.25}
        mock_hf = MagicMock(spec=["train", "save_model"])  # no .state
        mock_hf.train.return_value = mock_output
        trainer = PeftTrainer(mock_hf)
        trainer.train()
        metrics = trainer.get_metrics()
        assert metrics["train_loss"] == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# peft_trainer_factory — error paths
# ---------------------------------------------------------------------------


class TestPeftTrainerFactoryErrors:
    def test_raises_import_error_without_transformers(self) -> None:
        with patch.dict(sys.modules, {"transformers": None}):  # type: ignore[dict-item]
            config = FineTuneConfig(base_model="gpt2")
            with pytest.raises(ImportError, match="transformers"):
                peft_trainer_factory(config, [])

    def test_raises_import_error_without_peft(self) -> None:
        trans, _, _ = _make_mocks()
        with patch.dict(sys.modules, {"transformers": trans, "peft": None}):  # type: ignore[dict-item]
            config = FineTuneConfig(base_model="gpt2")
            with pytest.raises(ImportError, match="peft"):
                peft_trainer_factory(config, [])


# ---------------------------------------------------------------------------
# peft_trainer_factory — standard LoRA path
# ---------------------------------------------------------------------------


class TestPeftTrainerFactory:
    def test_returns_peft_trainer_instance(self) -> None:
        trans, peft_mod, bnb = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2")
            result = peft_trainer_factory(config, [])
        assert isinstance(result, PeftTrainer)

    def test_tokenizer_loaded_with_base_model(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="meta-llama/Llama-2-7b-hf")
            peft_trainer_factory(config, [])
        trans.AutoTokenizer.from_pretrained.assert_called_once_with(
            "meta-llama/Llama-2-7b-hf"
        )

    def test_model_loaded_with_base_model(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="mistral-7b")
            peft_trainer_factory(config, [])
        trans.AutoModelForCausalLM.from_pretrained.assert_called_once()
        args, _ = trans.AutoModelForCausalLM.from_pretrained.call_args
        assert args[0] == "mistral-7b"

    def test_lora_config_uses_correct_r(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2", lora_r=32)
            peft_trainer_factory(config, [])
        _, kwargs = peft_mod.LoraConfig.call_args
        assert kwargs["r"] == 32

    def test_lora_config_uses_correct_alpha(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2", lora_alpha=64)
            peft_trainer_factory(config, [])
        _, kwargs = peft_mod.LoraConfig.call_args
        assert kwargs["lora_alpha"] == 64

    def test_lora_config_uses_correct_dropout(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2", lora_dropout=0.05)
            peft_trainer_factory(config, [])
        _, kwargs = peft_mod.LoraConfig.call_args
        assert kwargs["lora_dropout"] == pytest.approx(0.05)

    def test_get_peft_model_called(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2")
            peft_trainer_factory(config, [])
        peft_mod.get_peft_model.assert_called_once()

    def test_training_args_output_dir(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2", output_dir="/tmp/run1")
            peft_trainer_factory(config, [])
        _, kwargs = trans.TrainingArguments.call_args
        assert kwargs["output_dir"] == "/tmp/run1"

    def test_training_args_epochs(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2", num_epochs=5)
            peft_trainer_factory(config, [])
        _, kwargs = trans.TrainingArguments.call_args
        assert kwargs["num_train_epochs"] == 5

    def test_training_args_fp16(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2", fp16=True)
            peft_trainer_factory(config, [])
        _, kwargs = trans.TrainingArguments.call_args
        assert kwargs["fp16"] is True

    def test_hf_trainer_constructed_with_dataset(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        dataset = ["sample1", "sample2"]
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2")
            peft_trainer_factory(config, dataset)
        _, kwargs = trans.Trainer.call_args
        assert kwargs["train_dataset"] is dataset

    def test_pad_token_set_when_none(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        tok = trans.AutoTokenizer.from_pretrained.return_value
        tok.pad_token = None
        tok.eos_token = "<eos>"
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2")
            peft_trainer_factory(config, [])
        assert tok.pad_token == "<eos>"

    def test_pad_token_unchanged_when_already_set(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        tok = trans.AutoTokenizer.from_pretrained.return_value
        tok.pad_token = "[PAD]"
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2")
            peft_trainer_factory(config, [])
        assert tok.pad_token == "[PAD]"

    def test_target_modules_passed_from_extra(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(
                base_model="gpt2",
                extra={"lora_target_modules": ["q_proj", "v_proj"]},
            )
            peft_trainer_factory(config, [])
        _, kwargs = peft_mod.LoraConfig.call_args
        assert kwargs["target_modules"] == ["q_proj", "v_proj"]

    def test_target_modules_absent_when_not_in_extra(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2")
            peft_trainer_factory(config, [])
        _, kwargs = peft_mod.LoraConfig.call_args
        assert "target_modules" not in kwargs

    def test_no_quantization_config_by_default(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2")
            peft_trainer_factory(config, [])
        _, kwargs = trans.AutoModelForCausalLM.from_pretrained.call_args
        assert "quantization_config" not in kwargs


# ---------------------------------------------------------------------------
# peft_trainer_factory — QLoRA path (use_4bit=True)
# ---------------------------------------------------------------------------


class TestPeftTrainerFactoryQLoRA:
    def test_qlora_raises_import_error_without_bitsandbytes(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        mods = {**_modules(trans, peft_mod), "bitsandbytes": None}  # type: ignore[dict-item]
        with patch.dict(sys.modules, mods):
            config = FineTuneConfig(base_model="gpt2", use_4bit=True)
            with pytest.raises(ImportError, match="bitsandbytes"):
                peft_trainer_factory(config, [])

    def test_qlora_creates_bits_and_bytes_config(self) -> None:
        trans, peft_mod, bnb = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod, bnb)):
            config = FineTuneConfig(base_model="gpt2", use_4bit=True)
            peft_trainer_factory(config, [])
        trans.BitsAndBytesConfig.assert_called_once()
        _, kwargs = trans.BitsAndBytesConfig.call_args
        assert kwargs.get("load_in_4bit") is True

    def test_qlora_passes_quantization_config_to_from_pretrained(self) -> None:
        trans, peft_mod, bnb = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod, bnb)):
            config = FineTuneConfig(base_model="gpt2", use_4bit=True)
            peft_trainer_factory(config, [])
        _, kwargs = trans.AutoModelForCausalLM.from_pretrained.call_args
        assert "quantization_config" in kwargs

    def test_qlora_calls_prepare_for_kbit_training(self) -> None:
        trans, peft_mod, bnb = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod, bnb)):
            config = FineTuneConfig(base_model="gpt2", use_4bit=True)
            peft_trainer_factory(config, [])
        peft_mod.prepare_model_for_kbit_training.assert_called_once()

    def test_prepare_kbit_not_called_without_use_4bit(self) -> None:
        trans, peft_mod, _ = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2", use_4bit=False)
            peft_trainer_factory(config, [])
        peft_mod.prepare_model_for_kbit_training.assert_not_called()


# ---------------------------------------------------------------------------
# Default factory integration — delegates to peft_trainer_factory
# ---------------------------------------------------------------------------


class TestDefaultFactoryIntegration:
    def test_default_factory_returns_peft_trainer(self) -> None:
        """FineTuner with no trainer_factory= uses peft_trainer_factory."""
        trans, peft_mod, _ = _make_mocks()
        with patch.dict(sys.modules, _modules(trans, peft_mod)):
            config = FineTuneConfig(base_model="gpt2", output_dir="/tmp/out")
            from llm_agents.training.fine_tuning import FineTuner

            tuner = FineTuner(config)
            result = tuner.run(dataset=[])
        # result.model_path comes from FineTuner, not PeftTrainer
        assert result.model_path == "/tmp/out"
