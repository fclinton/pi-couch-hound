import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Header from "./Header";
import MobileDrawer from "./MobileDrawer";

export default function Layout() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <MobileDrawer />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
