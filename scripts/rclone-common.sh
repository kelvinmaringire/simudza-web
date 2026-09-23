#!/usr/bin/env bash
# Shared rclone helpers for backup/restore scripts.

# Verify the remote works (refreshes short-lived access tokens when possible).
ensure_rclone_remote() {
  local remote="${1:-${RCLONE_REMOTE:-gdrive}}"
  local err_file
  err_file="$(mktemp)"
  trap 'rm -f "$err_file"' RETURN

  echo "  - Checking rclone remote ($remote)..."
  if rclone about "${remote}:" --timeout 2m 1>"$err_file" 2>&1; then
    return 0
  fi

  echo "Error: rclone remote '${remote}' is not reachable." >&2
  if grep -qiE 'invalid_grant|token expired|couldn.t fetch token' "$err_file"; then
    rclone_token_expiry_hint "$remote" >&2
  else
    cat "$err_file" >&2
  fi
  return 1
}

rclone_token_expiry_hint() {
  local remote="${1:-gdrive}"
  cat <<EOF

Google Drive OAuth token is invalid or expired (invalid_grant).

Fix now (on the VPS):
  rclone config reconnect ${remote}:
  # Answer: y
  # Open the URL in a browser, sign in, paste the verification code.

Headless VPS (no browser on server):
  1. On your laptop:  rclone authorize "drive"
  2. Copy the token blob rclone prints
  3. On the VPS:      rclone config reconnect ${remote}:
     Paste the token when prompted.

Prevent tokens expiring again:
  1. Google Cloud Console → APIs & Services → OAuth consent screen
     Set Publishing status to **Production** (Testing mode expires refresh tokens after ~7 days).
  2. Optional weekly health check cron:
     0 3 * * 0 cd $(pwd) && bash scripts/rclone-healthcheck.sh >> rclone-health.log 2>&1

Docs: https://rclone.org/drive/#making-your-own-client-id
EOF
}
