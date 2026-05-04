#!/bin/bash
# OneTab sync script for LaunchAgent scheduling
# Usage: launchctl load ~/Library/LaunchAgents/com.maxbourke.ubm-onetab-sync.plist

set -e

cd /Users/maxbourke/Code/ubm
uv run ubm.py onetab >> ~/.ubm/onetab-sync.log 2>&1

exit 0
