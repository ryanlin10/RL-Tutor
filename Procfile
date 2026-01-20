web: cd backend && gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
release: cd backend && flask db upgrade
