import { HOSTED_ZONE_REGIONS } from "@/lib/constants/regions";
import type { HostedZone, HostedZoneType, HostedZoneWrite } from "@/types/hosted-zone";

export interface HostedZoneFormValues {
  name: string;
  comment: string;
  zone_type: HostedZoneType;
  region: string;
  vpc_id: string;
}
export type HostedZoneFormErrors = Partial<Record<keyof HostedZoneFormValues, string>>;

export function formValues(zone?: HostedZone): HostedZoneFormValues {
  return { name: zone?.name ?? "", comment: zone?.comment ?? "", zone_type: zone?.zone_type ?? "PUBLIC",
    region: zone?.region ?? "", vpc_id: zone?.vpc_id ?? "" };
}

export function zonePayload(values: HostedZoneFormValues): HostedZoneWrite {
  return { name: values.name.trim().toLowerCase().replace(/\.$/, ""), comment: values.comment.trim() || null,
    zone_type: values.zone_type, region: values.zone_type === "PRIVATE" ? values.region : null,
    vpc_id: values.zone_type === "PRIVATE" ? values.vpc_id.trim() : null };
}

export function validateZoneForm(values: HostedZoneFormValues): HostedZoneFormErrors {
  const payload = zonePayload(values);
  const errors: HostedZoneFormErrors = {};
  if (!payload.name) errors.name = "Enter a domain name.";
  else if (payload.name.length > 253 || payload.name.split(".").some((label) => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) {
    errors.name = "Enter an ASCII domain name such as example.com, without spaces or a protocol.";
  }
  if ((payload.comment?.length ?? 0) > 1024) errors.comment = "Use at most 1024 characters.";
  if (values.zone_type === "PRIVATE") {
    if (!HOSTED_ZONE_REGIONS.some((option) => option.value === values.region)) errors.region = "Select a region.";
    if (!/^vpc-[0-9a-f]{8,17}$/.test(payload.vpc_id ?? "")) errors.vpc_id = "Enter a VPC ID with vpc- followed by 8–17 lowercase hexadecimal characters.";
  }
  return errors;
}
