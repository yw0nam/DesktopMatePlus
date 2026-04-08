#!/usr/bin/env bash
# pr-comments-filter.sh — Inline review comment resolver for a single PR
#
# Usage: pr-comments-filter.sh <owner/repo> <pr_number>
#
# Output:
#   SUMMARY: UNRESOLVED=N RESOLVED=N TOTAL=N
#   (one line per unresolved bot comment)
#   UNRESOLVED  <user>  <path>  <first 80 chars of body>

set -euo pipefail

REPO="${1:?Usage: pr-comments-filter.sh <owner/repo> <pr_number>}"
PR="${2:?Usage: pr-comments-filter.sh <owner/repo> <pr_number>}"

COMMENTS=$(gh api "repos/${REPO}/pulls/${PR}/comments" \
  --jq '[.[] | {id, in_reply_to_id, user: .user.login, path, body}]' 2>/dev/null)

# Build set of comment IDs that have at least one reply
# A bot comment is "resolved" if any reply exists with in_reply_to_id == bot_comment_id
echo "$COMMENTS" | jq -r '
  # IDs that are replied to
  ( [.[] | select(.in_reply_to_id != null) | .in_reply_to_id] | unique ) as $replied_ids |

  # Bot comment: login ends with "[bot]", or matches common bot prefixes.
  # Add new bots to the alternation as needed (e.g. "^dependabot|^renovate").
  def is_bot: test("\\[bot\\]$|^[Cc]opilot|^dependabot|^renovate");

  # Root bot comments (not a reply themselves)
  [ .[] | select(.user | is_bot) | select(.in_reply_to_id == null) ] as $bot_roots |

  # Unresolved = root bot comment whose id is NOT in replied_ids
  ( $bot_roots | map(select(.id as $id | $replied_ids | contains([$id]) | not)) ) as $unresolved |

  # Summary line
  "SUMMARY: UNRESOLVED=\($unresolved | length) RESOLVED=\($bot_roots | length - ($unresolved | length)) TOTAL=\(. | length)",

  # Detail lines for unresolved
  ( $unresolved[] |
    "UNRESOLVED\t\(.user)\t\(.path)\t\(.body | gsub("\\n";" ") | .[0:80])"
  )
'
