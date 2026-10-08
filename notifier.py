"""
Telegram Notification Module for JumiaDrop.
Sends real-time high-profit dropshipping alerts to Telegram.
"""
import logging
from typing import Dict, Any, Optional
import telebot
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.bot = telebot.TeleBot(self.token) if self.token else None

    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id and self.bot)

    def send_deal_alert(self, deal: Dict[str, Any]) -> bool:
        """
        Send a formatted deal alert to the configured Telegram chat.
        """
        if not self.is_configured():
            logger.info("Telegram not configured. Skipping alert.")
            return False

        jumia_title = deal.get("jumia_title", "Jumia Product")
        jiji_title = deal.get("jiji_title", "Jiji Supplier Product")
        jumia_price = deal.get("jumia_price", 0.0)
        jiji_price = deal.get("jiji_price", 0.0)
        net_profit = deal.get("net_profit", 0.0)
        margin_pct = deal.get("margin_pct", 0.0)
        opp_score = deal.get("opportunity_score", 0.0)
        jiji_region = deal.get("jiji_region", "Nairobi")
        jumia_url = deal.get("jumia_url", "")
        jiji_url = deal.get("jiji_url", "")
        image_url = deal.get("jumia_image") or deal.get("jiji_image")

        msg = (
            f"🚀 *HIGH-MARGIN DROPSHIPPING OPPORTUNITY*\n\n"
            f"📦 *Product:* `{jumia_title[:60]}...`\n"
            f"📁 *Category:* {deal.get('category', 'General')}\n\n"
            f"🛒 *Jumia Selling Price:* `KSh {jumia_price:,.0f}`\n"
            f"🏭 *Jiji Wholesale Cost:* `KSh {jiji_price:,.0f}`\n"
            f"📍 *Supplier Location:* {jiji_region}\n\n"
            f"💰 *Estimated Net Profit:* `KSh {net_profit:,.0f}`\n"
            f"📈 *Net Profit Margin:* `{margin_pct:.1f}%`\n"
            f"🎯 *Opportunity Score:* `{opp_score}/100`\n\n"
            f"🔗 [View on Jumia]({jumia_url})\n"
            f"🔗 [Contact Jiji Supplier]({jiji_url})\n"
        )

        try:
            if image_url and image_url.startswith("http"):
                self.bot.send_photo(self.chat_id, image_url, caption=msg, parse_mode="Markdown")
            else:
                self.bot.send_message(self.chat_id, msg, parse_mode="Markdown")
            logger.info(f"Telegram alert sent for: {jumia_title[:30]}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False

    def send_test_message(self) -> Dict[str, Any]:
        """Verify Telegram bot configuration."""
        if not self.is_configured():
            return {"success": False, "error": "Bot token or Chat ID is missing."}
        try:
            me = self.bot.get_me()
            self.bot.send_message(
                self.chat_id,
                f"✅ *JumiaDrop Alert Connected!*\nBot: @{me.username}\nReady to receive dropshipping alerts.",
                parse_mode="Markdown"
            )
            return {"success": True, "bot_username": me.username}
        except Exception as e:
            return {"success": False, "error": str(e)}

if __name__ == "__main__":
    notifier = TelegramNotifier()
    if notifier.is_configured():
        print("Testing Telegram connection...")
        res = notifier.send_test_message()
        print("Result:", res)
    else:
        print("Telegram not configured in config.py or .env")
