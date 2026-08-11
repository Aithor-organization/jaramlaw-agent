/** 스위트 시작 전에 프로덕션 번들을 최신으로 맞춘다.
 *
 * 왜 여기인가 (2026-08-12):
 * - `feature-coverage.spec` 은 `node dist/server.cjs` 를 띄운다. 그런데 예전에는
 *   dist가 **있기만 하면** 다시 빌드하지 않아서, 가입 화면에 동의 체크박스를 추가한 뒤에도
 *   두 테스트가 옛 번들을 상대로 돌다 "체크박스를 못 찾는다"로 죽었다. 조용히 옛 코드를
 *   통과시키는 쪽이 더 위험하다.
 * - 그렇다고 테스트 **도중**에 빌드하면 안 된다. `vite build` 가 `node_modules/.vite`
 *   의존성 캐시를 다시 쓰는 동안 공용 dev 서버(4321)가 최적화 캐시 무효화를 감지해
 *   페이지를 통째로 리로드했고, 그 순간 진행 중이던 테스트의 로그인 상태가 날아갔다.
 *   실패가 프로젝트를 옮겨 다니는 전형적인 경합이었다.
 *
 * globalSetup은 webServer가 뜨기 전에, 어떤 테스트보다 먼저 한 번만 돈다 — 두 문제가
 * 동시에 사라지는 유일한 지점이다.
 */
import { execSync } from "node:child_process";
import { existsSync, readdirSync, rmSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const UI_ROOT = path.dirname(fileURLToPath(import.meta.url)).replace(/[/\\]tests$/, "");

/** dist가 소스보다 오래됐나. dist·tests 자신은 세지 않는다. */
function isBundleStale(): boolean {
  const bundle = path.join(UI_ROOT, "dist", "server.cjs");
  if (!existsSync(bundle)) return true;
  const builtAt = statSync(bundle).mtimeMs;
  const skip = new Set(["dist", "tests", "node_modules", "test-results", "playwright-report", ".playwright-data"]);

  const newest = (dir: string): number => {
    let latest = 0;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.name.startsWith(".") || skip.has(entry.name)) continue;
      const full = path.join(dir, entry.name);
      latest = Math.max(latest, entry.isDirectory() ? newest(full) : statSync(full).mtimeMs);
    }
    return latest;
  };
  return newest(UI_ROOT) > builtAt;
}

/** 실행마다 테스트 상태를 비운다.
 *
 * 이게 없으면 e2e 계정이 무한정 쌓인다 — 2026-08-12 실측으로 364명 / accounts.json
 * 460KB / 감사로그 20MB였다. 계정 저장소는 가입 한 번에 **파일 전체를 다시 쓰므로**,
 * 쌓일수록 매 signup이 느려지고 그 지연이 다른 테스트의 타임아웃으로 튄다.
 * 실패가 실행마다 다른 테스트로 옮겨 다니던 이유 중 하나다.
 *
 * 지우는 대상은 테스트가 만든 산출물뿐이다(gitignore 대상). 사용자 데이터가 아니다.
 */
function resetTestData(): void {
  const dataDir = path.join(UI_ROOT, ".playwright-data");
  try {
    rmSync(dataDir, { recursive: true, force: true });
  } catch {
    // 못 지워도 테스트는 돌아간다 — 느려질 뿐이라 여기서 멈추지 않는다.
  }
}

export default function globalSetup(): void {
  resetTestData();
  if (!isBundleStale()) return;
  // 성공은 조용히, 실패는 시끄럽게 — 빌드가 깨졌으면 그 출력이 원인 그 자체다.
  execSync("npm run build", { cwd: UI_ROOT, stdio: "inherit" });
}
