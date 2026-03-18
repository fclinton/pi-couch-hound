import { useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useMobileMenuOpen, useSetMobileMenuOpen } from "@/stores/appStore";

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/events", label: "Events" },
  { to: "/events/stats", label: "Statistics" },
  { to: "/logs", label: "Logs" },
  { to: "/settings", label: "Settings" },
];

export default function MobileDrawer() {
  const open = useMobileMenuOpen();
  const setOpen = useSetMobileMenuOpen();
  const location = useLocation();

  // Close drawer on route change
  useEffect(() => {
    setOpen(false);
  }, [location.pathname, setOpen]);

  // Prevent body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <div className={cn("fixed inset-0 z-40 md:hidden", !open && "pointer-events-none")}>
      {/* Backdrop */}
      <div
        className={cn(
          "absolute inset-0 bg-black/50 transition-opacity duration-300",
          open ? "opacity-100" : "opacity-0",
        )}
        onClick={() => setOpen(false)}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <aside
        className={cn(
          "absolute inset-y-0 left-0 flex w-64 flex-col bg-white shadow-xl transition-transform duration-300 ease-in-out",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* Drawer header */}
        <div className="flex h-14 items-center justify-between border-b border-gray-200 px-4">
          <span className="text-lg font-bold text-brand-600">Couch Hound</span>
          <button
            onClick={() => setOpen(false)}
            className="flex h-10 w-10 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            aria-label="Close menu"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Nav links */}
        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex min-h-[44px] items-center rounded-md px-3 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-brand-50 text-brand-700"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
    </div>
  );
}
