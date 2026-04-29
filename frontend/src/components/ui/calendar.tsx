import { DayPicker, type DayPickerProps } from "react-day-picker";
import "react-day-picker/style.css";
import { cn } from "../../lib/utils";

export type CalendarProps = DayPickerProps;

export function Calendar({ className, classNames, ...props }: CalendarProps) {
  return (
    <DayPicker
      showOutsideDays
      className={cn("p-2", className)}
      classNames={{
        root: "rdp-root",
        months: "flex flex-col gap-4",
        month: "flex flex-col gap-2",
        month_caption:
          "flex justify-center pt-1 pb-2 relative items-center text-sm font-medium",
        caption_label: "text-sm font-medium",
        nav: "absolute inset-x-1 top-1 flex justify-between",
        button_previous:
          "h-7 w-7 inline-flex items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground",
        button_next:
          "h-7 w-7 inline-flex items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground",
        month_grid: "w-full border-collapse",
        weekdays: "flex",
        weekday:
          "text-muted-foreground rounded-md w-9 font-normal text-[0.7rem] uppercase",
        week: "flex w-full mt-1",
        day: "relative p-0 text-center text-sm focus-within:relative focus-within:z-20 [&:has([aria-selected])]:bg-accent",
        day_button:
          "inline-flex h-9 w-9 items-center justify-center rounded-md p-0 font-normal hover:bg-accent hover:text-accent-foreground aria-selected:opacity-100",
        selected:
          "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground",
        today: "bg-accent text-accent-foreground",
        outside: "text-muted-foreground/50 aria-selected:bg-accent/40",
        disabled: "text-muted-foreground/40 opacity-50",
        range_middle:
          "aria-selected:bg-accent aria-selected:text-accent-foreground",
        hidden: "invisible",
        ...classNames,
      }}
      {...props}
    />
  );
}
