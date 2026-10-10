import ContentLayout from "@cloudscape-design/components/content-layout";
import Header from "@cloudscape-design/components/header";
import Box from "@cloudscape-design/components/box";
import Container from "@cloudscape-design/components/container";
import SpaceBetween from "@cloudscape-design/components/space-between";
import type { Route53PageDefinition } from "@/lib/constants/navigation";

/** Consistent service availability page within the existing console shell. */
export function Route53PageContent({ page }: { page: Route53PageDefinition }) {
  return (
    <ContentLayout
      disableOverlap
      header={
        <Header variant="h1">
          {page.title}
        </Header>
      }
    >
      <Container header={<Header variant="h2">About {page.title.toLowerCase()}</Header>}>
        <SpaceBetween size="m">
          <Box>{page.description}</Box>
          <Box color="text-body-secondary">This demonstration focuses on hosted zones and DNS records.</Box>
        </SpaceBetween>
      </Container>
    </ContentLayout>
  );
}
