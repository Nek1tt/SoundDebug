#!/usr/bin/env sh
set -eu
branch="${1:-release/mvp-2026-08-23}"
current="$(git branch --show-current)"
if [ "$current" != "$branch" ]; then
  if git show-ref --verify --quiet "refs/heads/$branch"; then git switch "$branch"; else git switch -c "$branch"; fi
fi
git add -A
git status --short
echo "Review the list above, then run:"
echo 'git commit -m "feat: ship SoundDebug MVP with Demucs"'
echo "git push -u origin $branch"
echo "Then open a pull request from $branch into main."
