import HelpPanel from "@cloudscape-design/components/help-panel";
import Link from "@cloudscape-design/components/link";
import SpaceBetween from "@cloudscape-design/components/space-between";

export function Route53HelpPanel() {
  return <HelpPanel header={<h2>Route 53</h2>}>
    <SpaceBetween size="m">
      <p>Manage hosted zones and DNS records. This demonstration does not host DNS or provision AWS resources.</p>
      <Link external href="https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/Welcome.html" target="_blank">Route 53 Developer Guide</Link>
    </SpaceBetween>
  </HelpPanel>;
}
