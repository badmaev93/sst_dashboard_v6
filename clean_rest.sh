#!/bin/bash
git fetch origin
git checkout main
git pull origin main

git branch -D try-merge-rest 2>/dev/null || true
git checkout -b try-merge-rest origin/main

BRANCHES=$(git branch -r | grep -v 'origin/main' | grep -v 'HEAD' | sed 's/.*origin\///')

SUCCESS=0
FAIL=0

for BRANCH in $BRANCHES; do
    echo "Attempting to merge $BRANCH..."
    if git merge "origin/$BRANCH" --no-edit; then
        echo "✅ Successfully merged $BRANCH"
        SUCCESS=$((SUCCESS + 1))
    else
        echo "❌ Conflict detected for $BRANCH. Aborting merge."
        git merge --abort
        FAIL=$((FAIL + 1))
    fi
done

echo "Merged: $SUCCESS, Failed: $FAIL"

git checkout main
git merge try-merge-rest
git push origin main

for BRANCH in $BRANCHES; do
    echo "Deleting $BRANCH..."
    git push origin --delete "$BRANCH" || true
done
