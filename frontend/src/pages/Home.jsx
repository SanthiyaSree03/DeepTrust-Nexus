import { useNavigate } from "react-router-dom";

function Home() {
  const navigate = useNavigate();

  return (
    <div className="login-page">
      <div className="login-card" style={{ textAlign: "center", padding: "50px 40px" }}>
        {/* Shield Security Icon */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: "80px",
            height: "80px",
            borderRadius: "50%",
            backgroundColor: "#eff6ff",
            color: "#1d4ed8",
            marginBottom: "20px",
            boxShadow: "0 4px 12px rgba(29, 78, 216, 0.12)",
          }}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="44"
            height="44"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.5 3.8 17 5 19 5a1 1 0 0 1 1 1z" />
            <path d="m9 12 2 2 4-4" />
          </svg>
        </div>

        {/* Project Name & Subtitle */}
        <div
          style={{
            display: "inline-block",
            fontSize: "13px",
            fontWeight: "700",
            letterSpacing: "1.2px",
            textTransform: "uppercase",
            color: "#2563eb",
            backgroundColor: "#dbeafe",
            padding: "4px 12px",
            borderRadius: "20px",
            marginBottom: "12px",
          }}
        >
          DeepTrust Nexus
        </div>

        <h1 style={{ fontSize: "34px", fontWeight: "800", color: "#0f172a", marginBottom: "14px", lineHeight: "1.25" }}>
          Verify Certificates. Build Trust.
        </h1>

        <p
          style={{
            fontSize: "16px",
            color: "#475569",
            lineHeight: "1.65",
            maxWidth: "540px",
            margin: "0 auto 30px auto",
          }}
        >
          An AI-assisted document authentication platform that uses advanced optical character recognition (OCR)
          and intelligent image preprocessing to extract marksheet details and cross-reference them against trusted baseline records.
        </p>

        {/* Primary Call to Action Button */}
        <div>
          <button
            onClick={() => navigate("/upload")}
            style={{
              padding: "15px 34px",
              fontSize: "16px",
              fontWeight: "700",
              borderRadius: "10px",
              backgroundColor: "#1e293b",
              color: "#ffffff",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "10px",
              boxShadow: "0 6px 18px rgba(15, 23, 42, 0.2)",
              transition: "all 0.2s ease",
            }}
          >
            <span>Verify a Certificate</span>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </button>
        </div>

        {/* Feature Highlights */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
            gap: "14px",
            marginTop: "40px",
            paddingTop: "30px",
            borderTop: "1px solid #f1f5f9",
            textAlign: "left",
          }}
        >
          <div style={{ padding: "12px", backgroundColor: "#f8fafc", borderRadius: "8px" }}>
            <div style={{ fontWeight: "700", fontSize: "14px", color: "#1e293b", marginBottom: "4px" }}>
              🔍 EasyOCR Analysis
            </div>
            <div style={{ fontSize: "12px", color: "#64748b", lineHeight: "1.4" }}>
              2x CLAHE upscaling for character clarity on scans.
            </div>
          </div>

          <div style={{ padding: "12px", backgroundColor: "#f8fafc", borderRadius: "8px" }}>
            <div style={{ fontWeight: "700", fontSize: "14px", color: "#1e293b", marginBottom: "4px" }}>
              ⚖️ Weighted Match Score
            </div>
            <div style={{ fontSize: "12px", color: "#64748b", lineHeight: "1.4" }}>
              Scores serial number, candidate, marks, and board.
            </div>
          </div>

          <div style={{ padding: "12px", backgroundColor: "#f8fafc", borderRadius: "8px" }}>
            <div style={{ fontWeight: "700", fontSize: "14px", color: "#1e293b", marginBottom: "4px" }}>
              🏛️ Reference Verification
            </div>
            <div style={{ fontSize: "12px", color: "#64748b", lineHeight: "1.4" }}>
              Authenticates against authoritative baseline records.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Home;
