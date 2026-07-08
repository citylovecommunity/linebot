from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import cloudinary
import cloudinary.uploader
import requests
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

FONTS_DIR   = Path(__file__).parent.parent / "static" / "fonts"
DOODLES_PNG = Path(__file__).parent.parent / "static" / "images" / "intro_card_doodles.png"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    names = {
        "bold":    "NotoSansTC-Bold.otf",
        "medium":  "NotoSansTC-Medium.otf",
        "regular": "NotoSansTC-Regular.otf",
    }
    return ImageFont.truetype(str(FONTS_DIR / names[weight]), size)


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


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines, current = [], ""
    for ch in text:
        test = current + ch
        if font.getbbox(test)[2] > max_w and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _age(birthday: date | None) -> str:
    if not birthday:
        return "—"
    today = date.today()
    years = today.year - birthday.year - (
        (today.month, today.day) < (birthday.month, birthday.day)
    )
    return f"{years}歲"


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
    draw.text((W // 2, 102), display_name,
              font=_font("bold", 50), fill=DARK, anchor="mm")

    # 3. Profile photo — flush rectangle, no ring/shadow (matches template)
    photo_url = user_info.get("相片網址") or member.introduction_link
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

    # 4. Info fields — age / job, height / city (plain values, no captions)
    city_raw = user_info.get("可約會地區 (可複選)", "")
    city = city_raw.split(",")[0].strip() if city_raw else "—"

    fn_value = _font("medium", 34)
    draw.text((LEFT_COL_X,  ROW1_Y), _age(member.birthday),               font=fn_value, fill=DARK, anchor="lm")
    draw.text((RIGHT_COL_X, ROW1_Y), user_info.get("會員之職業類別", "—"), font=fn_value, fill=DARK, anchor="lm")
    draw.text((LEFT_COL_X,  ROW2_Y), f"{member.height} cm" if member.height else "—", font=fn_value, fill=DARK, anchor="lm")
    draw.text((RIGHT_COL_X, ROW2_Y), city,                                font=fn_value, fill=DARK, anchor="lm")

    # 5. Interests — plain wrapped line(s)
    cursor_y = INTERESTS_Y
    interests = [i.strip() for i in user_info.get("興趣", "").split(",") if i.strip()]
    if interests:
        fn_interests = _font("medium", 28)
        lines = _wrap("、".join(interests), fn_interests, TEXT_RIGHT - LEFT_COL_X)
        for line in lines:
            draw.text((LEFT_COL_X, cursor_y), line, font=fn_interests, fill=DARK, anchor="la")
            cursor_y += LINE_H

    # 6. Bio — plain wrapped text
    bio = user_info.get("簡單介紹自己", "").strip()
    if bio:
        bio_y = cursor_y + 40
        fn_bio = _font("regular", 27)
        for line in _wrap(bio, fn_bio, TEXT_RIGHT - LEFT_COL_X):
            draw.text((LEFT_COL_X, bio_y), line, font=fn_bio, fill=BIO_COLOR, anchor="la")
            bio_y += LINE_H

    # 7. Footer wordmark (sparkle mark is already baked into the doodle overlay)
    draw.text((W // 2, 1546), "CityLove 城遇",
              font=_font("medium", 26), fill=MUTED, anchor="mm")

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
