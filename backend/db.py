import aiosqlite
from loguru import logger

from backend.config import settings

DB_PATH = settings.db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    max_price REAL,
    location TEXT NOT NULL,
    radius INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fb_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    price REAL NOT NULL,
    fair_price REAL,
    discount_pct REAL,
    deal_quality TEXT NOT NULL DEFAULT 'none',
    link TEXT NOT NULL,
    thumbnail TEXT,
    location TEXT,
    item_name TEXT NOT NULL,
    first_seen TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS price_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT NOT NULL,
    median_price REAL NOT NULL,
    low_price REAL,
    high_price REAL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'ebay',
    estimated_at TEXT NOT NULL DEFAULT (datetime('now')),
    sold_prices TEXT
);

CREATE TABLE IF NOT EXISTS query_facets_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    spec_json TEXT NOT NULL,
    extracted_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_facets_query ON query_facets_cache(query);

CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    items_scanned INTEGER NOT NULL DEFAULT 0,
    deals_found INTEGER NOT NULL DEFAULT 0,
    new_listings INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'running'
);
"""


async def get_db() -> aiosqlite.Connection:
    # WAL lets the API read while a Celery worker writes; without it concurrent
    # access raises "database is locked". busy_timeout makes contenders wait
    # rather than fail instantly.
    db = await aiosqlite.connect(DB_PATH, timeout=30.0)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=30000")
    return db


# Columns added after the initial schema shipped. SQLite has no
# ADD COLUMN IF NOT EXISTS, so existing databases are migrated explicitly.
_LISTING_MIGRATIONS = {
    "relevance_score": "ALTER TABLE listings ADD COLUMN relevance_score REAL",
    "final_score": "ALTER TABLE listings ADD COLUMN final_score REAL",
    "match_details": "ALTER TABLE listings ADD COLUMN match_details TEXT",
}


async def _migrate_listings(db: aiosqlite.Connection):
    rows = await db.execute_fetchall("PRAGMA table_info(listings)")
    existing = {row["name"] for row in rows}
    for column, ddl in _LISTING_MIGRATIONS.items():
        if column not in existing:
            logger.info("Migrating listings: adding column {}", column)
            await db.execute(ddl)


async def init_db():
    logger.info("Initializing database at {}", DB_PATH)
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await _migrate_listings(db)
        await db.commit()
        logger.info("Database initialized successfully")
    finally:
        await db.close()


# --- Watchlist CRUD ---


async def add_watch_item(name: str, max_price: float | None, location: str, radius: int) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO watchlist (name, max_price, location, radius) VALUES (?, ?, ?, ?)",
            (name, max_price, location, radius),
        )
        await db.commit()
        row = await db.execute_fetchall(
            "SELECT * FROM watchlist WHERE id = ?", (cursor.lastrowid,)
        )
        logger.info("Added watch item: {} (id={})", name, cursor.lastrowid)
        return dict(row[0])
    finally:
        await db.close()


async def get_watch_items() -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM watchlist ORDER BY created_at DESC")
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_watch_item(item_id: int) -> dict | None:
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM watchlist WHERE id = ?", (item_id,))
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


async def delete_watch_item(item_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM watchlist WHERE id = ?", (item_id,))
        await db.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted watch item id={}", item_id)
        return deleted
    finally:
        await db.close()


# --- Listings CRUD ---


async def upsert_listing(
    fb_id: str,
    title: str,
    price: float,
    link: str,
    item_name: str,
    fair_price: float | None = None,
    discount_pct: float | None = None,
    deal_quality: str = "none",
    thumbnail: str | None = None,
    location: str | None = None,
    relevance_score: float | None = None,
    final_score: float | None = None,
    match_details: str | None = None,
) -> dict | None:
    db = await get_db()
    try:
        # A SELECT-then-INSERT loses the race against a concurrent writer and
        # raises IntegrityError, aborting the rest of the scan's listings. The
        # UNIQUE index decides instead: no row inserted means someone else won.
        cursor = await db.execute(
            """INSERT INTO listings
            (fb_id, title, price, fair_price, discount_pct, deal_quality, link, thumbnail, location,
             item_name, relevance_score, final_score, match_details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fb_id) DO NOTHING""",
            (fb_id, title, price, fair_price, discount_pct, deal_quality, link, thumbnail, location,
             item_name, relevance_score, final_score, match_details),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None  # already seen

        rows = await db.execute_fetchall("SELECT * FROM listings WHERE id = ?", (cursor.lastrowid,))
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


# Whitelisted so `sort` can never reach the query as user-controlled SQL.
# NULLs last keeps pre-migration rows from squatting the top of scored sorts.
SORT_CLAUSES = {
    "final": "ORDER BY final_score IS NULL, final_score DESC",
    "relevance": "ORDER BY relevance_score IS NULL, relevance_score DESC",
    "deal": "ORDER BY discount_pct IS NULL, discount_pct DESC",
    "price": "ORDER BY price ASC",
    "recent": "ORDER BY first_seen DESC",
}


async def get_listings(
    item_name: str | None = None,
    deal_quality: str | None = None,
    limit: int = 100,
    offset: int = 0,
    sort: str = "recent",
) -> list[dict]:
    db = await get_db()
    try:
        query = "SELECT * FROM listings WHERE 1=1"
        params: list = []
        if item_name:
            query += " AND item_name = ?"
            params.append(item_name)
        if deal_quality:
            query += " AND deal_quality = ?"
            params.append(deal_quality)
        query += f" {SORT_CLAUSES.get(sort, SORT_CLAUSES['recent'])} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = await db.execute_fetchall(query, params)
        return [dict(r) for r in rows]
    finally:
        await db.close()


# --- Price Cache ---


async def get_cached_price(item_name: str, max_age_days: int = 7) -> dict | None:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT * FROM price_cache
            WHERE item_name = ?
            AND julianday('now') - julianday(estimated_at) < ?
            ORDER BY estimated_at DESC LIMIT 1""",
            (item_name, max_age_days),
        )
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


async def save_price_cache(
    item_name: str,
    median_price: float,
    sample_count: int,
    source: str,
    low_price: float | None = None,
    high_price: float | None = None,
    sold_prices: str | None = None,
) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO price_cache
            (item_name, median_price, low_price, high_price, sample_count, source, sold_prices)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (item_name, median_price, low_price, high_price, sample_count, source, sold_prices),
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM price_cache WHERE id = ?", (cursor.lastrowid,))
        return dict(rows[0])
    finally:
        await db.close()


async def existing_fb_ids(fb_ids: list[str]) -> set[str]:
    """Which of these listings are already stored? One query, not N."""
    if not fb_ids:
        return set()
    db = await get_db()
    try:
        placeholders = ",".join("?" * len(fb_ids))
        rows = await db.execute_fetchall(
            f"SELECT fb_id FROM listings WHERE fb_id IN ({placeholders})", fb_ids
        )
        return {row["fb_id"] for row in rows}
    finally:
        await db.close()


# --- Facet cache ---


async def get_cached_facets(query: str, max_age_days: int = 30) -> str | None:
    """Return the cached spec JSON for a query, or None if absent/stale."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT spec_json FROM query_facets_cache
            WHERE query = ?
            AND julianday('now') - julianday(extracted_at) < ?
            ORDER BY extracted_at DESC LIMIT 1""",
            (query, max_age_days),
        )
        return rows[0]["spec_json"] if rows else None
    finally:
        await db.close()


async def save_facets_cache(query: str, spec_json: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO query_facets_cache (query, spec_json) VALUES (?, ?)",
            (query, spec_json),
        )
        await db.commit()
    finally:
        await db.close()


# --- Scans ---


async def create_scan() -> dict:
    db = await get_db()
    try:
        cursor = await db.execute("INSERT INTO scans (status) VALUES ('running')")
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM scans WHERE id = ?", (cursor.lastrowid,))
        return dict(rows[0])
    finally:
        await db.close()


async def update_scan(
    scan_id: int,
    status: str | None = None,
    items_scanned: int | None = None,
    deals_found: int | None = None,
    new_listings: int | None = None,
) -> dict:
    db = await get_db()
    try:
        updates = []
        params: list = []
        if status:
            updates.append("status = ?")
            params.append(status)
            if status in ("completed", "failed"):
                updates.append("completed_at = datetime('now')")
        if items_scanned is not None:
            updates.append("items_scanned = ?")
            params.append(items_scanned)
        if deals_found is not None:
            updates.append("deals_found = ?")
            params.append(deals_found)
        if new_listings is not None:
            updates.append("new_listings = ?")
            params.append(new_listings)
        params.append(scan_id)
        await db.execute(f"UPDATE scans SET {', '.join(updates)} WHERE id = ?", params)
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM scans WHERE id = ?", (scan_id,))
        return dict(rows[0])
    finally:
        await db.close()


async def get_scans(limit: int = 20) -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM scans ORDER BY started_at DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_scan(scan_id: int) -> dict | None:
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM scans WHERE id = ?", (scan_id,))
        return dict(rows[0]) if rows else None
    finally:
        await db.close()
