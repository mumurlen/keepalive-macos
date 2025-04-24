#!/bin/bash

# Fail on any error
set -e

APP_NAME="KeepAlive"

# Extract version from keepalive.py
APP_VERSION=$(grep '__version__' keepalive.py | cut -d '"' -f2)
DMG_NAME="$APP_NAME-$APP_VERSION.dmg"
APP_PATH="dist/$APP_NAME.app"

# Ensure the .app exists
if [ ! -d "$APP_PATH" ]; then
  echo "Error: $APP_PATH not found. Build the app first with py2app."
  exit 1
fi

# Remove any existing DMG with same name
rm -f "$DMG_NAME"

# Create the DMG
create-dmg \
  --volname "$APP_NAME Installer" \
  --window-pos 200 120 \
  --window-size 500 300 \
  --icon-size 100 \
  --icon "$APP_NAME.app" 125 150 \
  --app-drop-link 375 150 \
  "$DMG_NAME" \
  "dist/"

echo "✅ DMG created: $DMG_NAME"

