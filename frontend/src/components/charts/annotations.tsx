import type { InterventionData } from "../../types/api";

export type AnnotationCategory = InterventionData["category"];

export interface ChartAnnotation {
  readonly id: string | number;
  readonly startDate: string;
  readonly endDate: string | null;
  readonly label: string;
  readonly category: AnnotationCategory;
}

export const CATEGORY_COLOR: Record<AnnotationCategory, string> = {
  supplement: "hsl(142 71% 45%)",
  protocol: "hsl(217 91% 60%)",
  medication: "hsl(160 84% 39%)",
  lifestyle: "hsl(280 65% 60%)",
  diet: "hsl(38 92% 50%)",
};

export function interventionsToAnnotations(
  interventions: readonly InterventionData[] | undefined,
): readonly ChartAnnotation[] {
  if (!interventions?.length) return [];
  return interventions.map((i) => ({
    id: i.id,
    startDate: i.start_date,
    endDate: i.end_date,
    label: i.name,
    category: i.category,
  }));
}
