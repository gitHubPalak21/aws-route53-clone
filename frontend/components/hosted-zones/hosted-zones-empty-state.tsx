"use client";

import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useRouter } from "next/navigation";

export const CREATE_ZONE_PATH = "/route53/hosted-zones/create";

export function HostedZonesEmptyState({ filtered, outOfRange, onClear, onFirstPage }: {
  filtered: boolean;
  outOfRange: boolean;
  onClear: () => void;
  onFirstPage: () => void;
}) {
  const router = useRouter();
  return (
    <Box textAlign="center" margin={{ vertical: "l" }} color="inherit">
      <SpaceBetween size="m">
        <div>
          <Box variant="strong">{outOfRange ? "No hosted zones on this page" : filtered ? "No matches" : "No hosted zones"}</Box>
          <Box variant="p" color="inherit">
            {outOfRange ? "The hosted zone list has changed. Return to the first page." : filtered
              ? "No hosted zones match the current search or filters."
              : "You don't have any hosted zones yet."}
          </Box>
        </div>
        {outOfRange ? <Button onClick={onFirstPage}>Go to first page</Button> : filtered
          ? <Button onClick={onClear}>Clear filters</Button>
          : <Button href={CREATE_ZONE_PATH} onFollow={(event) => {
            event.preventDefault();
            router.push(CREATE_ZONE_PATH);
          }}>Create hosted zone</Button>}
      </SpaceBetween>
    </Box>
  );
}
