import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../../../components/ui/card";
import type { LongevityInsights } from "../../../types/api";
import { Heart, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "../../../lib/utils";
import { signPrefix, formatMetricLabel } from "./stat-utils";

function getLongevityScoreColor(score: number | null): string {
  if (score === null) return "text-muted-foreground";
  if (score >= 80) return "text-green-600 dark:text-green-400";
  if (score >= 60) return "text-green-500";
  if (score >= 40) return "text-yellow-500";
  if (score >= 20) return "text-orange-500";
  return "text-red-500";
}

function getAgeDeltaColor(delta: number | null): string {
  if (delta === null) return "text-muted-foreground";
  if (delta <= -5) return "text-green-600 dark:text-green-400";
  if (delta <= -2) return "text-green-500";
  if (delta <= 2) return "text-blue-500";
  if (delta <= 5) return "text-orange-500";
  return "text-red-500";
}

export interface LongevitySectionProps {
  readonly longevityInsights: LongevityInsights;
}

export function LongevitySection({ longevityInsights }: LongevitySectionProps) {
  const { biological_age, training_zones, longevity_score } = longevityInsights;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Longevity</h2>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card className="border-2">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <Heart className="h-4 w-4 text-rose-500" />
              <CardTitle className="text-base">Longevity Score</CardTitle>
            </div>
            <CardDescription>
              Composite score across all longevity pillars
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-center mb-4">
              <p
                className={cn(
                  "text-4xl font-bold",
                  getLongevityScoreColor(longevity_score.overall),
                )}
              >
                {longevity_score.overall == null
                  ? "—"
                  : longevity_score.overall.toFixed(0)}
              </p>
              <p className="text-xs text-muted-foreground mt-1">out of 100</p>
              {longevity_score.trend != null && (
                <div className="flex items-center justify-center gap-1 mt-1">
                  {longevity_score.trend > 0 && (
                    <TrendingUp className="h-3 w-3 text-green-500" />
                  )}
                  {longevity_score.trend < 0 && (
                    <TrendingDown className="h-3 w-3 text-red-500" />
                  )}
                  {longevity_score.trend === 0 && (
                    <Minus className="h-3 w-3 text-muted-foreground" />
                  )}
                  <span className="text-xs text-muted-foreground">
                    {signPrefix(longevity_score.trend)}
                    {longevity_score.trend.toFixed(1)}/mo
                  </span>
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              {[
                {
                  label: "Cardio",
                  value: longevity_score.cardiorespiratory,
                },
                {
                  label: "Recovery",
                  value: longevity_score.recovery_resilience,
                },
                {
                  label: "Sleep",
                  value: longevity_score.sleep_optimization,
                },
                {
                  label: "Body Comp",
                  value: longevity_score.body_composition,
                },
                {
                  label: "Activity",
                  value: longevity_score.activity_consistency,
                },
              ].map(({ label, value }) => (
                <div key={label} className="flex justify-between">
                  <span className="text-xs text-muted-foreground">{label}</span>
                  <span
                    className={cn(
                      "font-mono text-xs",
                      getLongevityScoreColor(value),
                    )}
                  >
                    {value == null ? "—" : value.toFixed(0)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Biological Age</CardTitle>
            <CardDescription>Estimated vs chronological age</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-center mb-4">
              <p
                className={cn(
                  "text-3xl font-bold",
                  getAgeDeltaColor(biological_age.age_delta),
                )}
              >
                {biological_age.composite_biological_age == null
                  ? "—"
                  : biological_age.composite_biological_age.toFixed(1)}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Chronological: {biological_age.chronological_age}
                {biological_age.age_delta != null && (
                  <span
                    className={cn(
                      "ml-2 font-medium",
                      getAgeDeltaColor(biological_age.age_delta),
                    )}
                  >
                    ({signPrefix(biological_age.age_delta)}
                    {biological_age.age_delta.toFixed(1)} yrs)
                  </span>
                )}
              </p>
            </div>
            {biological_age.pace_of_aging != null && (
              <div className="text-sm text-center mb-3">
                <span className="text-muted-foreground">Pace of aging: </span>
                <span
                  className={cn(
                    "font-medium",
                    biological_age.pace_of_aging < 1
                      ? "text-green-500"
                      : "text-red-500",
                  )}
                >
                  {biological_age.pace_of_aging.toFixed(2)} yr/yr
                </span>
              </div>
            )}
            <div className="space-y-1">
              {biological_age.components.map((comp) => (
                <div
                  key={comp.name}
                  className="flex justify-between items-center text-xs"
                >
                  <span className="text-muted-foreground">
                    {formatMetricLabel(comp.name)}
                  </span>
                  <span
                    className={cn("font-mono", getAgeDeltaColor(comp.delta))}
                  >
                    {comp.estimated_age == null
                      ? "—"
                      : comp.estimated_age.toFixed(1)}
                    {comp.delta != null && (
                      <span className="ml-1">
                        ({signPrefix(comp.delta)}
                        {comp.delta.toFixed(1)})
                      </span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Training Zones</CardTitle>
            <CardDescription>Zone 2 & Zone 5 distribution</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-muted-foreground">Zone 2 (7d)</span>
                  <span className="font-mono">
                    {training_zones.zone2_minutes_7d == null
                      ? "—"
                      : `${String(Math.round(training_zones.zone2_minutes_7d))} min`}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Zone 2 (30d)</span>
                  <span className="font-mono">
                    {training_zones.zone2_minutes_30d == null
                      ? "—"
                      : `${String(Math.round(training_zones.zone2_minutes_30d))} min`}
                    {training_zones.zone2_pct_of_total != null && (
                      <span className="text-muted-foreground ml-1">
                        ({training_zones.zone2_pct_of_total.toFixed(0)}%)
                      </span>
                    )}
                  </span>
                </div>
                {training_zones.zone2_target_met != null && (
                  <p
                    className={cn(
                      "text-xs mt-1",
                      training_zones.zone2_target_met
                        ? "text-green-500"
                        : "text-yellow-500",
                    )}
                  >
                    {training_zones.zone2_target_met
                      ? "Target met"
                      : "Below target"}
                  </p>
                )}
              </div>
              <div className="pt-2 border-t">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-muted-foreground">Zone 5 (7d)</span>
                  <span className="font-mono">
                    {training_zones.zone5_minutes_7d == null
                      ? "—"
                      : `${String(Math.round(training_zones.zone5_minutes_7d))} min`}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Zone 5 (30d)</span>
                  <span className="font-mono">
                    {training_zones.zone5_minutes_30d == null
                      ? "—"
                      : `${String(Math.round(training_zones.zone5_minutes_30d))} min`}
                    {training_zones.zone5_pct_of_total != null && (
                      <span className="text-muted-foreground ml-1">
                        ({training_zones.zone5_pct_of_total.toFixed(0)}%)
                      </span>
                    )}
                  </span>
                </div>
                {training_zones.zone5_target_met != null && (
                  <p
                    className={cn(
                      "text-xs mt-1",
                      training_zones.zone5_target_met
                        ? "text-green-500"
                        : "text-yellow-500",
                    )}
                  >
                    {training_zones.zone5_target_met
                      ? "Target met"
                      : "Below target"}
                  </p>
                )}
              </div>
              {training_zones.total_training_minutes_30d != null && (
                <div className="pt-2 border-t text-xs text-muted-foreground">
                  Total training:{" "}
                  {Math.round(training_zones.total_training_minutes_30d)}{" "}
                  min/30d
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
