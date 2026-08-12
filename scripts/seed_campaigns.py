"""
One-off: copy the legacy hardcoded campaigns (form_app/campaigns.py CAMPAIGNS dict)
into the DB-backed `campaign` table so they show up in Admin -> 活動管理 and become
PM-editable. Safe to re-run: skips slugs that already exist in the DB.
"""
from form_app.campaigns import CAMPAIGNS
from form_app.config import settings
from form_app.database import get_session_factory
from form_app.models import Campaign

SessionFactory = get_session_factory(settings.DB)

with SessionFactory() as db:
    for slug, static in CAMPAIGNS.items():
        if db.query(Campaign).filter_by(slug=slug).first():
            print(f"skip (already exists): {slug}")
            continue
        db.add(Campaign(
            slug=static.slug,
            badge=static.badge,
            title=static.title,
            subtitle=static.subtitle,
            features=static.features,
            note=static.note,
            cta=static.cta,
        ))
        print(f"added: {slug}")
    db.commit()
