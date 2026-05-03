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
  useHealthEvents,
  useCreateHealthEvent,
} from "../../hooks/useHealthLog";
import { useToday } from "../../hooks/useToday";
import type { HealthEventData } from "../../types/api";
import { cn } from "../../lib/utils";

type EventDomain = HealthEventData["domain"];

interface QuickTag {
  readonly name: string;
  readonly domain: EventDomain;
  readonly icon: LucideIcon;
  readonly accent: string;
}

const QUICK_TAGS: readonly QuickTag[] = [
  {
    name: "Alcohol",
    domain: "substance",
    icon: Wine,
    accent: "text-purple-500",
  },
  {
    name: "Illness",
    domain: "symptom",
    icon: Thermometer,
    accent: "text-red-500",
  },
  {
    name: "Travel",
    domain: "environment",
    icon: Plane,
    accent: "text-blue-500",
  },
  {
    name: "Fasting",
    domain: "nutrition",
    icon: Soup,
    accent: "text-amber-500",
  },
  {
    name: "Sauna",
    domain: "therapy",
    icon: Flame,
    accent: "text-orange-500",
  },
  {
    name: "Medication",
    domain: "medication",
    icon: Pill,
    accent: "text-emerald-500",
  },
];

export function InterventionQuickAdd() {
  const today = useToday();
  const todayKey = format(today, "yyyy-MM-dd");
  const { data: events = [] } = useHealthEvents(7);
  const createMutation = useCreateHealthEvent();

  const tagsLoggedToday = useMemo(() => {
    const set = new Set<string>();
    for (const e of events) {
      if (e.start_ts.startsWith(todayKey)) {
        set.add(`${e.domain}:${e.name.toLowerCase()}`);
      }
    }
    return set;
  }, [events, todayKey]);

  const handleTag = (tag: QuickTag) => {
    const key = `${tag.domain}:${tag.name.toLowerCase()}`;
    if (tagsLoggedToday.has(key)) {
      toast.info(`${tag.name} already logged today`);
      return;
    }
    createMutation.mutate(
      {
        name: tag.name,
        domain: tag.domain,
        start_ts: todayKey,
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
              const key = `${tag.domain}:${tag.name.toLowerCase()}`;
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
