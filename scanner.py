"""
Market Scanner & Pipeline Orchestrator for JumiaDrop.
Coordinates scraping Jumia and Jiji, running matcher and profit calculator, and updating the database.
"""
import time
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
    log_scan_event,
    get_connection
)
from scrapers.jumia_scraper import JumiaScraper
from scrapers.jiji_scraper import JijiScraper
from engine.calculator import ProfitCalculator
from engine.matcher import ProductMatcher

logger = logging.getLogger(__name__)

class MarketScanner:
    def __init__(
        self,
        min_profit: float = DEFAULT_MIN_NET_PROFIT_KES,
        min_margin: float = DEFAULT_MIN_MARGIN_PCT,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE_SCORE
    ):
        self.min_profit = min_profit
        self.min_margin = min_margin
        self.min_confidence = min_confidence

        self.jumia_scraper = JumiaScraper()
        self.jiji_scraper = JijiScraper()
        self.calculator = ProfitCalculator()
        self.matcher = ProductMatcher(min_confidence=min_confidence)

    def scan_keyword(
        self,
        keyword: str,
        category_name: str = "General",
        jumia_pages: int = 1,
        jiji_pages: int = 1,
        on_progress = None
    ) -> Dict[str, Any]:
        """
        Scan a single keyword or product query across both Jumia Kenya and Jiji Kenya.
        """
        start_time = time.time()
        logger.info(f"Starting scan for '{keyword}' (Category: {category_name})")
        if on_progress:
            on_progress(f"Scraping Jumia Kenya for '{keyword}'...", 0.2)

        # 1. Scrape Jumia
        jumia_items = self.jumia_scraper.search_products(keyword, category_name=category_name, max_pages=jumia_pages)
        jumia_db_records = []
        for item in jumia_items:
            db_id = save_jumia_product(item)
            item["db_id"] = db_id
            jumia_db_records.append(item)

        if on_progress:
            on_progress(f"Scraping Jiji Kenya Nairobi wholesale listings for '{keyword}'...", 0.5)

        # 2. Scrape Jiji (Strictly Nairobi)
        jiji_items = self.jiji_scraper.search_adverts(keyword, category_name=category_name, max_pages=jiji_pages)
        jiji_db_records = []
        for item in jiji_items:
            db_id = save_jiji_advert(item)
            item["db_id"] = db_id
            jiji_db_records.append(item)

        if on_progress:
            on_progress("Comparing products and calculating profit margins...", 0.8)

        # 3. Match and Calculate Arbitrage
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
            scan_type="keyword",
            target=keyword,
            jumia_c=len(jumia_db_records),
            jiji_c=len(jiji_db_records),
            deals_c=deals_found,
            duration=duration
        )

        if on_progress:
            on_progress(f"Scan complete in {duration}s!", 1.0)

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

    def scan_niche(self, niche_name: str, max_keywords: int = 5, on_progress = None) -> List[Dict[str, Any]]:
        """Scan multiple seed keywords within a specific niche."""
        keywords = STARTER_NICHES.get(niche_name, [])
        if max_keywords:
            keywords = keywords[:max_keywords]

        results = []
        total = len(keywords)
        for idx, kw in enumerate(keywords, 1):
            if on_progress:
                on_progress(f"Scanning niche '{niche_name}' ({idx}/{total}): '{kw}'", idx / total)
            res = self.scan_keyword(kw, category_name=niche_name, jumia_pages=1, jiji_pages=1)
            results.append(res)

        return results

    def scan_all_niches(self, max_keywords_per_niche: int = 3, on_progress = None) -> Dict[str, Any]:
        """Scan across all 5 starter niches."""
        total_niches = len(STARTER_NICHES)
        all_results = {}
        for idx, niche in enumerate(STARTER_NICHES.keys(), 1):
            if on_progress:
                on_progress(f"Processing niche {idx}/{total_niches}: {niche}", (idx - 1) / total_niches)
            res = self.scan_niche(niche, max_keywords=max_keywords_per_niche)
            all_results[niche] = res

        return all_results
