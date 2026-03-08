import { useAuth } from "../hooks/useAuth";

export function ProtectedRoute({ children, fallback = null }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return fallback;
  }

  return children;
}
