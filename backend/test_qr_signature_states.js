/**
 * QR and signature state tests. Uses an injected, harness-only issuer key to exercise the approval
 * path; that key is NOT an official issuer key. No network access and no URL is ever fetched.
 */
const assert = require("assert");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const server = require("./server");
const { evaluateCertificateAuthenticity, createSyntheticSignedToken } = server;

const { privateKey, publicKey } = crypto.generateKeyPairSync("rsa", {
  modulusLength: 2048,
  publicKeyEncoding: { type: "spki", format: "pem" },
  privateKeyEncoding: { type: "pkcs8", format: "pem" },
});
const KS = { "HARNESS-1": { issuer: "Harness Issuer (not official)", publicKeyPem: publicKey, algorithm: "RSA-SHA256", isTestKey: false } };
const sign = (claims) => createSyntheticSignedToken(claims, privateKey, "HARNESS-1");
const FS = { candidate_name: "CONFIDENT", registration_number: "CONFIDENT", certificate_number: "CONFIDENT" };
const FIELDS = { candidate_name: "MOHAN RAJ", candidate_name_confidence: 0.95, registration_number: "XM23R2195306000", certificate_number: "CBSE1234567", field_status: FS };
const qrOf = (payload, type, extra = {}) => ({ detected: true, detection_state: "DECODED_RECOGNIZED", raw_payload: payload, raw_payload_preview: String(payload).slice(0, 120), payload_classification: { payload_type: type, ...extra.pc }, consistency_check: extra.cc, });
const run = (o) => evaluateCertificateAuthenticity({ extractedFields: FIELDS, tamperAnalysis: { indicators_detected: [] }, ocrMetrics: { averageConfidence: 0.9 }, keystore: KS, ...o });

let n = 0;
const ok = (msg) => { n++; console.log(`  [PASS] ${msg}`); };

// ---- QR states -----------------------------------------------------------------------------
let r = run({ qrAnalysis: { detected: false } });
assert.strictEqual(r.qrVerification.state, "QR_NOT_DETECTED");
assert.ok(!/forg/i.test(r.qrVerification.explanation) || /not evidence of forgery/.test(r.qrVerification.explanation));
ok("No QR -> QR Not Detected (explicitly not evidence of forgery).");

r = run({ qrAnalysis: { detected: true, detection_state: "DETECTED_UNREADABLE", payload_classification: { payload_type: "UNREADABLE_IMAGE" } } });
assert.strictEqual(r.qrVerification.state, "QR_UNREADABLE");
ok("QR pattern without decodable content -> QR Detected but Unreadable.");

r = run({ qrAnalysis: qrOf("https://certverify.example.org/v?id=1", "EXTERNAL_URL", { pc: { is_url: true, domain: "certverify.example.org" } }) });
assert.strictEqual(r.qrVerification.state, "QR_VERIFICATION_UNAVAILABLE");
assert.notStrictEqual(r.status, "AUTHENTICITY VERIFIED");
assert.ok(/not opened or checked/.test(r.qrVerification.explanation));
assert.strictEqual(r.qrVerification.classification.domain, "certverify.example.org");
ok("Decoded external URL -> QR Verification Unavailable (link not opened); never Verified.");

r = run({ qrAnalysis: qrOf("https://dge.tn.gov.in/verify?x=1", "OFFICIAL_GOV_URL", { pc: { is_url: true, domain: "dge.tn.gov.in", is_official_domain: true } }) });
assert.strictEqual(r.qrVerification.state, "QR_VERIFICATION_UNAVAILABLE");
assert.notStrictEqual(r.status, "AUTHENTICITY VERIFIED");
ok("An official-looking government domain is still not verification.");

r = run({ qrAnalysis: qrOf("REF:ABC123", "PLAIN_TEXT") });
assert.strictEqual(r.qrVerification.state, "QR_DECODED");
ok("Unsigned decoded text -> QR Decoded.");

r = run({ qrAnalysis: qrOf("REG:1|NAME:X", "STRUCTURED_DELIMITED", { cc: { status: "DISCREPANCY_DETECTED", discrepancies: ["Name differs"] } }) });
assert.strictEqual(r.qrVerification.state, "QR_INVALID_OR_CONTRADICTORY");
ok("QR data contradicting the page -> QR Invalid or Contradictory.");

// ---- signed tokens ---------------------------------------------------------------------------
const good = sign({ name: "MOHAN RAJ", registration_number: "XM23R2195306000" });
r = run({ qrAnalysis: qrOf(good, "SIGNED_TOKEN") });
assert.strictEqual(r.qrVerification.state, "QR_VERIFIED");
assert.strictEqual(r.signatureVerification.state, "SIGNATURE_VERIFIED");
assert.strictEqual(r.status, "AUTHENTICITY VERIFIED");
ok("Valid production-style token bound to the page -> QR Verified + Signature Verified.");

r = run({ qrAnalysis: qrOf(good, "SIGNED_TOKEN"), extractedFields: { certificate_number: "CBSE1234567", candidate_name: null, field_status: { certificate_number: "CONFIDENT" } } });
assert.strictEqual(r.signatureVerification.state, "SIGNATURE_VERIFIED");
assert.strictEqual(r.qrVerification.state, "QR_DECODED");
assert.notStrictEqual(r.status, "AUTHENTICITY VERIFIED");
ok("Valid signature but not tied to the page -> Signature Verified, QR only Decoded, overall not Verified.");

const testTok = createSyntheticSignedToken({ name: "MOHAN RAJ", registration_number: "XM23R2195306000" });
r = run({ qrAnalysis: qrOf(testTok, "SIGNED_TOKEN") });
assert.strictEqual(r.signatureVerification.state, "SIGNATURE_UNTRUSTED");
assert.strictEqual(r.qrVerification.state, "QR_VERIFICATION_UNAVAILABLE");
assert.notStrictEqual(r.status, "AUTHENTICITY VERIFIED");
assert.ok(/demonstration key/.test(r.signatureVerification.explanation));
ok("Demonstration-key token -> Signature Untrusted, QR Verification Unavailable, never Verified.");

const parts = good.split(".");
const tampered = `${parts[0]}.${Buffer.from(JSON.stringify({ name: "SOMEONE ELSE" })).toString("base64url")}.${parts[2]}`;
r = run({ qrAnalysis: qrOf(tampered, "SIGNED_TOKEN") });
assert.strictEqual(r.signatureVerification.state, "SIGNATURE_INVALID");
assert.strictEqual(r.qrVerification.state, "QR_INVALID_OR_CONTRADICTORY");
ok("Tampered signed token -> Signature Invalid + QR Invalid or Contradictory.");

r = run({ qrAnalysis: qrOf(good, "SIGNED_TOKEN"), keystore: {} });
assert.strictEqual(r.signatureVerification.state, "SIGNATURE_UNTRUSTED");
ok("Token from an unconfigured issuer key -> Signature Untrusted.");

// ---- no signature / PDF -----------------------------------------------------------------------
r = run({ qrAnalysis: { detected: false } });
assert.strictEqual(r.signatureVerification.state, "SIGNATURE_NOT_PRESENT");
assert.ok(!["SUSPECTED TAMPERING", "VERIFIED MISMATCH"].includes(r.status));
assert.ok(/not evidence of forgery/.test(r.signatureVerification.explanation));
ok("Paper scan without a digital signature -> Signature Not Present; not treated as fraud.");

r = run({ qrAnalysis: { detected: false }, documentMetadata: { pdf_signature_markers: { detected: true, verified: false } } });
assert.strictEqual(r.signatureVerification.state, "SIGNATURE_VERIFICATION_UNAVAILABLE");
assert.strictEqual(r.signatureVerification.source, "PDF");
assert.notStrictEqual(r.status, "AUTHENTICITY VERIFIED");
ok("PDF with an embedded signature structure -> Verification Unavailable (never auto-approved).");

r = run({ qrAnalysis: { detected: false }, documentMetadata: { pdf_signature_markers: { detected: false } } });
assert.strictEqual(r.signatureVerification.state, "SIGNATURE_NOT_PRESENT");
ok("PDF without signature structure -> Signature Not Present.");

// ---- static safety check: the backend must not fetch QR URLs ---------------------------------
const src = fs.readFileSync(path.join(__dirname, "server.js"), "utf8");
for (const banned of [/\bfetch\s*\(/, /require\(["'](axios|node-fetch|got|request|undici)["']\)/, /https?\.(get|request)\s*\(/, /require\(["']https?["']\)/]) {
  assert.ok(!banned.test(src), `server.js must not make outbound HTTP requests (${banned})`);
}
ok("server.js contains no outbound HTTP client: QR URLs are never fetched (no SSRF surface).");

console.log(`\nALL ${n} QR / SIGNATURE STATE TESTS PASSED`);
