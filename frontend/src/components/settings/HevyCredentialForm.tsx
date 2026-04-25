import { useState } from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
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

const FIELD_INPUT_CLASS =
  "h-11 bg-transparent border-0 border-b border-border rounded-none px-0 font-serif text-[18px] focus-visible:ring-0 focus-visible:border-foreground placeholder:text-muted-foreground/50";

const FIELD_INPUT_STYLE = { fontVariationSettings: '"opsz" 14, "SOFT" 40' };

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
    <div className="mt-2 mb-7 pb-7 grid gap-7 md:grid-cols-[200px_1fr] md:gap-8 border-l border-border/40 pl-5 md:pl-8">
      <span className="type-mono-eyebrow text-muted-foreground hidden md:block pt-2">
        Hevy · api key
      </span>
      <div className="space-y-7 max-w-md">
        <div className="space-y-2">
          <Label
            htmlFor="hevy-api-key"
            className="type-mono-label text-muted-foreground"
          >
            Hevy API key
          </Label>
          <div className="relative">
            <Input
              id="hevy-api-key"
              type={showKey ? "text" : "password"}
              placeholder="paste API key"
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value);
              }}
              className={`${FIELD_INPUT_CLASS} pr-10`}
              style={FIELD_INPUT_STYLE}
            />
            <button
              type="button"
              aria-label={showKey ? "Hide key" : "Show key"}
              onClick={() => {
                setShowKey(!showKey);
              }}
              className="absolute right-0 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            >
              {showKey ? (
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
              onSave(apiKey.trim());
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
              onTest(apiKey.trim());
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
