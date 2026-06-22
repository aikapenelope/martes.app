# apps/landing-us

Original US/English landing + blog + docs. Kept for reference and as the
source for the `/us/`, `/blog/`, `/docs/` subroutes of the new VE primary
landing (built and copied by `apps/landing/Dockerfile`).

## When to use

This folder is the source of truth for:
- The US landing page
- The blog content (3 posts)
- The docs content (4 pages)

In `apps/landing/`, the multi-stage `Dockerfile` builds this app and
copies the relevant `dist/` outputs into the unified nginx container.

## Build standalone

```bash
cd apps/landing-us
npm install
npm run build
```

Output: `dist/`
