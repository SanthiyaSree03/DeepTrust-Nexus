function Result() {
  return (
    <div className="result-page">
      <div className="result-container">

        <h1>Verification Result</h1>

        <div className="result-card">

          <h2>Verification Complete</h2>

          <p>
            This is a demonstration result. The actual
            verification data will come from the backend.
          </p>

          <div className="result-details">
            <p><strong>Board:</strong> CBSE</p>
            <p><strong>Class:</strong> 12th</p>
          </div>

          <div className="verification-checks">

            <p>✓ Certificate Upload</p>
            <p>✓ OCR Processing</p>
            <p>✓ Board Identification</p>
            <p>✓ Data Verification</p>

          </div>

          <div className="score">
            <h2>Authenticity Score</h2>
            <p>92%</p>
          </div>

          <div className="status">
            VERIFIED
          </div>

        </div>

      </div>
    </div>
  );
}

export default Result;