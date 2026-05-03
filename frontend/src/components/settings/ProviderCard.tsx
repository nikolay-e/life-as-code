import type { ReactNode } from "react";
import type { UseMutationResult } from "@tanstack/react-query";
import { Button } from "../ui/button";
import { Spinner } from "../ui/spinner";
import {
  CheckCircle,
  XCircle,
  RefreshCw,
  ExternalLink,
  AlertCircle,
  Pencil,
  Trash2,
} from "lucide-react";
import type { BackoffSourceStatus, SyncResponse } from "../../types/api";

interface ProviderCardProps {
  readonly name: string;
  readonly shortName: string;
  readonly colorClass: string;
  readonly isConfigured: boolean;
  readonly isConnected?: boolean;
  readonly isTokenExpired?: boolean;
  readonly syncMutation: UseMutationResult<SyncResponse, Error, void>;
  readonly onSync: () => void;
  readonly authUrl?: string;
  readonly showOAuthNotConfigured?: boolean;
  readonly isLastItem?: boolean;
  readonly credentialHint?: string | null;
  readonly onEdit?: () => void;
  readonly onDisconnect?: () => void;
  readonly isDisconnecting?: boolean;
  readonly isEditing?: boolean;
  readonly editForm?: ReactNode;
  readonly backoffStatus?: BackoffSourceStatus;
}

function getStatusText(
  isConfigured: boolean,
  isConnected?: boolean,
  isTokenExpired?: boolean,
  backoffStatus?: BackoffSourceStatus,
): string {
  if (backoffStatus?.status === "exhausted") {
    return "Sync failed — manual retry required";
  }
  if (backoffStatus?.status === "retrying") {
    return `Sync issues — retrying in ${String(backoffStatus.backoff_minutes)}m`;
  }
  if (isTokenExpired) {
    return "Token expired";
  }
  if (isConnected !== undefined) {
    return isConnected ? "Connected" : "Not connected";
  }
  return isConfigured ? "Connected" : "Not configured";
}

interface SyncButtonProps {
  readonly name: string;
  readonly isPending: boolean;
  readonly onClick: () => void;
  readonly disabled?: boolean;
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
  readonly name: string;
  readonly shortName: string;
  readonly colorClass: string;
  readonly hasData?: boolean;
  readonly statusText?: string;
  readonly lastSyncDate?: string | null;
  readonly isLastItem?: boolean;
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
      className={`flex items-center justify-between py-4 ${isLastItem ? "" : "border-b"}`}
      aria-label={`${name} provider: ${hasData ? statusText : "No data"}`}
    >
      <div className="flex items-center gap-4">
        <div
          className={`w-10 h-10 rounded-full ${colorClass} flex items-center justify-center`}
        >
          <span
            className={`font-bold ${colorClass.replace("bg-", "text-").replace("-100", "-800").replace("-900", "-300")}`}
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
                <span className="text-green-700 dark:text-green-400">
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
  credentialHint,
  onEdit,
  onDisconnect,
  isDisconnecting,
  isEditing,
  editForm,
  backoffStatus,
}: ProviderCardProps) {
  const connected = isConnected ?? isConfigured;
  const statusText = getStatusText(
    isConfigured,
    isConnected,
    isTokenExpired,
    backoffStatus,
  );

  const renderActionButtons = () => {
    if (isTokenExpired && authUrl) {
      return (
        <a
          href={authUrl}
          aria-label={`Reconnect ${name} account`}
          className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium border border-input bg-background shadow-xs hover:bg-accent hover:text-accent-foreground h-8 px-3"
        >
          <ExternalLink className="h-4 w-4 mr-2" aria-hidden="true" />
          Reconnect
        </a>
      );
    }

    if (connected) {
      return (
        <>
          {onEdit && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onEdit}
              aria-label={`Edit ${name} credentials`}
            >
              <Pencil className="h-3.5 w-3.5 mr-1" aria-hidden="true" />
              Edit
            </Button>
          )}
          {onDisconnect && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onDisconnect}
              disabled={isDisconnecting}
              className="text-destructive hover:text-destructive"
              aria-label={`Disconnect ${name}`}
            >
              {isDisconnecting ? (
                <Spinner size="sm" className="mr-1" label="Disconnecting" />
              ) : (
                <Trash2 className="h-3.5 w-3.5 mr-1" aria-hidden="true" />
              )}
              Disconnect
            </Button>
          )}
          <SyncButton
            name={name}
            isPending={syncMutation.isPending}
            onClick={onSync}
          />
        </>
      );
    }

    if (authUrl) {
      return (
        <a
          href={authUrl}
          aria-label={`Connect ${name} account`}
          className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium border border-input bg-background shadow-xs hover:bg-accent hover:text-accent-foreground h-8 px-3"
        >
          <ExternalLink className="h-4 w-4 mr-2" aria-hidden="true" />
          Connect Account
        </a>
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

    if (!isConfigured && onEdit) {
      return (
        <Button
          variant="outline"
          size="sm"
          onClick={onEdit}
          aria-label={`Configure ${name}`}
        >
          <Pencil className="h-4 w-4 mr-2" aria-hidden="true" />
          Configure
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
    <div className={isLastItem ? "" : "border-b"}>
      <article
        className="flex items-center justify-between py-4"
        aria-label={`${name} provider status: ${statusText}`}
      >
        <div className="flex items-center gap-4">
          <div
            className={`w-10 h-10 rounded-full ${colorClass} flex items-center justify-center`}
          >
            <span
              className={`font-bold ${colorClass.replace("bg-", "text-").replace("-100", "-800").replace("-900", "-300")}`}
            >
              {shortName}
            </span>
          </div>
          <div>
            <h3 className="font-medium">{name}</h3>
            <div className="flex items-center gap-2 text-sm">
              {backoffStatus?.status === "exhausted" && (
                <>
                  <XCircle
                    className="h-4 w-4 text-red-500"
                    aria-hidden="true"
                  />
                  <span className="text-red-700 dark:text-red-400">
                    {statusText}
                  </span>
                </>
              )}
              {backoffStatus?.status === "retrying" && (
                <>
                  <AlertCircle
                    className="h-4 w-4 text-yellow-500"
                    aria-hidden="true"
                  />
                  <span className="text-yellow-700 dark:text-yellow-400">
                    {statusText}
                  </span>
                </>
              )}
              {(!backoffStatus || backoffStatus.status === "ok") &&
                isTokenExpired && (
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
              {(!backoffStatus || backoffStatus.status === "ok") &&
                !isTokenExpired &&
                connected && (
                  <>
                    <CheckCircle
                      className="h-4 w-4 text-green-500"
                      aria-hidden="true"
                    />
                    <span className="text-green-700 dark:text-green-400">
                      {statusText}
                    </span>
                  </>
                )}
              {(!backoffStatus || backoffStatus.status === "ok") &&
                !isTokenExpired &&
                !connected && (
                  <>
                    <XCircle
                      className="h-4 w-4 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <span className="text-muted-foreground">{statusText}</span>
                  </>
                )}
            </div>
            {credentialHint && (
              <p className="text-xs text-muted-foreground mt-0.5">
                {credentialHint}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">{renderActionButtons()}</div>
      </article>
      {isEditing && editForm}
    </div>
  );
}
