import { SEVERITY_CONFIG } from "@/lib/severity";
import type { Severity } from "@/lib/types";
import { Badge } from "./Badge";

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge config={SEVERITY_CONFIG[severity]} />;
}
