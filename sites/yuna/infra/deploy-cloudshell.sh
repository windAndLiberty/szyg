#!/usr/bin/env bash
set -euo pipefail

: "${YUNA_S3_BUCKET:?Set YUNA_S3_BUCKET to the existing website bucket}"
: "${YUNA_CLOUDFRONT_DISTRIBUTION_ID:?Set YUNA_CLOUDFRONT_DISTRIBUTION_ID to the existing distribution}"
release_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
site_dir="$(cd "${release_root}/.." && pwd)"

if [[ ! -f "${site_dir}/index.html" ]]; then
  echo "Missing ${site_dir}/index.html" >&2
  exit 1
fi

aws s3 sync "${site_dir}/" "s3://${YUNA_S3_BUCKET}/yuna/" \
  --cache-control "public,max-age=300"

# Keep the versioned hero asset cacheable while setting its MIME type
# explicitly (CloudShell's platform MIME database can vary).
aws s3 cp "${site_dir}/yuna-command-center-wide.webp" \
  "s3://${YUNA_S3_BUCKET}/yuna/yuna-command-center-wide.webp" \
  --content-type "image/webp" \
  --cache-control "public,max-age=31536000,immutable"

aws cloudfront create-invalidation \
  --distribution-id "${YUNA_CLOUDFRONT_DISTRIBUTION_ID}" \
  --paths "/yuna" "/yuna/*"

echo "Yuna website uploaded. Wait for the invalidation to complete before verification."
