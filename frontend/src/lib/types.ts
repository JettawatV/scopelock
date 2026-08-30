export type ModuleQuantity = {
  module_key: string;
  quantity: number;
};

export type PriceLineItem = {
  module_key: string;
  quantity: number;
  unit_rule: string;
  unit?: string | null;
  unit_amount_usd: number;
  subtotal_usd: number;
  currency: "USD";
  sop_version: string;
};

export type PricingResult = {
  currency: "USD";
  sop_version: string;
  line_items: PriceLineItem[];
  total_usd: number;
};

export type TimelineResult = {
  total_days: number;
  sop_version: string;
};

export type Project = {
  id: string;
  client_name: string;
  client_email: string;
  gmail_thread_id: string;
  title: string;
  lifecycle_status: string;
  baseline_scope_version_id?: string | null;
  active_scope_version_id?: string | null;
  active_proposal_id?: string | null;
  scope_buffer_id?: string | null;
  current_price_usd: number;
  current_timeline_days: number;
  correlation_id: string;
  created_at: string;
  updated_at: string;
};

export type Artifact = {
  id: string;
  project_id: string;
  artifact_type: string;
  version_number: number;
  change_order_number?: number | null;
  baseline_scope_version_id?: string | null;
  proposed_scope_version_id: string;
  source_buffer_id?: string | null;
  status: string;
  sop_version: string;
  calculation_inputs: ModuleQuantity[];
  pricing_result: PricingResult;
  timeline_result: TimelineResult;
  checksum?: string | null;
  created_at: string;
};

export type Evidence = {
  source_type: string;
  source_id: string;
  source_version?: string | null;
  quote_or_rule: string;
};

export type ScopeEvent = {
  id: string;
  project_id: string;
  gmail_message_id: string;
  baseline_scope_version_id: string;
  classification: string;
  status: string;
  description: string;
  additions: ModuleQuantity[];
  reductions: ModuleQuantity[];
  replacements: unknown[];
  evidence: Evidence[];
  price_delta_usd: number;
  timeline_delta_days: number;
  review_required: boolean;
  correlation_id: string;
  created_at: string;
};

export type ScopeBuffer = {
  id: string;
  project_id: string;
  baseline_scope_version_id: string;
  event_ids: string[];
  additions: ModuleQuantity[];
  reductions: ModuleQuantity[];
  replacements: unknown[];
  proposed_module_selections: ModuleQuantity[];
  net_price_delta_usd: number;
  net_timeline_delta_days: number;
  status: string;
  last_client_message_at: string;
  quiet_window_minutes: number;
  quiet_window_expires_at: string;
  finalized_at?: string | null;
  finalization_reason?: string | null;
  correlation_id: string;
  created_at: string;
  updated_at: string;
};

export type AgentRun = {
  id: string;
  correlation_id: string;
  project_id?: string | null;
  agent_name: string;
  model: string;
  prompt_version: string;
  status: string;
  started_at: string;
  completed_at?: string | null;
  tool_count: number;
  error_category?: string | null;
  retryable: boolean;
};

export type ReadinessCheck = {
  key: string;
  label: string;
  passed: number;
  expected: number;
};

export type AgentReadiness = {
  status: string;
  verified_at?: string | null;
  model?: string | null;
  prompt_versions: string[];
  checks: ReadinessCheck[];
  note: string;
};

export type DashboardSnapshot = {
  generated_at: string;
  projects: Project[];
  artifacts: Artifact[];
  scope_events: ScopeEvent[];
  scope_buffers: ScopeBuffer[];
  agent_runs: AgentRun[];
  readiness: AgentReadiness;
  warnings: string[];
};

export type ScopeVersion = {
  id: string;
  project_id: string;
  version_number: number;
  status: string;
  requirements: Array<{
    requirement_id: string;
    category: string;
    description: string;
    normalized_key: string;
  }>;
  module_selections: ModuleQuantity[];
  assumptions: string[];
  exclusions: string[];
  pricing_result: PricingResult;
  timeline_result: TimelineResult;
  total_price_usd: number;
  timeline_days: number;
  currency: "USD";
  sop_version: string;
  source_artifact_id?: string | null;
  created_at: string;
};

export type ProjectDetailSnapshot = {
  generated_at: string;
  project: Project;
  scope_versions: ScopeVersion[];
  artifacts: Artifact[];
  scope_events: ScopeEvent[];
  scope_buffers: ScopeBuffer[];
  agent_runs: AgentRun[];
  warnings: string[];
};
