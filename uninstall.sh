#!/usr/bin/env bash
# Uninstaller for launchd-folder-organizer.
#
# Unloads the launchd agent, removes the plist and the script. Leaves the
# log directory in place so prior moves.tsv entries remain available for
# review or rollback.

set -euo pipefail

SCRIPT_DST="$HOME/bin/organize-folders.py"
PLIST_DST="$HOME/Library/LaunchAgents/com.user.organize-folders.plist"
LABEL="com.user.organize-folders"
DOMAIN="gui/$(id -u)"
LOG_DIR="$HOME/Library/Logs/organize-folders"

echo "Unloading launchd agent ..."
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null && echo "  unloaded $LABEL" \
    || echo "  $LABEL was not loaded"

if [[ -e "$PLIST_DST" ]]; then
    rm "$PLIST_DST"
    echo "  removed $PLIST_DST"
fi

if [[ -e "$SCRIPT_DST" ]]; then
    rm "$SCRIPT_DST"
    echo "  removed $SCRIPT_DST"
fi

if [[ -d "$LOG_DIR" ]]; then
    echo
    echo "Logs left in place at $LOG_DIR"
    echo "(remove with: rm -rf '$LOG_DIR')"
fi

echo
echo "Uninstall complete. The .app wrapper at ~/Applications/OrganizeFolders.app"
echo "(if present) was NOT removed, and its Full Disk Access entry remains in"
echo "System Settings. Remove both manually if you want a clean slate."
