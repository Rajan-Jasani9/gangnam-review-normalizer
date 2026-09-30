/* Optional browser QA: NODE_PATH must point to a node_modules containing playwright. */
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const base = process.env.APP_URL || "http://127.0.0.1:8000";
const artifacts = path.resolve(__dirname, "../artifacts");
const record = {
  extraction: {
    original_language: "Korean",
    translated_review: "I had rhinoplasty at ID Hospital on March 12, 2025. I paid KRW 4,500,000 and do not remember the surgeon's name. There was swelling and bruising for the first two weeks, but they had mostly subsided after a month. I am happy with the natural shape. Comparing my before and after photos, the bridge looks more defined.",
    clinic_raw: "아이디병원", procedure_raw: "코수술", procedure_normalized: "Rhinoplasty",
    surgeon: null, price: "KRW 4,500,000", procedure_date: "March 12, 2025",
    positive_outcomes: ["Natural-looking nose shape", "More defined nasal bridge"],
    negative_outcomes: ["Swelling and bruising for the first two weeks"],
    trust_signals: ["clinic_named", "procedure_named", "price_present", "procedure_date_present", "recovery_details_present", "before_after_mentioned", "firsthand_experience"]
  },
  normalization: { clinic_raw: "아이디병원", clinic_canonical: "ID Hospital", matched_alias: "아이디병원", confidence: 1, status: "matched", match_method: "exact" }
};

(async () => {
  await fs.mkdir(artifacts, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1060 }, reducedMotion: "reduce" });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await page.goto(base);
    await page.locator("#review").waitFor();
    await page.screenshot({ path: path.join(artifacts, "desktop-empty.png"), fullPage: true });
    assert.equal(await page.title(), "Review Normalizer · Gangnam Beauty Guide");
    assert.equal(await page.locator(".demo-button").count(), 3);
    await page.locator('[data-example="0"]').click();
    assert.match(await page.locator("#review").inputValue(), /아이디병원/);
    await page.locator("#normalize-button").click();
    await page.locator("#error-message").waitFor({ state: "visible" });
    assert.match(await page.locator("#error-message").textContent(), /GEMINI_API_KEY/);
    assert.equal(await page.locator("#normalize-button").isEnabled(), true);
    assert.match(await page.locator("#review").inputValue(), /아이디병원/);
    await page.screenshot({ path: path.join(artifacts, "desktop-configuration-error.png"), fullPage: true });

    // Mock provider output only in this browser test. Production always calls Gemini.
    let responseRecord = structuredClone(record);
    let releaseResponse;
    await page.route("**/api/normalize", async (route) => {
      if (releaseResponse) await new Promise((resolve) => { releaseResponse(resolve); });
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(responseRecord) });
    });
    let release;
    releaseResponse = (resolve) => { release = resolve; };
    await page.locator("#normalize-button").click();
    await page.locator("#loading-state").waitFor({ state: "visible" });
    assert.equal(await page.locator("#review").isDisabled(), true);
    assert.equal(await page.locator("#normalize-button").isDisabled(), true);
    await page.waitForFunction(() => document.querySelector(".output-panel").getAttribute("aria-busy") === "true");
    while (!release) await new Promise((resolve) => setTimeout(resolve, 20));
    release(); releaseResponse = null;
    await page.locator("#results").waitFor({ state: "visible" });
    assert.equal(await page.locator("#clinic-canonical").textContent(), "ID Hospital");
    assert.equal(await page.locator("#surgeon").textContent(), "Not mentioned");
    assert.match(await page.locator("#confidence").textContent(), /100%/);
    assert.equal(await page.locator(".trust-chip").count(), 7);
    assert.equal(await page.locator(".json-details").getAttribute("open"), null);
    await page.screenshot({ path: path.join(artifacts, "desktop-result.png"), fullPage: true });
    await page.locator(".json-details summary").click();
    assert.deepEqual(JSON.parse(await page.locator("#json-output").textContent()), record);

    await page.locator('[data-example="1"]').click();
    assert.match(await page.locator("#review").inputValue(), /ID Plastic Surgery/);
    assert.equal(await page.locator("#results").isHidden(), true);
    responseRecord.normalization.clinic_raw = "ID Plastic Surgery";
    responseRecord.normalization.matched_alias = "ID Plastic Surgery";
    responseRecord.extraction.clinic_raw = "ID Plastic Surgery";
    responseRecord.extraction.original_language = "English";
    await page.locator("#normalize-button").click();
    await page.locator("#results").waitFor({ state: "visible" });
    assert.equal(await page.locator("#clinic-canonical").textContent(), "ID Hospital");

    responseRecord.normalization = { clinic_raw: "Sunshine Aesthetic Center", clinic_canonical: "Sunshine Aesthetic Center", matched_alias: null, confidence: .42, status: "unresolved", match_method: null };
    responseRecord.extraction.translated_review = '<img src=x onerror="window.unwantedExecution=true">';
    responseRecord.extraction.positive_outcomes = [];
    responseRecord.extraction.negative_outcomes = [];
    responseRecord.extraction.trust_signals = [];
    await page.locator("#review").fill("I went to Sunshine Aesthetic Center.");
    await page.locator("#normalize-button").click();
    await page.locator("#results").waitFor({ state: "visible" });
    assert.equal(await page.locator("#match-badge").textContent(), "Unresolved");
    assert.equal(await page.locator("#translation img").count(), 0);
    assert.equal(await page.evaluate(() => window.unwantedExecution), undefined);
    assert.match(await page.locator("#positive-outcomes").textContent(), /No positive/);
    assert.match(await page.locator("#negative-outcomes").textContent(), /No negative/);

    responseRecord = structuredClone(record);
    for (const width of [375, 768]) {
      await page.setViewportSize({ width, height: 900 });
      await page.locator("#clear-button").click();
      assert.equal(await page.locator("#review").inputValue(), "");
      await page.screenshot({ path: path.join(artifacts, `mobile-${width}-empty.png`), fullPage: true });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
      await page.locator('[data-example="0"]').click();
      await page.locator("#normalize-button").click();
      await page.locator("#results").waitFor({ state: "visible" });
      await page.screenshot({ path: path.join(artifacts, `mobile-${width}-result.png`), fullPage: true });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    }
    assert.deepEqual(errors, []);
    console.log("Browser checks passed: initial state, three demos, actual missing-key error, loading controls, both ID aliases, unknown clinic, missing outcomes, JSON, XSS escaping, and responsive layouts at 375/768/1440px. Successful extraction responses were mocked.");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
