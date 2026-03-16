import { useLocation } from "react-router-dom";
import { useConnectionStatus, useToggleMobileMenu } from "@/stores/appStore";
import { cn } from "@/lib/utils";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/events": "Events",
  "/events/stats": "Statistics",
  "/settings": "Settings",
};

export default function Header() {
  const connected = useConnectionStatus();
  const toggle = useToggleMobileMenu();
  const location = useLocation();

  const pageTitle =
    pageTitles[location.pathname] ??
    (location.pathname.startsWith("/events/") ? "Event Detail" : "Pi Couch Hound");

  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4 md:px-6">
      <div className="flex items-center gap-3">
        {/* Hamburger - mobile only */}
        <button
          onClick={toggle}
          className="flex h-10 w-10 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-700 md:hidden"
          aria-label="Open menu"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        {/* Page title on mobile, "Pi Couch Hound" on desktop */}
        <h2 className="text-sm font-medium text-gray-500">
          <span className="md:hidden">{pageTitle}</span>
          <span className="hidden md:inline">Pi Couch Hound</span>
        </h2>
      </div>

      <div className="flex items-center gap-2">
        <span
          className={cn(
            "inline-block h-2 w-2 rounded-full",
            connected ? "bg-green-500" : "bg-red-500",
          )}
        />
        <span className="hidden text-xs text-gray-500 sm:inline">
          {connected ? "Connected" : "Disconnected"}
        </span>
      </div>
    </header>
  );
}
