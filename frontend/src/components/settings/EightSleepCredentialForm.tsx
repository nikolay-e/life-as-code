import { useState } from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Spinner } from "../ui/spinner";
import { CheckCircle, Eye, EyeOff } from "lucide-react";

interface EightSleepCredentialFormProps {
  readonly onSave: (email: string, password: string) => void;
  readonly onTest: (email: string, password: string) => void;
  readonly onCancel: () => void;
  readonly isSaving: boolean;
  readonly isTesting: boolean;
  readonly testResult?: { success: boolean; error?: string } | null;
  readonly initialEmail?: string;
}

const FIELD_INPUT_CLASS =
  "h-11 bg-transparent border-0 border-b border-border rounded-none px-0 font-serif text-[18px] focus-visible:ring-0 focus-visible:border-foreground placeholder:text-muted-foreground/50";

const FIELD_INPUT_STYLE = { fontVariationSettings: '"opsz" 14, "SOFT" 40' };

export function EightSleepCredentialForm({
  onSave,
  onTest,
  onCancel,
  isSaving,
  isTesting,
  testResult,
  initialEmail,
}: EightSleepCredentialFormProps) {
  const [email, setEmail] = useState(initialEmail ?? "");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const isValid = email.trim().length > 0 && password.trim().length > 0;

  return (
    <div className="mt-2 mb-7 pb-7 grid gap-7 md:grid-cols-[200px_1fr] md:gap-8 border-l border-border/40 pl-5 md:pl-8">
      <span className="type-mono-eyebrow text-muted-foreground hidden md:block pt-2">
        Eight Sleep · credentials
      </span>
      <div className="space-y-7 max-w-md">
        <div className="space-y-2">
          <Label
            htmlFor="eight-sleep-email"
            className="type-mono-label text-muted-foreground"
          >
            Eight Sleep email
          </Label>
          <Input
            id="eight-sleep-email"
            type="email"
            placeholder="name@example.com"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
            }}
            className={FIELD_INPUT_CLASS}
            style={FIELD_INPUT_STYLE}
          />
        </div>
        <div className="space-y-2">
          <Label
            htmlFor="eight-sleep-password"
            className="type-mono-label text-muted-foreground"
          >
            Eight Sleep password
          </Label>
          <div className="relative">
            <Input
              id="eight-sleep-password"
              type={showPassword ? "text" : "password"}
              placeholder="enter your password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
              }}
              className={`${FIELD_INPUT_CLASS} pr-10`}
              style={FIELD_INPUT_STYLE}
            />
            <button
              type="button"
              aria-label={showPassword ? "Hide password" : "Show password"}
              onClick={() => {
                setShowPassword(!showPassword);
              }}
              className="absolute right-0 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            >
              {showPassword ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>

        {testResult && (
          <div className="type-mono-eyebrow flex items-center gap-2">
            {testResult.success ? (
              <span className="flex items-center gap-2 text-moss">
                <CheckCircle className="h-3.5 w-3.5" aria-hidden="true" />
                Connection verified
              </span>
            ) : (
              <span className="text-rust">
                {testResult.error ?? "Connection failed"}
              </span>
            )}
          </div>
        )}

        <div className="flex flex-wrap gap-3 pt-1">
          <Button
            size="sm"
            onClick={() => {
              onSave(email.trim(), password.trim());
            }}
            disabled={!isValid || isSaving}
          >
            {isSaving ? (
              <Spinner size="sm" className="mr-2" label="Saving" />
            ) : null}
            Save
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              onTest(email.trim(), password.trim());
            }}
            disabled={!isValid || isTesting}
          >
            {isTesting ? (
              <Spinner size="sm" className="mr-2" label="Testing" />
            ) : null}
            Test connection
          </Button>
          <Button size="sm" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}
