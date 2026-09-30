"use strict";

// Fictional examples for evaluator testing, not real patient testimonials.
const DEMO_REVIEWS = [
  "2025년 3월 12일 아이디병원에서 코수술을 받았어요. 비용은 450만원이었고 의사 선생님 이름은 기억이 안 나요. 첫 2주 동안 붓기와 멍이 있었지만 한 달 뒤에는 많이 가라앉았어요. 코 모양이 자연스러워서 만족해요. 수술 전후 사진을 비교하니 콧대가 더 또렷해졌어요.",
  "I had rhinoplasty at ID Plastic Surgery on April 8, 2025. I paid KRW 4,800,000. I don't remember my surgeon's name. My nose looks more balanced now, and the staff explained the aftercare clearly. I had swelling for about three weeks and some tenderness at the tip. At my six-week checkup, the tenderness was still there, though improving.",
  "바노바기성형외과에서 쌍꺼풀 수술을 받았어요. 처음 일주일은 눈이 많이 붓고 당기는 느낌이 있었어요. 3주 후에는 붓기가 줄었고 라인이 자연스러워 보여요. 상담 때 회복 과정을 자세히 설명해 줘서 좋았어요. 가격이나 수술 날짜는 이 후기에 적지 않을게요."
];

const TRUST_LABELS = {
  clinic_named: "Clinic named", surgeon_named: "Surgeon named", procedure_named: "Procedure named",
  procedure_date_present: "Procedure date", price_present: "Price included",
  recovery_details_present: "Recovery details", complications_described: "Complication described",
  before_after_mentioned: "Before / after mentioned", firsthand_experience: "Firsthand experience"
};

const $ = (id) => document.getElementById(id);
const review = $("review");
const outputPanel = document.querySelector(".output-panel");
const demoButtons = [...document.querySelectorAll(".demo-button")];
let busy = false;
let jsonText = "";

function updateInput() {
  $("character-count").textContent = `${review.value.length.toLocaleString("en-US")} / 10,000`;
  $("clear-button").disabled = busy || review.value.length === 0;
  demoButtons.forEach((button) => {
    const selected = review.value === DEMO_REVIEWS[Number(button.dataset.example)];
    button.classList.toggle("active", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
}

function resetOutput() {
  $("results").hidden = true;
  $("error-message").hidden = true;
  $("loading-state").hidden = true;
  $("empty-state").hidden = false;
  $("result-badge").textContent = "Awaiting review";
  $("live-status").textContent = "Review changed. Normalize it to see an updated record.";
  jsonText = "";
}

review.addEventListener("input", () => { updateInput(); resetOutput(); });
demoButtons.forEach((button) => button.addEventListener("click", () => {
  review.value = DEMO_REVIEWS[Number(button.dataset.example)];
  resetOutput(); updateInput(); review.focus();
}));
$("clear-button").addEventListener("click", () => { review.value = ""; resetOutput(); updateInput(); review.focus(); });

function setBusy(value) {
  busy = value;
  outputPanel.setAttribute("aria-busy", String(value));
  review.disabled = value;
  demoButtons.forEach((button) => { button.disabled = value; });
  $("normalize-button").disabled = value;
  document.querySelector(".button-label").textContent = value ? "Normalizing review…" : "Normalize Review";
  document.querySelector(".button-arrow").hidden = value;
  document.querySelector(".spinner").hidden = !value;
  $("loading-state").hidden = !value;
  updateInput();
}

function setFact(id, value) {
  $(id).textContent = value || "Not mentioned";
  $(id).classList.toggle("not-mentioned-value", !value);
}

function renderList(id, values, emptyText) {
  const list = $(id);
  list.replaceChildren();
  (values.length ? values : [emptyText]).forEach((value) => {
    const item = document.createElement("li");
    item.textContent = value;
    if (!values.length) item.className = "empty-value";
    list.append(item);
  });
}

function renderResult(data) {
  const extraction = data.extraction;
  const match = data.normalization;
  $("clinic-panel").classList.toggle("unresolved", match.status === "unresolved");
  $("clinic-panel").classList.toggle("not-mentioned", match.status === "not_mentioned");
  setFact("clinic-raw", match.clinic_raw);
  setFact("clinic-canonical", match.clinic_canonical);
  const similarity = `${Math.round(match.confidence * 100)}%`;
  if (match.status === "matched") {
    $("match-badge").textContent = match.match_method === "exact" ? "Exact alias match" : "Fuzzy alias match";
    $("match-explanation").textContent = `Matched alias: ${match.matched_alias}`;
    $("confidence").textContent = `${similarity} matching confidence`;
  } else if (match.status === "unresolved") {
    $("match-badge").textContent = "Unresolved";
    $("match-explanation").textContent = "No reliable alias match. Original name retained.";
    $("confidence").textContent = `Best similarity: ${similarity}`;
  } else {
    $("match-badge").textContent = "Not mentioned";
    $("match-explanation").textContent = "No clinic was named in this review.";
    $("confidence").textContent = "";
  }
  $("translation").textContent = extraction.translated_review;
  $("language-label").textContent = `${extraction.original_language} → English`;
  setFact("procedure", extraction.procedure_normalized);
  $("procedure-raw").textContent = extraction.procedure_raw && extraction.procedure_raw !== extraction.procedure_normalized ? `Mentioned: ${extraction.procedure_raw}` : "";
  setFact("surgeon", extraction.surgeon);
  setFact("price", extraction.price);
  setFact("procedure-date", extraction.procedure_date);
  $("trust-signals").replaceChildren();
  extraction.trust_signals.forEach((signal) => {
    const chip = document.createElement("span");
    chip.className = "trust-chip";
    chip.textContent = TRUST_LABELS[signal] || signal.replaceAll("_", " ");
    $("trust-signals").append(chip);
  });
  if (!extraction.trust_signals.length) {
    const empty = document.createElement("span");
    empty.className = "empty-value"; empty.textContent = "No detail signals identified.";
    $("trust-signals").append(empty);
  }
  renderList("positive-outcomes", extraction.positive_outcomes, "No positive outcomes mentioned.");
  renderList("negative-outcomes", extraction.negative_outcomes, "No negative outcomes mentioned.");
  jsonText = JSON.stringify(data, null, 2);
  $("json-output").textContent = jsonText;
  document.querySelector(".json-details").open = false;
  $("copy-json").textContent = "Copy JSON";
  $("results").hidden = false;
  $("empty-state").hidden = true;
  $("result-badge").textContent = "Review normalized";
  $("live-status").textContent = "Review normalized. Translation, clinic match, and treatment details are available.";
  if (window.matchMedia("(max-width: 900px)").matches) outputPanel.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" });
}

$("review-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  if (!review.value.trim()) {
    review.setCustomValidity("Paste a review before normalizing.");
    review.reportValidity(); review.setCustomValidity(""); return;
  }
  $("error-message").hidden = true; $("results").hidden = true; $("empty-state").hidden = true;
  $("result-badge").textContent = "Processing";
  $("live-status").textContent = "Normalizing review. Please wait.";
  setBusy(true);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);
  try {
    const response = await fetch("/api/normalize", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ review: review.value }), signal: controller.signal });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "This review could not be processed. Please try again.");
    renderResult(data);
  } catch (error) {
    $("error-message").textContent = error.name === "AbortError" ? "Extraction took too long. Please try again with a shorter review." : error instanceof TypeError || error instanceof SyntaxError ? "Could not reach the extraction service. Check your connection and try again." : error.message;
    $("error-message").hidden = false;
    $("empty-state").hidden = false;
    $("result-badge").textContent = "Try again";
    $("live-status").textContent = "Extraction failed. Your review is still available to retry.";
  } finally {
    clearTimeout(timeout);
    setBusy(false);
  }
});

$("copy-json").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(jsonText);
    $("copy-json").textContent = "Copied";
    $("live-status").textContent = "Structured JSON copied to clipboard.";
  } catch {
    $("copy-json").textContent = "Select JSON to copy";
    $("json-output").focus();
    const selection = window.getSelection();
    const range = document.createRange(); range.selectNodeContents($("json-output"));
    selection.removeAllRanges(); selection.addRange(range);
    $("live-status").textContent = "JSON selected. Use your keyboard copy command.";
  }
});
updateInput();
