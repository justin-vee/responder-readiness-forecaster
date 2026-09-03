# Architecture

The runnable prototype uses five explicit roles coordinated through a hybrid graph:

1. The **Coordinator Agent** validates the case, routes tasks, enforces stop conditions, and returns the final decision state.
2. The **Evidence Agent** calls the transparent retriever and checks evidence availability and alert freshness.
3. The **Readiness Analyst** calls deterministic scoring logic and records the observable drivers.
4. The **Operations Planner** runs bounded Tree-of-Thought beam search when the case is moderate or high strain.
5. The **Safety Critic** rejects plans that fail coverage or grounding rules.

The workflow is mostly sequential. The planner and critic form a bounded review boundary: the critic filters unsafe finalists in the current deterministic implementation. A future model-backed version may allow one revision, but the prototype does not implement an open-ended dialogue.

Cases that pass input validation write a structured trace to SQLite. Early input rejections return `ABSTAIN` without persisting the submitted payload. For accepted cases, the active trace is short-term memory. The aggregate run table is a limited form of long-term memory that demonstrates persistence without storing private person-level information.

## Planned framework mapping

- **CrewAI:** optional role definitions and task routing
- **LangChain:** optional graph orchestration and tool adapters
- **MCP:** optional shared resource and tool interface over an external state store

The current code does not claim those packages are installed. It implements the design contract directly so the demonstration remains reproducible and auditable.

## Local visual interface

The optional browser interface is served by a standard-library HTTP server bound to the loopback interface only. It provides two views: a single-scenario workflow and a sixteen-case synthetic showcase. The browser sends structured JSON to the same `run_forecast` function used by the command line, so the GUI and CLI share validation, retrieval, reasoning, safety, and audit behavior.

The GUI never performs an operational action. It presents the decision state, contributing factors, recommendations, plan comparison, evidence links, and five-agent trace. The showcase runs a separate unlabeled scenario library and reports behavior distributions and local processing time. Those cases are excluded from labeled accuracy calculations.

The server applies a request-size limit, same-origin checks for writes, loopback-only host validation, restrictive browser security headers, and a stable fail-closed JSON response contract. SQLite uses WAL mode, a busy timeout, and explicit transactions so concurrent local requests remain auditable.

## Tool allowlist

The prototype calls only local, read-only functions for evidence retrieval, readiness calculation, bounded plan search, and safety checking. A future NWS adapter should preserve retrieval, issue, effective, and expiration timestamps. Dispatch, scheduling, messaging, and mutual-aid actions are outside the allowlist.
