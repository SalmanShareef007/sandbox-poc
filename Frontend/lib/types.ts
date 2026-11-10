export type SandboxStatus =
  | "Active"
  | "Expiring"
  | "Pending"
  | "Provisioning"
  | "Failed"
  | "Rejected"
  | "Expired"
  | "Decommissioning"
  | "Decommissioned";

export type HistoryStatus =
  | "Submitted"
  | "Approved"
  | "Rejected"
  | "Provisioning"
  | "Active"
  | "Failed"
  | "Extension requested"
  | "Extension approved"
  | "Extension rejected"
  | "Extension applied"
  | "Decommission requested"
  | "Cleanup flagged"
  | "Decommission rejected"
  | "Decommissioning"
  | "Decommissioned";

export interface HistoryEntry {
  status: HistoryStatus;
  date: string;
  note: string;
}

export type SandboxTags = Record<string, string>;
export type SandboxOperation = "provision" | "extension" | "decommission";

export interface Sandbox {
  id: string;
  name: string;
  workload: string;
  type: "Subscription" | "Resource Group";
  status: SandboxStatus;
  businessUnit: string;
  businessUnitCode?: string | null;
  subscriptionId?: string;
  costCenter: string;
  budget: number;
  spent: number | null;
  costCurrency?: string;
  budgetCurrency?: string;
  costUpdatedAt?: string | null;
  costStatus?: "available" | "stale" | "unavailable";
  pendingExpiry?: string | null;
  region: string;
  owner: string;
  managerEmail?: string | null;
  tags: SandboxTags;
  history: HistoryEntry[];
  requestorName: string;
  requestorEmail: string;
  justification: string;
  description: string;
  pipelineRunUrl?: string;
  provisioningNote?: string | null;
  decisionBy?: string | null;
  decisionReason?: string | null;
  resourceId?: string | null;
  spendHistory?: number[];
  rejectionReason?: string | null;
  expiry?: string | null;
  daysLeft?: number | null;
  requestedOn?: string | null;
  durationDays?: number | null;
  role?: string;
  sandboxKey?: string;
  failedOperation?: SandboxOperation | null;
  operationInProgress?: SandboxOperation | null;
  decommissionPending?: boolean;
  decommissionReason?: string | null;
  decommissionRequestedBy?: string | null;
  imported?: boolean;
  expiryDate?: string | null;
  cleanupFlagged?: boolean;
  cleanupEligibleOn?: string | null;
}

export interface Notification {
  id: string;
  category: "Budget" | "Approval" | "Lifecycle";
  title: string;
  to: string;
  when: string;
}

export type ExtensionStatus = "Pending" | "Approved" | "Rejected";

export interface ExtensionRequest {
  id: string;
  sandboxId: string;
  sandboxName: string;
  requestorName: string;
  requestorEmail: string;
  extraDays: number;
  requestedExpiry?: string | null;
  reason: string;
  requestedOn: string;
  status: ExtensionStatus;
  decisionBy?: string | null;
  decisionReason?: string | null;
}

export interface BusinessUnit {
  id: string;
  name: string;
  shortCode: string;
  costCenters: string[];
  active: boolean;
}

export interface PlatformConfiguration {
  subscriptionId: string;
  subscriptionName?: string | null;
  subscriptionChangePending: boolean;
  subscriptionChangeError?: string | null;
  maxBudget: number;
  budgetCurrency: string;
  environment: string;
  budgetAlertThresholds: number[];
  businessUnits: BusinessUnit[];
  costCenterMode: "business_unit" | "shared" | "free_text";
  sharedCostCenters: string[];
  regions: string[];
  roles: string[];
  durations: number[];
  extensionDays: number[];
  maxExtensionDays: number;
  expiryGraceDays: number;
  expiryReminderDays: number;
  adminCleanupApprovalRequired: boolean;
}