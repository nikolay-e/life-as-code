import { useState, useEffect } from "react";
import {
  useSettings,
  useSaveSettings,
  useCredentials,
  useSaveCredentials,
  useSyncStatus,
  useTriggerSync,
} from "@/hooks/useSettings";

export default function SettingsPage() {
  return (
    <div className="space-y-8 max-w-4xl">
      <h2 className="text-2xl font-bold text-gray-900">Settings</h2>
      <CredentialsSection />
      <ThresholdsSection />
      <SyncSection />
    </div>
  );
}

function CredentialsSection() {
  const { data: credentials, isLoading } = useCredentials();
  const saveCredentials = useSaveCredentials();
  const [garminEmail, setGarminEmail] = useState("");
  const [garminPassword, setGarminPassword] = useState("");
  const [hevyApiKey, setHevyApiKey] = useState("");

  useEffect(() => {
    if (credentials) {
      setGarminEmail(credentials.garmin_email || "");
      setHevyApiKey(credentials.hevy_api_key || "");
    }
  }, [credentials]);

  const handleSave = () => {
    saveCredentials.mutate({
      garmin_email: garminEmail,
      garmin_password: garminPassword || undefined,
      hevy_api_key: hevyApiKey,
    });
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 animate-pulse h-48" />
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        API Credentials
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Garmin Email
          </label>
          <input
            type="email"
            value={garminEmail}
            onChange={(e) => setGarminEmail(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
            placeholder="your@email.com"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Garmin Password
          </label>
          <input
            type="password"
            value={garminPassword}
            onChange={(e) => setGarminPassword(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
            placeholder="Leave empty to keep current"
          />
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Heavy API Key
          </label>
          <input
            type="text"
            value={hevyApiKey}
            onChange={(e) => setHevyApiKey(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
            placeholder="Your Heavy API key"
          />
        </div>
      </div>
      <div className="mt-4 flex items-center space-x-4">
        <button
          onClick={handleSave}
          disabled={saveCredentials.isPending}
          className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white font-medium rounded-lg transition-colors"
        >
          {saveCredentials.isPending ? "Saving..." : "Save Credentials"}
        </button>
        {saveCredentials.isSuccess && (
          <span className="text-green-600 text-sm">Credentials saved!</span>
        )}
        {saveCredentials.isError && (
          <span className="text-red-600 text-sm">Failed to save</span>
        )}
      </div>
    </div>
  );
}

function ThresholdsSection() {
  const { data: settings, isLoading } = useSettings();
  const saveSettings = useSaveSettings();
  const [formData, setFormData] = useState({
    hrv_good_threshold: 45,
    hrv_moderate_threshold: 35,
    deep_sleep_good_threshold: 90,
    deep_sleep_moderate_threshold: 60,
    total_sleep_good_threshold: 7.5,
    total_sleep_moderate_threshold: 6.5,
    training_high_volume_threshold: 5000,
  });

  useEffect(() => {
    if (settings) {
      setFormData(settings);
    }
  }, [settings]);

  const handleChange = (field: string, value: number) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = () => {
    saveSettings.mutate(formData);
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 animate-pulse h-64" />
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Personal Thresholds
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            HRV Good (ms)
          </label>
          <input
            type="number"
            value={formData.hrv_good_threshold}
            onChange={(e) =>
              handleChange("hrv_good_threshold", Number(e.target.value))
            }
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            HRV Moderate (ms)
          </label>
          <input
            type="number"
            value={formData.hrv_moderate_threshold}
            onChange={(e) =>
              handleChange("hrv_moderate_threshold", Number(e.target.value))
            }
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Training High Volume (kg)
          </label>
          <input
            type="number"
            value={formData.training_high_volume_threshold}
            onChange={(e) =>
              handleChange(
                "training_high_volume_threshold",
                Number(e.target.value),
              )
            }
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Deep Sleep Good (min)
          </label>
          <input
            type="number"
            value={formData.deep_sleep_good_threshold}
            onChange={(e) =>
              handleChange("deep_sleep_good_threshold", Number(e.target.value))
            }
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Deep Sleep Moderate (min)
          </label>
          <input
            type="number"
            value={formData.deep_sleep_moderate_threshold}
            onChange={(e) =>
              handleChange(
                "deep_sleep_moderate_threshold",
                Number(e.target.value),
              )
            }
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Total Sleep Good (hrs)
          </label>
          <input
            type="number"
            step="0.5"
            value={formData.total_sleep_good_threshold}
            onChange={(e) =>
              handleChange("total_sleep_good_threshold", Number(e.target.value))
            }
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
          />
        </div>
      </div>
      <div className="mt-4 flex items-center space-x-4">
        <button
          onClick={handleSave}
          disabled={saveSettings.isPending}
          className="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:bg-primary-400 text-white font-medium rounded-lg transition-colors"
        >
          {saveSettings.isPending ? "Saving..." : "Save Thresholds"}
        </button>
        {saveSettings.isSuccess && (
          <span className="text-green-600 text-sm">Settings saved!</span>
        )}
      </div>
    </div>
  );
}

function SyncSection() {
  const { data: syncStatus, isLoading } = useSyncStatus();
  const triggerSync = useTriggerSync();

  const handleSync = (source: "garmin" | "heavy") => {
    triggerSync.mutate(source);
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Data Synchronization
      </h3>
      <div className="flex flex-wrap gap-4 mb-6">
        <button
          onClick={() => handleSync("garmin")}
          disabled={triggerSync.isPending}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-medium rounded-lg transition-colors"
        >
          {triggerSync.isPending ? "Syncing..." : "Sync Garmin"}
        </button>
        <button
          onClick={() => handleSync("heavy")}
          disabled={triggerSync.isPending}
          className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white font-medium rounded-lg transition-colors"
        >
          {triggerSync.isPending ? "Syncing..." : "Sync Heavy"}
        </button>
        {triggerSync.isSuccess && (
          <span className="text-green-600 text-sm self-center">
            Sync started!
          </span>
        )}
        {triggerSync.isError && (
          <span className="text-red-600 text-sm self-center">Sync failed</span>
        )}
      </div>

      {isLoading ? (
        <div className="animate-pulse h-24 bg-gray-100 rounded" />
      ) : syncStatus && syncStatus.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2 px-2 font-medium text-gray-700">
                  Source
                </th>
                <th className="text-left py-2 px-2 font-medium text-gray-700">
                  Type
                </th>
                <th className="text-left py-2 px-2 font-medium text-gray-700">
                  Last Sync
                </th>
                <th className="text-left py-2 px-2 font-medium text-gray-700">
                  Records
                </th>
                <th className="text-left py-2 px-2 font-medium text-gray-700">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {syncStatus.map((status, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="py-2 px-2 capitalize">{status.source}</td>
                  <td className="py-2 px-2 capitalize">{status.data_type}</td>
                  <td className="py-2 px-2">
                    {status.last_sync_date || "Never"}
                  </td>
                  <td className="py-2 px-2">{status.records_synced}</td>
                  <td className="py-2 px-2">
                    <span
                      className={`px-2 py-1 rounded-full text-xs ${
                        status.status === "success"
                          ? "bg-green-100 text-green-700"
                          : status.status === "error"
                            ? "bg-red-100 text-red-700"
                            : "bg-yellow-100 text-yellow-700"
                      }`}
                    >
                      {status.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-gray-500 text-sm">No sync history available</p>
      )}
    </div>
  );
}
