#!/bin/bash
# run_spotify_batch.sh - Auto-token-refresh batch logger
# Usage: ./run_spotify_batch.sh [N] (default: 50)
# Exit after N polls, auto-exports CSV

N=${1:-50}

echo "=========================================="
echo "🎵 Spotify Batch Logger (Auto-Token)"
echo "=========================================="
echo "Polls: ${N}"
echo "Cache: ~/.cache/spotify_oauth/"
echo "=========================================="
echo ""

# Run batch with cache-based token refresh
/opt/homebrew/bin/python3 ~/poolpat-portfolio/pipeline/run_batch_cached.py $N

# Export to CSV
echo ""
echo "📊 Exporting to CSV..."
sqlite3 ~/poolpat-portfolio/spotify_logs/analytics.db \
   ".mode csv" \
   ".output ~/poolpat-portfolio/spotify_logs/export_$(date +%Y%m%d_%H%M%S).csv" \
   "SELECT * FROM playback_history ORDER BY timestamp;"

echo "✅ Complete! Export: export_$(date +%Y%m%d_%H%M%S).csv"
