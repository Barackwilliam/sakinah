#!/usr/bin/env bash
# Render build step: install packages, collect static files, update the database.
set -o errexit
pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py ensure_admin
# Starter content (categories, plans, articles, events, templates). Safe to run every deploy: it only fills what is missing.
if [ "${SEED_ON_DEPLOY:-True}" = "True" ]; then python manage.py seed; fi
