"use client";

import Select from "@cloudscape-design/components/select";
import TextFilter from "@cloudscape-design/components/text-filter";
import type { HostedZoneType } from "@/types/hosted-zone";
import styles from "./hosted-zones.module.css";

const typeOptions = [
  { label: "All types", value: "ALL" },
  { label: "Public", value: "PUBLIC" },
  { label: "Private", value: "PRIVATE" },
];

interface Props {
  search: string;
  zoneType?: HostedZoneType;
  total?: number;
  loading: boolean;
  onSearchChange: (value: string) => void;
  onTypeChange: (value: HostedZoneType | undefined) => void;
}

export function HostedZonesToolbar({ search, zoneType, total, loading, onSearchChange, onTypeChange }: Props) {
  return (
    <div className={styles.toolbar}>
      <TextFilter
        filteringText={search}
        filteringPlaceholder="Search hosted zones"
        filteringAriaLabel="Search hosted zones"
        filteringClearAriaLabel="Clear hosted zone search"
        loading={loading}
        countText={total === undefined ? undefined : `${total} ${total === 1 ? "match" : "matches"}`}
        onChange={({ detail }) => onSearchChange(detail.filteringText)}
      />
      <Select
        ariaLabel="Filter hosted zones by type"
        options={typeOptions}
        selectedOption={typeOptions.find((option) => option.value === (zoneType ?? "ALL")) ?? typeOptions[0]}
        onChange={({ detail }) => {
          const value = detail.selectedOption.value;
          onTypeChange(value === "PUBLIC" || value === "PRIVATE" ? value : undefined);
        }}
      />
    </div>
  );
}
