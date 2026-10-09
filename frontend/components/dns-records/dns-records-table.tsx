"use client";

import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Header from "@cloudscape-design/components/header";
import Pagination from "@cloudscape-design/components/pagination";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Table, { type TableProps } from "@cloudscape-design/components/table";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useDNSRecords } from "@/hooks/use-dns-records";
import { createRecordPath, editRecordPath } from "@/lib/api/dns-records";
import { formatRecordTTL, ROUTING_POLICY_LABELS, type DNSRecord, type DNSRecordListParams } from "@/types/dns-record";
import { DNSRecordsEmptyState } from "./dns-records-empty-state";
import { DNSRecordsToolbar } from "./dns-records-toolbar";
import { RecordValuesCell } from "./record-values-cell";
import { DeleteDNSRecordModal } from "./delete-dns-record-modal";
import styles from "./dns-records.module.css";

const initialQuery: DNSRecordListParams = { page: 1, page_size: 20, sort_by: "name", sort_order: "asc" };
const columns: TableProps.ColumnDefinition<DNSRecord>[] = [
  { id: "name", header: "Record name", sortingField: "name", isRowHeader: true, minWidth: 170,
    cell: (record) => <span className={styles.name}>{record.name}</span> },
  { id: "record_type", header: "Type", sortingField: "record_type", minWidth: 125,
    cell: (record) => <SpaceBetween size="xxs"><span>{record.record_type}</span>{record.is_system && <Box fontSize="body-s" color="text-body-secondary">System managed</Box>}</SpaceBetween> },
  { id: "routing_policy", header: "Routing policy", minWidth: 115, cell: (record) => ROUTING_POLICY_LABELS[record.routing_policy] },
  { id: "values", header: "Value / Route traffic to", minWidth: 260, cell: (record) => <RecordValuesCell key={record.id} values={record.values} /> },
  { id: "ttl", header: "TTL", sortingField: "ttl", minWidth: 75, cell: (record) => formatRecordTTL(record.ttl) },
];

export function DNSRecordsTable({ zoneId, zoneRecordCount, onZoneMissing, onCountChanged }: {
  zoneId: string; zoneRecordCount: number; onZoneMissing: () => void; onCountChanged: () => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState<DNSRecordListParams>(initialQuery);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [deletingRecord, setDeletingRecord] = useState<DNSRecord | null>(null);
  const { data, error, isLoading, refetch } = useDNSRecords(zoneId, query);
  const searchPending = search.trim() !== (query.search ?? "");
  const filtered = Boolean(query.search || query.record_type);
  useEffect(() => {
    const timeout = setTimeout(() => {
      const value = search.trim() || undefined;
      setQuery((previous) => previous.search === value ? previous : { ...previous, search: value, page: 1 });
    }, 350);
    return () => clearTimeout(timeout);
  }, [search]);
  useEffect(() => { if (error === "missing") onZoneMissing(); }, [error, onZoneMissing]);
  useEffect(() => {
    if (data && !filtered && data.total !== zoneRecordCount) onCountChanged();
  }, [data, filtered, zoneRecordCount, onCountChanged]);

  function changeQuery(changes: DNSRecordListParams) {
    setSelectedId(null);
    setQuery((previous) => ({ ...previous, ...changes, page: changes.page ?? 1 }));
  }
  function clearFilters() { setSearch(""); changeQuery({ search: undefined, record_type: undefined }); }
  const items = data?.items ?? [];
  const outOfRange = Boolean(data?.total && !items.length);
  const selectedItems = searchPending ? [] : items.filter((record) => record.id === selectedId);
  const selected = selectedItems[0];
  const mutableSelection = Boolean(selected && !selected.is_system && !isLoading);
  if (error === "missing") return null;
  return <SpaceBetween size="m">
    {deletingRecord && <DeleteDNSRecordModal record={deletingRecord} onDismiss={() => setDeletingRecord(null)} onDeleted={() => {
      setDeletingRecord(null); setSelectedId(null);
      if (data?.items.length === 1 && data.page > 1) changeQuery({ page: data.page - 1 });
      else refetch();
      onCountChanged();
    }} />}
    <Table<DNSRecord> trackBy="id" variant="container" contentDensity="compact" wrapLines
      items={items} columnDefinitions={columns} loading={isLoading} loadingText="Loading records"
      selectionType="single" selectedItems={selectedItems}
      onSelectionChange={({ detail }) => setSelectedId(detail.selectedItems[0]?.id ?? null)}
      ariaLabels={{ tableLabel: "DNS records", selectionGroupLabel: "DNS record selection",
        itemSelectionLabel: (_, record) => `Select ${record.name} ${record.record_type} record${record.is_system ? ", system managed" : ""}` }}
      sortingColumn={columns.find((column) => column.sortingField === query.sort_by)} sortingDescending={query.sort_order === "desc"}
      onSortingChange={({ detail }) => {
        const field = detail.sortingColumn.sortingField;
        if (field === "name" || field === "record_type" || field === "ttl") changeQuery({ sort_by: field, sort_order: detail.isDescending ? "desc" : "asc" });
      }}
      header={<Header variant="h2" counter={data ? `(${data.total.toLocaleString("en-US")})` : undefined}
        description={selected?.is_system ? "The selected record is system managed and read-only." : undefined}
        actions={<SpaceBetween direction="horizontal" size="xs">
          <Button iconName="refresh" ariaLabel="Refresh records" loading={isLoading} loadingText="Refreshing records"
            onClick={() => { setSelectedId(null); refetch(); }}>Refresh</Button>
          <Button disabled={!mutableSelection} onClick={() => { if (selected && !selected.is_system) router.push(editRecordPath(zoneId, selected.id)); }}>Edit record</Button>
          <Button disabled={!mutableSelection} onClick={() => { if (selected && !selected.is_system) setDeletingRecord(selected); }}>Delete record</Button>
          <Button variant="primary" href={createRecordPath(zoneId)} onFollow={(event) => { event.preventDefault(); router.push(createRecordPath(zoneId)); }}>Create record</Button>
        </SpaceBetween>}>Records</Header>}
      filter={<DNSRecordsToolbar search={search} recordType={query.record_type} total={data?.total} loading={isLoading || searchPending}
        onSearchChange={(value) => { setSearch(value); setSelectedId(null); }}
        onTypeChange={(record_type) => changeQuery({ record_type })} />}
      pagination={<Pagination currentPageIndex={data?.page ?? query.page ?? 1} pagesCount={Math.max(1, data?.pages ?? query.page ?? 1)}
        disabled={isLoading || searchPending || Boolean(error) || !data?.total || outOfRange}
        onChange={({ detail }) => changeQuery({ page: detail.currentPageIndex })}
        ariaLabels={{ paginationLabel: "Records pagination", nextPageLabel: "Next records page", previousPageLabel: "Previous records page", pageLabel: (page) => `Records page ${page}` }} />}
      empty={error ? <Alert type="error" header="Unable to load records" action={<Button onClick={refetch}>Retry</Button>}>
        DNS records could not be loaded. Try again.
      </Alert> : <DNSRecordsEmptyState zoneId={zoneId} filtered={filtered} outOfRange={outOfRange}
        onClear={clearFilters} onFirstPage={() => changeQuery({ page: 1 })} />}
      footer={data && items.length ? <Box color="text-body-secondary">Showing {(data.page - 1) * data.page_size + 1}–{(data.page - 1) * data.page_size + items.length} of {data.total} records</Box> : undefined}
    />
  </SpaceBetween>;
}
