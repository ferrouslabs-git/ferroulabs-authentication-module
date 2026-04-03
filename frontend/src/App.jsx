import { Link, Navigate, Route, Routes } from "react-router-dom";
import { AUTH_CONFIG, useAuth } from "./auth_usermanagement";
import { LoginPage } from "./mockapp/growthgorilla/pages/LoginPage";
import { OnboardingPage } from "./mockapp/growthgorilla/pages/OnboardingPage";
import { PurchasePage } from "./mockapp/growthgorilla/pages/PurchasePage";
import { SignupPage } from "./mockapp/growthgorilla/pages/SignupPage";
import { SplashPage } from "./mockapp/growthgorilla/pages/SplashPage";
import { WheelPage } from "./mockapp/growthgorilla/pages/WheelPage";
import { FlowEntryPage } from "./mockapp/growthgorilla/pages/FlowEntryPage";

function AppShell({ children }) {
  const { isAuthenticated, logout } = useAuth();

  return (
    <div style={styles.frame}>
      <header style={styles.header}>
        <div style={styles.brand}>GrowthGorilla POC</div>
        <nav style={styles.nav}>
          <Link style={styles.navLink} to="/">Home</Link>
          <Link style={styles.navLink} to="/normal">Normal Route</Link>
          <Link style={styles.navLink} to="/splash">Splash Route</Link>
          <Link style={styles.navLink} to="/splash/S1">Splash</Link>
          <Link style={styles.navLink} to="/wheel">Wheel</Link>
          <Link style={styles.navLink} to="/signup">Signup</Link>
          {isAuthenticated ? (
            <button style={styles.signOutButton} onClick={logout}>Sign out</button>
          ) : null}
        </nav>
      </header>

      <main style={styles.main}>{children}</main>
    </div>
  );
}

function CallbackPage() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isAuthenticated) {
    return <Navigate to="/purchase" replace />;
  }

  return (
    <div style={styles.callbackCard}>
      <p style={styles.callbackKicker}>Completing sign-in</p>
      <h2 style={styles.callbackTitle}>Please wait...</h2>
      <p style={styles.callbackBody}>{isLoading ? "Exchanging tokens and restoring session." : "Redirecting..."}</p>
    </div>
  );
}

function HomeRoute() {
  return <FlowEntryPage />;
}

function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<HomeRoute />} />
        <Route path="/normal" element={<Navigate to="/login" replace />} />
        <Route path="/splash" element={<Navigate to="/splash/S1" replace />} />
        <Route path="/splash/:splashId" element={<SplashPage />} />
        <Route path="/wheel" element={<WheelPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/purchase" element={<PurchasePage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/dashboard" element={<Navigate to="/onboarding" replace />} />
        <Route path={AUTH_CONFIG.callbackPath} element={<CallbackPage />} />
        <Route path="*" element={<Navigate to="/splash/S1" replace />} />
      </Routes>
    </AppShell>
  );
}

const styles = {
  frame: {
    minHeight: "100vh",
    background: "radial-gradient(circle at 5% 5%, #d9f4ef, #edf5ff 40%, #fff4e8 100%)",
    fontFamily: '"Segoe UI", Tahoma, sans-serif',
  },
  header: {
    position: "sticky",
    top: 0,
    zIndex: 10,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "12px 18px",
    borderBottom: "1px solid #d8e6ee",
    background: "rgba(255, 255, 255, 0.88)",
    backdropFilter: "blur(8px)",
  },
  brand: {
    fontWeight: 800,
    color: "#103247",
    letterSpacing: "0.02em",
  },
  nav: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    flexWrap: "wrap",
  },
  navLink: {
    color: "#1d5a72",
    fontWeight: 700,
    textDecoration: "none",
  },
  signOutButton: {
    border: "none",
    borderRadius: 8,
    padding: "7px 10px",
    background: "#f2f6f8",
    color: "#35515e",
    fontWeight: 700,
    cursor: "pointer",
  },
  main: {
    paddingBottom: 30,
  },
  callbackCard: {
    maxWidth: 560,
    margin: "72px auto 0",
    borderRadius: 16,
    border: "1px solid #d8e6ee",
    background: "#fff",
    padding: 24,
  },
  callbackKicker: {
    margin: 0,
    color: "#1f6a84",
    fontWeight: 700,
    textTransform: "uppercase",
    fontSize: 12,
    letterSpacing: "0.08em",
  },
  callbackTitle: {
    marginTop: 8,
    marginBottom: 8,
    color: "#143244",
  },
  callbackBody: {
    margin: 0,
    color: "#3c5a69",
  },
};

export default App;
