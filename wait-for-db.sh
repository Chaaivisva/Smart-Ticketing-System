#!/bin/sh
# wait-for-db.sh

set -e

# The first argument to the script is the database host
host="$1"
shift
# The rest of the arguments are the command to execute after the database is ready
cmd="$@"

# Use a loop to keep trying to connect to the database
until PGPASSWORD="$PGPASSWORD" psql -h "$host" -U "$PGUSER" -d "$PGDATABASE" -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing command"
exec $cmd
