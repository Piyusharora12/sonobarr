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

if [ -d "${MIGRATIONS_DIR}" ] && [ -f "${MIGRATIONS_DIR}/env.py" ]; then
   echo "Applying database migrations..."
   su-exec ${PUID}:${PGID} flask db upgrade --directory "${MIGRATIONS_DIR}"
elif [ ! -d "${MIGRATIONS_DIR}" ]; then
   echo "Initializing migrations directory at ${MIGRATIONS_DIR}..."
   su-exec ${PUID}:${PGID} flask db init --directory "${MIGRATIONS_DIR}"
   echo "Applying database migrations..."
   su-exec ${PUID}:${PGID} flask db upgrade --directory "${MIGRATIONS_DIR}"
else
   echo "Migrations directory present but missing env.py, skipping automatic upgrade."
fi

# Start the application with the specified user permissions
echo "Running Sonobarr..."
exec su-exec ${PUID}:${PGID} gunicorn src.Sonobarr:app -c gunicorn_config.py
