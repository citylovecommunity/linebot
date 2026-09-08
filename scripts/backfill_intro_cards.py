"""
Regenerates member intro cards so previously-broken text renders correctly.

Older cards were drawn with NotoSansTC only, so emoji, ZWJ sequences and
Simplified-only hanzi in a member's bio/interests came out as overlapping
".notdef" tofu boxes. intro_card.generate_intro_card now falls back through
Traditional -> Simplified -> emoji fonts; this script re-runs it for members
who already have a generated card and rewrites the (version-bumped) Cloudinary
URL back onto the member.

Selection:
  * default  -- every member whose introduction_link points at the Cloudinary
                "Intro Cards" folder (i.e. an auto-generated card)
  * --ids 1,2,3  -- only these member ids (regenerates regardless of URL shape)

Custom / externally-hosted introduction_link values are left untouched unless
named explicitly with --ids.

Run with:
    uv run python scripts/backfill_intro_cards.py --dry-run
    uv run python scripts/backfill_intro_cards.py
    uv run python scripts/backfill_intro_cards.py --ids 1042,1057
    uv run python scripts/backfill_intro_cards.py --limit 50 --sleep 0.5
"""
import argparse
import time

from sqlalchemy import select

from form_app.config import settings
from form_app.database import get_session_factory
from form_app.models import Member
from form_app.services.intro_card import generate_intro_card

# Substring of the URL-encoded Cloudinary folder ("CityLove – Intro Cards.")
GENERATED_CARD_MARKER = "%intro%card%"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ids", help="comma-separated member ids to regenerate")
    p.add_argument("--limit", type=int, help="process at most N members")
    p.add_argument("--sleep", type=float, default=0.3,
                   help="seconds to wait between members (Cloudinary rate limit)")
    p.add_argument("--dry-run", action="store_true",
                   help="list the members that would be regenerated, do nothing")
    return p.parse_args()


def select_members(session, args):
    if args.ids:
        ids = [int(x) for x in args.ids.split(",") if x.strip()]
        rows = session.scalars(select(Member).where(Member.id.in_(ids))).all()
        found = {m.id for m in rows}
        for missing in sorted(set(ids) - found):
            print(f"  ! id {missing} not found")
        return rows

    return session.scalars(
        select(Member)
        .where(Member.introduction_link.ilike(GENERATED_CARD_MARKER))
        .order_by(Member.id)
    ).all()


def main():
    args = parse_args()
    SessionFactory = get_session_factory(settings.DB)

    with SessionFactory() as session:
        members = select_members(session, args)
        if args.limit:
            members = members[: args.limit]

        print(f"{len(members)} member(s) to regenerate.\n")
        if args.dry_run:
            for m in members:
                print(f"  [{m.id}] {m.name} -> {m.introduction_link}")
            print("\nDry run — nothing written.")
            return

        ok = failed = 0
        for m in members:
            try:
                new_url = generate_intro_card(m)
                m.introduction_link = new_url
                m.user_info = {**(m.user_info or {}), "會員介紹頁網址": new_url}
                session.commit()
                ok += 1
                print(f"  [{m.id}] {m.name}: OK")
            except Exception as e:  # keep going; one bad photo shouldn't stop the run
                session.rollback()
                failed += 1
                print(f"  [{m.id}] {m.name}: FAILED — {e}")
            time.sleep(args.sleep)

        print(f"\nDone. Regenerated {ok}, failed {failed}.")


if __name__ == "__main__":
    main()
