#!/usr/bin/env bash
# setup_hotspot.sh — Install and configure on-demand WiFi hotspot for BikeBox.
#
# Installs hostapd (access point) and dnsmasq (DHCP) and writes their config
# files, but does NOT enable them at boot. The hotspot is activated/deactivated
# at runtime by hotspot.py when the iOS app requests clip downloads.
#
# The Pi stays on home WiFi normally. SSH via bikebox.local always works.
#
# Run once:
#   chmod +x setup_hotspot.sh
#   sudo ./setup_hotspot.sh

set -euo pipefail

SSID="BikeBox"
PASSPHRASE="bikebox123"
PI_IP="192.168.4.1"
DHCP_START="192.168.4.2"
DHCP_END="192.168.4.20"
CHANNEL=6

echo "=== BikeBox On-Demand Hotspot Setup ==="
echo ""

# ── 1. Install dependencies ──
echo "[1/7] Installing hostapd, dnsmasq, ffmpeg..."
apt update -qq
apt install -y hostapd dnsmasq ffmpeg

# Stop and DISABLE services — they will be started on-demand by hotspot.py
systemctl stop hostapd 2>/dev/null || true
systemctl stop dnsmasq 2>/dev/null || true
systemctl disable hostapd 2>/dev/null || true
systemctl disable dnsmasq 2>/dev/null || true
systemctl unmask hostapd 2>/dev/null || true

echo "  hostapd and dnsmasq installed but DISABLED at boot"

# ── 2. Undo any previous always-on hotspot configuration ──
echo "[2/7] Reverting any previous always-on hotspot config..."

# Remove NetworkManager unmanage override (if it exists from previous setup)
if [ -f /etc/NetworkManager/conf.d/bikebox-unmanage-wlan0.conf ]; then
    rm -f /etc/NetworkManager/conf.d/bikebox-unmanage-wlan0.conf
    echo "  Removed NetworkManager unmanage config"
    systemctl reload NetworkManager 2>/dev/null || systemctl restart NetworkManager 2>/dev/null || true
fi

# Remove systemd-networkd static IP (if it exists from previous setup)
if [ -f /etc/systemd/network/10-bikebox-wlan0.network ]; then
    rm -f /etc/systemd/network/10-bikebox-wlan0.network
    systemctl restart systemd-networkd 2>/dev/null || true
    echo "  Removed systemd-networkd static IP config"
fi

# Remove any static IP lines we added to dhcpcd.conf
if [ -f /etc/dhcpcd.conf ]; then
    if grep -q "# BikeBox WiFi hotspot" /etc/dhcpcd.conf 2>/dev/null; then
        sed -i '/# BikeBox WiFi hotspot/,/nohook wpa_supplicant/d' /etc/dhcpcd.conf
        echo "  Removed static IP from /etc/dhcpcd.conf"
    fi
fi

# Remove the failsafe service (if it exists from previous troubleshooting)
if systemctl is-enabled bikebox-failsafe.service 2>/dev/null; then
    systemctl stop bikebox-failsafe.service 2>/dev/null || true
    systemctl disable bikebox-failsafe.service 2>/dev/null || true
    rm -f /etc/systemd/system/bikebox-failsafe.service
    systemctl daemon-reload 2>/dev/null || true
    echo "  Removed bikebox-failsafe service"
fi
if [ -f /home/pi/bikebox/hotspot_failsafe.sh ]; then
    rm -f /home/pi/bikebox/hotspot_failsafe.sh
    echo "  Removed hotspot_failsafe.sh"
fi

echo "  Previous configuration cleaned up"

# ── 3. hostapd configuration ──
echo "[3/7] Writing hostapd config..."

cat > /etc/hostapd/hostapd.conf <<EOF
interface=wlan0
driver=nl80211
ssid=${SSID}
hw_mode=g
channel=${CHANNEL}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=${PASSPHRASE}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

sed -i 's|^#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd 2>/dev/null || true
echo "  Written /etc/hostapd/hostapd.conf (SSID=$SSID, channel=$CHANNEL)"

# ── 4. dnsmasq configuration ──
echo "[4/7] Writing dnsmasq config..."

if [ -f /etc/dnsmasq.conf ] && [ ! -f /etc/dnsmasq.conf.orig ]; then
    cp /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
fi

cat > /etc/dnsmasq.d/bikebox.conf <<EOF
# BikeBox WiFi hotspot DHCP (on-demand only)
interface=wlan0
dhcp-range=${DHCP_START},${DHCP_END},255.255.255.0,24h
EOF

echo "  Written /etc/dnsmasq.d/bikebox.conf"

# ── 5. Sudoers for on-demand hotspot ──
echo "[5/7] Configuring passwordless sudo for hotspot commands..."

cat > /etc/sudoers.d/bikebox-hotspot <<'EOF'
# Allow user pi to start/stop hotspot services and configure wlan0 without a password.
# Required because bikebox.service runs as User=pi.
pi ALL=(ALL) NOPASSWD: /usr/bin/systemctl start hostapd
pi ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop hostapd
pi ALL=(ALL) NOPASSWD: /usr/bin/systemctl start dnsmasq
pi ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop dnsmasq
pi ALL=(ALL) NOPASSWD: /usr/bin/systemctl is-active hostapd
pi ALL=(ALL) NOPASSWD: /usr/bin/systemctl status hostapd *
pi ALL=(ALL) NOPASSWD: /usr/sbin/ip addr *
pi ALL=(ALL) NOPASSWD: /usr/sbin/ip link *
pi ALL=(ALL) NOPASSWD: /usr/bin/nmcli *
pi ALL=(ALL) NOPASSWD: /sbin/wpa_cli *
pi ALL=(ALL) NOPASSWD: /usr/bin/systemctl start wpa_supplicant
pi ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop wpa_supplicant
EOF
chmod 0440 /etc/sudoers.d/bikebox-hotspot
visudo -c -f /etc/sudoers.d/bikebox-hotspot
echo "  Written /etc/sudoers.d/bikebox-hotspot"

# ── 6. Update bikebox.service sandbox for sudo ──
echo "[6/7] Updating bikebox.service sandbox..."

SERVICE_FILE="/etc/systemd/system/bikebox.service"
if [ -f "$SERVICE_FILE" ]; then
    # Replace ProtectSystem=strict with ProtectSystem=full to allow /usr/sbin access for sudo
    sed -i 's/^ProtectSystem=strict/ProtectSystem=full/' "$SERVICE_FILE"
    # Ensure NoNewPrivileges is false (needed for sudo)
    sed -i 's/^NoNewPrivileges=true/NoNewPrivileges=false/' "$SERVICE_FILE"
    systemctl daemon-reload
    echo "  Updated $SERVICE_FILE (ProtectSystem=full, NoNewPrivileges=false)"
else
    echo "  WARNING: $SERVICE_FILE not found — hotspot commands may fail without manual fix"
fi

# ── 7. Create clip directory ──
echo "[7/7] Ensuring clip directory exists..."
mkdir -p /home/pi/bikebox/data/clips
chown -R pi:pi /home/pi/bikebox

echo ""
echo "=== Setup Complete ==="
echo ""
echo "  SSID:       $SSID"
echo "  Password:   $PASSPHRASE"
echo "  Pi IP:      $PI_IP (when hotspot is active)"
echo "  DHCP range: $DHCP_START — $DHCP_END"
echo "  Clip dir:   /home/pi/bikebox/data/clips"
echo ""
echo "  The hotspot is OFF by default."
echo "  It activates on-demand when you tap 'Download Clips' in the iOS app."
echo "  SSH via bikebox.local works normally at all times."
echo ""
echo "  NO REBOOT NEEDED — the Pi stays on home WiFi."
