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
  | "Decommission rejected"
  | "Decommissioning"
  | "Decommissioned";

export interface HistoryEntry {
  status: HistoryStatus;
  date: string;
  note: string;
}

/** Tags applied to the resource group by Terraform. */
export type SandboxTags = Record<string, string>;

export type SandboxOperation = "provision" | "extension" | "decommission";

export interface Sandbox {
  id: string;
  name: string;
  workload: string;
  type: "Subscription" | "Resource Group";
  status: SandboxStatus;
  businessUnit: string;
  costCenter: string;
  budget: number;
  spent: number;
  region: string;
  owner: string;
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
  /** Cumulative spend in INR, one value per week. */
  spendHistory?: number[];
  rejectionReason?: string | null;
  expiry?: string | null;
  daysLeft?: number | null;
  requestedOn?: string | null;
  durationDays?: number | null;
  /** Azure role granted on the resource group. */
  role?: string;
  /** Terraform key, e.g. eng-salman-001. */
  sandboxKey?: string;
  failedOperation?: SandboxOperation | null;
  operationInProgress?: SandboxOperation | null;
  decommissionPending?: boolean;
  decommissionReason?: string | null;
  decommissionRequestedBy?: string | null;
  /** Provisioned before the portal and imported from Terraform. */
  imported?: boolean;
}

export interface Notification {
  id: string;
  category: "Budget" | "Approval";
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
  extraDays: 30 | 60;
  reason: string;
  requestedOn: string;
  status: ExtensionStatus;
  decisionBy?: string | null;
  decisionReason?: string | null;
}

/** Email used by the signed-in requestor's own demo sandboxes. */
export const DEMO_REQUESTOR_EMAIL = "you@company.com";
const DEMO_REQUESTOR_NAME = "Demo User";
const ADMIN_EMAIL = "it.admin@company.com";

export const sandboxes: Sandbox[] = [
  {
    id: "SBX-1001",
    name: "sbx-eng-001",
    requestorName: DEMO_REQUESTOR_NAME,
    requestorEmail: DEMO_REQUESTOR_EMAIL,
    description: "AKS cluster to compare service mesh options",
    justification:
      "Evaluate Istio vs Linkerd on AKS before the platform team commits to one for production.",
    workload: "Containers / AKS",
    type: "Subscription",
    status: "Active",
    businessUnit: "Engineering",
    costCenter: "CC-1010",
    budget: 500,
    spent: 212.4,
    region: "East US",
    owner: "you@company.com",
    tags: {
      Owner: "you@company.com",
      BusinessUnit: "Engineering",
      CostCenter: "CC-1010",
      Environment: "Sandbox",
      ExpiryDate: "2026-12-17",
      Workload: "Containers / AKS",
    },
    history: [
      { status: "Submitted", date: "16 Oct 2026", note: "Request routed to IT Administrators" },
      { status: "Approved", date: "17 Oct 2026", note: "Approved by IT Administrators" },
      { status: "Provisioning", date: "17 Oct 2026", note: "Terraform run via GitHub Actions" },
      { status: "Active", date: "18 Oct 2026", note: "Subscription ready, Contributor role assigned" },
    ],
    resourceId: "/subscriptions/3f2a9c1e-7b4d-4e8a-9c61-2d5f8a7b1001",
    spendHistory: [12.5, 31.8, 58.2, 84.9, 118.3, 149.6, 181.7, 212.4],
    expiry: "17 Dec 2026",
    daysLeft: 40,
  },
  {
    id: "SBX-1002",
    name: "rg-sbx-eng-002",
    requestorName: DEMO_REQUESTOR_NAME,
    requestorEmail: DEMO_REQUESTOR_EMAIL,
    description: "Customer portal API prototype on App Service",
    justification:
      "Prototype the customer portal API to validate the auth flow and scaling behaviour under load.",
    workload: "Web Apps & APIs",
    type: "Resource Group",
    status: "Expiring",
    businessUnit: "Engineering",
    costCenter: "CC-1010",
    budget: 800,
    spent: 735.1,
    region: "West Europe",
    owner: "you@company.com",
    tags: {
      Owner: "you@company.com",
      BusinessUnit: "Engineering",
      CostCenter: "CC-1010",
      Environment: "Sandbox",
      ExpiryDate: "2026-11-12",
      Workload: "Web Apps & APIs",
    },
    history: [
      { status: "Submitted", date: "10 Oct 2026", note: "Request routed to IT Administrators" },
      { status: "Approved", date: "11 Oct 2026", note: "Approved by IT Administrators" },
      { status: "Provisioning", date: "12 Oct 2026", note: "Terraform run via GitHub Actions" },
      { status: "Active", date: "12 Oct 2026", note: "Resource group ready, Contributor role assigned" },
    ],
    resourceId:
      "/subscriptions/8c4e1b7d-2a9f-4d36-b5e0-6f1c3a9d0002/resourceGroups/rg-sbx-eng-002",
    spendHistory: [64.2, 158.9, 247.5, 339.8, 446.1, 541.7, 642.3, 735.1],
    expiry: "12 Nov 2026",
    daysLeft: 5,
  },
  {
    id: "SBX-1003",
    name: "sbx-eng-003",
    requestorName: DEMO_REQUESTOR_NAME,
    requestorEmail: DEMO_REQUESTOR_EMAIL,
    description: "VM size benchmarks for the nightly batch job",
    justification:
      "Benchmark VM sizes for the nightly batch job to find a cheaper SKU that still meets the SLA.",
    workload: "Compute / Virtual Machines",
    type: "Subscription",
    status: "Pending",
    businessUnit: "Engineering",
    costCenter: "CC-1010",
    budget: 500,
    spent: 0,
    region: "Central India",
    owner: "you@company.com",
    tags: {
      Owner: "you@company.com",
      BusinessUnit: "Engineering",
      CostCenter: "CC-1010",
      Environment: "Sandbox",
      ExpiryDate: "2026-12-06",
      Workload: "Compute / Virtual Machines",
    },
    history: [
      { status: "Submitted", date: "06 Nov 2026", note: "Request routed to IT Administrators" },
    ],
    requestedOn: "06 Nov 2026",
    durationDays: 30,
  },
  {
    id: "SBX-0998",
    name: "sbx-eng-000",
    requestorName: DEMO_REQUESTOR_NAME,
    requestorEmail: DEMO_REQUESTOR_EMAIL,
    description: "Synapse proof of concept for finance reporting",
    justification:
      "Consolidate finance reporting data from three source systems into a single Synapse workspace.",
    decisionBy: ADMIN_EMAIL,
    decisionReason:
      "Requested budget of $3,000 exceeds the $500 sandbox default without director approval. Resubmit with a lower budget or attach approval.",
    workload: "Data & Analytics",
    type: "Subscription",
    status: "Rejected",
    businessUnit: "Engineering",
    costCenter: "CC-1010",
    budget: 3000,
    spent: 0,
    region: "East US",
    owner: "you@company.com",
    tags: {
      Owner: "you@company.com",
      BusinessUnit: "Engineering",
      CostCenter: "CC-1010",
      Environment: "Sandbox",
      ExpiryDate: "2026-10-17",
      Workload: "Data & Analytics",
    },
    rejectionReason:
      "Requested budget of $3,000 exceeds the $500 sandbox default without director approval. Resubmit with a lower budget or attach approval.",
    history: [
      { status: "Submitted", date: "18 Aug 2026", note: "Request routed to IT Administrators" },
      { status: "Rejected", date: "20 Aug 2026", note: "Rejected by IT Administrators" },
    ],
  },
];

export const notifications: Notification[] = [
  {
    id: "n1",
    category: "Budget",
    title: "Budget alert (75%) — rg-sbx-eng-002",
    to: "you@company.com",
    when: "26 Oct, 21:34",
  },
  {
    id: "n2",
    category: "Budget",
    title: "Budget WARNING (90%) — rg-sbx-eng-002",
    to: "you@company.com; sandbox-admins@company.com",
    when: "04 Nov, 21:34",
  },
  {
    id: "n3",
    category: "Approval",
    title: "Sandbox request rejected — SBX-0998",
    to: "you@company.com",
    when: "20 Aug, 21:34",
  },
];

// ---------------------------------------------------------------------------
// Admin demo data: sandboxes requested by other users.
// ---------------------------------------------------------------------------

const SPEND_CURVE = [0.06, 0.15, 0.27, 0.39, 0.52, 0.66, 0.83, 1];

type AdminSeed = Pick<
  Sandbox,
  | "id"
  | "name"
  | "workload"
  | "type"
  | "status"
  | "businessUnit"
  | "costCenter"
  | "budget"
  | "region"
  | "requestorName"
  | "requestorEmail"
  | "description"
  | "justification"
  | "durationDays"
> &
  Partial<
    Pick<
      Sandbox,
      "spent" | "expiry" | "daysLeft" | "pipelineRunUrl" | "provisioningNote" | "decisionReason"
    >
  > & { requestedOn: string; expiryIso: string };

function seedHistory(status: SandboxStatus, date: string): HistoryEntry[] {
  const submitted: HistoryEntry = { status: "Submitted", date, note: "Request routed to IT Administrators" };
  const approved: HistoryEntry = { status: "Approved", date, note: `Approved by ${ADMIN_EMAIL}` };
  const provisioning: HistoryEntry = { status: "Provisioning", date, note: "Terraform run via GitHub Actions" };

  switch (status) {
    case "Pending":
      return [submitted];
    case "Provisioning":
      return [submitted, approved];
    case "Failed":
      return [submitted, approved, { ...provisioning, note: "Terraform run failed in GitHub Actions" }];
    case "Rejected":
      return [submitted, { status: "Rejected", date, note: "Rejected by IT Administrators" }];
    default:
      return [submitted, approved, provisioning, { status: "Active", date, note: "Sandbox ready, Contributor role assigned" }];
  }
}

function seed({ expiryIso, ...s }: AdminSeed): Sandbox {
  const live = s.status === "Active" || s.status === "Expiring";
  const spent = s.spent ?? 0;
  const subscription = `/subscriptions/6d0e4c1a-93b2-4f5e-8a7c-${s.id.replace("SBX-", "").padStart(12, "0")}`;

  return {
    ...s,
    spent,
    owner: s.requestorEmail,
    tags: {
      Owner: s.requestorEmail,
      BusinessUnit: s.businessUnit,
      CostCenter: s.costCenter,
      Environment: "Sandbox",
      ExpiryDate: expiryIso,
      Workload: s.workload,
    },
    history: seedHistory(s.status, s.requestedOn),
    decisionBy: s.status === "Pending" ? undefined : ADMIN_EMAIL,
    rejectionReason: s.status === "Rejected" ? s.decisionReason : undefined,
    ...(live
      ? {
          resourceId:
            s.type === "Subscription" ? subscription : `${subscription}/resourceGroups/${s.name}`,
          spendHistory: SPEND_CURVE.map((f) => Math.round(spent * f * 100) / 100),
        }
      : {}),
  };
}

const PIPELINE_RUNS = "https://github.com/company/sandbox-iac/actions/runs";

export const adminRequests: Sandbox[] = [
  // Pending
  seed({
    id: "SBX-0951",
    name: "sbx-fin-priya-004",
    workload: "Data & Analytics",
    type: "Subscription",
    status: "Pending",
    businessUnit: "Finance",
    costCenter: "CC-2040",
    budget: 1500,
    region: "West Europe",
    requestorName: "Priya Nair",
    requestorEmail: "priya.nair@company.com",
    description: "Databricks workspace for month-end forecasting models",
    justification:
      "Test whether Databricks can cut the month-end close forecast run from 6 hours to under 1 hour.",
    requestedOn: "31 Oct 2026",
    durationDays: 60,
    expiryIso: "2026-12-30",
  }),
  seed({
    id: "SBX-0952",
    name: "rg-sbx-ope-marcus-002",
    workload: "Compute / Virtual Machines",
    type: "Resource Group",
    status: "Pending",
    businessUnit: "Operations",
    costCenter: "CC-3015",
    budget: 500,
    region: "East US",
    requestorName: "Marcus Webb",
    requestorEmail: "marcus.webb@company.com",
    description: "Windows Server VMs to test the new patching runbook",
    justification:
      "Validate the automated patching runbook on Windows Server 2025 before it rolls out to production.",
    requestedOn: "04 Nov 2026",
    durationDays: 30,
    expiryIso: "2026-12-04",
  }),
  seed({
    id: "SBX-0953",
    name: "sbx-mar-elena-001",
    workload: "Web Apps & APIs",
    type: "Subscription",
    status: "Pending",
    businessUnit: "Marketing",
    costCenter: "CC-4100",
    budget: 800,
    region: "Central India",
    requestorName: "Elena Rossi",
    requestorEmail: "elena.rossi@company.com",
    description: "Campaign landing page with A/B testing",
    justification:
      "Run an A/B test of the new campaign landing page with Front Door and App Service before launch.",
    requestedOn: "07 Nov 2026",
    durationDays: 90,
    expiryIso: "2027-02-05",
  }),
  // Provisioning
  seed({
    id: "SBX-0947",
    name: "sbx-dat-kenji-006",
    workload: "AI / Machine Learning",
    type: "Subscription",
    status: "Provisioning",
    businessUnit: "Data & Analytics",
    costCenter: "CC-5020",
    budget: 2500,
    region: "West US 2",
    requestorName: "Kenji Tanaka",
    requestorEmail: "kenji.tanaka@company.com",
    description: "Azure OpenAI evaluation for document summarisation",
    justification:
      "Evaluate Azure OpenAI models for summarising support tickets and measure accuracy against a labelled set.",
    requestedOn: "02 Nov 2026",
    durationDays: 60,
    expiryIso: "2027-01-07",
    pipelineRunUrl: `${PIPELINE_RUNS}/9876543210`,
  }),
  // Failed
  seed({
    id: "SBX-0945",
    name: "rg-sbx-eng-aisha-003",
    workload: "Networking",
    type: "Resource Group",
    status: "Failed",
    businessUnit: "Engineering",
    costCenter: "CC-1020",
    budget: 700,
    region: "East US",
    requestorName: "Aisha Khan",
    requestorEmail: "aisha.khan@company.com",
    description: "Hub-spoke network with Azure Firewall",
    justification:
      "Prototype a hub-spoke topology with Azure Firewall to validate the proposed landing zone network design.",
    requestedOn: "01 Nov 2026",
    durationDays: 30,
    expiryIso: "2026-12-03",
    pipelineRunUrl: `${PIPELINE_RUNS}/9876543102`,
    provisioningNote:
      "Terraform apply failed: quota exceeded for Standard DSv5 vCPUs in East US (requested 16, available 8).",
  }),
  // Active
  seed({
    id: "SBX-0931",
    name: "sbx-eng-daniel-002",
    workload: "Containers / AKS",
    type: "Subscription",
    status: "Active",
    businessUnit: "Engineering",
    costCenter: "CC-1020",
    budget: 1000,
    spent: 412.6,
    region: "West Europe",
    requestorName: "Daniel Okafor",
    requestorEmail: "daniel.okafor@company.com",
    description: "AKS with KEDA for event-driven workers",
    justification:
      "Prove that KEDA autoscaling can replace the fixed worker pool and reduce idle compute for queue processing.",
    requestedOn: "18 Sep 2026",
    durationDays: 90,
    expiry: "20 Dec 2026",
    daysLeft: 42,
    expiryIso: "2026-12-20",
  }),
  seed({
    id: "SBX-0934",
    name: "rg-sbx-fin-oliver-001",
    workload: "Web Apps & APIs",
    type: "Resource Group",
    status: "Active",
    businessUnit: "Finance",
    costCenter: "CC-2040",
    budget: 500,
    spent: 468.9,
    region: "East US",
    requestorName: "Oliver Brown",
    requestorEmail: "oliver.brown@company.com",
    description: "Expense approval API prototype",
    justification:
      "Build an expense approval API prototype to check integration with the ERP system's webhook model.",
    requestedOn: "01 Oct 2026",
    durationDays: 60,
    expiry: "30 Nov 2026",
    daysLeft: 22,
    expiryIso: "2026-11-30",
  }),
  seed({
    id: "SBX-0938",
    name: "sbx-dat-sofia-003",
    workload: "Data & Analytics",
    type: "Subscription",
    status: "Active",
    businessUnit: "Data & Analytics",
    costCenter: "CC-5020",
    budget: 3000,
    spent: 1284.3,
    region: "West US 2",
    requestorName: "Sofia Alvarez",
    requestorEmail: "sofia.alvarez@company.com",
    description: "Fabric lakehouse for sales analytics",
    justification:
      "Evaluate Microsoft Fabric as a replacement for the on-premises sales data warehouse and its nightly ETL.",
    requestedOn: "07 Oct 2026",
    durationDays: 90,
    expiry: "05 Jan 2027",
    daysLeft: 58,
    expiryIso: "2027-01-05",
  }),
  seed({
    id: "SBX-0940",
    name: "rg-sbx-ope-liam-004",
    workload: "Compute / Virtual Machines",
    type: "Resource Group",
    status: "Active",
    businessUnit: "Operations",
    costCenter: "CC-3020",
    budget: 600,
    spent: 187.2,
    region: "Central India",
    requestorName: "Liam Murphy",
    requestorEmail: "liam.murphy@company.com",
    description: "Linux VMs for monitoring agent rollout tests",
    justification:
      "Test the Azure Monitor Agent migration on Linux VMs and confirm no gaps in the existing alert rules.",
    requestedOn: "15 Oct 2026",
    durationDays: 60,
    expiry: "15 Dec 2026",
    daysLeft: 37,
    expiryIso: "2026-12-15",
  }),
  // Expiring
  seed({
    id: "SBX-0925",
    name: "sbx-mar-chloe-002",
    workload: "AI / Machine Learning",
    type: "Subscription",
    status: "Expiring",
    businessUnit: "Marketing",
    costCenter: "CC-4110",
    budget: 1200,
    spent: 1096.8,
    region: "West Europe",
    requestorName: "Chloe Martin",
    requestorEmail: "chloe.martin@company.com",
    description: "Product image generation experiments",
    justification:
      "Experiment with image generation models for product imagery and measure cost per approved asset.",
    requestedOn: "14 Aug 2026",
    durationDays: 90,
    expiry: "12 Nov 2026",
    daysLeft: 4,
    expiryIso: "2026-11-12",
  }),
  seed({
    id: "SBX-0927",
    name: "rg-sbx-eng-ravi-005",
    workload: "Containers / AKS",
    type: "Resource Group",
    status: "Expiring",
    businessUnit: "Engineering",
    costCenter: "CC-1030",
    budget: 800,
    spent: 512.4,
    region: "East US",
    requestorName: "Ravi Patel",
    requestorEmail: "ravi.patel@company.com",
    description: "Container Apps migration spike",
    justification:
      "Assess moving three internal services from AKS to Container Apps to reduce cluster maintenance effort.",
    requestedOn: "15 Sep 2026",
    durationDays: 60,
    expiry: "14 Nov 2026",
    daysLeft: 6,
    expiryIso: "2026-11-14",
  }),
  // Rejected
  seed({
    id: "SBX-0942",
    name: "sbx-fin-noah-002",
    workload: "Compute / Virtual Machines",
    type: "Subscription",
    status: "Rejected",
    businessUnit: "Finance",
    costCenter: "CC-2050",
    budget: 3000,
    region: "East US",
    requestorName: "Noah Fischer",
    requestorEmail: "noah.fischer@company.com",
    description: "GPU VMs for risk simulation",
    justification:
      "Run Monte Carlo risk simulations on GPU VMs to compare runtime against the current CPU cluster.",
    requestedOn: "28 Oct 2026",
    durationDays: 30,
    expiryIso: "2026-11-27",
    decisionReason:
      "GPU SKUs are not allowed in sandboxes under the current policy. Please raise a project request through the CCoE instead.",
  }),
];

export const extensionRequests: ExtensionRequest[] = [
  {
    id: "EXT-203",
    sandboxId: "SBX-0925",
    sandboxName: "sbx-mar-chloe-002",
    requestorName: "Chloe Martin",
    requestorEmail: "chloe.martin@company.com",
    extraDays: 30,
    reason: "Waiting on brand team sign-off before the final round of image tests.",
    requestedOn: "06 Nov 2026",
    status: "Pending",
  },
  {
    id: "EXT-202",
    sandboxId: "SBX-0927",
    sandboxName: "rg-sbx-eng-ravi-005",
    requestorName: "Ravi Patel",
    requestorEmail: "ravi.patel@company.com",
    extraDays: 60,
    reason: "Third service migration slipped; need time to load test before the go/no-go review.",
    requestedOn: "07 Nov 2026",
    status: "Pending",
  },
  {
    id: "EXT-201",
    sandboxId: "SBX-0934",
    sandboxName: "rg-sbx-fin-oliver-001",
    requestorName: "Oliver Brown",
    requestorEmail: "oliver.brown@company.com",
    extraDays: 30,
    reason: "ERP vendor moved the webhook sandbox release to December.",
    requestedOn: "05 Nov 2026",
    status: "Pending",
  },
  {
    id: "EXT-198",
    sandboxId: "SBX-0931",
    sandboxName: "sbx-eng-daniel-002",
    requestorName: "Daniel Okafor",
    requestorEmail: "daniel.okafor@company.com",
    extraDays: 60,
    reason: "Want to keep the cluster for the next quarter's demos.",
    requestedOn: "20 Oct 2026",
    status: "Rejected",
    decisionBy: ADMIN_EMAIL,
    decisionReason:
      "Sandboxes are for experiments, not long-running demos. Please request a shared demo environment instead.",
  },
];