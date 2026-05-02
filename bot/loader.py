"""
Dataset pre-loader — reads expanded dataset files at startup
so the bot has context from tick 1, before the judge pushes anything.

Pre-loaded data uses version=0, so judge pushes (version ≥ 1) always win.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import DATASET_DIR, EXPANDED_DIR
from .context_store import ContextStore


def preload_dataset(store: ContextStore):
    """Load all expanded dataset files into the context store at version 0."""
    print("[LOADER] Pre-loading dataset...")

    # ── Categories (always from seed — they're already complete) ──
    cat_dir = DATASET_DIR / "categories"
    cat_count = 0
    if cat_dir.exists():
        for f in cat_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                slug = data.get("slug", f.stem)
                store.upsert("category", slug, 0, data)
                cat_count += 1
            except Exception as e:
                print(f"[LOADER] Error loading category {f.name}: {e}")
    print(f"[LOADER]   Categories: {cat_count}")

    # ── Merchants ──
    mer_count = _load_dir(store, "merchant", EXPANDED_DIR / "merchants", "merchant_id")
    if mer_count == 0:
        # Fallback to seed file
        mer_count = _load_seed_file(store, "merchant", DATASET_DIR / "merchants_seed.json", "merchants", "merchant_id")
    print(f"[LOADER]   Merchants: {mer_count}")

    # ── Customers ──
    cus_count = _load_dir(store, "customer", EXPANDED_DIR / "customers", "customer_id")
    if cus_count == 0:
        cus_count = _load_seed_file(store, "customer", DATASET_DIR / "customers_seed.json", "customers", "customer_id")
    print(f"[LOADER]   Customers: {cus_count}")

    # ── Triggers ──
    trg_count = _load_dir(store, "trigger", EXPANDED_DIR / "triggers", "id")
    if trg_count == 0:
        trg_count = _load_seed_file(store, "trigger", DATASET_DIR / "triggers_seed.json", "triggers", "id")
    print(f"[LOADER]   Triggers: {trg_count}")

    total = store.counts()
    print(f"[LOADER] Done. Totals: {total}")


def _load_dir(store: ContextStore, scope: str, dir_path: Path, id_key: str) -> int:
    """Load all JSON files from a directory."""
    count = 0
    if not dir_path.exists():
        return 0
    for f in dir_path.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            cid = data.get(id_key, f.stem)
            store.upsert(scope, cid, 0, data)
            count += 1
        except Exception as e:
            print(f"[LOADER] Error loading {f.name}: {e}")
    return count


def _load_seed_file(store: ContextStore, scope: str, path: Path, list_key: str, id_key: str) -> int:
    """Load from a single seed JSON file containing a list."""
    count = 0
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get(list_key, [])
        for item in items:
            cid = item.get(id_key, "")
            if cid:
                store.upsert(scope, cid, 0, item)
                count += 1
    except Exception as e:
        print(f"[LOADER] Error loading seed {path.name}: {e}")
    return count
