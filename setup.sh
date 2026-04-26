#!/bin/bash

echo "🔳 ZL1RFF COCKPIT INSTALLER FOR ASL3"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Install System Dependencies
echo "📦 Installing system dependencies..."
sudo apt update
sudo apt install -y python3-pip python3-venv git asterisk

# 2. Setup Virtual Environment
echo "🐍 Setting up Python Virtual Environment..."
python3 -m venv venv
source venv/bin/activate
./venv/bin/pip install python-telegram-bot requests

# 3. Gather User Input
read -p "Enter your AllStarLink Node Number: " node_num
read -p "Enter your Telegram Bot Token: " tg_token

# 4. Create config.json
echo "⚙️ Creating configuration file..."
cat <<EOF > config.json
{
    "node_number": "$node_num",
    "bot_token": "$tg_token"
}
EOF

# 5. Create the Systemd Service
echo "🛠️ Configuring System Startup Service..."
WORKING_DIR=$(pwd)
cat <<EOF | sudo tee /etc/systemd/system/tgbot.service
[Unit]
Description=Telegram ASL3 Cockpit Bot
After=network.target asterisk.service

[Service]
ExecStart=$WORKING_DIR/venv/bin/python3 $WORKING_DIR/bot04.py
WorkingDirectory=$WORKING_DIR
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
EOF

# 6. Finalize
sudo systemctl daemon-reload
sudo systemctl enable tgbot.service
sudo systemctl restart tgbot.service

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ INSTALLATION COMPLETE!"
echo "Your bot is now running in the background."
