# Pushing this repo to GitHub

The repo is committed and ready (`git log` shows one commit on `main`). It could **not** be pushed
from the container because there are no GitHub credentials here. Push it yourself — two options.

## Option A — with the GitHub CLI (easiest)

In a terminal in your container:

```bash
gh auth login                      # one-time, follow the browser prompt
cd "/workspace/Lexerd Capital Management/maturity-radar"
gh repo create maturity-radar --private --source=. --remote=origin --push
```

If `gh` isn't installed: `sudo apt-get install gh` (or download from cli.github.com).

## Option B — with a Personal Access Token (no gh)

1. Create a token at github.com → Settings → Developer settings → Personal access tokens
   (classic), scope **repo**.
2. Run these, replacing `YOURNAME` and pasting the token when prompted (keep it out of shared logs):

```bash
cd "/workspace/Lexerd Capital Management/maturity-radar"

# create the empty repo (reads the token from an env var so it isn't stored)
read -s -p "token: " GH && echo
curl -s -H "Authorization: token $GH" https://api.github.com/user/repos \
  -d '{"name":"maturity-radar","private":true}' >/dev/null

# push
git remote add origin "https://$GH@github.com/YOURNAME/maturity-radar.git"
git push -u origin main
git remote set-url origin "https://github.com/YOURNAME/maturity-radar.git"   # drop the token from the remote
```

## Note on privacy

The sample properties, owners, and loans are **illustrative**, not real Lexerd or GSE records, so
the repo is safe to make public if you prefer — but `--private` is the safe default for interview
work.
