#!/usr/bin/env sh
set -e

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

BASE=http://localhost:${BACKEND_PORT:-8000}

TOKEN=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' -d '{"email":"researcher@example.com","password":"researcher123"}' | sed -E 's/.*"access_token":"([^"]+)".*/\1/')

echo "Token acquired"

PROJECT=$(curl -s -X POST $BASE/projects -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"title":"Smoke Project","ai_mode_enabled":false}')
PID=$(echo "$PROJECT" | sed -E 's/.*"id":([0-9]+).*/\1/')

echo "Project $PID created"

PARTICIPANTS=$(curl -s -X GET $BASE/projects/$PID/participants -H "Authorization: Bearer $TOKEN")
FAC=$(echo "$PARTICIPANTS" | sed -E 's/.*\{"id":([0-9]+).*/\1/')

curl -s -X PUT $BASE/projects/$PID/canvas/problem/response -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"participant_id\":$FAC,\"content\":\"Need better ML maintainability\"}" > /dev/null
echo "Canvas response submitted"

curl -s -X POST $BASE/projects/$PID/advance-phase -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' > /dev/null
echo "Project advanced to phase 2"

INVITE=$(curl -s -X POST $BASE/projects/$PID/invites -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}')
URL=$(echo "$INVITE" | sed -E 's/.*"invite_url":"([^"]+)".*/\1/' | sed 's#\\/##g')
TOKEN_INV=$(echo "$URL" | awk -F'/invite/' '{print $2}')

JOIN=$(curl -s -X POST $BASE/invites/$TOKEN_INV/accept -H 'Content-Type: application/json' -d '{"email":"alice.acme@invite.local"}')
PART=$(echo "$JOIN" | sed -E 's/.*"participant_id":([0-9]+).*/\1/')
echo "Participant $PART joined"

curl -s -X POST $BASE/projects/$PID/advance-phase -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' > /dev/null
PROJECT_STATE=$(curl -s -X GET "$BASE/projects/$PID?participant_id=$PART")
echo "$PROJECT_STATE" | grep -q "\"current_phase\":3" && echo "Guest sees updated phase via polling endpoint"

echo "Smoke flow executed"
