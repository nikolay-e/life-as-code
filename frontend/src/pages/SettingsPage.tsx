import { useCallback, useState } from "react";
import { toast } from "sonner";
import {
  useCredentials,
  useSyncGarmin,
  useSyncHevy,
  useSyncWhoop,
  useSyncEightSleep,
  useUpdateGarminCredentials,
  useUpdateHevyCredentials,
  useUpdateEightSleepCredentials,
  useDeleteGarminCredentials,
  useDeleteHevyCredentials,
  useDeleteEightSleepCredentials,
  useTestGarminCredentials,
  useTestHevyCredentials,
  useTestEightSleepCredentials,
} from "../hooks/useSettings";
import { useProfile, useUpdateProfile } from "../hooks/useProfile";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import { DateInputPicker } from "../components/ui/date-range-picker";
import { LoadingState } from "../components/ui/loading-state";
import { ErrorCard } from "../components/ui/error-card";
import { SkeletonCard } from "../components/ui/skeleton";
import {
  ProviderCard,
  ReadOnlyProviderCard,
} from "../components/settings/ProviderCard";
import { GarminCredentialForm } from "../components/settings/GarminCredentialForm";
import { HevyCredentialForm } from "../components/settings/HevyCredentialForm";
import { EightSleepCredentialForm } from "../components/settings/EightSleepCredentialForm";
import { Settings, User, Database, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { useBackoffStatus } from "../hooks/useHealthData";
import type { CredentialTestResult } from "../types/api";

type GenderValue = "" | "male" | "female";

export function SettingsPage() {
  const { data: credentials, isLoading: credentialsLoading } = useCredentials();
  const { data: backoffStatus } = useBackoffStatus();
  const syncGarmin = useSyncGarmin();
  const syncHevy = useSyncHevy();
  const syncWhoop = useSyncWhoop();
  const syncEightSleep = useSyncEightSleep();
  const updateGarmin = useUpdateGarminCredentials();
  const updateHevy = useUpdateHevyCredentials();
  const updateEightSleep = useUpdateEightSleepCredentials();
  const deleteGarmin = useDeleteGarminCredentials();
  const deleteHevy = useDeleteHevyCredentials();
  const deleteEightSleep = useDeleteEightSleepCredentials();
  const testGarmin = useTestGarminCredentials();
  const testHevy = useTestHevyCredentials();
  const testEightSleep = useTestEightSleepCredentials();

  const {
    data: profile,
    isLoading: profileLoading,
    error: profileError,
  } = useProfile();
  const updateProfile = useUpdateProfile();

  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [garminTestResult, setGarminTestResult] =
    useState<CredentialTestResult | null>(null);
  const [hevyTestResult, setHevyTestResult] =
    useState<CredentialTestResult | null>(null);
  const [eightSleepTestResult, setEightSleepTestResult] =
    useState<CredentialTestResult | null>(null);

  const initialBirthDate = profile?.birth_date ?? "";
  const initialGender = (profile?.gender as GenderValue | null) ?? "";
  const initialHeightCm = profile?.height_cm ?? null;

  const [profileEdits, setProfileEdits] = useState<{
    birthDate: string | null;
    gender: GenderValue | null;
    heightCm: number | null | undefined;
  }>({ birthDate: null, gender: null, heightCm: undefined });

  const birthDate = profileEdits.birthDate ?? initialBirthDate;
  const gender = profileEdits.gender ?? initialGender;
  const heightCm =
    profileEdits.heightCm !== undefined
      ? profileEdits.heightCm
      : initialHeightCm;
  const setBirthDate = (v: string) => {
    setProfileEdits((p) => ({ ...p, birthDate: v }));
  };
  const setGender = (v: GenderValue) => {
    setProfileEdits((p) => ({ ...p, gender: v }));
  };
  const setHeightCm = (v: number | null) => {
    setProfileEdits((p) => ({ ...p, heightCm: v }));
  };
  const isProfileDirty =
    birthDate !== initialBirthDate ||
    gender !== initialGender ||
    heightCm !== initialHeightCm;

  const handleSaveProfile = useCallback(() => {
    updateProfile.mutate(
      {
        birth_date: birthDate === "" ? null : birthDate,
        gender: gender === "" ? null : gender,
        height_cm: heightCm,
      },
      {
        onSuccess: () => {
          toast.success("Profile saved");
        },
        onError: (err) =>
          toast.error(
            err instanceof Error ? err.message : "Failed to save profile",
          ),
      },
    );
  }, [birthDate, gender, heightCm, updateProfile]);

  const handleSync = useCallback(
    async (
      provider: "garmin" | "hevy" | "whoop" | "eight_sleep",
      mutate: typeof syncGarmin,
    ) => {
      const providerNames: Record<string, string> = {
        garmin: "Garmin",
        hevy: "Hevy",
        whoop: "Whoop",
        eight_sleep: "Eight Sleep",
      };
      const providerName = providerNames[provider] ?? provider;
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
              <User className="h-4 w-4 text-primary" />
            </div>
            <div>
              <CardTitle>Profile</CardTitle>
              <CardDescription className="mt-1">
                Used to calculate biological age and longevity insights
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {(() => {
            if (profileLoading) {
              return <LoadingState message="Loading profile..." />;
            }
            if (profileError) {
              const msg =
                profileError instanceof Error
                  ? profileError.message
                  : "Failed to load profile";
              return <ErrorCard message={msg} />;
            }
            return null;
          })()}
          {!profileLoading && !profileError && (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="profile-birth-date">Birth date</Label>
                  <div className="flex items-center gap-2">
                    <DateInputPicker
                      value={birthDate}
                      onChange={(next) => {
                        setBirthDate(next);
                      }}
                      placeholder="Select birth date"
                      captionLayout="dropdown"
                      fromYear={1924}
                      toYear={new Date().getFullYear() - 10}
                    />
                    {birthDate ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setBirthDate("");
                        }}
                      >
                        Clear
                      </Button>
                    ) : null}
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="profile-gender">Gender</Label>
                  <select
                    id="profile-gender"
                    value={gender}
                    onChange={(e) => {
                      setGender(e.target.value as GenderValue);
                    }}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <option value="">Not specified</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="profile-height">Height (cm)</Label>
                  <input
                    id="profile-height"
                    type="number"
                    min={50}
                    max={300}
                    step={1}
                    value={heightCm ?? ""}
                    onChange={(e) => {
                      const v = e.target.value;
                      setHeightCm(v === "" ? null : Number(v));
                    }}
                    placeholder="e.g. 178"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                </div>
              </div>
              <div className="flex justify-end">
                <Button
                  type="button"
                  onClick={handleSaveProfile}
                  disabled={!isProfileDirty || updateProfile.isPending}
                >
                  {updateProfile.isPending ? "Saving..." : "Save"}
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

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
            backoffStatus={backoffStatus?.garmin}
            credentialHint={credentials?.garmin_email_hint}
            onEdit={() => {
              setEditingProvider("garmin");
              setGarminTestResult(null);
            }}
            onDisconnect={() => {
              if (
                // eslint-disable-next-line no-alert
                confirm(
                  "Disconnect Garmin? This will remove your saved credentials.",
                )
              ) {
                deleteGarmin.mutate(undefined, {
                  onSuccess: () => {
                    toast.success("Garmin disconnected");
                    setEditingProvider(null);
                    setGarminTestResult(null);
                  },
                  onError: (err) =>
                    toast.error(
                      err instanceof Error
                        ? err.message
                        : "Failed to disconnect Garmin",
                    ),
                });
              }
            }}
            isDisconnecting={deleteGarmin.isPending}
            isEditing={editingProvider === "garmin"}
            editForm={
              <GarminCredentialForm
                onSave={(email, password) => {
                  updateGarmin.mutate(
                    { email, password },
                    {
                      onSuccess: () => {
                        toast.success("Garmin credentials saved");
                        setEditingProvider(null);
                        setGarminTestResult(null);
                      },
                      onError: (err) => toast.error(err.message),
                    },
                  );
                }}
                onTest={(email, password) => {
                  setGarminTestResult(null);
                  testGarmin.mutate(
                    { email, password },
                    {
                      onSuccess: (result) => {
                        setGarminTestResult(result);
                      },
                      onError: () => {
                        setGarminTestResult({
                          success: false,
                          error: "Connection failed",
                        });
                      },
                    },
                  );
                }}
                onCancel={() => {
                  setEditingProvider(null);
                  setGarminTestResult(null);
                }}
                isSaving={updateGarmin.isPending}
                isTesting={testGarmin.isPending}
                testResult={garminTestResult}
              />
            }
          />
          <ProviderCard
            name="Hevy"
            shortName="H"
            colorClass="bg-purple-100 dark:bg-purple-900/30"
            isConfigured={credentials?.hevy_configured ?? false}
            syncMutation={syncHevy}
            onSync={() => handleSync("hevy", syncHevy)}
            backoffStatus={backoffStatus?.hevy}
            credentialHint={credentials?.hevy_api_key_hint}
            onEdit={() => {
              setEditingProvider("hevy");
              setHevyTestResult(null);
            }}
            onDisconnect={() => {
              if (
                // eslint-disable-next-line no-alert
                confirm("Disconnect Hevy? This will remove your saved API key.")
              ) {
                deleteHevy.mutate(undefined, {
                  onSuccess: () => {
                    toast.success("Hevy disconnected");
                    setEditingProvider(null);
                    setHevyTestResult(null);
                  },
                  onError: (err) =>
                    toast.error(
                      err instanceof Error
                        ? err.message
                        : "Failed to disconnect Hevy",
                    ),
                });
              }
            }}
            isDisconnecting={deleteHevy.isPending}
            isEditing={editingProvider === "hevy"}
            editForm={
              <HevyCredentialForm
                onSave={(apiKey) => {
                  updateHevy.mutate(
                    { apiKey },
                    {
                      onSuccess: () => {
                        toast.success("Hevy credentials saved");
                        setEditingProvider(null);
                        setHevyTestResult(null);
                      },
                      onError: (err) => toast.error(err.message),
                    },
                  );
                }}
                onTest={(apiKey) => {
                  setHevyTestResult(null);
                  testHevy.mutate(
                    { apiKey },
                    {
                      onSuccess: (result) => {
                        setHevyTestResult(result);
                      },
                      onError: () => {
                        setHevyTestResult({
                          success: false,
                          error: "Connection failed",
                        });
                      },
                    },
                  );
                }}
                onCancel={() => {
                  setEditingProvider(null);
                  setHevyTestResult(null);
                }}
                isSaving={updateHevy.isPending}
                isTesting={testHevy.isPending}
                testResult={hevyTestResult}
              />
            }
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
            backoffStatus={backoffStatus?.whoop}
          />
          <ProviderCard
            name="Eight Sleep"
            shortName="8S"
            colorClass="bg-indigo-100 dark:bg-indigo-900/30"
            isConfigured={credentials?.eight_sleep_configured ?? false}
            syncMutation={syncEightSleep}
            onSync={() => handleSync("eight_sleep", syncEightSleep)}
            backoffStatus={backoffStatus?.eight_sleep}
            credentialHint={credentials?.eight_sleep_email_hint}
            onEdit={() => {
              setEditingProvider("eight_sleep");
              setEightSleepTestResult(null);
            }}
            onDisconnect={() => {
              if (
                // eslint-disable-next-line no-alert
                confirm(
                  "Disconnect Eight Sleep? This will remove your saved credentials.",
                )
              ) {
                deleteEightSleep.mutate(undefined, {
                  onSuccess: () => {
                    toast.success("Eight Sleep disconnected");
                    setEditingProvider(null);
                    setEightSleepTestResult(null);
                  },
                  onError: (err) =>
                    toast.error(
                      err instanceof Error
                        ? err.message
                        : "Failed to disconnect Eight Sleep",
                    ),
                });
              }
            }}
            isDisconnecting={deleteEightSleep.isPending}
            isEditing={editingProvider === "eight_sleep"}
            editForm={
              <EightSleepCredentialForm
                onSave={(email, password) => {
                  updateEightSleep.mutate(
                    { email, password },
                    {
                      onSuccess: () => {
                        toast.success("Eight Sleep credentials saved");
                        setEditingProvider(null);
                        setEightSleepTestResult(null);
                      },
                      onError: (err) => toast.error(err.message),
                    },
                  );
                }}
                onTest={(email, password) => {
                  setEightSleepTestResult(null);
                  testEightSleep.mutate(
                    { email, password },
                    {
                      onSuccess: (result) => {
                        setEightSleepTestResult(result);
                      },
                      onError: () => {
                        setEightSleepTestResult({
                          success: false,
                          error: "Connection failed",
                        });
                      },
                    },
                  );
                }}
                onCancel={() => {
                  setEditingProvider(null);
                  setEightSleepTestResult(null);
                }}
                isSaving={updateEightSleep.isPending}
                isTesting={testEightSleep.isPending}
                testResult={eightSleepTestResult}
              />
            }
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

      <Link
        to="/dashboard/data-status"
        className="md:hidden flex items-center justify-between p-4 rounded-xl border bg-card hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="p-1.5 rounded-lg bg-primary/10">
            <Database className="h-4 w-4 text-primary" />
          </div>
          <div>
            <p className="font-medium text-sm">Data Status</p>
            <p className="text-xs text-muted-foreground">
              View sync status and data availability
            </p>
          </div>
        </div>
        <ChevronRight className="h-4 w-4 text-muted-foreground" />
      </Link>
    </div>
  );
}
