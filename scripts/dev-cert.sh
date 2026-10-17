#!/usr/bin/env bash
# HTTPS certificate for the development server on the local network.
#
# Phones only install the app and keep it working offline over HTTPS. This
# creates a small private certificate authority (once) and a certificate for
# this computer's current Wi-Fi address, all inside .certs/ (git-ignored).
# Install .certs/chhapakhata-dev-ca.crt once on each phone (`make lan-ca`).
#
# Usage: scripts/dev-cert.sh <lan-ip>
set -euo pipefail

IP="${1:?Usage: scripts/dev-cert.sh <lan-ip>}"
DIR="$(cd "$(dirname "$0")/.." && pwd)/.certs"
mkdir -p "$DIR"
chmod 700 "$DIR"
cd "$DIR"

if [[ ! -f ca.key ]]; then
  echo "Creating the private certificate authority (once)…"
  openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 3650 \
    -keyout ca.key -out chhapakhata-dev-ca.crt \
    -subj "/O=ChhapaKhata development/CN=ChhapaKhata Dev CA" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" 2>/dev/null
  chmod 600 ca.key
fi

NAME="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"
cat > dev.ext <<EXT
basicConstraints=CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:localhost,DNS:${NAME}.local,IP:127.0.0.1,IP:${IP}
EXT

# Phones reject certificates valid for more than 825 days; 397 is safe everywhere.
openssl req -newkey rsa:2048 -nodes -keyout dev-key.pem -out dev.csr \
  -subj "/O=ChhapaKhata development/CN=${IP}" 2>/dev/null
openssl x509 -req -in dev.csr -CA chhapakhata-dev-ca.crt -CAkey ca.key -CAcreateserial \
  -out dev.pem -days 397 -sha256 -extfile dev.ext 2>/dev/null
chmod 600 dev-key.pem
rm -f dev.csr dev.ext
echo "$IP" > dev.ip
echo "Certificate ready for https://${IP}:5173 and https://localhost:5173"
