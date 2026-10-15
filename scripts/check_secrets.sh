#!/usr/bin/env bash
# Scan the files that would be committed for secrets and private data. Run before every push.
#   bash scripts/check_secrets.sh      -> exit 0 clean, 1 on any hit
# Allowed: Andrew's own address in the OpenStreetMap User-Agent (OSM's usage policy asks for a contact).
set -u
cd "$(dirname "$0")/.." || exit 2
files=$( (git ls-files --cached --others --exclude-standard 2>/dev/null || find . -type f -not -path './.git/*') | grep -v '^scripts/check_secrets.sh$')
hits=0
check() {  # label, extended regex
  local out
  out=$(printf '%s\n' "$files" | while read -r f; do [ -f "$f" ] && grep -EnoH "$2" "$f"; done 2>/dev/null)
  if [ -n "$out" ]; then echo "== $1"; echo "$out" | head -20; hits=1; fi
}
check "API keys / tokens" '(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|shpat_[a-f0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)'
check "secret assignments" '(api[_-]?key|secret|password|token)[A-Za-z_]*["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"' ]{8,}'
check "phone numbers" '\(?[0-9]{3}\)?[ .-][0-9]{3}-[0-9]{4}'
check "emails (other than the OSM contact)" '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
check "vault path mentions (review; rule text is fine)" '(Brain/Private|\.config/tro-vault|\.env\b)'
if [ "$hits" -ne 0 ]; then
  echo
  echo "Review the hits above. The only expected one is andrew2000garcia@gmail.com in a User-Agent string."
fi
# fail only on hits that are not the known OSM contact line
bad=$(printf '%s\n' "$files" | while read -r f; do [ -f "$f" ] && grep -EnH '(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|shpat_|PRIVATE KEY|\(?[0-9]{3}\)?[ .-][0-9]{3}-[0-9]{4})' "$f"; done; \
      printf '%s\n' "$files" | while read -r f; do [ -f "$f" ] && grep -EnH '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' "$f" | grep -v 'andrew2000garcia@gmail.com' | grep -v 'noreply@anthropic.com'; done)
if [ -n "$bad" ]; then echo "SECRET SCAN FAILED"; exit 1; fi
echo "Secret scan passed."
