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
MIGRATIONS_DIR=${MIGRATIONS_DIR:-${CONFIG_DIR}/migrations}
BUNDLED_VERSIONS_DIR="${APP_DIR}/migrations/versions"
SENTINEL="${MIGRATIONS_DIR}/.managed-by-sonobarr-0.7"

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

init_scaffold() {
  # Generate a clean Alembic scaffold (env.py, alembic.ini, script template)
  su-exec ${PUID}:${PGID} flask db init --directory "${MIGRATIONS_DIR}"
  touch "${SENTINEL}"
}

echo "Preparing migrations scaffold..."
if [ -d "${MIGRATIONS_DIR}" ]; then
  if [ ! -f "${SENTINEL}" ]; then
    echo "Resetting legacy scaffold at ${MIGRATIONS_DIR}..."
    rm -rf "${MIGRATIONS_DIR}"
    mkdir -p "${MIGRATIONS_DIR}"
    init_scaffold()
  fi
else
  mkdir -p "${MIGRATIONS_DIR}"
  init_scaffold()
fi

mkdir -p "${MIGRATIONS_DIR}/versions"

if [ -d "${BUNDLED_VERSIONS_DIR}" ]; then
  echo "Syncing shipped version scripts..."
  # Remove any stray old versions (we only keep what we ship)
  find "${MIGRATIONS_DIR}/versions" -type f -name "*.py" -delete
  cp -n "${BUNDLED_VERSIONS_DIR}"/*.py "${MIGRATIONS_DIR}/versions/" 2>/dev/null || true
fi

echo "Applying database migrations..."
SONOBARR_SKIP_PROFILE_BACKFILL=1 su-exec ${PUID}:${PGID} flask db upgrade --directory "${MIGRATIONS_DIR}"

echo "Starting app..."
exec su-exec ${PUID}:${PGID} gunicorn src.Sonobarr:app -c [gunicorn_config.py](http://_vscodecontentref_/3)
