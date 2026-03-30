#!/bin/bash

set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$APP_DIR/venv"

echo "==> Installing proc tools..."

# Create venv
if [ ! -d "$VENV_DIR" ]; then
    echo "==> Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Upgrade pip
pip install --upgrade pip

# Install requirements
if [ -f "$APP_DIR/requirements.txt" ]; then
    pip install -r "$APP_DIR/requirements.txt"
else
    pip install textual psutil pyperclip
fi

deactivate

# Create procMon command
echo "==> Installing procMon..."
sudo tee /usr/local/bin/procMon > /dev/null <<EOF
#!/bin/bash
exec sudo "$VENV_DIR/bin/python" "$APP_DIR/procMon.py"
EOF

# Create procUsage command
echo "==> Installing procUsage..."
sudo tee /usr/local/bin/procUsage > /dev/null <<EOF
#!/bin/bash
exec sudo "$VENV_DIR/bin/python" "$APP_DIR/procUsage.py"
EOF

# Make executable
sudo chmod +x /usr/local/bin/procMon
sudo chmod +x /usr/local/bin/procUsage

echo ""
echo "[+] Done!"
echo "Run:"
echo "  procMon"
echo "  procUsage"
