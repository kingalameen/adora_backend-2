#!/bin/bash
# Render build script
set -e

echo "Installing dependencies..."
pip install --upgrade pip
pip install --no-build-isolation --no-cache-dir -r requirements.txt

echo "Build complete and ready to deploy!"
