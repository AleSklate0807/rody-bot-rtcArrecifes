import os
import sys

# Variables falsas para que Settings() no falle y no se usen credenciales reales.
os.environ.update(
    TELEGRAM_BOT_TOKEN="test-token",
    TELEGRAM_WEBHOOK_SECRET="test-secret",
    SUPABASE_URL="https://example.supabase.co",
    SUPABASE_SERVICE_KEY="test-key",
    GEMINI_API_KEY="test-key",
    ADMIN_TELEGRAM_IDS="111",
)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
