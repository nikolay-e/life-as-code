import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap font-mono text-[11px] tracking-[0.18em] uppercase font-normal ring-offset-background transition-all duration-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground border border-primary hover:bg-foreground/85",
        destructive:
          "bg-destructive text-destructive-foreground border border-destructive hover:bg-destructive/85",
        outline:
          "border border-border bg-background text-foreground hover:border-primary hover:bg-secondary/40",
        secondary:
          "bg-secondary text-secondary-foreground border border-border hover:bg-secondary/70",
        ghost:
          "text-muted-foreground hover:text-foreground hover:bg-secondary/50",
        link: "text-foreground underline-offset-4 hover:underline decoration-brass",
      },
      size: {
        default: "h-10 px-5 py-2",
        sm: "h-8 px-3",
        lg: "h-12 px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  };

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button };
