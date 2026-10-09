"use client";

import Alert from "@cloudscape-design/components/alert";
import Button from "@cloudscape-design/components/button";
import ContentLayout from "@cloudscape-design/components/content-layout";
import Header from "@cloudscape-design/components/header";
import Spinner from "@cloudscape-design/components/spinner";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useRouter } from "next/navigation";

export function HostedZoneResourceState({ loading, missing, onRetry }: { loading: boolean; missing: boolean; onRetry: () => void }) {
  const router = useRouter();
  if (loading) return <ContentLayout disableOverlap header={<Header variant="h1">Hosted zone</Header>}>
    <div role="status"><SpaceBetween direction="horizontal" size="xs"><Spinner /><span>Loading hosted zone</span></SpaceBetween></div>
  </ContentLayout>;
  return <ContentLayout disableOverlap header={<Header variant="h1">{missing ? "Hosted zone not found" : "Unable to load hosted zone"}</Header>}>
    <SpaceBetween size="m">
      <Alert type="error">{missing ? "The hosted zone may have been deleted or you may not have access to it." : "The hosted zone could not be loaded. Try again."}</Alert>
      <SpaceBetween direction="horizontal" size="xs">
        <Button onClick={() => router.push("/route53/hosted-zones")}>Back to hosted zones</Button>
        {!missing && <Button onClick={onRetry}>Retry</Button>}
      </SpaceBetween>
    </SpaceBetween>
  </ContentLayout>;
}
