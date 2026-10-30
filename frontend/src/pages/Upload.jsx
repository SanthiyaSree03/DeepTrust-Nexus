import { useState } from "react";
import { useNavigate } from "react-router-dom";

function Upload() {
  const navigate = useNavigate();

  const [file, setFile] = useState(null);
  const [classType, setClassType] = useState("");
  const [board, setBoard] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleFileChange = (event) => {
    const selectedFile = event.target.files[0];
    setErrorMessage("");

    if (selectedFile) {
      const allowedExtensions = [".jpg", ".jpeg", ".png", ".pdf"];
      const fileNameLower = selectedFile.name.toLowerCase();
      const isValidExt = allowedExtensions.some((ext) => fileNameLower.endsWith(ext));

      if (!isValidExt) {
        setErrorMessage("Unsupported file format. Please upload a JPG, JPEG, PNG, or PDF marksheet.");
        setFile(null);
        event.target.value = "";
        return;
      }

      const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB
      if (selectedFile.size > MAX_FILE_SIZE) {
        setErrorMessage("File size exceeds 25 MB limit. Please upload a document smaller than 25 MB.");
        setFile(null);
        event.target.value = "";
        return;
      }

      setFile(selectedFile);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setErrorMessage("");

    if (!file || !classType || !board) {
      setErrorMessage("Please select a class, board, and marksheet document.");
      return;
    }

    const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB
    if (file.size > MAX_FILE_SIZE) {
      setErrorMessage("File size exceeds 25 MB limit. Please upload a document smaller than 25 MB.");
      return;
    }

    const formData = new FormData();
    formData.append("marksheet", file);
    formData.append("classType", classType);
    formData.append("board", board);

    setIsLoading(true);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 180000);

    try {
      const response = await fetch("http://localhost:5000/api/verify", {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Verification failed. Please check the uploaded document.");
      }

      // Navigate to results screen with real verification data
      navigate("/result", {
        state: {
          verificationData: data,
          userInputs: { classType, board },
        },
      });
    } catch (err) {
      clearTimeout(timeoutId);
      console.error("Upload error:", err);
      if (err.name === "AbortError") {
        setErrorMessage("Verification timed out (>85s). The image took too long to process on CPU. Please upload a clear, standard-resolution image.");
      } else {
        setErrorMessage(err.message || "Failed to connect to backend server. Ensure backend is running on port 5000.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="upload-page">
      <div className="upload-container">
        <h1>Verify Marksheet</h1>

        <p>
          Upload your 10th or 12th marksheet for AI OCR scanning &amp; authoritative verification.
        </p>

        <div style={{
          fontSize: "12px",
          color: "#334155",
          backgroundColor: "#f1f5f9",
          padding: "8px 12px",
          borderRadius: "6px",
          marginBottom: "18px",
          borderLeft: "3px solid #2563eb",
          lineHeight: "1.5"
        }}>
          ℹ️ <strong>Permitted Documents:</strong> Only <strong>10th Standard (SSLC)</strong> and <strong>12th Standard (HSC)</strong> marksheets can be processed. Other documents (e.g., Aadhaar cards, PAN cards, college degrees, bills, random images) are automatically rejected.
        </div>

        {errorMessage && (
          <div
            style={{
              padding: "12px 16px",
              marginBottom: "16px",
              backgroundColor: "#fef2f2",
              border: "1px solid #f87171",
              borderRadius: "8px",
              color: "#b91c1c",
              fontSize: "14px",
            }}
          >
            ⚠️ {errorMessage}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <label>Class</label>

          <select
            value={classType}
            onChange={(event) => setClassType(event.target.value)}
            disabled={isLoading}
          >
            <option value="">Select Class</option>
            <option value="10">10th Standard (SSLC)</option>
            <option value="12">12th Standard (HSC)</option>
          </select>

          <label>Board</label>

          <select
            value={board}
            onChange={(event) => setBoard(event.target.value)}
            disabled={isLoading}
          >
            <option value="">Select Board</option>
            <option value="State Board">State Board</option>
            <option value="CBSE">CBSE</option>
            <option value="CISCE">CISCE / ICSE</option>
            <option value="Other">Other Board</option>
          </select>

          <label>Marksheet (JPG, JPEG, PNG, PDF)</label>

          <input
            type="file"
            accept=".jpg,.jpeg,.png,.pdf,image/png,image/jpeg,application/pdf"
            onChange={handleFileChange}
            disabled={isLoading}
          />

          <button type="submit" disabled={isLoading} style={{ cursor: isLoading ? "not-allowed" : "pointer", opacity: isLoading ? 0.7 : 1 }}>
            {isLoading ? "Scanning & Verifying Marksheet..." : "Verify Marksheet"}
          </button>
        </form>

        {isLoading && (
          <div style={{ textAlign: "center", marginTop: "20px", color: "#4b5563" }}>
            <p style={{ margin: "4px 0", fontWeight: "600" }}>⏳ Scanning &amp; Verifying Marksheet...</p>
            <small style={{ color: "#64748b" }}>Normalizing resolution, extracting marks &amp; verifying QR evidence (~10-20 seconds on CPU).</small>
          </div>
        )}
      </div>
    </div>
  );
}

export default Upload;