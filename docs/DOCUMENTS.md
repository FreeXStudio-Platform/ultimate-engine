<!-- title: DOCUMENT_TYPES -->
<!-- generated from document_types.json by `python3 -m tools.docgen.doc_types --write`; do not edit -->
# Document types

How documents are written, linked and kept true: [the document rules](DOCUMENT_RULES.md).

Every document has a type, named by its id prefix (`REQ-001` is a requirements document). This page lists the
types in the order a project writes them, what each is for, when it is needed, which types it builds on and the
sections it must hold. `ultimate-engine new <TYPE> "<title>"` writes a document with every section in place;
`ultimate-engine doc-map` shows which documents a project has, which it still needs and in what order to read them.

**Every project needs at least:** `BRF`, `STATE`, `REQ`, `SYS`, `PLAN`, `TEST`.

| order | prefix | type | needed | builds on |
|---|---|---|---|---|
| Start | `BRF` | Project brief | always: the first document of every project | — |
| Start | `STATE` | Project state | always: written with the brief and kept current | `BRF` |
| Start | `GLO` | Glossary | when the project has terms or ids of its own | `BRF` |
| Decide what | `REQ` | Requirements | always | `BRF` |
| Decide how | `SYS` | System architecture | always | `REQ` |
| Decide how | `DATA` | Data model | when the system stores or processes data | `REQ`, `SYS` |
| Decide how | `SEC` | Security and privacy | when the system has users, personal data, secrets, money or a network surface | `REQ`, `SYS` |
| Contracts | `SPEC` | Component specification | one for each part named in the system architecture that holds behaviour | `SYS`, `REQ` |
| Contracts | `API` | Interface reference | when the system exposes an interface to people or programs | `SPEC` |
| Deliver and prove | `PLAN` | Delivery plan | always | `REQ`, `SYS` |
| Deliver and prove | `TEST` | Verification plan | always | `REQ`, `SPEC` |
| Deliver and prove | `FND` | Findings and deviations | once building starts | `SPEC`, `TEST` |
| Operate and explain | `OPS` | Operations runbook | when the system is deployed or run for others | `SYS`, `SEC` |
| Operate and explain | `GUIDE` | Usage guide | when the result has users | `REQ` |
| Operate and explain | `REF` | Reference table | when readers need to look facts up | — |
| Operate and explain | `WF` | Workflow explainer | when a process involves more than one step or role | — |
| Any time | `ADR` | Decision record | for every decision that is hard to reverse, surprising without context, or a real trade-off; and for every locked-rule change | — |
| Any time | `CHG` | Change record | for every change to a finished document or a locked rule | — |

## Start

*What problem, for whom, and what would success look like?*

### `BRF` — Project brief

Turns an idea, even one sentence, into a problem, a proposed solution, a goal and a scope that every later document answers to.

- **Needed:** always: the first document of every project.
- **Builds on:** nothing; it can be written first.
- **Describes blueprint parts:** no.
- **Default surface and audience:** repo; everyone working on the project.

| section | what it holds |
|---|---|
| Idea | The idea as it was first stated, word for word. |
| Problem | Who has the problem, when it occurs, what it costs them today. |
| Proposed solution | The solution in a few sentences, and what it does not try to do. |
| Goal | One sentence that says what finished means. Later documents are checked against it. |
| Users | Who uses the result and who is affected by it. |
| Scope | In scope and out of scope, as two lists. |
| Success measures | How success is measured, each with a number or a test. |
| Constraints | Time, money, platforms, rules and anything fixed in advance. |
| Open questions | What is not known yet, and who will answer it. |

### `STATE` — Project state

The one page anyone opens first: where the project stands, what to read in what order, which source wins, and the single next action.

- **Needed:** always: written with the brief and kept current.
- **Builds on:** `BRF`.
- **Describes blueprint parts:** no.
- **Default surface and audience:** repo; everyone working on the project.

| section | what it holds |
|---|---|
| Status | Where the project stands now, in a few lines. Replaced in place on every change, never appended below. |
| Read first | The documents to read, in order, for someone new. Point at DOCUMENT_MAP.json for the full list. |
| Order of authority | Which source wins when two disagree (DOCUMENT_RULES.md D4), and anything this project adds. |
| Next action | Exactly one next action, who takes it and what finished looks like. |
| Open blockers | Each blocker with its owner and how it can be resolved or waived. None yet is a valid answer. |

### `GLO` — Glossary

Defines the project's own terms and the id prefixes it uses, once, so every document uses them the same way.

- **Needed:** when the project has terms or ids of its own.
- **Builds on:** `BRF`.
- **Describes blueprint parts:** no.
- **Default surface and audience:** repo; everyone.

| section | what it holds |
|---|---|
| Terms | Each term and its meaning, alphabetically. |
| Identifiers | Each id prefix the project uses (documents, requirements, components, decisions) and what it names. |

## Decide what

*What exactly must be true when the work is finished?*

### `REQ` — Requirements

States, as numbered checkable lines, everything that must be true when the work is finished.

- **Needed:** always.
- **Builds on:** `BRF`.
- **Describes blueprint parts:** no.
- **Default surface and audience:** repo; builders and verifiers.

| section | what it holds |
|---|---|
| Functional requirements | Numbered (REQ-n.1, REQ-n.2 ...), one behaviour per line, each traceable to the brief. |
| Quality requirements | Performance, reliability, accessibility, privacy and security, each with a measure. |
| Acceptance criteria | For each requirement, the test or observation that shows it holds. |
| Out of scope | What is deliberately not required, so nobody builds it. |

## Decide how

*Which parts, which data, which protections?*

### `SYS` — System architecture

Names the parts of the system, their boundaries and how data and control move between them. Each part is a container in the project blueprint.

- **Needed:** always.
- **Builds on:** `REQ`.
- **Describes blueprint parts:** yes — list them in `covers`.
- **Default surface and audience:** repo; builders.

| section | what it holds |
|---|---|
| Context | The system, its users and the outside systems it talks to. |
| Parts | Each part with its job; each part's id is the blueprint container id. |
| Boundaries | Trust, network and ownership boundaries, and what crosses each. |
| Data flow | How data moves through the parts, with a figure. |
| Deployment | Where each part runs. |
| Decisions | The decision records (ADR) that shaped this structure. |

### `DATA` — Data model

Defines what the system stores: entities, fields, ownership, retention and sensitivity.

- **Needed:** when the system stores or processes data.
- **Builds on:** `REQ`, `SYS`.
- **Describes blueprint parts:** yes — list them in `covers`.
- **Default surface and audience:** repo; builders.

| section | what it holds |
|---|---|
| Entities | Each entity, its fields and types, and its relations, with a figure. |
| Ownership | Which part writes each entity; one writer per entity. |
| Sensitivity | Personal, secret or regulated fields and how each is protected. |
| Retention | How long each entity is kept and how it is deleted. |
| Migrations | How the model changes without losing data. |

### `SEC` — Security and privacy

Names what must be protected, from whom, and the controls that protect it.

- **Needed:** when the system has users, personal data, secrets, money or a network surface.
- **Builds on:** `REQ`, `SYS`.
- **Describes blueprint parts:** yes — list them in `covers`.
- **Default surface and audience:** repo; builders and reviewers.

| section | what it holds |
|---|---|
| Assets | What is valuable: data, keys, money, availability. |
| Threats | Who could attack or misuse each asset, and how. |
| Controls | The control for each threat and where it is enforced. |
| Secrets | Where secrets live and how they are used; never their values. |
| Privacy | What personal data is collected, why, for how long, and who sees it. |
| Residual risk | What is left unprotected, its bound and its owner. |

## Contracts

*What does each part promise, and through which interface?*

### `SPEC` — Component specification

The normative contract of one part: what it must do, what it provides and needs, and how it fails.

- **Needed:** one for each part named in the system architecture that holds behaviour.
- **Builds on:** `SYS`, `REQ`.
- **Describes blueprint parts:** yes — list them in `covers`.
- **Default surface and audience:** repo; builders and verifiers.

| section | what it holds |
|---|---|
| Purpose | The part's job in one paragraph. |
| Normative requirements | MUST / MUST NOT lines, each traceable to REQ. |
| Interfaces provided | What other parts may call, with inputs, outputs and errors. |
| Interfaces consumed | What this part calls, and what it assumes about it. |
| State model | The states, transitions and stored state, with a figure when there is more than one state. |
| Failure and recovery | Each failure, how it is detected and how the part recovers. |
| Security boundary | What the part trusts, what it checks, what it never does. |
| Completion | The checks that show this part is finished. |

### `API` — Interface reference

Every callable surface a consumer may use: endpoints or commands, parameters, results and errors.

- **Needed:** when the system exposes an interface to people or programs.
- **Builds on:** `SPEC`.
- **Describes blueprint parts:** yes — list them in `covers`.
- **Default surface and audience:** web; consumers of the interface.

| section | what it holds |
|---|---|
| Overview | What the interface is for and how to authenticate. |
| Operations | Each operation with its parameters and results. |
| Errors | Every error, what causes it and what to do. |
| Limits | Rate, size and time limits. |
| Examples | A complete request and response for the common tasks. |

## Deliver and prove

*In what order is it built, and how is each promise shown to hold?*

### `PLAN` — Delivery plan

The order of the work: milestones, what each delivers, what each depends on, and how each is accepted.

- **Needed:** always.
- **Builds on:** `REQ`, `SYS`.
- **Describes blueprint parts:** no.
- **Default surface and audience:** repo; everyone working on the project.

| section | what it holds |
|---|---|
| Milestones | Each milestone, what it delivers and the requirements it closes. |
| Order and dependencies | What must finish before what, with a figure. |
| Acceptance set | For each milestone, 5 to 10 checks, each a command or observation with an expected result, written before building. |
| Risks | What could stop the plan, and the response. |
| Status | Where the plan stands. Derived from the documents' states where possible, never restated by hand. |

### `TEST` — Verification plan

How each requirement and contract is shown to hold, and what evidence is kept.

- **Needed:** always.
- **Builds on:** `REQ`, `SPEC`.
- **Describes blueprint parts:** no.
- **Default surface and audience:** repo; builders and verifiers.

| section | what it holds |
|---|---|
| Coverage | Each requirement and the tests that prove it; none left without one. |
| Test levels | Unit, integration, end-to-end and manual checks, and what each catches. |
| Negative and adversarial cases | What must be refused, and the tests that try it. |
| Evidence | What a passing run leaves behind and where it is kept. |
| Independent verification | Who verifies, separately from who built, and what they are given. |

### `FND` — Findings and deviations

Where built code differs from the documented design, and the defects found in documents, each with its state and owner.

- **Needed:** once building starts.
- **Builds on:** `SPEC`, `TEST`.
- **Describes blueprint parts:** yes — list them in `covers`.
- **Default surface and audience:** repo; builders and verifiers.

| section | what it holds |
|---|---|
| Deviations | Each place where the built system differs from the design: what differs, why, and whether the code or the design will change. |
| Findings | Each defect found in a document or the system: id, severity, state, owner. |
| Accepted risks | Each risk accepted rather than fixed: description, bound, owner, resolution path. |

## Operate and explain

*How is it run, recovered and used?*

### `OPS` — Operations runbook

How the system is deployed, watched, recovered and rolled back.

- **Needed:** when the system is deployed or run for others.
- **Builds on:** `SYS`, `SEC`.
- **Describes blueprint parts:** yes — list them in `covers`.
- **Default surface and audience:** repo; operators.

| section | what it holds |
|---|---|
| Deploy | The exact steps, and how to tell they worked. |
| Monitor | What is watched, the thresholds and who is alerted. |
| Recover | Each known failure and its recovery steps. |
| Roll back | How to return to the previous release, and what is lost. |
| Contacts | Roles to contact, not personal data. |

### `GUIDE` — Usage guide

Task-oriented instructions for the people who use the result.

- **Needed:** when the result has users.
- **Builds on:** `REQ`.
- **Describes blueprint parts:** no.
- **Default surface and audience:** web; users.

| section | what it holds |
|---|---|
| Before you start | What the reader needs first. |
| Tasks | Each task as numbered steps with the result to expect. |
| Troubleshooting | The common problems and what to do. |

### `REF` — Reference table

Enumerated facts: options, codes, limits and defaults. Derived from code wherever code owns them.

- **Needed:** when readers need to look facts up.
- **Builds on:** nothing; it can be written first.
- **Describes blueprint parts:** no.
- **Default surface and audience:** web; users and builders.

| section | what it holds |
|---|---|
| Contents | The table or tables. |
| Source | Where each fact comes from, and the check that keeps it current. |

### `WF` — Workflow explainer

How a process runs end to end: steps, roles, inputs and outputs.

- **Needed:** when a process involves more than one step or role.
- **Builds on:** nothing; it can be written first.
- **Describes blueprint parts:** no.
- **Default surface and audience:** web; everyone in the process.

| section | what it holds |
|---|---|
| Steps | The steps in order, with a figure. |
| Roles | Who does each step. |
| Inputs and outputs | What each step takes and produces. |

## Any time

*What was decided, and what changed?*

### `ADR` — Decision record

One decision, its context, the options considered and its consequences.

- **Needed:** for every decision that is hard to reverse, surprising without context, or a real trade-off; and for every locked-rule change.
- **Builds on:** nothing; it can be written first.
- **Describes blueprint parts:** no.
- **Default surface and audience:** repo; builders and reviewers.

| section | what it holds |
|---|---|
| Context | The situation that forced a decision. |
| Options | Each option considered, with its cost. |
| Decision | The option chosen. |
| Consequences | What follows, including what becomes harder. |

### `CHG` — Change record

One recorded change: what changed, why, and what it affects.

- **Needed:** for every change to a finished document or a locked rule.
- **Builds on:** nothing; it can be written first.
- **Describes blueprint parts:** no.
- **Default surface and audience:** repo; everyone.

| section | what it holds |
|---|---|
| Change | What changed, by file and section. |
| Reason | Why it changed. |
| Impact | Which documents, parts and users it affects. |
