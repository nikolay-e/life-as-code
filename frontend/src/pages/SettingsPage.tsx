import { useCallback, useState } from "react";
import { format } from "date-fns";
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
import { SkeletonCard } from "../components/ui/skeleton";
import {
  ProviderCard,
  ReadOnlyProviderCard,
} from "../components/settings/ProviderCard";
import { GarminCredentialForm } from "../components/settings/GarminCredentialForm";
import { HevyCredentialForm } from "../components/settings/HevyCredentialForm";
import { EightSleepCredentialForm } from "../components/settings/EightSleepCredentialForm";
import { useBackoffStatus } from "../hooks/useHealthData";
import { Masthead } from "../components/luxury/Masthead";
import { SectionHead, SerifEm } from "../components/luxury/SectionHead";
import type { CredentialTestResult } from "../types/api";

const SETTINGS_NAV: ReadonlyArray<{ id: string; label: string }> = [
  { id: "services", label: "Connected services" },
  { id: "manual", label: "Manual imports" },
  { id: "encryption", label: "Encryption" },
];

interface AnchorNavProps {
  readonly items: ReadonlyArray<{ id: string; label: string }>;
}

function AnchorNav({ items }: AnchorNavProps) {
  return (
    <nav
      aria-label="Settings sections"
      className="flex flex-col gap-0 self-start lg:sticky lg:top-24"
    >
      {items.map((item, idx) => (
        <a
          key={item.id}
          href={`#${item.id}`}
          className={`type-mono-eyebrow text-muted-foreground hover:text-foreground hover:pl-2 transition-all duration-300 py-3.5 border-b border-border/60 ${
            idx === 0 ? "border-t border-border" : ""
          }`}
        >
          {item.label}
        </a>
      ))}
    </nav>
  );
}

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

  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [garminTestResult, setGarminTestResult] =
    useState<CredentialTestResult | null>(null);
  const [hevyTestResult, setHevyTestResult] =
    useState<CredentialTestResult | null>(null);
  const [eightSleepTestResult, setEightSleepTestResult] =
    useState<CredentialTestResult | null>(null);

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
  const todayDate = new Date();
  const dateLine = format(todayDate, "d LLLL yyyy");

  return (
    <div className="space-y-0">
      <Masthead
        leftLine="Section · Configuration"
        title={
          <>
            The <SerifEm>mechanism</SerifEm>
          </>
        }
        rightLine={dateLine}
      />

      <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-10 lg:gap-14 pt-10 lg:pt-14">
        <AnchorNav items={SETTINGS_NAV} />

        <div className="flex flex-col gap-14">
          <section id="services" className="scroll-mt-24">
            <SectionHead
              title={
                <>
                  Connected <SerifEm>services</SerifEm>
                </>
              }
              meta="credentials sealed · Fernet"
            />

            <div>
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
                    confirm(
                      "Disconnect Hevy? This will remove your saved API key.",
                    )
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
            </div>
          </section>

          <section id="manual" className="scroll-mt-24">
            <SectionHead
              title={
                <>
                  Manual <SerifEm>imports</SerifEm>
                </>
              }
              meta="file uploads · no live sync"
            />
            <div>
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
            </div>
          </section>

          <section id="encryption" className="scroll-mt-24">
            <SectionHead
              title={
                <>
                  At-rest <SerifEm>encryption</SerifEm>
                </>
              }
              meta="single-admin model"
            />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-0">
              <div className="py-5 border-t border-border md:pr-8">
                <div className="type-mono-label text-muted-foreground mb-2">
                  Cipher
                </div>
                <div
                  className="font-serif text-[18px] text-foreground"
                  style={{ fontVariationSettings: '"opsz" 14, "SOFT" 40' }}
                >
                  Fernet · per-user key
                </div>
              </div>
              <div className="py-5 border-t border-border md:pl-8 md:border-l md:border-border/60">
                <div className="type-mono-label text-muted-foreground mb-2">
                  Credential edits
                </div>
                <div
                  className="font-serif italic text-[18px] text-foreground"
                  style={{ fontVariationSettings: '"opsz" 14, "SOFT" 100' }}
                >
                  Kubernetes secrets only
                </div>
              </div>
              <div className="py-5 border-t border-border/60 md:pr-8">
                <div className="type-mono-label text-muted-foreground mb-2">
                  Token cache
                </div>
                <div className="font-mono text-[14px] tracking-[0.02em] text-foreground">
                  PVC · garminconnect
                </div>
              </div>
              <div className="py-5 border-t border-border/60 md:pl-8 md:border-l md:border-border/60">
                <div className="type-mono-label text-muted-foreground mb-2">
                  Update flow
                </div>
                <div
                  className="font-serif text-[18px] text-foreground"
                  style={{ fontVariationSettings: '"opsz" 14, "SOFT" 40' }}
                >
                  Edit secret · restart pod
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
