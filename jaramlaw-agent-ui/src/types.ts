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
  workflowReport?: Record<string, unknown>;
  integration?: {
    backend: 'python-engine' | 'local-rule-engine' | 'local-seed' | string;
    connected: boolean;
    engine?: string;
    fallback_reason?: string;
  };
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
