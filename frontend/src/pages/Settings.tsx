import { useState } from "react";
import { cn } from "@/lib/utils";
import { useConfig } from "@/api/config";
import CameraTab from "@/components/settings/CameraTab";
import DetectionTab from "@/components/settings/DetectionTab";
import RoiTab from "@/components/settings/RoiTab";
import ActionsTab from "@/components/settings/ActionsTab";
import CooldownTab from "@/components/settings/CooldownTab";
import SystemTab from "@/components/settings/SystemTab";

const tabs = ["Camera", "Detection", "ROI", "Actions", "Cooldown", "System"] as const;
type Tab = (typeof tabs)[number];

export default function Settings() {
  const [activeTab, setActiveTab] = useState<Tab>("Camera");
  const { data: config, isLoading, error } = useConfig();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-6">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "border-b-2 pb-3 text-sm font-medium transition-colors",
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
          <>
            {activeTab === "Camera" && <CameraTab config={config} />}
            {activeTab === "Detection" && <DetectionTab config={config} />}
            {activeTab === "ROI" && <RoiTab config={config} />}
            {activeTab === "Actions" && <ActionsTab config={config} />}
            {activeTab === "Cooldown" && <CooldownTab config={config} />}
            {activeTab === "System" && <SystemTab config={config} />}
          </>
        )}
      </div>
    </div>
  );
}
