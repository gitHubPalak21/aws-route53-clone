"use client";

import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import ContentLayout from "@cloudscape-design/components/content-layout";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import Select from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";
import { recordErrorFeedback } from "@/lib/api/dns-record-errors";
import { hostedZonePath } from "@/lib/api/hosted-zones";
import { initialRecordValues, recordName, recordPayload, RECORD_TYPE_GUIDANCE, USER_RECORD_TYPES, validateRecordForm, type DNSRecordFormErrors } from "@/lib/validation/dns-records";
import type { DNSRecord, DNSRecordWrite } from "@/types/dns-record";
import type { HostedZone } from "@/types/hosted-zone";
import { DNSRecordValuesInput, type RecordValueRow } from "./dns-record-values-input";
import styles from "./dns-records.module.css";

const options = USER_RECORD_TYPES.map((type) => ({ label: type, value: type, description: RECORD_TYPE_GUIDANCE[type].description }));

export function DNSRecordForm({ mode, hostedZone, initialRecord, onSubmit, onSuccess }: {
  mode: "create" | "edit"; hostedZone: HostedZone; initialRecord?: DNSRecord;
  onSubmit: (payload: DNSRecordWrite) => Promise<DNSRecord>; onSuccess: (record: DNSRecord) => void;
}) {
  const router = useRouter();
  const { refreshUser } = useAuth();
  const [values, setValues] = useState(() => {
    const initial = initialRecordValues(hostedZone.name, initialRecord);
    return { name: initial.name, record_type: initial.record_type, ttl: initial.ttl };
  });
  const [rows, setRows] = useState<RecordValueRow[]>(() => initialRecordValues(hostedZone.name, initialRecord).values.map((value, id) => ({ id, value })));
  const nextRowId = useRef(rows.length);
  const [errors, setErrors] = useState<DNSRecordFormErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const pending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const creating = mode === "create";
  const normalized = recordName(values.name, hostedZone.name, values.record_type);
  const showSuffix = values.name.trim() && values.name.trim() !== "@" && normalized.name === `${values.name.trim().toLowerCase()}.${hostedZone.name}`;

  function clearValueErrors() { setErrors((previous) => ({ ...previous, values: undefined, valueErrors: undefined })); setFailure(null); }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current || initialRecord?.is_system) return;
    const formValues = { ...values, values: rows.map((row) => row.value) };
    const validation = validateRecordForm(formValues, hostedZone.name);
    setErrors(validation); setFailure(null);
    if (Object.keys(validation).length) {
      const index = validation.valueErrors?.findIndex(Boolean) ?? -1;
      const field = validation.name ? "record-name" : validation.record_type ? "record-type" : validation.ttl ? "record-ttl" : `record-value-${rows[Math.max(0, index)]?.id}`;
      document.getElementById(field)?.focus();
      return;
    }
    const payload = recordPayload(formValues, hostedZone.name);
    pending.current = true; setSubmitting(true);
    let saved = false;
    try {
      const record = await onSubmit(payload);
      saved = true;
      if (mounted.current) onSuccess(record);
    } catch (error: unknown) {
      if (!mounted.current) return;
      if (error instanceof ApiError && error.status === 401) { void refreshUser(); return; }
      const feedback = recordErrorFeedback(error, payload);
      setErrors({ name: feedback.fields.name, record_type: feedback.fields.record_type, ttl: feedback.fields.ttl, values: feedback.fields.values });
      setFailure(feedback.message);
    } finally {
      if (!saved) { pending.current = false; if (mounted.current) setSubmitting(false); }
    }
  }

  return <ContentLayout disableOverlap header={<Header variant="h1">{creating ? "Create record" : "Edit record"}</Header>}>
    <form onSubmit={submit} noValidate>
      <Form actions={<SpaceBetween direction="horizontal" size="xs">
        <Button formAction="none" variant="link" disabled={submitting} onClick={() => router.push(hostedZonePath(hostedZone.id))}>Cancel</Button>
        <Button variant="primary" formAction="submit" loading={submitting} loadingText={creating ? "Creating record" : "Saving record"}>
          {creating ? "Create record" : "Save changes"}
        </Button>
      </SpaceBetween>}>
        <SpaceBetween size="l">
          {failure && <div role="alert"><Alert type="error" header={creating ? "Unable to create record" : "Unable to update record"}>{failure}</Alert></div>}
          <Container header={<Header variant="h2">Record details</Header>}><SpaceBetween size="l">
            <FormField label="Record name" controlId="record-name" errorText={errors.name}
              description="Enter a relative label or full in-zone name. Leave blank or use @ for the zone apex."
              constraintText={!normalized.error ? `Record name: ${normalized.name}` : undefined}>
              <div className={styles.recordName}>
                <div className={styles.nameInput}><Input controlId="record-name" value={values.name} placeholder="www" readOnly={submitting}
                  disableBrowserAutocorrect spellcheck={false} onChange={({ detail }) => {
                    setValues((previous) => ({ ...previous, name: detail.value })); setErrors((previous) => ({ ...previous, name: undefined })); setFailure(null);
                  }} /></div>
                {showSuffix && <Box color="text-body-secondary">.{hostedZone.name}</Box>}
              </div>
            </FormField>
            <FormField label="Record type" controlId="record-type" errorText={errors.record_type}>
              <Select controlId="record-type" options={options} selectedOption={options.find((option) => option.value === values.record_type) ?? null}
                disabled={submitting} onChange={({ detail }) => {
                  const type = USER_RECORD_TYPES.find((type) => type === detail.selectedOption.value);
                  if (type) { setValues((previous) => ({ ...previous, record_type: type })); setErrors({}); setFailure(null); }
                }} />
            </FormField>
            <DNSRecordValuesInput rows={rows} type={values.record_type} disabled={submitting} errors={errors.valueErrors} error={errors.values}
              onChange={(id, value) => { setRows((previous) => previous.map((row) => row.id === id ? { ...row, value } : row)); clearValueErrors(); }}
              onAdd={() => { const id = nextRowId.current++; setRows((previous) => [...previous, { id, value: "" }]); clearValueErrors(); }}
              onRemove={(id) => { setRows((previous) => previous.length > 1 ? previous.filter((row) => row.id !== id) : previous); clearValueErrors(); }} />
            <FormField label="TTL (seconds)" controlId="record-ttl" errorText={errors.ttl} description="The amount of time DNS resolvers cache this record.">
              <div className={styles.ttl}><Input controlId="record-ttl" value={values.ttl} inputMode="numeric" ariaRequired readOnly={submitting}
                onChange={({ detail }) => { setValues((previous) => ({ ...previous, ttl: detail.value })); setErrors((previous) => ({ ...previous, ttl: undefined })); setFailure(null); }} /></div>
            </FormField>
            <FormField label="Routing policy" controlId="record-routing-policy">
              <Select controlId="record-routing-policy" readOnly selectedOption={{ label: "Simple", value: "SIMPLE" }}
                options={[{ label: "Simple", value: "SIMPLE" }]} />
            </FormField>
          </SpaceBetween></Container>
        </SpaceBetween>
      </Form>
    </form>
  </ContentLayout>;
}
