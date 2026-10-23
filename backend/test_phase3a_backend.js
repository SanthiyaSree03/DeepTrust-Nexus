// Automated Regression Test Suite for DeepTrust Nexus Name Evaluation and Verification Statuses
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

// Load the exact functions directly from backend/server.js to prevent any test drift
const serverCode = fs.readFileSync(__dirname + "/server.js", "utf8");
const sandbox = { console, Math };
const script = new vm.Script(
  serverCode.substring(
    serverCode.indexOf("const DEMO_REFERENCE_REGISTRY"),
    serverCode.indexOf("// Health check")
  )
);
vm.createContext(sandbox);
script.runInContext(sandbox);

const { DEMO_REFERENCE_REGISTRY, evaluateCandidateName, calculateDataMatchScore, evaluateAuthenticity } = sandbox;

function runRegressionSuite() {
  console.log("=== DeepTrust Nexus Regression Test Suite ===");

  // -------------------------------------------------------------
  // Regression Case 1: RAVANAIEL C vs SARAVANAVEL C (Degraded OCR)
  // -------------------------------------------------------------
  console.log("\n--- Case 1: Degraded OCR 'RAVANAIEL C' vs 'SARAVANAVEL C' ---");
  const nameEval1 = evaluateCandidateName("RAVANAIEL C", "SARAVANAVEL C");
  assert.strictEqual(nameEval1.status, "PARTIAL_MATCH", "Should be PARTIAL_MATCH");
  assert.ok(nameEval1.earned >= 10 && nameEval1.earned <= 13, `Partial points earned should be 10-13 (got ${nameEval1.earned})`);
  assert.strictEqual(nameEval1.isConflict, false, "Should not be a critical conflict");
  assert.strictEqual(nameEval1.matched, true, "Should be matched with partial points");

  const auth1 = evaluateAuthenticity(
    {
      certificate_number: "11180882",
      candidate_name: "RAVANAIEL C",
      board: "State Board of School Examinations, Tamil Nadu",
      course: "Higher Secondary Examination (12th)",
    },
    { board: "State Board", classType: "12" }
  );
  assert.strictEqual(auth1.status, "VERIFIED", "Status should be VERIFIED for demo reference record");
  assert.strictEqual(auth1.dataMatchScore, 82, `Data match score should be 82% (35+20+15+12=82), got ${auth1.dataMatchScore}`);
  console.log("  [PASS] Case 1 correctly awards partial points (12/15) with an 82% match score.");

  // -------------------------------------------------------------
  // Regression Case 2: nilina Sree vs SANTHIYA SREE S (Substantial Disparity / Conflict)
  // -------------------------------------------------------------
  console.log("\n--- Case 2: Primary Name Conflict 'nilina Sree' vs 'SANTHIYA SREE S' ---");
  const nameEval2 = evaluateCandidateName("nilina Sree", "SANTHIYA SREE S");
  assert.strictEqual(nameEval2.isConflict, true, "Must be flagged as critical identity conflict");
  assert.strictEqual(nameEval2.earned, 0, "Conflicting primary name must earn 0 name points");
  assert.strictEqual(nameEval2.matched, false, "Matched must be false");

  const auth2 = evaluateAuthenticity(
    {
      certificate_number: "36260174",
      candidate_name: "nilina Sree",
      board: "State Board of School Examinations, Tamil Nadu",
      course: "Higher Secondary Examination (12th)",
      total_marks: "527",
      registration_number: "2414265216",
    },
    { board: "State Board", classType: "12" }
  );
  // CRITICAL REQUIREMENT: Must NOT return VERIFIED! Must return MISMATCH!
  assert.strictEqual(auth2.status, "MISMATCH", "Status MUST be MISMATCH due to primary name conflict");
  assert.strictEqual(auth2.matches, false, "matches must be false");
  assert.strictEqual(auth2.dataMatchScore, 85, `Score must drop to 85% (not 100%), got ${auth2.dataMatchScore}`);
  assert.ok(auth2.mismatches.length > 0, "mismatches array must contain the candidate name conflict");
  console.log("  [PASS] Case 2 correctly prevents false positive: Status is MISMATCH, score is 85% (not 100%).");

  // -------------------------------------------------------------
  // Regression Case 3: Exact Matches for All Three Demo Records
  // -------------------------------------------------------------
  console.log("\n--- Case 3: Exact Matches for Demo Records ---");
  // Demo 1 Exact
  const authDemo1 = evaluateAuthenticity(
    {
      certificate_number: "11180882",
      candidate_name: "SARAVANAVEL C",
      board: "State Board",
      course: "12th",
      total_marks: "824",
      registration_number: "1610468100",
    },
    { board: "State Board", classType: "12" }
  );
  assert.strictEqual(authDemo1.status, "VERIFIED");
  assert.strictEqual(authDemo1.dataMatchScore, 100);
  console.log("  [PASS] Demo 1 Exact Match (Saravanavel C): VERIFIED, 100%");

  // Demo 2 Exact
  const authDemo2 = evaluateAuthenticity(
    {
      certificate_number: "36260174",
      candidate_name: "SANTHIYA SREE S",
      board: "State Board",
      course: "12th",
      total_marks: "527",
      registration_number: "2414265216",
    },
    { board: "State Board", classType: "12" }
  );
  assert.strictEqual(authDemo2.status, "VERIFIED");
  assert.strictEqual(authDemo2.dataMatchScore, 100);
  console.log("  [PASS] Demo 2 Exact Match (Santhiya Sree S): VERIFIED, 100%");

  // Demo 3 Exact
  const authDemo3 = evaluateAuthenticity(
    {
      certificate_number: "CBSE9876543",
      candidate_name: "PRIYA SHARMA",
      board: "CBSE",
      course: "10th",
      total_marks: "485",
      registration_number: "9876543210",
    },
    { board: "CBSE", classType: "10" }
  );
  assert.strictEqual(authDemo3.status, "VERIFIED");
  assert.strictEqual(authDemo3.dataMatchScore, 100);
  console.log("  [PASS] Demo 3 Exact Match (Priya Sharma): VERIFIED, 100%");

  // -------------------------------------------------------------
  // Regression Case 4: Unrelated Candidate Name (Identity Conflict Override)
  // -------------------------------------------------------------
  console.log("\n--- Case 4: Unrelated Candidate Name on Registered Serial ---");
  const authUnrelated = evaluateAuthenticity(
    {
      certificate_number: "CBSE9876543",
      candidate_name: "VIKRAM MALHOTRA", // Registered candidate is PRIYA SHARMA
      board: "CBSE",
      course: "10th",
      total_marks: "485",
      registration_number: "9876543210",
    },
    { board: "CBSE", classType: "10" }
  );
  // CRITICAL REQUIREMENT 6: High overall score (85%) must NOT override critical identity conflict!
  assert.strictEqual(authUnrelated.status, "MISMATCH", "Unrelated name must trigger MISMATCH");
  assert.strictEqual(authUnrelated.matches, false);
  assert.strictEqual(authUnrelated.dataMatchScore, 85, "Name score must be 0/15");
  assert.ok(authUnrelated.mismatches.some(m => m.includes("conflict")), "Must report identity conflict in mismatches");
  console.log("  [PASS] Case 4 correctly prevents score override: Status is MISMATCH (candidate identity conflict).");

  // -------------------------------------------------------------
  // Regression Case 5: Missing Candidate Name Field
  // -------------------------------------------------------------
  console.log("\n--- Case 5: Missing Candidate Name ---");
  const authMissingName = evaluateAuthenticity(
    {
      certificate_number: "11180882",
      candidate_name: null,
      board: "State Board",
      course: "12th",
    },
    { board: "State Board", classType: "12" }
  );
  assert.strictEqual(authMissingName.status, "UNVERIFIED", "Missing name must return UNVERIFIED");
  assert.strictEqual(authMissingName.matches, false);
  console.log("  [PASS] Case 5 correctly returns UNVERIFIED when candidate name is missing.");

  // -------------------------------------------------------------
  // Regression Case 6: Missing Certificate Number Field
  // -------------------------------------------------------------
  console.log("\n--- Case 6: Missing Certificate Number ---");
  const authMissingCert = evaluateAuthenticity(
    {
      certificate_number: null,
      candidate_name: "SARAVANAVEL C",
      board: "State Board",
      course: "12th",
    },
    { board: "State Board", classType: "12" }
  );
  assert.strictEqual(authMissingCert.status, "UNVERIFIED");
  assert.strictEqual(authMissingCert.matches, false);
  console.log("  [PASS] Case 6 correctly returns UNVERIFIED when certificate number is missing.");

  // -------------------------------------------------------------
  // Regression Case 7: Demo Reference Description Check (Requirement 5)
  // -------------------------------------------------------------
  console.log("\n--- Case 7: Explicit Demo Reference Dataset Descriptions ---");
  assert.ok(authDemo1.summary.includes("demo test record") || authDemo1.summary.includes("local demonstration reference dataset"), "Summary must state demo dataset");
  assert.ok(authDemo1.evidence.some(e => e.note.includes("demo")), "Evidence must clearly state demo dataset");
  console.log("  [PASS] Case 7 explicitly states demo reference matching instead of live government databases.");

  // -------------------------------------------------------------
  // Regression Case 8: 6%-Confidence Incorrect Name -> REVIEW REQUIRED
  // -------------------------------------------------------------
  console.log("\n--- Case 8: 6%-Confidence Incorrect Name ---");
  const nameEvalLowConf = evaluateCandidateName("nilina Sree", "SANTHIYA SREE S", { nameConfidence: 0.06 });
  assert.strictEqual(nameEvalLowConf.isConflict, false, "Low-confidence name must NEVER be flagged as critical identity conflict");
  assert.strictEqual(nameEvalLowConf.isUncertain, true, "Low-confidence name must be flagged as uncertain");
  assert.strictEqual(nameEvalLowConf.status, "UNCERTAIN_LOW_CONFIDENCE", "Status must be UNCERTAIN_LOW_CONFIDENCE");

  const authLowConf = evaluateAuthenticity(
    {
      certificate_number: "36260174",
      candidate_name: "nilina Sree",
      candidate_name_confidence: 0.06,
      field_status: { candidate_name: "UNCERTAIN" },
      board: "State Board of School Examinations, Tamil Nadu",
      course: "Higher Secondary Examination (12th)",
      total_marks: "527",
      registration_number: "2414265216",
    },
    { board: "State Board", classType: "12" }
  );
  assert.strictEqual(authLowConf.status, "REVIEW REQUIRED", "6%-confidence name must route to REVIEW REQUIRED, NOT MISMATCH");
  assert.strictEqual(authLowConf.matches, false, "matches must be false");
  console.log("  [PASS] Case 8 correctly prevents false mismatch: 6%-confidence name routes to REVIEW REQUIRED.");

  // -------------------------------------------------------------
  // Regression Case 9: High-Confidence Genuine Name Mismatch -> MISMATCH
  // -------------------------------------------------------------
  console.log("\n--- Case 9: High-Confidence Genuine Name Mismatch ---");
  const nameEvalHighConf = evaluateCandidateName("VIKRAM MALHOTRA", "PRIYA SHARMA", { nameConfidence: 0.95 });
  assert.strictEqual(nameEvalHighConf.isConflict, true, "High-confidence mismatch MUST be flagged as critical identity conflict");
  assert.strictEqual(nameEvalHighConf.status, "CONFLICT", "Status must be CONFLICT");

  const authHighConf = evaluateAuthenticity(
    {
      certificate_number: "CBSE9876543",
      candidate_name: "VIKRAM MALHOTRA",
      candidate_name_confidence: 0.95,
      board: "CBSE",
      course: "10th",
      total_marks: "485",
      registration_number: "9876543210",
    },
    { board: "CBSE", classType: "10" }
  );
  assert.strictEqual(authHighConf.status, "MISMATCH", "High-confidence name mismatch must return MISMATCH");
  console.log("  [PASS] Case 9 correctly identifies high-confidence genuine name mismatch as MISMATCH.");

  // -------------------------------------------------------------
  // Regression Case 10: Missing Candidate Name -> UNVERIFIED
  // -------------------------------------------------------------
  console.log("\n--- Case 10: Missing Candidate Name ---");
  const nameEvalMissing = evaluateCandidateName(null, "SANTHIYA SREE S");
  assert.strictEqual(nameEvalMissing.isConflict, false, "Missing name is not a conflict");
  assert.strictEqual(nameEvalMissing.isUncertain, true, "Missing name is uncertain");
  assert.strictEqual(nameEvalMissing.status, "MISSING");
  console.log("  [PASS] Case 10 correctly marks missing candidate name as MISSING with zero conflict.");

  // -------------------------------------------------------------
  // Regression Case 11: Correctly Extracted Matching Name -> VERIFIED (Demo)
  // -------------------------------------------------------------
  console.log("\n--- Case 11: Correctly Extracted Matching Name ---");
  const nameEvalExact = evaluateCandidateName("SANTHIYA SREE S", "SANTHIYA SREE S", { nameConfidence: 0.98 });
  assert.strictEqual(nameEvalExact.matched, true, "Exact name must match");
  assert.strictEqual(nameEvalExact.isConflict, false, "Exact name must not conflict");
  assert.strictEqual(nameEvalExact.status, "EXACT_MATCH");
  assert.strictEqual(nameEvalExact.earned, 15);

  const authExact = evaluateAuthenticity(
    {
      certificate_number: "36260174",
      candidate_name: "SANTHIYA SREE S",
      candidate_name_confidence: 0.98,
      board: "State Board",
      course: "12th",
      total_marks: "527",
      registration_number: "2414265216",
    },
    { board: "State Board", classType: "12" }
  );
  assert.strictEqual(authExact.status, "VERIFIED", "Accurate match must return VERIFIED for demo record");
  assert.strictEqual(authExact.dataMatchScore, 100);
  console.log("  [PASS] Case 11 correctly evaluates genuine matching name as VERIFIED with 100% score.");

  console.log("\n========================================================");
  console.log("ALL 11 REGRESSION TESTS PASSED WITH 100% SUCCESS!");
  console.log("========================================================");
}

runRegressionSuite();
