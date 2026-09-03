"use strict";

const state = {
  presets: [],
  currentResult: null,
  selectedPresetScenario: null,
};

const $ = (selector) => document.querySelector(selector);

const elements = {
  forecastTab: $("#forecast-tab"),
  showcaseTab: $("#showcase-tab"),
  forecastView: $("#forecast-view"),
  showcaseView: $("#showcase-view"),
  form: $("#scenario-form"),
  preset: $("#preset-select"),
  presetHelp: $("#preset-help"),
  customizeButton: $("#customize-button"),
  resultStale: $("#result-stale"),
  resultContext: $("#result-context"),
  formError: $("#form-error"),
  runButton: $("#run-button"),
  resetButton: $("#reset-button"),
  weatherToggle: $("#weather-toggle"),
  weatherFields: $("#weather-fields"),
  trainingToggle: $("#training-toggle"),
  emptyState: $("#empty-state"),
  loadingState: $("#loading-state"),
  resultsContent: $("#results-content"),
  liveRegion: $("#result-live-region"),
  downloadButton: $("#download-button"),
  resultsPanel: $("#results-panel"),
  showcaseButton: $("#run-showcase-button"),
  showcaseEmpty: $("#showcase-empty"),
  showcaseLoading: $("#showcase-loading"),
  showcaseResults: $("#showcase-results"),
};

const rangeOutputs = [
  ["#incident-count", "#incident-count-output", (value) => value],
  ["#overnight-calls", "#overnight-calls-output", (value) => value],
  ["#longest-shift", "#longest-shift-output", (value) => `${value} hours`],
  ["#staffing-ratio", "#staffing-ratio-output", (value) => `${value}%`],
  ["#guard-conflicts", "#guard-conflicts-output", (value) => value],
];

const factorLabels = {
  incident_load: "Incident load",
  overnight_disruption: "Overnight disruption",
  extended_shift: "Extended shift",
  reduced_staffing: "Reduced staffing",
  guard_reserve_availability: "Guard or Reserve availability",
  current_weather_alert: "Current weather alert",
};

const decisionLabels = {
  ADVISORY: "Monitoring advisory",
  HUMAN_REVIEW_REQUIRED: "Human review required",
  ABSTAIN: "Forecast stopped safely",
};

const actionLabels = {
  request_mutual_aid: "Review mutual-aid coverage",
  protect_recovery_window: "Protect a recovery window",
  move_outdoor_training: "Consider moving outdoor training",
  heat_work_rest_cycle: "Use heat work-rest controls",
  rotate_assignments: "Consider rotating assignments",
};

function presetGroup(id) {
  const number = Number(String(id).slice(0, 2));
  if (number <= 2) return "Routine monitoring";
  if ([3, 4, 5, 6, 12].includes(number)) return "Moderate conditions";
  if (number >= 7 && number <= 11) return "High-strain conditions";
  return "Safety and fallback checks";
}

function friendlyReason(reason) {
  const value = String(reason || "");
  if (value.startsWith("missing_required_fields:")) {
    const fields = value.split(":", 2)[1].trim().replaceAll("_", " ");
    return `The run stopped because required team-level information is missing: ${fields}. Add it and try again.`;
  }
  if (value.startsWith("private_person_data_not_allowed") || value.startsWith("sensitive_text_not_allowed")) {
    return "The run stopped because the input may contain private person-level information. Use only public, synthetic, or approved anonymized team-level data.";
  }
  if (value.startsWith("unexpected_fields_not_allowed") || value.startsWith("nested_or_collection_value_not_allowed")) {
    return "The run stopped because the scenario contains an unsupported field or nested information. Use the prepared team-level fields only.";
  }
  if (value.startsWith("scenario_status_must_be") || value.startsWith("unapproved_scenario")) {
    return "The run stopped because the information was not clearly labeled public, synthetic, or anonymized.";
  }
  if (value.startsWith("tool_or_evidence_failure") || value.startsWith("audit_memory_unavailable")) {
    return "The run stopped safely because an evidence or audit component was unavailable. No recommendation was released.";
  }
  if (value.includes("out_of_range") || value.includes("must_be_finite") || value.includes("_exceeds_")) {
    return "The run stopped because one or more values are outside the supported demonstration range. Review the highlighted team-level inputs and try again.";
  }
  return value;
}

function humanize(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function setText(selector, value) {
  const element = typeof selector === "string" ? $(selector) : selector;
  if (element) element.textContent = value ?? "—";
}

function clear(element) {
  while (element.firstChild) element.removeChild(element.firstChild);
}

function localInputValue(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value).slice(0, 16);
  const local = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function isoValue(value) {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toISOString();
}

function updateRangeOutputs() {
  rangeOutputs.forEach(([inputSelector, outputSelector, formatter]) => {
    const input = $(inputSelector);
    const value = input.dataset.missing === "true" ? "Missing" : formatter(input.value);
    setText(outputSelector, value);
  });
}

function showView(view) {
  const forecastActive = view === "forecast";
  elements.forecastView.hidden = !forecastActive;
  elements.showcaseView.hidden = forecastActive;
  elements.forecastTab.classList.toggle("is-active", forecastActive);
  elements.showcaseTab.classList.toggle("is-active", !forecastActive);
  elements.forecastTab.setAttribute("aria-pressed", String(forecastActive));
  elements.showcaseTab.setAttribute("aria-pressed", String(!forecastActive));
}

function setWeatherVisibility(enabled) {
  elements.weatherToggle.checked = Boolean(enabled);
  elements.weatherFields.hidden = !enabled;
  [$("#weather-alert"), $("#alert-issued"), $("#alert-expires")].forEach((field) => {
    field.disabled = !enabled;
    field.required = enabled;
  });
}

function clearStaleResult() {
  elements.resultStale.hidden = true;
  elements.resultsPanel.classList.remove("has-stale-result");
  elements.downloadButton.disabled = false;
  elements.downloadButton.textContent = "Download JSON";
}

function markResultStale() {
  if (!state.currentResult || elements.resultsContent.hidden) return;
  elements.resultStale.hidden = false;
  elements.resultsPanel.classList.add("has-stale-result");
  elements.downloadButton.disabled = true;
  elements.downloadButton.textContent = "Run again to download";
  elements.liveRegion.textContent = "Inputs changed. Run the forecast again to refresh the result.";
}

function populateForm(scenario) {
  $("#department").value = scenario.department || "Synthetic volunteer fire and EMS planning team";
  $("#location").value = scenario.location || "Cranberry Township, Butler County, Pennsylvania";
  $("#forecast-days").value = scenario.forecast_days ?? 7;
  $("#as-of").value = localInputValue(scenario.as_of || new Date().toISOString());
  $("#incident-count").value = scenario.incident_count_72h ?? 1;
  $("#overnight-calls").value = scenario.overnight_calls_72h ?? 0;
  $("#longest-shift").value = scenario.longest_shift_hours ?? 6;
  const staffingInput = $("#staffing-ratio");
  const staffingIsMissing = Boolean(state.selectedPresetScenario) && !Object.hasOwn(scenario, "available_staff_ratio");
  staffingInput.disabled = staffingIsMissing;
  staffingInput.dataset.missing = String(staffingIsMissing);
  staffingInput.value = staffingIsMissing ? 0 : Math.round((scenario.available_staff_ratio ?? 0.94) * 100);
  $("#guard-conflicts").value = scenario.guard_reserve_conflicts ?? 0;
  $("#weather-alert").value = scenario.active_weather_alert || "";
  $("#alert-issued").value = localInputValue(scenario.alert_issued_at);
  $("#alert-expires").value = localInputValue(scenario.alert_expires_at);
  elements.trainingToggle.checked = Boolean(scenario.outdoor_training_scheduled);
  setWeatherVisibility(Boolean(scenario.active_weather_alert));
  updateRangeOutputs();
  elements.formError.hidden = true;
}

function activatePreset(preset) {
  state.selectedPresetScenario = preset?.scenario || null;
  populateForm(preset?.scenario || {});
  if (!preset) return;
  const missingStaffing = !Object.hasOwn(preset.scenario, "available_staff_ratio");
  const privacyGuardrail = Boolean(preset.scenario.contains_private_person_data);
  elements.customizeButton.hidden = !(missingStaffing || privacyGuardrail);
  if (missingStaffing) {
    elements.presetHelp.textContent = "Locked guardrail demonstration: available staffing is missing, so the system should stop safely. Make an editable copy to correct it.";
  } else if (privacyGuardrail) {
    elements.presetHelp.textContent = "Locked guardrail demonstration: a synthetic privacy flag is set. No actual private data is included. Make an editable copy to clear it.";
  } else {
    elements.presetHelp.textContent = `${preset.description} All values are synthetic and editable.`;
  }
  markResultStale();
}

function makeEditableCopy() {
  const staffingInput = $("#staffing-ratio");
  state.selectedPresetScenario = null;
  elements.preset.value = "custom";
  elements.customizeButton.hidden = true;
  staffingInput.disabled = false;
  staffingInput.dataset.missing = "false";
  if (Number(staffingInput.value) === 0) staffingInput.value = 80;
  elements.presetHelp.textContent = "Editable synthetic copy. It is no longer tied to a locked guardrail demonstration.";
  updateRangeOutputs();
  markResultStale();
}

function choosePreset(id, { clearResult = false } = {}) {
  const preset = state.presets.find((item) => item.id === id);
  if (!preset) return false;
  elements.preset.value = preset.id;
  activatePreset(preset);
  showView("forecast");
  if (clearResult) {
    state.currentResult = null;
    setResultMode("empty");
    clearStaleResult();
    elements.resultContext.textContent = "No case analyzed yet";
  }
  return true;
}

function collectScenario() {
  const incidents = Number($("#incident-count").value);
  const overnight = Number($("#overnight-calls").value);
  if (overnight > incidents) {
    throw new Error("Overnight calls cannot be greater than the total number of incidents.");
  }
  const weatherEnabled = elements.weatherToggle.checked;
  const alert = weatherEnabled ? $("#weather-alert").value.trim() : "";
  if (weatherEnabled && !alert) {
    throw new Error("Enter a clearly labeled hypothetical weather alert or turn the alert off.");
  }

  const scenario = {
    department: $("#department").value.trim(),
    location: $("#location").value.trim(),
    scenario_status: $("#scenario-status").value,
    forecast_days: Number($("#forecast-days").value),
    incident_count_72h: incidents,
    overnight_calls_72h: overnight,
    longest_shift_hours: Number($("#longest-shift").value),
    available_staff_ratio: Number($("#staffing-ratio").value) / 100,
    guard_reserve_conflicts: Number($("#guard-conflicts").value),
    active_weather_alert: alert,
    alert_issued_at: weatherEnabled ? isoValue($("#alert-issued").value) : null,
    alert_expires_at: weatherEnabled ? isoValue($("#alert-expires").value) : null,
    as_of: isoValue($("#as-of").value),
    outdoor_training_scheduled: elements.trainingToggle.checked,
    contains_private_person_data: false,
  };
  if (state.selectedPresetScenario) {
    if (!Object.hasOwn(state.selectedPresetScenario, "available_staff_ratio")) {
      delete scenario.available_staff_ratio;
    }
    if (state.selectedPresetScenario.contains_private_person_data) {
      scenario.contains_private_person_data = true;
    }
  }
  return scenario;
}

async function loadPresets() {
  try {
    const response = await fetch("/api/presets", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("Could not load the synthetic examples.");
    const payload = await response.json();
    state.presets = payload.presets || [];
    setText("#showcase-ready-count", `${state.presets.length} synthetic cases`);
    clear(elements.preset);
    const groups = new Map();
    state.presets.forEach((preset) => {
      const groupName = presetGroup(preset.id);
      if (!groups.has(groupName)) {
        const group = document.createElement("optgroup");
        group.label = groupName;
        groups.set(groupName, group);
        elements.preset.appendChild(group);
      }
      const option = document.createElement("option");
      option.value = preset.id;
      option.textContent = preset.label;
      groups.get(groupName).appendChild(option);
    });
    const customOption = document.createElement("option");
    customOption.value = "custom";
    customOption.textContent = "Custom synthetic case";
    elements.preset.appendChild(customOption);
    if (state.presets.length) {
      elements.preset.value = state.presets[0].id;
      activatePreset(state.presets[0]);
    } else {
      elements.presetHelp.textContent = "No prepared cases were found. Enter synthetic values manually.";
      populateForm({});
    }
  } catch (error) {
    clear(elements.preset);
    const option = document.createElement("option");
    option.textContent = "Examples unavailable";
    elements.preset.appendChild(option);
    elements.presetHelp.textContent = error.message;
    populateForm({});
  }
}

function setResultMode(mode) {
  elements.emptyState.hidden = mode !== "empty";
  elements.loadingState.hidden = mode !== "loading";
  elements.resultsContent.hidden = mode !== "result";
  elements.downloadButton.hidden = mode !== "result";
  elements.resultsPanel.setAttribute("aria-busy", String(mode === "loading"));
}

function renderDecision(result) {
  const banner = $("#decision-banner");
  banner.classList.remove("advisory", "abstain");
  if (result.decision === "ADVISORY") banner.classList.add("advisory");
  if (result.decision === "ABSTAIN") banner.classList.add("abstain");
  elements.resultsPanel.dataset.decision = result.decision;
  setText("#decision-title", decisionLabels[result.decision] || humanize(result.decision));
  setText("#decision-reason", friendlyReason(result.decision_reason));
  const approvalText = result.human_review_required ? "Human check required" : "Monitoring only";
  setText("#approval-badge", approvalText);
}

function renderSummary(result) {
  const score = Number(result.risk_score || 0);
  const confidence = Math.round(Number(result.confidence || 0) * 100);
  setText("#risk-score", score);
  setText("#confidence-value", `${confidence}%`);
  const ring = $("#risk-ring");
  ring.style.setProperty("--risk-angle", `${Math.max(0, Math.min(360, (score / 9) * 360))}deg`);
  ring.setAttribute("aria-label", `Risk score ${score} out of 9`);

  const strainPill = $("#strain-pill");
  strainPill.className = `strain-pill ${result.strain || "unknown"}`;
  strainPill.textContent = `${humanize(result.strain)} strain`;
  setText("#forecast-period", result.forecast_days ? `${result.forecast_days} days` : "Not available");
  setText("#evidence-count", `${(result.evidence || []).length} sources`);
  setText("#node-count", result.tree_search?.evaluated_nodes ?? 0);
  setText("#latency-value", `${Number(result.latency_ms || 0).toFixed(2)} ms`);
}

function renderFactors(components) {
  const chart = $("#factor-chart");
  clear(chart);
  const entries = Object.entries(components || {});
  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "no-items";
    empty.textContent = "No readiness factors were calculated because a guardrail stopped this run.";
    chart.appendChild(empty);
    return;
  }
  entries.forEach(([name, value]) => {
    const row = document.createElement("div");
    row.className = "factor-row";
    const label = document.createElement("strong");
    label.textContent = factorLabels[name] || humanize(name);
    const track = document.createElement("div");
    track.className = "factor-track";
    const fill = document.createElement("div");
    fill.className = "factor-fill";
    fill.style.width = `${Math.min(100, (Number(value) / 2) * 100)}%`;
    track.appendChild(fill);
    const points = document.createElement("span");
    points.className = "factor-value";
    points.textContent = String(value);
    row.append(label, track, points);
    chart.appendChild(row);
  });
}

function renderRecommendations(items, decision) {
  const list = $("#recommendation-list");
  clear(list);
  if (decision === "ADVISORY") {
    setText("#recommendations-heading", "Monitoring guidance");
    setText("#recommendation-status", "No operational change");
  } else if (decision === "ABSTAIN") {
    setText("#recommendations-heading", "No recommendation released");
    setText("#recommendation-status", "Guardrail stopped run");
  } else {
    setText("#recommendations-heading", "Recommendations for human review");
    setText("#recommendation-status", "Human decision required");
  }
  if (!items?.length) {
    const empty = document.createElement("div");
    empty.className = "no-items";
    empty.textContent = "No operational change was proposed. Review the decision reason above.";
    list.appendChild(empty);
    return;
  }
  items.forEach((item, index) => {
    const article = document.createElement("article");
    article.className = "recommendation-item";
    const number = document.createElement("span");
    number.className = "recommendation-number";
    number.textContent = String(index + 1);
    const body = document.createElement("div");
    const title = document.createElement("h4");
    title.textContent = item.label;
    const support = document.createElement("p");
    const evidenceCount = (item.topic_aligned_guidance || []).length;
    support.textContent = `${evidenceCount} topic-aligned source${evidenceCount === 1 ? "" : "s"} · Authorized approval required`;
    body.append(title, support);
    article.append(number, body);
    list.appendChild(article);
  });
}

function renderPlans(result) {
  const body = $("#plan-table-body");
  clear(body);
  const finalists = result.finalists || [];
  setText("#plan-gap", result.metrics?.finalist_gap == null ? "No finalist gap" : `${result.metrics.finalist_gap}-point finalist gap`);
  if (!finalists.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.className = "no-items";
    cell.textContent = "No plan cleared the conditions required for comparison.";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  finalists.forEach((plan, index) => {
    const row = document.createElement("tr");
    const planCell = document.createElement("td");
    const label = document.createElement("strong");
    label.textContent = index === 0 ? "Leading plan" : `Alternative ${index}`;
    const actions = document.createElement("div");
    actions.className = "plan-actions";
    (plan.actions || []).forEach((action) => {
      const chip = document.createElement("span");
      chip.className = "action-chip";
      chip.textContent = actionLabels[action] || humanize(action);
      actions.appendChild(chip);
    });
    planCell.append(label, actions);
    const score = document.createElement("td");
    score.textContent = String(plan.score ?? "—");
    const coverage = document.createElement("td");
    coverage.textContent = plan.projected_coverage == null ? "—" : `${Math.round(plan.projected_coverage * 100)}%`;
    const safety = document.createElement("td");
    safety.className = plan.hard_failures?.length ? "" : "safe-status";
    safety.textContent = plan.hard_failures?.length ? plan.hard_failures.map(humanize).join(", ") : "Passed prototype checks";
    row.append(planCell, score, coverage, safety);
    body.appendChild(row);
  });
}

function renderEvidence(items) {
  const list = $("#evidence-list");
  clear(list);
  if (!items?.length) {
    const empty = document.createElement("div");
    empty.className = "no-items";
    empty.textContent = "No approved evidence was available for this result.";
    list.appendChild(empty);
    return;
  }
  items.forEach((item) => {
    const article = document.createElement("article");
    article.className = "evidence-item";
    const body = document.createElement("div");
    const title = document.createElement("h4");
    title.textContent = item.title;
    const meta = document.createElement("p");
    meta.className = "evidence-meta";
    meta.textContent = `${item.source} · Relevance ${Number(item.score || 0).toFixed(3)} · Project review ${item.last_reviewed}`;
    body.append(title, meta);
    const link = document.createElement("a");
    link.className = "evidence-link";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Verify source ↗";
    article.append(body, link);
    list.appendChild(article);
  });
}

function summarizeObservation(item) {
  const observation = item.observation;
  if (!observation || typeof observation !== "object") return String(observation || "Step completed.");
  if (item.agent === "Coordinator Agent" && item.action === "understand_case") {
    return `${observation.forecast_days}-day window; ${observation.prior_aggregate_runs} prior aggregate runs in local audit memory.`;
  }
  if (item.agent === "Evidence Agent") {
    return `${observation.results || 0} approved evidence records retrieved.`;
  }
  if (item.agent === "Readiness Analyst") {
    return `${humanize(observation.strain)} strain; score ${observation.score}; ${Math.round(Number(observation.confidence || 0) * 100)}% rule-based confidence.`;
  }
  if (item.agent === "Operations Planner") {
    return `${observation.evaluated_nodes || 0} plan nodes evaluated; ${(observation.finalists || []).length} finalists retained.`;
  }
  if (item.agent === "Safety Critic") {
    const rejected = Array.isArray(observation.rejected) ? observation.rejected.length : 0;
    return `${observation.accepted || 0} finalists passed prototype checks; ${rejected} rejected.`;
  }
  if (item.action === "fail_closed") return "The workflow stopped safely after an unexpected component failure.";
  return "Step completed and recorded in the local audit trace.";
}

function renderTrace(items) {
  const list = $("#trace-list");
  clear(list);
  (items || []).forEach((item) => {
    const row = document.createElement("li");
    const agent = document.createElement("strong");
    agent.textContent = item.agent;
    const action = document.createElement("span");
    action.textContent = `${humanize(item.action)} — ${summarizeObservation(item)}`;
    row.append(agent, action);
    list.appendChild(row);
  });
}

function renderResult(result) {
  state.currentResult = result;
  clearStaleResult();
  renderDecision(result);
  renderSummary(result);
  renderFactors(result.risk_components);
  renderRecommendations(result.recommendations, result.decision);
  renderPlans(result);
  renderEvidence(result.evidence);
  renderTrace(result.trace);
  setText("#safety-boundary", result.safety_boundary);
  const contextParts = [result.department, result.location, result.forecast_days ? `${result.forecast_days}-day outlook` : null].filter(Boolean);
  elements.resultContext.textContent = contextParts.join(" · ") || "Synthetic case result";
  setResultMode("result");
  elements.liveRegion.textContent = `${decisionLabels[result.decision] || result.decision}. ${result.strain} strain, risk score ${result.risk_score}.`;
  $("#decision-title").focus();
}

async function runForecast(event) {
  event.preventDefault();
  elements.formError.hidden = true;
  if (!elements.form.checkValidity()) {
    elements.form.reportValidity();
    return;
  }
  let scenario;
  try {
    scenario = collectScenario();
  } catch (error) {
    elements.formError.textContent = error.message;
    elements.formError.hidden = false;
    elements.formError.focus();
    return;
  }
  elements.runButton.disabled = true;
  setResultMode("loading");
  try {
    const response = await fetch("/api/forecast", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ scenario }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "The forecast request failed.");
    renderResult(payload);
  } catch (error) {
    setResultMode("empty");
    elements.formError.textContent = `The local service could not complete the request: ${error.message}`;
    elements.formError.hidden = false;
    elements.formError.focus();
  } finally {
    elements.runButton.disabled = false;
  }
}

function addDistributionRows(container, distribution, colorClass = "") {
  clear(container);
  const entries = Object.entries(distribution || {});
  const total = entries.reduce((sum, [, count]) => sum + Number(count), 0) || 1;
  entries.forEach(([label, count]) => {
    const row = document.createElement("div");
    row.className = "distribution-row";
    const name = document.createElement("strong");
    name.textContent = humanize(label);
    const track = document.createElement("div");
    track.className = "distribution-track";
    const fill = document.createElement("div");
    fill.className = `distribution-fill ${colorClass}`.trim();
    fill.style.width = `${(Number(count) / total) * 100}%`;
    track.appendChild(fill);
    const value = document.createElement("span");
    value.textContent = String(count);
    row.append(name, track, value);
    container.appendChild(row);
  });
}

function renderShowcase(payload) {
  setText("#showcase-case-count", payload.case_count);
  setText("#showcase-review-count", payload.decision_distribution?.HUMAN_REVIEW_REQUIRED || 0);
  setText("#showcase-abstain-count", payload.decision_distribution?.ABSTAIN || 0);
  setText("#showcase-latency", `${Number(payload.mean_latency_ms || 0).toFixed(2)} ms`);
  setText("#showcase-p95", `Local p95 ${Number(payload.p95_latency_ms || 0).toFixed(2)} ms`);
  addDistributionRows($("#decision-distribution"), payload.decision_distribution, "teal");
  addDistributionRows($("#strain-distribution"), payload.strain_distribution, "amber");

  const body = $("#showcase-table-body");
  clear(body);
  (payload.cases || []).forEach((item) => {
    const row = document.createElement("tr");
    const scenario = document.createElement("td");
    scenario.textContent = item.label;
    const strain = document.createElement("td");
    const pill = document.createElement("span");
    pill.className = `strain-pill ${item.strain || "unknown"}`;
    pill.textContent = humanize(item.strain);
    strain.appendChild(pill);
    const score = document.createElement("td");
    score.textContent = String(item.risk_score);
    const decision = document.createElement("td");
    decision.textContent = decisionLabels[item.decision] || humanize(item.decision);
    const latency = document.createElement("td");
    latency.textContent = `${Number(item.latency_ms || 0).toFixed(2)} ms`;
    const openCell = document.createElement("td");
    const openButton = document.createElement("button");
    openButton.type = "button";
    openButton.className = "table-action";
    openButton.textContent = "Open case";
    openButton.setAttribute("aria-label", `Open ${item.label} in the single forecast view`);
    openButton.addEventListener("click", () => {
      if (choosePreset(item.id, { clearResult: true })) {
        elements.preset.focus();
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    });
    openCell.appendChild(openButton);
    row.append(scenario, strain, score, decision, latency, openCell);
    body.appendChild(row);
  });
  elements.showcaseLoading.hidden = true;
  elements.showcaseEmpty.hidden = true;
  elements.showcaseResults.hidden = false;
  elements.showcaseView.setAttribute("aria-busy", "false");
  elements.showcaseResults.focus();
}

async function runShowcase() {
  elements.showcaseButton.disabled = true;
  elements.showcaseEmpty.hidden = true;
  elements.showcaseResults.hidden = true;
  elements.showcaseLoading.hidden = false;
  elements.showcaseView.setAttribute("aria-busy", "true");
  try {
    const response = await fetch("/api/showcase", { method: "POST", headers: { Accept: "application/json" } });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "The showcase could not run.");
    renderShowcase(payload);
  } catch (error) {
    elements.showcaseLoading.hidden = true;
    elements.showcaseEmpty.hidden = false;
    elements.showcaseView.setAttribute("aria-busy", "false");
    elements.showcaseEmpty.querySelector("h3").textContent = "The showcase could not run";
    elements.showcaseEmpty.querySelector("p").textContent = error.message;
  } finally {
    elements.showcaseButton.disabled = false;
  }
}

function downloadResult() {
  if (!state.currentResult || elements.downloadButton.disabled) return;
  const blob = new Blob([`${JSON.stringify(state.currentResult, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `readiness-forecast-${state.currentResult.run_id}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

elements.forecastTab.addEventListener("click", () => showView("forecast"));
elements.showcaseTab.addEventListener("click", () => showView("showcase"));
elements.form.addEventListener("submit", runForecast);
elements.form.addEventListener("input", markResultStale);
elements.form.addEventListener("change", markResultStale);
elements.weatherToggle.addEventListener("change", () => setWeatherVisibility(elements.weatherToggle.checked));
elements.preset.addEventListener("change", () => {
  const preset = state.presets.find((item) => item.id === elements.preset.value);
  if (preset) activatePreset(preset);
  else if (elements.preset.value === "custom") makeEditableCopy();
});
elements.customizeButton.addEventListener("click", makeEditableCopy);
elements.resetButton.addEventListener("click", () => {
  const preset = state.presets.find((item) => item.id === elements.preset.value) || state.presets[0];
  if (preset) elements.preset.value = preset.id;
  activatePreset(preset);
  state.currentResult = null;
  setResultMode("empty");
  clearStaleResult();
  elements.resultContext.textContent = "No case analyzed yet";
});
elements.downloadButton.addEventListener("click", downloadResult);
elements.showcaseButton.addEventListener("click", runShowcase);
rangeOutputs.forEach(([inputSelector]) => $(inputSelector).addEventListener("input", updateRangeOutputs));
document.querySelectorAll("[data-quick-preset]").forEach((button) => {
  button.addEventListener("click", () => {
    if (choosePreset(button.dataset.quickPreset)) elements.form.requestSubmit();
  });
});

loadPresets();
