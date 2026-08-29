import { useState } from "react";
import { useNavigate } from "react-router-dom";

function Login() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleLogin = (event) => {
    event.preventDefault();

    // For today's frontend demo only.
    // Real authentication will be handled by the backend.
    if (email && password) {
      navigate("/dashboard");
    } else {
      alert("Please enter your email and password.");
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>DeepTrust Nexus</h1>

        <p className="tagline">
          Verify Beyond the Surface
        </p>

        <p className="login-description">
          Secure 10th & 12th Marksheet Authentication
        </p>

        <form onSubmit={handleLogin}>
          <label>Email</label>

          <input
            type="email"
            placeholder="Enter your email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />

          <label>Password</label>

          <input
            type="password"
            placeholder="Enter your password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />

          <button type="submit">
            Login
          </button>
        </form>
      </div>
    </div>
  );
}

export default Login;