"""Manually (re)seed the compliance knowledge base.

Run:
    python scripts/seed_rules.py                 # mock embeddings (free)
    EMBEDDER=openai OPENAI_API_KEY=... python scripts/seed_rules.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.embeddings import get_embedder  # noqa: E402
from app.knowledge import seed_rules  # noqa: E402

Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    n = seed_rules(db, get_embedder())
    print(f"seeded {n} rules" if n else "rules already present (no-op)")
finally:
    db.close()
