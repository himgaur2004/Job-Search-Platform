# 03 — Frontend Dashboard

## Scope Check First
The core agent runs headless (cron/GitHub Actions) — it doesn't need a frontend to function. The dashboard is a **read-mostly reporting layer**: emails sent, replies, interviews, follow-ups due. Treat it as optional-but-valuable, not blocking.

## Stack (all free tier)
| Layer | Choice | Why |
|---|---|---|
| Framework | Next.js (App Router) | Free Vercel hosting, built-in API routes if needed |
| Hosting | Vercel Hobby plan | Free, auto-deploys from GitHub, HTTPS included |
| Styling | Tailwind CSS | No build cost, fast to ship |
| Charts | Recharts | Free, lightweight, good enough for daily counts |
| Auth (optional) | Simple shared-secret query param or NextAuth + GitHub OAuth (free) | You're the only user — don't over-build auth |
| Data fetching | Direct read from your Postgres/SQLite via a thin API route | No separate backend service needed just for reads |

## Pages
```
app/
  page.tsx                → Dashboard home (today's summary)
  jobs/page.tsx            → Table of all jobs processed, with match score, status
  replies/page.tsx         → Classified replies (Interview/Rejected/etc.)
  followups/page.tsx       → Due-for-follow-up list
  api/
    summary/route.ts       → GET aggregate counts
    jobs/route.ts           → GET paginated job list
```

## Dashboard Home — Key Metrics
Mirror what your plan already specifies, rendered as simple stat cards + one chart:
- Emails sent today / this week
- Replies received (with category breakdown)
- Interviews scheduled
- Companies contacted (unique count)
- Follow-ups due (count + list)
- Success rate = interviews / emails sent

```tsx
// app/page.tsx (simplified)
async function getSummary() {
  const res = await fetch(`${process.env.API_BASE_URL}/api/summary`, { cache: "no-store" });
  return res.json();
}

export default async function Dashboard() {
  const data = await getSummary();
  return (
    <main className="p-8 grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatCard label="Sent Today" value={data.sentToday} />
      <StatCard label="Replies" value={data.replies} />
      <StatCard label="Interviews" value={data.interviews} />
      <StatCard label="Success Rate" value={`${data.successRate}%`} />
    </main>
  );
}
```

## Data Access Pattern
Since the agent already writes to Postgres (recommend Supabase free tier — see doc 04), the dashboard's API routes are thin read queries, not a duplicate backend:

```ts
// app/api/summary/route.ts
import { sql } from "@/lib/db"; // shared pg client

export async function GET() {
  const sent = await sql`SELECT COUNT(*) FROM emails WHERE sent_at::date = CURRENT_DATE`;
  const interviews = await sql`SELECT COUNT(*) FROM replies WHERE category = 'INTERVIEW'`;
  // ... aggregate and return
  return Response.json({ sentToday: sent[0].count, interviews: interviews[0].count });
}
```

## Design Guidance
- Keep it information-dense, not decorative — this is a personal ops dashboard, not a marketing site. A clean table + 4–6 stat cards is enough.
- Use relative time ("2h ago") for the jobs table and absolute dates for anything older than a day.
- Color-code status: green (interview), yellow (need info), gray (no reply), red (rejected) — consistent with the classification categories from doc 02.
- Mobile isn't a priority here, but Tailwind's responsive classes make it near-free to support anyway — don't skip it just because it's "internal."

## Deployment (Free, Zero Config Maintenance)
1. Push repo to GitHub.
2. Connect repo in Vercel (free Hobby tier) — auto-builds on every push to `main`.
3. Set environment variables (`DATABASE_URL`, etc.) in Vercel project settings — never commit them.
4. Optional: put the dashboard behind a simple password using Vercel's free "Password Protection" (Hobby tier supports this for personal projects) or a lightweight `middleware.ts` check against a shared secret, since this exposes your job-search activity and shouldn't be public.

## What NOT to build
- Don't build a separate frontend "send email now" trigger button unless you specifically want manual override control — it adds auth/security surface (anyone with the URL could trigger sends) for a feature the cron job already handles. If you do want it, gate it behind the same shared-secret check and call a dedicated, rate-limited backend endpoint — never let the frontend hold Gmail credentials directly.
- Don't add real-time websockets/polling — a dashboard that refreshes on page load (or every few minutes via `revalidate`) is more than sufficient for a once-daily batch job.
