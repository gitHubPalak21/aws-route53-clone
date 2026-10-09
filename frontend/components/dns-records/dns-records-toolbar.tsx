"use client";

import Select from "@cloudscape-design/components/select";
import TextFilter from "@cloudscape-design/components/text-filter";
import { DNS_RECORD_TYPES, type DNSRecordType } from "@/types/dns-record";
import styles from "./dns-records.module.css";

const options = [{ label: "All record types", value: "ALL" }, ...DNS_RECORD_TYPES.map((type) => ({ label: type, value: type }))];

export function DNSRecordsToolbar({ search, recordType, total, loading, onSearchChange, onTypeChange }: {
  search: string; recordType?: DNSRecordType; total?: number; loading: boolean;
  onSearchChange: (value: string) => void; onTypeChange: (value: DNSRecordType | undefined) => void;
}) {
  return <div className={styles.toolbar}>
    <TextFilter filteringText={search} filteringPlaceholder="Search records" filteringAriaLabel="Search records"
      filteringClearAriaLabel="Clear record search" loading={loading}
      countText={total === undefined ? undefined : `${total} ${total === 1 ? "match" : "matches"}`}
      onChange={({ detail }) => onSearchChange(detail.filteringText)} />
    <Select ariaLabel="Filter records by type" options={options}
      selectedOption={options.find((option) => option.value === (recordType ?? "ALL")) ?? options[0]}
      onChange={({ detail }) => onTypeChange(DNS_RECORD_TYPES.find((type) => type === detail.selectedOption.value))} />
  </div>;
}
