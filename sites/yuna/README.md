# Yuna AI website

This directory is the canonical source for the public Yuna AI website at
`https://yuse.studio/yuna/`.

It is intentionally separate from the cloud control plane. The desktop app may
link to these public pages, but the website and the separately configured
desktop API must remain independent deployments.

## Hosting contract

- Publish the contents of this directory below the `/yuna/` prefix.
- Do not change the desktop application's cloud API while deploying the site.
- Serve extensionless legal routes by resolving them to their matching HTML
  files (`terms.html`, `privacy.html`, `support.html`, and
  `account-deletion.html`).
- Resolve both `/yuna` and `/yuna/` to `yuna/index.html` without losing query
  parameters such as the selected language.
- Invalidate `/yuna*` after an upload when the CDN does not deploy atomically.

The production host currently resolves through Amazon CloudFront with an S3
origin. Deployment therefore requires access to the existing AWS distribution
and bucket; do not create a second distribution without confirming ownership.
Set `YUNA_S3_BUCKET` and `YUNA_CLOUDFRONT_DISTRIBUTION_ID` before running the
deployment helper; production account identifiers are intentionally not stored
in this repository.

`infra/cloudfront-yuna-router.js` mirrors the distribution's existing clean-URL
viewer-request function and adds the `/yuna` root exception. Update the existing
`yuse-studio-clean-urls` function rather than associating a second function or
replacing its other routes.
