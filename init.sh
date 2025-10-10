#!/bin/sh
set -e

echo -e "\033[1;34mSonobarr\033[0m"
echo "Initializing app..."

cat << 'EOF'
         ██          _______.  ______   .__   __.   ______   .______        ___      .______       .______
         ██         /       | /  __  \  |  \ |  |  /  __  \  |   _  \      /   \     |   _  \      |   _  \ 
      ██ ██ ▄▄     |   (----`|  |  |  | |   \|  | |  |  |  | |  |_)  |    /  ^  \    |  |_)  |     |  |_)  |
   ██ ██ ██ ██      \   \    |  |  |  | |  . `  | |  |  |  | |   _  <    /  /_\  \   |      /      |      /
██ ██ ██ ██ ██  .----)   |   |  `--'  | |  |\   | |  `--'  | |  |_)  |  /  _____  \  |  |\  \----. |  |\  \----.
██ ██ ██ ██ ██  |_______/     \______/  |__| \__|  \______/  |______/  /__/     \__\ | _| `._____| | _| `._____|
EOF

PUID=${PUID:-1000}
PGID=${PGID:-1000}
APP_DIR=/sonobarr
SRC_DIR="${APP_DIR}/src"
CONFIG_DIR="${APP_DIR}/config"
CONFIG_MIGRATIONS_DIR="${CONFIG_DIR}/migrations"
MIGRATIONS_DIR=${MIGRATIONS_DIR:-${APP_DIR}/migrations}

export PYTHONPATH=${PYTHONPATH:-${SRC_DIR}}
export FLASK_APP=${FLASK_APP:-src.Sonobarr}
export FLASK_ENV=${FLASK_ENV:-production}
export FLASK_RUN_FROM_CLI=${FLASK_RUN_FROM_CLI:-true}

echo "-----------------"
echo -e "\033[1mRunning with:\033[0m"
echo "PUID=${PUID}"
echo "PGID=${PGID}"
echo "-----------------"

# Create the required directories with the correct permissions
echo "Setting up directories.."
mkdir -p "${CONFIG_DIR}"
chown -R ${PUID}:${PGID} "${APP_DIR}"

if [ -d "${CONFIG_MIGRATIONS_DIR}" ]; then
  echo "Removing legacy migrations directory at ${CONFIG_MIGRATIONS_DIR}..."
  rm -rf "${CONFIG_MIGRATIONS_DIR}"
fi

if [ ! -d "${MIGRATIONS_DIR}" ]; then
  echo "Error: bundled migrations directory ${MIGRATIONS_DIR} is missing." >&2
  exit 1
fi

echo "Applying database migrations..."
SONOBARR_SKIP_PROFILE_BACKFILL=1 su-exec ${PUID}:${PGID} flask db upgrade --directory "${MIGRATIONS_DIR}"

echo "Starting app..."
exec su-exec ${PUID}:${PGID} gunicorn src.Sonobarr:app -c gunicorn_config.py
