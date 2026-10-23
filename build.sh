#!/usr/bin/env bash
# Render build step: install packages, collect static files, update the database.
set -o errexit

# --- the steps the site cannot run without: a failure here stops the deploy, and Render keeps serving the old build
pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py ensure_admin

# --- starter content and housekeeping
# These only add what is missing, so a failure must never stop the deploy: migrate has already changed the database,
# and aborting here would leave the old code serving a newer database - every page that touches a new column then 500s.
optional() {
  echo "--> $*"
  if ! "$@"; then
    echo "WARNING: '$*' failed. The deploy continues, because the site works without it." >&2
    echo "         Fix it when you can, then deploy again." >&2
  fi
}

# Starter content (categories, plans, articles, events, templates). Safe to run every deploy: it only fills what is missing.
if [ "${SEED_ON_DEPLOY:-True}" = "True" ]; then optional python manage.py seed; fi
# Render's disk is wiped on each deploy; put back starter images the database still points to (no-op with Supabase Storage).
optional python manage.py restore_media
# Stamp the watermark on pictures stored before it was switched on (only needed once, with Supabase Storage). Skips pictures already stamped.
if [ "${WATERMARK_EXISTING:-False}" = "True" ]; then optional python manage.py watermark_images; fi
