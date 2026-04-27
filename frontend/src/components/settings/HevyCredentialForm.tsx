import { useState } from "react";
import { Button } from "../ui/button";
import { Spinner } from "../ui/spinner";
import { CheckCircle, Eye, EyeOff } from "lucide-react";

interface HevyCredentialFormProps {
  readonly onSave: (apiKey: string) => void;
  readonly onTest: (apiKey: string) => void;
  readonly onCancel: () => void;
  readonly isSaving: boolean;
  readonly isTesting: boolean;
  readonly testResult?: { success: boolean; error?: string } | null;
}

export function HevyCredentialForm({
  onSave,
  onTest,
  onCancel,
  isSaving,
  isTesting,
  testResult,
}: HevyCredentialFormProps) {
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);

  const isValid = apiKey.trim().length > 0;

  return (
    <div className="mt-3 space-y-3 pl-14">
      <div className="relative max-w-sm">
        <input
          type={showKey ? "text" : "password"}
          placeholder="Hevy API key"
          value={apiKey}
          onChange={(e) => {
            setApiKey(e.target.value);
          }}
          className="w-full px-3 py-2 text-sm border rounded-md bg-background pr-10"
        />
        <button
          type="button"
          onClick={() => {
            setShowKey(!showKey);
          }}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
        >
          {showKey ? (
            <EyeOff className="h-4 w-4" />
          ) : (
            <Eye className="h-4 w-4" />
          )}
        </button>
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
            onSave(apiKey.trim());
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
            onTest(apiKey.trim());
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
