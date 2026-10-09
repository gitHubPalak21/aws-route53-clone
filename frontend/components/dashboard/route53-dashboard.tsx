"use client";

import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Container from "@cloudscape-design/components/container";
import ContentLayout from "@cloudscape-design/components/content-layout";
import Header from "@cloudscape-design/components/header";
import Link from "@cloudscape-design/components/link";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Spinner from "@cloudscape-design/components/spinner";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import { useRouter } from "next/navigation";
import { useHostedZones } from "@/hooks/use-hosted-zones";
import { ROUTE53_PAGES } from "@/lib/constants/navigation";

const services = [
  { page: ROUTE53_PAGES.healthChecks, title: "Health checks" },
  { page: ROUTE53_PAGES.trafficPolicies, title: "Traffic flow" },
  { page: ROUTE53_PAGES.resolver, title: "Resolver" },
  { page: ROUTE53_PAGES.profiles, title: "Profiles" },
];

export function Route53Dashboard() {
  const router = useRouter();
  // Use the owner-scoped collection total without downloading the collection.
  const { data, isLoading, error, refetch } = useHostedZones({ page: 1, page_size: 1 });
  const zonesHref = ROUTE53_PAGES.hostedZones.href;
  const createHref = `${zonesHref}/create`;

  return <ContentLayout disableOverlap header={
    <Header variant="h1" description={ROUTE53_PAGES.dashboard.description}>Route 53</Header>
  }>
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">DNS management</Header>}>
        <SpaceBetween size="m">
          {isLoading ? <div role="status"><SpaceBetween direction="horizontal" size="xs">
            <Spinner /><span>Loading hosted zone summary</span>
          </SpaceBetween></div> : error ? <Alert type="error" header="Unable to load hosted zone summary"
            action={<Button onClick={refetch}>Retry</Button>}>Try again to view the hosted zone count.</Alert>
            : data && <div><Box variant="strong">Hosted zones</Box>
              <Box>{data.total.toLocaleString("en-US")} {data.total === 1 ? "hosted zone" : "hosted zones"}</Box>
            </div>}
          <Box>Create and manage hosted zones and DNS records for your domains.</Box>
          <SpaceBetween direction="horizontal" size="xs">
            <Button href={zonesHref} onFollow={(event) => { event.preventDefault(); router.push(zonesHref); }}>View hosted zones</Button>
            <Button variant="primary" href={createHref} onFollow={(event) => { event.preventDefault(); router.push(createHref); }}>Create hosted zone</Button>
          </SpaceBetween>
        </SpaceBetween>
      </Container>
      <ColumnLayout columns={2}>
        {services.map(({ page, title }) => <Container key={page.href} header={<Header variant="h2">{title}</Header>}>
          <SpaceBetween size="m">
            <StatusIndicator type="not-started">Outside demonstration scope</StatusIndicator>
            <Box>{page.description}</Box>
            <Link href={page.href} onFollow={(event) => { event.preventDefault(); router.push(page.href); }}>Open {page.title.toLowerCase()}</Link>
          </SpaceBetween>
        </Container>)}
      </ColumnLayout>
    </SpaceBetween>
  </ContentLayout>;
}
