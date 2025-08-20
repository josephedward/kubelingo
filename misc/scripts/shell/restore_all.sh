#!/usr/bin/env bash
# Kubelingo Full Restore Script
# This restores your primary DB from backup, copies all YAML quizzes, and imports all quizzes into the database.
set -euo pipefail

echo "\n=== Kubelingo Full Restore ==="

# 1) Restore primary database
DB_BACKUP="$(pwd)/question-data-backup/kubelingo_original.db"
LIVE_DB="$HOME/.kubelingo/kubelingo.db"
echo "Restoring primary DB from $DB_BACKUP to $LIVE_DB..."
mkdir -p "$(dirname "$LIVE_DB")"
if [ -f "$DB_BACKUP" ]; then
    cp -f "$DB_BACKUP" "$LIVE_DB" || echo "Warning: failed to copy DB backup."
else
    echo "Warning: backup DB not found at $DB_BACKUP"
fi

# 2) Copy all YAML quizzes into active quiz directory
YAML_DST="$(pwd)/question-data/yaml"
echo "Copying YAML quizzes to $YAML_DST..."
mkdir -p "$YAML_DST"
cp -n question-data/yaml-bak/*.yaml "$YAML_DST" 2>/dev/null || true
cp -n question-data/manifests/*.yaml "$YAML_DST" 2>/dev/null || true

# 3) Migrate YAML quizzes into DB
echo "Migrating YAML quizzes into database..."
kubelingo migrate-yaml || true

# 4) Import JSON quizzes into DB
echo "Importing JSON quizzes into database..."
kubelingo import-json || true

echo "=== Full Restore Complete ===\n"