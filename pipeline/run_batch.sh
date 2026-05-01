#!/bin/bash
# Auto-run N× batch playback logging
# Usage: ./run_batch.sh [N] (default: 50)
# Exit after N polls, export CSV

N=${1:-50}

echo "🚀 Running ${N} poll batch..."
python3 ~/poolpat-portfolio/pipeline/run_batch.py $N

echo "📊 Exporting to CSV..."
sqlite3 ~/poolpat-portfolio/spotify_logs/analytics.db \
  ".mode csv" \
  ".output ~/poolpat-portfolio/spotify_logs/export_$(date +%Y%m%d_%H%M%S).csv" \
  "SELECT * FROM playback_history ORDER BY timestamp;"

echo "✅ Done! Export: ~/poolpat-portfolio/spotify_logs/export_$(date +%Y%m%d_%H%M%S).csv"
