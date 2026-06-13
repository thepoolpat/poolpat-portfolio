#!/bin/bash
# setup_discord_webhook.sh
# Configure Discord webhook for Spotify playback notifications
# Usage: ./setup_discord_webhook.sh

echo "=========================================="
echo "🔔 Setup Discord Webhook for Spotify"
echo "=========================================="
echo ""
echo "1. Go to your Discord server → Server Settings"
echo "2. Navigate to Integrations → Webhooks"
echo "3. Create new webhook or copy existing URL"
echo "4. Paste webhook URL below"
echo ""
read -p "Enter webhook URL: " WEBHOOK_URL

# Update .env.discord (repo root, derived from this script's location)
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

rm -f .env.discord
cat > .env.discord << EOF
# Discord webhook URL for Spotify playback notifications
# Generated: $(date)
DISCORD_WEBHOOK_URL=${WEBHOOK_URL}
EOF

chmod 600 .env.discord

echo ""
echo "=========================================="
echo "✅ Webhook configured!"
echo "=========================================="
echo "File: $REPO/.env.discord"
echo "Webhook: ${WEBHOOK_URL}"
echo ""
echo "The batch logger will now send notifications to Discord when tracks change"
echo "=========================================="
