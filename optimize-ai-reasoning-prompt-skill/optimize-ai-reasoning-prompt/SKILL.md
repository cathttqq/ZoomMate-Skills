---
name: optimize-ai-reasoning-prompt
description: >-
  Rewrites and optimizes the prompt for an AI Reasoning node (the Agent node) in a Zoom
  Agentic Workflow. Use whenever someone is writing, tuning, debugging, or improving the
  prompt inside an AI Reasoning / Agent node — e.g. "optimize my AI Reasoning node prompt",
  "my agent node keeps failing or rejecting the task", "the node's structured output is
  empty or missing fields", or when they paste a task prompt from a Zoom workflow node to
  clean up. Also trigger when someone is *building* a new AI Reasoning node and only
  describes what it should do — the skill drafts the prompt from that. Key insight it
  applies: the prompt you author is the *task prompt* (a user message to a tool-using ReAct
  agent that already has a fixed system prompt), and the node runs two more hidden LLM stages
  after it — a success-gate evaluation and schema-based output extraction — so handling all
  three is what makes the prompt work live. Do NOT use for the Condition, Tool, or plain LLM
  node — different mechanics.
---

# Optimize the AI Reasoning (Agent) node prompt

The AI Reasoning node — called the **Agent node** in code (`AgentNode`) — is the reasoning-and-acting
node of a Zoom Agentic Workflow. A workflow builder configures it with a **prompt**, a set of
**tools/toolsets**, a **model**, and an optional **output schema**. This skill optimizes that prompt.

The reason a careful skill is needed here — rather than "just make the prompt clearer" — is that the
node is not a single LLM call. The prompt you write drives only the first of **three** LLM stages, and
the other two are fixed and invisible from the node UI. Most prompts that look good in isolation fail
because they fight the fixed stages instead of cooperating with them. Internalize the model below before
you touch a single line.

## The mental model: what your prompt actually is

**Your prompt is the _task prompt_ — a user message to a ReAct agent, not a system prompt.**

When the node runs, it does this (see `references/agent-node-internals.md` for the code-level detail):

1. **ReAct agent loop.** Your task prompt is rendered (Jinja2) and sent as the *user message* to a
   single tool-using agent. That agent already carries a large **fixed system prompt** you do not
   control and should not restate. The system prompt alone handles: prompt-injection defense and the
   `[Read Only Content]` data markers, the `<think>/<api>/<response>` output format, the **mandatory
   `task_end()` call**, full **autonomy** ("never ask for clarification, use reasonable defaults"),
   idempotency / de-duplication via conversation history, `cache_id` handling, hiding technical IDs,
   an absolute **ban on cross-user operations**, and Zoom `@mention` formatting. The agent calls your
   configured tools in a loop until it calls `task_end()`.

2. **Evaluation (a hidden success gate).** A *separate* LLM call reads the whole transcript and returns
   `{"success": true/false, ...}`. **If it returns `false`, the entire node errors out.** It is
   deliberately lenient — it fails *only* on clear errors/exceptions or when the agent **explicitly
   rejected or said it could not do the task**. Empty results, no matches, and short summaries all count
   as success. The practical consequence is large: an ambiguous, contradictory, or infeasible task
   prompt makes the agent reject → the node fails. A prompt that lets the agent attempt and finish
   passes.

3. **Output generation (schema extraction from the transcript).** If the node has an output schema,
   another *separate* LLM call extracts JSON matching that schema **from the conversation history** —
   it does not re-run the task. **Any field's value must already appear somewhere in the agent's
   dialogue or tool results, or it cannot be extracted.** This runs in parallel with evaluation.

Three consequences fall directly out of this model, and they drive every rewrite:

- **Don't duplicate the system prompt.** Re-stating security rules, "always call task_end", "don't ask
  the user", "return valid JSON", "don't expose IDs", output-format tags — all of that is already there.
  Repeating it wastes tokens and occasionally conflicts with the real system prompt. Cut it.
- **Keep the agent attempting, never rejecting.** Ambiguity is the enemy, because the agent is autonomous
  and will either guess (fine) or reject (fails the node). Resolve ambiguity *for* it and supply defaults.
- **Flag cross-user side effects — they silently kill the node.** The fixed system prompt hard-bans acting
  on *other people* (messaging/emailing them, changing their access, sharing or editing their data). If the
  task asks for that, the agent rejects and the node fails — and no amount of prompt wording fixes it,
  because the ban is in the system prompt, not your prompt. Distinguish this from legitimate **in-scope**
  tool use (acting within the user's own account/resources), which is fine. When you spot a cross-user
  action, don't bury it in a caveat: call it out plainly, and move it to a **dedicated downstream action
  node** (e.g. a Send-Chat / Send-Email node) or tell the user it isn't permitted here. See the check in
  `references/optimization-checklist.md`.
- **Make the transcript contain what the schema needs.** The output stage can only surface facts the
  agent actually produced. If a schema field has no home in the conversation, name it in the task so the
  agent gathers or states it.

## Workflow

### 1. Detect the mode

- **Optimize an existing prompt** — the user pasted a task prompt (or a whole node). Diagnose it against
  the checklist below and rewrite.
- **Build from a description** — the user only described what the node should do. Draft the task prompt
  from scratch using the template below.

If the user also shares the **tools/toolset**, the **output schema**, and the **upstream variables**, use
them — they are what make the difference between a generic prompt and a tuned one. If they didn't, ask for
whichever is relevant (you rarely need all three), but don't block on it: you can produce a strong draft
and mark the spots that depend on the missing piece.

### 2. Diagnose (for existing prompts)

Read the prompt against **`references/optimization-checklist.md`**, which is the heart of this skill — it
maps each of the four optimization goals (reasoning accuracy, reliable structured output, tool selection,
token efficiency) to concrete failure patterns and their fixes, with before/after examples. Identify which
patterns apply before rewriting; don't rewrite blind.

### 3. Rewrite

Produce the task prompt using this structure. It's a default, not a straitjacket — a two-line task doesn't
need all of it, and you should drop sections that add nothing.

```
[Goal] One or two sentences: what this node must accomplish, stated as a concrete outcome.

[Inputs] The upstream data the node works from, referenced as {{variable_name}} (see Variables below).

[Steps / approach] For multi-step tasks, the sequence — including which tool to use for which sub-goal
and in what order. Name tools explicitly when the node has several and the choice isn't obvious.

[Decisions & defaults] How to resolve the ambiguity the agent will hit, and the default to take when
data is missing — so it attempts instead of rejecting.

[What to surface] The facts/values the agent must state or gather, so the output-generation stage can
extract every schema field. Only needed when the node has an output schema.
```

Then pressure-test the draft against the three stages: Would the agent ever say "I can't"? (rejection →
node failure) — **and specifically, does the task ask the agent to act on another user?** (cross-user →
guaranteed rejection; pull it into a dedicated action node instead). Does every output-schema field have a
source in the intended transcript? Did you re-state anything the fixed system prompt already covers? (cut it).

### 4. Deliver

**Output the optimized prompt only** — a single clean, ready-to-paste block, no commentary woven in. The
user asked for a paste-ready prompt, so lead with it. You may add a short, clearly separated "what changed
and why" note *after* the prompt if the rewrite was substantial, but keep the prompt itself pristine and
copyable. Never wrap the prompt in explanation the user has to edit out.

## Variables and Jinja2 (get this exactly right)

Upstream node outputs and workflow variables are injected into the task prompt with **Jinja2**, using
`{{variable_name}}` syntax; nested values use dot notation (`{{node_output.field}}`).

- **Reference large content, don't paste it.** Large variable values are automatically cached and injected
  wrapped in read-only data tags. Pasting a big blob of upstream text inline defeats that and burns tokens —
  write `{{transcript}}`, not the transcript.
- **Undefined variables pass through literally.** Rendering preserves unknown `{{...}}` as-is rather than
  erroring, so a typo'd `{{transcirpt}}` silently ends up as literal text in the agent's prompt. Double-check
  every variable name against what upstream actually emits.
- **Only use `{{...}}` inside a tool parameter when that parameter documents Jinja2 support** — otherwise the
  agent is told to treat it as a literal. This matters when you're telling the agent what to pass to a tool.

## Structured output: couple the prompt to the schema

Because output is a separate extraction pass over the transcript, the task prompt and the schema have to be
designed together:

- For each schema field, make sure the agent will **produce or state that fact** during the task. Missing
  transcript coverage is the #1 cause of empty/partial output.
- **Don't ask the agent to hand-build the final JSON** in its response — that's the extraction stage's job,
  and doing it twice invites drift. Just make the information present and clear.
- For a large field value (e.g. a long summary the agent generated via a tool), you can have the value
  reference a `{{cache_id}}`; the system resolves it to the real content. Good for keeping big content out of
  the JSON while still delivering it.
- If the node feeds a downstream **Condition node** for branching, remember the branching decision happens in
  *that* node, not this one — so expose the field the Condition node will read (e.g. a clear category/status
  value), and make sure the agent sets it unambiguously.

## Guardrails

- **Stay in scope.** This skill is for the AI Reasoning / Agent node's task prompt. If the user is actually
  editing a **Condition node** (LLM-based branching, pinned system prompt), a **Tool node** (deterministic
  single-tool call with field mappings), or a plain **LLM node** (has its own `system_prompt` field), say so —
  the mechanics differ and this skill's advice won't transfer.
- **Don't invent tools, variables, or schema fields.** If the rewrite depends on a tool or variable you can
  only assume exists, mark it as an assumption instead of quietly baking it in.
- **Preserve intent.** When optimizing, keep the user's actual task and constraints; tighten wording, resolve
  ambiguity, and cut redundancy — don't silently change what the node does.
- **Don't fight the fixed stages.** No "output ONLY JSON and nothing else", no re-litigating security, no
  "you may ask me if unclear" — the system prompt already settles all of these, and contradicting it makes
  behavior worse, not better.
