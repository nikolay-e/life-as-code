import type { ReactNode } from "react";
import type { UseMutationResult } from "@tanstack/react-query";
import { Button } from "../ui/button";
import { Spinner } from "../ui/spinner";
import { RefreshCw, ExternalLink, Pencil, Trash2 } from "lucide-react";
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

type StatusTone = "ok" | "warn" | "err" | "off";

interface StatusInfo {
  readonly tone: StatusTone;
  readonly text: string;
}

function getStatusInfo(
  isConfigured: boolean,
  isConnected: boolean | undefined,
  isTokenExpired: boolean | undefined,
  backoffStatus: BackoffSourceStatus | undefined,
): StatusInfo {
  if (backoffStatus?.status === "exhausted") {
    return { tone: "err", text: "Failed" };
  }
  if (backoffStatus?.status === "retrying") {
    return {
      tone: "warn",
      text: `Retry · ${String(backoffStatus.backoff_minutes)}m`,
    };
  }
  if (isTokenExpired) {
    return { tone: "warn", text: "Re-auth" };
  }
  const connected = isConnected ?? isConfigured;
  if (connected) {
    return { tone: "ok", text: "Live" };
  }
  return { tone: "off", text: "Idle" };
}

const STATUS_DOT: Record<StatusTone, string> = {
  ok: "bg-moss shadow-[0_0_0_4px_rgba(63,82,54,0.18)]",
  warn: "bg-brass shadow-[0_0_0_4px_rgba(154,115,39,0.18)]",
  err: "bg-rust shadow-[0_0_0_4px_rgba(149,68,42,0.18)]",
  off: "bg-muted-foreground/40",
};

const STATUS_TEXT: Record<StatusTone, string> = {
  ok: "text-moss",
  warn: "text-brass",
  err: "text-rust",
  off: "text-muted-foreground",
};

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
        <RefreshCw className="h-3 w-3 mr-2" aria-hidden="true" />
      )}
      Sync
    </Button>
  );
}

interface StatusPipProps {
  readonly tone: StatusTone;
  readonly text: string;
}

function StatusPip({ tone, text }: StatusPipProps) {
  return (
    <span className="inline-flex items-center gap-2 type-mono-eyebrow">
      <span
        className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[tone]}`}
        aria-hidden="true"
      />
      <span className={STATUS_TEXT[tone]}>{text}</span>
    </span>
  );
}

interface ServiceRowProps {
  readonly name: string;
  readonly meta: ReactNode;
  readonly status: ReactNode;
  readonly actions?: ReactNode;
  readonly editForm?: ReactNode;
  readonly isEditing?: boolean;
  readonly ariaLabel: string;
  readonly isLastItem?: boolean;
}

function ServiceRow({
  name,
  meta,
  status,
  actions,
  editForm,
  isEditing,
  ariaLabel,
  isLastItem,
}: ServiceRowProps) {
  return (
    <div className={isLastItem ? "" : "border-b border-border"}>
      <article
        className="grid grid-cols-1 md:grid-cols-[200px_1fr_auto] gap-4 md:gap-8 items-start md:items-center py-6"
        aria-label={ariaLabel}
      >
        <h3
          className="font-serif text-[22px] md:text-[24px] leading-none tracking-[-0.01em] italic"
          style={{
            fontVariationSettings: '"opsz" 144, "SOFT" 100',
            fontWeight: 400,
          }}
        >
          {name}
        </h3>
        <div className="flex flex-col gap-1 type-mono-eyebrow text-muted-foreground">
          {meta}
        </div>
        <div className="flex items-center gap-3 md:gap-4 flex-wrap md:justify-end">
          {status}
          {actions}
        </div>
      </article>
      {isEditing && editForm}
    </div>
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
  hasData = true,
  statusText = "Data imported",
  lastSyncDate,
  isLastItem,
}: ReadOnlyProviderCardProps) {
  const tone: StatusTone = hasData ? "ok" : "off";
  const pipText = hasData ? "Live" : "Idle";

  return (
    <ServiceRow
      name={name}
      ariaLabel={`${name} provider: ${hasData ? statusText : "No data"}`}
      isLastItem={isLastItem}
      meta={
        <>
          <span>
            <strong className="text-foreground font-medium">Source</strong> ·
            manual import
          </span>
          {lastSyncDate ? (
            <span>
              <strong className="text-foreground font-medium">
                Last import
              </strong>{" "}
              · {new Date(lastSyncDate).toLocaleDateString()}
            </span>
          ) : (
            <span>{statusText}</span>
          )}
        </>
      }
      status={<StatusPip tone={tone} text={pipText} />}
    />
  );
}

export function ProviderCard({
  name,
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
  const statusInfo = getStatusInfo(
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
          className="inline-flex items-center justify-center gap-2 whitespace-nowrap font-mono text-[11px] tracking-[0.18em] uppercase font-normal h-8 px-3 border border-border bg-background text-foreground transition-all duration-300 hover:border-primary hover:bg-secondary/40"
        >
          <ExternalLink className="h-3 w-3" aria-hidden="true" />
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
              <Pencil className="h-3 w-3 mr-2" aria-hidden="true" />
              Edit
            </Button>
          )}
          {onDisconnect && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onDisconnect}
              disabled={isDisconnecting}
              className="text-rust hover:text-rust"
              aria-label={`Disconnect ${name}`}
            >
              {isDisconnecting ? (
                <Spinner size="sm" className="mr-2" label="Disconnecting" />
              ) : (
                <Trash2 className="h-3 w-3 mr-2" aria-hidden="true" />
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
          className="inline-flex items-center justify-center gap-2 whitespace-nowrap font-mono text-[11px] tracking-[0.18em] uppercase font-normal h-8 px-3 border border-border bg-background text-foreground transition-all duration-300 hover:border-primary hover:bg-secondary/40"
        >
          <ExternalLink className="h-3 w-3" aria-hidden="true" />
          Connect
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
          OAuth missing
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
          <Pencil className="h-3 w-3 mr-2" aria-hidden="true" />
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

  const meta = connected ? (
    <>
      <span>
        <strong className="text-foreground font-medium">Status</strong> ·{" "}
        {statusInfo.tone === "warn"
          ? "attention required"
          : statusInfo.tone === "err"
            ? "manual retry required"
            : "credentials sealed · Fernet"}
      </span>
      {credentialHint && (
        <span>
          <strong className="text-foreground font-medium">Account</strong> ·{" "}
          {credentialHint}
        </span>
      )}
    </>
  ) : (
    <>
      <span>
        <strong className="text-foreground font-medium">Not configured</strong>
      </span>
      <span>
        {showOAuthNotConfigured
          ? "OAuth client missing — configure via Kubernetes secret"
          : "Add credentials to begin sync"}
      </span>
    </>
  );

  return (
    <ServiceRow
      name={name}
      ariaLabel={`${name} provider status: ${statusInfo.text}`}
      isLastItem={isLastItem}
      meta={meta}
      status={<StatusPip tone={statusInfo.tone} text={statusInfo.text} />}
      actions={renderActionButtons()}
      editForm={editForm}
      isEditing={isEditing}
    />
  );
}
