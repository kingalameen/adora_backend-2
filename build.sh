#!/bin/bash
# Render build script
set -e

echo "Installing dependencies..."
pip install --no-build-isolation --no-cache-dir -r requirements.txt

echo "Checking and fixing database if needed..."
# Add any database setup commands here if needed

echo "Build complete!"
