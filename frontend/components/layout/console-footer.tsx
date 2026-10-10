import Icon from "@cloudscape-design/components/icon";
import Link from "@cloudscape-design/components/link";

/** Console chrome only; links lead to official information, never fake tools. */
export function ConsoleFooter() {
  return <footer id="console-footer" className="console-footer">
    <nav className="console-footer-tools" aria-label="AWS console resources">
      <span className="console-footer-tool" title="CloudShell is outside this demonstration"><Icon name="command-prompt" />CloudShell</span>
      <span className="console-footer-optional" title="Agent Toolkit is outside this demonstration">Agent Toolkit for AWS</span>
      <Link fontSize="body-s" href="https://github.com/gitHubPalak21/aws-route53-clone/issues" target="_blank">Feedback</Link>
      <Link fontSize="body-s" href="https://aws.amazon.com/console/mobile/" target="_blank" className="console-footer-optional">Console Mobile App</Link>
    </nav>
    <nav className="console-footer-legal" aria-label="Legal and project information">
      <span>© 2026 Route 53 Clone · Unaffiliated demonstration</span>
      <Link fontSize="body-s" href="https://aws.amazon.com/privacy/" target="_blank">Privacy</Link>
      <Link fontSize="body-s" href="https://aws.amazon.com/terms/" target="_blank">Terms</Link>
      <Link fontSize="body-s" href="https://aws.amazon.com/legal/cookies/" target="_blank">Cookie notice</Link>
    </nav>
  </footer>;
}
