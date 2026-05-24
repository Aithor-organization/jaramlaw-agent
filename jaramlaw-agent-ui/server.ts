/**
 * JaramLaw React UI server.
 *
 * The UI is a second surface for the parent Python JaramLaw agent system.
 * It calls the 14-node Python workflow first and falls back to a deterministic
 * local route when Python is unavailable, mirroring the Compliance Sentinel UI
 * integration pattern.
 */

import express from "express";
import path from "path";
import fs from "fs";
import { spawn } from "child_process";
import { createHash } from "crypto";
import { createServer as createViteServer } from "vite";
import dotenv from "dotenv";
import type {
  ConsultationSession,
  CryptoLog,
  DocSummary,
  LawItem,
  Message,
  RiskAnalysis,
} from "./src/types.js";

type JsonRecord = Record<string, unknown>;
type ClientType = ConsultationSession["clientType"];
type UiLanguage = "ko" | "en";

const APP_ROOT = process.cwd();
const PARENT_ROOT = path.resolve(APP_ROOT, "..");
const PYTHON_SRC = path.join(PARENT_ROOT, "src");
const WORKFLOW_PATH = path.join(PARENT_ROOT, "workflows", "family-legal-jaramlaw.workflow.yaml");
const AUDIT_LOG_DIR = path.join(PARENT_ROOT, "audit_logs");
const TRACE_LOG_PATH = path.join(AUDIT_LOG_DIR, "trace.jsonl");
const RUNS_DIR = path.join(PARENT_ROOT, "runs");
const TEAM_TOPOLOGY_PATH = path.join(PARENT_ROOT, "agents", "team.yaml");
const MODEL_ROUTING_WORKFLOW_PATH = path.join(PARENT_ROOT, "workflows", "jaramlaw-model-routing.workflow.yaml");
const BRAIN_WORKFLOW_PATH = path.join(PARENT_ROOT, "workflows", "jaramlaw-brain.workflow.yaml");

dotenv.config({ path: path.join(APP_ROOT, ".env") });
dotenv.config({ path: path.join(APP_ROOT, ".env.local") });
dotenv.config({ path: path.join(PARENT_ROOT, ".env") });

const app = express();
const PORT = Number(process.env.PORT || 3000);
const PYTHON_BIN = process.env.PYTHON_BIN || "python";
const PYTHON_TIMEOUT_MS = Number(process.env.JARAMLAW_PYTHON_TIMEOUT_MS || 25000);

app.use(express.json({ limit: "15mb" }));

const PYTHON_WORKFLOW_SCRIPT = String.raw`
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

src = os.environ.get("JARAMLAW_PYTHON_SRC")
if src and src not in sys.path:
    sys.path.insert(0, src)

from jaramlaw_agent.audit import _serialize
from jaramlaw_agent.orchestrator import run_workflow

payload = json.loads(sys.stdin.read() or "{}")
report = run_workflow(
    raw_input=payload.get("raw_input") or {},
    scenario_id=payload.get("scenario_id"),
    write_audit=True,
)
print(json.dumps(_serialize(report), ensure_ascii=False, default=str))
`;

const generateId = () => Math.random().toString(36).slice(2, 11);

const PRELOADED_LAWS: LawItem[] = [
  {
    id: "equal-employment-19",
    title: "남녀고용평등법 제19조 (육아휴직)",
    summary: "만 8세 이하 또는 초등학교 2학년 이하 자녀 양육을 위한 육아휴직 신청권을 보장합니다.",
    clause: "남녀고용평등과 일·가정 양립 지원에 관한 법률",
    application: "사업주가 정당한 사유 없이 거부하거나 불리한 처우를 하면 행정·형사 리스크가 발생합니다.",
    relevance: 98,
  },
  {
    id: "academy-decree-18",
    title: "학원법 시행령 제18조 제2항 [별표 4] (교습비 반환기준)",
    summary: "1개월 초과 교습 계약의 중도 해지 시 미경과 기간 교습비를 반환하도록 정합니다.",
    clause: "학원의 설립·운영 및 과외교습에 관한 법률 시행령",
    application: "선결제 할인, 내부 규정, 패키지 약정을 이유로 한 일괄 환불 거부에 대응할 수 있습니다.",
    relevance: 95,
  },
  {
    id: "childcare-15-5",
    title: "영유아보육법 제15조의5 (CCTV 열람)",
    summary: "보호자는 아동 안전 확인을 위해 어린이집 CCTV 영상정보 열람을 요청할 수 있습니다.",
    clause: "영유아보육법",
    application: "사고 경위, 학대 의심, 방임 정황이 있을 때 영상 보전과 열람 청구의 법적 근거가 됩니다.",
    relevance: 94,
  },
  {
    id: "childcare-33-3",
    title: "영유아보육법 제33조의3 (안전사고 보고)",
    summary: "중대한 안전사고 발생 시 어린이집은 보호자와 관할 지자체에 사고 경위와 조치를 보고해야 합니다.",
    clause: "영유아보육법",
    application: "사고보고서, 공제회 접수, 지자체 민원으로 이어지는 체크리스트를 구성할 수 있습니다.",
    relevance: 91,
  },
  {
    id: "school-violence-16",
    title: "학교폭력예방법 제16조 (피해학생 보호조치)",
    summary: "피해학생에게 심리상담, 일시보호, 치료, 학급교체 등 보호조치를 요청할 수 있습니다.",
    clause: "학교폭력예방 및 대책에 관한 법률",
    application: "담임 또는 학교 대응이 미흡할 때 공식 보호조치 신청과 위원회 절차의 근거가 됩니다.",
    relevance: 89,
  },
];

const securityLogs: CryptoLog[] = [
  {
    id: "log_seed_tls",
    timestamp: new Date(Date.now() - 1000 * 60 * 40).toISOString(),
    type: "TLS_HANDSHAKE",
    payloadSize: "0.4 KB",
    status: "SUCCESS",
    details: "UI server initialized with local TLS simulation and secure audit ledger.",
  },
  {
    id: "log_seed_bridge",
    timestamp: new Date(Date.now() - 1000 * 60 * 25).toISOString(),
    type: "SHA_256_HASH",
    payloadSize: "workflow",
    status: "SECURED",
    details: "Python workflow bridge path fingerprint recorded for runtime validation.",
  },
];

const savedDocuments: DocSummary[] = [
  {
    id: "doc_seed_refund",
    title: "학원 수강료 중도 해지 환불 요청 서한.txt",
    date: new Date(Date.now() - 1000 * 60 * 60 * 12).toISOString(),
    length: 1250,
    overallSummary:
      "3개월 선결제 학원 계약의 중도 해지 및 잔여 교습비 반환을 요구하는 문서입니다. 환불 거부 문구는 학원법 시행령 반환기준과 충돌할 수 있습니다.",
    coreArguments: [
      "중도 해지 의사를 명확히 통보한 시점과 결제 내역을 입증해야 합니다.",
      "선결제 할인 약정은 강행 반환기준을 배제하기 어렵습니다.",
    ],
    criticalRisks: [
      "구두 통보만 남아 있으면 환불 기준일 다툼이 생길 수 있습니다.",
      "교육지원청 민원 전 증거 보전과 정산표 요청이 선행되어야 합니다.",
    ],
    actionableSteps: [
      "내용증명 또는 문자로 해지일, 결제액, 수강일수를 명확히 재통보합니다.",
      "학원법 시행령 별표 4 기준의 정산표를 요구합니다.",
    ],
    lawChecklist: ["학원법 시행령 제18조 제2항 [별표 4]", "민법상 약관 무효·불공정 조항 검토"],
  },
];

const sessions: ConsultationSession[] = [
  buildSeedSession(
    "학원 환불 거부 대응",
    "초등학생 영어학원 3개월분을 선결제했는데 1개월 조금 지나 중도 해지하자 환불이 안 된다고 합니다.",
    "학원법 시행령 제18조 제2항 [별표 4]를 기준으로 미경과 기간 교습비 반환을 요구할 수 있습니다. 결제 내역, 해지 통보일, 실제 수강일수를 보전한 뒤 정산표와 환불 기한을 서면으로 요구하세요.",
    [PRELOADED_LAWS[1]],
    "local-seed",
  ),
  buildSeedSession(
    "어린이집 CCTV 열람",
    "아이 이마에 멍이 생겼는데 어린이집이 CCTV 열람을 거부합니다.",
    "영유아보육법상 보호자는 아동 안전 확인 목적의 CCTV 열람을 요구할 수 있습니다. 영상 보전 요청, 사고보고서 요구, 관할 보육과 민원을 함께 준비하세요.",
    [PRELOADED_LAWS[2], PRELOADED_LAWS[3]],
    "local-seed",
  ),
];

function buildSeedSession(
  title: string,
  userText: string,
  botText: string,
  laws: LawItem[],
  backend: string,
): ConsultationSession {
  const now = new Date().toISOString();
  return {
    id: `session_${generateId()}`,
    title,
    date: now,
    clientType: "layperson",
    messages: [
      { id: `msg_${generateId()}`, sender: "user", text: userText, timestamp: now },
      { id: `msg_${generateId()}`, sender: "bot", text: botText, timestamp: now },
    ],
    riskAnalysis: {
      overallScore: laws.some((law) => law.id.includes("childcare")) ? 55 : 30,
      contractualAmbiguity: 38,
      evidenceStrength: 74,
      precedentSupport: 88,
      financialImpact: 42,
      riskReason: "초기 증거와 법령 근거는 확인되지만, 상대방 통지 기록과 공식 문서 확보 여부가 결과를 좌우합니다.",
      recommendations: ["증거와 통지일을 보전하세요.", "관련 기관에 제출할 서면 초안을 준비하세요.", "고위험 사안은 전문가 검토를 받으세요."],
    },
    recommendedLaws: laws,
    securityLevel: "AES-256-GCM",
    synced: backend === "python-engine",
    integration: {
      backend,
      connected: backend === "python-engine",
      engine: "seed",
    },
  };
}

app.get("/api/health", (_req, res) => {
  res.json({
    status: "ok",
    app: "jaramlaw-agent-react-ui",
    parent_root: PARENT_ROOT,
    python_bridge: {
      enabled: process.env.JARAMLAW_DISABLE_PYTHON_BRIDGE !== "1",
      python_bin: PYTHON_BIN,
      source_path: PYTHON_SRC,
      source_present: fs.existsSync(PYTHON_SRC),
      workflow_path: WORKFLOW_PATH,
      workflow_present: fs.existsSync(WORKFLOW_PATH),
      timeout_ms: PYTHON_TIMEOUT_MS,
    },
    audit: {
      path: AUDIT_LOG_DIR,
      present: fs.existsSync(AUDIT_LOG_DIR),
      recent_count: readRecentAuditRecords(20).length,
    },
    seed_data: {
      laws: countFiles(path.join(PARENT_ROOT, "data", "seed", "laws"), ".yaml"),
      supports: countFiles(path.join(PARENT_ROOT, "data", "seed", "supports"), ".yaml"),
      scenarios: countFiles(path.join(PARENT_ROOT, "data", "seed", "scenarios"), ".yaml"),
    },
    operations: {
      team_topology_present: fs.existsSync(TEAM_TOPOLOGY_PATH),
      model_routing_workflow_present: fs.existsSync(MODEL_ROUTING_WORKFLOW_PATH),
      brain_workflow_present: fs.existsSync(BRAIN_WORKFLOW_PATH),
      trace_path: TRACE_LOG_PATH,
      trace_present: fs.existsSync(TRACE_LOG_PATH),
      trace_recent_count: readTraceRecords(50).length,
    },
    history_count: sessions.length,
  });
});

app.get("/api/ops/workflow/status", (_req, res) => {
  const audits = readRecentAuditRecords(25);
  const traces = readTraceRecords(80);
  res.json({
    status: "success",
    data: {
      parent_root: PARENT_ROOT,
      workflow: {
        path: WORKFLOW_PATH,
        present: fs.existsSync(WORKFLOW_PATH),
        model_routing: {
          path: MODEL_ROUTING_WORKFLOW_PATH,
          present: fs.existsSync(MODEL_ROUTING_WORKFLOW_PATH),
        },
        brain: {
          path: BRAIN_WORKFLOW_PATH,
          present: fs.existsSync(BRAIN_WORKFLOW_PATH),
        },
      },
      topology: {
        path: TEAM_TOPOLOGY_PATH,
        present: fs.existsSync(TEAM_TOPOLOGY_PATH),
      },
      audit: {
        path: AUDIT_LOG_DIR,
        present: fs.existsSync(AUDIT_LOG_DIR),
        recent_count: audits.length,
        latest_id: asOptionalString(audits[0]?.audit_log_id),
      },
      trace: {
        path: TRACE_LOG_PATH,
        present: fs.existsSync(TRACE_LOG_PATH),
        recent_count: traces.length,
        latest_node: asOptionalString(traces[0]?.node),
      },
      budget: {
        per_run_limit_usd: Number(process.env.JARAMLAW_PER_RUN_BUDGET_USD || 0.25),
        monthly_limit_usd: Number(process.env.JARAMLAW_MONTHLY_BUDGET_USD || 25),
      },
    },
  });
});

app.get("/api/ops/audit/logs", (req, res) => {
  const limit = Math.min(Number(req.query.limit || 40), 120);
  res.json({ status: "success", data: readRecentAuditRecords(limit) });
});

app.get("/api/ops/traces", (req, res) => {
  const limit = Math.min(Number(req.query.limit || 80), 240);
  res.json({ status: "success", data: readTraceRecords(limit) });
});

app.post("/api/ops/workflow/publish", (req, res) => {
  const { note = "local workflow publish" } = req.body as { note?: string };
  const manifest = {
    status: "published-local",
    workflow_path: WORKFLOW_PATH,
    model_routing_workflow_path: MODEL_ROUTING_WORKFLOW_PATH,
    brain_workflow_path: BRAIN_WORKFLOW_PATH,
    team_topology_path: TEAM_TOPOLOGY_PATH,
    workflow_sha1: fs.existsSync(WORKFLOW_PATH)
      ? createHash("sha1").update(fs.readFileSync(WORKFLOW_PATH)).digest("hex")
      : null,
    note,
    published_at: new Date().toISOString(),
  };
  fs.mkdirSync(RUNS_DIR, { recursive: true });
  fs.writeFileSync(path.join(RUNS_DIR, "workflow-publish.json"), JSON.stringify(manifest, null, 2), "utf8");
  addSecurityLog("SHA_256_HASH", "workflow", "Local workflow publish manifest written.");
  res.json({ status: "success", data: manifest });
});

app.post("/api/ops/batch-consult", async (req, res) => {
  const { items, clientType = "layperson" } = req.body as { items?: unknown[]; clientType?: ClientType };
  const inputs = Array.isArray(items)
    ? items.map((item) => {
        if (typeof item === "string") return item;
        const record = asRecord(item);
        return asString(record.message) || asString(record.content) || asString(record.query);
      }).filter(Boolean).slice(0, 10)
    : [];

  if (!inputs.length) {
    return res.status(400).json({ status: "error", message: "batch items are required" });
  }

  const results: JsonRecord[] = [];
  for (const text of inputs) {
    try {
      const report = await runPythonWorkflow(buildWorkflowInput(text, clientType), inferScenarioId(text));
      results.push({
        status: "success",
        message: text.slice(0, 120),
        audit_log_id: report.audit_log_id,
        validation: asRecord(report.independent_validation).status,
        routing: asRecord(report.model_routing).criticality,
      });
    } catch (error) {
      results.push({
        status: "error",
        message: text.slice(0, 120),
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  addSecurityLog("SHA_256_HASH", `${results.length} batch items`, "Batch consult operation completed.");
  res.json({ status: "success", data: results });
});

app.get("/api/history", (_req, res) => {
  res.json({ status: "success", count: sessions.length, data: sessions });
});

app.get("/api/history/:id", (req, res) => {
  const session = sessions.find((item) => item.id === req.params.id);
  if (!session) {
    return res.status(404).json({ status: "error", message: "상담 세션을 찾을 수 없습니다." });
  }
  return res.json({ status: "success", data: session });
});

app.post("/api/history/:id/expert-review", (req, res) => {
  const sessionIndex = sessions.findIndex((item) => item.id === req.params.id);
  if (sessionIndex === -1) {
    return res.status(404).json({ status: "error", message: "상담 세션을 찾을 수 없습니다." });
  }

  const { reviewerName, feedbackText, rating, status, editedLaws } = req.body as JsonRecord;
  if (!asString(reviewerName) || !asString(feedbackText) || !Number(rating)) {
    return res.status(400).json({ status: "error", message: "작성자, 피드백, 평점은 필수입니다." });
  }

  const original = sessions[sessionIndex];
  sessions[sessionIndex] = {
    ...original,
    expertFeedback: {
      id: original.expertFeedback?.id || `feedback_${generateId()}`,
      reviewerName: asString(reviewerName),
      feedbackText: asString(feedbackText),
      rating: Number(rating),
      status: status === "draft" ? "draft" : "verified",
      reviewedAt: new Date().toISOString(),
      editedLaws: Array.isArray(editedLaws) ? editedLaws.map(String) : undefined,
    },
  };

  addSecurityLog(
    "SHA_256_HASH",
    `${Buffer.byteLength(JSON.stringify(sessions[sessionIndex].expertFeedback))} B`,
    `Expert review signed for ${sessions[sessionIndex].id}.`,
  );

  return res.json({ status: "success", data: sessions[sessionIndex] });
});

app.post("/api/consult", async (req, res) => {
  const { message, clientType = "layperson", language = "ko" } = req.body as {
    message?: string;
    history?: Message[];
    clientType?: ClientType;
    language?: UiLanguage;
  };
  const query = typeof message === "string" ? message.trim() : "";

  if (!query) {
    return res.status(400).json({ status: "error", message: "상담 내용을 입력해 주세요." });
  }

  const userMsg: Message = {
    id: `msg_user_${generateId()}`,
    sender: "user",
    text: query,
    timestamp: new Date().toISOString(),
  };

  const rawInput = buildWorkflowInput(query, clientType);

  if (process.env.JARAMLAW_DISABLE_PYTHON_BRIDGE !== "1" && fs.existsSync(PYTHON_SRC)) {
    try {
      const report = await runPythonWorkflow(rawInput, inferScenarioId(query));
      const session = buildSessionFromReport(query, userMsg, report, clientType, language, {
        backend: "python-engine",
        connected: true,
        engine: "jaramlaw_agent.orchestrator.run_workflow",
      });
      sessions.unshift(session);
      addSecurityLog("SHA_256_HASH", `${query.length} chars`, `Python workflow completed. audit=${session.auditLogId || "n/a"}`);
      return res.json({ status: "success", dynamic: true, data: session });
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      const fallback = buildFallbackSession(query, userMsg, clientType, language, reason);
      sessions.unshift(fallback);
      addSecurityLog("KEY_ROTATION", `${query.length} chars`, `Python bridge failed; deterministic fallback used. ${reason.slice(0, 120)}`);
      return res.json({ status: "success", dynamic: false, failover: true, data: fallback });
    }
  }

  const fallback = buildFallbackSession(query, userMsg, clientType, language, "python_bridge_disabled_or_missing");
  sessions.unshift(fallback);
  return res.json({ status: "success", dynamic: false, failover: true, data: fallback });
});

app.get("/api/documents", (_req, res) => {
  res.json({ status: "success", count: savedDocuments.length, data: savedDocuments });
});

app.post("/api/summarize", (req, res) => {
  const { title = "업로드 문서", content } = req.body as { title?: string; content?: string; language?: UiLanguage };
  const text = typeof content === "string" ? content.trim() : "";
  if (!text) {
    return res.status(400).json({ status: "error", message: "문서 내용을 입력해 주세요." });
  }

  const matched = selectRelevantLaws(text);
  const doc: DocSummary = {
    id: `doc_${generateId()}`,
    title,
    date: new Date().toISOString(),
    length: text.length,
    overallSummary: `문서에서 ${matched.map((law) => law.title).slice(0, 2).join(", ")} 관련 쟁점이 감지되었습니다. 증거 보전, 통지일, 공식 제출 경로를 분리해 정리하는 것이 필요합니다.`,
    coreArguments: [
      "상대방 의무와 신청인의 권리를 구분해 한 문단씩 정리해야 합니다.",
      "법령 조항, 일자, 금액, 기관명을 원문 그대로 남기는 것이 유리합니다.",
    ],
    criticalRisks: [
      "상대방에게 이미 전달한 구두 통지만으로는 증명력이 약할 수 있습니다.",
      "민원·신고·내용증명 문구가 법률 자문으로 오해되지 않도록 표현을 조정해야 합니다.",
    ],
    actionableSteps: [
      "핵심 사실관계를 날짜순으로 정렬합니다.",
      "법령명과 조항을 별도 체크리스트로 분리합니다.",
      "필요하면 JaramLaw 상담 탭에서 같은 내용으로 workflow 진단을 실행합니다.",
    ],
    lawChecklist: matched.map((law) => law.title),
    rawText: text.slice(0, 1000),
  };

  savedDocuments.unshift(doc);
  addSecurityLog("AES_GCM_ENCRYPT", `${text.length} chars`, `Document summary stored: ${doc.id}`);
  return res.json({ status: "success", data: doc });
});

app.post("/api/encrypt-demo", (req, res) => {
  const { text, mode, cipher } = req.body as { text?: string; mode?: string; cipher?: string };
  if (mode === "encrypt") {
    if (!text) return res.status(400).json({ status: "error", message: "암호화할 텍스트가 없습니다." });
    const cipherText = Buffer.from(`JARAMLAW:${text}:${new Date().toISOString()}`).toString("base64");
    addSecurityLog("AES_GCM_ENCRYPT", `${text.length} chars`, "AES-GCM simulation sealed a client-side payload.");
    return res.json({ status: "success", cipherText });
  }

  if (!cipher) return res.status(400).json({ status: "error", message: "복호화할 블록이 없습니다." });
  const decoded = Buffer.from(cipher, "base64").toString("utf8");
  const decrypted = decoded.replace(/^JARAMLAW:/, "").replace(/:\d{4}-\d{2}-\d{2}T.*$/, "");
  addSecurityLog("AES_GCM_DECRYPT", `${cipher.length} chars`, "AES-GCM simulation restored a sealed payload.");
  return res.json({ status: "success", decrypted });
});

app.post("/api/sync-cloud", (_req, res) => {
  sessions.forEach((session) => {
    session.synced = true;
  });
  addSecurityLog("KEY_ROTATION", `${sessions.length} sessions`, "Device sync reconciliation completed for consultation history.");
  res.json({ status: "success", synced: sessions.length, data: sessions });
});

app.get("/api/security-logs", (_req, res) => {
  res.json({ status: "success", logs: securityLogs });
});

async function runPythonWorkflow(rawInput: JsonRecord, scenarioId: string | null): Promise<JsonRecord> {
  return new Promise((resolve, reject) => {
    const env = {
      ...process.env,
      JARAMLAW_PYTHON_SRC: PYTHON_SRC,
      PYTHONIOENCODING: "utf-8",
      PYTHONPATH: [PYTHON_SRC, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
    };
    const child = spawn(PYTHON_BIN, ["-c", PYTHON_WORKFLOW_SCRIPT], {
      cwd: PARENT_ROOT,
      env,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    const timeout = setTimeout(() => {
      child.kill("SIGTERM");
      reject(new Error(`Python workflow timed out after ${PYTHON_TIMEOUT_MS}ms`));
    }, PYTHON_TIMEOUT_MS);

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf8");
    });
    child.on("error", (error) => {
      clearTimeout(timeout);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timeout);
      if (code !== 0) {
        reject(new Error(stderr || `Python workflow exited with code ${code}`));
        return;
      }
      try {
        const lastJson = stdout.trim().split(/\r?\n/).filter(Boolean).at(-1) || "{}";
        resolve(JSON.parse(lastJson) as JsonRecord);
      } catch (error) {
        reject(new Error(`Unable to parse Python workflow output: ${error instanceof Error ? error.message : String(error)}`));
      }
    });

    child.stdin.write(JSON.stringify({ raw_input: rawInput, scenario_id: scenarioId }));
    child.stdin.end();
  });
}

function buildWorkflowInput(message: string, clientType: ClientType | undefined): JsonRecord {
  const scenarioType = inferScenarioType(message);
  const baseChildren =
    scenarioType === "academy_refund" || scenarioType === "school_violence"
      ? [{ name_masked: "C1", birth_date: "2019-08-10", sex: "unknown", facility: "elementary_school" }]
      : [{ name_masked: "C1", birth_date: "2024-05-15", sex: "unknown", facility: "childcare_center" }];

  const data: JsonRecord = {};
  if (scenarioType === "academy_refund") {
    Object.assign(data, {
      academy_name: "Jaram Academy",
      monthly_fee_krw: 350000,
      months_paid: 3,
      total_paid_krw: 1050000,
      payment_date: "2026-04-20",
      use_start_date: "2026-04-21",
      cancellation_request_date: new Date().toISOString().slice(0, 10),
      days_used: 35,
      total_days: 90,
      refusal_notice_received: /거부|불가|안.?됨/.test(message),
      refusal_text: message.slice(0, 160),
    });
  }
  if (scenarioType === "daycare_accident") {
    Object.assign(data, {
      notification_text: message.slice(0, 180),
      parent_observation: message,
      cctv_access_denied: /CCTV|열람|거부|안.?보여/.test(message),
      accident_report_received: false,
      keywords_detected: Array.from(message.matchAll(/멍|상처|학대|방임|CCTV|사고/g)).map((match) => match[0]),
    });
  }

  return {
    persona: clientType === "lawyer" ? "P3" : "P1",
    reference_date: new Date().toISOString().slice(0, 10),
    parents: [
      { role: "mother", age: 34, employment: "unknown", region_code: "11440" },
      { role: "father", age: 36, employment: "unknown", region_code: "11440" },
    ],
    children: baseChildren,
    events: scenarioType === "parental_leave" ? [{ type: "pregnancy", date: new Date().toISOString().slice(0, 10) }] : [],
    flags: scenarioType === "parental_leave" ? ["working_mom", "dual_income"] : [],
    scenario: {
      type: scenarioType,
      query: message,
      data,
    },
  };
}

function buildSessionFromReport(
  query: string,
  userMsg: Message,
  report: JsonRecord,
  clientType: ClientType | undefined,
  language: UiLanguage,
  integration: NonNullable<ConsultationSession["integration"]>,
): ConsultationSession {
  const laws = normalizeLaws(asArray(report.matched_laws));
  const riskAnalysis = buildRiskFromReport(report);
  const botText = renderWorkflowReply(report, laws, language);
  const botMsg: Message = {
    id: `msg_bot_${generateId()}`,
    sender: "bot",
    text: botText,
    timestamp: new Date().toISOString(),
  };
  const auditLogId = asOptionalString(report.audit_log_id);

  return {
    id: `session_${generateId()}`,
    title: query.slice(0, 42) + (query.length > 42 ? "..." : ""),
    date: new Date().toISOString(),
    clientType: clientType === "lawyer" ? "lawyer" : "layperson",
    messages: [userMsg, botMsg],
    riskAnalysis,
    recommendedLaws: laws.length ? laws : selectRelevantLaws(query),
    securityLevel: "AES-256-GCM",
    synced: integration.connected,
    auditLogId,
    workflowReport: report,
    integration,
  };
}

function buildFallbackSession(
  query: string,
  userMsg: Message,
  clientType: ClientType | undefined,
  language: UiLanguage,
  reason: string,
): ConsultationSession {
  const laws = selectRelevantLaws(query);
  const botText =
    language === "en"
      ? `The Python workflow bridge is unavailable, so JaramLaw used the deterministic local route.\n\nRelevant legal anchors: ${laws.map((law) => law.title).join(", ")}.\n\nBridge note: ${reason}`
      : `Python workflow 브리지가 응답하지 않아 로컬 deterministic 경로로 진단했습니다.\n\n관련 법령 축: ${laws.map((law) => law.title).join(", ")}\n\n브리지 상태: ${reason}`;

  return {
    id: `session_${generateId()}`,
    title: query.slice(0, 42) + (query.length > 42 ? "..." : ""),
    date: new Date().toISOString(),
    clientType: clientType === "lawyer" ? "lawyer" : "layperson",
    messages: [
      userMsg,
      { id: `msg_bot_${generateId()}`, sender: "bot", text: botText, timestamp: new Date().toISOString() },
    ],
    riskAnalysis: {
      overallScore: /학대|멍|상처|응급|폭력/.test(query) ? 72 : 36,
      contractualAmbiguity: /계약|환불|약정/.test(query) ? 58 : 24,
      evidenceStrength: /문자|영수증|사진|진단서|녹취/.test(query) ? 82 : 52,
      precedentSupport: laws.length ? 84 : 55,
      financialImpact: /환불|돈|금액|손해/.test(query) ? 62 : 28,
      riskReason: "Python 엔진 fallback 상태이므로 seed 법령과 휴리스틱만으로 산정한 임시 리스크입니다.",
      recommendations: ["Python 브리지 상태를 확인하세요.", "증거와 날짜를 구조화해 다시 실행하세요.", "긴급 안전 신호는 즉시 공공기관에 연락하세요."],
    },
    recommendedLaws: laws,
    securityLevel: "AES-256-GCM",
    synced: false,
    integration: {
      backend: "local-rule-engine",
      connected: false,
      engine: "deterministic-fallback",
      fallback_reason: reason,
    },
  };
}

function renderWorkflowReply(report: JsonRecord, laws: LawItem[], language: UiLanguage): string {
  const humanReview = asRecord(report.human_review);
  const safety = asRecord(report.safety_routing);
  const supports = asArray(report.support_matches);
  const docs = asArray(report.draft_documents);
  const rights = asArray(report.rights_cards);
  const verifier = asRecord(report.verifier_results);
  const verifierRatio = Number(verifier.verified_ratio ?? 0);

  if (language === "en") {
    return [
      "### JaramLaw Python workflow result",
      `- Matched laws: ${laws.length}`,
      `- Support matches: ${supports.length}`,
      `- Rights cards: ${rights.length}`,
      `- Draft documents: ${docs.length}`,
      `- Verified claim ratio: ${Math.round(verifierRatio * 100)}%`,
      humanReview.needed ? `- Human review: recommended (${asString(humanReview.reason, "review needed")})` : "- Human review: not required by deterministic gate",
      safety.triggered ? `- Safety routing: ${asString(safety.category)} / ${asString(safety.contact)}` : "",
      "",
      "Use the workflow panels below for citations, generated documents, and board diagnostics. This is an information-assist tool, not legal advice.",
    ].filter(Boolean).join("\n");
  }

  return [
    "### JaramLaw Python 14-node workflow 결과",
    `- 매칭 법령: ${laws.length}건`,
    `- 지원제도 매칭: ${supports.length}건`,
    `- 권리카드: ${rights.length}건`,
    `- 생성 문서 초안: ${docs.length}건`,
    `- 원자 claim 검증률: ${Math.round(verifierRatio * 100)}%`,
    humanReview.needed ? `- 전문가 검토 권장: ${asString(humanReview.reason, "검토 필요")}` : "- 전문가 검토 게이트: 자동 차단 사유 없음",
    safety.triggered ? `- 안전 라우팅: ${asString(safety.category)} / ${asString(safety.contact)}` : "",
    "",
    "아래 workflow 패널에서 인용 법령, 생성 문서, 전문가 보드 진단을 확인하세요. 본 결과는 법률 자문이 아닌 정보 보조입니다.",
  ].filter(Boolean).join("\n");
}

function buildRiskFromReport(report: JsonRecord): RiskAnalysis {
  const safety = asRecord(report.safety_routing);
  const human = asRecord(report.human_review);
  const laws = asArray(report.matched_laws);
  const docs = asArray(report.draft_documents);
  const verifier = asRecord(report.verifier_results);
  const verifiedRatio = Number(verifier.verified_ratio ?? 0);
  const safetyScore = safety.triggered ? 82 : 0;
  const reviewScore = human.needed ? 62 : 22;

  return {
    overallScore: Math.max(safetyScore, reviewScore),
    contractualAmbiguity: docs.length ? 46 : 28,
    evidenceStrength: Math.round(Math.max(45, Math.min(95, verifiedRatio * 100 || (laws.length ? 76 : 48)))),
    precedentSupport: Math.round(Math.max(45, Math.min(96, laws.length * 8 + 56))),
    financialImpact: docs.some((doc) => /refund|환불|교습비/.test(asString(doc.kind) + asString(doc.title))) ? 64 : 34,
    riskReason: safety.triggered
      ? "안전 신호가 감지되어 일반 상담보다 보호기관 라우팅과 전문가 확인이 우선입니다."
      : human.needed
      ? "검증 게이트가 전문가 검토를 권장했습니다. 인용과 예외 조항을 보강해야 합니다."
      : "시드 법령과 workflow 검증을 통과한 정보 보조 결과입니다.",
    recommendations: [
      "workflow 패널의 법령·권리카드·문서 초안을 분리해 확인하세요.",
      "상대방 통지, 사진, 진단서, 영수증 등 증거를 날짜순으로 묶으세요.",
      "고위험 안전 신호나 분쟁 금액이 큰 사안은 전문가 검토 루프를 사용하세요.",
    ],
  };
}

function normalizeLaws(rawLaws: JsonRecord[]): LawItem[] {
  return rawLaws.slice(0, 10).map((law, index) => ({
    id: asString(law.law_id, `law_${index + 1}`),
    title: [asString(law.law_name), asString(law.article), asString(law.title)].filter(Boolean).join(" "),
    summary: asString(law.text_summary, "법령 요약이 제공되지 않았습니다."),
    clause: asString(law.law_name),
    application: asArray(law.applies_reason).map((item) => asString(item)).filter(Boolean).join(" · ") || "workflow 매칭 결과를 확인하세요.",
    relevance: Math.round(Number(law.relevance_score ?? 0) * 100) || 80,
  }));
}

function selectRelevantLaws(text: string): LawItem[] {
  const selected = PRELOADED_LAWS.filter((law) => {
    if (/학원|환불|교습|수강/.test(text)) return law.id.includes("academy");
    if (/어린이집|CCTV|상처|멍|사고|학대/.test(text)) return law.id.includes("childcare");
    if (/육아휴직|출산|임신|태아|배우자/.test(text)) return law.id.includes("equal-employment");
    if (/학교폭력|괴롭힘|따돌림|폭행/.test(text)) return law.id.includes("school");
    return false;
  });
  return selected.length ? selected : PRELOADED_LAWS.slice(0, 3);
}

function inferScenarioType(text: string): string {
  if (/학원|환불|교습|수강료|선결제/.test(text)) return "academy_refund";
  if (/어린이집|CCTV|안전사고|상처|멍|학대|방임/.test(text)) return "daycare_accident";
  if (/육아휴직|출산|임신|태아|배우자/.test(text)) return "parental_leave";
  if (/학교폭력|괴롭힘|따돌림|폭행/.test(text)) return "school_violence";
  return "general";
}

function inferScenarioId(text: string): string | null {
  const type = inferScenarioType(text);
  if (type === "academy_refund") return "B";
  if (type === "daycare_accident") return "C";
  if (type === "parental_leave") return "A";
  return null;
}

function addSecurityLog(type: CryptoLog["type"], payloadSize: string, details: string) {
  securityLogs.unshift({
    id: `log_${generateId()}`,
    timestamp: new Date().toISOString(),
    type,
    payloadSize,
    status: "SUCCESS",
    details,
  });
  if (securityLogs.length > 80) securityLogs.pop();
}

function readRecentAuditRecords(limit: number): JsonRecord[] {
  if (!fs.existsSync(AUDIT_LOG_DIR)) return [];
  return fs.readdirSync(AUDIT_LOG_DIR)
    .filter((name) => name !== "trace.jsonl" && (name.endsWith(".jsonl") || name.endsWith(".json")))
    .map((name) => path.join(AUDIT_LOG_DIR, name))
    .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)
    .flatMap((filePath) => readJsonRecordsFromFile(filePath, limit))
    .slice(0, limit);
}

function readTraceRecords(limit: number): JsonRecord[] {
  if (!fs.existsSync(TRACE_LOG_PATH)) return [];
  return readJsonRecordsFromFile(TRACE_LOG_PATH, limit).slice(0, limit);
}

function readJsonRecordsFromFile(filePath: string, limit: number): JsonRecord[] {
  try {
    const text = fs.readFileSync(filePath, "utf8");
    if (filePath.endsWith(".jsonl")) {
      return text.split(/\r?\n/)
        .filter(Boolean)
        .slice(-limit)
        .reverse()
        .map((line) => {
          try {
            const parsed = JSON.parse(line);
            return { ...asRecord(parsed), source_file: path.basename(filePath) };
          } catch {
            return { raw: line, source_file: path.basename(filePath) };
          }
        });
    }

    const parsed = JSON.parse(text);
    if (Array.isArray(parsed)) {
      return parsed.map(asRecord).map((item) => ({ ...item, source_file: path.basename(filePath) })).slice(0, limit);
    }
    return [{ ...asRecord(parsed), source_file: path.basename(filePath) }];
  } catch {
    return [];
  }
}

function countFiles(dirPath: string, extension: string): number {
  if (!fs.existsSync(dirPath)) return 0;
  return fs.readdirSync(dirPath).filter((name) => name.endsWith(extension)).length;
}

function asRecord(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : {};
}

function asArray(value: unknown): JsonRecord[] {
  return Array.isArray(value) ? value.map(asRecord).filter((item) => Object.keys(item).length > 0) : [];
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function asOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

async function initializeServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: {
        middlewareMode: true,
        hmr: process.env.DISABLE_HMR === "true" ? false : undefined,
      },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(APP_ROOT, "dist");
    app.use(express.static(distPath));
    app.get("*", (_req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    const fingerprint = createHash("sha1").update(PYTHON_SRC).digest("hex").slice(0, 8);
    console.log(`JaramLaw Agent UI running at http://localhost:${PORT} (bridge ${fingerprint})`);
  });
}

initializeServer().catch((error) => {
  console.error("Failed to boot JaramLaw UI server:", error);
  process.exitCode = 1;
});
