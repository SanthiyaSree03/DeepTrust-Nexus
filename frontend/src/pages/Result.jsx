import { useLocation, useNavigate } from "react-router-dom";

function Result() {
  const location = useLocation();
  const navigate = useNavigate();

  const data = location.state?.verificationData;
  const userInputs = location.state?.userInputs || {};

  // If accessed directly without an upload session
  if (!data) {
    return (
      <div className="result-page">
        <div className="result-container">
          <h1>Verification Result</h1>
          <div className="result-card" style={{ textAlign: "center" }}>
            <h2>No Marksheet Scanned</h2>
            <p style={{ color: "#6b7280", margin: "20px 0" }}>
              No verification session was found. Please upload a marksheet to begin analysis.
            </p>
            <button onClick={() => navigate("/upload")}>Go to Upload</button>
          </div>
        </div>
      </div>
    );
  }

  const { verification, extractedFields = {}, ocrMetrics = {}, authenticityDisclaimer } = data;
  const isVerified = verification.status === "VERIFIED";
  const isMismatch = verification.status === "MISMATCH";

  // Status badge styling
  let badgeBackground = "#fef2f2";
  let badgeColor = "#991b1b";
  let statusBorder = "#ef4444";

  if (isVerified) {
    badgeBackground = "#ecfdf5";
    badgeColor = "#065f46";
    statusBorder = "#10b981";
  } else if (isMismatch) {
    badgeBackground = "#fffbeb";
    badgeColor = "#92400e";
    statusBorder = "#f59e0b";
  }

  // Determine OCR confidence display (show "Unavailable" if not available or empty)
  const ocrConfidenceText =
    ocrMetrics.ocrConfidenceDisplay && ocrMetrics.ocrConfidenceDisplay !== "0%" && ocrMetrics.ocrConfidenceDisplay !== "Unavailable"
      ? ocrMetrics.ocrConfidenceDisplay
      : ocrMetrics.averageConfidencePercentage && ocrMetrics.averageConfidencePercentage !== "0%"
      ? ocrMetrics.averageConfidencePercentage
      : "Unavailable";

  return (
    <div className="result-page">
      <div className="result-container">
        <h1>Verification Result</h1>

        <div className="result-card">
          {/* Status Header Badge */}
          <div
            className="status"
            style={{
              backgroundColor: badgeBackground,
              color: badgeColor,
              border: `2px solid ${statusBorder}`,
              fontSize: "20px",
              letterSpacing: "1px",
              marginTop: 0,
            }}
          >
            {verification.statusText || verification.status}
          </div>

          <p style={{ marginTop: "20px", color: "#374151", lineHeight: "1.6" }}>
            {verification.summary}
          </p>

          {/* DOCUMENT DATA MATCH SCORE SECTION */}
          <div
            style={{
              marginTop: "25px",
              padding: "20px",
              borderRadius: "12px",
              backgroundColor: verification.dataMatchScore !== null ? "#f0fdf4" : "#f9fafb",
              border: `1px solid ${verification.dataMatchScore !== null ? "#bbf7d0" : "#e5e7eb"}`,
              textAlign: "center",
            }}
          >
            <h3 style={{ margin: "0 0 6px 0", fontSize: "16px", color: "#374151", textTransform: "uppercase" }}>
              Document Data Match Score
            </h3>
            <div
              style={{
                fontSize: verification.dataMatchScore !== null ? "38px" : "20px",
                fontWeight: "bold",
                color: verification.dataMatchScore !== null ? (verification.dataMatchScore >= 80 ? "#15803d" : "#b45309") : "#6b7280",
                margin: "8px 0",
              }}
            >
              {verification.dataMatchScore !== null ? verification.dataMatchScoreDisplay : "Score unavailable — no reference record"}
            </div>
            <p style={{ margin: "4px 0 0 0", fontSize: "13px", color: "#6b7280" }}>
              {verification.dataMatchScore !== null
                ? "Calculated strictly from weighted comparisons against the demo reference record."
                : "No baseline record exists in the reference dataset. A match score cannot be fabricated without reference data."}
            </p>
          </div>

          {/* FIELD-BY-FIELD MATCH BREAKDOWN (if reference record exists) */}
          {verification.matchBreakdown && verification.matchBreakdown.length > 0 && (
            <div style={{ marginTop: "25px" }}>
              <h3 style={{ borderBottom: "1px solid #e5e7eb", paddingBottom: "8px", marginBottom: "12px" }}>
                Field-by-Field Verification Breakdown
              </h3>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
                  <thead>
                    <tr style={{ backgroundColor: "#f8fafc", textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
                      <th style={{ padding: "8px" }}>Field</th>
                      <th style={{ padding: "8px" }}>Extracted (OCR)</th>
                      <th style={{ padding: "8px" }}>Expected (Demo Registry)</th>
                      <th style={{ padding: "8px", textAlign: "center" }}>Weight</th>
                      <th style={{ padding: "8px", textAlign: "center" }}>Match</th>
                    </tr>
                  </thead>
                  <tbody>
                    {verification.matchBreakdown.map((item, idx) => (
                      <tr key={idx} style={{ borderBottom: "1px solid #f1f5f9" }}>
                        <td style={{ padding: "10px 8px", fontWeight: "600" }}>{item.field}</td>
                        <td style={{ padding: "10px 8px", color: "#334155" }}>{item.extracted}</td>
                        <td style={{ padding: "10px 8px", color: "#334155" }}>{item.expected}</td>
                        <td style={{ padding: "10px 8px", textAlign: "center", color: "#64748b" }}>
                          {item.earned}/{item.weight} pts
                        </td>
                        <td style={{ padding: "10px 8px", textAlign: "center" }}>
                          {item.matched ? (
                            <span style={{ color: "#16a34a", fontWeight: "bold" }}>✅ Match</span>
                          ) : (
                            <span style={{ color: "#dc2626", fontWeight: "bold" }}>❌ Mismatch</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* User Submitted vs Extracted Details */}
          <div className="result-details" style={{ marginTop: "25px" }}>
            <h3 style={{ borderBottom: "1px solid #e5e7eb", paddingBottom: "8px", marginBottom: "15px" }}>
              Extracted Document Metadata
            </h3>
            <p>
              <strong>Certificate No:</strong>{" "}
              {extractedFields.certificate_number || "Not detected"}
            </p>
            <p>
              <strong>Candidate Name:</strong>{" "}
              {extractedFields.candidate_name || "Not clearly identified"}
            </p>
            <p>
              <strong>Board / Authority:</strong>{" "}
              {extractedFields.board || userInputs.board || "State Board"}
            </p>
            <p>
              <strong>Course / Class:</strong>{" "}
              {extractedFields.course || `${userInputs.classType}th`}
            </p>
            {extractedFields.total_marks && (
              <p>
                <strong>Extracted Total Marks:</strong> {extractedFields.total_marks}
              </p>
            )}
            {extractedFields.registration_number && (
              <p>
                <strong>Permanent Reg Number:</strong> {extractedFields.registration_number}
              </p>
            )}
          </div>

          {/* Demo Reference Registry Details */}
          {verification.trustedRecord && (
            <div
              style={{
                marginTop: "20px",
                padding: "16px",
                backgroundColor: "#f8fafc",
                borderRadius: "8px",
                border: "1px solid #cbd5e1",
              }}
            >
              <h3 style={{ margin: "0 0 6px 0", color: "#1e293b", fontSize: "15px" }}>
                🏛️ Sample Reference Registry (Demo Dataset)
              </h3>
              <p style={{ margin: "4px 0 10px 0", fontSize: "12px", color: "#64748b" }}>
                Baseline comparison record loaded from the local demo dataset (not an official government database).
              </p>
              <p style={{ margin: "4px 0", fontSize: "14px" }}>
                <strong>Registered Name:</strong> {verification.trustedRecord.candidate_name}
              </p>
              <p style={{ margin: "4px 0", fontSize: "14px" }}>
                <strong>Registered Board:</strong> {verification.trustedRecord.board}
              </p>
              <p style={{ margin: "4px 0", fontSize: "14px" }}>
                <strong>Registered Course:</strong> {verification.trustedRecord.course}
              </p>
              {verification.trustedRecord.total_marks && (
                <p style={{ margin: "4px 0", fontSize: "14px" }}>
                  <strong>Registered Marks:</strong> {verification.trustedRecord.total_marks}
                </p>
              )}
            </div>
          )}

          {/* Verification Evidence Checks */}
          <div className="verification-checks">
            <h3 style={{ borderBottom: "1px solid #e5e7eb", paddingBottom: "8px", marginBottom: "12px" }}>
              Evidence &amp; Verification Checks
            </h3>
            {verification.evidence && verification.evidence.length > 0 ? (
              verification.evidence.map((item, idx) => (
                <p key={idx} style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ fontSize: "18px" }}>{item.passed ? "✅" : "❌"}</span>
                  <span>
                    <strong>{item.check}:</strong> {item.note}
                  </span>
                </p>
              ))
            ) : (
              <p>No checks recorded.</p>
            )}
          </div>

          {/* SEPARATE OCR CONFIDENCE SECTION */}
          <div className="score" style={{ borderTop: "1px solid #e5e7eb", paddingTop: "25px", marginTop: "25px" }}>
            <h2 style={{ fontSize: "15px", color: "#6b7280", textTransform: "uppercase" }}>
              Optical Character Recognition (OCR) Confidence
            </h2>
            <p style={{ margin: "5px 0", color: "#1f2937", fontSize: "36px", fontWeight: "bold" }}>
              {ocrConfidenceText}
            </p>
            <small style={{ color: "#6b7280", display: "block", marginTop: "6px" }}>
              {ocrMetrics.totalBoxes || 0} text boxes detected via EasyOCR with 2x CLAHE preprocessing.
            </small>
            <div
              style={{
                marginTop: "12px",
                padding: "10px 14px",
                backgroundColor: "#eff6ff",
                borderRadius: "6px",
                fontSize: "12px",
                color: "#1e40af",
                lineHeight: "1.5",
              }}
            >
              ℹ️ <strong>Critical Distinction:</strong> OCR confidence reflects optical character clarity, not authenticity. Document authenticity is verified strictly by comparing extracted fields against authoritative reference records.
            </div>
          </div>

          <div style={{ marginTop: "30px", display: "flex", gap: "12px" }}>
            <button onClick={() => navigate("/upload")} style={{ flex: 1 }}>
              Verify Another Marksheet
            </button>
            <button
              onClick={() => navigate("/dashboard")}
              style={{
                flex: 1,
                background: "#f3f4f6",
                color: "#1f2937",
                border: "1px solid #d1d5db",
              }}
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Result;