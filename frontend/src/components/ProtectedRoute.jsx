import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../auth.jsx';

export default function ProtectedRoute() {
  const { token, loading } = useAuth();
  if (loading) return <div className="center-screen">Loading…</div>;
  if (!token) return <Navigate to="/login" replace />;
  return <Outlet />;
}
