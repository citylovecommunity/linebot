from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import cloudinary
import cloudinary.uploader
import requests
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from form_app.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
)

# ── Canvas & colour palette ───────────────────────────────────────────────────
# Matches the CityLove intro-card template: warm cream background with
# hand-drawn blue doodles / yellow sparkle accents (baked into DOODLES_PNG).
W, H = 900, 1600

BG        = (225, 212, 204)   # warm cream/taupe
PLACEHOLD = (238, 238, 238)   # photo placeholder fill
DARK      = ( 82,  78,  74)   # warm dark grey (name / values)
MUTED     = (150, 140, 131)   # warm muted grey (footer)
BIO_COLOR = ( 92,  86,  82)   # warm grey (bio text)

BOX_X0, BOX_Y0, BOX_X1, BOX_Y1 = 62, 154, 826, 853   # photo rectangle
BOX_W, BOX_H = BOX_X1 - BOX_X0, BOX_Y1 - BOX_Y0

LEFT_COL_X  = 197
RIGHT_COL_X = 509
ROW1_Y      = 912
ROW2_Y      = 1010
INTERESTS_Y = 1090
TEXT_RIGHT  = 820             # right-hand wrap boundary for interests/bio
LINE_H      = 42
BODY_MAX_Y  = 1500            # interests/bio stop here so they never hit the footer

FONTS_DIR   = Path(__file__).parent.parent / "static" / "fonts"
DOODLES_PNG = Path(__file__).parent.parent / "static" / "images" / "intro_card_doodles.png"


# ── Fonts & per-glyph fallback ────────────────────────────────────────────────
# NotoSansTC covers Traditional Chinese + Latin + CJK punctuation only. Member
# free-text answers (bio / interests) routinely contain emoji and Simplified-
# only hanzi, which have no glyph in that font and render as ".notdef" tofu
# boxes that visually collide. We resolve every character against a stack —
# Traditional → Simplified → monochrome emoji — and draw each maximal run with
# the first font that has the glyph. Characters covered by none (ZWJ joiners,
# variation selectors, skin-tone modifiers, unknown symbols) are dropped.

FONT_STACK = {
    "bold":    ("NotoSansTC-Bold.otf",    "NotoSansSC-Bold.otf",    "NotoEmoji-Regular.ttf"),
    "medium":  ("NotoSansTC-Medium.otf",  "NotoSansSC-Medium.otf",  "NotoEmoji-Regular.ttf"),
    "regular": ("NotoSansTC-Regular.otf", "NotoSansSC-Regular.otf", "NotoEmoji-Regular.ttf"),
}

_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
_cmap_cache: dict[str, set[int]] = {}


def _cmap(filename: str) -> set[int]:
    if filename not in _cmap_cache:
        _cmap_cache[filename] = set(TTFont(str(FONTS_DIR / filename)).getBestCmap())
    return _cmap_cache[filename]


def _load(filename: str, size: int) -> ImageFont.FreeTypeFont:
    key = (filename, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(str(FONTS_DIR / filename), size)
    return _font_cache[key]


def _resolve(ch: str, weight: str, size: int) -> ImageFont.FreeTypeFont | None:
    cp = ord(ch)
    for filename in FONT_STACK[weight]:
        if cp in _cmap(filename):
            return _load(filename, size)
    return None


def _runs(text: str, weight: str, size: int) -> list[tuple[str, ImageFont.FreeTypeFont]]:
    """Split text into consecutive same-font runs, dropping unrenderable chars."""
    runs: list[tuple[str, ImageFont.FreeTypeFont]] = []
    for ch in text:
        fnt = _resolve(ch, weight, size)
        if fnt is None:
            continue
        if runs and runs[-1][1] is fnt:
            runs[-1] = (runs[-1][0] + ch, fnt)
        else:
            runs.append((ch, fnt))
    return runs


def _measure(text: str, weight: str, size: int) -> float:
    return sum(f.getlength(s) for s, f in _runs(text, weight, size))


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, *,
          weight: str, size: int, fill, anchor: str = "la") -> None:
    """draw.text() replacement that renders mixed-font runs on one baseline."""
    x, y = xy
    ha, va = anchor[0], anchor[1]
    runs = _runs(text, weight, size)
    if not runs:
        return
    widths = [f.getlength(s) for s, f in runs]
    if ha == "m":
        x -= sum(widths) / 2
    elif ha == "r":
        x -= sum(widths)
    for (s, f), w in zip(runs, widths):
        draw.text((x, y), s, font=f, fill=fill, anchor="l" + va)
        x += w


def _cover_crop(img: Image.Image, w: int, h: int) -> Image.Image:
    img = img.convert("RGB")
    src_ratio, dst_ratio = img.width / img.height, w / h
    if src_ratio > dst_ratio:
        new_w = round(img.height * dst_ratio)
        x0 = (img.width - new_w) // 2
        img = img.crop((x0, 0, x0 + new_w, img.height))
    else:
        new_h = round(img.width / dst_ratio)
        y0 = (img.height - new_h) // 2
        img = img.crop((0, y0, img.width, y0 + new_h))
    return img.resize((w, h), Image.LANCZOS)


def _wrap(text: str, weight: str, size: int, max_w: int) -> list[str]:
    # Collapse embedded newlines/tabs/runs of spaces first — form answers
    # sometimes contain literal "\r\n". A raw newline passed into draw.text()
    # renders as its own multi-line block with tight internal spacing, which
    # then overlaps the next wrapped line since cursor_y only advances by one
    # LINE_H per _wrap() line.
    text = " ".join(text.split())
    lines, current = [], ""
    for ch in text:
        test = current + ch
        if _measure(test, weight, size) > max_w and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _birth(birthday: date | None) -> str:
    if not birthday:
        return "—"
    return f"{birthday.year}年{birthday.month}月"


# ── Main generator ────────────────────────────────────────────────────────────

def generate_intro_card(member) -> str:
    user_info = member.user_info or {}

    # 1. Base canvas + decorative doodle/sparkle overlay
    card = Image.new("RGB", (W, H), BG)
    doodles = Image.open(DOODLES_PNG).convert("RGBA")
    card.paste(doodles, (0, 0), mask=doodles)
    draw = ImageDraw.Draw(card)

    # 2. Name — display surname + 先生/小姐, not the full real name
    surname = (member.name or "")[0] if member.name else ""
    honorific = "先生" if member.gender == "M" else "小姐"
    display_name = f"{surname}{honorific}" if surname else honorific
    _text(draw, (W // 2, 102), display_name,
          weight="bold", size=50, fill=DARK, anchor="mm")

    # 3. Profile photo — flush rectangle, no ring/shadow (matches template)
    photo_url = member.photo_url or user_info.get("相片網址") or member.introduction_link
    pasted = False
    if photo_url:
        try:
            resp = requests.get(photo_url, timeout=12)
            resp.raise_for_status()
            photo = _cover_crop(Image.open(io.BytesIO(resp.content)), BOX_W, BOX_H)
            card.paste(photo, (BOX_X0, BOX_Y0))
            pasted = True
        except Exception:
            pasted = False
    if not pasted:
        draw.rectangle([BOX_X0, BOX_Y0, BOX_X1, BOX_Y1], fill=PLACEHOLD)
    draw = ImageDraw.Draw(card)

    # 4. Info fields — birth date / job, height / city (plain values, no captions)
    city_raw = user_info.get("可約會地區 (可複選)", "")
    city = city_raw.split(",")[0].strip() if city_raw else "—"

    _V = dict(fill=DARK, anchor="lm")
    _text(draw, (LEFT_COL_X,  ROW1_Y), _birth(member.birthday),                        weight="medium", size=34, **_V)
    _text(draw, (RIGHT_COL_X, ROW1_Y), user_info.get("會員之職業類別", "—"),           weight="medium", size=34, **_V)
    _text(draw, (LEFT_COL_X,  ROW2_Y), f"{member.height} cm" if member.height else "—", weight="medium", size=34, **_V)
    _text(draw, (RIGHT_COL_X, ROW2_Y), city,                                            weight="medium", size=34, **_V)

    # 5. Interests + 6. Bio — plain wrapped line(s), never drawn onto the footer
    cursor_y = INTERESTS_Y
    interests = [i.strip() for i in user_info.get("興趣", "").split(",") if i.strip()]
    if interests:
        for line in _wrap("、".join(interests), "medium", 28, TEXT_RIGHT - LEFT_COL_X):
            if cursor_y > BODY_MAX_Y:
                break
            _text(draw, (LEFT_COL_X, cursor_y), line, weight="medium", size=28, fill=DARK, anchor="la")
            cursor_y += LINE_H

    bio = user_info.get("簡單介紹自己", "").strip()
    if bio:
        bio_y = cursor_y + 40
        for line in _wrap(bio, "regular", 27, TEXT_RIGHT - LEFT_COL_X):
            if bio_y > BODY_MAX_Y:
                break
            _text(draw, (LEFT_COL_X, bio_y), line, weight="regular", size=27, fill=BIO_COLOR, anchor="la")
            bio_y += LINE_H

    # 7. Footer wordmark (sparkle mark is already baked into the doodle overlay)
    _text(draw, (W // 2, 1546), "CityLove 城遇",
          weight="medium", size=26, fill=MUTED, anchor="mm")

    # 8. Upload to Cloudinary
    buf = io.BytesIO()
    card.save(buf, format="JPEG", quality=92)
    buf.seek(0)

    result = cloudinary.uploader.upload(
        buf,
        folder="CityLove – Intro Cards.",
        public_id=str(member.id),
        resource_type="image",
        overwrite=True,
    )
    return result["secure_url"]
