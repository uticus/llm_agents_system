# Project Build
# File: .cursor/memory/project/build.md
# Maintained by: Memory writer + Environment agent

> Used by: Environment, Implementer (all), Tester
> Purpose: facts about the build system, project layout, and toolchain.
> Update when: new targets added, presets change, toolchain changes.
>
> [SETUP] Fill in all sections below. This file is created by the Environment agent
> during the first CP4 run. See SETUP.md for instructions.

---

## Project structure

<!-- SETUP: Fill in the actual directory structure. -->

```
<repo>/
  [source-dir]/       primary source
    include/          public headers
    src/              implementation
  [tests-dir]/        test suite
  [bindings-dir]/     language bindings (if applicable)
  [examples-dir]/     usage examples
```

---

## Build system

<!-- SETUP: Fill in the actual build system, tool, and preset/configuration names. -->

| Field | Value |
|---|---|
| Build tool | [cmake / npm / cargo / make / etc.] |
| Configuration file | [CMakePresets.json / package.json / Cargo.toml / etc.] |
| Toolchain | [Visual Studio / GCC / Clang / etc.] |

---

## CMake targets (if applicable)

<!-- SETUP: Fill in or remove this section depending on build tool. -->

| Target | Build file | Purpose | Build when |
|---|---|---|---|
| `[library]` | `[source-dir]/CMakeLists.txt` | Primary library | Always |
| `[tests]` | `[tests-dir]/CMakeLists.txt` | Test suite | Any change |
| `[bindings]` | `[bindings-dir]/` | Language bindings | Binding or API change |
| `[examples]` | `[examples-dir]/CMakeLists.txt` | Usage examples | API change |

---

## Presets / Configurations

<!-- SETUP: List the actual preset or configuration names. -->

| Preset name | Purpose |
|---|---|
| `[preset-1]` | [description] |
| `[preset-2]` | [description] |

---

## Standard build sequence

```bash
# From project root — always:
[configure command] --preset [preset]
[build command] --preset [preset] --target [target]
[test command] --preset [preset]
```

---

## Impact matrix

| Change | [library] | [tests] | [bindings] | [examples] |
|---|---|---|---|---|
| Internal impl | build | build + run | — | build |
| Public header | build | build + run | build + verify | build + run |
| Bindings | — | — | build + verify | build + run |

---

## Python environment (if applicable)

<!-- SETUP: Remove this section if not applicable. -->

```bash
# Verify binding import:
python -c "import [module_name]; print('ok')"
```

If import fails — check build output.
