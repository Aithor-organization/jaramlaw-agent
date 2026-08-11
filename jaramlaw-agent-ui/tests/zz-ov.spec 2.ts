import { test } from "@playwright/test";
test("find overflow", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile", "mobile only");
  await page.goto("/");
  const out = await page.evaluate(() => {
    const w = document.documentElement.clientWidth;
    const bad: string[] = [];
    document.querySelectorAll<HTMLElement>("*").forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.right > w + 1 || r.left < -1) bad.push(`${el.tagName}.${el.className}` + ` L${Math.round(r.left)} R${Math.round(r.right)} (vw=${w})`);
    });
    return bad.slice(0, 8);
  });
  console.log("OVERFLOW:", JSON.stringify(out, null, 1));
});
