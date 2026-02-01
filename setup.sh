#!/bin/bash
# Setup script for Freelance Job Alerts Bot

echo "🚀 Setting up Freelance Job Alerts Bot..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python3 -c "from bot import init_db; init_db(); print('✅ Database initialized')"

echo ""
echo "📋 NEXT STEPS:"
echo "1. Create Telegram bot: @BotFather on Telegram"
echo "2. Get your bot token and set it:"
echo "   export TELEGRAM_BOT_TOKEN='your_token_here'"
echo "3. Start the bot:"
echo "   python3 bot.py"
echo ""
echo "4. Setup cron job for alerts (runs every hour):"
echo "   crontab -e"
echo "   Add: 0 * * * * cd /path/to/freelance-bot && /path/to/venv/bin/python3 cron_worker.py"
echo ""
echo "✅ Setup complete!"
