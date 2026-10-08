"""
High-Speed Asynchronous Market Scanner for JumiaDrop.
Crawls Jumia and Jiji concurrently using aiohttp with proxy rotation, parallel keyword sweeps, and batch DB writes.
"""
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional
from config import (
    STARTER_NICHES,
    DEFAULT_MIN_NET_PROFIT_KES,
    DEFAULT_MIN_MARGIN_PCT,
    DEFAULT_MIN_CONFIDENCE_SCORE
)
from database import (
    save_jumia_product,
    save_jiji_advert,
    save_arbitrage_deal,
    log_scan_event
)
from scrapers.async_jumia_scraper import AsyncJumiaScraper
from scrapers.async_jiji_scraper import AsyncJijiScraper
from engine.calculator import ProfitCalculator
from engine.matcher import ProductMatcher
from proxy_manager import global_proxy_manager

logger = logging.getLogger(__name__)

class AsyncMarketScanner:
    def __init__(
        self,
        min_profit: float = DEFAULT_MIN_NET_PROFIT_KES,
        min_margin: float = DEFAULT_MIN_MARGIN_PCT,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE_SCORE,
        use_proxies: bool = False,
        max_concurrent_keywords: int = 4
    ):
        self.min_profit = min_profit
        self.min_margin = min_margin
        self.min_confidence = min_confidence
        self.use_proxies = use_proxies
        self.kw_semaphore = asyncio.Semaphore(max_concurrent_keywords)

        self.jumia_scraper = AsyncJumiaScraper()
        self.jiji_scraper = AsyncJijiScraper()
        self.calculator = ProfitCalculator()
        self.matcher = ProductMatcher(min_confidence=min_confidence)

    async def scan_keyword(
        self,
        keyword: str,
        category_name: str = "General",
        jumia_pages: int = 1,
        jiji_pages: int = 1,
        on_progress = None
    ) -> Dict[str, Any]:
        """
        Concurrently crawl Jumia and Jiji for a single keyword in parallel.
        """
        start_time = time.time()
        logger.info(f"Async scanning '{keyword}' ({category_name}) with proxies={self.use_proxies}...")

        if on_progress:
            on_progress(f"⚡ Concurrently scraping Jumia & Jiji for '{keyword}'...", 0.3)

        async with self.kw_semaphore:
            # Launch Jumia and Jiji concurrent fetch tasks simultaneously
            jumia_task = self.jumia_scraper.search_products(
                query=keyword,
                category_name=category_name,
                max_pages=jumia_pages,
                use_proxies=self.use_proxies
            )
            jiji_task = self.jiji_scraper.search_adverts(
                query=keyword,
                category_name=category_name,
                max_pages=jiji_pages,
                use_proxies=self.use_proxies
            )

            jumia_items, jiji_items = await asyncio.gather(jumia_task, jiji_task, return_exceptions=True)

        if isinstance(jumia_items, Exception):
            logger.error(f"Jumia scrape error: {jumia_items}")
            jumia_items = []
        if isinstance(jiji_items, Exception):
            logger.error(f"Jiji scrape error: {jiji_items}")
            jiji_items = []

        if on_progress:
            on_progress(f"Found {len(jumia_items)} Jumia & {len(jiji_items)} Jiji items. Processing matches...", 0.7)

        # Save Jumia products to database
        jumia_db_records = []
        for item in jumia_items:
            db_id = save_jumia_product(item)
            item["db_id"] = db_id
            jumia_db_records.append(item)

        # Save Jiji adverts to database
        jiji_db_records = []
        for item in jiji_items:
            db_id = save_jiji_advert(item)
            item["db_id"] = db_id
            jiji_db_records.append(item)

        # Compare and calculate arbitrage opportunities
        deals_found = 0
        qualified_deals = []

        for jm in jumia_db_records:
            best_match_deal = None
            best_confidence = 0.0

            for jj in jiji_db_records:
                conf, meta = self.matcher.compute_match_confidence(
                    jumia_title=jm["title"],
                    jiji_title=jj["title"],
                    jiji_description=jj.get("short_description", ""),
                    jumia_price=jm["price"],
                    jiji_price=jj["price"]
                )

                if conf >= self.min_confidence:
                    fin = self.calculator.calculate_deal_finances(
                        jumia_price=jm["price"],
                        jiji_price=jj["price"],
                        category=category_name
                    )

                    comp_score = self.calculator.compute_competition_score(
                        reviews_count=jm.get("reviews_count", 0),
                        rating=jm.get("rating", 0.0),
                        is_express=bool(jm.get("is_express"))
                    )

                    opp_score = self.calculator.compute_opportunity_score(
                        net_profit=fin["net_profit"],
                        margin_pct=fin["margin_pct"],
                        competition_score=comp_score,
                        confidence_score=conf
                    )

                    deal_dict = {
                        "jumia_id": jm["db_id"],
                        "jiji_id": jj["db_id"],
                        "confidence_score": conf,
                        "category": category_name,
                        "jumia_price": jm["price"],
                        "jiji_price": jj["price"],
                        "jumia_commission": fin["jumia_commission"],
                        "vat_amount": fin["vat_amount"],
                        "packaging_cost": fin["packaging_cost"],
                        "boda_cost": fin["boda_cost"],
                        "total_cost": fin["total_cost"],
                        "net_profit": fin["net_profit"],
                        "margin_pct": fin["margin_pct"],
                        "competition_score": comp_score,
                        "opportunity_score": opp_score,
                        "status": "active"
                    }

                    if conf > best_confidence:
                        best_confidence = conf
                        best_match_deal = deal_dict

            if best_match_deal:
                save_arbitrage_deal(best_match_deal)
                deals_found += 1
                if (best_match_deal["net_profit"] >= self.min_profit and 
                    best_match_deal["margin_pct"] >= self.min_margin):
                    qualified_deals.append(best_match_deal)

        duration = round(time.time() - start_time, 2)
        log_scan_event(
            scan_type="async_keyword",
            target=keyword,
            jumia_c=len(jumia_db_records),
            jiji_c=len(jiji_db_records),
            deals_c=deals_found,
            duration=duration
        )

        if on_progress:
            on_progress(f"⚡ Async scan complete in {duration}s! ({deals_found} matches)", 1.0)

        return {
            "keyword": keyword,
            "category": category_name,
            "jumia_count": len(jumia_db_records),
            "jiji_count": len(jiji_db_records),
            "deals_count": deals_found,
            "qualified_deals_count": len(qualified_deals),
            "duration_sec": duration,
            "deals": qualified_deals
        }

    async def scan_niche(self, niche_name: str, max_keywords: int = 5, on_progress = None) -> List[Dict[str, Any]]:
        """Concurrently scan multiple keywords within a niche."""
        keywords = STARTER_NICHES.get(niche_name, [])[:max_keywords]
        total = len(keywords)

        tasks = []
        for idx, kw in enumerate(keywords, 1):
            tasks.append(self.scan_keyword(kw, category_name=niche_name, jumia_pages=1, jiji_pages=1))

        if on_progress:
            on_progress(f"⚡ Concurrently scanning {total} keywords in '{niche_name}'...", 0.2)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid_results = [r for r in results if isinstance(r, dict)]

        if on_progress:
            on_progress(f"Niche scan complete!", 1.0)

        return valid_results

    async def scan_all_niches(self, max_keywords_per_niche: int = 2, on_progress = None) -> Dict[str, Any]:
        """Scan across all 5 starter niches concurrently."""
        all_results = {}
        total = len(STARTER_NICHES)
        for idx, niche in enumerate(STARTER_NICHES.keys(), 1):
            if on_progress:
                on_progress(f"Sweeping niche ({idx}/{total}): {niche}", (idx - 1) / total)
            res = await self.scan_niche(niche, max_keywords=max_keywords_per_niche)
            all_results[niche] = res
        return all_results
