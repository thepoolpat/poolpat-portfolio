#!/bin/bash
# test_discord_webhook.sh
# Send test message to Discord webhook
# Usage: ./test_discord_webhook.sh

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEBHOOK_URL=$(grep DISCORD_WEBHOOK_URL "$REPO/.env.discord" | cut -d'=' -f2)

echo "Sending test message to Discord webhook..."

payload=$(cat <<EOF
{"content": "🎵 **Spotify Logging Test**\n\nYour Discord webhook is configured! 🎉\n\nTimestamp: $(date)"}
EOF
)

curl -X POST "$WEBHOOK_URL" \
   -H "Content-Type: application/json" \
   -d "$payload"

echo ""
echo "✅ Test message sent!"
