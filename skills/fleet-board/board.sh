#!/usr/bin/env bash
# board.sh — local task board for agent fleets (plain files, bash + awk only).
# Board dir: $BOARD, else .omc/fleet/${RUN:-default}/board
#   new   "<title>" [-t tier] [-d T-001,T-002] [-f path1,path2] [-a "acceptance"]
#   claim T-NNN <owner>                 atomic claim + exclusive file leases (WIP_LIMIT, default 1)
#   set   T-NNN <owner> <status> [note] doing|review|blocked (owner only)
#   note  T-NNN <owner> "<handoff note>"
#   done  T-NNN <owner> "<evidence>"    evidence required; releases leases
#   release T-NNN <owner>               give up: back to todo, release leases
#   list | index                        print table | regenerate board.md
set -euo pipefail
B="${BOARD:-.omc/fleet/${RUN:-default}/board}"
T="$B/tasks"; L="$B/locks"
mkdir -p "$T" "$L/files" "$B/ids"
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
die() { echo "board: $*" >&2; exit 1; }
file_of() { local f; f=$(ls "$T/$1"-*.md 2>/dev/null | head -1); [ -n "$f" ] || die "no task $1"; echo "$f"; }
fm() { awk -v k="$2" '/^---$/{n++; next} n==1 { i=index($0,":"); if (substr($0,1,i-1)==k) { v=substr($0,i+1); sub(/^ +/,"",v); print v; exit } }' "$1"; }
setfm() { # file key value — rewrite one frontmatter key, atomic via rename
  awk -v k="$2" -v v="$3" '/^---$/{n++} n==1 && index($0,k":")==1 {print k": "v; next} {print}' "$1" > "$1.tmp.$$" && mv "$1.tmp.$$" "$1"
}
log() { printf -- '- %s %s: %s\n' "$(now)" "$2" "$3" >> "$1"; setfm "$1" updated "$(now)"; }
own() { [ "$(fm "$1" owner)" = "$2" ] || die "$(fm "$1" id) is owned by '$(fm "$1" owner)', not $2"; }
key() { printf '%s' "$1" | tr '/ ' '__'; }
unlease() { local f; for f in $(fm "$1" files | tr ',' ' '); do rm -rf "$L/files/$(key "$f")"; done; }

cmd="${1:-list}"; shift || true
case "$cmd" in
new)
  title="${1:?title}"; shift; tier=sonnet deps= files= acc=
  while [ $# -gt 0 ]; do case "$1" in
    -t) tier="$2";; -d) deps="$2";; -f) files="$2";; -a) acc="$2";; *) die "bad flag $1";; esac; shift 2; done
  n=$(( $(ls "$B/ids" | wc -l) + 1 ))
  until mkdir "$B/ids/$n" 2>/dev/null; do n=$((n+1)); done   # atomic id allocation
  id=$(printf 'T-%03d' "$n")
  slug=$(printf '%s' "$title" | tr 'A-Z' 'a-z' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//' | cut -c1-40)
  f="$T/$id-$slug.md"
  cat > "$f" <<EOF
---
id: $id
title: $title
status: todo
owner:
tier: $tier
depends_on: $deps
files: $files
acceptance: $acc
created: $(now)
updated: $(now)
---
## Notes

## Log
EOF
  echo "$id" ;;
claim)
  id="${1:?id}" who="${2:?owner}"; f=$(file_of "$id")
  [ "$(fm "$f" status)" = todo ] || die "$id is $(fm "$f" status)"
  for d in $(fm "$f" depends_on | tr ',' ' '); do
    [ "$(fm "$(file_of "$d")" status)" = done ] || die "$id waits on $d"; done
  wip=$(grep -l "^owner: $who\$" "$T"/*.md 2>/dev/null | xargs grep -lE '^status: (claimed|doing|review)$' 2>/dev/null | wc -l || true)
  [ "$wip" -lt "${WIP_LIMIT:-1}" ] || die "$who at WIP limit ${WIP_LIMIT:-1}"
  mkdir "$L/$id.claim" 2>/dev/null || die "$id already claimed"          # the atomic step
  got=()
  for p in $(fm "$f" files | tr ',' ' '); do
    if mkdir "$L/files/$(key "$p")" 2>/dev/null; then echo "$id $who" > "$L/files/$(key "$p")/owner"; got+=("$p")
    else for g in "${got[@]:-}"; do [ -n "$g" ] && rm -rf "$L/files/$(key "$g")"; done
         rmdir "$L/$id.claim"; die "$p leased by $(cat "$L/files/$(key "$p")/owner" 2>/dev/null)"; fi
  done
  setfm "$f" owner "$who"; setfm "$f" status claimed; log "$f" "$who" claimed; echo "claimed $id by $who" ;;
set)
  id="${1:?id}" who="${2:?owner}" st="${3:?status}"; f=$(file_of "$id"); own "$f" "$who"
  case "$st" in doing|review|blocked) ;; *) die "use done/release for $st";; esac
  setfm "$f" status "$st"; log "$f" "$who" "-> $st ${4:-}" ;;
note)
  f=$(file_of "${1:?id}"); log "$f" "${2:?owner}" "${3:?note}" ;;
done)
  id="${1:?id}" who="${2:?owner}" ev="${3:-}"; f=$(file_of "$id"); own "$f" "$who"
  [ -n "$ev" ] || die "done needs evidence (test output tail, SHA, screenshot path)"
  setfm "$f" status done; log "$f" "$who" "DONE evidence: $ev"; unlease "$f"; echo "done $id" ;;
release)
  id="${1:?id}" who="${2:?owner}"; f=$(file_of "$id"); own "$f" "$who"
  unlease "$f"; rmdir "$L/$id.claim" 2>/dev/null || true
  setfm "$f" status todo; setfm "$f" owner ""; log "$f" "$who" released ;;
list|index)
  out=$( { echo "| id | status | owner | tier | depends_on | files | title |"; echo "|---|---|---|---|---|---|---|"
    for f in "$T"/*.md; do [ -e "$f" ] || continue
      echo "| $(fm "$f" id) | $(fm "$f" status) | $(fm "$f" owner) | $(fm "$f" tier) | $(fm "$f" depends_on) | $(fm "$f" files) | $(fm "$f" title) |"; done; } )
  if [ "$cmd" = index ]; then printf '# Board (%s)\n\n%s\n' "$(now)" "$out" > "$B/board.md"; echo "$B/board.md"; else echo "$out"; fi ;;
*) sed -n '2,10p' "$0"; exit 2 ;;
esac
