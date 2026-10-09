"use client";

import Button from "@cloudscape-design/components/button";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Textarea from "@cloudscape-design/components/textarea";
import type { UserDNSRecordType } from "@/types/dns-record";
import { RECORD_TYPE_GUIDANCE } from "@/lib/validation/dns-records";
import styles from "./dns-records.module.css";

export interface RecordValueRow { id: number; value: string }
export function DNSRecordValuesInput({ rows, type, errors, error, disabled, onChange, onAdd, onRemove }: {
  rows: RecordValueRow[]; type: UserDNSRecordType; errors?: (string | undefined)[]; error?: string; disabled: boolean;
  onChange: (id: number, value: string) => void; onAdd: () => void; onRemove: (id: number) => void;
}) {
  const guidance = RECORD_TYPE_GUIDANCE[type];
  return <SpaceBetween size="m">
    {rows.map((row, index) => <div className={styles.valueRow} key={row.id}>
      <FormField label={rows.length === 1 ? "Value" : `Value ${index + 1}`} controlId={`record-value-${row.id}`}
        description={index === 0 ? guidance.help : undefined} errorText={errors?.[index] || (index === 0 ? error : undefined)}>
        {type === "TXT" ? <Textarea controlId={`record-value-${row.id}`} value={row.value} rows={2} resize="vertical" readOnly={disabled}
          ariaRequired placeholder={guidance.example} onChange={({ detail }) => onChange(row.id, detail.value)} />
          : <Input controlId={`record-value-${row.id}`} value={row.value} readOnly={disabled} ariaRequired
            disableBrowserAutocorrect spellcheck={false} placeholder={guidance.example} onChange={({ detail }) => onChange(row.id, detail.value)} />}
      </FormField>
      {rows.length > 1 && <Button formAction="none" disabled={disabled} ariaLabel={`Remove value ${index + 1}`} onClick={() => onRemove(row.id)}>Remove</Button>}
    </div>)}
    <div><Button formAction="none" disabled={disabled || rows.length >= 100} onClick={onAdd}>Add another value</Button></div>
  </SpaceBetween>;
}
