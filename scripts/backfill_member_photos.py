"""Backfill Member.photo_url/photo_public_id from existing 會員介紹頁 data.

Precedence per member (never overwrites an existing photo_url):
  1. Already has photo_url -> skip.
  2. Has user_info['相片網址'] (raw face-cropped photo from /join upload) -> copy directly.
  3. Has introduction_link, and it's not a generated intro-card (which may have no
     real face, just a placeholder box) -> re-upload to Cloudinary and face-crop.
  4. Otherwise -> skip (no usable source).

Defaults to a dry run (no DB writes). Pass --apply to actually commit changes.
"""
import argparse

from cloudinary import CloudinaryImage

from form_app.config import settings
from form_app.database import get_session_factory
from form_app.models import Member
from form_app.services.photo import derive_face_cropped_photo

INTRO_CARD_MARKERS = ('Intro Cards', 'Intro%20Cards')


def _rebuild_thumb_url(public_id: str) -> str:
    """Rebuild a properly face-thumbnailed URL from an existing public_id, no re-upload needed."""
    return CloudinaryImage(public_id).build_url(
        width=400, height=400, crop='thumb', gravity='face',
        quality='auto', format='webp', flags='awebp',
        secure=True,
    )


def main(apply: bool) -> None:
    SessionFactory = get_session_factory(settings.DB)
    with SessionFactory() as db:
        members = db.query(Member).all()

        copied = 0
        derived = 0
        skipped_has_photo = 0
        skipped_placeholder_card = 0
        skipped_no_source = 0
        failed = []

        for member in members:
            if member.photo_url:
                skipped_has_photo += 1
                continue

            user_info = member.user_info or {}
            raw_photo = user_info.get('相片網址')
            raw_public_id = user_info.get('相片公開ID')

            if raw_photo:
                if raw_public_id:
                    # Rebuild with a proper face-thumb crop from the original upload -- free, no re-upload.
                    photo_url, public_id = _rebuild_thumb_url(raw_public_id), raw_public_id
                else:
                    photo_url, public_id = raw_photo, None
                copied += 1
                print(f"[copy]   member {member.id} ({member.name}) -> {photo_url}")
                if apply:
                    member.photo_url = photo_url
                    member.photo_public_id = public_id
                    db.commit()
                continue

            link = member.introduction_link
            if not link:
                skipped_no_source += 1
                continue

            if any(marker in link for marker in INTRO_CARD_MARKERS):
                skipped_placeholder_card += 1
                print(f"[skip]   member {member.id} ({member.name}) -- link is a generated intro card, may lack a real face")
                continue

            result = derive_face_cropped_photo(link)
            if result is None:
                failed.append((member.id, member.name, link))
                print(f"[FAILED] member {member.id} ({member.name}) -- could not derive from {link}")
                continue

            photo_url, public_id = result
            derived += 1
            print(f"[derive] member {member.id} ({member.name}) -> {photo_url}")
            if apply:
                member.photo_url = photo_url
                member.photo_public_id = public_id
                db.commit()

        print()
        print("=== Summary ===")
        print(f"mode: {'APPLY (committed)' if apply else 'DRY RUN (no writes)'}")
        print(f"total members:              {len(members)}")
        print(f"copied (already cropped):   {copied}")
        print(f"derived (face-cropped now): {derived}")
        print(f"skipped (already had photo):{skipped_has_photo}")
        print(f"skipped (placeholder card): {skipped_placeholder_card}")
        print(f"skipped (no source):        {skipped_no_source}")
        print(f"failed:                     {len(failed)}")
        for member_id, name, link in failed:
            print(f"  - {member_id} ({name}): {link}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Actually write changes (default: dry run)')
    args = parser.parse_args()
    main(apply=args.apply)
