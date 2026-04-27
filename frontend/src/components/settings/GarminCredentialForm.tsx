import { useState } from "react";
import { Button } from "../ui/button";
import { Spinner } from "../ui/spinner";
import { CheckCircle, Eye, EyeOff } from "lucide-react";

interface GarminCredentialFormProps {
  readonly onSave: (email: string, password: string) => void;
  readonly onTest: (email: string, password: string) => void;
  readonly onCancel: () => void;
  readonly isSaving: boolean;
  readonly isTesting: boolean;
  readonly testResult?: { success: boolean; error?: string } | null;
  readonly initialEmail?: string;
}

export function GarminCredentialForm({
  onSave,
  onTest,
  onCancel,
  isSaving,
  isTesting,
  testResult,
  initialEmail,
}: GarminCredentialFormProps) {
  const [email, setEmail] = useState(initialEmail ?? "");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const isValid = email.trim().length > 0 && password.trim().length > 0;

  return (
    <div className="mt-3 space-y-3 pl-14">
      <div className="space-y-2">
        <input
          type="email"
          placeholder="Garmin email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
          }}
          className="w-full max-w-sm px-3 py-2 text-sm border rounded-md bg-background"
        />
        <div className="relative max-w-sm">
          <input
            type={showPassword ? "text" : "password"}
            placeholder="Garmin password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
            }}
            className="w-full px-3 py-2 text-sm border rounded-md bg-background pr-10"
          />
          <button
            type="button"
            onClick={() => {
              setShowPassword(!showPassword);
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
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
        <div
          className={`text-sm ${testResult.success ? "text-green-700" : "text-red-700"}`}
        >
          {testResult.success ? (
            <span className="flex items-center gap-1">
              <CheckCircle className="h-3.5 w-3.5" />
              Connection successful
            </span>
          ) : (
            (testResult.error ?? "Connection failed")
          )}
        </div>
      )}

      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={() => {
            onSave(email.trim(), password.trim());
          }}
          disabled={!isValid || isSaving}
        >
          {isSaving ? (
            <Spinner size="sm" className="mr-1" label="Saving" />
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
            <Spinner size="sm" className="mr-1" label="Testing" />
          ) : null}
          Test Connection
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
