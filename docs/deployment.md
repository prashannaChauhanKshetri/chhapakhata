# Deployment at the shop

The shop computer runs four containers: PostgreSQL, the Django API, a background worker (nightly backups) and Caddy (HTTPS and the web app). Staff devices on the shop network open `https://chhapakhata.local` (or the computer's IP).

## 1. Prepare the computer

| Item | Recommendation |
|---|---|
| Hardware | 4+ CPU cores, 8 GB RAM, SSD, **UPS** |
| OS | Windows 10/11 Pro with Docker Desktop (WSL 2), or Ubuntu 24.04 with Docker Engine |
| Network | Reserve a fixed IP for the computer in the router (DHCP reservation), e.g. `192.168.1.10` |
| Name | Optional: add `chhapakhata.local` to the router's DNS, or use the IP address |
| Second disk / USB | For local backup copies (`BACKUP_HOST_DIR`) |

**Windows:** in Docker Desktop settings turn on *Start Docker Desktop when you sign in*, and set Windows to sign in automatically to the shop account, so the system comes back by itself after a power cut. A small dedicated Linux mini PC avoids this step.

## 2. Install

```bash
git clone <repository> chhapakhata && cd chhapakhata/deploy
./scripts/install.sh              # Windows: powershell -ExecutionPolicy Bypass -File scripts\install.ps1
# First run creates deploy/.env with fresh secrets. Edit SITE_ADDRESS, ALLOWED_HOSTS
# and CSRF_TRUSTED_ORIGINS for the shop's name/IP, then run the script again.
docker compose run --rm api python manage.py create_owner --username anil --first-name Anil --last-name Pokhrel
```

Then sign in as the owner and complete **Settings → Shop** (name, PAN/VAT, VAT registration, logo, stamp, signature), **Rate card**, and **Users** (front desk and operators).

## 3. Load the shop's data

Fill the templates in `docs/templates/` (CSV, or Excel with the same columns) and import:

```bash
docker compose run --rm -v "$PWD/../docs/templates:/import" api \
  python manage.py import_opening_stock /import/opening_stock.csv --owner anil
docker compose run --rm -v "$PWD/../docs/templates:/import" api \
  python manage.py import_rate_card /import/rate_card.csv
docker compose run --rm -v "$PWD/../docs/templates:/import" api \
  python manage.py import_customers /import/customers.csv --owner anil --as-of 2026-11-09
```

Add `--dry-run` first to check a file. A file with any bad row saves nothing and lists every problem.

## 4. Trust the certificate on each device

Caddy issues the HTTPS certificate from its own local authority. Copy its root certificate once and install it on each staff device:

```bash
docker compose cp web:/data/caddy/pki/authorities/local/root.crt ./chhapakhata-root.crt
```

- Windows: double-click → Install Certificate → Local Machine → *Trusted Root Certification Authorities*.
- Android: Settings → Security → Encryption & credentials → Install a certificate → CA certificate.
- iPhone: AirDrop/email the file, install the profile, then Settings → General → About → Certificate Trust Settings → enable.

If this is not possible, use the plain-HTTP fallback (`CADDYFILE=Caddyfile.http`, `SECURE_COOKIES=false`, origins with `http://`) on a WPA2-protected network only. Over plain HTTP, phones cannot install the app or open it offline; everything else works.

### Install the app on phones and tablets

With the certificate trusted, open `https://<SITE_ADDRESS>` on the device and sign in:

- **Android / Chrome / Edge:** account menu → **Install app on this device**.
- **iPhone / iPad:** Safari → Share → **Add to Home Screen**.

The installed app opens full screen from its icon. It keeps working when the Wi-Fi drops or the shop computer is off: it opens, and shows the orders, jobs and balances last loaded (kept on the device for 24 hours and removed on sign-out), with a banner saying so. Changes can only be saved while the shop computer answers, because order, invoice and receipt numbers and stock are allocated there. After an update, staff see **New version ready → Reload now**.

## 5. Printers

- **A4 / A5:** install the printer driver on each counter PC; PDFs open in a new tab, print with *Actual size*.
- **3-inch thermal:** install the vendor's Windows driver with an 80 mm paper size; receipts are generated at 80 mm wide and cut to length. In the print dialog choose the thermal printer, margins *None*, scale *100 %*.

## 6. Online backup copy

See [backup-restore.md](backup-restore.md) to configure the encrypted rclone remote.

## 7. Updates

```bash
cd deploy && ./scripts/update.sh    # backs up, pulls, rebuilds, restarts
```

## Operations checklist

- [ ] Dashboard shows no backup warning the morning after installation
- [ ] Online copy status reads "Copied online"
- [ ] Restore drill done once (see backup-restore.md) and noted
- [ ] All demo passwords changed or demo data never loaded
- [ ] Root certificate installed on every staff device
- [ ] Thermal and A4 test prints from each counter PC
