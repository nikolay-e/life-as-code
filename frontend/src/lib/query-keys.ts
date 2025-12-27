export const healthKeys = {
  all: ["health"] as const,
  data: () => [...healthKeys.all, "data"] as const,
  dataRange: (start: string, end: string) =>
    [...healthKeys.data(), start, end] as const,
  sync: () => [...healthKeys.all, "sync"] as const,
  syncStatus: () => [...healthKeys.sync(), "status"] as const,
};

export const settingsKeys = {
  all: ["settings"] as const,
  thresholds: () => [...settingsKeys.all, "thresholds"] as const,
  credentials: () => [...settingsKeys.all, "credentials"] as const,
};
