import type { ClinicalAlerts } from "../../../types/api";
import {
  Heart,
  TrendingDown,
  Scale,
  Flame,
  type LucideIcon,
} from "lucide-react";

export interface ClinicalSectionProps {
  readonly clinicalAlerts: ClinicalAlerts;
}

interface AlertItemProps {
  readonly icon: LucideIcon;
  readonly label: string;
  readonly detail: string;
  readonly tone?: "warn" | "alert";
}

function AlertItem({
  icon: Icon,
  label,
  detail,
  tone = "alert",
}: AlertItemProps) {
  const accent = tone === "warn" ? "text-brass" : "text-rust";
  return (
    <article className="flex items-start gap-4 px-6 py-6 border-l border-border first:border-l-0 first:pl-0 sm:first:pl-6 sm:first:border-l-0">
      <Icon className={`h-4 w-4 mt-0.5 ${accent}`} />
      <div className="flex flex-col gap-1.5">
        <span
          className={`font-serif text-[18px] leading-none tracking-[-0.01em] ${accent}`}
          style={{
            fontVariationSettings: '"opsz" 144, "SOFT" 100',
            fontStyle: "italic",
            fontWeight: 400,
          }}
        >
          {label}
        </span>
        <span className="type-mono-label text-muted-foreground normal-case tracking-wide">
          {detail}
        </span>
      </div>
    </article>
  );
}

export function ClinicalSection({ clinicalAlerts }: ClinicalSectionProps) {
  if (!clinicalAlerts.any_alert) return null;
  return (
    <div className="border border-rust/40 bg-rust/[0.04] grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 divide-y sm:divide-y-0 divide-border">
      {clinicalAlerts.persistent_tachycardia && (
        <AlertItem
          icon={Heart}
          label="Elevated RHR"
          detail={`${String(clinicalAlerts.tachycardia_days)} consecutive days above baseline +2σ`}
        />
      )}
      {clinicalAlerts.acute_hrv_drop && (
        <AlertItem
          icon={TrendingDown}
          label="Acute HRV drop"
          detail={`${
            clinicalAlerts.hrv_drop_percent == null
              ? "—"
              : `${(clinicalAlerts.hrv_drop_percent * 100).toFixed(0)}%`
          } drop from previous day`}
        />
      )}
      {clinicalAlerts.progressive_weight_loss && (
        <AlertItem
          icon={Scale}
          tone="warn"
          label="Weight loss"
          detail={`${
            clinicalAlerts.weight_loss_percent == null
              ? "—"
              : `${(clinicalAlerts.weight_loss_percent * 100).toFixed(1)}%`
          } loss over 30 days`}
        />
      )}
      {clinicalAlerts.severe_overtraining && (
        <AlertItem
          icon={Flame}
          label="Overtraining risk"
          detail="High ACWR + suppressed HRV detected"
        />
      )}
    </div>
  );
}
