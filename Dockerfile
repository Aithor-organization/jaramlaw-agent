# syntax=docker/dockerfile:1
#
# JaramLaw — Railway 배포 이미지.
#
# UI 서버(Express)가 상담 1건마다 Python 워크플로우를 spawn 한다(server.ts runPythonWorkflow).
# 따라서 Node 와 Python 이 같은 컨테이너에 있어야 한다 — Vercel 정적/서버리스로는
# 성립하지 않던 구조이고, Railway 로 옮기는 이유다.
#
# 런타임 레이아웃 (server.ts 가 이 경로들을 전제한다):
#   /app                      = PARENT_ROOT  → src/ workflows/ agents/ audit_logs/ runs/
#   /app/jaramlaw-agent-ui    = APP_ROOT     = 프로세스 cwd

FROM node:22-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python 런타임 ────────────────────────────────────────────────────────────
# Debian 12 는 PEP 668 로 시스템 파이썬에 pip 설치를 막는다 → venv 로 분리.
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 의존성 선언(pyproject) + 패키지 소스만 먼저 복사해 레이어 캐시를 살린다.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .

# AgentShield(입력/출력 런타임 가드)는 별도 비공개 저장소다.
# 미설치 시 가드가 degrade 한 채로 뜨므로(pyproject 주석 참조), 프로덕션에서는 켤 것.
#   Railway → Settings → Build → Build Arguments 에
#   AGENTSHIELD_GIT=git+https://<GITHUB_TOKEN>@github.com/Aithor-organization/AgentShield
# 값을 비워두면 설치를 건너뛴다. 설치를 시도했다가 실패하면 빌드를 세운다(조용한 degrade 금지).
ARG AGENTSHIELD_GIT=""
RUN if [ -n "$AGENTSHIELD_GIT" ]; then pip install --no-cache-dir "$AGENTSHIELD_GIT"; fi

# ── Node UI ─────────────────────────────────────────────────────────────────
COPY jaramlaw-agent-ui/package.json jaramlaw-agent-ui/package-lock.json ./jaramlaw-agent-ui/
RUN npm --prefix jaramlaw-agent-ui ci

COPY . .

# vite build → dist/assets, esbuild → dist/server.cjs.
# 번들은 --packages=external 이라 런타임에도 express·dotenv·vite 가 필요하다(셋 다 dependencies).
RUN npm --prefix jaramlaw-agent-ui run build \
 && npm --prefix jaramlaw-agent-ui prune --omit=dev \
 && npm cache clean --force

# HOST 는 0.0.0.0 이어야 Railway 트래픽이 들어온다. 다만 non-loopback 인 순간
# server.ts 가 JARAMLAW_API_TOKEN 없이는 부팅을 거부한다(fail-closed, 아동 개인정보 보호).
# → Railway Variables 에 JARAMLAW_API_TOKEN 을 반드시 넣을 것.
ENV NODE_ENV=production \
    JARAMLAW_HOST=0.0.0.0 \
    PYTHON_BIN=/opt/venv/bin/python

WORKDIR /app/jaramlaw-agent-ui

EXPOSE 3000
CMD ["node", "dist/server.cjs"]
