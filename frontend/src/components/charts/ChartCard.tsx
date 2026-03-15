import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

interface ChartCardProps {
  title: string;
  icon: LucideIcon;
  iconColorClass: string;
  iconBgClass: string;
  children: ReactNode;
  contentClassName?: string;
}

export function ChartCard({
  title,
  icon: Icon,
  iconColorClass,
  iconBgClass,
  children,
  contentClassName,
}: ChartCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded-lg ${iconBgClass}`}>
            <Icon className={`h-4 w-4 ${iconColorClass}`} />
          </div>
          <CardTitle>{title}</CardTitle>
        </div>
      </CardHeader>
      <CardContent className={contentClassName}>{children}</CardContent>
    </Card>
  );
}
