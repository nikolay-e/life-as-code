import { useState, type FormEvent } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuthStore } from "./store";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Spinner } from "../../components/ui/spinner";
import { VersionInfo } from "../../components/ui/version-info";
import { ArrowRight } from "lucide-react";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const { login, isLoading, error, clearError } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as { from?: { pathname?: string } } | null;
  const from = state?.from?.pathname ?? "/dashboard";

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    clearError();
    login(username, password)
      .then(() => navigate(from, { replace: true }))
      .catch(() => {});
  };

  return (
    <main
      className="min-h-screen bg-background grid place-items-center px-5"
      style={{
        paddingTop: "max(2rem, env(safe-area-inset-top))",
        paddingBottom: "max(2rem, env(safe-area-inset-bottom))",
      }}
    >
      <div className="w-full max-w-[420px]">
        {/* Brand */}
        <div className="text-center mb-12">
          <h1
            className="font-serif text-[44px] leading-none tracking-[-0.03em]"
            style={{
              fontVariationSettings: '"opsz" 144, "SOFT" 100',
              fontWeight: 380,
            }}
          >
            vita<span className="text-brass">.</span>
          </h1>
          <div className="mt-3 type-mono-label text-muted-foreground">
            longevity intelligence
          </div>
        </div>

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="border-t border-foreground pt-9"
        >
          {error && (
            <div className="mb-6 p-3 border border-rust text-rust type-mono-eyebrow">
              {error}
            </div>
          )}

          <div className="space-y-7">
            <div className="space-y-2">
              <Label
                htmlFor="username"
                className="type-mono-label text-muted-foreground"
              >
                Username
              </Label>
              <Input
                id="username"
                type="text"
                placeholder="enter your username"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value);
                }}
                disabled={isLoading}
                required
                className="h-12 bg-transparent border-0 border-b border-border rounded-none px-0 font-serif text-[18px] focus-visible:ring-0 focus-visible:border-foreground placeholder:text-muted-foreground/50"
                style={{ fontVariationSettings: '"opsz" 14, "SOFT" 40' }}
              />
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="password"
                className="type-mono-label text-muted-foreground"
              >
                Password
              </Label>
              <Input
                id="password"
                type="password"
                placeholder="enter your password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                }}
                disabled={isLoading}
                required
                className="h-12 bg-transparent border-0 border-b border-border rounded-none px-0 font-serif text-[18px] focus-visible:ring-0 focus-visible:border-foreground placeholder:text-muted-foreground/50"
                style={{ fontVariationSettings: '"opsz" 14, "SOFT" 40' }}
              />
            </div>
          </div>

          <Button
            type="submit"
            className="w-full h-12 mt-9"
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <Spinner size="sm" className="mr-2" />
                Signing in…
              </>
            ) : (
              <>
                Sign in
                <ArrowRight className="ml-2 h-3.5 w-3.5" />
              </>
            )}
          </Button>
        </form>

        <p
          className="mt-8 text-center font-serif italic text-muted-foreground text-[15px]"
          style={{ fontVariationSettings: '"opsz" 14, "SOFT" 100' }}
        >
          Contact your administrator for account access.
        </p>
        <div className="mt-6 flex justify-center type-mono-label text-muted-foreground">
          <VersionInfo />
        </div>
      </div>
    </main>
  );
}
