#!/bin/bash
# Run this after homly.py to push scraped data to GitHub.
# The cloud dashboard will auto-refresh with the new results.

set -e

cd "$(dirname "$0")"

if [ ! -d "yad2_output" ] || [ -z "$(ls -A yad2_output 2>/dev/null)" ]; then
    echo "No data found in yad2_output/. Run homly.py first."
    exit 1
fi

git add yad2_output/
git commit -m "Update scraped data — $(date '+%Y-%m-%d %H:%M')"
git push

echo ""
echo "Done. Your dashboard will refresh in ~30 seconds."
