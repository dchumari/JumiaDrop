"""
Background Scheduler for periodic JumiaDrop market scans.
Supports cadences: Daily, Every 2 Days, Weekly.
"""
import time
import threading
import logging
from datetime import datetime
import schedule
from scanner import MarketScanner
from notifier import TelegramNotifier
from config import STARTER_NICHES

logger = logging.getLogger(__name__)

class ScanScheduler:
    def __init__(
        self,
        cadence: str = "daily", # daily, every_2_days, weekly
        keywords_per_niche: int = 2,
        enable_telegram: bool = True
    ):
        self.cadence = cadence
        self.keywords_per_niche = keywords_per_niche
        self.enable_telegram = enable_telegram
        self.scanner = MarketScanner()
        self.notifier = TelegramNotifier()
        self.is_running = False
        self._thread = None
        self.last_run_time = None
        self.last_status = "Idle"

    def run_scheduled_job(self):
        """Execute the scheduled sweep across top niches."""
        logger.info(f"[{datetime.now()}] Triggering scheduled market sweep...")
        self.last_status = f"Running scan at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        try:
            results = self.scanner.scan_all_niches(max_keywords_per_niche=self.keywords_per_niche)
            total_deals = 0
            all_qualified = []

            for niche, niche_results in results.items():
                for res in niche_results:
                    total_deals += res.get("deals_count", 0)
                    all_qualified.extend(res.get("deals", []))

            logger.info(f"Scheduled sweep finished. Deals found: {total_deals}, Qualified: {len(all_qualified)}")

            # Send Telegram alerts for top qualified opportunities
            if self.enable_telegram and self.notifier.is_configured():
                # Sort by opportunity score and notify top 3
                sorted_deals = sorted(all_qualified, key=lambda d: d.get("opportunity_score", 0), reverse=True)
                for deal in sorted_deals[:3]:
                    self.notifier.send_deal_alert(deal)

            self.last_run_time = datetime.now().isoformat()
            self.last_status = f"Completed at {datetime.now().strftime('%H:%M:%S')} ({len(all_qualified)} deals)"
        except Exception as e:
            logger.error(f"Error during scheduled job: {e}")
            self.last_status = f"Error: {e}"

    def start_in_background(self):
        """Configure schedule and run in a daemon thread."""
        schedule.clear()

        if self.cadence == "daily":
            schedule.every().day.at("06:00").do(self.run_scheduled_job)
        elif self.cadence == "every_2_days":
            schedule.every(2).days.at("06:00").do(self.run_scheduled_job)
        elif self.cadence == "weekly":
            schedule.every().monday.at("06:00").do(self.run_scheduled_job)
        else:
            schedule.every().day.at("06:00").do(self.run_scheduled_job)

        self.is_running = True

        def _loop():
            while self.is_running:
                schedule.run_pending()
                time.sleep(10)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()
        logger.info(f"Scheduler started with cadence: {self.cadence}")

    def stop(self):
        self.is_running = False
        schedule.clear()
        logger.info("Scheduler stopped.")

if __name__ == "__main__":
    scheduler = ScanScheduler(cadence="daily")
    print("Testing immediate scheduled job execution...")
    scheduler.run_scheduled_job()
