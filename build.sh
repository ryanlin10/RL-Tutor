#!/bin/bash
set -e

echo "Building frontend..."
cd frontend
npm ci
npm run build

echo "Copying frontend build to backend..."
mkdir -p ../backend/static
cp -r dist/* ../backend/static/

echo "Installing backend dependencies..."
cd ../backend
pip install -r requirements.txt

echo "Build complete!"
