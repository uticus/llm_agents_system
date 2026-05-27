# Skill: Clarifying Dialog
# File: .cursor/skills/dialog.md

> Algorithm for conducting a focused clarifying dialog with the developer.
> Used by: Analyst
> Goal: transform a raw request into an unambiguous problem statement.

---

## Algorithm

### Step 1: Read and parse the request

Read the developer's full message without interrupting.
Internally identify:
- What is clearly stated
- What is ambiguous or missing
- What assumptions you might be tempted to make (do not make them)

### Step 2: Prioritize what to ask

Rank gaps by impact on downstream agents:
1. Goal clarity — without this, nothing else can proceed
2. Scope boundaries — prevents scope creep in planning
3. Hard constraints — performance, ABI, compatibility, determinism
4. Success criteria — needed by Test designer
5. Dependencies — needed by Decomposer and Architect

Ask about high-impact gaps first.
Do not ask about implementation details — those are resolved in later phases.

### Step 3: Form questions

Rules for forming questions:
- One topic per question — never bundle two questions into one
- Ask 2-3 questions maximum per dialog turn
- Phrase questions as open-ended when possible ("What should happen when...?")
  not leading ("Should it use X or Y?")
- If you need to propose options — offer no more than 3, briefly
- If after 3 dialog turns the request is still ambiguous — stop and escalate:
  "I still have unresolved questions: [list]. How should we proceed?"

### Step 4: Process the answer

After each developer response:
- Mark resolved gaps
- Identify any new gaps the answer revealed
- If the answer is still ambiguous — ask one focused follow-up
- Do not move on until the gap is genuinely resolved

### Step 5: Summarize and confirm

When all high-impact gaps are resolved:
- Write a structured summary of the request
- Cover: goal, scope, constraints, success criteria, dependencies, open questions
- Present it to the developer: "Here is my understanding. Is this accurate?"
- If the developer requests corrections — update the summary and confirm again
- Do not write the output file until the developer explicitly confirms

### Step 6: Write output

Check `tasks/inbox/` for the highest existing number. Use next available NNN.
Write `tasks/inbox/request-NNN.md` using the format defined in `analyst.md`.
Notify the developer with the file path.

---

## Handling difficult situations

**Developer gives a very short request ("add X to Y")**
Do not assume. Ask about goal, scope, and constraints before anything else.

**Developer provides contradictory requirements**
Surface the contradiction explicitly: "These two requirements seem to conflict — [A] vs [B].
Which takes priority, or should we resolve this differently?"

**Developer keeps expanding scope during dialog**
Note each expansion. When scope grows significantly, ask:
"This has expanded to include [list]. Should these be separate requests,
or do you want them handled together?"

**Developer says "you decide"**
Do not decide. Explain that architectural and scope decisions belong to later phases.
Ask the developer to choose, or flag it as an open question for the design phase.

**Request touches a frozen or sensitive area**
Note it explicitly in the open questions section.
Do not make assumptions about what is allowed — Architect resolves this.
