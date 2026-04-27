#!/bin/bash
# Enable Discord logging for Spotify analytics
# Requires: Discord webhook URL from your server

echo "🔔 Setting up Discord webhook..."

# Get webhook URL from user
echo "Enter your Discord webhook URL:"
read WEBHOOK_URL

if [ -z "$WEBHOOK_URL" ]; then
    echo "❌ No webhook URL provided"
    exit 1
fi

# Save to env file
echo "DISCORD_WEBHOOK_URL=$WEBHOOK_URL" >> ../.env.discord

echo "✅ Discord webhook configured!"
echo "   URL saved to: .env.discord"
echo ""
echo "Test: hermes send-message target=discord:#general message='Spotify logging ready'"
