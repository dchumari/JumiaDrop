"""
Blue Ocean & Reverse Sourcing Engine for JumiaDrop.
Discovers wholesale products that are readily available on Jiji Kenya in Nairobi,
queries Jumia Kenya, and if 0 competing listings exist, classifies them as
"💎 Blue Ocean Unlisted Opportunities" with automated suggested selling prices and profit margins.
"""
import time
import asyncio
import logging
from typing import List, Dict, Any, Optional
import pandas as pd
from scrapers.async_jiji_scraper import AsyncJijiScraper
from scrapers.async_jumia_scraper import AsyncJumiaScraper
from engine.calculator import ProfitCalculator
from engine.matcher import ProductMatcher
from database import (
    save_jiji_advert,
    get_connection,
    init_db
)

logger = logging.getLogger(__name__)

class ReverseSourcingEngine:
    def __init__(
        self,
        min_profit_kes: float = 600.0,
        min_margin_pct: float = 30.0,
        target_markup: float = 2.2, # 2.2x wholesale price
        use_proxies: bool = False
    ):
        self.min_profit_kes = min_profit_kes
        self.min_margin_pct = min_margin_pct
        self.target_markup = target_markup
        self.use_proxies = use_proxies

        self.jiji_scraper = AsyncJijiScraper()
        self.jumia_scraper = AsyncJumiaScraper()
        self.calculator = ProfitCalculator()
        self.matcher = ProductMatcher(min_confidence=60.0)
        self.init_blue_ocean_table()

    def init_blue_ocean_table(self):
        """Create blue_ocean_deals table in SQLite if it does not exist."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS blue_ocean_deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jiji_id INTEGER NOT NULL,
            category TEXT,
            title TEXT NOT NULL,
            jiji_price REAL NOT NULL,
            recommended_jumia_price REAL NOT NULL,
            estimated_commission REAL NOT NULL,
            vat_amount REAL NOT NULL,
            packaging_cost REAL NOT NULL,
            boda_cost REAL NOT NULL,
            net_profit REAL NOT NULL,
            margin_pct REAL NOT NULL,
            opportunity_score REAL NOT NULL,
            jiji_region TEXT,
            jiji_location TEXT,
            jiji_url TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(jiji_id)
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bo_profit ON blue_ocean_deals(net_profit);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bo_cat ON blue_ocean_deals(category);")
        conn.commit()
        conn.close()

    def save_blue_ocean_deal(self, deal: Dict[str, Any]) -> int:
        """Save an unlisted Blue Ocean opportunity to the database."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO blue_ocean_deals (
            jiji_id, category, title, jiji_price, recommended_jumia_price,
            estimated_commission, vat_amount, packaging_cost, boda_cost,
            net_profit, margin_pct, opportunity_score, jiji_region, jiji_location,
            jiji_url, image_url, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(jiji_id) DO UPDATE SET
            category = excluded.category,
            title = excluded.title,
            jiji_price = excluded.jiji_price,
            recommended_jumia_price = excluded.recommended_jumia_price,
            estimated_commission = excluded.estimated_commission,
            vat_amount = excluded.vat_amount,
            packaging_cost = excluded.packaging_cost,
            boda_cost = excluded.boda_cost,
            net_profit = excluded.net_profit,
            margin_pct = excluded.margin_pct,
            opportunity_score = excluded.opportunity_score,
            jiji_region = excluded.jiji_region,
            jiji_location = excluded.jiji_location,
            jiji_url = excluded.jiji_url,
            image_url = excluded.image_url
        """, (
            deal["jiji_id"],
            deal.get("category", "General"),
            deal["title"],
            deal["jiji_price"],
            deal["recommended_jumia_price"],
            deal["estimated_commission"],
            deal["vat_amount"],
            deal["packaging_cost"],
            deal["boda_cost"],
            deal["net_profit"],
            deal["margin_pct"],
            deal["opportunity_score"],
            deal.get("jiji_region"),
            deal.get("jiji_location"),
            deal.get("jiji_url"),
            deal.get("image_url"),
            deal.get("status", "active")
        ))
        deal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return deal_id

    async def scan_for_unlisted_products(
        self,
        query: str,
        category_name: str = "General",
        max_jiji_pages: int = 2,
        on_progress = None
    ) -> List[Dict[str, Any]]:
        """
        1. Fetch wholesale products from Jiji Nairobi.
        2. Query Jumia for each product title.
        3. If Jumia returns ZERO competing listings, calculate Blue Ocean pricing and profit.
        """
        if on_progress:
            on_progress(f"Fetching wholesale listings on Jiji Nairobi for '{query}'...", 0.2)

        jiji_ads = await self.jiji_scraper.search_adverts(
            query=query,
            category_name=category_name,
            max_pages=max_jiji_pages,
            strict_nairobi=True,
            use_proxies=self.use_proxies
        )

        if not jiji_ads:
            return []

        # Save Jiji items to adverts table
        for ad in jiji_ads:
            db_id = save_jiji_advert(ad)
            ad["db_id"] = db_id

        unlisted_deals = []
        total = len(jiji_ads)

        for idx, ad in enumerate(jiji_ads, 1):
            if on_progress:
                pct = 0.2 + (idx / total) * 0.7
                on_progress(f"Checking Jumia competition ({idx}/{total}): '{ad['title'][:35]}...'", pct)

            # Search Jumia for this specific item title
            # Clean title to extract key query terms
            clean_search = " ".join(self.matcher.clean_title(ad["title"]).split()[:5])
            jumia_matches = await self.jumia_scraper.search_products(
                query=clean_search,
                category_name=category_name,
                max_pages=1,
                use_proxies=self.use_proxies
            )

            # Check if any Jumia listing actually matches this product
            has_competitor = False
            for jm in jumia_matches:
                conf, _ = self.matcher.compute_match_confidence(
                    jumia_title=jm["title"],
                    jiji_title=ad["title"],
                    jiji_description=ad.get("short_description", "")
                )
                if conf >= 60.0:
                    has_competitor = True
                    break

            # If ZERO competitors found on Jumia, this is a BLUE OCEAN product!
            if not has_competitor:
                jiji_price = ad["price"]
                # Calculate recommended retail price
                rec_price = round(jiji_price * self.target_markup, -1) # rounded to nearest 10 KSh
                if rec_price < jiji_price + 600:
                    rec_price = jiji_price + 800

                fin = self.calculator.calculate_deal_finances(
                    jumia_price=rec_price,
                    jiji_price=jiji_price,
                    category=category_name
                )

                if fin["net_profit"] >= self.min_profit_kes and fin["margin_pct"] >= self.min_margin_pct:
                    deal_record = {
                        "jiji_id": ad["db_id"],
                        "category": category_name,
                        "title": ad["title"],
                        "jiji_price": jiji_price,
                        "recommended_jumia_price": rec_price,
                        "estimated_commission": fin["jumia_commission"],
                        "vat_amount": fin["vat_amount"],
                        "packaging_cost": fin["packaging_cost"],
                        "boda_cost": fin["boda_cost"],
                        "net_profit": fin["net_profit"],
                        "margin_pct": fin["margin_pct"],
                        "opportunity_score": 98.0, # 0 competition = Maximum Opportunity!
                        "jiji_region": ad.get("region_name", "Nairobi"),
                        "jiji_location": ad.get("location_text", ""),
                        "jiji_url": ad.get("url"),
                        "image_url": ad.get("image_url"),
                        "status": "active"
                    }
                    self.save_blue_ocean_deal(deal_record)
                    unlisted_deals.append(deal_record)

        if on_progress:
            on_progress(f"Reverse scan complete! Discovered {len(unlisted_deals)} unlisted Blue Ocean products.", 1.0)

        return unlisted_deals

def get_blue_ocean_deals(
    category: Optional[str] = None,
    min_profit: float = 0.0,
    min_margin: float = 0.0,
    limit: int = 100
) -> pd.DataFrame:
    """Query unlisted Blue Ocean products from the database."""
    conn = get_connection()
    query = """
    SELECT * FROM blue_ocean_deals
    WHERE net_profit >= ? AND margin_pct >= ?
    """
    params = [min_profit, min_margin]

    if category and category != "All":
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY net_profit DESC LIMIT ?"
    params.append(limit)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df
