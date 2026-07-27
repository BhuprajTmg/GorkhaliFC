#!/bin/bash
# Run this on PythonAnywhere Bash console to update the live site:
#   bash scripts/pythonanywhere_update.sh
set -euo pipefail

cd ~/GorkhaliFC
source ~/.virtualenvs/gurkhali/bin/activate

echo "==> Fetching latest main from GitHub..."
git fetch origin
git checkout main
git reset --hard origin/main

echo "==> Installing dependencies..."
pip install -r requirements.txt

echo "==> Migrating database..."
python manage.py migrate --noinput

echo "==> Repairing legacy DB artifacts (duplicates / stale indexes)..."
python manage.py db_doctor || true

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Django check..."
python manage.py check

echo "==> Reloading the web app..."
# PythonAnywhere reloads the site when its WSGI file is touched.
RELOADED=0
for wsgi in /var/www/*_wsgi.py; do
  if [ -f "$wsgi" ]; then
    touch "$wsgi"
    echo "    touched $wsgi"
    RELOADED=1
  fi
done
if [ "$RELOADED" -eq 0 ]; then
  echo "    !! No /var/www/*_wsgi.py found — click Reload on the Web tab instead."
fi

echo
echo "DONE."
echo "Verify the live site is serving new code (should NOT contain '#register'):"
echo "  curl -s https://\$USER.pythonanywhere.com/ | grep -o 'action=\"[^\"]*\"' | head"
