import { Card, CardContent } from "./card";

interface ErrorCardProps {
  readonly message: string;
}

export function ErrorCard({ message }: ErrorCardProps) {
  return (
    <Card className="border-destructive/50 bg-destructive/5">
      <CardContent className="pt-6">
        <p className="text-destructive">{message}</p>
      </CardContent>
    </Card>
  );
}
