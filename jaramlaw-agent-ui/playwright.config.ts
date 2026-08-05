import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  /* 워커를 1로 고정한다. fullyParallel:false 는 파일 안에서만 순차라 파일은 여전히
     여러 워커에 흩어지고, 그러면 chromium/mobile 프로젝트가 동시에
     ① 공용 dev 서버(4321)의 /api/consult 레이트리밋(20/분)을 나눠 쓰고
     ② feature-coverage 가 자기 서버(4373)를 두 번 스폰·종료한다.
     그 간섭 때문에 매 실행마다 다른 테스트가 무작위로 실패했다 (실측: 3회 연속,
     매번 다른 테스트). 직렬 실행에서는 33/33 통과한다. */
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4321",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 5"] } },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:4321/api/health",
    reuseExistingServer: true,
    timeout: 120_000,
    env: {
      PORT: "4321",
      JARAMLAW_DISABLE_PYTHON_BRIDGE: "1",
      // 계정 저장소를 저장소 루트 밖으로 — 테스트가 만든 계정이 커밋에 섞이지 않게.
      JARAMLAW_DATA_DIR: "./.playwright-data",
      /* 레이트리밋(기본 20회/분/IP)은 운영용 안전장치인데, 스위트 전체가 한 IP에서
         1분 안에 signup·briefing 을 수십 번 두드린다 — signup 과 briefing 이 **같은
         버킷**을 쓰므로 진단 테스트가 늘면 무관한 로그인 테스트가 429 로 죽는다.
         실제로 결과 화면 테스트 4개를 추가하자 mobile 프로젝트의 로그인 테스트 2개가
         전체 실행에서만 실패했다(단독 실행은 통과 — 2026-08-04).
         여기서 상한만 올린다. 429 동작을 검증하는 테스트는 없으므로 잃는 커버리지도 없다. */
      JARAMLAW_RATE_LIMIT_MAX: "500",
    },
  },
});
