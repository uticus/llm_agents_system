"""Unit tests for infra/model_hub.

Covers ModelBackend protocol, FakeBackend cycling, ModelHub registration/retrieval,
and OpenAIBackend import-guard (no openai package needed).
No real network calls.
"""

from __future__ import annotations

import asyncio

import pytest

from llm_agents.infra.model_hub import FakeBackend, ModelBackend, ModelHub, OpenAIBackend

# ---------------------------------------------------------------------------
# T1: FakeBackend
# ---------------------------------------------------------------------------


def test_fake_backend_requires_responses():
    """T1: FakeBackend raises ValueError if constructed with empty responses."""
    with pytest.raises(ValueError, match="at least one response"):
        FakeBackend("test", [])


def test_fake_backend_single_response():
    """T1b: FakeBackend returns its single response on every call."""
    backend = FakeBackend("b", ["hello"])
    result = asyncio.run(backend.generate("prompt"))
    assert result == "hello"
    assert backend.call_count == 1


def test_fake_backend_multiple_responses_in_order():
    """T1c: FakeBackend returns responses in order."""
    backend = FakeBackend("b", ["first", "second", "third"])
    r1 = asyncio.run(backend.generate("p"))
    r2 = asyncio.run(backend.generate("p"))
    r3 = asyncio.run(backend.generate("p"))
    assert r1 == "first"
    assert r2 == "second"
    assert r3 == "third"


def test_fake_backend_cycles():
    """T1d: FakeBackend cycles responses when exhausted."""
    backend = FakeBackend("b", ["a", "b"])
    results = [asyncio.run(backend.generate("p")) for _ in range(5)]
    assert results == ["a", "b", "a", "b", "a"]


def test_fake_backend_call_count():
    """T1e: FakeBackend.call_count increments on each generate call."""
    backend = FakeBackend("b", ["x"])
    for _ in range(4):
        asyncio.run(backend.generate("p"))
    assert backend.call_count == 4


def test_fake_backend_metadata():
    """T1f: FakeBackend.metadata() returns a dict with name and backend keys."""
    backend = FakeBackend("my-fake", ["r"])
    meta = backend.metadata()
    assert meta["name"] == "my-fake"
    assert meta["backend"] == "fake"


# ---------------------------------------------------------------------------
# T2: ModelBackend protocol
# ---------------------------------------------------------------------------


def test_fake_backend_satisfies_protocol():
    """T2: FakeBackend satisfies the ModelBackend protocol at runtime."""
    assert isinstance(FakeBackend("x", ["r"]), ModelBackend)


def test_openai_backend_satisfies_protocol():
    """T2b: OpenAIBackend satisfies the ModelBackend protocol at runtime."""
    assert isinstance(OpenAIBackend("gpt-test"), ModelBackend)


# ---------------------------------------------------------------------------
# T3: ModelHub
# ---------------------------------------------------------------------------


def test_hub_register_and_get():
    """T3: ModelHub stores and retrieves a backend by name."""
    hub = ModelHub()
    b = FakeBackend("my-model", ["ok"])
    hub.register(b)
    assert hub.get("my-model") is b


def test_hub_get_unknown_returns_none():
    """T3b: ModelHub.get() returns None for an unregistered name."""
    hub = ModelHub()
    assert hub.get("nonexistent") is None


def test_hub_list_names_alphabetical():
    """T3c: ModelHub.list_names() returns sorted names."""
    hub = ModelHub()
    for name in ["zebra", "apple", "mango"]:
        hub.register(FakeBackend(name, ["r"]))
    assert hub.list_names() == ["apple", "mango", "zebra"]


def test_hub_register_overwrites():
    """T3d: Registering a second backend with the same name overwrites the first."""
    hub = ModelHub()
    b1 = FakeBackend("m", ["v1"])
    b2 = FakeBackend("m", ["v2"])
    hub.register(b1)
    hub.register(b2)
    assert hub.get("m") is b2


def test_hub_len():
    """T3e: len(hub) returns the number of registered backends."""
    hub = ModelHub()
    assert len(hub) == 0
    hub.register(FakeBackend("a", ["r"]))
    assert len(hub) == 1


def test_hub_initial_backends():
    """T3f: ModelHub accepts initial backends dict."""
    b = FakeBackend("init", ["r"])
    hub = ModelHub(backends={"init": b})
    assert hub.get("init") is b


# ---------------------------------------------------------------------------
# T4: OpenAIBackend import guard
# ---------------------------------------------------------------------------


def test_openai_backend_import_succeeds_without_openai():
    """T4: OpenAIBackend can be imported/instantiated without the openai package."""
    # If we got here, the import didn't raise. Just check basic attributes.
    ob = OpenAIBackend("gpt-4o", model_id="gpt-4o")
    assert ob.name == "gpt-4o"
    meta = ob.metadata()
    assert meta["backend"] == "openai"


def test_openai_backend_generate_raises_without_openai(monkeypatch):
    """T4b: OpenAIBackend.generate() raises ImportError if openai is not installed."""
    import builtins

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("openai not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    ob = OpenAIBackend("gpt-4o")
    with pytest.raises(ImportError, match="openai"):
        asyncio.run(ob.generate("hello"))
