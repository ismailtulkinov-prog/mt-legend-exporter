#!/usr/bin/env bash
set -euo pipefail

REPO_NAME="${1:-mt-legend-exporter}"
VISIBILITY="${2:-public}"
DESCRIPTION="${3:-Mod for Mir Tankov that exports the Onslaught Legend threshold from the client}"
TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"

if [[ -z "${TOKEN}" ]]; then
  echo "Set GITHUB_TOKEN or GH_TOKEN first."
  exit 1
fi

if [[ ! -d .git ]]; then
  echo "Run this script from the git repository root."
  exit 1
fi

if [[ "${VISIBILITY}" != "public" && "${VISIBILITY}" != "private" ]]; then
  echo "Visibility must be 'public' or 'private'."
  exit 1
fi

AUTH_HEADER="Authorization: Bearer ${TOKEN}"
ACCEPT_HEADER="Accept: application/vnd.github+json"

LOGIN="$(
  curl -fsSL \
    -H "${AUTH_HEADER}" \
    -H "${ACCEPT_HEADER}" \
    https://api.github.com/user | python3 -c 'import json,sys; print(json.load(sys.stdin)["login"])'
)"

PRIVATE=false
if [[ "${VISIBILITY}" == "private" ]]; then
  PRIVATE=true
fi

CREATE_HTTP_CODE="$(
  curl -sS -o /tmp/github-create-repo.json -w "%{http_code}" \
    -H "${AUTH_HEADER}" \
    -H "${ACCEPT_HEADER}" \
    https://api.github.com/user/repos \
    -d "$(printf '{"name":"%s","description":"%s","private":%s}' "${REPO_NAME}" "${DESCRIPTION}" "${PRIVATE}")"
)"

if [[ "${CREATE_HTTP_CODE}" != "201" && "${CREATE_HTTP_CODE}" != "422" ]]; then
  echo "GitHub API error:"
  cat /tmp/github-create-repo.json
  exit 1
fi

git branch -M main
git remote remove origin >/dev/null 2>&1 || true
git remote add origin "https://github.com/${LOGIN}/${REPO_NAME}.git"
git push "https://x-access-token:${TOKEN}@github.com/${LOGIN}/${REPO_NAME}.git" main

echo "https://github.com/${LOGIN}/${REPO_NAME}"
