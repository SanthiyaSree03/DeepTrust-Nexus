import { useNavigate } from "react-router-dom";

function Dashboard() {
  const navigate = useNavigate();

  return (
    <div className="dashboard-page">
      <div className="dashboard-container">

        <h1>DeepTrust Nexus</h1>

        <p>
          Welcome to the secure marksheet verification system.
        </p>

        <div className="dashboard-card">
          <h2>Verify a Marksheet</h2>

          <p>
            Upload a 10th or 12th marksheet to begin verification.
          </p>

          <button onClick={() => navigate("/upload")}>
            Upload Marksheet
          </button>
        </div>

      </div>
    </div>
  );
}

export default Dashboard;