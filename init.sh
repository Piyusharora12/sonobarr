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

CURRENT_UID="$(id -u)"
CURRENT_GID="$(id -g)"

PUID=${PUID:-}
PGID=${PGID:-}
APP_DIR=/sonobarr
SRC_DIR="${APP_DIR}/src"
CONFIG_DIR="${APP_DIR}/config"
CONFIG_MIGRATIONS_DIR="${CONFIG_DIR}/migrations"
MIGRATIONS_DIR=${MIGRATIONS_DIR:-${APP_DIR}/migrations}
WRITABLE_PATHS="${CONFIG_DIR}"

export PYTHONPATH=${PYTHONPATH:-${SRC_DIR}}
export FLASK_APP=${FLASK_APP:-src.Sonobarr}
export FLASK_ENV=${FLASK_ENV:-production}
export FLASK_RUN_FROM_CLI=${FLASK_RUN_FROM_CLI:-true}

# If we're not running as root, make sure UID/GID align with the current user
if [ "${CURRENT_UID}" -eq 0 ]; then
  PUID=${PUID:-1000}
  PGID=${PGID:-1000}
else
  PUID=${PUID:-${CURRENT_UID}}
  PGID=${PGID:-${CURRENT_GID}}
fi

echo "-----------------"
echo -e "\033[1mRunning with:\033[0m"
echo "PUID=${PUID}"
echo "PGID=${PGID}"
echo "-----------------"

# Create the required directories with the correct permissions
echo "Setting up directories.."
mkdir -p "${CONFIG_DIR}"

if [ "${CURRENT_UID}" -eq 0 ]; then
  for path in ${WRITABLE_PATHS}; do
    chown -R ${PUID}:${PGID} "${path}"
  done
fi

if [ -d "${CONFIG_MIGRATIONS_DIR}" ]; then
  echo "Removing legacy migrations directory at ${CONFIG_MIGRATIONS_DIR}..."
  rm -rf "${CONFIG_MIGRATIONS_DIR}"
fi

if [ ! -d "${MIGRATIONS_DIR}" ]; then
  echo "Error: bundled migrations directory ${MIGRATIONS_DIR} is missing." >&2
  exit 1
fi

if [ "${CURRENT_UID}" -eq 0 ]; then
  RUNNER="su-exec ${PUID}:${PGID}"
else
  if [ "${PUID}" != "${CURRENT_UID}" ] || [ "${PGID}" != "${CURRENT_GID}" ]; then
    echo "Warning: running as UID ${CURRENT_UID} but PUID=${PUID}; ignoring PUID/PGID overrides because process is not root." >&2
  fi
  RUNNER=""
fi

echo "Applying database migrations..."
if [ -n "${RUNNER}" ]; then
  SONOBARR_SKIP_PROFILE_BACKFILL=1 ${RUNNER} flask db upgrade --directory "${MIGRATIONS_DIR}"
else
  SONOBARR_SKIP_PROFILE_BACKFILL=1 flask db upgrade --directory "${MIGRATIONS_DIR}"
fi

echo "Starting app..."
if [ -n "${RUNNER}" ]; then
  exec ${RUNNER} gunicorn src.Sonobarr:app -c gunicorn_config.py
else
  exec gunicorn src.Sonobarr:app -c gunicorn_config.py
fi
