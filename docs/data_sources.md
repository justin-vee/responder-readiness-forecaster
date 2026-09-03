# Public evidence sources

The prototype uses short paraphrased passages from an approved source list. Each record in `data/public/authoritative_guidance.json` includes a stable identifier, publisher, title, HTTPS URL, topic labels, a project review date, a retrieval date, and text. The project review date records when the source was checked for this corpus. It is not presented as a publisher update date. The retriever rejects malformed records, future dates, duplicate identifiers, unapproved publishers, and URLs outside the domain allowlist.

Approved publishers in the current demonstration are:

- CDC/NIOSH
- National Weather Service
- U.S. Fire Administration
- Defense Health Agency
- Cranberry Township
- Cranberry Township EMS
- Butler County, Pennsylvania

The local corpus supports an offline and repeatable demonstration. It is not a substitute for live-source verification. A production weather adapter should preserve retrieval, issue, effective, and expiration timestamps and should use recorded fixtures in tests.

## How dates appear in the GUI

- **Project review date** records when a source was checked for this project corpus. It is not a claim about when the publisher last updated the page.
- **Retrieval date** records when the source was collected or checked for the offline demonstration.
- **Alert issued at**, **alert expires at**, and the scenario **as-of** time determine whether a hypothetical alert is treated as current.

These fields make age and provenance visible, but they do not provide live verification. Before a real-world decision, the reviewer must open the cited authoritative page, confirm the current publication or alert status, and apply local policy. A high semantic retrieval score indicates query similarity, not truth, currentness, or local suitability.

## Showcase data

The presets in `data/synthetic/showcase/` are deliberately varied, fictional scenarios for GUI demonstrations. They are separate from the six fixed evaluation fixtures in `data/synthetic/scenarios/`. Showcase values must never be described as present conditions at Cranberry Township Volunteer Fire Company, Cranberry Township EMS, Butler County 911, or any other real organization.

No private agency records, responder schedules, patient information, medical information, military orders, disciplinary records, names, or responder identifiers belong in the corpus.
