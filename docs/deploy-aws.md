# Putting ChhapaKhata online on AWS EC2

This runs the same Docker stack as the shop computer (PostgreSQL, the Django API with gunicorn, the background worker for backups, and Caddy serving the app over HTTPS) on one EC2 server. Use it for the online demo or for a shop that prefers a cloud server. Allow about an hour the first time.

The stack was built and tested on 28 October 2026: all containers start, PDFs and backups work inside them, a restore drill restored every row, and the browser test suite passes against it.

## 0. Before you start

**A domain name** is needed for a trusted HTTPS certificate (and phones only install the app over trusted HTTPS). Either:

- a domain you own, with an **A record** such as `demo.yourdomain.com` → your server's Elastic IP; or
- free, no setup: `<ip-with-dashes>.sslip.io`, which always points at that IP. For the IP `13.233.1.2` the name is `13-233-1-2.sslip.io`.

**If the domain's DNS is on Cloudflare:** set the A records to **DNS only** (grey cloud), not Proxied (orange). Caddy gets the certificate directly from Let's Encrypt and serves HTTPS itself; through the proxy the certificate check fails, and Cloudflare's default "Flexible" SSL mode causes an endless redirect. (The proxy can be turned on later with SSL/TLS mode **Full (strict)**, once HTTPS works.)

To serve both the bare domain and `www`, list both everywhere an address is asked for, separated by commas (see step 4).

**Costs** (approximate; check the EC2 pricing page for your region): a t3.small, a 30 GB disk and a public IP come to roughly USD 20–25 a month, all drawn from your AWS credit. In the AWS console, open **Billing → Budgets** and create a monthly budget of USD 10 with an email alert, so nothing surprises you.

## 1. Launch the server

EC2 console → **Launch instance**:

| Setting | Value |
|---|---|
| Region (top right) | **Asia Pacific (Mumbai) ap-south-1**, closest to Nepal |
| Name | `chhapakhata` |
| Image | **Ubuntu Server 24.04 LTS**, 64-bit (x86) |
| Instance type | **t3.small** (2 vCPU, 2 GB). t3.micro (1 GB) is too small. |
| Key pair | **Create new key pair** → name `chhapakhata`, type ED25519, format **.pem** → it downloads once. Keep it safe; never put it in the project folder or GitHub. |
| Network settings → Edit | Create a security group with three inbound rules: **SSH (22) from My IP**, **HTTP (80) from Anywhere**, **HTTPS (443) from Anywhere**. Nothing else (never open 5432 or 8000). |
| Storage | **30 GiB gp3** |
| Advanced details → Credit specification | Leave the default, **Unlimited**. A new t3 in Standard mode starts with no CPU credits and would crawl at 20 % speed through the first build; Unlimited costs only cents extra for occasional heavy work, and the budget alert catches anything unusual. |

Launch, then **Elastic IPs → Allocate** and **Associate** it with the instance, so the address survives restarts. Point your domain at that IP (or note the sslip.io name).

## 2. Connect

On your Mac:

```bash
mv ~/Downloads/chhapakhata.pem ~/.ssh/
chmod 400 ~/.ssh/chhapakhata.pem
ssh -i ~/.ssh/chhapakhata.pem ubuntu@<ELASTIC-IP>
```

Everything below runs on the server.

## 3. Let the server read the (private) repository

Give the server its own **read-only deploy key**, so no personal GitHub password or token lives on it:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N "" -C "chhapakhata-ec2"
cat ~/.ssh/github_deploy.pub
printf 'Host github.com\n  IdentityFile ~/.ssh/github_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config
```

Copy the printed key. On GitHub: repository → **Settings → Deploy keys → Add deploy key**, paste it, leave **Allow write access unticked**, save. Then:

```bash
git clone git@github.com:prashannaChauhanKshetri/chhapakhata.git
sudo chhapakhata/deploy/scripts/aws-bootstrap.sh     # swap, Docker, git
exit                                                 # log out so the docker group applies
```

Connect again with the same `ssh` command.

## 4. Configure and start

```bash
cd ~/chhapakhata/deploy
./scripts/install.sh        # first run: creates .env with fresh secrets, then stops
nano .env
```

Set these lines (keep the generated `SECRET_KEY` and `POSTGRES_PASSWORD`):

```ini
SITE_ADDRESS=demo.yourdomain.com
ALLOWED_HOSTS=demo.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://demo.yourdomain.com
# Both the bare domain and www, for example:
#   SITE_ADDRESS=chhapakhata.tech, www.chhapakhata.tech
#   ALLOWED_HOSTS=chhapakhata.tech,www.chhapakhata.tech
#   CSRF_TRUSTED_ORIGINS=https://chhapakhata.tech,https://www.chhapakhata.tech
CADDYFILE=Caddyfile.public
ACME_EMAIL=you@example.com
SECURE_COOKIES=true
GUNICORN_WORKERS=2
```

Save (Ctrl+O, Enter, Ctrl+X) and start:

```bash
./scripts/install.sh        # second run: builds (about 10 minutes on a t3.small) and starts
docker compose ps           # db, api, worker and web should be "Up", api "healthy"
```

Open `https://demo.yourdomain.com`. The first visit may take a few seconds while Caddy fetches the certificate.

## 5. Accounts and data

Choose **one** of these. Each creates the accounts, so use them on an empty database only.

**A. A real shop:** create the owner (you are asked for the password), then add staff in Settings → Users.

```bash
docker compose run --rm api python manage.py create_owner --username anil --first-name Anil --last-name Pokhrel
```

**B. The demo, with three weeks of sample orders:** owner / frontdesk / operator. **Always give your own strong password.** The default demo password is published in the README, and anyone could use it on a public server.

```bash
docker compose exec api python manage.py seed_demo --password 'choose-a-long-password'
```

**C. Six years of history** (12,000 orders; takes about 40 minutes): sign in as newowner, sunita, anjali, kamal or suresh.

```bash
docker compose exec api python manage.py seed_history --password 'choose-a-long-password'
```

## 6. Phones

Open the site on the phone and sign in. Android/Chrome: account menu → **Install app on this device**. iPhone: Safari → Share → **Add to Home Screen**. No certificate needs installing, because Let's Encrypt is trusted everywhere.

## 7. Backups

The nightly backup (21:00, with 14 daily, 8 weekly and 12 monthly copies kept) is written to `~/chhapakhata/deploy/backups`, on the **same disk** as the server. Add at least one copy off it:

- **Disk snapshots (simplest):** EC2 → **Lifecycle Manager** → create a policy for the instance's volume: daily, keep 7. A lost server can be rebuilt from a snapshot.
- **Encrypted online copy:** set up the rclone remote described in [backup-restore.md](backup-restore.md) (Google Drive or S3).

A manual backup any time: `./scripts/backup-now.sh`. A restore: `./scripts/restore.sh backups/sets/<file>.dump` (asks you to type RESTORE).

## 8. Updates

After new code is pushed to GitHub:

```bash
cd ~/chhapakhata/deploy && ./scripts/update.sh    # backs up, pulls, rebuilds, restarts
```

## 9. Looking after it

| Task | Command |
|---|---|
| Status | `docker compose ps` |
| Live logs | `docker compose logs -f api` (or `worker`, `web`) |
| Restart everything | `docker compose restart` |
| Memory and disk | `free -h` · `df -h` |

Security checklist: SSH open only to your IP (update the rule if your IP changes); the `.pem` file and `deploy/.env` never shared; demo passwords changed; Ubuntu installs security updates automatically (`unattended-upgrades` is on by default); the budget alert set.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Browser shows a certificate error or Caddy logs "challenge failed" | The domain does not point at the Elastic IP yet, or port 80 is closed in the security group. Fix, then `docker compose restart web`. |
| "Bad Request (400)" | `ALLOWED_HOSTS` in `.env` does not match the address you opened. |
| Sign-in fails with a CSRF error | `CSRF_TRUSTED_ORIGINS` must be `https://` plus the exact address. |
| Build stops with "Killed" | Out of memory: check the swap is on (`swapon --show`); rerun `aws-bootstrap.sh`. |
| Site down after a reboot | `docker compose ps`; containers restart on their own (`restart: unless-stopped`). If not, `docker compose up -d`. |
