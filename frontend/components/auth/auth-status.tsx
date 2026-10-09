"use client";

import Alert from "@cloudscape-design/components/alert";
import Button from "@cloudscape-design/components/button";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Spinner from "@cloudscape-design/components/spinner";

export function AuthLoading() {
  return (
    <div className="auth-status" role="status" aria-live="polite">
      <SpaceBetween size="s" direction="horizontal">
        <Spinner />
        <span>Checking your session…</span>
      </SpaceBetween>
    </div>
  );
}

export function AuthUnavailable({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="auth-status" role="alert">
      <Alert type="error" header="Unable to check your session" action={<Button onClick={onRetry}>Try again</Button>}>
        {message}
      </Alert>
    </div>
  );
}
