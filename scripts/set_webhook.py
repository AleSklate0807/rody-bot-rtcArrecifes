"""
Registra el webhook del bot en Telegram.

Uso:
    python scripts/set_webhook.py https://tu-proyecto.vercel.app
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import settings  # noqa: E402
from app.services.telegram import set_webhook  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Uso: python scripts/set_webhook.py https://tu-proyecto.vercel.app")
    url = sys.argv[1].rstrip("/") + "/api/webhook"
    ok = asyncio.run(set_webhook(url, settings.TELEGRAM_WEBHOOK_SECRET))
    print(f"✅ Webhook registrado en {url}" if ok else "❌ No se pudo registrar el webhook")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
