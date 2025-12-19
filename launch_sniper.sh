#!/bin/bash
# Clean old files
rm -rf build dist Sniper_AI.spec

# Rebuild with "Collect All"
pyinstaller --noconfirm --onedir --windowed \
--icon "sniper.icns" \
--name "Sniper_AI" \
--add-data "templates:templates" \
--add-data "static:static" \
--collect-all "eventlet" \
--collect-all "dns" \
--hidden-import "engineio.async_drivers.eventlet" \
app.py