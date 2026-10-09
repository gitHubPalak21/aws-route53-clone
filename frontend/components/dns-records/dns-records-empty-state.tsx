"use client";

import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useRouter } from "next/navigation";
import { createRecordPath } from "@/lib/api/dns-records";

export function DNSRecordsEmptyState({ zoneId, filtered, outOfRange, onClear, onFirstPage }: {
  zoneId: string; filtered: boolean; outOfRange: boolean; onClear: () => void; onFirstPage: () => void;
}) {
  const router = useRouter();
  return <Box textAlign="center" margin={{ vertical: "l" }} color="inherit"><SpaceBetween size="m">
    <div>
      <Box variant="strong">{outOfRange ? "No records on this page" : filtered ? "No matches" : "No records"}</Box>
      <Box variant="p" color="inherit">{outOfRange ? "The records list has changed. Return to the first page."
        : filtered ? "No records match the current search or filters." : "There are no DNS records in this hosted zone."}</Box>
    </div>
    {outOfRange ? <Button onClick={onFirstPage}>Go to first page</Button> : filtered
      ? <Button onClick={onClear}>Clear filters</Button>
      : <Button href={createRecordPath(zoneId)} onFollow={(event) => { event.preventDefault(); router.push(createRecordPath(zoneId)); }}>Create record</Button>}
  </SpaceBetween></Box>;
}
