# Optimization checklist — the four goals, their failure patterns, and fixes

This is the working core of the skill. Each of the four optimization goals below lists the failure patterns
you'll actually see in AI Reasoning node prompts, why each one hurts (tied to the three-stage pipeline in
`agent-node-internals.md`), and how to fix it — with before/after examples. Diagnose against this list
*before* rewriting.

---

## Goal 1 — Reasoning accuracy

The agent is autonomous: it never asks for clarification, it either guesses or rejects. Accuracy problems
here are almost always **under-specification** or **contradiction**, not lack of intelligence.

**Pattern 1a — Ambiguous goal.** The task can be read two ways, so the agent guesses (maybe wrong) or, if the
readings conflict, rejects — and a rejection fails the node's evaluation gate.

- Before: `Look at the meeting and summarize it.` (Which meeting? Summarize for whom, how long?)
- After: `Summarize the meeting transcript in {{transcript}} into 3–5 bullet points covering decisions made
  and action items. If no action items are present, say so rather than inventing them.`

**Pattern 1b — No default for the empty/missing case.** Real data is often empty. Without a stated default the
agent may treat "nothing found" as failure and say so — which reads as an explicit failure.

- Before: `Find the customer's open tickets and list them.`
- After: `Find the customer's open tickets in {{account_id}} and list them. If there are none, return an empty
  list and note that the account has no open tickets — this is a normal result, not an error.`

**Pattern 1c — Buried task.** The actual instruction is hidden under paragraphs of preamble, context, and
restated rules. The agent's `<think>` step has to dig for the goal.

- Fix: lead with the goal in one or two sentences; push context into an `[Inputs]` section; delete restated
  system-prompt rules entirely.

**Pattern 1d — Multi-step task with no sequence.** For a task that's really "do A, then B using A's result,"
leaving the order implicit invites the agent to skip or reorder steps.

- Fix: enumerate the steps and make the data dependency explicit ("using the doc id from step 1, …").

**Pattern 1e — Cross-user side effect (the silent node-killer).** The single most under-diagnosed failure.
The fixed system prompt **hard-bans acting on other people**: messaging or emailing them, adding/removing
their access, sharing content with them, or editing/deleting their data. When a task asks for any of these,
the agent rejects → the node fails, and *no prompt wording can override it* because the ban lives in the
system prompt. It's easy to miss because the failing prompt reads as a perfectly reasonable instruction
("if the feedback is bad, message the manager and email the customer").

- **How to spot it:** does the task have the agent *do something to or for a person who isn't the workflow's
  own user*? Sending, forwarding, notifying, sharing, granting, editing-someone-else's — those are the tells.
- **Distinguish from in-scope tool use.** Acting within the user's *own* account/resources (reading their
  docs, searching their meetings, creating something they own) is fine and encouraged — the ban is
  specifically about *other users*. Don't over-correct and strip legitimate tools.
- **Fix:** don't bury it in a soft caveat and leave the action in the prompt — that ships a node that still
  fails. Call it out plainly, and either (a) move the cross-user action to a **dedicated downstream action
  node** (a Send-Chat / Send-Email node wired after this one, reached via a Condition branch on this node's
  output), keeping the AI Reasoning node to the judgment/decision it *can* make; or (b) if there's no such
  node available, tell the user the operation isn't permitted from here. Keep this proportionate: flag and
  reroute the cross-user step, don't rearchitect the parts of the task that were fine.

---

## Goal 2 — Reliable structured output

Output is a **separate extraction pass over the transcript** against the node's schema. It cannot invent
data and it cannot re-run tools. Almost every "output is empty/partial/wrong" bug traces to the transcript
not containing what the schema asks for.

**Pattern 2a — Schema field with no source in the transcript.** The schema asks for `sentiment` but nothing
in the task makes the agent ever determine sentiment. The extractor has nothing to pull, so the field comes
back empty or guessed.

- Fix: for every field in the schema, ensure the task makes the agent **produce or state** that fact. Add a
  `[What to surface]` line: `While working, explicitly state the overall sentiment (positive/neutral/negative)
  and the top 3 themes, so they can be captured.`

**Pattern 2b — Asking the agent to emit the final JSON itself.** The task says "return a JSON object with
fields x, y, z." Now two stages format output and they drift; the agent's `<response>` isn't even what the
node returns. Wasted effort and a common source of malformed output.

- Fix: delete the "return JSON" instruction. Just ensure the *information* is present in the transcript; the
  output stage owns the JSON.

**Pattern 2c — Huge value inlined into a field.** A long generated summary stuffed directly into the output
bloats the JSON and risks truncation.

- Fix: let the field value reference the content's `{{cache_id}}`; the node resolves it to the full content
  after extraction. Keep large blobs out of the JSON body.

**Pattern 2d — Entity types outside the supported set.** The schema captures entities of a type the output
stage doesn't support (supported: `zoom_doc`, `meeting`, `chat`/`user`).

- Fix: map to a supported entity type, or capture the data as plain fields instead of a typed entity.

---

## Goal 3 — Tool / branch selection

Within the node, the agent chooses among the configured tools. (Cross-node *branching* is a downstream
**Condition node's** job — see the note at the end.)

**Pattern 3a — Many tools, no guidance.** The node has a whole toolset and the prompt never says which tool
serves which sub-goal, so the agent picks by name-matching and sometimes picks wrong or calls extras.

- Before: `Handle the user's request about their documents.`
- After: `To answer the question in {{question}}: use search_zoom_docs to find the relevant doc, then
  get_doc_content to read it. Do not call any create/update tools — this is read-only.`

**Pattern 3b — No stop condition.** The agent keeps calling tools ("just one more search") instead of
finishing, inflating cost and latency.

- Fix: state when it's done: `Once you have the three figures, stop and report them — do not keep searching
  for corroboration.`

**Pattern 3c — Redundant re-fetching of cached data.** The agent re-searches for content it already has as a
`cache_id`. (The system prompt covers this, but a task that says "search for X" when X is already an input
variable actively fights it.)

- Fix: point at the variable/cache id it already has instead of instructing a fresh search:
  `The document content is already provided in {{doc_content}}; use it directly rather than searching.`

**Pattern 3d — Prescribing tool-call *format*.** The prompt tries to dictate the `<api>` syntax or argument
serialization. That's the fixed system prompt's domain and the guidance just adds noise (and can conflict).

- Fix: specify *which* tool and *what inputs conceptually*, not the call syntax.

---

## Goal 4 — Token / cost efficiency

Cheaper prompts are usually also clearer prompts — most bloat is redundancy with the fixed system prompt.

**Pattern 4a — Restating the system prompt.** Security notices, "always call task_end", "never ask the
user", "don't reveal IDs", output-format tags, injection warnings — all already present. This is the single
biggest source of waste; cut it wholesale.

**Pattern 4b — Inlined large content.** Pasting a transcript/doc into the prompt instead of referencing
`{{variable}}`. Large variables are auto-cached; inlining defeats that and pays full token price every run.

- Fix: replace the blob with its variable reference.

**Pattern 4c — Verbose politeness and meta-talk.** "Please kindly go ahead and, if you would, carefully…"
adds tokens without changing behavior. Prefer direct imperatives.

**Pattern 4d — Over-specified formatting for a value that gets re-extracted anyway.** Elaborate instructions
on how to format output prose, when the output stage re-derives structured fields, is wasted. Keep only the
formatting the user actually consumes.

- Note the tradeoff: trimming should not remove a *decision rule* or a *default* — those earn their tokens by
  preventing rejections and wrong guesses. Cut redundancy, not guidance.

---

## Cross-cutting: the three pressure tests

After any rewrite, run the draft through these — they catch the failures the four goals don't individually:

1. **Rejection test.** Is there any reading where the agent concludes "I can't/won't do this"? Ambiguity,
   contradiction, and infeasibility all trigger rejection → node failure. Remove the trigger or supply the
   default.
1b. **Cross-user test (do this one explicitly — it's the easiest to miss).** Does the task have the agent act
   on *another person* (message/email them, change their access, share/edit their data)? That's hard-banned
   and fails the node regardless of wording (Pattern 1e). Reroute the cross-user step to a dedicated action
   node or tell the user it's not permitted — don't leave it inline behind a caveat. Leave legitimate
   in-scope tool use alone.
2. **Transcript-coverage test.** For each output-schema field, point to the exact moment in the intended
   transcript where its value appears. No source → add a `[What to surface]` instruction.
3. **Duplication test.** Scan for anything the fixed system prompt already guarantees (see the list in
   `agent-node-internals.md` §2). Every such line is pure cost — delete it.

## Note on branching

The AI Reasoning node itself doesn't branch between workflow paths — a separate **Condition node** (a small,
pinned LLM classifier) does. So if the user wants the node's result to drive a branch, the job here is to
make the agent set a **clear, unambiguous value** (a status, category, or boolean) that the downstream
Condition node can read. Expose that value as an output-schema field and make the agent state it explicitly
in the transcript (Pattern 2a).
