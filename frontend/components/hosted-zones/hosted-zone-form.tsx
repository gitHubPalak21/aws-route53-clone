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
import RadioGroup from "@cloudscape-design/components/radio-group";
import Select from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Textarea from "@cloudscape-design/components/textarea";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";
import { validationFeedback } from "@/lib/api/validation-errors";
import { HOSTED_ZONE_REGIONS } from "@/lib/constants/regions";
import { formValues, validateZoneForm, zonePayload, type HostedZoneFormErrors, type HostedZoneFormValues } from "@/lib/hosted-zones/form-values";
import type { HostedZone, HostedZoneWrite } from "@/types/hosted-zone";

interface Props {
  mode: "create" | "edit";
  initialZone?: HostedZone;
  cancelHref: string;
  onSubmit: (payload: HostedZoneWrite) => Promise<HostedZone>;
  onSuccess: (zone: HostedZone) => void;
}

export function HostedZoneForm({ mode, initialZone, cancelHref, onSubmit, onSuccess }: Props) {
  const router = useRouter();
  const { refreshUser } = useAuth();
  const [values, setValues] = useState(() => formValues(initialZone));
  const [errors, setErrors] = useState<HostedZoneFormErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const pending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const creating = mode === "create";

  function change<K extends keyof HostedZoneFormValues>(field: K, value: HostedZoneFormValues[K]) {
    setValues((previous) => ({ ...previous, [field]: value }));
    setErrors((previous) => ({ ...previous, [field]: undefined }));
    setFailure(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const validation = validateZoneForm(values);
    setErrors(validation);
    setFailure(null);
    if (Object.keys(validation).length) {
      document.getElementById(`zone-${Object.keys(validation)[0]}`)?.focus();
      return;
    }
    pending.current = true;
    setSubmitting(true);
    let saved = false;
    try {
      const zone = await onSubmit(zonePayload(values));
      saved = true;
      if (mounted.current) onSuccess(zone);
    } catch (error: unknown) {
      if (!mounted.current) return;
      if (error instanceof ApiError && error.status === 401) { void refreshUser(); return; }
      const feedback = validationFeedback(error);
      const mapped: HostedZoneFormErrors = {};
      for (const field of ["name", "comment", "zone_type", "region", "vpc_id"] as const) {
        if (feedback.fields[field]) mapped[field] = feedback.fields[field];
      }
      setErrors(mapped);
      setFailure(feedback.messages.length ? feedback.messages.join(" ") : error instanceof ApiError && error.status === 404
        ? "The hosted zone no longer exists or you don't have access to it."
        : error instanceof ApiError && error.status === 409 ? error.message
        : "The request could not be completed. Your entries have been kept. Try again.");
    } finally {
      // Keep successful submissions locked until navigation unmounts the form.
      if (!saved) {
        pending.current = false;
        if (mounted.current) setSubmitting(false);
      }
    }
  }

  return (
    <ContentLayout disableOverlap header={<Header variant="h1">{creating ? "Create hosted zone" : "Edit hosted zone"}</Header>}>
        <form onSubmit={submit} noValidate>
          <Form actions={<SpaceBetween direction="horizontal" size="xs">
            <Button formAction="none" variant="link" disabled={submitting} onClick={() => router.push(cancelHref)}>Cancel</Button>
            <Button variant="primary" formAction="submit" loading={submitting}
              loadingText={creating ? "Creating hosted zone" : "Saving hosted zone"}>{creating ? "Create hosted zone" : "Save changes"}</Button>
          </SpaceBetween>}>
            <SpaceBetween size="l">
              {failure && <div role="alert"><Alert type="error" header={creating ? "Unable to create hosted zone" : "Unable to update hosted zone"}>{failure}</Alert></div>}
              <Container header={<Header variant="h2">Hosted zone configuration</Header>}>
                <SpaceBetween size="l">
                  <FormField label="Domain name" controlId="zone-name" errorText={errors.name}
                    description="Enter a domain name such as example.com. Do not include a protocol.">
                    <Input controlId="zone-name" value={values.name} onChange={({ detail }) => change("name", detail.value)}
                      placeholder="example.com" ariaRequired readOnly={submitting} disableBrowserAutocorrect spellcheck={false} />
                  </FormField>
                  <FormField label="Description - optional" controlId="zone-comment" errorText={errors.comment} constraintText="Maximum 1024 characters.">
                    <Textarea controlId="zone-comment" value={values.comment} onChange={({ detail }) => change("comment", detail.value)}
                      rows={3} resize="vertical" readOnly={submitting} />
                  </FormField>
                  <FormField label="Type" errorText={errors.zone_type}
                    description={creating ? undefined : "Hosted zone type cannot be changed after creation."}>
                    {creating ? <RadioGroup value={values.zone_type} readOnly={submitting} items={[
                      { value: "PUBLIC", label: "Public hosted zone", description: "Routes traffic on the internet." },
                      { value: "PRIVATE", label: "Private hosted zone", description: "Routes traffic within a VPC." },
                    ]} onChange={({ detail }) => {
                      if (detail.value !== "PUBLIC" && detail.value !== "PRIVATE") return;
                      setValues((previous) => ({ ...previous, zone_type: detail.value === "PRIVATE" ? "PRIVATE" : "PUBLIC", region: "", vpc_id: "" }));
                      setErrors({}); setFailure(null);
                    }} /> : <Box>{values.zone_type === "PRIVATE" ? "Private hosted zone" : "Public hosted zone"}</Box>}
                  </FormField>
                </SpaceBetween>
              </Container>
              {values.zone_type === "PRIVATE" && <Container header={<Header variant="h2" description="Associate a VPC with this private hosted zone.">VPC association</Header>}>
                <SpaceBetween size="l">
                  <FormField label="Region" controlId="zone-region" errorText={errors.region}>
                    <Select controlId="zone-region" options={[...HOSTED_ZONE_REGIONS]} placeholder="Choose a region"
                      selectedOption={HOSTED_ZONE_REGIONS.find((option) => option.value === values.region) ?? null}
                      ariaRequired disabled={submitting} onChange={({ detail }) => change("region", detail.selectedOption.value ?? "")} />
                  </FormField>
                  <FormField label="VPC ID" controlId="zone-vpc_id" errorText={errors.vpc_id}
                    description="Enter the VPC ID associated with this private hosted zone.">
                    <Input controlId="zone-vpc_id" value={values.vpc_id} placeholder="vpc-0123456789abcdef"
                      ariaRequired readOnly={submitting} spellcheck={false} onChange={({ detail }) => change("vpc_id", detail.value)} />
                  </FormField>
                </SpaceBetween>
              </Container>}
            </SpaceBetween>
          </Form>
        </form>
    </ContentLayout>
  );
}
