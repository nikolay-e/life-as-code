import {
  useState,
  useRef,
  useEffect,
  useCallback,
  cloneElement,
  Children,
  isValidElement,
  type ReactElement,
  type ReactNode,
  type MouseEvent,
} from "react";
import { cn } from "../../lib/utils";

interface PopoverProps {
  readonly trigger: ReactElement;
  readonly children: ReactNode;
  readonly align?: "start" | "center" | "end";
  readonly side?: "top" | "bottom";
  readonly className?: string;
  readonly contentClassName?: string;
  readonly open?: boolean;
  readonly onOpenChange?: (open: boolean) => void;
}

export function Popover({
  trigger,
  children,
  align = "start",
  side = "bottom",
  className,
  contentClassName,
  open: controlledOpen,
  onOpenChange,
}: PopoverProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(false);
  const open = controlledOpen ?? uncontrolledOpen;
  const setOpen = useCallback(
    (next: boolean) => {
      setUncontrolledOpen(next);
      onOpenChange?.(next);
    },
    [onOpenChange],
  );

  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (
        target &&
        containerRef.current &&
        !containerRef.current.contains(target)
      ) {
        setOpen(false);
      }
    };
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", handlePointerDown, true);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open, setOpen]);

  const triggerEl = isValidElement(trigger)
    ? cloneElement(
        trigger as ReactElement<{ onClick?: (e: MouseEvent) => void }>,
        {
          onClick: (event: MouseEvent) => {
            (trigger.props as { onClick?: (e: MouseEvent) => void }).onClick?.(
              event,
            );
            setOpen(!open);
          },
        },
      )
    : trigger;

  return (
    <div ref={containerRef} className={cn("relative inline-block", className)}>
      {triggerEl}
      {open && (
        <div
          role="dialog"
          className={cn(
            "absolute z-50 min-w-[8rem] rounded-md border bg-popover p-2 text-popover-foreground shadow-md outline-none animate-in fade-in-0",
            side === "bottom" ? "top-full mt-2" : "bottom-full mb-2",
            align === "start" && "left-0",
            align === "center" && "left-1/2 -translate-x-1/2",
            align === "end" && "right-0",
            contentClassName,
          )}
        >
          {Children.map(children, (child) => child)}
        </div>
      )}
    </div>
  );
}
