import { useState } from "react";
import { useNavigate } from "react-router-dom";

function Upload() {
  const navigate = useNavigate();

  const [file, setFile] = useState(null);
  const [classType, setClassType] = useState("");
  const [board, setBoard] = useState("");

  const handleSubmit = (event) => {
    event.preventDefault();

    if (!file || !classType || !board) {
      alert("Please complete all fields.");
      return;
    }

    // Backend connection will be added later.
    navigate("/result");
  };

  return (
    <div className="upload-page">
      <div className="upload-container">

        <h1>Verify Marksheet</h1>

        <p>
          Upload your 10th or 12th marksheet for verification.
        </p>

        <form onSubmit={handleSubmit}>

          <label>Class</label>

          <select
            value={classType}
            onChange={(event) => setClassType(event.target.value)}
          >
            <option value="">Select Class</option>
            <option value="10">10th</option>
            <option value="12">12th</option>
          </select>

          <label>Board</label>

          <select
            value={board}
            onChange={(event) => setBoard(event.target.value)}
          >
            <option value="">Select Board</option>
            <option value="CBSE">CBSE</option>
            <option value="CISCE">CISCE / ICSE</option>
            <option value="State Board">State Board</option>
            <option value="Other">Other Board</option>
          </select>

          <label>Marksheet</label>

          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            onChange={(event) => setFile(event.target.files[0])}
          />

          <button type="submit">
            Verify Marksheet
          </button>

        </form>

      </div>
    </div>
  );
}

export default Upload;