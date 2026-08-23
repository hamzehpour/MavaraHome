#!/usr/bin/env python3
"""
Seeds the `portfolio` table with Mansour's real resume/CV content
(31 productions — cinema, series, shorts, theater). Unlike
seed_database.py, this is REAL production content, not test/fake data —
so it's safe to run in any environment, including production, and is
idempotent (does nothing if the table already has rows, so re-running it
by accident never creates duplicates).

Source data: data/portfolio_seed.json (extracted once from the website's
original assets/js/legacy-data.js — the 31-item dataset that used to live
only in frontend JS with no admin-editable backend).

Usage:
    python seed_portfolio.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    from database.schema import init_db
    from database.repositories import portfolio as portfolio_repo

    init_db()

    existing = portfolio_repo.count()
    if existing > 0:
        print(f"Portfolio table already has {existing} item(s) — nothing to do.")
        print("(This script is additive-only; edit existing items from the admin panel instead.)")
        return

    seed_path = Path(__file__).resolve().parent / "data" / "portfolio_seed.json"
    if not seed_path.exists():
        print(f"❌ Seed file not found: {seed_path}")
        return

    items = json.loads(seed_path.read_text(encoding="utf-8"))
    for i, item in enumerate(items):
        portfolio_repo.create(
            title_fa=item["title_fa"], title_en=item.get("title_en"),
            year=item.get("year"), category=item["category"],
            director=item.get("director"), director_en=item.get("director_en"),
            role=item.get("role"), role_en=item.get("role_en"),
            festival=item.get("festival"), festival_en=item.get("festival_en"),
            poster=item.get("poster"), gallery=item.get("gallery") or [],
            video=item.get("video"), desc_fa=item.get("desc_fa"), desc_en=item.get("desc_en"),
            status=item.get("status", "active"),
            sort_order=i,
        )
    print(f"✅ Seeded {len(items)} portfolio items.")


if __name__ == "__main__":
    main()
