import type { LongevityInsights } from "../../../types/api";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "../../../lib/utils";
import { signPrefix, formatMetricLabel } from "./stat-utils";

function getLongevityScoreColor(score: number | null): string {
  if (score === null) return "text-muted-foreground";
  if (score >= 80) return "text-moss";
  if (score >= 60) return "text-moss";
  if (score >= 40) return "text-brass";
  if (score >= 20) return "text-rust";
  return "text-rust";
}

function getAgeDeltaColor(delta: number | null): string {
  if (delta === null) return "text-muted-foreground";
  if (delta <= -5) return "text-moss";
  if (delta <= -2) return "text-moss";
  if (delta <= 2) return "text-foreground";
  if (delta <= 5) return "text-brass";
  return "text-rust";
}

interface PanelProps {
  readonly title: string;
  readonly description?: string;
  readonly children: React.ReactNode;
}

function Panel({ title, description, children }: PanelProps) {
  return (
    <article className="border border-border bg-background flex flex-col transition-colors duration-300 hover:bg-secondary/40">
      <header className="px-5 py-4 border-b border-border flex flex-col gap-1">
        <h3
          className="font-serif text-[18px] leading-none tracking-[-0.01em]"
          style={{
            fontVariationSettings: '"opsz" 144, "SOFT" 100',
            fontStyle: "italic",
            fontWeight: 400,
          }}
        >
          {title}
        </h3>
        {description && (
          <span className="type-mono-label text-muted-foreground normal-case tracking-wide">
            {description}
          </span>
        )}
      </header>
      <div className="px-5 py-5 flex-1">{children}</div>
    </article>
  );
}

interface RowProps {
  readonly label: React.ReactNode;
  readonly value: React.ReactNode;
  readonly toneClass?: string;
}

function Row({ label, value, toneClass }: RowProps) {
  return (
    <div className="flex justify-between items-center gap-3 py-1">
      <span className="type-mono-label text-muted-foreground normal-case tracking-wide">
        {label}
      </span>
      <span
        className={cn(
          "font-mono text-[13px] tracking-tight",
          toneClass ?? "text-foreground",
        )}
        style={{ fontFeatureSettings: '"lnum","tnum"' }}
      >
        {value}
      </span>
    </div>
  );
}

export interface LongevitySectionProps {
  readonly longevityInsights: LongevityInsights;
}

export function LongevitySection({ longevityInsights }: LongevitySectionProps) {
  const { biological_age, training_zones, longevity_score } = longevityInsights;
  const overallTone = getLongevityScoreColor(longevity_score.overall);
  const ageTone = getAgeDeltaColor(biological_age.age_delta);

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      <Panel title="Longevity score" description="composite across all pillars">
        <div className="flex flex-col items-center text-center gap-1 mb-5">
          <span
            className={cn(
              "font-serif text-[clamp(56px,7vw,88px)] leading-none tracking-[-0.04em]",
              overallTone,
            )}
            style={{
              fontVariationSettings: '"opsz" 144, "SOFT" 50',
              fontWeight: 320,
              fontFeatureSettings: '"lnum","tnum"',
            }}
          >
            {longevity_score.overall == null
              ? "—"
              : longevity_score.overall.toFixed(0)}
          </span>
          <span className="type-mono-label text-muted-foreground normal-case tracking-wide">
            out of 100
          </span>
          {longevity_score.trend != null && (
            <span className="flex items-center gap-1 type-mono-label text-muted-foreground normal-case tracking-wide">
              {longevity_score.trend > 0 && (
                <TrendingUp className="h-3 w-3 text-moss" />
              )}
              {longevity_score.trend < 0 && (
                <TrendingDown className="h-3 w-3 text-rust" />
              )}
              {longevity_score.trend === 0 && (
                <Minus className="h-3 w-3 text-muted-foreground" />
              )}
              {signPrefix(longevity_score.trend)}
              {longevity_score.trend.toFixed(1)}/mo
            </span>
          )}
        </div>
        <div className="pt-3 border-t border-border flex flex-col gap-1">
          {[
            { label: "Cardio", value: longevity_score.cardiorespiratory },
            { label: "Recovery", value: longevity_score.recovery_resilience },
            { label: "Sleep", value: longevity_score.sleep_optimization },
            { label: "Body comp", value: longevity_score.body_composition },
            { label: "Activity", value: longevity_score.activity_consistency },
          ].map(({ label, value }) => (
            <Row
              key={label}
              label={label}
              value={value == null ? "—" : value.toFixed(0)}
              toneClass={getLongevityScoreColor(value)}
            />
          ))}
        </div>
      </Panel>

      <Panel title="Biological age" description="estimated vs chronological">
        <div className="flex flex-col items-center text-center gap-1 mb-5">
          <span
            className={cn(
              "font-serif text-[clamp(48px,6vw,72px)] leading-none tracking-[-0.04em]",
              ageTone,
            )}
            style={{
              fontVariationSettings: '"opsz" 144, "SOFT" 50',
              fontWeight: 320,
              fontFeatureSettings: '"lnum","tnum"',
            }}
          >
            {biological_age.composite_biological_age == null
              ? "—"
              : biological_age.composite_biological_age.toFixed(1)}
          </span>
          <span className="type-mono-label text-muted-foreground normal-case tracking-wide">
            chronological {biological_age.chronological_age}
            {biological_age.age_delta != null && (
              <span className={cn("ml-2", ageTone)}>
                ({signPrefix(biological_age.age_delta)}
                {biological_age.age_delta.toFixed(1)} yrs)
              </span>
            )}
          </span>
          {biological_age.pace_of_aging != null && (
            <span className="type-mono-label text-muted-foreground normal-case tracking-wide">
              pace ·{" "}
              <span
                className={
                  biological_age.pace_of_aging < 1 ? "text-moss" : "text-rust"
                }
              >
                {biological_age.pace_of_aging.toFixed(2)} yr/yr
              </span>
            </span>
          )}
        </div>
        <div className="pt-3 border-t border-border flex flex-col gap-1">
          {biological_age.components.map((comp) => (
            <Row
              key={comp.name}
              label={formatMetricLabel(comp.name)}
              value={
                <>
                  {comp.estimated_age == null
                    ? "—"
                    : comp.estimated_age.toFixed(1)}
                  {comp.delta != null && (
                    <span className="ml-1">
                      ({signPrefix(comp.delta)}
                      {comp.delta.toFixed(1)})
                    </span>
                  )}
                </>
              }
              toneClass={getAgeDeltaColor(comp.delta)}
            />
          ))}
        </div>
      </Panel>

      <Panel
        title="Training zones"
        description="zone 2 &amp; zone 5 distribution"
      >
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <Row
              label="Zone 2 · 7d"
              value={
                training_zones.zone2_minutes_7d == null
                  ? "—"
                  : `${String(Math.round(training_zones.zone2_minutes_7d))} min`
              }
            />
            <Row
              label="Zone 2 · 30d"
              value={
                <>
                  {training_zones.zone2_minutes_30d == null
                    ? "—"
                    : `${String(Math.round(training_zones.zone2_minutes_30d))} min`}
                  {training_zones.zone2_pct_of_total != null && (
                    <span className="text-muted-foreground ml-1">
                      ({training_zones.zone2_pct_of_total.toFixed(0)}%)
                    </span>
                  )}
                </>
              }
            />
            {training_zones.zone2_target_met != null && (
              <span
                className={cn(
                  "type-mono-label normal-case tracking-wide pt-1",
                  training_zones.zone2_target_met ? "text-moss" : "text-brass",
                )}
              >
                {training_zones.zone2_target_met
                  ? "target met"
                  : "below target"}
              </span>
            )}
          </div>
          <div className="pt-3 border-t border-border flex flex-col gap-1">
            <Row
              label="Zone 5 · 7d"
              value={
                training_zones.zone5_minutes_7d == null
                  ? "—"
                  : `${String(Math.round(training_zones.zone5_minutes_7d))} min`
              }
            />
            <Row
              label="Zone 5 · 30d"
              value={
                <>
                  {training_zones.zone5_minutes_30d == null
                    ? "—"
                    : `${String(Math.round(training_zones.zone5_minutes_30d))} min`}
                  {training_zones.zone5_pct_of_total != null && (
                    <span className="text-muted-foreground ml-1">
                      ({training_zones.zone5_pct_of_total.toFixed(0)}%)
                    </span>
                  )}
                </>
              }
            />
            {training_zones.zone5_target_met != null && (
              <span
                className={cn(
                  "type-mono-label normal-case tracking-wide pt-1",
                  training_zones.zone5_target_met ? "text-moss" : "text-brass",
                )}
              >
                {training_zones.zone5_target_met
                  ? "target met"
                  : "below target"}
              </span>
            )}
          </div>
          {training_zones.total_training_minutes_30d != null && (
            <div className="pt-3 border-t border-border type-mono-label text-muted-foreground normal-case tracking-wide">
              total training ·{" "}
              {Math.round(training_zones.total_training_minutes_30d)} min/30d
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
}
