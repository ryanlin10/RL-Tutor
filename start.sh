#!/bin/bash
set -e

# Navigate to backend and start the server
cd backend
exec gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --threads 4 --timeout 120
