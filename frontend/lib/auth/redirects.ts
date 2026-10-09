import { ROUTE53_PAGES } from "@/lib/constants/navigation";

const allowedDestinations: readonly string[] = Object.values(ROUTE53_PAGES).map((page) => page.href);

/** Only known service paths may be used; URLs, encoded paths and queries are rejected. */
export function safeReturnTo(destination: string | null): string {
  return destination && allowedDestinations.includes(destination)
    ? destination
    : ROUTE53_PAGES.dashboard.href;
}

export function loginDestination(pathname: string): string {
  const destination = safeReturnTo(pathname);
  return destination === ROUTE53_PAGES.dashboard.href
    ? "/login"
    : `/login?next=${encodeURIComponent(destination)}`;
}
