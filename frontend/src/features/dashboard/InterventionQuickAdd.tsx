import { useMemo } from "react";
import { format } from "date-fns";
import { toast } from "sonner";
import {
  Wine,
  Thermometer,
  Plane,
  Soup,
  Flame,
  Pill,
  type LucideIcon,
} from "lucide-react";
import { Card, CardContent } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import {
  useInterventions,
  useCreateIntervention,
} from "../../hooks/useHealthLog";
import { useToday } from "../../hooks/useToday";
import type { InterventionData } from "../../types/api";
import { cn } from "../../lib/utils";

type Category = InterventionData["category"];

interface QuickTag {
  readonly name: string;
  readonly category: Category;
  readonly icon: LucideIcon;
  readonly accent: string;
}

const QUICK_TAGS: readonly QuickTag[] = [
  {
    name: "Alcohol",
    category: "lifestyle",
    icon: Wine,
    accent: "text-purple-500",
  },
  {
    name: "Illness",
    category: "lifestyle",
    icon: Thermometer,
    accent: "text-red-500",
  },
  {
    name: "Travel",
    category: "lifestyle",
    icon: Plane,
    accent: "text-blue-500",
  },
  { name: "Fasting", category: "diet", icon: Soup, accent: "text-amber-500" },
  {
    name: "Sauna",
    category: "lifestyle",
    icon: Flame,
    accent: "text-orange-500",
  },
  {
    name: "Medication",
    category: "medication",
    icon: Pill,
    accent: "text-emerald-500",
  },
];

export function InterventionQuickAdd() {
  const today = useToday();
  const todayKey = format(today, "yyyy-MM-dd");
  const { data: interventions = [] } = useInterventions();
  const createMutation = useCreateIntervention();

  const tagsLoggedToday = useMemo(() => {
    const set = new Set<string>();
    for (const i of interventions) {
      if (i.start_date === todayKey) {
        set.add(`${i.category}:${i.name.toLowerCase()}`);
      }
    }
    return set;
  }, [interventions, todayKey]);

  const handleTag = (tag: QuickTag) => {
    const key = `${tag.category}:${tag.name.toLowerCase()}`;
    if (tagsLoggedToday.has(key)) {
      toast.info(`${tag.name} already logged today`);
      return;
    }
    createMutation.mutate(
      {
        name: tag.name,
        category: tag.category,
        start_date: todayKey,
      },
      {
        onSuccess: () => {
          toast.success(`Logged ${tag.name.toLowerCase()} for today`);
        },
        onError: (error) => {
          toast.error(
            `Failed to log ${tag.name.toLowerCase()}: ${error.message}`,
          );
        },
      },
    );
  };

  return (
    <Card>
      <CardContent className="p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium">Quick log</p>
            <p className="text-xs text-muted-foreground">
              Tag today&apos;s lifestyle event — appears as marker on every
              metric chart.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {QUICK_TAGS.map((tag) => {
              const key = `${tag.category}:${tag.name.toLowerCase()}`;
              const logged = tagsLoggedToday.has(key);
              const Icon = tag.icon;
              return (
                <Button
                  key={tag.name}
                  type="button"
                  variant={logged ? "secondary" : "outline"}
                  size="sm"
                  onClick={() => {
                    handleTag(tag);
                  }}
                  disabled={createMutation.isPending}
                  className={cn(
                    "gap-1.5 font-medium",
                    logged && "ring-1 ring-primary/40",
                  )}
                  aria-pressed={logged}
                >
                  <Icon
                    className={cn(
                      "h-3.5 w-3.5",
                      logged ? "text-primary" : tag.accent,
                    )}
                  />
                  <span>{tag.name}</span>
                </Button>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
