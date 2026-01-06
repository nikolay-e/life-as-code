import type { UseMutationResult } from "@tanstack/react-query";
import { Button } from "../ui/button";
import { Spinner } from "../ui/spinner";
import {
  CheckCircle,
  XCircle,
  RefreshCw,
  ExternalLink,
  AlertCircle,
} from "lucide-react";
import type { SyncResponse } from "../../types/api";

interface ProviderCardProps {
  name: string;
  shortName: string;
  colorClass: string;
  isConfigured: boolean;
  isConnected?: boolean;
  isTokenExpired?: boolean;
  syncMutation: UseMutationResult<SyncResponse, Error, void>;
  onSync: () => void;
  authUrl?: string;
  showOAuthNotConfigured?: boolean;
  isLastItem?: boolean;
}

function getStatusText(
  isConfigured: boolean,
  isConnected?: boolean,
  isTokenExpired?: boolean,
): string {
  if (isTokenExpired) {
    return "Token expired";
  }
  if (isConnected !== undefined) {
    return isConnected ? "Connected" : "Not connected";
  }
  return isConfigured ? "Connected" : "Not configured";
}

interface SyncButtonProps {
  name: string;
  isPending: boolean;
  onClick: () => void;
  disabled?: boolean;
}

function SyncButton({ name, isPending, onClick, disabled }: SyncButtonProps) {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={onClick}
      disabled={disabled ?? isPending}
      aria-label={`Sync ${name}`}
    >
      {isPending ? (
        <Spinner size="sm" className="mr-2" label={`Syncing ${name}`} />
      ) : (
        <RefreshCw className="h-4 w-4 mr-2" aria-hidden="true" />
      )}
      Sync
    </Button>
  );
}

interface ReadOnlyProviderCardProps {
  name: string;
  shortName: string;
  colorClass: string;
  hasData?: boolean;
  statusText?: string;
  lastSyncDate?: string | null;
  isLastItem?: boolean;
}

export function ReadOnlyProviderCard({
  name,
  shortName,
  colorClass,
  hasData = true,
  statusText = "Data imported",
  lastSyncDate,
  isLastItem,
}: ReadOnlyProviderCardProps) {
  return (
    <article
      className={`flex items-center justify-between py-4 ${!isLastItem ? "border-b" : ""}`}
      aria-label={`${name} provider: ${hasData ? statusText : "No data"}`}
    >
      <div className="flex items-center gap-4">
        <div
          className={`w-10 h-10 rounded-full ${colorClass} flex items-center justify-center`}
        >
          <span
            className={`font-bold ${colorClass.replace("bg-", "text-").replace("-100", "-600").replace("-900", "-300")}`}
          >
            {shortName}
          </span>
        </div>
        <div>
          <h3 className="font-medium">{name}</h3>
          <div className="flex items-center gap-2 text-sm">
            {hasData ? (
              <>
                <CheckCircle
                  className="h-4 w-4 text-green-500"
                  aria-hidden="true"
                />
                <span className="text-green-600 dark:text-green-400">
                  {statusText}
                </span>
              </>
            ) : (
              <>
                <XCircle
                  className="h-4 w-4 text-muted-foreground"
                  aria-hidden="true"
                />
                <span className="text-muted-foreground">No data</span>
              </>
            )}
          </div>
        </div>
      </div>
      <div className="text-sm text-muted-foreground">
        {lastSyncDate &&
          `Last import: ${new Date(lastSyncDate).toLocaleDateString()}`}
      </div>
    </article>
  );
}

export function ProviderCard({
  name,
  shortName,
  colorClass,
  isConfigured,
  isConnected,
  isTokenExpired,
  syncMutation,
  onSync,
  authUrl,
  showOAuthNotConfigured,
  isLastItem,
}: ProviderCardProps) {
  const connected = isConnected ?? isConfigured;
  const statusText = getStatusText(isConfigured, isConnected, isTokenExpired);

  const renderActionButton = () => {
    if (isTokenExpired && authUrl) {
      return (
        <Button variant="outline" size="sm" asChild>
          <a href={authUrl} aria-label={`Reconnect ${name} account`}>
            <ExternalLink className="h-4 w-4 mr-2" aria-hidden="true" />
            Reconnect
          </a>
        </Button>
      );
    }

    if (connected) {
      return (
        <SyncButton
          name={name}
          isPending={syncMutation.isPending}
          onClick={onSync}
        />
      );
    }

    if (authUrl) {
      return (
        <Button variant="outline" size="sm" asChild>
          <a href={authUrl} aria-label={`Connect ${name} account`}>
            <ExternalLink className="h-4 w-4 mr-2" aria-hidden="true" />
            Connect Account
          </a>
        </Button>
      );
    }

    if (showOAuthNotConfigured) {
      return (
        <Button
          variant="outline"
          size="sm"
          disabled
          aria-label="OAuth not configured"
        >
          OAuth not configured
        </Button>
      );
    }

    return (
      <SyncButton
        name={name}
        isPending={syncMutation.isPending}
        onClick={onSync}
        disabled={!isConfigured}
      />
    );
  };

  return (
    <article
      className={`flex items-center justify-between py-4 ${!isLastItem ? "border-b" : ""}`}
      aria-label={`${name} provider status: ${statusText}`}
    >
      <div className="flex items-center gap-4">
        <div
          className={`w-10 h-10 rounded-full ${colorClass} flex items-center justify-center`}
        >
          <span
            className={`font-bold ${colorClass.replace("bg-", "text-").replace("-100", "-600").replace("-900", "-300")}`}
          >
            {shortName}
          </span>
        </div>
        <div>
          <h3 className="font-medium">{name}</h3>
          <div className="flex items-center gap-2 text-sm">
            {isTokenExpired && (
              <>
                <AlertCircle
                  className="h-4 w-4 text-orange-500"
                  aria-hidden="true"
                />
                <span className="text-orange-600 dark:text-orange-400">
                  {statusText}
                </span>
              </>
            )}
            {!isTokenExpired && connected && (
              <>
                <CheckCircle
                  className="h-4 w-4 text-green-500"
                  aria-hidden="true"
                />
                <span className="text-green-600 dark:text-green-400">
                  {statusText}
                </span>
              </>
            )}
            {!isTokenExpired && !connected && (
              <>
                <XCircle
                  className="h-4 w-4 text-muted-foreground"
                  aria-hidden="true"
                />
                <span className="text-muted-foreground">{statusText}</span>
              </>
            )}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-4">{renderActionButton()}</div>
    </article>
  );
}
