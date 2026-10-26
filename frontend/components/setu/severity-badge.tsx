import { AlertCircle, Info, Siren, TriangleAlert } from "lucide-react";
import type { Severity } from "@/lib/schemas";

const severityView = {
  CRITICAL: { label: "Critical", icon: Siren, className: "severity-critical" },
  HIGH: { label: "High", icon: TriangleAlert, className: "severity-high" },
  MEDIUM: { label: "Medium", icon: AlertCircle, className: "severity-medium" },
  LOW: { label: "Low", icon: Info, className: "severity-low" },
} satisfies Record<Severity, { label: string; icon: typeof Info; className: string }>;

export function SeverityBadge({ severity }: { severity: Severity }) {
  const view = severityView[severity];
  const Icon = view.icon;
  return <span className={`severity-badge ${view.className}`}><Icon size={15} aria-hidden="true" />{view.label}</span>;
}
