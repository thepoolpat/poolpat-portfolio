#!/bin/bash
# test_discord_webhook.sh
# Send test message to Discord webhook
# Usage: ./test_discord_webhook.sh

WEBHOOK_URL=$(cat ~/poolpat-portfolio/.env.discord | grep DISCORD_WEBHOOK_URL | cut -d'=' -f2)

echo "Sending test message to Discord webhook..."

curl -X POST "$WEBHOOK_URL" \
   -H "Content-Type: application/json" \
   -d '{
     "content": "🎵 **Spotify Logging Test**\n\nYour Discord webhook is configured! 🎉\n\nTimestamp: '$(date)"
   }'

echo ""
echo "✅ Test message sent!"
