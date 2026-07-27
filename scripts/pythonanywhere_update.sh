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

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Django check..."
python manage.py check

echo
echo "DONE. Now open the PythonAnywhere Web tab and click the green Reload button."
echo "Then hard-refresh https://bhupraj.pythonanywhere.com/ (Ctrl+Shift+R)."
echo
echo "Quick verify — this should print action=\"/\" (not #register):"
rg -n 'action=' templates/club/includes/_register.html || grep -n 'action=' templates/club/includes/_register.html
