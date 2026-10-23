/**
 * backend/test_pdf_upload.js
 * --------------------------
 * Focused integration test suite for PDF upload, file validation,
 * 25 MB size limit enforcement, format rejection, and cleanup.
 */

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const http = require("http");
const { app } = require("./server");

async function runUploadTestSuite() {
  console.log("=== DeepTrust Nexus PDF & Upload Pipeline Test Suite ===\n");

  // Start app on ephemeral port for isolated testing
  const server = await new Promise((resolve) => {
    const s = app.listen(0, () => resolve(s));
  });
  const port = server.address().port;
  const baseUrl = `http://127.0.0.1:${port}`;

  const uploadsDir = path.join(__dirname, "uploads");
  const getUploadsCount = () => {
    if (!fs.existsSync(uploadsDir)) return 0;
    return fs.readdirSync(uploadsDir).filter((f) => f.startsWith("marksheet-")).length;
  };

  const initialUploadsCount = getUploadsCount();

  try {
    // -----------------------------------------------------------------------
    // Test 1: Reject unsupported file extension (.exe)
    // -----------------------------------------------------------------------
    console.log("--- Test 1: Reject Unsupported File (.exe) ---");
    const boundary = "----WebKitFormBoundary" + Math.random().toString(36).substring(2);
    const bodyParts = [
      `--${boundary}\r\n`,
      'Content-Disposition: form-data; name="classType"\r\n\r\n',
      "12\r\n",
      `--${boundary}\r\n`,
      'Content-Disposition: form-data; name="board"\r\n\r\n',
      "State Board\r\n",
      `--${boundary}\r\n`,
      'Content-Disposition: form-data; name="marksheet"; filename="malicious.exe"\r\n',
      "Content-Type: application/x-msdownload\r\n\r\n",
      "MZ90FakeExecutableData\r\n",
      `--${boundary}--\r\n`,
    ];
    const bodyBuffer = Buffer.from(bodyParts.join(""), "utf-8");

    const res1 = await fetch(`${baseUrl}/api/verify`, {
      method: "POST",
      headers: {
        "Content-Type": `multipart/form-data; boundary=${boundary}`,
      },
      body: bodyBuffer,
    });

    const data1 = await res1.json();
    assert.strictEqual(res1.status, 400, `Expected status 400, got ${res1.status}`);
    assert.strictEqual(data1.success, false);
    assert.ok(
      data1.error.includes("Only JPG, JPEG, PNG, and PDF"),
      `Expected allowed formats message, got: ${data1.error}`
    );
    console.log(`  [PASS] Rejected .exe file: '${data1.error}'`);

    // -----------------------------------------------------------------------
    // Test 2: Reject oversized file (> 25 MB)
    // -----------------------------------------------------------------------
    console.log("\n--- Test 2: Reject Oversized File (> 25 MB) ---");
    // Generate a multipart payload exceeding 25 MB
    const largeSize = 25 * 1024 * 1024 + 1024; // 25 MB + 1 KB
    const headPart = Buffer.from(
      `--${boundary}\r\nContent-Disposition: form-data; name="marksheet"; filename="oversized.pdf"\r\nContent-Type: application/pdf\r\n\r\n`
    );
    const tailPart = Buffer.from(`\r\n--${boundary}--\r\n`);
    const dummyChunk = Buffer.alloc(1024 * 1024, 65); // 1 MB chunk of 'A'

    // Stream to server
    const reqPromise = new Promise((resolve, reject) => {
      const req = http.request(
        `${baseUrl}/api/verify`,
        {
          method: "POST",
          headers: {
            "Content-Type": `multipart/form-data; boundary=${boundary}`,
          },
        },
        (res) => {
          let resData = "";
          res.on("data", (c) => (resData += c));
          res.on("end", () => resolve({ status: res.statusCode, body: resData }));
        }
      );
      req.on("error", reject);
      req.write(headPart);
      // Write 26 MB
      for (let i = 0; i < 26; i++) {
        req.write(dummyChunk);
      }
      req.write(tailPart);
      req.end();
    });

    const res2 = await reqPromise;
    assert.strictEqual(res2.status, 400, `Expected status 400 for oversized file, got ${res2.status}`);
    const data2 = JSON.parse(res2.body);
    assert.strictEqual(data2.success, false);
    assert.ok(
      data2.error.includes("25 MB limit") || data2.error.includes("too large"),
      `Expected limit error, got: ${data2.error}`
    );
    console.log(`  [PASS] Rejected oversized file: '${data2.error}'`);

    // -----------------------------------------------------------------------
    // Test 3: Multer accepts valid PDF and forwards to OCR pipeline
    // -----------------------------------------------------------------------
    console.log("\n--- Test 3: Accept PDF Marksheet Upload ---");
    // Minimal valid 1-page PDF
    const minimalPdf =
      "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n" +
      "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n" +
      "3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n" +
      "xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \n" +
      "trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n";

    const pdfParts = [
      `--${boundary}\r\n`,
      'Content-Disposition: form-data; name="classType"\r\n\r\n',
      "12\r\n",
      `--${boundary}\r\n`,
      'Content-Disposition: form-data; name="board"\r\n\r\n',
      "State Board\r\n",
      `--${boundary}\r\n`,
      'Content-Disposition: form-data; name="marksheet"; filename="valid_marksheet.pdf"\r\n',
      "Content-Type: application/pdf\r\n\r\n",
      minimalPdf,
      `\r\n--${boundary}--\r\n`,
    ];
    const pdfBuffer = Buffer.from(pdfParts.join(""), "utf-8");

    const res3 = await fetch(`${baseUrl}/api/verify`, {
      method: "POST",
      headers: {
        "Content-Type": `multipart/form-data; boundary=${boundary}`,
      },
      body: pdfBuffer,
    });

    const data3 = await res3.json();
    assert.strictEqual(res3.status, 200, `Expected 200, got ${res3.status}: ${JSON.stringify(data3)}`);
    assert.strictEqual(data3.success, true);
    assert.ok(data3.verification, "Must include verification decision");
    assert.ok(data3.documentMetadata, "Must include documentMetadata");
    assert.strictEqual(data3.documentMetadata.format, "PDF");
    assert.strictEqual(data3.documentMetadata.page_count, 1);
    console.log(`  [PASS] Successfully accepted PDF marksheet: format=${data3.documentMetadata.format}, status=${data3.verification.status}`);

    // -----------------------------------------------------------------------
    // Test 4: Preserves existing JPG/PNG Upload Behavior
    // -----------------------------------------------------------------------
    console.log("\n--- Test 4: Preserve JPG/PNG Upload Behavior ---");
    const sampleImagePath = path.join(__dirname, "..", "ai", "sample_marksheet.jpg");
    assert.ok(fs.existsSync(sampleImagePath), "sample_marksheet.jpg must exist");
    const imageBytes = fs.readFileSync(sampleImagePath);

    const imgPartsHead = Buffer.from(
      `--${boundary}\r\nContent-Disposition: form-data; name="classType"\r\n\r\n12\r\n` +
      `--${boundary}\r\nContent-Disposition: form-data; name="board"\r\n\r\nState Board\r\n` +
      `--${boundary}\r\nContent-Disposition: form-data; name="marksheet"; filename="sample_marksheet.jpg"\r\nContent-Type: image/jpeg\r\n\r\n`
    );
    const imgPartsTail = Buffer.from(`\r\n--${boundary}--\r\n`);
    const fullImgPayload = Buffer.concat([imgPartsHead, imageBytes, imgPartsTail]);

    const res4 = await fetch(`${baseUrl}/api/verify`, {
      method: "POST",
      headers: {
        "Content-Type": `multipart/form-data; boundary=${boundary}`,
      },
      body: fullImgPayload,
    });

    const data4 = await res4.json();
    assert.strictEqual(res4.status, 200, `Expected 200, got ${res4.status}: ${JSON.stringify(data4)}`);
    assert.strictEqual(data4.success, true);
    assert.ok(data4.verification);
    assert.ok(data4.extractedFields);
    console.log(`  [PASS] Successfully accepted JPG marksheet: name='${data4.extractedFields.candidate_name}', status=${data4.verification.status}`);

    // -----------------------------------------------------------------------
    // Test 5: Verify Temporary Uploads Cleanup
    // -----------------------------------------------------------------------
    console.log("\n--- Test 5: Temporary Uploads Cleanup Verification ---");
    // Give OS a moment to finish any asynchronous fs.unlink
    await new Promise((r) => setTimeout(r, 1000));
    const finalUploadsCount = getUploadsCount();
    assert.strictEqual(
      finalUploadsCount,
      initialUploadsCount,
      `Uploads directory leaked temp files: initial=${initialUploadsCount}, final=${finalUploadsCount}`
    );
    console.log(`  [PASS] All temporary uploads cleaned up (active temp files = ${finalUploadsCount})`);

    console.log("\nALL 5 BACKEND UPLOAD INTEGRATION TESTS PASSED SUCCESSFULLY!");
  } finally {
    server.close();
  }
}

runUploadTestSuite().catch((err) => {
  console.error("Test Suite Failed:", err);
  process.exit(1);
});
