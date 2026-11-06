# OpenNext Starter

This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

Read the documentation at https://opennext.js.org/cloudflare.

## Develop

Run the Next.js development server:

```bash
npm run dev
# or similar package manager command
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

## Preview

Preview the application locally on the Cloudflare runtime:

```bash
npm run preview
# or similar package manager command
```

## Deploy

Production deploys run through Cloudflare Workers Builds, the GitHub integration on the Worker. There is no GitHub Actions workflow. Connect `DavidSRoy/packet-code` in the Worker’s Settings → Build:

| Setting | Value |
| --- | --- |
| Production branch | `master` |
| Root directory | `landing` |
| Build command | `npx opennextjs-cloudflare build` |
| Deploy command | `npx opennextjs-cloudflare deploy` |
| Preview command | `npx wrangler preview` |

The Worker is `packet-landing`. Production signups go to the `packet-landing` D1 database.

### Previews (one URL per branch)

With **Settings → Build → Branch control → Enable Preview Builds** turned on, every push to a branch other than `master` runs the build command, then `npx wrangler preview`. The branch gets a stable Preview URL that follows its latest push, and the pull request gets a comment with the link. Find all Previews in the Worker's **Previews** section.

Previews use the `previews` block in `wrangler.jsonc`, not the production settings. Signups from a Preview go to the `packet-landing-preview` D1 database, never to production. When you add a migration, apply it to both databases:

```bash
npx wrangler d1 migrations apply packet-landing --remote
npx wrangler d1 migrations apply packet-landing-preview --remote --config wrangler.preview-migrations.jsonc
```

Preview URLs are public. To require sign-in, put them behind Cloudflare Access.

`npm run deploy` builds and deploys from a machine. That bypasses Workers Builds, so those runs do not show up in the Cloudflare build log.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!
