/**
 * backend/test_authenticity_engine.js - Comprehensive Authenticity Decision Engine Tests
 * --------------------------------------------------------------------------------------
 * Tests all 10 Priority 3 scenarios:
 * 1. Valid trusted issuer evidence with matching data -> AUTHENTICITY VERIFIED
 * 2. Invalid or tampered signature -> VERIFIED MISMATCH
 * 3. Official-looking but untrusted QR URL -> UNVERIFIED (Never verified solely on URL)
 * 4. Trusted QR data contradicting visible certificate text -> VERIFIED MISMATCH
 * 5. Suspicious image anomalies without trusted issuer evidence -> SUSPECTED TAMPERING
 * 6. Low OCR confidence (< 0.45) -> REVIEW REQUIRED
 * 7. Missing QR code on clean scan -> UNVERIFIED
 * 8. Marks arithmetic mismatch -> SUSPECTED TAMPERING
 * 9. Exact demo registry match -> UNVERIFIED (Never produces AUTHENTICITY VERIFIED)
 * 10. Missing core certificate identifiers -> REVIEW REQUIRED
 */

const assert = require("assert");
const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");
const {
  evaluateCertificateAuthenticity,
  verifyCryptographicSignature,
  createSyntheticSignedToken,
  loadTrustedIssuerKeystore,
  mapPythonOcrMetrics,
  TRUSTED_ISSUER_KEYSTORE,
  TEST_ISSUER_KEYSTORE,
  DEMO_REFERENCE_REGISTRY,
} = require("./server");

// A harness-only issuer keypair, injected as a *production-style* keystore so the approval path
// can be tested. It is not an official issuer key and exists only inside this test process.
const { privateKey: HARNESS_PRIV, publicKey: HARNESS_PUB } = crypto.generateKeyPairSync("rsa", {
  modulusLength: 2048,
  publicKeyEncoding: { type: "spki", format: "pem" },
  privateKeyEncoding: { type: "pkcs8", format: "pem" },
});
const HARNESS_KEYSTORE = {
  "HARNESS-ISSUER-KEY-1": { issuer: "Test-Harness Issuer (injected, not official)", publicKeyPem: HARNESS_PUB, algorithm: "RSA-SHA256", isTestKey: false },
};
const signHarness = (payload) => createSyntheticSignedToken(payload, HARNESS_PRIV, "HARNESS-ISSUER-KEY-1");
const CONFIDENT_FS = { candidate_name: "CONFIDENT", certificate_number: "CONFIDENT", registration_number: "CONFIDENT", total_marks: "CONFIDENT" };

function runAuthenticityEngineTests() {
  console.log("=== DeepTrust Nexus Priority 3 Authenticity Engine Test Suite ===\n");

  // -------------------------------------------------------------------------
  // Scenario 1: Valid Trusted Issuer Cryptographic Evidence with Matching Data
  // -------------------------------------------------------------------------
  console.log("--- Scenario 1: Valid Trusted Issuer Cryptographic Evidence ---");
  const testPayload1 = {
    name: "PRIYA SHARMA",
    registration_number: "9876543210",
    certificate_number: "CBSE9876543",
    total_marks: "485",
    board: "CBSE",
    course: "10th",
  };
  const validToken = signHarness(testPayload1);

  const res1 = evaluateCertificateAuthenticity({
    extractedFields: {
      certificate_number: "CBSE9876543",
      candidate_name: "PRIYA SHARMA",
      registration_number: "9876543210",
      total_marks: "485",
      board: "Central Board of Secondary Education (CBSE)",
      course: "Secondary School Leaving Certificate (10th)",
      candidate_name_confidence: 0.95,
      field_status: CONFIDENT_FS,
    },
    qrAnalysis: {
      detected: true,
      // Realistic extract_cli output: full payload plus a TRUNCATED preview.
      raw_payload: validToken,
      raw_payload_preview: validToken.slice(0, 120) + "...",
      payload_classification: { payload_type: "SIGNED_TOKEN", is_official_domain: false },
    },
    tamperAnalysis: { indicators_detected: [] },
    ocrMetrics: { averageConfidence: 0.92, averageConfidencePercentage: "92.0%" },
    keystore: HARNESS_KEYSTORE,
  });

  assert.strictEqual(res1.status, "AUTHENTICITY VERIFIED", "Valid signature with matching data must be AUTHENTICITY VERIFIED");
  assert.strictEqual(res1.matches, true, "Matches must be true");
  assert.strictEqual(res1.issuerTrust.verified, true, "Issuer trust must be verified");
  assert.ok(res1.summary.includes("validated successfully"), "Summary must mention successful validation");
  console.log("  [PASS] Scenario 1: Cryptographically signed token correctly produces AUTHENTICITY VERIFIED.");

  // -------------------------------------------------------------------------
  // Scenario 2: Tampered / Invalid Cryptographic Signature
  // -------------------------------------------------------------------------
  console.log("\n--- Scenario 2: Tampered / Invalid Cryptographic Signature ---");
  const tamperedToken = validToken.substring(0, validToken.length - 8) + "invalid9";
  const res2 = evaluateCertificateAuthenticity({
    extractedFields: {
      certificate_number: "CBSE9876543",
      candidate_name: "PRIYA SHARMA",
    },
    qrAnalysis: {
      detected: true,
      raw_payload_preview: tamperedToken,
      payload_classification: { payload_type: "SIGNED_TOKEN" },
    },
    tamperAnalysis: { indicators_detected: [] },
    ocrMetrics: { averageConfidence: 0.88 },
    keystore: HARNESS_KEYSTORE,
  });

  assert.strictEqual(res2.status, "VERIFIED MISMATCH", "Corrupted signature must trigger VERIFIED MISMATCH");
  assert.strictEqual(res2.matches, false);
  assert.strictEqual(res2.issuerTrust.verified, false);
  assert.ok(res2.summary.includes("failed mathematical verification"), "Must explain signature verification failure");
  console.log("  [PASS] Scenario 2: Modified signature digest correctly triggers VERIFIED MISMATCH.");

  // -------------------------------------------------------------------------
  // Scenario 3: Official-Looking QR URL without Cryptographic Evidence
  // -------------------------------------------------------------------------
  console.log("\n--- Scenario 3: Official-Looking QR URL (Never Standalone Authentic) ---");
  const res3 = evaluateCertificateAuthenticity({
    extractedFields: {
      certificate_number: "CBSE9876543",
      candidate_name: "PRIYA SHARMA",
      total_marks: "485",
    },
    qrAnalysis: {
      detected: true,
      raw_payload_preview: "https://cbse.gov.in/verify?cert=CBSE9876543",
      payload_classification: {
        payload_type: "OFFICIAL_GOV_URL",
        domain: "cbse.gov.in",
        is_official_domain: true,
      },
      consistency_check: { status: "CONSISTENT", discrepancies: [] },
    },
    tamperAnalysis: { indicators_detected: [] },
    ocrMetrics: { averageConfidence: 0.90 },
  });

  // CRITICAL RULE: Must NOT return AUTHENTICITY VERIFIED merely because URL contains cbse.gov.in
  assert.strictEqual(res3.status, "UNVERIFIED", "Official-looking URL without crypto signature must remain UNVERIFIED");
  assert.strictEqual(res3.matches, false);
  assert.notStrictEqual(res3.status, "AUTHENTICITY VERIFIED", "URL alone MUST NEVER yield AUTHENTICITY VERIFIED");
  console.log("  [PASS] Scenario 3: Official-looking URL correctly kept as UNVERIFIED (never trusted without signature).");

  // -------------------------------------------------------------------------
  // Scenario 4: Trusted QR Data Contradicting Visible Certificate Text (Copied QR)
  // -------------------------------------------------------------------------
  console.log("\n--- Scenario 4: QR Data Contradicting Visible Text (Copied QR) ---");
  const res4 = evaluateCertificateAuthenticity({
    extractedFields: {
      certificate_number: "36260174",
      candidate_name: "VIKRAM ADITYA", // Visibly printed on paper
      total_marks: "350",
    },
    qrAnalysis: {
      detected: true,
      consistency_check: {
        status: "DISCREPANCY_DETECTED",
        discrepancies: [
          "Candidate name discrepancy: QR payload has 'SANTHIYA SREE S', but visible certificate OCR extracted 'VIKRAM ADITYA'",
          "Marks discrepancy: QR records total of 527, while visible text records 350",
        ],
      },
    },
    tamperAnalysis: { indicators_detected: [] },
    ocrMetrics: { averageConfidence: 0.89 },
  });

  assert.strictEqual(res4.status, "VERIFIED MISMATCH", "Contradictory QR data must trigger VERIFIED MISMATCH");
  assert.strictEqual(res4.matches, false);
  assert.ok(res4.discrepancies.length >= 2, "Discrepancies list must be included");
  console.log("  [PASS] Scenario 4: Copied QR contradiction correctly produces VERIFIED MISMATCH.");

  // -------------------------------------------------------------------------
  // Scenario 5: Suspicious Image Forensics Anomalies without Trusted Evidence
  // -------------------------------------------------------------------------
  console.log("\n--- Scenario 5: Visual Forensics Anomalies Detected ---");
  const res5 = evaluateCertificateAuthenticity({
    extractedFields: {
      certificate_number: "12345678",
      candidate_name: "ANANYA VERMA",
      total_marks: "450",
    },
    qrAnalysis: { detected: false },
    tamperAnalysis: {
      indicators_detected: ["FONT_SIZE_ALIGNMENT_ANOMALY", "LOCAL_COMPRESSION_VARIATION"],
      forensic_summary: "Identified 2 potential anomaly indicators (FONT_SIZE_ALIGNMENT_ANOMALY, LOCAL_COMPRESSION_VARIATION).",
      limitations: ["Image forensics heuristics detect statistical and visual anomalies."],
    },
    ocrMetrics: { averageConfidence: 0.85 },
  });

  assert.strictEqual(res5.status, "SUSPECTED TAMPERING", "Visual anomalies must produce SUSPECTED TAMPERING");
  assert.strictEqual(res5.matches, false);
  assert.ok(res5.tamperingIndicators.includes("FONT_SIZE_ALIGNMENT_ANOMALY"));
  assert.ok(res5.explanation.includes("false positives"), "Must explain possibility of false positives");
  console.log("  [PASS] Scenario 5: Visual anomalies correctly produce SUSPECTED TAMPERING with honest limitations.");

  // -------------------------------------------------------------------------
  // Scenario 6: Low OCR Confidence (< 0.45)
  // -------------------------------------------------------------------------
  console.log("\n--- Scenario 6: Low OCR Confidence (< 0.45) ---");
  const res6 = evaluateCertificateAuthenticity({
    extractedFields: {
      certificate_number: "11180882",
      candidate_name: "SARAVANAVEL C",
    },
    tamperAnalysis: { indicators_detected: [] },
    ocrMetrics: { averageConfidence: 0.38, averageConfidencePercentage: "38.0%" },
  });

  assert.strictEqual(res6.status, "REVIEW REQUIRED", "OCR < 0.45 must produce REVIEW REQUIRED");
  assert.strictEqual(res6.reviewReason, "LOW_OCR_CONFIDENCE");
  assert.strictEqual(res6.matches, false);
  console.log("  [PASS] Scenario 6: Low OCR confidence (38%) correctly returns REVIEW REQUIRED.");

  // -------------------------------------------------------------------------
  // Scenario 7: Missing QR Code on Clean Physical Scan
  // -------------------------------------------------------------------------
  console.log("\n--- Scenario 7: Missing QR on Clean Physical Scan ---");
  const res7 = evaluateCertificateAuthenticity({
    extractedFields: {
      certificate_number: "77889900",
      candidate_name: "DEEPAK KUMAR",
      total_marks: "410",
    },
    qrAnalysis: { detected: false },
    tamperAnalysis: { indicators_detected: [] },
    ocrMetrics: { averageConfidence: 0.88 },
  });

  // Missing QR alone does not prove forgery; it is UNVERIFIED
  assert.strictEqual(res7.status, "UNVERIFIED", "Missing QR on clean scan must be UNVERIFIED, not forged");
  assert.strictEqual(res7.matches, false);
  assert.strictEqual(res7.unverifiedReason, "NO_TRUSTED_ISSUER_EVIDENCE");
  console.log("  [PASS] Scenario 7: Clean paper scan without QR correctly classified as UNVERIFIED.");

  // -------------------------------------------------------------------------
  // Scenario 8: Subject Marks Arithmetic Mismatch
  // -------------------------------------------------------------------------
  console.log("\n--- Scenario 8: Marks Arithmetic Mismatch ---");
  const res8 = evaluateCertificateAuthenticity({
    extractedFields: {
      certificate_number: "22334455",
      candidate_name: "KAVITHA M",
      total_marks: "500", // Forged total
      subject_marks: [{ subject: "TAMIL", marks: 80 }, { subject: "ENGLISH", marks: 80 }, { subject: "MATHS", marks: 80 }],
      arithmetic_check: {
        applicable: true,
        consistent: false,
        calculated_sum: 240,
        recorded_total: 500,
        details: "Sum of 3 subject marks (240) differs from recorded total (500) by -260.",
      },
    },
    tamperAnalysis: {
      indicators_detected: ["MARKS_ARITHMETIC_MISMATCH"],
      forensic_summary: "Recorded total (500) contradicts sum of subject marks (240).",
    },
    ocrMetrics: { averageConfidence: 0.91 },
  });

  assert.strictEqual(res8.status, "REVIEW REQUIRED", "OCR-derived arithmetic mismatch alone must NOT be called tampering");
  assert.strictEqual(res8.reviewReason, "ARITHMETIC_INCONSISTENCY_UNCONFIRMED");
  assert.strictEqual(res8.matches, false);
  assert.ok(res8.summary.includes("arithmetic inconsistency"), "Summary must state arithmetic mismatch");
  console.log("  [PASS] Scenario 8: Arithmetic-only discrepancy correctly produces REVIEW REQUIRED (not tampering).");

  // -------------------------------------------------------------------------
  // Scenario 9: Exact Demo Registry Match (CRITICAL RULE)
  // -------------------------------------------------------------------------
  console.log("\n--- Scenario 9: Exact Demo Registry Match (Never AUTHENTICITY VERIFIED) ---");
  const res9 = evaluateCertificateAuthenticity({
    extractedFields: {
      certificate_number: "11180882",
      candidate_name: "SARAVANAVEL C",
      total_marks: "824",
      registration_number: "1610468100",
      board: "State Board",
      course: "12th",
    },
    qrAnalysis: { detected: false },
    tamperAnalysis: { indicators_detected: [] },
    ocrMetrics: { averageConfidence: 0.95 },
    userInputs: { board: "State Board", classType: "12" },
  });

  // MANDATORY REQUIREMENT: A demo match must NEVER produce AUTHENTICITY VERIFIED
  assert.strictEqual(res9.status, "UNVERIFIED", "Demo match must be UNVERIFIED (test fixture only)");
  assert.notStrictEqual(res9.status, "AUTHENTICITY VERIFIED", "Demo match MUST NEVER produce AUTHENTICITY VERIFIED");
  assert.strictEqual(res9.matches, false);
  assert.strictEqual(res9.unverifiedReason, "DEMO_TEST_FIXTURE_ONLY");
  assert.ok(res9.demoFixtureMatch !== null, "Demo fixture match details must be attached");
  assert.strictEqual(res9.demoFixtureMatch.isTestFixture, true, "Must be clearly labeled as test fixture");
  assert.ok(res9.summary.includes("local demonstration test record"), "Summary must state local test fixture");
  console.log("  [PASS] Scenario 9: Exact demo registry match correctly produces UNVERIFIED with clear test fixture notice.");

  // -------------------------------------------------------------------------
  // Scenario 10: Missing Core Certificate Identifiers
  // -------------------------------------------------------------------------
  console.log("\n--- Scenario 10: Missing Core Identifiers (No Cert No and No Name) ---");
  const res10 = evaluateCertificateAuthenticity({
    extractedFields: {
      certificate_number: null,
      candidate_name: null,
      total_marks: "450",
    },
    qrAnalysis: { detected: false },
    tamperAnalysis: { indicators_detected: [] },
    ocrMetrics: { averageConfidence: 0.85 },
  });

  assert.strictEqual(res10.status, "REVIEW REQUIRED", "Missing core identifiers must trigger REVIEW REQUIRED");
  assert.strictEqual(res10.reviewReason, "MISSING_CORE_IDENTIFIERS");
  assert.strictEqual(res10.matches, false);
  console.log("  [PASS] Scenario 10: Missing cert serial and candidate name correctly triggers REVIEW REQUIRED.");


  // =========================================================================
  // SECURITY REGRESSIONS (added after source review)
  // =========================================================================
  console.log("\n--- Security S1: Test-key signature can NEVER authenticate ---");
  const testKeyToken = createSyntheticSignedToken({ name: "PRIYA SHARMA", registration_number: "9876543210" });
  const baseFields = { certificate_number: "CBSE9876543", candidate_name: "PRIYA SHARMA", registration_number: "9876543210", candidate_name_confidence: 0.95, field_status: CONFIDENT_FS };
  const s1 = evaluateCertificateAuthenticity({
    extractedFields: baseFields,
    qrAnalysis: { detected: true, raw_payload: testKeyToken, payload_classification: { payload_type: "SIGNED_TOKEN" } },
    tamperAnalysis: { indicators_detected: [] },
    ocrMetrics: { averageConfidence: 0.95 },
  });
  assert.notStrictEqual(s1.status, "AUTHENTICITY VERIFIED");
  assert.strictEqual(s1.status, "UNVERIFIED");
  assert.strictEqual(s1.digitalSignature.status, "TEST KEY ONLY");
  assert.strictEqual(s1.issuerTrust.verified, false);
  // even if someone injects a test-flagged key into the "production" keystore:
  const flagged = { "TEST-CBSE-KEY-2024": { ...TEST_ISSUER_KEYSTORE["TEST-CBSE-KEY-2024"] } };
  const s1b = evaluateCertificateAuthenticity({
    extractedFields: baseFields,
    qrAnalysis: { detected: true, raw_payload: testKeyToken, payload_classification: { payload_type: "SIGNED_TOKEN" } },
    tamperAnalysis: { indicators_detected: [] }, ocrMetrics: { averageConfidence: 0.95 }, keystore: flagged,
  });
  assert.notStrictEqual(s1b.status, "AUTHENTICITY VERIFIED");
  assert.deepStrictEqual(Object.keys(TRUSTED_ISSUER_KEYSTORE), [], "Production keystore must be empty unless real keys are configured");
  console.log("  [PASS] S1: Test keys never verify, even when injected; production keystore is empty by default.");

  console.log("\n--- Security S2: Valid signature must be bound to the scanned page ---");
  const goodToken = signHarness({ name: "PRIYA SHARMA", registration_number: "9876543210" });
  const mkQr = (tok) => ({ detected: true, raw_payload: tok, raw_payload_preview: tok.slice(0, 120) + "...", payload_classification: { payload_type: "SIGNED_TOKEN" } });
  const common = { tamperAnalysis: { indicators_detected: [] }, ocrMetrics: { averageConfidence: 0.9 }, keystore: HARNESS_KEYSTORE };
  const s2a = evaluateCertificateAuthenticity({ ...common, qrAnalysis: mkQr(goodToken),
    extractedFields: { certificate_number: "X1234567", candidate_name: null, field_status: { candidate_name: "MISSING", certificate_number: "CONFIDENT" } } });
  assert.strictEqual(s2a.status, "REVIEW REQUIRED");
  assert.strictEqual(s2a.reviewReason, "SIGNED_CLAIMS_NOT_BOUND_TO_DOCUMENT");
  const s2b = evaluateCertificateAuthenticity({ ...common, qrAnalysis: mkQr(goodToken),
    extractedFields: { certificate_number: "X1234567", candidate_name: "UGoll", candidate_name_confidence: 0.59, field_status: { candidate_name: "UNCERTAIN" } } });
  assert.notStrictEqual(s2b.status, "AUTHENTICITY VERIFIED");
  const s2c = evaluateCertificateAuthenticity({ ...common, qrAnalysis: mkQr(goodToken),
    extractedFields: { certificate_number: "X1234567", candidate_name: "ARAVIND KUMAR", candidate_name_confidence: 0.96, field_status: { candidate_name: "CONFIDENT" } } });
  assert.strictEqual(s2c.status, "VERIFIED MISMATCH", "Confident different name vs signed record is a real contradiction");
  const s2d = evaluateCertificateAuthenticity({ ...common, qrAnalysis: mkQr(goodToken),
    extractedFields: { candidate_name: "PRIYA SHARMA", candidate_name_confidence: 0.95, registration_number: "1111111111", field_status: { candidate_name: "CONFIDENT", registration_number: "UNCERTAIN" } } });
  assert.notStrictEqual(s2d.status, "VERIFIED MISMATCH", "UNCERTAIN OCR numbers must not create a verified mismatch");
  assert.strictEqual(s2d.status, "AUTHENTICITY VERIFIED");
  console.log("  [PASS] S2: Unbound / uncertain / contradicting fields handled without false approval or false mismatch.");

  console.log("\n--- Security S3: Token validity rules ---");
  const expired = signHarness({ name: "PRIYA SHARMA", exp: 1000 });
  assert.strictEqual(verifyCryptographicSignature(expired, HARNESS_KEYSTORE).error, "TOKEN_EXPIRED");
  const hdr = Buffer.from(JSON.stringify({ alg: "none", typ: "JWT", kid: "HARNESS-ISSUER-KEY-1" })).toString("base64url");
  const noneTok = `${hdr}.${Buffer.from("{}").toString("base64url")}.AAAA`;
  assert.strictEqual(verifyCryptographicSignature(noneTok, HARNESS_KEYSTORE).error, "UNSUPPORTED_ALGORITHM");
  assert.strictEqual(verifyCryptographicSignature(goodToken.slice(0, 120) + "...", HARNESS_KEYSTORE).verified, false);
  assert.strictEqual(verifyCryptographicSignature(goodToken, HARNESS_KEYSTORE).verified, true);
  assert.strictEqual(verifyCryptographicSignature(goodToken, {}).error, "KEY_NOT_FOUND");
  console.log("  [PASS] S3: Expired, alg=none, truncated and unknown-key tokens are rejected; intact token verifies.");

  console.log("\n--- Security S4: Production keystore loader rejects test keys ---");
  const tmp = path.join(os.tmpdir(), `dt-keys-${process.pid}.json`);
  fs.writeFileSync(tmp, JSON.stringify({
    "TEST-CBSE-KEY-2024": { issuer: "x", publicKeyPem: HARNESS_PUB },
    "FLAGGED": { issuer: "x", publicKeyPem: HARNESS_PUB, isTestKey: true },
    "BADPEM": { issuer: "x", publicKeyPem: "not a pem" },
    "REAL-1": { issuer: "Configured Issuer", publicKeyPem: HARNESS_PUB },
  }));
  const loaded = loadTrustedIssuerKeystore(tmp);
  fs.unlinkSync(tmp);
  assert.deepStrictEqual(Object.keys(loaded), ["REAL-1"]);
  assert.strictEqual(loaded["REAL-1"].isTestKey, false);
  console.log("  [PASS] S4: TEST-/flagged/invalid entries are refused; only valid configured keys load.");

  console.log("\n--- Reliability R1: OCR confidence gate on the live-route data shape ---");
  const pyMetrics = { total_boxes_detected: 115, average_confidence: 0.124, average_confidence_percentage: "12.4%" };
  const r1 = evaluateCertificateAuthenticity({ extractedFields: { certificate_number: "1234567", candidate_name: "A B" }, ocrMetrics: mapPythonOcrMetrics(pyMetrics), tamperAnalysis: { indicators_detected: [] } });
  assert.strictEqual(r1.reviewReason, "LOW_OCR_CONFIDENCE", "Gate must see Python's snake_case metrics via the mapper");
  const r1b = evaluateCertificateAuthenticity({ extractedFields: { certificate_number: "1234567", candidate_name: "A B" },
    ocrMetrics: mapPythonOcrMetrics({ ...pyMetrics, readable_text_confidence: 0.91 }), tamperAnalysis: { indicators_detected: [] } });
  assert.notStrictEqual(r1b.reviewReason, "LOW_OCR_CONFIDENCE", "Watermark-deflated mean must not alone trigger the gate when readable text is confident");
  console.log("  [PASS] R1: Low-confidence gate fires on live shape; uses text-weighted confidence when available.");

  console.log("\n--- Reliability R2: Tampering needs more than an arithmetic mismatch ---");
  const r2 = evaluateCertificateAuthenticity({ extractedFields: { certificate_number: "22334455", candidate_name: "K M", arithmetic_check: { details: "sum 449 vs 349" } },
    tamperAnalysis: { indicators_detected: ["MARKS_ARITHMETIC_MISMATCH", "LOCAL_COMPRESSION_VARIATION"] }, ocrMetrics: { averageConfidence: 0.9 } });
  assert.strictEqual(r2.status, "SUSPECTED TAMPERING");
  console.log("  [PASS] R2: Arithmetic + independent visual indicator still escalates to SUSPECTED TAMPERING.");

  console.log("\n--- Honesty H1: demo-fixture comparison is not reported as accuracy ---");
  const rec = DEMO_REFERENCE_REGISTRY[0];
  const h1 = evaluateCertificateAuthenticity({ extractedFields: { certificate_number: rec.certificate_number, candidate_name: rec.candidate_name, candidate_name_confidence: 0.95, field_status: { candidate_name: "CONFIDENT" } },
    tamperAnalysis: { indicators_detected: [] }, ocrMetrics: { averageConfidence: 0.95 } });
  assert.strictEqual(h1.extractionAccuracy.measured, false);
  assert.strictEqual(h1.extractionAccuracy.accuracyPercentage, null);
  assert.strictEqual(h1.status, "UNVERIFIED");
  console.log("  [PASS] H1: Demo match stays UNVERIFIED and reports no accuracy percentage.");

  console.log("\n=================================================================");
  console.log("ALL AUTHENTICITY ENGINE + SECURITY REGRESSION TESTS PASSED!");
  console.log("=================================================================");
}

runAuthenticityEngineTests();
