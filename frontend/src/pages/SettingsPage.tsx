import { useCallback } from "react";
import { toast } from "sonner";
import {
  useCredentials,
  useSyncGarmin,
  useSyncHevy,
  useSyncWhoop,
} from "../hooks/useSettings";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { SkeletonCard } from "../components/ui/skeleton";
import {
  ProviderCard,
  ReadOnlyProviderCard,
} from "../components/settings/ProviderCard";
import { Settings } from "lucide-react";

export function SettingsPage() {
  const { data: credentials, isLoading: credentialsLoading } = useCredentials();
  const syncGarmin = useSyncGarmin();
  const syncHevy = useSyncHevy();
  const syncWhoop = useSyncWhoop();

  const handleSync = useCallback(
    async (
      provider: "garmin" | "hevy" | "whoop",
      mutate: typeof syncGarmin,
    ) => {
      const providerName = provider.charAt(0).toUpperCase() + provider.slice(1);
      const toastId = toast.loading(`Syncing ${providerName}...`);

      try {
        const result = await mutate.mutateAsync();
        toast.success(result.message || `${providerName} sync completed`, {
          id: toastId,
        });
      } catch (error) {
        toast.error(
          error instanceof Error
            ? error.message
            : `${providerName} sync failed`,
          { id: toastId },
        );
      }
    },
    [],
  );

  if (credentialsLoading) {
    return (
      <output className="space-y-6 block" aria-label="Loading settings">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </output>
    );
  }

  const whoopAuthUrl = credentials?.whoop_auth_url;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Manage your data sources and sync configuration
        </p>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-primary/10">
              <Settings className="h-4 w-4 text-primary" />
            </div>
            <div>
              <CardTitle>Data Sources</CardTitle>
              <CardDescription className="mt-1">
                Connect and sync your health data from various providers
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-1">
          <ProviderCard
            name="Garmin Connect"
            shortName="G"
            colorClass="bg-blue-100 dark:bg-blue-900/30"
            isConfigured={credentials?.garmin_configured ?? false}
            syncMutation={syncGarmin}
            onSync={() => handleSync("garmin", syncGarmin)}
          />
          <ProviderCard
            name="Hevy"
            shortName="H"
            colorClass="bg-purple-100 dark:bg-purple-900/30"
            isConfigured={credentials?.hevy_configured ?? false}
            syncMutation={syncHevy}
            onSync={() => handleSync("hevy", syncHevy)}
          />
          <ProviderCard
            name="Whoop"
            shortName="W"
            colorClass="bg-orange-100 dark:bg-orange-900/30"
            isConfigured={credentials?.whoop_configured ?? false}
            isConnected={credentials?.whoop_configured}
            isTokenExpired={credentials?.whoop_token_expired ?? false}
            syncMutation={syncWhoop}
            onSync={() => handleSync("whoop", syncWhoop)}
            authUrl={whoopAuthUrl}
            showOAuthNotConfigured={!whoopAuthUrl}
          />
          <ReadOnlyProviderCard
            name="Google Fit"
            shortName="GF"
            colorClass="bg-green-100 dark:bg-green-900/30"
            hasData={true}
            statusText="Manually imported"
          />
          <ReadOnlyProviderCard
            name="Apple Health"
            shortName="AH"
            colorClass="bg-red-100 dark:bg-red-900/30"
            hasData={true}
            statusText="Manually imported"
            isLastItem
          />
        </CardContent>
      </Card>
    </div>
  );
}
