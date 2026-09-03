# Responder Readiness and Recovery Forecaster

## Executive Summary

My capstone is an advisory system that helps volunteer fire and EMS leaders recognize team-level operational strain before it becomes a coverage or safety problem. The standing test case is Cranberry Township in Butler County, Pennsylvania. The Cranberry Township Volunteer Fire Company serves the community from the Haine and Park stations and is dispatched through Butler County 911. Cranberry Township EMS is a separate organization. The prototype does not combine those agencies or claim access to either organization’s internal information.

The demonstration uses only public guidance and synthetic operational data. It does not accept free-text notes or person-level fields such as names, medical records, military orders, disciplinary history, or individual performance data. It does not diagnose burnout or decide whether a responder is fit for duty. It also cannot change a schedule, contact a responder, control dispatch, or request mutual aid. Its purpose is narrower. It estimates whether the team may face low, moderate, or high strain during a short planning period. It then gives an authorized leader evidence-linked options to review.

I built the capstone as a five-agent workflow. A Coordinator manages the case. An Evidence Agent retrieves current and relevant guidance. A Readiness Analyst converts the scenario into a transparent risk estimate. An Operations Planner uses bounded Tree-of-Thought search to compare response plans. A Safety Critic rejects plans that fail coverage, evidence, privacy, or feasibility checks. The final controller returns one of three decisions: ADVISORY, HUMAN_REVIEW_REQUIRED, or ABSTAIN.

The integrated Python prototype runs without an external model or API key. It includes a browser-based GUI, sixteen synthetic showcase presets, a DPR-inspired retriever, a ReAct-style trace, concurrent-safe SQLite memory, beam search, guardrails, six labeled evaluation cases, three deliberately unsafe critic cases, and fifty-five automated tests. In the labeled evaluation, all six forecast cases reached their expected decision, all required escalations were detected, both unavailable-knowledge and stale-alert fallbacks succeeded, all three unsafe plans were rejected, and no hard safety violation occurred. Those results confirm that the current rules behave as designed. They do not establish predictive validity. Real use would require local validation, approved thresholds, live-source testing, privacy review, and human-factors testing.

## 1. Problem and Intended User

Volunteer fire and EMS organizations must maintain readiness while working with limited staffing and unpredictable demand. A demanding period may include several calls in a short window, overnight interruptions, extended shifts, training obligations, severe weather, and reduced availability. Some responders may also have Guard or Reserve commitments. Each factor may be manageable by itself. The risk appears when several factors overlap and leave the team with less coverage or recovery time.

The intended user is an authorized fire, EMS, or public-safety leader who already has responsibility for staffing and readiness decisions. The agent is not designed for individual responders, medical providers, or disciplinary use. It gives the leader an early team-level signal and a small set of options. The user remains responsible for confirming local conditions and making any operational decision.

A prompt-only language model is not reliable enough for this problem. It may answer from general knowledge even when an alert has expired. It may fail to show which source supports an action. It can also commit to the first plausible plan and skip a safer alternative. Most importantly, a fluent response can hide missing data or uncertainty. This capstone addresses those failures with retrieval, visible calculations, bounded search, a separate critic, persistent trace records, and mandatory human approval.

## 2. Local Test Case and Data Boundary

Cranberry Township is a useful test case because it has a clear public-safety setting without requiring private operational access. The township publicly identifies the Cranberry Township Volunteer Fire Company, its Haine and Park stations, its Public Safety Training Facility, and Butler County 911 dispatch. Cranberry Township EMS publicly describes itself as a separate nonprofit service with paid and volunteer personnel. I use those facts only to make the scenario realistic.

Every workload value in the demonstration is invented. The high-strain scenario assumes five incidents during seventy-two hours, three overnight calls, a fourteen-hour maximum shift, seventy-two percent team availability, two fictional Guard or Reserve conflicts, scheduled outdoor training, and a hypothetical heat warning. None of those values describes current conditions in Cranberry Township. The label “synthetic test data” travels with the input and output.

The system accepts team-level counts, ratios, dates, and public alerts. It rejects free-text notes and unexpected person-level fields, including names, responder identifiers, medical notes, diagnoses, disciplinary information, actual military orders, and unit details. Guard or Reserve commitments are represented only as an aggregate availability count. This boundary recognizes that outside service can affect scheduling while avoiding an individual readiness label.

## 3. System Goal and Scope

The goal is to produce a grounded seven-day readiness advisory that helps a leader decide whether normal monitoring is enough or whether operational review is needed. The system should answer five questions:

- Are the required inputs present and within reasonable ranges?
- Which public guidance is relevant and current?
- What is driving the team-level strain estimate?
- Which response options best protect coverage and recovery?
- Is the evidence and confidence strong enough to proceed, or must the system stop?

The prototype can validate inputs, retrieve approved passages, score a synthetic case, explore a limited plan tree, check candidates, preserve an audit trace, and produce a structured recommendation. It cannot confirm live staffing, interpret clinical information, predict an individual’s behavior, or take an operational action. A real deployment would remain decision support, not command automation.

## 4. Final Architecture

The final architecture uses five roles because the task needs distinct kinds of judgment. More agents would add handoffs without solving a new problem. Fewer agents would combine evidence review, scoring, planning, and safety review in the same reasoning path.

### Coordinator Agent

The Coordinator opens the case, creates a run identifier, checks prior aggregate runs, routes work, and applies the final decision contract. It does not invent evidence or override a safety failure. It is also responsible for presenting the plan, alternatives, escalation reasons, and safety boundary to the user.

### Evidence Agent

The Evidence Agent searches an approved public corpus. The current corpus includes CDC/NIOSH fatigue and heat guidance, National Weather Service alert guidance, U.S. Fire Administration wellness material, Defense Health Agency readiness context, and Cranberry Township’s public fire-services page. Each stored passage includes a source, title, URL, project review date, retrieval date, topic labels, and a short paraphrase.

The retriever is DPR-inspired rather than a trained Dense Passage Retrieval model. It builds separate query and passage vectors across transparent concepts such as fatigue, hours, heat, staffing, readiness, and weather. It chunks the scenario into workload, capacity, and environment queries. It then calculates cosine similarity and returns up to four passages. A diversity step preserves evidence for active weather, heat, staffing, and fatigue concerns. Separate weights act like separate encoders because the wording that matters in a scenario is not always the wording that matters in guidance. This improves relevance while keeping the prototype explainable.

Retrieved passages are reused at the sequence level. The planner receives one evidence set for the whole response. I chose this RAG Sequence-style design because the final advisory is short and should remain internally consistent. A RAG Token design could change evidence while generating individual words. That added flexibility would make provenance harder to follow in this safety-sensitive use case. The prototype does not claim true neural marginalization. The evidence scores are ranking signals, not trained probabilities.

### Readiness Analyst

The Readiness Analyst uses fixed and visible rules. It looks at incident load, overnight disruption, extended shift length, available staffing, aggregate Guard or Reserve conflicts, and a current weather alert. The output includes each component, the total score, the strain category, and confidence. These thresholds are synthetic. They exist to demonstrate the workflow and must be replaced with locally approved values before a pilot.

### Operations Planner

The planner uses Tree-of-Thought reasoning where branching adds value: choosing a response plan. A thought is one possible action, such as requesting an authorized mutual-aid review, protecting a recovery window, adjusting outdoor training, applying a heat work-rest cycle, or rotating demanding assignments. A node is a partial plan. A branch adds one action. Depth is the number of actions in the plan.

The search uses beam search with a width of three and a depth of three. It evaluates at most a small, bounded set of nodes. Candidate plans are scored for coverage and safety, recovery benefit, feasibility, evidence, privacy, fairness, and reversibility. Hard failures remove a branch. The search also preserves heat and coverage branches when those constraints are active. This prevents an early high score from eliminating a necessary safety control.

### Safety Critic

The Safety Critic independently checks every finalist. It rejects a plan if projected coverage is below the illustrative minimum, if the plan has no supporting evidence, or if another hard failure is present. The Coordinator then applies the release rules. Operational changes always require human approval. A stale weather alert, unavailable evidence, low confidence, or plans separated by three points or fewer also cause escalation. Missing or prohibited input causes the system to abstain.

## 5. Reasoning, Action, Memory, and Tools

The workflow follows a ReAct-style loop: understand, act, observe, and update. The Coordinator first interprets the task and verifies the data boundary. The Evidence Agent acts by retrieving guidance. The retrieval result becomes an observation. The Analyst updates the case with a strain estimate. The Planner explores response branches. The Critic observes their scores and failures. The Coordinator then decides whether the system can provide a monitoring advisory, must ask for human review, or must abstain.

This structure matters because an observation can change the next action. If the weather alert is expired, the system does not continue as if heat risk were confirmed. If retrieval returns no approved source, the system does not generate an unsupported response. If two plans are close, it shows both rather than treating a small score difference as certainty.

The prototype uses both short-term and long-term memory. Short-term memory is the trace for the current case. It stores observations, evidence identifiers, candidate plans, scores, rejected plans, and escalation reasons. Long-term memory is an SQLite record of prior aggregate runs and decisions. It contains no personal responder history. In future work, anonymized outcome feedback could support calibration and drift monitoring. Retention limits and access controls would be required before storing real operational aggregates.

External tools address limits that a language model cannot solve by memory alone. The most important production tool would be the National Weather Service alert service. A live call would confirm the alert location, effective time, expiration time, and retrieval time. The local prototype uses recorded structured inputs so it remains repeatable and does not need network access. A calculator tool performs transparent risk and plan scoring. A read-only retrieval tool grounds the response in the approved corpus. Every tool result is recorded in the trace.

## 6. Evolution Across the Program

The first version was a broad idea about predicting burnout. I narrowed it because burnout is an occupational phenomenon usually assessed at the individual level, and the available team-level operational data cannot establish it. The project became a team-level readiness and recovery forecaster. That change made the purpose more practical and reduced the chance that the system would stigmatize or discipline a responder.

The next design added the ReAct loop, memory, and tools. This turned a one-time answer into a process that could notice missing information and change course. The course architecture distinguishes parametric model knowledge from nonparametric external memory. The runnable prototype has no language model, so it implements the inspectable public corpus and deterministic rules. A future model-backed version would combine both, with retrieved passages controlling factual grounding.

Tree-of-Thought reasoning was added only to plan selection. Linear reasoning was still appropriate for validation and calculation. Planning had higher branching and more competing constraints, so beam search was a better fit. The project then moved to five agents. Role separation gave evidence, analysis, planning, and criticism clear owners. The last stage added explicit decision states, input guardrails, freshness rules, evaluation metrics, and human intervention criteria.

The design originally mapped CrewAI to role separation, LangChain to control flow and tool integration, and MCP to shared state and context passing. The runnable capstone implements those responsibilities directly in standard Python so the logic is easy to inspect and run without credentials. CrewAI, LangChain, and an MCP server remain possible integration layers. I do not claim they are present in this version.

## 7. Implementation and Demonstration

The code is organized as a small Python package. Separate modules define schemas, retrieval, reasoning, agents, orchestration, memory, evaluation, the command-line interface, and a local browser GUI. Public guidance is stored as structured JSON. Synthetic scenarios are separate from code. The package has no runtime dependencies outside the Python standard library. The GUI offers a single-case workflow and a sixteen-case synthetic showcase, while using the same guarded forecasting function as the command line.

In the main demonstration, the input passes the synthetic-data and range checks. The Evidence Agent retrieves four passages: National Weather Service alert guidance, CDC/NIOSH heat recommendations, Cranberry Township fire-services context, and CDC/NIOSH fatigue guidance. The Analyst produces a high strain score of nine out of a possible nine, with 0.90 rule-based confidence. The scale runs from zero to nine, with four to six treated as moderate strain and seven or above as high strain. The Planner evaluates twenty-six nodes. Two plans survive. The highest plan scores 93. The second scores 90.

The top plan proposes three items for review: consider authorized mutual-aid coverage, protect a recovery window, and apply a heat work-rest cycle with water and cooling. The alternate plan replaces the recovery window with moving or postponing the synthetic outdoor training. The controller returns HUMAN_REVIEW_REQUIRED because every proposed operational change requires authorized approval. The three-point gap falls within the closely-scored threshold of three points or fewer, so it adds a closely-scored-plans escalation and a second sentence to the decision reason. Both options are displayed. The system does not act on either plan.

This example shows why retrieval and structured reasoning both matter. Without heat guidance, a recovery-only plan could look attractive but miss a current environmental control. Without Tree-of-Thought comparison, the system could commit to the first feasible response. Without the human-review gate, a small scoring difference could be mistaken for authority.

## 8. Evaluation and Results

I evaluated observable behavior with six labeled synthetic cases: high strain, low strain, missing required data, prohibited private data, an expired weather alert, and unavailable authoritative knowledge. Three additional red-team candidates test the critic against low coverage, missing evidence, and an explicit hard failure. Sixteen unlabeled showcase cases demonstrate a broader range of GUI behavior without changing the accuracy denominator. Fifty-five automated tests cover strict schema and type validation, all packaged datasets, prohibited free text, unapproved or malformed evidence, future dates, finite and boundary values, escalation, concurrent memory, batch processing, GUI assets and routes, request saturation, path traversal attempts, support tags, and fallback behavior.

| Metric | Observed result | Interpretation |
|---|---:|---|
| Decision agreement | 6 of 6 cases | Every scenario reached its expected decision state. |
| Strain agreement | 4 of 4 labeled cases | The fixed rules matched every scenario with an expected strain label. |
| Mandatory escalation recall | 100% | Every case requiring review or abstention was escalated. |
| Recommendation citation coverage | 100% | Every released recommendation carried a scenario reference and topic-aligned guidance. |
| Topic-aligned guidance coverage | 100% | Each action matched at least one retrieved passage by its declared topic. |
| Unsafe-plan rejection | 3 of 3 | The critic rejected low-coverage, ungrounded, and hard-failure candidates. |
| Fallback success | 100% | Both stale-alert and unavailable-knowledge cases stopped safely. |
| Hard safety violations | 0 | No recommendation was released from an abstained case. |
| Mean local latency | single-digit milliseconds | The deterministic offline workflow is fast on this small corpus. |

The strongest result is not perfect accuracy. It is that the system fails closed in the tested edge cases. Missing staffing data produces ABSTAIN. Prohibited private data produces ABSTAIN. An expired weather alert produces HUMAN_REVIEW_REQUIRED with no plan. Missing authoritative knowledge also produces HUMAN_REVIEW_REQUIRED with no unsupported recommendation.

The limits of these results are substantial. Six deterministic forecast cases and three critic cases cannot measure real forecasting skill. The expected labels were written from the same design assumptions as the rules. The corpus is small. The latency result excludes a live network, a language model, and a human review. Citation coverage and topic matching are structural checks. They do not prove that a subject-matter expert agrees with each recommendation. A field evaluation would need historical replay, blinded expert review, false-negative analysis, calibration measures such as Brier score or expected calibration error, source freshness tests, and usability testing.

## 9. Safety, Reliability, and Human Intervention

Safety begins at input. The schema requires a department label, location, scenario status, forecast window, workload counts, shift length, staffing ratio, and aggregate Guard or Reserve conflicts. It rejects missing fields, negative counts, impossible ratios, excessive time ranges, and overnight calls greater than total calls. It also rejects any input marked as private person data or containing prohibited personal keys.

The Evidence Agent uses an allowlisted corpus and preserves source metadata. A live version would verify retrieval, effective, and expiration times on every alert. Tools remain read-only. The system has no credential for dispatch, scheduling, messaging, or mutual-aid systems. Output actions are framed as options for review, and every operational option carries a human-approval flag.

Human intervention is required when the strain is moderate or high and an operational change is proposed. It is also required when confidence is below 0.75, an alert is stale, evidence is unavailable, or finalist scores differ by three points or fewer. The system abstains when required data is missing, private data is present, or no plan passes the critic. An authorized leader must confirm real staffing, current conditions, policy, resource availability, and mutual-aid procedures before acting.

The main trade-off is autonomy versus reliability. More automatic action could reduce response time, but it would also let an unvalidated score affect coverage and people. I chose a conservative design. Most communication is one-way to limit delay. The planner and critic have one revision opportunity in the conceptual architecture, although the deterministic prototype filters plans in one pass. Beam width and depth are capped to prevent branch explosion. Shared state avoids repeated retrieval. The cost is that the system may escalate often. In this setting, a false sense of certainty is more harmful than an extra review.

## 10. Limitations and Next Steps

The current retriever is transparent but not semantic in the same way as a trained DPR model. The action effects and readiness thresholds are illustrative. The public guidance corpus is hand-curated. The prototype uses recorded alert fields rather than a live National Weather Service call. Long-term memory records only aggregate run summaries and has no production retention policy. The system has not been evaluated by Cranberry Township personnel, and it must not be presented as an operational product for that community.

The next step is a controlled offline pilot. I would work with authorized subject-matter experts to define approved team-level features, remove any variable that could be used as a proxy for individual discipline, and set conservative thresholds. I would add a read-only NWS adapter with recorded fixtures for testing. I would compare the transparent retriever against sparse BM25 and a real embedding model. I would build a larger scenario set with independent labels and measure false negatives, calibration, stale-source detection, unsafe-plan rejection, escalation quality, latency, and cost.

Only after those steps would I consider a limited shadow-mode trial. The system would run beside existing planning practice and would not influence dispatch or staffing. Every output would be reviewed. Users would report whether the evidence was useful, whether options were feasible, and whether escalation reasons were clear. A privacy and security review would set access, retention, audit, and incident-response rules.

## 11. GitHub Repository Plan

The submission includes a GitHub-ready local repository named `responder-readiness-forecaster`. It uses the `main` branch and includes an initial capstone commit. The root contains the README, security and contribution guidance, project configuration, source package, public guidance, synthetic scenarios, tests, example outputs, documentation, and continuous-integration workflow.

The `.gitignore` excludes virtual environments, caches, Office lock files, local databases, temporary output, secrets, and real responder data. Only curated JSON examples should be committed. Large Word, PDF, and PowerPoint deliverables should be attached to a tagged GitHub Release or stored with Git LFS. The README prominently states that the system is advisory, the data is synthetic, and the thresholds are not operational facts.

The repository now includes the MIT License for its software and original project documentation, plus a notice that linked public guidance remains subject to its publishers' terms. Before publication, the owner should confirm the repository settings. A manual review of the local repository found no obvious credentials or real responder records. The remaining publication step is to renew GitHub authentication, create the account-controlled remote, enable secret scanning and dependency alerts, and protect `main` with required checks.

Publication status: the local repository is initialized, tested, and MIT-licensed, but the public URL is pending GitHub reauthentication and creation of the account-controlled remote.

## Conclusion

This capstone does not try to decide whether a person is burned out. It helps an authorized leader see when team-level conditions deserve attention. The design combines current evidence, visible scoring, structured alternatives, independent criticism, memory, and explicit stopping rules. The Cranberry Township demonstration shows how the system can produce a useful planning conversation while keeping the real decision with people.

The prototype is successful as a course capstone because the main agent concepts are observable in one flow. Retrieval changes the plan. ReAct observations change later actions. Tree-of-Thought search exposes alternatives. Multiple agents separate responsibilities. Guardrails cause the system to abstain or escalate. The evaluation shows those controls working in a small synthetic suite. The next challenge is not adding more autonomy. It is earning confidence through independent data, expert review, and careful shadow-mode testing.

## References

1. Cranberry Township. “Fire & Emergency Services.” https://www.cranberrytownship.org/196/Fire-Emergency-Services
2. Cranberry Township EMS. “About Us.” https://cranberrytownshipems.org/about-us/
3. Butler County, Pennsylvania. “911 Emergency Services.” https://www.butlercountypa.gov/232/911-Emergency-Services
4. National Weather Service. “API Web Service” and “Alerts Web Service.” https://www.weather.gov/documentation/services-web-API and https://www.weather.gov/documentation/services-web-alerts
5. CDC/NIOSH. “Firefighter Safety and Health.” https://www.cdc.gov/niosh/firefighters/about/index.html
6. CDC/NIOSH. “Fatigue and Work.” https://www.cdc.gov/niosh/fatigue/about/index.html
7. CDC/NIOSH. “Workplace Recommendations for Heat Stress.” https://www.cdc.gov/niosh/heat-stress/recommendations/index.html
8. U.S. Fire Administration. “Emergency Responder Health, Safety and Wellness.” https://www.usfa.fema.gov/a-z/health-safety-wellness/index.html
9. Patterson, P. D., et al. “Association between Poor Sleep, Fatigue, and Safety Outcomes in Emergency Medical Services Providers.” Prehospital Emergency Care. https://pubmed.ncbi.nlm.nih.gov/22023164/
10. Weaver, M. D., et al. “An Observational Study of Shift Length, Crew Familiarity, and Occupational Injury and Illness in Emergency Medical Services Workers.” Occupational and Environmental Medicine, 72(11), 798–804, 2015. https://pubmed.ncbi.nlm.nih.gov/26371071/
11. Khoshakhlagh, A. H., et al. “Global Prevalence and Associated Factors of Sleep Disorders and Poor Sleep Quality Among Firefighters: A Systematic Review and Meta-analysis.” Heliyon, 9(2), e13250, 2023. https://pubmed.ncbi.nlm.nih.gov/36798763/
12. U.S. Department of Labor. “USERRA Compliance Assistance.” https://www.dol.gov/agencies/vets/programs/userra/compliance
13. World Health Organization. “Burn-out an Occupational Phenomenon.” https://www.who.int/standards/classifications/frequently-asked-questions/burn-out-an-occupational-phenomenon
14. National Institute of Standards and Technology. “AI Risk Management Framework 1.0.” https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10
15. GitHub Docs. “Best Practices for Repositories.” https://docs.github.com/en/repositories/creating-and-managing-repositories/best-practices-for-repositories
