import type { HealthEventData, ProtocolData } from "../../types/api";

export type AnnotationDomain =
  | "substance"
  | "therapy"
  | "nutrition"
  | "sleep"
  | "stress"
  | "environment"
  | "symptom"
  | "medication"
  | "supplement"
  | "diet"
  | "lifestyle"
  | "training"
  | "other"
  | "protocol";

export interface ChartAnnotation {
  readonly id: string | number;
  readonly startDate: string;
  readonly endDate: string | null;
  readonly label: string;
  readonly category: AnnotationDomain;
}

export const CATEGORY_COLOR: Record<string, string> = {
  substance: "hsl(280 65% 60%)",
  therapy: "hsl(38 92% 50%)",
  nutrition: "hsl(142 71% 45%)",
  sleep: "hsl(217 91% 60%)",
  stress: "hsl(0 84% 60%)",
  environment: "hsl(190 80% 50%)",
  symptom: "hsl(0 72% 51%)",
  medication: "hsl(160 84% 39%)",
  supplement: "hsl(142 71% 45%)",
  diet: "hsl(38 92% 50%)",
  lifestyle: "hsl(280 65% 60%)",
  training: "hsl(217 91% 60%)",
  other: "hsl(220 9% 46%)",
  protocol: "hsl(217 91% 60%)",
};

function tsToDateStr(ts: string): string {
  return ts.slice(0, 10);
}

export function healthEventsToAnnotations(
  events: readonly HealthEventData[] | undefined,
): readonly ChartAnnotation[] {
  if (!events?.length) return [];
  return events.map((e) => ({
    id: `event-${String(e.id)}`,
    startDate: tsToDateStr(e.start_ts),
    endDate: e.end_ts ? tsToDateStr(e.end_ts) : null,
    label: e.name,
    category: e.domain,
  }));
}

export function protocolsToAnnotations(
  protocols: readonly ProtocolData[] | undefined,
): readonly ChartAnnotation[] {
  if (!protocols?.length) return [];
  return protocols.map((p) => ({
    id: `protocol-${String(p.id)}`,
    startDate: p.start_date,
    endDate: p.end_date,
    label: p.name,
    category: p.domain,
  }));
}
