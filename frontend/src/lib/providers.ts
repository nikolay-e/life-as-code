// Provider Registry - Centralized provider configuration
// Add new providers here to extend the system

export type DataProvider = "garmin" | "whoop" | "hevy" | "google" | "blended";

export interface ProviderConfig {
  id: DataProvider;
  name: string;
  shortName: string;
  colorClass: string;
  bgClass: string;
  badgeColor: string;
  priority: number; // Lower = higher priority for conflict resolution
}

// Provider configurations - add new providers here
export const PROVIDER_CONFIGS: Record<DataProvider, ProviderConfig> = {
  garmin: {
    id: "garmin",
    name: "Garmin Connect",
    shortName: "G",
    colorClass: "text-blue-500",
    bgClass: "bg-blue-500/10",
    badgeColor: "#3B82F6",
    priority: 1,
  },
  whoop: {
    id: "whoop",
    name: "Whoop",
    shortName: "W",
    colorClass: "text-purple-500",
    bgClass: "bg-purple-500/10",
    badgeColor: "#A855F7",
    priority: 2,
  },
  hevy: {
    id: "hevy",
    name: "Hevy",
    shortName: "H",
    colorClass: "text-orange-500",
    bgClass: "bg-orange-500/10",
    badgeColor: "#F97316",
    priority: 3,
  },
  google: {
    id: "google",
    name: "Google Fit",
    shortName: "Gf",
    colorClass: "text-red-500",
    bgClass: "bg-red-500/10",
    badgeColor: "#EA4335",
    priority: 4,
  },
  blended: {
    id: "blended",
    name: "Blended",
    shortName: "B",
    colorClass: "text-green-500",
    bgClass: "bg-green-500/10",
    badgeColor: "#22C55E",
    priority: 0,
  },
};
