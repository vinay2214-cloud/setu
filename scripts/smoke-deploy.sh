#!/usr/bin/env bash
# Smoke test for a running Setu deployment (Render or local).
# Usage: scripts/smoke-deploy.sh https://your-service.onrender.com
#        SKIP_WEB=1 scripts/smoke-deploy.sh http://localhost:8000     (API only)
# Env:   EMAIL / PASSWORD override the demo login. KEEP_STATE=1 leaves the hero-run data in place.
# It RESETS and RE-SEEDS the demo data, runs the 5-step hero scenario, then resets again so the
# app is clean for recording. Use only on a demo deployment (DEMO_MODE=true) with synthetic data.
set -uo pipefail
BASE="${1:?usage: $0 <base-url>}"; BASE="${BASE%/}"
API="$BASE/api/v1"; EMAIL="${EMAIL:-dr.anitha@demo.setu}"; PASSWORD="${PASSWORD:-demo123}"
JAR="$(mktemp)"; trap 'rm -f "$JAR"' EXIT
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  \033[31mFAIL\033[0m %s\n' "$1"; [ -n "${2:-}" ] && printf '       %s\n' "$2"; }
check(){ if [ "$2" = "1" ]; then ok "$1"; else bad "$1" "${3:-}"; fi; }
post() { curl -sS -m 60 -b "$JAR" -c "$JAR" -H 'content-type: application/json' -X POST -d "$2" "$API$1"; }
get()  { curl -sS -m 60 -b "$JAR" -c "$JAR" "$API$1"; }
py()   { python3 -c "$1"; }

echo "Setu deployment smoke test -> $BASE"

echo "1. Service is up (waits up to ~3 min for a cold start)"
H=""
for i in $(seq 1 18); do
  H="$(curl -sS -m 15 "$API/health" 2>/dev/null || true)"
  echo "$H" | grep -q '"status":"ok"' && break
  sleep 10
done
check "health returns ok" "$(echo "$H" | grep -q '"status":"ok"' && echo 1 || echo 0)" "$H"
check "22 rules loaded" "$(echo "$H" | grep -q '"rules_loaded":22' && echo 1 || echo 0)" "$H"
check "mock AI active (offline-safe)" "$(echo "$H" | grep -q '"llm":"mock"' && echo 1 || echo 0)" "$H"
if [ "${SKIP_WEB:-0}" != "1" ]; then
  CODE="$(curl -sS -m 30 -o /dev/null -w '%{http_code}' "$BASE/login" || echo 000)"
  check "login page loads (HTTP $CODE)" "$([ "$CODE" = 200 ] && echo 1 || echo 0)"
  CODE="$(curl -sS -m 30 -o /dev/null -w '%{http_code}' "$BASE/sim" || echo 000)"
  check "simulator page responds (HTTP $CODE)" "$([ "$CODE" = 200 ] || [ "$CODE" = 307 ] || [ "$CODE" = 308 ] || [ "$CODE" = 302 ] && echo 1 || echo 0)"
fi

echo "2. Login and live stream"
R="$(post /auth/login "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")"
check "login succeeds" "$(echo "$R" | grep -q 'clinician' && echo 1 || echo 0)" "$R"
check "session cookie works (/auth/me)" "$(get /auth/me | grep -q '"id"' && echo 1 || echo 0)"
HDR="$(curl -sS -N -m 4 -D - -o /dev/null -b "$JAR" "$API/alerts/stream" 2>/dev/null || true)"
check "alert stream is text/event-stream" "$(echo "$HDR" | tr -d '\r' | grep -qi 'content-type: text/event-stream' && echo 1 || echo 0)" "$(echo "$HDR" | head -3 | tr '\r\n' ' ')"

echo "3. Reset and seed"
post /demo/reset '{}' >/dev/null
S="$(post /demo/seed '{"scenario":"default"}')"
check "seed created 5 patients and 3 starting alerts" "$(echo "$S" | grep -q '"patients":5' && echo "$S" | grep -q '"alerts":3' && echo 1 || echo 0)" "$S"
check "clock is Day 8 morning (day_offset)" "$(get /demo/state | grep -q '"now":"2026-10-26T02:30' && echo 1 || echo 0)" "$(get /demo/state)"

echo "4. Hero scenario (5 steps)"
STEP1="$(post /demo/scenario-step '{"patient_id":"P001","step":1}')"
for s in 2 3 4; do post /demo/scenario-step "{\"patient_id\":\"P001\",\"step\":$s}" >/dev/null; done
check "step 1 sent a Telugu check-in with greeting first" "$(echo "$STEP1" | py "
import sys,json
m=json.load(sys.stdin)['messages']
print(1 if m and m[0]['template_key']=='greeting_morning' and 'సేతు' in m[0]['text'] else 0)" 2>/dev/null || echo 0)" "$(echo "$STEP1" | head -c 300)"
A="$(get /alerts)"
check "one HIGH R-COMBO-01 alert for P001 with R-ADH-01 as a contributing flag, call approved" "$(echo "$A" | py "
import sys,json
d=json.load(sys.stdin); it=d['items'] if isinstance(d,dict) else d
hits=[a for a in it if a['patient']['id']=='P001' and a['rule']['id']=='R-COMBO-01']
a=hits[0] if hits else None
print(1 if a and a['severity']=='HIGH' and a['status']=='acknowledged' and 'R-ADH-01' in [c['id'] for c in a.get('contributing_rules',[])] and len(a.get('evidence',[]))>=2 else 0)" 2>/dev/null || echo 0)" "$(echo "$A" | head -c 300)"
post /demo/scenario-step '{"patient_id":"P001","step":5}' >/dev/null
A="$(get /alerts)"
check "CRITICAL R-CRIT-SYM-01 alert from the chest-pain message" "$(echo "$A" | py "
import sys,json
d=json.load(sys.stdin); it=d['items'] if isinstance(d,dict) else d
print(1 if any(a['patient']['id']=='P001' and a['rule']['id']=='R-CRIT-SYM-01' and a['severity']=='CRITICAL' for a in it) else 0)" 2>/dev/null || echo 0)"
M="$(get /patients/P001/messages)"
check "fixed emergency reply (Telugu, contains 108) was sent" "$(echo "$M" | py "
import sys,json
d=json.load(sys.stdin); it=d['items'] if isinstance(d,dict) else d
print(1 if any(m['direction']=='out' and m.get('template_key')=='emergency_advice' and '108' in m['text'] for m in it) else 0)" 2>/dev/null || echo 0)"
check "check-in messages are in the right order" "$(echo "$M" | py "
import sys,json
d=json.load(sys.stdin); it=d['items'] if isinstance(d,dict) else d
keys=[m['template_key'] for m in it if m['direction']=='out' and m.get('template_key')]
want=['greeting_morning','ask_meds_morning','ask_glucose','ask_symptoms']
i=keys.index('greeting_morning') if 'greeting_morning' in keys else -1
print(1 if i>=0 and keys[i:i+4]==want else 0)" 2>/dev/null || echo 0)"
check "demo controls report mock provider" "$(get /demo/state | grep -q '"llm_provider":"mock"' && echo 1 || echo 0)"

if [ "${KEEP_STATE:-0}" != "1" ]; then
  echo "5. Clean up for recording"
  post /demo/reset '{}' >/dev/null
  S="$(post /demo/seed '{"scenario":"default"}')"
  check "re-seeded to the clean starting state" "$(echo "$S" | grep -q '"patients":5' && echo 1 || echo 0)" "$S"
fi

echo; echo "Result: $PASS passed, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then echo "READY FOR RECORDING"; else echo "NOT READY - fix the FAIL lines above first"; fi
[ "$FAIL" -eq 0 ]
