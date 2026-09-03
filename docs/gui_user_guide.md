# GUI user guide

## What this prototype does

The Responder Readiness and Recovery Forecaster is a course demonstration for team-level planning. It estimates operational strain from synthetic activity, recovery, staffing, Guard or Reserve conflict, and weather conditions. It then presents evidence-linked response options for an authorized leader to consider.

The prototype is advisory only. It does not diagnose burnout, determine whether a person is fit for duty, direct an emergency response, or change staffing, schedules, training, mutual aid, or dispatch operations.

## Before you begin

- Use the supplied synthetic showcase scenarios for demonstrations.
- Confirm that the scenario is labeled **Synthetic test data; not a statement of current local conditions**.
- Do not paste or upload real agency records unless a future approved deployment provides a governed team-level data process.
- During an active incident, stop using the prototype and follow incident command and Butler County 911 procedures.

Never enter names, badge or employee numbers, personal schedules, medical or mental-health information, disciplinary or performance records, patient information, incident narratives, credentials, military orders, unit details, or deployment information. A small team can sometimes be re-identified even after names are removed, so synthetic data is the safest demonstration choice.

## Run a showcase scenario

1. Choose a scenario from the synthetic example list. You can also use one of the three quick-start cards.
2. Review the scenario label, location, forecast period, and **as-of** time.
3. Check the team-level factors. These include incidents and overnight calls during the last 72 hours, longest shift, available staffing ratio, count of fictional Guard or Reserve conflicts, and any hypothetical weather alert.
4. Select **Run this example** near the scenario list or **Run readiness forecast** at the bottom of the form.
5. Read the decision before reviewing the suggested plan.
6. Open the evidence details and check the publisher, source link, and project review date.
7. If the output proposes an operational change, send it to an authorized fire or EMS leader. Do not act on it directly.

If you change an input after a forecast runs, the interface marks the existing result as out of date and disables its download button. Run the forecast again before reviewing or saving the result. The two locked guardrail examples intentionally contain missing information or a synthetic privacy flag. Use **Make an editable synthetic copy** if you want to correct one of those examples.

The **Synthetic showcase** view runs all sixteen prepared cases together. Use **Open case** in any row to return that case to the single-forecast form for closer review.

## Understand the result

- **ADVISORY** means the prototype found a low-strain synthetic case. It means monitor the conditions; it does not certify that the team or any person is safe.
- **HUMAN_REVIEW_REQUIRED** means an authorized leader must evaluate the evidence, local policy, live conditions, and coverage before deciding what to do.
- **ABSTAIN** means a guardrail stopped the run because the input was missing, invalid, or privacy-sensitive. This is an intentional safe outcome, not permission to ignore the problem.

The strain score and plan scores are transparent demonstration heuristics, not validated clinical or operational predictions. Confidence reflects the completeness and consistency of the supplied scenario. Evidence relevance scores show how closely a passage matches the search; they do not prove that the passage is correct or that a recommendation is suitable locally.

## Check evidence dates

The **project review date** shows when the project team checked a source for the local evidence corpus. It is not necessarily the source publisher's last update. The **retrieval date** records when the source entered or was checked for the demonstration corpus. Neither field proves that the web page is current today.

Weather alert issue and expiration times are separate from evidence dates. An alert is treated as usable only when its issue and expiration times are present and the scenario's as-of time falls within that window. For any real-world decision, open the linked authoritative source and verify that the guidance or alert is still current.

## Required human review

Human approval is required for any proposed change involving coverage, mutual aid, training, recovery periods, schedules, or staffing. Review is also required when evidence is stale, missing, contradictory, or unavailable; confidence is low; finalists are closely scored; a safety check fails; or the situation involves an active incident or unclear policy. The human reviewer owns the final decision.
