export interface Message {
  id: string;
  sender: 'user' | 'bot' | 'system';
  text: string;
  timestamp: string;
  encrypted?: boolean;
  cipherText?: string;
}

export interface LawItem {
  id: string;
  title: string;
  summary: string;
  application: string;
  relevance: number; // 0 to 100
  clause?: string;
}

export interface RiskAnalysis {
  /** Internal triage signal, not a statistical probability. */
  overallScore: number; // 0 to 100
  contractualAmbiguity: number; // 0 to 100
  evidenceStrength: number; // 0 to 100
  precedentSupport: number; // 0 to 100
  financialImpact: number; // 0 to 100
  riskReason: string;
  recommendations: string[];
}

export interface ExpertFeedback {
  id: string;
  reviewerName: string;
  feedbackText: string;
  rating: number; // 1 to 5
  status: 'draft' | 'verified';
  reviewedAt: string;
  editedLaws?: string[];
}

/**
 * Structured artifacts the Python workflow returns inside `workflowReport`. Field names
 * mirror the backend dataclasses exactly (jaramlaw_agent/models.py) so the UI can render
 * the actual content — refund figures, draft bodies, rights — instead of only counts.
 * Every field is optional: the backend omits what a given scenario does not produce, and
 * a `safety`-routed run returns empty arrays by design.
 */
export interface LegalBasis {
  law?: string;
  article?: string;
  effective_date?: string;
  source_url?: string;
}

/** Present only when the backend could compute a refund; `insufficient_facts` otherwise. */
export interface CalculationBreakdown {
  status?: 'insufficient_facts';
  missing?: string[];
  total_paid_krw?: number;
  days_used?: number;
  total_days?: number;
  remaining_days?: number;
  refund_krw?: number;
  formula?: string;
}

export interface DraftDocument {
  doc_id?: string;
  title: string;
  kind?: string;
  body_markdown?: string;
  legal_basis?: LegalBasis[];
  next_actions?: string[];
  calculation_breakdown?: CalculationBreakdown;
}

/** How a right is typically denied and the recourse. The backend returns this as an
 * object (not a string) — rendering it directly was React error #31. */
export interface RightsDenial {
  violation?: string;
  penalty_summary?: string;
  report_channel?: string;
}

export interface RightsCard {
  card_id?: string;
  title: string;
  holder?: string;
  legal_basis?: LegalBasis;
  denial?: RightsDenial;
  example_denial?: string;
}

export interface SupportMatch {
  support_id?: string;
  name: string;
  amount_krw?: number;
  amount_description?: string;
  condition_summary?: string;
  application_channel?: string;
  deadline_days_left?: number;
  deadline_kind?: string;
}

export interface CalendarEvent {
  kind?: string;
  title: string;
  scheduled_date?: string;
  legal_basis?: LegalBasis;
  notes?: string;
}

export interface WorkflowReport {
  matched_laws?: unknown[];
  support_matches?: SupportMatch[];
  rights_cards?: RightsCard[];
  draft_documents?: DraftDocument[];
  calendar?: { events?: CalendarEvent[]; ical_export?: string };
  verifier_results?: {
    verified_count?: number;
    partial_count?: number;
    unverifiable_count?: number;
    verified_ratio?: number;
  };
  safety_routing?: { triggered?: boolean; category?: string; contact?: string };
  ai_answer?: { mode?: string };
  [key: string]: unknown;
}

export interface ConsultationSession {
  id: string;
  title: string;
  date: string;
  clientType: 'layperson' | 'lawyer';
  messages: Message[];
  riskAnalysis?: RiskAnalysis;
  recommendedLaws: LawItem[];
  expertFeedback?: ExpertFeedback;
  securityLevel: 'Standard' | 'AES-256-GCM';
  synced: boolean;
  auditLogId?: string;
  workflowReport?: WorkflowReport;
  integration?: {
    backend: 'python-engine' | 'local-rule-engine' | 'local-seed' | string;
    connected: boolean;
    engine?: string;
    fallback_reason?: string;
  };
}

/** Scenario-specific facts the user can supply so the backend can compute concrete results. */
export interface CaseData {
  monthly_fee_krw?: number;
  months_paid?: number;
  total_paid_krw?: number;
  days_used?: number;
  total_days?: number;
  [key: string]: unknown;
}

export interface DocSummary {
  id: string;
  title: string;
  date: string;
  length: number;
  overallSummary: string;
  coreArguments: string[];
  criticalRisks: string[];
  actionableSteps: string[];
  lawChecklist: string[];
  rawText?: string;
  summaryText?: string;
}

export interface CryptoLog {
  id: string;
  timestamp: string;
  type: 'TLS_HANDSHAKE' | 'AES_GCM_ENCRYPT' | 'AES_GCM_DECRYPT' | 'SHA_256_HASH' | 'KEY_ROTATION';
  payloadSize: string;
  status: 'SUCCESS' | 'SECURED';
  details: string;
}

export interface HealthStatus {
  status: string;
  app: string;
  python_bridge: {
    enabled: boolean;
    source_present: boolean;
    workflow_present: boolean;
    timeout_ms: number;
  };
  audit: {
    present: boolean;
    recent_count: number;
  };
  seed_data: {
    laws: number;
    supports: number;
    scenarios: number;
  };
  operations?: {
    team_topology_present: boolean;
    model_routing_workflow_present: boolean;
    brain_workflow_present: boolean;
    trace_present: boolean;
    trace_recent_count: number;
  };
  history_count: number;
}
