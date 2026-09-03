# Responder Readiness and Recovery Forecaster — Full Presentation Script

## Slide 1 — Title | 0:00–0:40

Hello. My capstone is the Responder Readiness and Recovery Forecaster. It is an advisory multi-agent system that helps volunteer fire and EMS leaders recognize team-level operational strain before it becomes a coverage or safety problem. I use Cranberry Township, Pennsylvania as the standing test case. The public organizational facts are real, but every workload, staffing, alert, recovery, and Guard or Reserve value in the demonstration is synthetic. The central idea is simple: give leaders an earlier, grounded planning signal while keeping every consequential decision in human hands.

## Slide 2 — The operational problem | 0:40–1:30

Volunteer departments can face several pressures at once. Calls may compress recovery time. Overnight incidents can interrupt sleep. Work schedules, training, heat, and Guard or Reserve commitments can reduce availability. Each factor may be manageable by itself. The concern is the combination.

Cranberry Township gives the project a realistic public setting. The township identifies the volunteer fire company, its two stations, its training facility, and Butler County 911 dispatch. Cranberry Township EMS is a separate service, so I do not combine the agencies. The intended user is an authorized fire or EMS leader.

An agent-based approach fits because this is not one simple answer. Evidence must be checked. Readiness must be assessed. Plans must be compared. A separate safety review must be able to stop a weak recommendation.

## Slide 3 — A deliberately narrow scope | 1:30–2:20

I first considered predicting burnout. I changed that framing because burnout is an occupational phenomenon usually assessed at the individual level. Team-level operational data cannot establish it. This system forecasts team strain instead.

It accepts aggregate counts, ratios, dates, and public alerts. It rejects free-text notes and unexpected person-level fields. That includes names, medical information, disciplinary records, actual military orders, and unit details. Guard or Reserve commitments appear only as an aggregate availability count.

The agent cannot control dispatch, change schedules, contact responders, or request mutual aid. Its outputs are monitoring advice, options that require human review, or an abstention. That boundary is not just a disclaimer. It is enforced in the input schema, tool permissions, output contract, and tests.

## Slide 4 — How the system works | 2:20–3:00

The workflow moves through five stages: coordinate, retrieve, assess, explore, and critique. It also follows a ReAct-style loop: understand, act, observe, and update.

Observations change the next step. If an alert is expired or was issued after the case time, the system does not treat it as current. If approved guidance is unavailable, it does not create a plan. If the top plans are too close, it shows both and escalates. That makes the stopping rules visible.

## Slide 5 — Five agents with clear ownership | 3:00–3:45

The five roles have clear ownership. The Coordinator routes work and applies the final decision contract. The Evidence Agent validates and retrieves sources. The Readiness Analyst calculates the strain score. The Planner explores options. The Critic rejects unsafe or unsupported finalists.

Most communication is one-way to limit delay. Shared state carries the case, evidence, observations, candidates, and unresolved questions. SQLite stores accepted-case traces and aggregate history, not individual profiles. The design maps CrewAI to role separation, LangChain to control flow, and MCP to shared state. The prototype implements those responsibilities directly in standard Python so it runs without API keys.

## Slide 6 — Retrieval grounds the response | 3:45–4:45

The course architecture separates parametric model knowledge from nonparametric external memory. This offline prototype has no language model. It implements the inspectable public corpus and deterministic rules. A future model-backed version could combine both, while retrieved evidence would control factual grounding.

The Evidence Agent uses a transparent, DPR-inspired retriever. It builds workload, capacity, and environment queries. Separate query and passage weights help match plain incident language to formal guidance. Cosine ranking returns up to four passages, while a diversity rule preserves active weather, heat, staffing, and fatigue topics.

The demo retrieves NWS alert guidance, CDC/NIOSH heat guidance, Cranberry Township fire-services context, and CDC/NIOSH fatigue guidance. One evidence set supports the full advisory. That is a RAG Sequence-style choice. It is easier to audit than changing evidence token by token. This is not a trained DPR model or neural marginalization.

## Slide 7 — Tree-of-Thought planning | 4:45–5:25

Tree-of-Thought is used only for response planning, where several choices compete. A thought is one action. A node is a partial plan. A branch adds another action. Beam width three and depth three keep the search bounded.

Plans are scored for coverage, safety, recovery, feasibility, evidence, privacy, fairness, and reversibility. Hard failures are pruned. Safety-relevant branches stay in the search when heat or reduced coverage is active. The action effects are synthetic demonstration values. They are not operational facts.

## Slide 8 — Cranberry Township synthetic demo | 5:25–6:35

Here is the main demonstration. Every operational value is invented. The seven-day case has five incidents in seventy-two hours, three overnight calls, a fourteen-hour maximum shift, seventy-two percent availability, two fictional Guard or Reserve conflicts, outdoor training, and a hypothetical heat warning.

The case passes the privacy and range checks. The Evidence Agent returns four passages. The Analyst assigns a high strain score of nine out of nine, with rule-based confidence of zero point nine. The planner evaluates twenty-six nodes and produces two finalists.

The top plan scores ninety-three. It proposes an authorized mutual-aid review, a recovery window, and a heat work-rest cycle. The alternate scores ninety and replaces the recovery window with moving the synthetic training. The system returns HUMAN_REVIEW_REQUIRED because every proposed operational change requires authorized approval. The three-point gap is within the closely-scored threshold, so it adds a closely-scored-plans flag and a second sentence to the decision reason. It shows both options and takes no action. This is the behavior I wanted: useful preparation without automatic control.

## Slide 9 — The same run in the browser | 6:35–7:10

The same engine runs behind a local browser interface, so the run is inspectable rather than described. On the left is the high-strain case from the previous slide, rendered live: the decision, the strain dial, and the audit snapshot. On the right the same interface refuses to run. A synthetic private-data flag is set, so the guardrail stops the forecast before any evidence is retrieved or any plan is scored: zero sources, zero plans, no recommendation released. Neither panel is a mock-up. Both are live prototype output on synthetic data.

## Slide 10 — Guardrails and evaluation | 7:10–7:55

The release contract has three states. ADVISORY means monitor. HUMAN_REVIEW_REQUIRED means an authorized leader must decide. ABSTAIN means no plan is released.

All six labeled forecast cases reached the expected decision. Required escalation recall was one hundred percent. Both fallback cases stopped safely. The critic rejected all three unsafe red-team plans. No hard safety violation occurred. The expanded repository also passed fifty-five automated tests, including every packaged dataset, boundary values, concurrency, GUI routes, malformed types, future dates, private fields, unapproved sources, request saturation, and browser-request boundaries.

These are software checks, not proof of field effectiveness. The cases are small and deterministic. The labels share the rules’ assumptions. Citation coverage shows that support tags exist. It does not prove that an expert agrees with the recommendation.

## Slide 11 — Repository, limitations, and next steps | 7:55–8:50

The main limits are clear. The retriever is DPR-inspired rather than trained. Thresholds and action effects are illustrative. Alerts are recorded fixtures. The corpus is small. There has been no field calibration or user testing.

The local Git repository is ready. It uses `main` and includes source code, a browser-based GUI, sixteen showcase scenarios, tests, example outputs, safety documents, continuous integration, and an MIT License. A manual review found no obvious credentials or real responder records. The actual public URL is not shown because GitHub authentication and the account-controlled remote are still pending.

Next, I would add a read-only NWS adapter with recorded fixtures. I would compare this retriever with BM25 and a real embedding model. I would build a larger, independently labeled scenario set. Only after expert review would I consider a shadow-mode pilot with no operational authority.

## Slide 12 — Closing reflection | 8:50–9:35

This capstone does not replace a chief, captain, or EMS leader. It organizes evidence, shows assumptions, compares options, and knows when to stop.

My main lesson was that a narrower problem is safer and easier to test. Grounded retrieval and independent criticism worked well because they made evidence and stopping conditions visible. My next improvement would be independent labels and a read-only live weather tool.

The system brings the course concepts into one traceable flow: tools, ReAct, retrieval, memory, Tree-of-Thought, multiple agents, and guardrails. The result is ready as a course demonstration, not an operational product. Real use would need local policy, expert validation, and much more evidence. Thank you.

## Optional 90-Second Elevator Pitch

My capstone is the Responder Readiness and Recovery Forecaster. It helps volunteer fire and EMS leaders recognize team-level operational strain before it becomes a coverage or safety problem. I use Cranberry Township, Pennsylvania as a realistic test case, but all workload, staffing, alert, and Guard or Reserve values are synthetic.

The system does not diagnose burnout or judge any individual. It rejects private personal data and cannot change schedules, control dispatch, contact responders, or request mutual aid. It gives an authorized leader a grounded planning signal.

Five agents work together. One coordinates the case. One retrieves public guidance. One calculates strain. One explores response plans through bounded Tree-of-Thought search. A separate safety critic rejects weak or unsupported plans. The final result is either a monitoring advisory, a request for human review, or an abstention.

In the main demo, the agent retrieves official weather, heat, local fire-services, and fatigue guidance. It evaluates twenty-six planning nodes and finds two safe options. It stops for human review because every operational change requires authorized approval, and the three-point gap between them adds a closely-scored-plans flag rather than pretending the top score is certain. The repository passed fifty-five automated tests and includes sixteen additional GUI showcase cases. The project shows how agentic AI can support public-safety planning while keeping evidence visible and decisions human.

## Demonstration Backup

If the live browser interface is not available, run the command-line demonstration. If neither is available, show the saved `high_strain_forecast.json` output. Point first to `decision: HUMAN_REVIEW_REQUIRED`. Then show the score gap of three, the four retrieved evidence records, the two finalists, and the five-agent trace. Close by showing the evaluation report with six forecast cases, three unsafe critic cases, one hundred percent mandatory escalation recall, and zero hard safety violations. State that the saved files are deterministic prototype outputs and not live Cranberry Township conditions.

## Likely Questions and Short Answers

### Why not predict individual burnout?

Burnout is an occupational phenomenon usually assessed at the individual level. The available data cannot support that conclusion. Team-level strain is more measurable and better aligned with operational planning.

### Why is Guard or Reserve status included?

Only aggregate availability conflicts are used. The system does not store orders, units, or individual service details. The factor represents a scheduling constraint, not a risk label.

### Why use multiple agents instead of one?

Evidence review, scoring, planning, and safety criticism are different tasks. Separate ownership makes errors easier to find and prevents the planner from approving its own work.

### Are the evaluation results meaningful?

They show that the software follows its rules in six synthetic cases. They do not establish real forecasting accuracy. Field claims require independent data and expert validation.

### Would you deploy this now?

No. I would first conduct an offline expert review, add live-source tests, expand the scenario set, and run a shadow-mode pilot with no operational authority.
