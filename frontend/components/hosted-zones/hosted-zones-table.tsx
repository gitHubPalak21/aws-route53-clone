"use client";

import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import ContentLayout from "@cloudscape-design/components/content-layout";
import Header from "@cloudscape-design/components/header";
import Link from "@cloudscape-design/components/link";
import Pagination from "@cloudscape-design/components/pagination";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Table, { type TableProps } from "@cloudscape-design/components/table";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useHostedZones } from "@/hooks/use-hosted-zones";
import { HOSTED_ZONE_TYPE_LABELS, type HostedZone, type HostedZoneListParams } from "@/types/hosted-zone";
import { CREATE_ZONE_PATH, HostedZonesEmptyState } from "./hosted-zones-empty-state";
import { HostedZonesToolbar } from "./hosted-zones-toolbar";
import styles from "./hosted-zones.module.css";
import { DeleteHostedZoneModal } from "./delete-hosted-zone-modal";
import { hostedZonePath } from "@/lib/api/hosted-zones";

const initialQuery: HostedZoneListParams = { page: 1, page_size: 20, sort_by: "name", sort_order: "asc" };

function DomainLink({ zone }: { zone: HostedZone }) {
  const router = useRouter();
  const href = hostedZonePath(zone.id);
  return <Link href={href} onFollow={(event) => { event.preventDefault(); router.push(href); }}>{zone.name}</Link>;
}

const columns: TableProps.ColumnDefinition<HostedZone>[] = [
  { id: "name", header: "Domain name", sortingField: "name", isRowHeader: true, minWidth: 210,
    cell: (zone) => <DomainLink zone={zone} /> },
  { id: "zone_type", header: "Type", sortingField: "zone_type", minWidth: 100,
    cell: (zone) => HOSTED_ZONE_TYPE_LABELS[zone.zone_type] },
  { id: "record_count", header: "Record count", minWidth: 125, cell: (zone) => zone.record_count },
  { id: "comment", header: "Description", minWidth: 185,
    cell: (zone) => <span className={styles.description} title={zone.comment || undefined}>{zone.comment || "—"}</span> },
  { id: "id", header: "Hosted zone ID", sortingField: "id", minWidth: 210,
    cell: (zone) => <Box variant="span" color="text-body-secondary"><span className={styles.zoneId}>{zone.id}</span></Box> },
];

export function HostedZonesTable() {
  const router = useRouter();
  const [query, setQuery] = useState<HostedZoneListParams>(initialQuery);
  const [searchText, setSearchText] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<HostedZone | null>(null);
  const { data, isLoading, error, refetch } = useHostedZones(query);
  const searchPending = searchText.trim() !== (query.search ?? "");

  useEffect(() => {
    const timeout = setTimeout(() => {
      const search = searchText.trim() || undefined;
      setQuery((previous) => previous.search === search ? previous : { ...previous, search, page: 1 });
    }, 350);
    return () => clearTimeout(timeout);
  }, [searchText]);

  function changeQuery(changes: HostedZoneListParams) {
    setSelectedId(null);
    setQuery((previous) => ({ ...previous, ...changes, page: changes.page ?? 1 }));
  }

  function clearFilters() {
    setSearchText("");
    changeQuery({ search: undefined, zone_type: undefined });
  }

  const items = data?.items ?? [];
  const selectedItems = searchPending ? [] : items.filter((zone) => zone.id === selectedId);
  const selected = selectedItems[0];
  const counter = data ? `(${selectedItems.length ? `${selectedItems.length}/` : ""}${data.total.toLocaleString("en-US")})` : undefined;
  const filtered = Boolean(query.search || query.zone_type);
  const outOfRange = Boolean(data?.total && !items.length);
  const sortingColumn = columns.find((column) => column.sortingField === query.sort_by);

  return (
    <ContentLayout disableOverlap>
      <Table<HostedZone>
        variant="full-page"
        trackBy="id"
        items={items}
        columnDefinitions={columns}
        wrapLines
        loading={isLoading}
        loadingText="Loading hosted zones"
        selectionType="single"
        selectedItems={selectedItems}
        onSelectionChange={({ detail }) => setSelectedId(detail.selectedItems[0]?.id ?? null)}
        ariaLabels={{
          tableLabel: "Hosted zones",
          selectionGroupLabel: "Hosted zone selection",
          itemSelectionLabel: (_, zone) => `Select ${zone.name}`,
        }}
        sortingColumn={sortingColumn}
        sortingDescending={query.sort_order === "desc"}
        onSortingChange={({ detail }) => {
          const field = detail.sortingColumn.sortingField;
          if (field === "name" || field === "zone_type" || field === "id") {
            changeQuery({ sort_by: field, sort_order: detail.isDescending ? "desc" : "asc" });
          }
        }}
        header={
          <Header variant="h1" counter={counter} description="Create and manage public and private hosted zones."
            actions={
              <SpaceBetween direction="horizontal" size="xs">
                <Button iconName="refresh" ariaLabel="Refresh hosted zones" loading={isLoading}
                  loadingText="Refreshing hosted zones" onClick={() => { setSelectedId(null); refetch(); }}>Refresh</Button>
                <Button disabled={!selected} onClick={() => { if (selected) router.push(`${hostedZonePath(selected.id)}/edit`); }}>Edit</Button>
                <Button disabled={!selected} onClick={() => { if (selected) setDeleteTarget(selected); }}>Delete</Button>
                <Button variant="primary" href={CREATE_ZONE_PATH} onFollow={(event) => {
                  event.preventDefault(); router.push(CREATE_ZONE_PATH);
                }}>Create hosted zone</Button>
              </SpaceBetween>
            }>
            Hosted zones
          </Header>
        }
        filter={
          <HostedZonesToolbar search={searchText} zoneType={query.zone_type} total={data?.total}
            loading={isLoading || searchPending}
            onSearchChange={(value) => { setSearchText(value); setSelectedId(null); }}
            onTypeChange={(zone_type) => changeQuery({ zone_type })} />
        }
        pagination={
          <Pagination currentPageIndex={data?.page ?? query.page ?? 1}
            pagesCount={Math.max(1, data?.pages ?? query.page ?? 1)}
            disabled={isLoading || searchPending || Boolean(error) || !data?.total || outOfRange}
            onChange={({ detail }) => changeQuery({ page: detail.currentPageIndex })}
            ariaLabels={{ paginationLabel: "Hosted zones pagination", nextPageLabel: "Next page",
              previousPageLabel: "Previous page", pageLabel: (page) => `Page ${page}` }} />
        }
        empty={error ?
          <Alert type="error" header="Unable to load hosted zones" action={<Button onClick={refetch}>Retry</Button>}>
            {error}
          </Alert> :
          <HostedZonesEmptyState filtered={filtered} outOfRange={outOfRange}
            onClear={clearFilters} onFirstPage={() => changeQuery({ page: 1 })} />}
        footer={data && data.total > 0 && items.length > 0 ?
          <Box color="text-body-secondary">
            Showing {(data.page - 1) * data.page_size + 1}–{(data.page - 1) * data.page_size + items.length} of {data.total} hosted zones
          </Box> : undefined}
      />
      {deleteTarget && <DeleteHostedZoneModal zone={deleteTarget} onDismiss={() => setDeleteTarget(null)} onDeleted={() => {
        setDeleteTarget(null); setSelectedId(null);
        if (data?.items.length === 1 && data.page > 1) changeQuery({ page: data.page - 1 });
        else refetch();
      }} />}
    </ContentLayout>
  );
}
