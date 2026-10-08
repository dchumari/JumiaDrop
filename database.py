"""
Database module for JumiaDrop.
Handles SQLite storage for Jumia products, Jiji adverts, arbitrage deals, and scan logs.
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
from config import DB_PATH

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables with optimal indexes."""
    conn = get_connection()
    cursor = conn.cursor()

    # Jumia Products Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jumia_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_key TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        category TEXT,
        price REAL NOT NULL,
        old_price REAL,
        rating REAL DEFAULT 0.0,
        reviews_count INTEGER DEFAULT 0,
        is_express INTEGER DEFAULT 0,
        badge TEXT,
        url TEXT NOT NULL,
        image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Jiji Adverts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jiji_adverts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        advert_key TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        category TEXT,
        price REAL NOT NULL,
        region_name TEXT,
        location_text TEXT,
        short_description TEXT,
        url TEXT NOT NULL,
        image_url TEXT,
        user_id TEXT,
        user_phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Arbitrage Opportunities Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS arbitrage_deals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        jumia_id INTEGER NOT NULL,
        jiji_id INTEGER NOT NULL,
        confidence_score REAL NOT NULL,
        category TEXT,
        jumia_price REAL NOT NULL,
        jiji_price REAL NOT NULL,
        jumia_commission REAL NOT NULL,
        vat_amount REAL NOT NULL,
        packaging_cost REAL NOT NULL,
        boda_cost REAL NOT NULL,
        total_cost REAL NOT NULL,
        net_profit REAL NOT NULL,
        margin_pct REAL NOT NULL,
        competition_score REAL NOT NULL,
        opportunity_score REAL NOT NULL,
        status TEXT DEFAULT 'active', -- active, starred, listed, ignored
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(jumia_id, jiji_id),
        FOREIGN KEY (jumia_id) REFERENCES jumia_products(id) ON DELETE CASCADE,
        FOREIGN KEY (jiji_id) REFERENCES jiji_adverts(id) ON DELETE CASCADE
    )
    """)

    # Scan Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scan_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_type TEXT,
        target_name TEXT,
        jumia_found INTEGER DEFAULT 0,
        jiji_found INTEGER DEFAULT 0,
        deals_found INTEGER DEFAULT 0,
        duration_sec REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create Indexes for fast lookup and filtering
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jumia_cat ON jumia_products(category);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jiji_price ON jiji_adverts(price);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deal_profit ON arbitrage_deals(net_profit);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deal_margin ON arbitrage_deals(margin_pct);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deal_opp_score ON arbitrage_deals(opportunity_score);")

    conn.commit()
    conn.close()

def save_jumia_product(item: Dict[str, Any]) -> int:
    """Insert or update a Jumia product and return its database ID."""
    conn = get_connection()
    cursor = conn.cursor()
    product_key = item.get("url") or item.get("title")
    now = datetime.utcnow().isoformat()

    cursor.execute("""
    INSERT INTO jumia_products (
        product_key, title, category, price, old_price, rating, reviews_count,
        is_express, badge, url, image_url, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(product_key) DO UPDATE SET
        title = excluded.title,
        category = COALESCE(excluded.category, jumia_products.category),
        price = excluded.price,
        old_price = excluded.old_price,
        rating = excluded.rating,
        reviews_count = excluded.reviews_count,
        is_express = excluded.is_express,
        badge = excluded.badge,
        url = excluded.url,
        image_url = excluded.image_url,
        updated_at = excluded.updated_at
    """, (
        product_key,
        item.get("title"),
        item.get("category"),
        item.get("price", 0.0),
        item.get("old_price"),
        item.get("rating", 0.0),
        item.get("reviews_count", 0),
        1 if item.get("is_express") else 0,
        item.get("badge"),
        item.get("url"),
        item.get("image_url"),
        now
    ))
    conn.commit()
    cursor.execute("SELECT id FROM jumia_products WHERE product_key = ?", (product_key,))
    row = cursor.fetchone()
    jumia_id = row[0] if row else 0
    conn.close()
    return jumia_id

def save_jiji_advert(item: Dict[str, Any]) -> int:
    """Insert or update a Jiji advert and return its database ID."""
    conn = get_connection()
    cursor = conn.cursor()
    advert_key = str(item.get("id") or item.get("url"))
    now = datetime.utcnow().isoformat()

    cursor.execute("""
    INSERT INTO jiji_adverts (
        advert_key, title, category, price, region_name, location_text,
        short_description, url, image_url, user_id, user_phone, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(advert_key) DO UPDATE SET
        title = excluded.title,
        category = COALESCE(excluded.category, jiji_adverts.category),
        price = excluded.price,
        region_name = excluded.region_name,
        location_text = excluded.location_text,
        short_description = excluded.short_description,
        url = excluded.url,
        image_url = excluded.image_url,
        user_id = excluded.user_id,
        user_phone = excluded.user_phone,
        updated_at = excluded.updated_at
    """, (
        advert_key,
        item.get("title"),
        item.get("category"),
        item.get("price", 0.0),
        item.get("region_name"),
        item.get("location_text"),
        item.get("short_description"),
        item.get("url"),
        item.get("image_url"),
        str(item.get("user_id") or ""),
        item.get("user_phone"),
        now
    ))
    conn.commit()
    cursor.execute("SELECT id FROM jiji_adverts WHERE advert_key = ?", (advert_key,))
    row = cursor.fetchone()
    jiji_id = row[0] if row else 0
    conn.close()
    return jiji_id

def save_arbitrage_deal(deal: Dict[str, Any]) -> int:
    """Insert or update an arbitrage match."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    cursor.execute("""
    INSERT INTO arbitrage_deals (
        jumia_id, jiji_id, confidence_score, category, jumia_price, jiji_price,
        jumia_commission, vat_amount, packaging_cost, boda_cost, total_cost,
        net_profit, margin_pct, competition_score, opportunity_score, status, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(jumia_id, jiji_id) DO UPDATE SET
        confidence_score = excluded.confidence_score,
        category = excluded.category,
        jumia_price = excluded.jumia_price,
        jiji_price = excluded.jiji_price,
        jumia_commission = excluded.jumia_commission,
        vat_amount = excluded.vat_amount,
        packaging_cost = excluded.packaging_cost,
        boda_cost = excluded.boda_cost,
        total_cost = excluded.total_cost,
        net_profit = excluded.net_profit,
        margin_pct = excluded.margin_pct,
        competition_score = excluded.competition_score,
        opportunity_score = excluded.opportunity_score,
        updated_at = excluded.updated_at
    """, (
        deal["jumia_id"],
        deal["jiji_id"],
        deal["confidence_score"],
        deal.get("category", "General"),
        deal["jumia_price"],
        deal["jiji_price"],
        deal["jumia_commission"],
        deal["vat_amount"],
        deal["packaging_cost"],
        deal["boda_cost"],
        deal["total_cost"],
        deal["net_profit"],
        deal["margin_pct"],
        deal["competition_score"],
        deal["opportunity_score"],
        deal.get("status", "active"),
        now
    ))
    deal_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return deal_id

def log_scan_event(scan_type: str, target: str, jumia_c: int, jiji_c: int, deals_c: int, duration: float):
    """Record a scan run in the logs table."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO scan_logs (scan_type, target_name, jumia_found, jiji_found, deals_found, duration_sec)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (scan_type, target, jumia_c, jiji_c, deals_c, duration))
    conn.commit()
    conn.close()

def get_arbitrage_deals(
    category: Optional[str] = None,
    min_profit: float = 0.0,
    min_margin: float = 0.0,
    max_reviews: Optional[int] = None,
    min_confidence: float = 50.0,
    status: Optional[str] = "active",
    limit: int = 200
) -> pd.DataFrame:
    """Fetch deals joined with Jumia and Jiji listing details as a pandas DataFrame."""
    conn = get_connection()
    query = """
    SELECT 
        d.id as deal_id,
        d.confidence_score,
        d.opportunity_score,
        d.category,
        d.jumia_price,
        d.jiji_price,
        d.jumia_commission,
        d.vat_amount,
        d.packaging_cost,
        d.boda_cost,
        d.total_cost,
        d.net_profit,
        d.margin_pct,
        d.competition_score,
        d.status,
        -- Jumia details
        p.title as jumia_title,
        p.rating as jumia_rating,
        p.reviews_count as jumia_reviews,
        p.is_express as jumia_express,
        p.url as jumia_url,
        p.image_url as jumia_image,
        -- Jiji details
        j.title as jiji_title,
        j.region_name as jiji_region,
        j.location_text as jiji_location,
        j.short_description as jiji_description,
        j.url as jiji_url,
        j.image_url as jiji_image,
        j.user_id as jiji_user_id,
        j.user_phone as jiji_phone
    FROM arbitrage_deals d
    JOIN jumia_products p ON d.jumia_id = p.id
    JOIN jiji_adverts j ON d.jiji_id = j.id
    WHERE d.net_profit >= ?
      AND d.margin_pct >= ?
      AND d.confidence_score >= ?
    """
    params = [min_profit, min_margin, min_confidence]

    if category and category != "All":
        query += " AND d.category = ?"
        params.append(category)

    if max_reviews is not None:
        query += " AND p.reviews_count <= ?"
        params.append(max_reviews)

    if status and status != "All":
        query += " AND d.status = ?"
        params.append(status)

    query += " ORDER BY d.opportunity_score DESC LIMIT ?"
    params.append(limit)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def update_deal_status(deal_id: int, new_status: str, notes: Optional[str] = None):
    """Update deal status (starred, listed, ignored)."""
    conn = get_connection()
    cursor = conn.cursor()
    if notes:
        cursor.execute("UPDATE arbitrage_deals SET status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, notes, deal_id))
    else:
        cursor.execute("UPDATE arbitrage_deals SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, deal_id))
    conn.commit()
    conn.close()

def get_database_stats() -> Dict[str, Any]:
    """Return summary statistics of the database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM jumia_products")
    jumia_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM jiji_adverts")
    jiji_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM arbitrage_deals")
    deals_count = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(net_profit), MAX(net_profit), AVG(margin_pct) FROM arbitrage_deals WHERE net_profit > 0")
    row = cursor.fetchone()
    avg_profit = row[0] or 0.0
    max_profit = row[1] or 0.0
    avg_margin = row[2] or 0.0

    conn.close()
    return {
        "jumia_products": jumia_count,
        "jiji_adverts": jiji_count,
        "total_deals": deals_count,
        "avg_profit_kes": round(avg_profit, 2),
        "max_profit_kes": round(max_profit, 2),
        "avg_margin_pct": round(avg_margin, 2)
    }

def is_recently_scraped(target: str, ttl_hours: float = 24.0) -> bool:
    """Check if a target keyword or category was crawled within the TTL window."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT created_at FROM scan_logs 
        WHERE LOWER(target_name) = LOWER(?)
        ORDER BY id DESC LIMIT 1
    """, (target.strip(),))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        return False

    try:
        # SQLite CURRENT_TIMESTAMP is in format: YYYY-MM-DD HH:MM:SS
        created_str = str(row[0])
        created_time = datetime.fromisoformat(created_str.replace("Z", ""))
        elapsed_hours = (datetime.utcnow() - created_time).total_seconds() / 3600.0
        return elapsed_hours < ttl_hours
    except Exception:
        return False

def get_distinct_categories() -> List[str]:
    """Retrieve all unique product categories stored in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT category FROM jumia_products WHERE category IS NOT NULL AND category != ''
        UNION
        SELECT DISTINCT category FROM arbitrage_deals WHERE category IS NOT NULL AND category != ''
    """)
    rows = cursor.fetchall()
    conn.close()
    cats = [r[0] for r in rows if r[0]]
    return sorted(list(set(cats)))

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
