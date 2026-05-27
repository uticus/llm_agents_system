# Rules: Implementation Planning
# File: .cursor/rules/planning.md
# Applied by: Planner

> Constraints and forbidden patterns for implementation planning.

---

## Plan step requirements

Every plan step must contain:
- Verb phrase title describing the change (not the intent)
- Explicit file list — no "and related files", no wildcards
- Specific change — symbol name, method name, parameter name
- Architectural rationale — reference to §architecture or ADR
- Risk assessment for all four dimensions: ABI, Perf, Det, Bindings
- Dependency statement: "step N" or "none"

A step missing any of these is incomplete and cannot be submitted to Critic.

---

## Forbidden patterns in plans

| Pattern | Why forbidden |
|---|---|
| Step mixes refactoring with new functionality | Verification becomes impossible — always separate steps |
| Step with "and related files" in file list | Implementer cannot execute — list explicitly |
| Step makes an architectural decision | Planner's scope is steps, not decisions — return to Architect |
| Risk assessment of "TBD" | Downstream agents cannot plan — assess now |
| Step order violates compilation order | Code won't compile — reorder |
| Plan approved before Critic signals AGREE | Premature — use loop stop condition |

---

## Ordering rules

Standard step order — deviation requires explicit justification:
1. Internal changes (no public API impact)
2. Public header changes
3. Implementation updates matching new headers
4. Test updates
5. Python binding updates
6. Example updates

Refactoring steps always precede feature addition steps.
Never mix refactoring and new functionality in the same step.

---

## Scope rules

- Plan must cover only the scope defined in `§decomposition`
- If a required change is outside scope — flag to developer, do not expand silently
- Plan must not introduce changes to `_deps/` or external dependencies

---

## Iteration rules

- Revise only steps mentioned in Critic feedback
- Do not revise steps not flagged — unnecessary churn
- Append each revision as a new iteration to `sessions/task-NNN-plan.md`
- Do not overwrite previous iterations — full history must be preserved

---

## Stop condition

Plan is complete when Critic writes AGREE with zero [BLOCKING] issues.
Planner writes clean plan to `task-NNN.md §plan` only after stop condition is met.


