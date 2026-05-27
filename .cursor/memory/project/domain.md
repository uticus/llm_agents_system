# Domain Reference
# File: .cursor/memory/project/domain.md

> Maintained by: Memory writer
> Purpose: domain constraints relevant to the project that drive architectural decisions.

---

## Domain characteristics (implementation-relevant)

| Property | Value |
|---|---|
| Domain | LLM platform: agent orchestration, RAG, model management, MLOps |
| Inference location | Hosted APIs (OpenAI) and local backends (HuggingFace, GGUF via llama.cpp/vLLM) |
| Determinism | Outputs non-deterministic; reproducibility via recorded traces |
| Primary cost/latency driver | LLM calls (network round-trips / GPU inference) and token usage |
| Concurrency | Many agent/tool/retrieval calls run concurrently (mostly I/O bound) |
| Dependency policy | Light core; heavy integrations behind interfaces + optional extras |

---

## Primary objective

Provide reusable, composable subsystems that let developers assemble grounded LLM agent
systems — model management, ingestion, RAG, memory/planning/tools, serving, fine-tuning,
and evaluation — while keeping each concern independently testable and heavy dependencies
optional.

---

## Information structure

### Inputs
- User/agent goals and prompts
- Internal documents from connectors (PostgreSQL, Confluence, Jira, Google Drive, files)
- Tool definitions and their results
- Recorded run traces (for replay analysis)
- Model responses (hosted or local)

### Outputs
- Grounded agent answers and tool invocations
- Plans and decomposed task graphs
- Vector indexes over ingested documents
- Evaluation scores, benchmarks, and hallucination reports
- Fine-tuned model artifacts and versions

---

## Scale and performance constraints

- Latency dominated by LLM calls (network for hosted, GPU for local) — design for async/
  concurrent I/O and a separate inference tier for local models
- Token budgets are a first-class constraint (long_context manages context windows)
- Vector index size grows with the corpus — choose a scalable vector store
- No tight CPU loops or no-allocation hot paths in the orchestration code

---

## Determinism requirements

Strict output determinism is NOT required: LLM responses vary across calls. Where
reproducibility matters, it is achieved by recording and replaying run traces rather
than by enforcing identical outputs.

---

## Domain-specific edge cases

- LLM/API failures, timeouts, rate limits: handled at the routing/orchestration boundary
- Context-window overflow: long_context must chunk/summarize before exceeding limits
- Tool execution errors: tool_orchestration must surface failures without crashing the agent
- Non-deterministic outputs: evaluation must tolerate variance (avoid exact-match-only assertions)
- Empty/low-relevance retrieval: RAG must handle "no good context" without fabricating answers
- Stale index: ingestion must re-embed changed documents and avoid duplicates
- Unsafe/off-domain output: guardrails must filter before responses reach the user
- Missing optional extra: importing an adapter without its extra must fail with a clear message
