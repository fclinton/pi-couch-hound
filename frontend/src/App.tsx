import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/layout/Layout";
import { useAuthStatus } from "./api/auth";
import { useAuthStore } from "./stores/authStore";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Events = lazy(() => import("./pages/Events"));
const EventStats = lazy(() => import("./pages/EventStats"));
const EventDetail = lazy(() => import("./pages/EventDetail"));
const Training = lazy(() => import("./pages/Training"));
const Settings = lazy(() => import("./pages/Settings"));
const Logs = lazy(() => import("./pages/Logs"));
const Login = lazy(() => import("./pages/Login"));
const Setup = lazy(() => import("./pages/Setup"));

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

  if (data?.setup_required) {
    return <Navigate to="/setup" replace />;
  }

  // Fail closed: if the status check is enabled-and-unauthenticated, or it
  // failed to load at all (data undefined), require login rather than exposing
  // the protected UI.
  if (!data || (data.auth_enabled && !token)) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function RedirectIfSetupDone({ children }: { children: React.ReactNode }) {
  const { data, isLoading } = useAuthStatus();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-sm text-gray-500">Loading...</p>
      </div>
    );
  }

  if (data && !data.setup_required) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}

const Loading = () => (
  <div className="flex h-screen items-center justify-center">
    <p className="text-sm text-gray-500">Loading...</p>
  </div>
);

function App() {
  return (
    <Suspense fallback={<Loading />}>
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/setup"
        element={
          <RedirectIfSetupDone>
            <Setup />
          </RedirectIfSetupDone>
        }
      />
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
        <Route path="/training" element={<Training />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/logs" element={<Logs />} />
      </Route>
    </Routes>
    </Suspense>
  );
}

export default App;
