# Printify Bulk Uploader

Uses GitHub raw URLs to upload all designs in `public/designs/`.

## Setup
1. Set Vercel env var: `PRINTIFY_TOKEN`
2. (Optional) `GITHUB_BASE_URL` if you change repo/branch
3. Run the command to generate `designs.json` (see above)
4. Commit & push → Vercel auto-deploys
5. Test: `/debug` → `/status` → `/upload`

Cron runs every day at 02:00 UTC automatically.
