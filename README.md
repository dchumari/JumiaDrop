# 🛍️ JumiaDrop: Jiji-to-Jumia Dropshipping Arbitrage Engine (Kenya)

An automated market research, product discovery, and profit arbitrage suite engineered specifically for dropshipping in Kenya.

JumiaDrop indexes and matches products between **Jumia Kenya** and wholesale suppliers on **Jiji Kenya (Nairobi wholesale hubs: CBD, Kamukunji, Eastleigh, Industrial Area)**, factoring in all Jumia seller commissions, 16% VAT, packaging flyers, and Nairobi boda pickup buffers to identify low-competition, high-margin opportunities.

---

## ⚡ Key Capabilities

- **🌊 💎 Blue Ocean Reverse Sourcing**: Hunts for products readily available from Nairobi wholesale suppliers on Jiji that have **ZERO competing listings on Jumia Kenya**, calculating suggested retail prices and guaranteed uncontested margins.
- **📦 Deep Catalog Bulk Harvester**: Deep-crawls up to **50 pages per category** across the official 20 primary Jumia categories parsed directly from your 21 Excel product creation templates.
- **🖼️ Compact Specification Clusters with Image Thumbnails**: Minimized, image-rich product family cards showing Min, Median, Average, and Max price spreads across Jumia and Jiji.
- **⚖️ Supply vs Demand Arbitrage Index**: Flags products that are **"🔥 Abundant on Jiji, Scarce on Jumia"** with a single toggle.
- **🛡️ 48-Source Rotating Proxy Pool**: Automatically ingests, health-checks, and rotates proxies across 48 public GitHub proxy lists (HTTP, HTTPS, SOCKS4, SOCKS5).
- **🚀 High-Speed Asynchronous Crawlers**: Multi-worker parallel page and keyword fetchers for both Jumia and Jiji API.
- **🔄 Auto-Reload on Code Edits**: Pre-configured with `.streamlit/config.toml` so edits hot-reload without restarting the server.
- **🧮 Realistic Kenyan Unit Economics**: Complete fee modeling (commissions, 16% VAT, packaging KES 30, Boda allowance KES 150).

---

## 📂 Project Structure

```
JumiaDrop/
├── .streamlit/
│   └── config.toml            # Auto-reload and dark theme configuration
├── app.py                     # Streamlit Interactive Web Dashboard
├── async_scanner.py           # High-speed asynchronous market orchestrator
├── bulk_harvester.py          # Deep catalog crawler (up to 50 pages per category)
├── template_loader.py         # Parses official Jumia categories from 21 templates
├── categories_taxonomy.json   # Cached category taxonomy (20 primary, 20,000+ leaves)
├── proxy_manager.py           # 48-source proxy fetcher, validator & rotator
├── working_proxies.json       # Cached verified fast working proxies
├── config.py                  # Fee tables, starter niches, Nairobi filters
├── database.py                # SQLite persistence (jumia_drop.db)
├── run_scanner.py             # CLI runner for quick scans and proxy commands
├── scheduler.py               # Background scheduler (daily, 2-day, weekly)
├── notifier.py                # Telegram bot integration
├── templates/
│   └── jumia_templates/       # 21 Official Jumia Seller Center Excel templates
├── engine/
│   ├── calculator.py          # Kenyan unit economics & opportunity scoring
│   ├── matcher.py             # Attribute extraction & fuzzy matching
│   ├── clustering.py          # Product grouping & price distribution analytics
│   └── reverse_sourcing.py    # Blue Ocean unlisted product engine
├── scrapers/
│   ├── jumia_scraper.py       # Synchronous Jumia scraper
│   ├── jiji_scraper.py        # Synchronous Jiji scraper
│   ├── async_jumia_scraper.py # High-speed async Jumia scraper
│   └── async_jiji_scraper.py  # High-speed async Jiji scraper
└── tests/                     # Automated unit test suite (8 passing tests)
```

---

## 🚀 Quick Start Guide

### 1. Launch the Web Dashboard
```powershell
.venv\Scripts\streamlit run app.py
```
Open your browser at `http://localhost:8501`. (Edits will auto-reload automatically).

### 2. Run a Deep Bulk Harvest (CLI)
```powershell
# Crawl 10 pages of Automobile category
.venv\Scripts\python run_scanner.py --category "Automobile" --jumia-pages 10 --async

# Scan specific keyword with rotating proxies
.venv\Scripts\python run_scanner.py --keyword "cordless drill" --use-proxies
```

### 3. Run Unit Tests
```powershell
.venv\Scripts\pytest tests/
```
