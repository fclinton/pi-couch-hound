import { lazy, Suspense, useState } from "react";
import { cn } from "@/lib/utils";
import { useConfig } from "@/api/config";

const CameraTab = lazy(() => import("@/components/settings/CameraTab"));
const DetectionTab = lazy(() => import("@/components/settings/DetectionTab"));
const RoiTab = lazy(() => import("@/components/settings/RoiTab"));
const ActionsTab = lazy(() => import("@/components/settings/ActionsTab"));
const EscalationTab = lazy(() => import("@/components/settings/EscalationTab"));
const CooldownTab = lazy(() => import("@/components/settings/CooldownTab"));
const SystemTab = lazy(() => import("@/components/settings/SystemTab"));

const tabs = ["Camera", "Detection", "ROI", "Actions", "Escalation", "Cooldown", "System"] as const;
type Tab = (typeof tabs)[number];

export default function Settings() {
  const [activeTab, setActiveTab] = useState<Tab>("Camera");
  const { data: config, isLoading, error } = useConfig();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      <div className="-mx-4 border-b border-gray-200 md:mx-0">
        <nav className="-mb-px flex space-x-4 overflow-x-auto px-4 scrollbar-none sm:space-x-6 md:px-0">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "min-h-[44px] shrink-0 border-b-2 px-1 text-sm font-medium transition-colors",
                activeTab === tab
                  ? "border-brand-500 text-brand-600"
                  : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700",
              )}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-6">
        {isLoading && (
          <p className="text-sm text-gray-500">Loading configuration...</p>
        )}
        {error && (
          <p className="text-sm text-red-600">
            Failed to load configuration: {error.message}
          </p>
        )}
        {config && (
          <Suspense
            fallback={
              <p className="text-sm text-gray-500">Loading...</p>
            }
          >
            {activeTab === "Camera" && <CameraTab config={config} />}
            {activeTab === "Detection" && <DetectionTab config={config} />}
            {activeTab === "ROI" && <RoiTab config={config} />}
            {activeTab === "Actions" && <ActionsTab config={config} />}
            {activeTab === "Escalation" && <EscalationTab config={config} />}
            {activeTab === "Cooldown" && <CooldownTab config={config} />}
            {activeTab === "System" && <SystemTab config={config} />}
          </Suspense>
        )}
      </div>
    </div>
  );
}
