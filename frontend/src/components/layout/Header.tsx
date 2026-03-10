import { useConnectionStatus } from "@/stores/appStore";

export default function Header() {
  const connected = useConnectionStatus();

  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6">
      <h2 className="text-sm font-medium text-gray-500">Pi Couch Hound</h2>
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "inline-block h-2 w-2 rounded-full",
            connected ? "bg-green-500" : "bg-red-500",
          )}
        />
        <span className="text-xs text-gray-500">
          {connected ? "Connected" : "Disconnected"}
        </span>
      </div>
    </header>
  );
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}
