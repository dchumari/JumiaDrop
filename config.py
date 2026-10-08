"""
Configuration settings for JumiaDrop: Jiji to Jumia Dropshipping Engine.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "jumia_drop.db")

# Jumia Kenya Commission Rates by Category (approximate seller fees)
DEFAULT_CATEGORY_COMMISSIONS = {
    "Home & Kitchen": 0.14,           # 14%
    "Auto Accessories": 0.12,         # 12%
    "Electronics & Gadgets": 0.09,    # 9%
    "Phones & Tablets Accessories": 0.08, # 8%
    "Health & Beauty": 0.15,          # 15%
    "Tools & Home Improvement": 0.12, # 12%
    "Fashion & Accessories": 0.16,    # 16%
    "Other": 0.12                     # Default 12%
}

# Standard Kenyan E-commerce Cost Parameters
VAT_ON_COMMISSION = 0.16  # 16% VAT charged on Jumia commission
DEFAULT_PACKAGING_COST_KES = 30.0  # Jumia standard flyer / branded bag
DEFAULT_BODA_RUNNER_COST_KES = 150.0  # Nairobi courier pickup to Jumia hub buffer

# Dropshipping Opportunity Qualifying Thresholds
DEFAULT_MIN_NET_PROFIT_KES = 500.0  # Minimum KES 500 net profit
DEFAULT_MIN_MARGIN_PCT = 25.0       # Minimum 25% net profit margin
DEFAULT_MIN_CONFIDENCE_SCORE = 65.0 # Match similarity threshold (0-100)
DEFAULT_MAX_JUMIA_REVIEWS = 35     # Items with fewer than 35 reviews = Low Competition

# Top 5 Starter Niches and Seed Queries
STARTER_NICHES = {
    "Home & Kitchen": [
        "portable air fryer accessories",
        "handheld milk frother",
        "electric garlic chopper",
        "silicone kitchen utensils",
        "spice rack organizer",
        "mini sealing machine",
        "vegetable slicer cutter"
    ],
    "Auto Accessories": [
        "car vacuum cleaner cordless",
        "car dash cam 1080p",
        "high pressure car wash spray",
        "car phone mount wireless charger",
        "car scratch repair kit",
        "inflatable car bed mattress",
        "car bluetooth fm transmitter"
    ],
    "Electronics & Gadgets": [
        "smart watch magnetic strap",
        "rgb ring light with tripod",
        "wireless bluetooth lapel mic",
        "solar rechargeable emergency light",
        "rechargeable mini desk fan",
        "portable power bank 20000mah",
        "tws wireless earbuds"
    ],
    "Health & Beauty": [
        "cordless hair clipper trimmer",
        "deep tissue muscle massage gun",
        "electric facial cleansing brush",
        "hair straightener comb",
        "nail lamp uv led 48w",
        "blackhead remover vacuum"
    ],
    "Tools & Home Improvement": [
        "cordless drill driver 21v",
        "digital laser distance measure",
        "flexible socket wrench set",
        "electric soldering iron kit",
        "hot melt glue gun cordless",
        "multimeter digital tester"
    ]
}

# Jiji Regional Filtering: strictly Nairobi wholesale hubs for same-day 24h pickup
NAIROBI_ACCEPTED_REGIONS = [
    "nairobi", "cbd", "kamukunji", "eastleigh", "industrial area", 
    "westlands", "ngara", "kasarani", "river road", "luthuli", "gikomba"
]

# Telegram Alert Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Request Headers to mimic real browser
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

JIJI_API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://jiji.co.ke",
    "Referer": "https://jiji.co.ke/",
}
