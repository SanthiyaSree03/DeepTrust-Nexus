/**
 * backend/test_class_and_document_validation.js
 * ---------------------------------------------
 * Tests for:
 * 1. 10th Marksheet uploaded with 12th std selected -> Highlights selected 12th and flags VERIFIED MISMATCH
 * 2. 12th Marksheet uploaded with 10th std selected -> Highlights selected 10th and flags VERIFIED MISMATCH
 * 3. Matching standard (10th with 10th, 12th with 12th) -> classMismatch.isMismatch is false
 * 4. Document rejection: Documents that are not 10th or 12th marksheets are rejected.
 */

const assert = require("assert");
const path = require("path");
const fs = require("fs");
const cp = require("child_process");
const { evaluateCertificateAuthenticity } = require("./server");

function runValidationTests() {
  console.log("=== DeepTrust Nexus Standard Selection & Marksheet Validation Test Suite ===\n");

  // -------------------------------------------------------------------------
  // Test 1: User gives 10th marksheet while selecting 12th Std
  // -------------------------------------------------------------------------
  console.log("--- Test 1: 10th Marksheet uploaded with 12th Option Selected ---");
  const extracted10th = {
    certificate_number: "SEC202401",
    candidate_name: "SANTHIYA SREE",
    board: "State Board of School Examinations, Tamil Nadu",
    course: "Secondary School Leaving Certificate (10th)",
    detected_standard: "10",
    detected_standard_label: "10th Standard (SSLC)",
    total_marks: "449",
    registration_number: "2195306000",
    candidate_name_confidence: 0.95,
  };

  const res1 = evaluateCertificateAuthenticity({
    extractedFields: extracted10th,
    userInputs: { classType: "12", board: "State Board" },
  });

  assert.strictEqual(res1.status, "VERIFIED MISMATCH", "Status must be VERIFIED MISMATCH when 10th marksheet is uploaded with 12th selected");
  assert.ok(res1.classMismatch, "classMismatch object must be present in result");
  assert.strictEqual(res1.classMismatch.isMismatch, true, "isMismatch must be true");
  assert.strictEqual(res1.classMismatch.selectedClass, "12", "Selected class must be '12'");
  assert.strictEqual(res1.classMismatch.detectedClass, "10", "Detected class must be '10'");
  assert.strictEqual(res1.classMismatch.selectedClassDisplay, "12th Standard");
  assert.strictEqual(res1.classMismatch.detectedClassDisplay, "10th Standard (SSLC Marksheet)");
  assert.ok(res1.summary.includes("12th Standard") && res1.summary.includes("10th Standard"), "Summary must mention both selected 12th and detected 10th");
  console.log("  [PASS] 10th marksheet with 12th selection flagged as VERIFIED MISMATCH with highlighted 12th and 10th.");

  // -------------------------------------------------------------------------
  // Test 2: User gives 12th marksheet while selecting 10th Std
  // -------------------------------------------------------------------------
  console.log("\n--- Test 2: 12th Marksheet uploaded with 10th Option Selected ---");
  const extracted12th = {
    certificate_number: "HSE202402",
    candidate_name: "SANTHIYA SREE",
    board: "State Board of School Examinations, Tamil Nadu",
    course: "Higher Secondary Examination (12th)",
    detected_standard: "12",
    detected_standard_label: "12th Standard (HSC)",
    total_marks: "527",
    registration_number: "36260174",
    candidate_name_confidence: 0.95,
  };

  const res2 = evaluateCertificateAuthenticity({
    extractedFields: extracted12th,
    userInputs: { classType: "10", board: "State Board" },
  });

  assert.strictEqual(res2.status, "VERIFIED MISMATCH", "Status must be VERIFIED MISMATCH when 12th marksheet is uploaded with 10th selected");
  assert.strictEqual(res2.classMismatch.isMismatch, true);
  assert.strictEqual(res2.classMismatch.selectedClass, "10");
  assert.strictEqual(res2.classMismatch.detectedClass, "12");
  console.log("  [PASS] 12th marksheet with 10th selection flagged as VERIFIED MISMATCH with highlighted 10th and 12th.");

  // -------------------------------------------------------------------------
  // Test 3: Matching Selection (12th with 12th, 10th with 10th)
  // -------------------------------------------------------------------------
  console.log("\n--- Test 3: Matching Standard Selections ---");
  const res3a = evaluateCertificateAuthenticity({
    extractedFields: extracted12th,
    userInputs: { classType: "12", board: "State Board" },
  });
  assert.strictEqual(res3a.classMismatch.isMismatch, false, "Matching 12th must have isMismatch = false");

  const res3b = evaluateCertificateAuthenticity({
    extractedFields: extracted10th,
    userInputs: { classType: "10", board: "State Board" },
  });
  assert.strictEqual(res3b.classMismatch.isMismatch, false, "Matching 10th must have isMismatch = false");
  console.log("  [PASS] Matching selections (10th/10th, 12th/12th) produce isMismatch = false.");

  // -------------------------------------------------------------------------
  // Test 4: Document Validation in Python extract_cli.py
  // -------------------------------------------------------------------------
  console.log("\n--- Test 4: Non-Marksheet Document Rejection in extract_cli.py ---");
  const pythonExecutable = path.join(__dirname, "..", "ai", "venv", "Scripts", "python.exe");
  const pyCode = `
import sys, os
sys.path.insert(0, r"${path.join(__dirname, "..", "ai").replace(/\\/g, "/")}")
from extract_cli import validate_marksheet_type

# 4A. Aadhaar Card
res_aadhaar = validate_marksheet_type([{"text": "Aadhaar Card"}], "GOVERNMENT OF INDIA UNIQUE IDENTIFICATION AUTHORITY OF INDIA MERA AADHAAR", {})
assert res_aadhaar["valid"] == False, "Aadhaar must be rejected"
assert res_aadhaar["reason"] == "UNSUPPORTED_DOCUMENT_TYPE"

# 4B. PAN Card
res_pan = validate_marksheet_type([{"text": "INCOME TAX"}], "INCOME TAX DEPARTMENT PERMANENT ACCOUNT NUMBER GOVT OF INDIA", {})
assert res_pan["valid"] == False, "PAN must be rejected"
assert res_pan["reason"] == "UNSUPPORTED_DOCUMENT_TYPE"

# 4C. College Degree Certificate
res_degree = validate_marksheet_type([{"text": "BACHELOR OF TECHNOLOGY"}], "UNIVERSITY OF MADRAS CONVOCATION DEGREE OF BACHELOR OF TECHNOLOGY", {})
assert res_degree["valid"] == False, "College Degree must be rejected"
assert res_degree["reason"] == "UNSUPPORTED_DOCUMENT_TYPE"

# 4D. Invoice / Bill
res_bill = validate_marksheet_type([{"text": "TAX INVOICE"}], "TAX INVOICE BILL TO GSTIN PAYMENT RECEIPT TOTAL AMOUNT DUE", {})
assert res_bill["valid"] == False, "Invoice must be rejected"

# 4E. Random text / Insufficient text
res_random = validate_marksheet_type([{"text": "Hello world"}], "HELLO WORLD THIS IS A RANDOM FILE", {})
assert res_random["valid"] == False, "Random text must be rejected"
assert res_random["reason"] == "NOT_10TH_OR_12TH_MARKSHEET"

# 4F. Valid 10th Marksheet
res_10 = validate_marksheet_type([{"text": "SSLC"}], "STATE BOARD OF SCHOOL EXAMINATIONS SECONDARY SCHOOL LEAVING CERTIFICATE X STANDARD MARKS TOTAL", {})
assert res_10["valid"] == True, "10th marksheet must be accepted"
assert res_10["standard"] == "10"

# 4G. Valid 12th Marksheet
res_12 = validate_marksheet_type([{"text": "HSC"}], "STATE BOARD OF SCHOOL EXAMINATIONS HIGHER SECONDARY EXAMINATION CLASS XII MARKS TOTAL", {})
print("DEBUG res_12:", res_12)
assert res_12["valid"] == True, f"12th marksheet must be accepted, got: {res_12}"
assert res_12["standard"] == "12", f"Expected standard 12, got: {res_12.get('standard')}"

print("ALL_PYTHON_VALIDATION_PASSED")

`;

  try {
    const res = cp.spawnSync(pythonExecutable, ["-c", pyCode], { encoding: "utf-8" });
    const pyOutput = (res.stdout || "") + (res.stderr || "");
    if (res.error) throw res.error;
    if (res.status !== 0) {
      throw new Error(`Python exited with status ${res.status}: ${res.stderr || res.stdout}`);
    }
    assert.ok(pyOutput.includes("ALL_PYTHON_VALIDATION_PASSED"), "Python validation tests must pass");
    console.log("  [PASS] Non-marksheet documents (Aadhaar, PAN, Degree, Invoice, Random) rejected; 10th & 12th marksheets accepted.");
  } catch (err) {
    console.error("  [FAIL] Python validation test failed:", err.message);
    process.exit(1);
  }

  console.log("\n=== ALL VALIDATION TESTS PASSED SUCCESSFULLY! ===");
}

runValidationTests();
