#!/bin/bash
# test_discord_webhook.sh
# Send test message to Discord webhook
# Usage: ./test_discord_webhook.sh

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEBHOOK_URL=$(grep DISCORD_WEBHOOK_URL "$REPO/.env.discord" | cut -d'=' -f2)

echo "Sending test message to Discord webhook..."

curl -X POST "$WEBHOOK_URL" \
   -H "Content-Type: application/json" \
   -d '{
     "content": "🎵 **Spotify Logging Test**\n\nYour Discord webhook is configured! 🎉\n\nTimestamp: '$(date)"
   }'

echo ""
echo "✅ Test message sent!"
