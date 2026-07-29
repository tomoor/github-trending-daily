// Cloudflare Worker: 定时触发 GitHub Actions workflow_dispatch
// Cron Triggers 见 wrangler.toml; GITHUB_TOKEN 通过 wrangler secret 注入
export default {
  async scheduled(event, env, ctx) {
    const resp = await fetch(
      "https://api.github.com/repos/tomoor/github-trending-daily/actions/workflows/daily.yml/dispatches",
      {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
          "Accept": "application/vnd.github+json",
          "User-Agent": "trending-dispatch-worker",
          "X-GitHub-Api-Version": "2022-11-28",
        },
        body: JSON.stringify({ ref: "main" }),
      },
    );
    if (resp.status === 204) {
      console.log(`dispatched ok at cron ${event.cron}`);
    } else {
      console.error(`dispatch failed: ${resp.status} ${await resp.text()}`);
    }
  },
};
