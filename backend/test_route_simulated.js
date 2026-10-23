/**
 * Drives the REAL /api/verify route handler + REAL ai/extract_cli.py + REAL decision engine, with:
 *   - Express/Multer/CORS/dotenv replaced by capture stubs (no HTTP server is started),
 *   - the Python venv check bypassed and the spawn redirected to ai/_fake_pipeline_driver.py,
 *   - a FAKE OCR reader (scripted layout).
 * It verifies route mapping and the response contract. It is NOT a live HTTP/UI test and says nothing
 * about EasyOCR accuracy on real documents.
 * Env: PYTHON (default "python3" / "python"), PYTHONPATH as needed for your Python environment.
 */
const assert = require("assert");
const Module = require("module");
const path = require("path");
const fs = require("fs");
const os = require("os");
const cp = require("child_process");

const handlers = {};
const stubs = {
  express: Object.assign(() => ({ use() {}, get(p, ...h) { handlers["GET " + p] = h[h.length - 1]; }, post(p, ...h) { handlers["POST " + p] = h[h.length - 1]; }, listen() {} }), { json: () => () => {} }),
  cors: () => () => {},
  multer: Object.assign(() => ({ single: () => () => {} }), { diskStorage: () => ({}) }),
  dotenv: { config() {} },
};
const origLoad = Module._load;
Module._load = function (request, ...rest) { return stubs[request] || origLoad.call(this, request, ...rest); };

const defaultVenv = path.join(__dirname, "..", "ai", "venv", "Scripts", "python.exe");
const PY = process.env.PYTHON || (fs.existsSync(defaultVenv) ? defaultVenv : (process.platform === "win32" ? "python" : "python3"));
const driver = path.join(__dirname, "..", "ai", "_fake_pipeline_driver.py");
const realSpawn = cp.spawn;
cp.spawn = (_exe, args) => realSpawn(PY, [driver, args[1]], { env: process.env });
const realExists = fs.existsSync;
fs.existsSync = (p) => (String(p).endsWith("python.exe") ? true : realExists(p));

require("./server"); // registers handlers on the capture stub
const handler = handlers["POST /api/verify"];
assert.ok(handler, "POST /api/verify handler was not registered");

const img = path.join(os.tmpdir(), `dt-route-${process.pid}.png`);
cp.execFileSync(PY, ["-c", `import cv2,numpy as np;cv2.imwrite(r"${img}",np.full((1400,1800,3),255,np.uint8))`]);

const res = {
  code: 200,
  status(c) { this.code = c; return this; },
  json(body) { this.body = body; this.done(); return this; },
};
new Promise((resolve) => { res.done = resolve; handler({ file: { path: img }, body: { classType: "12", board: "Tamil Nadu" } }, res); })
  .then(() => {
    const b = res.body;
    assert.strictEqual(res.code, 200, JSON.stringify(b).slice(0, 300));
    assert.strictEqual(b.success, true);
    // extraction
    assert.strictEqual(b.extractedFields.candidate_name, "MOHAN RAJ");
    assert.strictEqual(b.extractedFields.field_status.candidate_name, "CONFIDENT");
    assert.strictEqual(b.extractedFields.candidate_name_first_pass.raw, "UGoll");
    assert.strictEqual(b.extractedFields.registration_number, "XM23R2195306000");
    assert.strictEqual(b.extractedFields.emis_id, "2414265216");
    // measured (not hardcoded 0.95) per-field confidences
    assert.strictEqual(b.ocrMetrics.fieldsConfidence.registration_number, 0.9);
    assert.strictEqual(b.ocrMetrics.fieldsConfidence.total_marks, 0.95);
    // metrics mapped for the engine and dashboard
    assert.ok(typeof b.ocrMetrics.readableTextConfidence === "number");
    assert.deepStrictEqual(b.ocrMetrics.languagesActive, ["en"]);
    assert.ok(Array.isArray(b.ocrMetrics.variantsUsed) && b.ocrMetrics.variantsUsed.length >= 1);
    assert.ok(b.ocrDiagnostics && b.ocrDiagnostics.name_region && b.ocrDiagnostics.name_region.best);
    // verification: no QR, no signature, no trusted issuer -> honest, non-accusatory result
    assert.strictEqual(b.verification.status, "UNVERIFIED");
    assert.strictEqual(b.qrVerification.state, "QR_NOT_DETECTED");
    assert.strictEqual(b.signatureVerification.state, "SIGNATURE_NOT_PRESENT");
    assert.strictEqual(b.verification.authenticityLikelihood, "Not available");
    assert.notStrictEqual(b.verification.status, "AUTHENTICITY VERIFIED");
    console.log("  [PASS] Real route + real extract_cli + real engine (fake OCR reader): response contract, measured confidences, states and honest UNVERIFIED result verified.");
    fs.existsSync = realExists;
    try { fs.unlinkSync(img); } catch (e) { /* already cleaned */ }
    process.exit(0);
  })
  .catch((e) => { console.error("  [FAIL]", e.message); process.exit(1); });
setTimeout(() => { console.error("  [FAIL] timeout"); process.exit(1); }, 120000);
