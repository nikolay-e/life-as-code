interface EmptyChartMessageProps {
  readonly message: string;
}

export function EmptyChartMessage({ message }: EmptyChartMessageProps) {
  return (
    <div className="flex items-center justify-center h-full text-muted-foreground">
      {message}
    </div>
  );
}
