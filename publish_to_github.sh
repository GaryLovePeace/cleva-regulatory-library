#!/usr/bin/env bash
set -euo pipefail

REPO_NAME="${1:-cleva-regulatory-library}"
VISIBILITY="${2:-private}"

if [[ "$VISIBILITY" != "private" && "$VISIBILITY" != "public" ]]; then
  echo "Usage: ./publish_to_github.sh [repo-name] [private|public]" >&2
  exit 2
fi

if ! command -v git >/dev/null 2>&1; then
  echo "Git is not installed. Install Apple's command line tools: xcode-select --install" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is not installed. Run: brew install gh" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub login is required. Starting: gh auth login"
  gh auth login
fi

# Refuse to continue if local secret files are not ignored.
for secret in .env .streamlit/secrets.toml; do
  touch "$secret"
  if ! git check-ignore -q "$secret" 2>/dev/null; then
    rm -f "$secret"
    echo "Safety check failed: $secret is not ignored by Git." >&2
    exit 1
  fi
  rm -f "$secret"
done

if [[ ! -d .git ]]; then
  git init
fi

git branch -M main
git add .

if ! git diff --cached --quiet; then
  git commit -m "Deployable Cleva Regulatory Library"
else
  echo "No new files to commit."
fi

OWNER="$(gh api user --jq .login)"
FULL_REPO="$OWNER/$REPO_NAME"

if gh repo view "$FULL_REPO" >/dev/null 2>&1; then
  echo "Repository already exists: $FULL_REPO"
  if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "https://github.com/$FULL_REPO.git"
  fi
  git push -u origin main
else
  gh repo create "$REPO_NAME" "--$VISIBILITY" --source=. --remote=origin --push
fi

echo
echo "Published: https://github.com/$FULL_REPO"
echo "Next: deploy app.py from this repository in Streamlit Community Cloud."
