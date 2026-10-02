#!/usr/bin/env sh
set -e

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

BASE=http://localhost:${BACKEND_PORT:-8000}

# request AUTH_TOKEN METHOD PATH [JSON_BODY] -> prints the response body; aborts the smoke test on HTTP >= 400.
request() {
  OUT=$(curl -s -w '\n%{http_code}' -X "$2" "$BASE$3" ${1:+-H "Authorization: Bearer $1"} -H 'Content-Type: application/json' ${4:+-d "$4"})
  CODE=$(echo "$OUT" | tail -n 1)
  BODY=$(echo "$OUT" | sed '$d')
  if [ -z "$CODE" ] || [ "$CODE" -ge 400 ] || [ "$CODE" = "000" ]; then
    echo "FAILED: $2 $3 -> HTTP $CODE $BODY" >&2
    exit 1
  fi
  echo "$BODY"
}

# Facilitator calls carry the researcher token; guest calls go unauthenticated like the invite flow.
api() { request "$TOKEN" "$@"; }
guest_api() { request "" "$@"; }

TOKEN=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' -d '{"email":"researcher@example.com","password":"researcher123"}' | sed -E 's/.*"access_token":"([^"]+)".*/\1/')

echo "Token acquired"

PROJECT=$(api POST /projects '{"title":"Smoke Project","ai_mode_enabled":false}')
PID=$(echo "$PROJECT" | sed -E 's/.*"id":([0-9]+).*/\1/')

echo "Project $PID created"

PARTICIPANTS=$(api GET /projects/$PID/participants)
FAC=$(echo "$PARTICIPANTS" | sed -E 's/.*\{"id":([0-9]+).*/\1/')

# Advancing past phase 1 requires every canvas field to be filled.
QUESTION_KEYS=$(api GET /projects/$PID/canvas | grep -o '"question_key":"[^"]*"' | sed -E 's/"question_key":"([^"]*)"/\1/')
for KEY in $QUESTION_KEYS; do
  api PUT /projects/$PID/canvas/$KEY/response "{\"participant_id\":$FAC,\"content\":\"Smoke test answer for $KEY: need better ML maintainability\"}" > /dev/null
done
echo "Canvas responses submitted ($(echo "$QUESTION_KEYS" | wc -w | tr -d ' ') fields)"

api POST /projects/$PID/advance-phase '{}' > /dev/null
echo "Project advanced to phase 2"

INVITE=$(api POST /projects/$PID/invites '{}')
URL=$(echo "$INVITE" | sed -E 's/.*"invite_url":"([^"]+)".*/\1/' | sed 's#\\/##g')
TOKEN_INV=$(echo "$URL" | awk -F'/invite/' '{print $2}')

JOIN=$(guest_api POST /invites/$TOKEN_INV/accept '{"email":"alice.acme@invite.local"}')
PART=$(echo "$JOIN" | sed -E 's/.*"participant_id":([0-9]+).*/\1/')
echo "Participant $PART joined"

api POST /projects/$PID/advance-phase '{}' > /dev/null
PROJECT_STATE=$(guest_api GET "/projects/$PID?participant_id=$PART")
if ! echo "$PROJECT_STATE" | grep -q "\"current_phase\":3"; then
  echo "FAILED: guest does not see phase 3: $PROJECT_STATE" >&2
  exit 1
fi
echo "Guest sees updated phase via polling endpoint"

echo "Smoke flow executed"
