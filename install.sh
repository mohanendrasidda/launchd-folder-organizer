#!/usr/bin/env bash
# Installer for launchd-folder-organizer.
#
# Copies the script into ~/bin, materializes the plist with the current
# $HOME substituted in, and loads the launchd agent. Idempotent: prompts
# before overwriting existing files.
#
# Does NOT grant Full Disk Access. macOS only lets the user do that, via
# System Settings -> Privacy & Security -> Full Disk Access. See README.

set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/bin"
SCRIPT_DST="$BIN_DIR/organize-folders.py"
PLIST_SRC="$SRC_DIR/com.user.organize-folders.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.user.organize-folders.plist"
LABEL="com.user.organize-folders"
DOMAIN="gui/$(id -u)"

confirm_overwrite() {
    local target="$1"
    if [[ -e "$target" ]]; then
        read -r -p "Overwrite existing $target? [y/N] " reply
        [[ "$reply" =~ ^[Yy]$ ]]
    else
        return 0
    fi
}

echo "Installing organize-folders to $BIN_DIR ..."
mkdir -p "$BIN_DIR"
if confirm_overwrite "$SCRIPT_DST"; then
    cp "$SRC_DIR/organize_folders.py" "$SCRIPT_DST"
    chmod +x "$SCRIPT_DST"
    echo "  wrote $SCRIPT_DST"
else
    echo "  kept existing $SCRIPT_DST"
fi

echo "Installing launchd plist ..."
mkdir -p "$(dirname "$PLIST_DST")"
if confirm_overwrite "$PLIST_DST"; then
    sed "s|__HOME__|$HOME|g" "$PLIST_SRC" > "$PLIST_DST"
    echo "  wrote $PLIST_DST"
else
    echo "  kept existing $PLIST_DST"
fi

echo "Loading launchd agent ..."
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST_DST"
echo "  loaded $LABEL"

cat <<EOF

Installed. Next steps:

  1. Grant Full Disk Access to the .app wrapper so the agent can read
     ~/Documents and ~/Downloads under macOS sandboxing.

     The default plist runs an osacompile applet at:
         $HOME/Applications/OrganizeFolders.app

     If you have not created it yet, run:
         osacompile -e 'do shell script "$SCRIPT_DST"' \\
             -o "$HOME/Applications/OrganizeFolders.app"

     Then open System Settings -> Privacy & Security -> Full Disk Access,
     click +, and add OrganizeFolders.app.

  2. (Optional) Trigger an immediate run to verify:
         launchctl kickstart -k $DOMAIN/$LABEL

  3. Logs land in $HOME/Library/Logs/organize-folders/

EOF
