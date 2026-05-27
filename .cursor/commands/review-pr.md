# Command: review-pr
# File: .cursor/commands/review-pr.md
# Type: developer command
# Activates: Reviewer

> Review a pull request or code diff.
> Reviewer evaluates against all six categories and produces a structured report.

---

## Usage

```
review-pr: <PR number>
review-pr: <paste diff directly>
review-pr task-NNN: <PR number>   # links review to a task card
```

## Preparation

Get the diff via GitHub CLI:
```bash
gh pr diff <PR_NUMBER>
```
Paste the output into the conversation.

## What happens

1. Reviewer reads the diff
2. If task card provided — reads `task-NNN.md §spec` and `§architecture`
3. If no task card — uses `memory/architecture/map.md` and `checklist.md`
4. Evaluates all six categories:
   spec compliance, architecture, hot-path, determinism, ownership, test quality
5. Produces a structured review report

## Output

```
## Review: <title>

### Spec compliance     PASS | issues
### Architecture        PASS | issues
### Hot-path            PASS | issues
### Determinism         PASS | issues
### Ownership / safety  PASS | issues
### Test quality        PASS | issues

### Verdict: APPROVE | REQUEST CHANGES | NEEDS DISCUSSION

### Issues
| # | Severity | Location | Issue | Direction |
```

## Notes

- Reviewer does not post to GitHub — developer does that:
  `gh pr review <N> --body "..." --request-changes`
- Reviewer uses `skills/code-review.md` and `skills/arch-check.md`
