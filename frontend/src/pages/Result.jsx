import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

function Result() {
  const location = useLocation();
  const navigate = useNavigate();
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  const data = location.state?.verificationData;
  const userInputs = location.state?.userInputs || {};

  // If accessed directly without an active upload session
  if (!data) {
    return (
      <div style={{ minHeight: "100vh", backgroundColor: "#f8fafc", padding: "60px 20px" }}>
        <div style={{ maxWidth: "560px", margin: "0 auto", backgroundColor: "#ffffff", borderRadius: "16px", padding: "40px 32px", textAlign: "center", boxShadow: "0 4px 20px rgba(0,0,0,0.06)", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: "48px", marginBottom: "16px" }}>📄</div>
          <h2 style={{ fontSize: "22px", fontWeight: "700", color: "#0f172a", marginBottom: "10px" }}>No Marksheet Scanned</h2>
          <p style={{ color: "#64748b", fontSize: "14px", lineHeight: "1.6", marginBottom: "28px" }}>
            No active verification session was found. Please upload a marksheet document (JPG, PNG, or PDF) to begin multi-layer credential inspection.
          </p>
          <button
            onClick={() => navigate("/upload")}
            style={{
              padding: "12px 28px",
              backgroundColor: "#0f172a",
              color: "#ffffff",
              border: "none",
              borderRadius: "8px",
              fontWeight: "600",
              fontSize: "14px",
              cursor: "pointer",
            }}
          >
            Go to Upload
          </button>
        </div>
      </div>
    );
  }

  const {
    verification = {},
    digitalSignature = verification.digitalSignature || null,
    extractionAccuracy = verification.extractionAccuracy || null,
    extractedFields = {},
    qrAnalysis = null,
    tamperAnalysis = null,
    ocrMetrics = {},
    documentMetadata = null,
  } = data;

  const status = verification.status || "UNVERIFIED";

  // Concise QR / signature states are derived once by the backend
  const TONES = {
    success: { bg: "#ecfdf5", color: "#065f46", border: "#a7f3d0" },
    info: { bg: "#eff6ff", color: "#1d4ed8", border: "#bfdbfe" },
    warning: { bg: "#fffbeb", color: "#92400e", border: "#fde68a" },
    danger: { bg: "#fef2f2", color: "#991b1b", border: "#fecaca" },
    neutral: { bg: "#f1f5f9", color: "#475569", border: "#cbd5e1" },
  };
  const qrV = verification.qrVerification || data.qrVerification || null;
  const sigV = verification.signatureVerification || data.signatureVerification || null;

  // Primary Status Theme Palette
  let statusTheme;
  if (status === "AUTHENTICITY VERIFIED") {
    statusTheme = {
      bg: "#ecfdf5",
      border: "#10b981",
      color: "#065f46",
      badgeBg: "#d1fae5",
      badgeColor: "#065f46",
      icon: "🛡️",
      title: "Authenticity Verified",
      subtitle: "Trusted cryptographic digital signature validated with matching certificate credentials.",
    };
  } else if (status === "VERIFIED MISMATCH") {
    statusTheme = {
      bg: "#fef2f2",
      border: "#ef4444",
      color: "#991b1b",
      badgeBg: "#fee2e2",
      badgeColor: "#991b1b",
      icon: "⚠️",
      title: "Verified Mismatch Detected",
      subtitle: "Material conflict identified between document text and authoritative / QR data.",
    };
  } else if (status === "SUSPECTED TAMPERING") {
    statusTheme = {
      bg: "#fffbeb",
      border: "#f59e0b",
      color: "#92400e",
      badgeBg: "#fef3c7",
      badgeColor: "#92400e",
      icon: "🔍",
      title: "Suspected Tampering",
      subtitle: "Forensic image manipulation anomalies or marks arithmetic discrepancies detected.",
    };
  } else if (status === "REVIEW REQUIRED") {
    statusTheme = {
      bg: "#faf5ff",
      border: "#a855f7",
      color: "#6b21a8",
      badgeBg: "#f3e8ff",
      badgeColor: "#6b21a8",
      icon: "📋",
      title: "Manual Review Required",
      subtitle: "Low OCR character legibility, missing core identifiers, or ambiguous evidence requires human inspection.",
    };
  } else if (sigV?.state === "PHYSICAL_SIGNATURE_DETECTED" && (tamperAnalysis?.indicators_detected?.length || 0) === 0) {
    statusTheme = {
      bg: "#f0fdf4",
      border: "#86efac",
      color: "#166534",
      badgeBg: "#dcfce7",
      badgeColor: "#166534",
      icon: "🏛️",
      title: "Physical Marksheet Verified (Official Board Issuance)",
      subtitle: verification.summary || "Official authority signature and credentials verified. Standard physical marksheet issued without forensic tampering anomalies.",
    };
  } else {
    // UNVERIFIED
    statusTheme = {
      bg: "#f8fafc",
      border: "#94a3b8",
      color: "#334155",
      badgeBg: "#e2e8f0",
      badgeColor: "#334155",
      icon: "⚖️",
      title: "Authenticity Could Not Be Established",
      subtitle: "Document scan does not carry an offline-verifiable cryptographic digital signature or live issuer access.",
    };
  }

  // Digital Signature state
  const sigStatus = digitalSignature?.status || "NOT SIGNED / NOT AVAILABLE";
  let sigBadgeTheme = { bg: "#f1f5f9", color: "#475569", border: "#cbd5e1" };
  if (sigStatus === "APPROVED") {
    sigBadgeTheme = { bg: "#ecfdf5", color: "#065f46", border: "#a7f3d0" };
  } else if (sigStatus === "UNVERIFIED ISSUER") {
    sigBadgeTheme = { bg: "#fffbeb", color: "#92400e", border: "#fde68a" };
  } else if (sigStatus === "REVIEW REQUIRED") {
    sigBadgeTheme = { bg: "#faf5ff", color: "#6b21a8", border: "#e9d5ff" };
  } else if (sigStatus === "REJECTED") {
    sigBadgeTheme = { bg: "#fef2f2", color: "#991b1b", border: "#fecaca" };
  }
  if (sigV) {
    sigBadgeTheme = TONES[sigV.tone] || TONES.neutral;
  }
  const sigLabel = sigV ? sigV.label : sigStatus;

  // QR Code state
  let qrDisplayState = {
    title: "QR Code Not Detected",
    badge: "NOT DETECTED",
    badgeBg: "#f1f5f9",
    badgeColor: "#475569",
    note: "No QR code pattern was detected on this marksheet scan. Older examination certificates typically do not carry QR codes; this is standard and does not indicate forgery.",
  };

  const isQrUnauthenticatable = Boolean(
    qrAnalysis &&
    qrAnalysis.detected &&
    (qrAnalysis.detection_state === "DETECTED_UNREADABLE" ||
     qrV?.state === "QR_UNREADABLE" ||
     qrAnalysis.payload_classification?.payload_type === "UNREADABLE_IMAGE" ||
     qrAnalysis.payload_classification?.payload_type === "EMPTY")
  );

  if (qrAnalysis && qrAnalysis.detected) {
    const dState = qrAnalysis.detection_state || "DECODED";
    const pType = qrAnalysis.payload_classification?.payload_type;
    const consistency = qrAnalysis.consistency_check;

    if (dState === "DETECTED_UNREADABLE" || pType === "UNREADABLE_IMAGE") {
      qrDisplayState = {
        title: "QR Unauthenticatable (Maybe Tampered / Blur)",
        badge: "SUSPECTED TAMPERING / UNREADABLE",
        badgeBg: "#fff7ed",
        badgeColor: "#c2410c",
        note: "A QR pattern was detected on the certificate, but it cannot be authenticated or decoded. In AI-generated certificates and digital document fraud, non-standard or pseudo-random QR patterns indicate that the document may be tampered, synthetic, or artificially generated.",
      };
    } else if (consistency && consistency.status === "DISCREPANCY_DETECTED") {
      qrDisplayState = {
        title: "QR Verification Failed (Contradictory Evidence)",
        badge: "CONTRADICTION DETECTED",
        badgeBg: "#fef2f2",
        badgeColor: "#b91c1c",
        note: "Readable QR code directly contradicts the visible document text, indicating possible document alteration or a QR code copied from another certificate.",
      };
    } else if (digitalSignature?.status === "APPROVED" && pType === "SIGNED_TOKEN") {
      qrDisplayState = {
        title: "QR Payload Validated (Cryptographic Issuer Signature)",
        badge: "VALIDATED AGAINST ISSUER",
        badgeBg: "#ecfdf5",
        badgeColor: "#047857",
        note: `QR payload contains a cryptographically signed token validated against ${digitalSignature.issuer || "Trusted Keystore"}. Document integrity confirmed.`,
      };
    } else if (dState === "DECODED_RECOGNIZED") {
      qrDisplayState = {
        title: "QR Payload Recognized",
        badge: "PAYLOAD RECOGNIZED",
        badgeBg: "#eff6ff",
        badgeColor: "#1d4ed8",
        note: qrAnalysis.payload_classification?.is_official_domain
          ? `QR links to portal (${qrAnalysis.payload_classification?.domain}). Web links alone do not prove document genuineness.`
          : qrAnalysis.payload_classification?.description || "Structured credential payload recognized.",
      };
    } else {
      qrDisplayState = {
        title: "QR Code Decoded",
        badge: "DECODED",
        badgeBg: "#eff6ff",
        badgeColor: "#1d4ed8",
        note: "QR code data was extracted. No authoritative cryptographic signature was present in payload.",
      };
    }
  }

  if (qrV) {
    const t = TONES[qrV.tone] || TONES.neutral;
    qrDisplayState = { title: qrV.label, badge: qrV.label, badgeBg: t.bg, badgeColor: t.color, note: qrV.explanation };
  }

  // OCR Metrics
  const ocrConfidenceText =
    ocrMetrics.ocrConfidenceDisplay &&
    ocrMetrics.ocrConfidenceDisplay !== "0%" &&
    ocrMetrics.ocrConfidenceDisplay !== "Unavailable"
      ? ocrMetrics.ocrConfidenceDisplay
      : ocrMetrics.averageConfidencePercentage &&
        ocrMetrics.averageConfidencePercentage !== "0%"
      ? ocrMetrics.averageConfidencePercentage
      : "Unavailable";

  const demoFixture = verification.demoFixtureMatch;
  const claims = digitalSignature?.claims || null;
  const discrepancies = verification.discrepancies || qrAnalysis?.consistency_check?.discrepancies || [];

  const fstat = extractedFields.field_status || {};
  const fconf = extractedFields.field_confidence || {};
  const fnotes = extractedFields.field_notes || {};
  const confPct = (k) => (fconf[k] != null ? `${Math.round(fconf[k] * 100)}%` : null);

  const DISAGREE = "Different preprocessing passes read this differently; verify manually";
  const NAME_SOURCES = {
    HEADER: "Read next to candidate-name label",
    HEADER_FUZZY: "Name label damaged by OCR; verify manually",
    HEADER_REGION_REOCR: "Re-read from name region; passes agreed",
    HEADER_REGION_REOCR_UNCONFIRMED: "Re-read from name region; passes diverged",
    PATTERN_FALLBACK: "No name label found; best-guess text",
  };
  const CERT_SOURCES = {
    CBSE_PATTERN: "Matches CBSE serial pattern",
    LABELLED_SERIAL: "Read next to serial-number label",
    UNLABELLED_NUMERIC: "Unlabelled number; not anchored to label",
  };
  const REG_SOURCES = {
    LABELLED_REGISTRATION: "Read next to permanent-register label",
    LABELLED_ROLL: "Roll number (no permanent-register label)",
    FUZZY_LABEL_REGISTRATION: "Label damaged by OCR; verify manually",
    UNLABELLED_10_DIGIT: "Unlabelled 10-digit number; not anchored",
  };

  const nameSourceNote = () => {
    if (claims?.name) return `Verified against ${digitalSignature.issuer} signed claims`;
    if (fnotes.candidate_name === "VARIANTS_DISAGREE") return DISAGREE;
    return NAME_SOURCES[extractedFields.candidate_name_source] || (extractedFields.candidate_name ? "Read by OCR; no trusted reference checked" : "Not detected on document scan");
  };

  const getFieldStatus = (fieldKey, value, customConf = null) => {
    if (!value || value === "Not detected" || value === "MISSING") {
      return { status: "Missing", bg: "#f1f5f9", color: "#64748b", border: "#cbd5e1" };
    }
    const hasDiscrepancy = discrepancies.some(
      (d) =>
        d.toLowerCase().includes(fieldKey.replace("_", " ")) ||
        (fieldKey === "candidate_name" && d.toLowerCase().includes("name")) ||
        (fieldKey === "total_marks" && d.toLowerCase().includes("marks"))
    );
    if (hasDiscrepancy) {
      return { status: "Mismatch", bg: "#fef2f2", color: "#b91c1c", border: "#fecaca" };
    }
    if (fieldKey === "candidate_name") {
      const conf = customConf ?? extractedFields.candidate_name_confidence ?? 1.0;
      if (conf < 0.45 || extractedFields.field_status?.candidate_name === "UNCERTAIN") {
        return { status: "Uncertain", bg: "#fffbeb", color: "#b45309", border: "#fde68a" };
      }
      if (claims?.name && String(claims.name).toUpperCase() === String(value).toUpperCase()) {
        return { status: "Matched Trusted", bg: "#ecfdf5", color: "#065f46", border: "#a7f3d0" };
      }
      return { status: "Confident OCR", bg: "#eff6ff", color: "#1d4ed8", border: "#bfdbfe" };
    }
    if (fieldKey === "total_marks") {
      if (claims?.total_marks && String(claims.total_marks) === String(value)) {
        return { status: "Matched Trusted", bg: "#ecfdf5", color: "#065f46", border: "#a7f3d0" };
      }
      if (extractedFields.total_marks_conflict) {
        return { status: "Mismatch", bg: "#fef2f2", color: "#b91c1c", border: "#fecaca" };
      }
      if (extractedFields.total_marks_source === "CALCULATED_SUBJECT_SUM") {
        return { status: "Calculated", bg: "#ecfdf5", color: "#065f46", border: "#a7f3d0" };
      }
    }
    if (extractedFields.field_status?.[fieldKey] === "UNCERTAIN") {
      return { status: "Uncertain", bg: "#fffbeb", color: "#b45309", border: "#fde68a" };
    }
    if (extractedFields.field_status?.[fieldKey] === "CONFIDENT") {
      return { status: "Confident OCR", bg: "#eff6ff", color: "#1d4ed8", border: "#bfdbfe" };
    }
    return { status: "Read by OCR", bg: "#f8fafc", color: "#334155", border: "#e2e8f0" };
  };

  // Candidate Name display normalization
  const candidateNameValue = !extractedFields.candidate_name
    ? "Not detected"
    : fstat.candidate_name === "UNCERTAIN" && (extractedFields.candidate_name_confidence ?? 0) < 0.6
    ? "Not reliably read"
    : extractedFields.candidate_name;

  const candidateNameRaw =
    extractedFields.candidate_name && fstat.candidate_name === "UNCERTAIN" && (extractedFields.candidate_name_confidence ?? 0) < 0.6
      ? extractedFields.candidate_name
      : null;

  const candidateNameStatus = getFieldStatus("candidate_name", extractedFields.candidate_name, extractedFields.candidate_name_confidence);
  const regNoStatus = getFieldStatus("registration_number", extractedFields.registration_number);
  const certNoStatus = getFieldStatus("certificate_number", extractedFields.certificate_number);
  const totalMarksStatus = getFieldStatus("total_marks", extractedFields.total_marks);

  // Subject Marks & Arithmetic
  const subjects = extractedFields.subject_marks || [];
  const arithmetic = extractedFields.arithmetic_check || {};
  const hasTheoryOrPractical = subjects.some((s) => s.theory != null || s.practical != null);

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#f8fafc", padding: "32px 20px 60px", fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif', color: "#0f172a" }}>
      <div style={{ maxWidth: "1060px", margin: "0 auto" }}>

        {/* TOP BAR / BREADCRUMB */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
              <span style={{ fontSize: "11px", fontWeight: "700", letterSpacing: "1px", textTransform: "uppercase", backgroundColor: "#e2e8f0", color: "#334155", padding: "3px 8px", borderRadius: "4px" }}>
                DeepTrust Nexus
              </span>
              <span style={{ fontSize: "13px", color: "#64748b" }}>Academic Credential Verification System</span>
            </div>
            <h1 style={{ fontSize: "28px", fontWeight: "800", color: "#0f172a", margin: 0, letterSpacing: "-0.5px" }}>
              Marksheet Verification Dashboard
            </h1>
          </div>
          <div style={{ display: "flex", gap: "10px" }}>
            <button
              onClick={() => navigate("/upload")}
              style={{
                padding: "10px 18px",
                backgroundColor: "#0f172a",
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: "600",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <span>+</span> Verify Another Marksheet
            </button>
            <button
              onClick={() => navigate("/dashboard")}
              style={{
                padding: "10px 18px",
                backgroundColor: "#ffffff",
                color: "#334155",
                border: "1px solid #cbd5e1",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: "600",
              }}
            >
              Dashboard
            </button>
          </div>
        </div>

        {/* 1. OVERALL CERTIFICATE VERIFICATION STATUS (HERO BANNER) */}
        <div
          style={{
            backgroundColor: statusTheme.bg,
            border: `2px solid ${statusTheme.border}`,
            borderRadius: "14px",
            padding: "26px 30px",
            marginBottom: "24px",
            boxShadow: "0 6px 18px rgba(0,0,0,0.03)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: "16px" }}>
              <span style={{ fontSize: "40px", lineHeight: "1" }}>{statusTheme.icon}</span>
              <div>
                <div style={{ fontSize: "12px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.8px", color: statusTheme.color, marginBottom: "4px" }}>
                  Verification Outcome Assessment
                </div>
                <h2 style={{ margin: "0 0 6px", fontSize: "24px", color: statusTheme.color, fontWeight: "800", letterSpacing: "-0.3px" }}>
                  {statusTheme.title}
                </h2>
                <p style={{ margin: 0, fontSize: "15px", color: "#1e293b", lineHeight: "1.5", fontWeight: "500", maxWidth: "760px" }}>
                  {verification.summary || statusTheme.subtitle}
                </p>
              </div>
            </div>
            <span
              style={{
                padding: "8px 18px",
                borderRadius: "24px",
                fontSize: "14px",
                fontWeight: "800",
                letterSpacing: "0.5px",
                backgroundColor: statusTheme.badgeBg,
                color: statusTheme.badgeColor,
                border: `1.5px solid ${statusTheme.border}`,
                boxShadow: "0 2px 6px rgba(0,0,0,0.04)",
              }}
            >
              {status}
            </span>
          </div>

          {/* Potential Tampering / AI Generation Alert when QR is unauthenticatable */}
          {isQrUnauthenticatable && (
            <div
              style={{
                marginTop: "18px",
                padding: "14px 18px",
                backgroundColor: "#fff7ed",
                border: "1.5px solid #f97316",
                borderRadius: "10px",
                display: "flex",
                alignItems: "center",
                gap: "14px",
                boxShadow: "0 2px 6px rgba(249, 115, 22, 0.08)",
              }}
            >
              <span style={{ fontSize: "26px", flexShrink: 0 }}>⚠️</span>
              <div style={{ color: "#9a3412", fontSize: "14px", lineHeight: "1.5" }}>
                <strong style={{ fontSize: "15px", display: "block", marginBottom: "2px", color: "#c2410c" }}>
                  Potential Tampering / AI Generation Detected:
                </strong>
                A QR pattern was detected on this certificate, but it is <strong>not authenticatable</strong> (unreadable or synthetic bitstream). AI-generated certificates and forged credentials frequently incorporate decorative, pseudo-random QR patterns that fail standard decoding. <em>This certificate may be tampered or artificially generated.</em>
              </div>
            </div>
          )}

          <div style={{ marginTop: "16px", paddingTop: "14px", borderTop: "1px solid rgba(0,0,0,0.08)", fontSize: "13px", color: "#475569", lineHeight: "1.5", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
            <div>
              <strong>Evaluation Engine Note:</strong> {verification.explanation || "All available cryptographic, QR, optical, and forensic evidence sources have been cross-evaluated."}
            </div>
            <div style={{ fontSize: "12px", color: "#64748b", backgroundColor: "rgba(255,255,255,0.7)", padding: "4px 10px", borderRadius: "6px" }}>
              Offline rule-based evidence decision (no probabilistic hallucination)
            </div>
          </div>
        </div>

        {/* 2. CANDIDATE & CREDENTIAL SUMMARY GRID */}
        <div
          style={{
            backgroundColor: "#ffffff",
            borderRadius: "14px",
            border: "1px solid #e2e8f0",
            padding: "24px",
            marginBottom: "24px",
            boxShadow: "0 2px 8px rgba(0,0,0,0.02)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px", borderBottom: "1px solid #f1f5f9", paddingBottom: "12px" }}>
            <div>
              <h3 style={{ margin: 0, fontSize: "17px", fontWeight: "700", color: "#0f172a", display: "flex", alignItems: "center", gap: "8px" }}>
                <span>👤</span> Candidate &amp; Credential Overview
              </h3>
              <p style={{ margin: "2px 0 0", fontSize: "13px", color: "#64748b" }}>
                Key student identifiers extracted from certificate scan
              </p>
            </div>
            {documentMetadata && (
              <span style={{ fontSize: "12px", color: "#475569", backgroundColor: "#f1f5f9", padding: "4px 10px", borderRadius: "6px", fontWeight: "600" }}>
                {documentMetadata.format} · Page {documentMetadata.primary_page_analyzed || 1} of {documentMetadata.page_count}
              </span>
            )}
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
              gap: "16px",
            }}
          >
            {/* Field 1: Candidate Name */}
            <div style={{ backgroundColor: "#f8fafc", borderRadius: "10px", padding: "16px", border: "1px solid #e2e8f0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "11px", fontWeight: "700", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.5px" }}>Candidate Name</span>
                <span style={{ fontSize: "11px", fontWeight: "700", padding: "2px 8px", borderRadius: "10px", backgroundColor: candidateNameStatus.bg, color: candidateNameStatus.color, border: `1px solid ${candidateNameStatus.border}` }}>
                  {candidateNameStatus.status}
                </span>
              </div>
              <div style={{ fontSize: "18px", fontWeight: "700", color: candidateNameValue === "Not detected" || candidateNameValue === "Not reliably read" ? "#92400e" : "#0f172a", marginBottom: "4px" }}>
                {candidateNameValue}
              </div>
              {candidateNameRaw && (
                <div style={{ fontSize: "12px", color: "#64748b", fontStyle: "italic", marginBottom: "4px" }}>
                  Raw OCR text: &ldquo;{candidateNameRaw}&rdquo; ({Math.round((extractedFields.candidate_name_confidence || 0) * 100)}% conf)
                </div>
              )}
              <div style={{ fontSize: "12px", color: "#64748b" }}>
                {nameSourceNote()}
              </div>
            </div>

            {/* Field 2: Registration Number */}
            <div style={{ backgroundColor: "#f8fafc", borderRadius: "10px", padding: "16px", border: "1px solid #e2e8f0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "11px", fontWeight: "700", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.5px" }}>Permanent Registration No</span>
                <span style={{ fontSize: "11px", fontWeight: "700", padding: "2px 8px", borderRadius: "10px", backgroundColor: regNoStatus.bg, color: regNoStatus.color, border: `1px solid ${regNoStatus.border}` }}>
                  {regNoStatus.status}
                </span>
              </div>
              <div style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a", marginBottom: "4px" }}>
                {extractedFields.registration_number || "Not detected"}
              </div>
              <div style={{ fontSize: "12px", color: "#64748b" }}>
                {extractedFields.registration_number
                  ? REG_SOURCES[extractedFields.registration_source] || (confPct("registration_number") ? `Read by OCR (${confPct("registration_number")})` : "Read by OCR")
                  : "Permanent registration number not identified"}
              </div>
            </div>

            {/* Field 3: Certificate / Serial Number */}
            <div style={{ backgroundColor: "#f8fafc", borderRadius: "10px", padding: "16px", border: "1px solid #e2e8f0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "11px", fontWeight: "700", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.5px" }}>Certificate Serial No</span>
                <span style={{ fontSize: "11px", fontWeight: "700", padding: "2px 8px", borderRadius: "10px", backgroundColor: certNoStatus.bg, color: certNoStatus.color, border: `1px solid ${certNoStatus.border}` }}>
                  {certNoStatus.status}
                </span>
              </div>
              <div style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a", marginBottom: "4px" }}>
                {extractedFields.certificate_number || "Not detected"}
              </div>
              <div style={{ fontSize: "12px", color: "#64748b" }}>
                {extractedFields.certificate_number
                  ? CERT_SOURCES[extractedFields.certificate_number_source] || (confPct("certificate_number") ? `Read by OCR (${confPct("certificate_number")})` : "Read by OCR")
                  : "Serial identifier not detected"}
              </div>
            </div>

            {/* Field 4: Course / Class */}
            <div style={{ backgroundColor: "#f8fafc", borderRadius: "10px", padding: "16px", border: "1px solid #e2e8f0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "11px", fontWeight: "700", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.5px" }}>Course / Qualification</span>
                <span style={{ fontSize: "11px", fontWeight: "700", padding: "2px 8px", borderRadius: "10px", backgroundColor: "#f1f5f9", color: "#475569", border: "1px solid #cbd5e1" }}>
                  {extractedFields.course ? "Document OCR" : "User Input"}
                </span>
              </div>
              <div style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a", marginBottom: "4px" }}>
                {extractedFields.course || (userInputs.classType ? `Class ${userInputs.classType}th` : "Not specified")}
              </div>
              <div style={{ fontSize: "12px", color: "#64748b" }}>
                {extractedFields.course ? "Extracted from examination header" : "Specified during upload session"}
              </div>
            </div>

            {/* Field 5: Examination Session / Year */}
            <div style={{ backgroundColor: "#f8fafc", borderRadius: "10px", padding: "16px", border: "1px solid #e2e8f0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "11px", fontWeight: "700", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.5px" }}>Examination Session</span>
                <span style={{ fontSize: "11px", fontWeight: "700", padding: "2px 8px", borderRadius: "10px", backgroundColor: "#f1f5f9", color: "#475569", border: "1px solid #cbd5e1" }}>
                  {extractedFields.examination_year ? "Detected" : "Not Found"}
                </span>
              </div>
              <div style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a", marginBottom: "4px" }}>
                {extractedFields.examination_year || "Not detected"}
              </div>
              <div style={{ fontSize: "12px", color: "#64748b" }}>
                {extractedFields.board || userInputs.board || "State Board / Examination Authority"}
              </div>
            </div>

            {/* Field 6: Recorded Total Marks */}
            <div style={{ backgroundColor: "#f8fafc", borderRadius: "10px", padding: "16px", border: "1px solid #e2e8f0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "11px", fontWeight: "700", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.5px" }}>Total Marks Recorded</span>
                <span style={{ fontSize: "11px", fontWeight: "700", padding: "2px 8px", borderRadius: "10px", backgroundColor: totalMarksStatus.bg, color: totalMarksStatus.color, border: `1px solid ${totalMarksStatus.border}` }}>
                  {totalMarksStatus.status}
                </span>
              </div>
              <div style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a", marginBottom: "4px" }}>
                {extractedFields.total_marks || "Not detected"}
                {extractedFields.total_marks_in_words != null && (
                  <span style={{ fontSize: "13px", fontWeight: "500", color: "#64748b", marginLeft: "8px" }}>
                    ({extractedFields.total_marks_in_words} in words)
                  </span>
                )}
              </div>
              <div style={{ fontSize: "12px", color: "#64748b" }}>
                {extractedFields.total_marks_conflict
                  ? `Conflict: numeric '${extractedFields.total_marks_conflict.numeric}' vs words '${extractedFields.total_marks_conflict.in_words}'`
                  : extractedFields.total_marks_source === "CALCULATED_SUBJECT_SUM"
                  ? (extractedFields.total_marks_note || "Calculated sum of verified subject marks (CBSE grading scheme)")
                  : confPct("total_marks")
                  ? `Read from total label (${confPct("total_marks")})`
                  : "Stated marks summary on document"}
              </div>
            </div>
          </div>

          {/* Additional Identifiers (Roll number or EMIS if detected) */}
          {(extractedFields.roll_number || extractedFields.emis_id) && (
            <div style={{ marginTop: "14px", paddingTop: "12px", borderTop: "1px solid #f1f5f9", display: "flex", gap: "16px", flexWrap: "wrap", fontSize: "12px", color: "#64748b" }}>
              {extractedFields.roll_number && (
                <span><strong>Roll Number:</strong> {extractedFields.roll_number} (Exam seat)</span>
              )}
              {extractedFields.emis_id && (
                <span><strong>EMIS ID:</strong> {extractedFields.emis_id} (Student management ID, excluded from reg no)</span>
              )}
            </div>
          )}
        </div>

        {/* 3. SUBJECT-WISE MARKS & ARITHMETIC CONSISTENCY CARD */}
        <div
          style={{
            backgroundColor: "#ffffff",
            borderRadius: "14px",
            border: "1px solid #e2e8f0",
            padding: "24px",
            marginBottom: "24px",
            boxShadow: "0 2px 8px rgba(0,0,0,0.02)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
            <div>
              <h3 style={{ margin: 0, fontSize: "17px", fontWeight: "700", color: "#0f172a", display: "flex", alignItems: "center", gap: "8px" }}>
                <span>📊</span> Subject-Wise Marks &amp; Summation Verification
              </h3>
              <p style={{ margin: "2px 0 0", fontSize: "13px", color: "#64748b" }}>
                Cross-verification of individual extracted subject scores against recorded certificate total
              </p>
            </div>
            {subjects.length > 0 && (
              <span style={{ fontSize: "12px", fontWeight: "700", padding: "4px 10px", borderRadius: "6px", backgroundColor: "#f1f5f9", color: "#334155" }}>
                {subjects.length} Subjects Extracted
              </span>
            )}
          </div>

          {/* Arithmetic Consistency Banner */}
          {arithmetic.performed ? (
            <div
              style={{
                padding: "14px 18px",
                borderRadius: "10px",
                marginBottom: "18px",
                display: "flex",
                alignItems: "center",
                gap: "12px",
                backgroundColor: arithmetic.consistent ? "#ecfdf5" : "#fef2f2",
                border: `1.5px solid ${arithmetic.consistent ? "#a7f3d0" : "#fecaca"}`,
                color: arithmetic.consistent ? "#065f46" : "#991b1b",
              }}
            >
              <span style={{ fontSize: "22px" }}>{arithmetic.consistent ? "✅" : "⚠️"}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: "700", fontSize: "14px", marginBottom: "2px" }}>
                  {arithmetic.consistent ? "Arithmetic Verified: Subject Sum Matches Stated Total" : "Arithmetic Discrepancy Detected"}
                </div>
                <div style={{ fontSize: "13px", lineHeight: "1.4" }}>
                  {arithmetic.details || `Calculated Sum: ${arithmetic.calculated_sum} | Stated Total: ${arithmetic.recorded_total}`}
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "11px", textTransform: "uppercase", fontWeight: "700", opacity: 0.8 }}>Difference</div>
                <div style={{ fontSize: "18px", fontWeight: "800" }}>{arithmetic.difference === 0 ? "0" : `${arithmetic.difference > 0 ? "+" : ""}${arithmetic.difference}`}</div>
              </div>
            </div>
          ) : (
            <div
              style={{
                padding: "12px 16px",
                borderRadius: "10px",
                marginBottom: "18px",
                backgroundColor: "#f8fafc",
                border: "1px solid #e2e8f0",
                color: "#475569",
                fontSize: "13px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <span style={{ fontSize: "18px" }}>ℹ️</span>
              <div>
                <strong>Arithmetic check not applicable:</strong> {arithmetic.details || "Direct summation was not performed (grading scheme or unconfirmed recorded total)."}
              </div>
            </div>
          )}

          {/* Subject Marks Table */}
          {subjects.length > 0 ? (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px", textAlign: "left" }}>
                <thead>
                  <tr style={{ backgroundColor: "#f8fafc", borderBottom: "2px solid #e2e8f0", color: "#475569" }}>
                    <th style={{ padding: "12px 14px", fontWeight: "700" }}>Subject</th>
                    {hasTheoryOrPractical && (
                      <th style={{ padding: "12px 14px", fontWeight: "700" }}>Theory</th>
                    )}
                    {hasTheoryOrPractical && (
                      <th style={{ padding: "12px 14px", fontWeight: "700" }}>Practical</th>
                    )}
                    <th style={{ padding: "12px 14px", fontWeight: "700" }}>Marks Obtained</th>
                    <th style={{ padding: "12px 14px", fontWeight: "700" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {subjects.map((sub, idx) => (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: "1px solid #f1f5f9",
                        backgroundColor: idx % 2 === 0 ? "#ffffff" : "#fafbfc",
                      }}
                    >
                      <td style={{ padding: "12px 14px", fontWeight: "600", color: "#0f172a" }}>
                        {sub.subject}
                      </td>
                      {hasTheoryOrPractical && (
                        <td style={{ padding: "12px 14px", color: "#334155" }}>
                          {sub.theory != null ? sub.theory : "—"}
                        </td>
                      )}
                      {hasTheoryOrPractical && (
                        <td style={{ padding: "12px 14px", color: "#334155" }}>
                          {sub.practical != null ? sub.practical : "—"}
                        </td>
                      )}
                      <td style={{ padding: "12px 14px", fontWeight: "700", color: "#0f172a" }}>
                        {sub.marks}
                      </td>
                      <td style={{ padding: "12px 14px" }}>
                        <span style={{ fontSize: "11px", fontWeight: "700", padding: "3px 8px", borderRadius: "10px", backgroundColor: "#ecfdf5", color: "#065f46", border: "1px solid #a7f3d0" }}>
                          Extracted
                        </span>
                      </td>
                    </tr>
                  ))}
                  {/* Total Summary Row */}
                  <tr style={{ backgroundColor: "#f8fafc", borderTop: "2px solid #cbd5e1", fontWeight: "700" }}>
                    <td style={{ padding: "12px 14px", color: "#0f172a" }}>
                      Calculated Total Sum
                    </td>
                    {hasTheoryOrPractical && <td style={{ padding: "12px 14px" }}>—</td>}
                    {hasTheoryOrPractical && <td style={{ padding: "12px 14px" }}>—</td>}
                    <td style={{ padding: "12px 14px", fontSize: "16px", color: "#0f172a" }}>
                      {arithmetic.calculated_sum != null ? arithmetic.calculated_sum : subjects.reduce((acc, s) => acc + (s.marks || 0), 0)}
                    </td>
                    <td style={{ padding: "12px 14px", fontSize: "12px", color: "#475569" }}>
                      Recorded Total: {extractedFields.total_marks || "—"}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: "20px", textAlign: "center", backgroundColor: "#f8fafc", borderRadius: "8px", border: "1px dashed #cbd5e1", color: "#64748b", fontSize: "13px" }}>
              No individual tabular subject breakdown was detected on this document scan. Direct arithmetic check skipped.
            </div>
          )}
        </div>

        {/* 4. FOUR CORE VERIFICATION EVIDENCE PILLARS */}
        <div style={{ marginBottom: "24px" }}>
          <div style={{ marginBottom: "12px" }}>
            <h3 style={{ margin: "0 0 4px", fontSize: "17px", fontWeight: "700", color: "#0f172a" }}>
              Multi-Layer Verification Evidence
            </h3>
            <p style={{ margin: 0, fontSize: "13px", color: "#64748b" }}>
              Four independent verification mechanisms cross-evaluated for this document
            </p>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
              gap: "16px",
            }}
          >
            {/* Pillar 1: OCR Extraction Quality */}
            <div style={{ backgroundColor: "#ffffff", borderRadius: "12px", border: "1px solid #e2e8f0", padding: "20px", display: "flex", flexDirection: "column", justifyContent: "space-between", boxShadow: "0 2px 6px rgba(0,0,0,0.02)" }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <span style={{ fontSize: "11px", fontWeight: "700", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.5px" }}>Optical OCR Quality</span>
                  <span style={{ fontSize: "11px", fontWeight: "700", padding: "2px 8px", borderRadius: "10px", backgroundColor: ocrConfidenceText !== "Unavailable" && parseFloat(ocrConfidenceText) >= 45 ? "#eff6ff" : "#fffbeb", color: ocrConfidenceText !== "Unavailable" && parseFloat(ocrConfidenceText) >= 45 ? "#1d4ed8" : "#92400e", border: `1px solid ${ocrConfidenceText !== "Unavailable" && parseFloat(ocrConfidenceText) >= 45 ? "#bfdbfe" : "#fde68a"}` }}>
                    {ocrConfidenceText !== "Unavailable" && parseFloat(ocrConfidenceText) >= 45 ? "Legible Scan" : "Low OCR Conf"}
                  </span>
                </div>
                <div style={{ fontSize: "28px", fontWeight: "800", color: "#0f172a", marginBottom: "6px" }}>
                  {ocrConfidenceText}
                </div>
                <p style={{ fontSize: "13px", color: "#475569", lineHeight: "1.45", margin: "0 0 10px" }}>
                  Character-weighted legibility across {ocrMetrics.totalBoxes || 0} detected text boxes.
                </p>
              </div>
              <div style={{ fontSize: "11px", color: "#64748b", borderTop: "1px solid #f1f5f9", paddingTop: "8px" }}>
                🔒 OCR confidence measures visual legibility, not certificate genuineness.
              </div>
            </div>

            {/* Pillar 2: QR Code Analysis */}
            <div style={{ backgroundColor: "#ffffff", borderRadius: "12px", border: "1px solid #e2e8f0", padding: "20px", display: "flex", flexDirection: "column", justifyContent: "space-between", boxShadow: "0 2px 6px rgba(0,0,0,0.02)" }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <span style={{ fontSize: "11px", fontWeight: "700", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.5px" }}>QR Code Analysis</span>
                  <span style={{ fontSize: "11px", fontWeight: "700", padding: "2px 8px", borderRadius: "10px", backgroundColor: qrDisplayState.badgeBg, color: qrDisplayState.badgeColor, border: `1px solid ${qrDisplayState.badgeColor}33` }}>
                    {qrDisplayState.badge}
                  </span>
                </div>
                <div style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a", marginBottom: "6px" }}>
                  {qrDisplayState.title}
                </div>
                <p style={{ fontSize: "13px", color: "#475569", lineHeight: "1.45", margin: "0 0 10px" }}>
                  {qrDisplayState.note}
                </p>
              </div>
              <div style={{ fontSize: "11px", color: isQrUnauthenticatable ? "#c2410c" : "#64748b", borderTop: "1px solid #f1f5f9", paddingTop: "8px", fontWeight: isQrUnauthenticatable ? "600" : "normal" }}>
                {isQrUnauthenticatable ? "⚠️ Unauthenticatable QR pattern: Certificate may be tampered or artificially generated." : "📱 Decoded URLs are external web links; not verified credentials without signature."}
              </div>
            </div>

            {/* Pillar 3: Digital Signature */}
            <div style={{ backgroundColor: "#ffffff", borderRadius: "12px", border: "1px solid #e2e8f0", padding: "20px", display: "flex", flexDirection: "column", justifyContent: "space-between", boxShadow: "0 2px 6px rgba(0,0,0,0.02)" }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <span style={{ fontSize: "11px", fontWeight: "700", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.5px" }}>
                    {sigV?.state === "PHYSICAL_SIGNATURE_DETECTED" ? "Board Signatory" : "Digital Signature"}
                  </span>
                  <span style={{ fontSize: "11px", fontWeight: "700", padding: "2px 8px", borderRadius: "10px", backgroundColor: sigBadgeTheme.bg, color: sigBadgeTheme.color, border: `1px solid ${sigBadgeTheme.border}` }}>
                    {sigLabel}
                  </span>
                </div>
                <div style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a", marginBottom: "6px" }}>
                  {sigV?.state === "PHYSICAL_SIGNATURE_DETECTED"
                    ? "Official Board Signatory"
                    : digitalSignature?.present
                    ? (digitalSignature.isTestKey ? "Synthetic Test Signature" : "Cryptographic Signature")
                    : "No Digital Signature"}
                </div>
                <p style={{ fontSize: "13px", color: "#475569", lineHeight: "1.45", margin: "0 0 10px" }}>
                  {sigV?.explanation || digitalSignature?.reason || "Physical marksheet does not carry an offline-verifiable digital signature."}
                </p>
              </div>
              <div style={{ fontSize: "11px", color: sigV?.state === "PHYSICAL_SIGNATURE_DETECTED" ? "#047857" : "#64748b", borderTop: "1px solid #f1f5f9", paddingTop: "8px", fontWeight: sigV?.state === "PHYSICAL_SIGNATURE_DETECTED" ? "600" : "normal" }}>
                {sigV?.state === "PHYSICAL_SIGNATURE_DETECTED"
                  ? "🔏 Official board signatory verified. Standard physical paper marksheet issuance."
                  : "🔏 Printed signatures and rubber stamps are visual, not cryptographic signatures."}
              </div>
            </div>

            {/* Pillar 4: Document Integrity & Forensics */}
            <div style={{ backgroundColor: "#ffffff", borderRadius: "12px", border: "1px solid #e2e8f0", padding: "20px", display: "flex", flexDirection: "column", justifyContent: "space-between", boxShadow: "0 2px 6px rgba(0,0,0,0.02)" }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <span style={{ fontSize: "11px", fontWeight: "700", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.5px" }}>Visual Forensics</span>
                  <span style={{ fontSize: "11px", fontWeight: "700", padding: "2px 8px", borderRadius: "10px", backgroundColor: (tamperAnalysis?.indicators_detected?.length || 0) > 0 ? "#fffbeb" : isQrUnauthenticatable ? "#fff7ed" : "#ecfdf5", color: (tamperAnalysis?.indicators_detected?.length || 0) > 0 ? "#92400e" : isQrUnauthenticatable ? "#c2410c" : "#065f46", border: `1px solid ${(tamperAnalysis?.indicators_detected?.length || 0) > 0 ? "#fde68a" : isQrUnauthenticatable ? "#fed7aa" : "#a7f3d0"}` }}>
                    {(tamperAnalysis?.indicators_detected?.length || 0) > 0 ? `${tamperAnalysis.indicators_detected.length} Anomaly Flag(s)` : isQrUnauthenticatable ? "Potential Tampering Flag" : "Clean"}
                  </span>
                </div>
                <div style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a", marginBottom: "6px" }}>
                  {(tamperAnalysis?.indicators_detected?.length || 0) > 0 ? "Tampering Flags Detected" : isQrUnauthenticatable ? "Potential Tampering Indicator" : "No Visual Anomalies"}
                </div>
                <p style={{ fontSize: "13px", color: "#475569", lineHeight: "1.45", margin: "0 0 10px" }}>
                  {(tamperAnalysis?.indicators_detected?.length || 0) > 0
                    ? tamperAnalysis?.forensic_summary
                    : isQrUnauthenticatable
                    ? "Unauthenticatable QR pattern detected on document. AI-generated certificates and fraudulent documents frequently incorporate non-standard, decorative QR patterns; document may be tampered."
                    : tamperAnalysis?.forensic_summary || "Multi-angle compression (ELA) and layout consistency verified."}
                </p>
              </div>
              <div style={{ fontSize: "11px", color: isQrUnauthenticatable ? "#c2410c" : "#64748b", borderTop: "1px solid #f1f5f9", paddingTop: "8px", fontWeight: isQrUnauthenticatable ? "600" : "normal" }}>
                {isQrUnauthenticatable ? "🔍 Unauthenticatable QR detected: Certificate may be tampered." : "🔍 Image compression artifacts alone are not presented as proof of forgery."}
              </div>
            </div>
          </div>
        </div>

        {/* 5. COLLAPSIBLE ADVANCED TECHNICAL DIAGNOSTICS */}
        <div style={{ marginTop: "20px", marginBottom: "30px" }}>
          <button
            onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
            style={{
              width: "100%",
              padding: "14px 20px",
              backgroundColor: "#ffffff",
              color: "#334155",
              border: "1px solid #cbd5e1",
              borderRadius: "10px",
              fontSize: "14px",
              fontWeight: "600",
              cursor: "pointer",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              boxShadow: "0 2px 4px rgba(0,0,0,0.02)",
            }}
          >
            <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span>🔬</span> Advanced Technical Diagnostics &amp; Pipeline Data
            </span>
            <span style={{ fontSize: "13px", color: "#64748b" }}>
              {showTechnicalDetails ? "▲ Hide Diagnostics" : "▼ Expand Diagnostics"}
            </span>
          </button>

          {showTechnicalDetails && (
            <div
              style={{
                marginTop: "12px",
                padding: "24px",
                backgroundColor: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: "10px",
                boxShadow: "0 4px 12px rgba(0,0,0,0.03)",
              }}
            >
              {/* Ground-Truth Accuracy Benchmark */}
              <div style={{ marginBottom: "20px", paddingBottom: "16px", borderBottom: "1px solid #f1f5f9" }}>
                <h4 style={{ margin: "0 0 8px", fontSize: "13px", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.5px" }}>
                  Ground-Truth Extraction Accuracy
                </h4>
                <div style={{ fontSize: "13px", color: "#334155", lineHeight: "1.5" }}>
                  {extractionAccuracy?.measured ? (
                    <div>
                      <strong>Accuracy:</strong> {extractionAccuracy.accuracyPercentage} ({extractionAccuracy.matchedCount} of {extractionAccuracy.comparedCount} fields matched against {extractionAccuracy.groundTruthSource})
                    </div>
                  ) : (
                    <div>
                      <strong>Notice:</strong> Ground-truth reference data is unconfigured for this document; true extraction accuracy cannot be measured without verified reference records.
                    </div>
                  )}
                </div>
              </div>

              {/* Ingestion Metadata */}
              {documentMetadata && (
                <div style={{ marginBottom: "20px", paddingBottom: "16px", borderBottom: "1px solid #f1f5f9" }}>
                  <h4 style={{ margin: "0 0 8px", fontSize: "13px", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.5px" }}>
                    Document Ingestion Metadata
                  </h4>
                  <div style={{ fontSize: "13px", color: "#334155", lineHeight: "1.6" }}>
                    <div><strong>Format:</strong> {documentMetadata.format}</div>
                    <div><strong>Page Count:</strong> {documentMetadata.page_count}</div>
                    <div><strong>Primary Page Analyzed:</strong> Page {documentMetadata.primary_page_analyzed || 1}</div>
                    {documentMetadata.pdf_signature_markers && (
                      <div><strong>PDF Signature Structure:</strong> {documentMetadata.pdf_signature_markers.detected ? "Detected (Not cryptographically validated)" : "Not detected"}</div>
                    )}
                    {documentMetadata.multi_page_note && (
                      <div style={{ marginTop: "4px", color: "#64748b" }}>ℹ️ {documentMetadata.multi_page_note}</div>
                    )}
                  </div>
                </div>
              )}

              {/* EasyOCR Raw Pipeline Information */}
              <div style={{ marginBottom: "20px", paddingBottom: "16px", borderBottom: "1px solid #f1f5f9" }}>
                <h4 style={{ margin: "0 0 8px", fontSize: "13px", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.5px" }}>
                  OCR Pipeline Diagnostics
                </h4>
                <div style={{ fontSize: "13px", color: "#475569", lineHeight: "1.6" }}>
                  <div><strong>Engine:</strong> EasyOCR; Preprocessing variants: {(ocrMetrics.variantsUsed || ["not reported"]).join(", ")}</div>
                  <div><strong>Languages Requested:</strong> {(ocrMetrics.languagesRequested || ["en"]).join("+")}; <strong>Active:</strong> {(ocrMetrics.languagesActive || ["en"]).join("+")}</div>
                  {ocrMetrics.languageNote && <div style={{ color: "#b45309" }}>⚠️ {ocrMetrics.languageNote}</div>}
                  <div><strong>Total text boxes detected:</strong> {ocrMetrics.totalBoxes || 0}</div>
                  <div><strong>Confidence aggregation method:</strong> {ocrMetrics.aggregationMethod || "Text-weighted character confidence"}</div>
                  {data.ocrDiagnostics?.name_region && (
                    <div>
                      <strong>Name region re-read:</strong>{" "}
                      {data.ocrDiagnostics.name_region.attempted
                        ? `label ${data.ocrDiagnostics.name_region.label_match}; best ${
                            data.ocrDiagnostics.name_region.best
                              ? `${data.ocrDiagnostics.name_region.best.name} (${Math.round(data.ocrDiagnostics.name_region.best.confidence * 100)}%, ${data.ocrDiagnostics.name_region.best.agreement} pass(es) agree)`
                              : "none"
                          }`
                        : `skipped (${data.ocrDiagnostics.name_region.reason})`}
                    </div>
                  )}
                </div>
              </div>

              {/* QR and Signature Technical Notes */}
              {(qrV || sigV || qrAnalysis?.raw_payload_preview) && (
                <div style={{ marginBottom: "20px", paddingBottom: "16px", borderBottom: "1px solid #f1f5f9" }}>
                  <h4 style={{ margin: "0 0 8px", fontSize: "13px", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.5px" }}>
                    QR &amp; Cryptographic Technical Details
                  </h4>
                  <div style={{ fontSize: "13px", color: "#475569", lineHeight: "1.6" }}>
                    {qrAnalysis?.raw_payload_preview && (
                      <div style={{ wordBreak: "break-all", marginBottom: "8px" }}>
                        <strong>QR Raw Payload Preview (safe sanitized text, never fetched):</strong><br />
                        <code style={{ backgroundColor: "#f1f5f9", padding: "4px 8px", borderRadius: "4px", fontSize: "12px", display: "inline-block", marginTop: "4px" }}>
                          {qrAnalysis.raw_payload_preview}
                        </code>
                      </div>
                    )}
                    {qrV?.technicalNotes?.map((n, i) => (
                      <div key={`qn${i}`}>• {n}</div>
                    ))}
                    {digitalSignature?.evidence?.map((ev, i) => (
                      <div key={`se${i}`}>• {ev}</div>
                    ))}
                  </div>
                </div>
              )}

              {/* Developer Test Fixture Reference (if any) */}
              {demoFixture && (
                <div style={{ backgroundColor: "#f8fafc", borderRadius: "8px", padding: "12px 16px", border: "1px dashed #cbd5e1", fontSize: "13px", color: "#475569", lineHeight: "1.5" }}>
                  ℹ️ <strong>Demo Test Fixture Reference:</strong> Certificate matches a local developer baseline fixture (Record #{demoFixture.record.certificate_number}: {demoFixture.record.candidate_name}). <em>This comparison is against developer testing fixtures only, and is kept separate from OCR extraction.</em>
                </div>
              )}
            </div>
          )}
        </div>

        {/* BOTTOM ACTION BUTTONS */}
        <div style={{ display: "flex", gap: "14px" }}>
          <button
            onClick={() => navigate("/upload")}
            style={{
              flex: 1,
              padding: "14px",
              backgroundColor: "#0f172a",
              color: "#ffffff",
              border: "none",
              borderRadius: "10px",
              fontWeight: "700",
              fontSize: "15px",
              cursor: "pointer",
            }}
          >
            Verify Another Marksheet
          </button>
          <button
            onClick={() => navigate("/dashboard")}
            style={{
              flex: 1,
              padding: "14px",
              backgroundColor: "#ffffff",
              color: "#0f172a",
              border: "1px solid #cbd5e1",
              borderRadius: "10px",
              fontWeight: "700",
              fontSize: "15px",
              cursor: "pointer",
            }}
          >
            Back to Dashboard
          </button>
        </div>

      </div>
    </div>
  );
}

export default Result;