import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/layout/Layout";
import Dashboard from "./pages/Dashboard";
import Events from "./pages/Events";
import EventStats from "./pages/EventStats";
import EventDetail from "./pages/EventDetail";
import Settings from "./pages/Settings";
import Login from "./pages/Login";
import { useAuthStatus } from "./api/auth";
import { useAuthStore } from "./stores/authStore";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { data, isLoading } = useAuthStatus();
  const token = useAuthStore((s) => s.token);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-sm text-gray-500">Loading...</p>
      </div>
    );
  }

  if (data?.auth_enabled && !token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/events/stats" element={<EventStats />} />
        <Route path="/events" element={<Events />} />
        <Route path="/events/:id" element={<EventDetail />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}

export default App;
