# Backup and restore

## What is backed up

Every night at `BACKUP_HOUR` (default 21:00) and whenever the owner clicks **Back up now**:

- the whole database (`pg_dump` custom format) → `chhapakhata-db-YYYYMMDD-HHMMSS.dump`
- uploaded images (logo, stamp, signature) → `chhapakhata-media-YYYYMMDD-HHMMSS.tar.gz`
- a SHA-256 checksum → `chhapakhata-db-YYYYMMDD-HHMMSS.sha256`

Files go to `BACKUP_HOST_DIR/sets` on the shop computer. Retention keeps the last **14 daily**, one per week for **8 weeks**, and one per month for **12 months**. Each run is listed in **Settings → Backups**; the dashboard warns if the last good backup is more than 26 hours old.

## Online copy (encrypted)

After each backup the worker runs `rclone copy` to `RCLONE_REMOTE`. `copy` never deletes online files, so a damaged local disk can't wipe the online copy. If there is no internet, the status shows "Waiting for internet" and the next backup uploads everything missing.

Set up once (Google Drive's free 15 GB is plenty for years):

```bash
cd deploy
docker run --rm -it -v "$PWD/rclone:/config/rclone" rclone/rclone config
#   1. new remote "gdrive"  → type drive → follow the browser sign-in
#   2. new remote "shopbackup" → type crypt → remote "gdrive:chhapakhata"
#      → choose a strong password AND salt; write both on paper and keep them safe
```

Then in `deploy/.env`: `RCLONE_REMOTE=shopbackup:` and restart (`docker compose up -d`). **Without the crypt password the online copy cannot be read, by anyone, including you.**

## Restore

Restoring **replaces all current data**. Stop and think: is the current data really lost?

```bash
cd deploy
./scripts/restore.sh backups/sets/chhapakhata-db-20261109-210000.dump
# Windows: powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 backups\sets\chhapakhata-db-20261109-210000.dump
```

The script verifies the checksum, asks you to type `RESTORE`, stops the app, recreates the database, restores it, restores images, and starts the app again.

To restore from the online copy first download the files:

```bash
docker run --rm -v "$PWD/rclone:/config/rclone" -v "$PWD/backups:/data" rclone/rclone \
  copy shopbackup:sets/ /data/sets/ --include "chhapakhata-*20261109*"
```

## Restore drill (do this at installation and every 3 months)

1. Take a backup now.
2. On a spare machine (or a scratch database), restore it.
3. Compare: number of orders, invoices, payments, and one customer's balance.
4. Note the date and result in the shop's maintenance notebook.

During development the drill was run against the demo data: orders, invoices, payments, ledger entries and stock movements matched exactly.

## Data export

**Settings → Backups → Download Excel export** gives every table (customers, orders, items, invoices, payments, ledger, stock, activity) as one workbook: the client's data in a form they can open anywhere.
