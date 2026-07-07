from __future__ import annotations

import io
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
W, H = 900, 1600

BG         = (249, 246, 241)   # warm cream
GRAD_TOP   = (255, 168,  72)   # warm amber
GRAD_BOT   = (210, 100,  25)   # burnt orange
WHITE      = (255, 255, 255)
DARK       = ( 35,  30,  25)   # warm near-black
MUTED      = (148, 135, 120)   # warm grey
ACCENT     = (115,  95,  75)   # warm brown (pills)
PILL_BG    = (240, 234, 224)   # warm cream
BIO_BG     = (242, 236, 226)   # warm cream
DIVIDER    = (215, 207, 196)   # warm divider
SHADOW     = (182, 172, 160)   # warm shadow

HEADER_H   = 530
PHOTO_D    = 340               # photo circle diameter
RING       = 8                 # white ring thickness around photo
OUTER_D    = PHOTO_D + RING * 2

FONTS_DIR = Path(__file__).parent.parent / "static" / "fonts"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    names = {
        "bold":    "NotoSansTC-Bold.otf",
        "medium":  "NotoSansTC-Medium.otf",
        "regular": "NotoSansTC-Regular.otf",
    }
    return ImageFont.truetype(str(FONTS_DIR / names[weight]), size)


def _gradient(draw: ImageDraw.ImageDraw, y0: int, y1: int) -> None:
    for y in range(y0, y1):
        t = (y - y0) / max(y1 - y0 - 1, 1)
        r = int(GRAD_TOP[0] + (GRAD_BOT[0] - GRAD_TOP[0]) * t)
        g = int(GRAD_TOP[1] + (GRAD_BOT[1] - GRAD_TOP[1]) * t)
        b = int(GRAD_TOP[2] + (GRAD_BOT[2] - GRAD_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def _circle_crop(img: Image.Image, size: int) -> Image.Image:
    img  = img.convert("RGBA")
    side = min(img.width, img.height)
    img  = img.crop((
        (img.width  - side) // 2,
        (img.height - side) // 2,
        (img.width  + side) // 2,
        (img.height + side) // 2,
    )).resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    img.putalpha(mask)
    return img


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


def _pill(draw: ImageDraw.ImageDraw, x: int, y: int, text: str,
          font: ImageFont.FreeTypeFont) -> int:
    bbox   = font.getbbox(text)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = 20, 10
    pw     = tw + px * 2
    ph     = th + py * 2
    draw.rounded_rectangle([x, y, x + pw, y + ph],
                            radius=ph // 2, fill=PILL_BG, outline=ACCENT, width=2)
    draw.text((x + px, y + py - bbox[1]), text, font=font, fill=ACCENT)
    return x + pw + 14


# ── Main generator ────────────────────────────────────────────────────────────

def generate_intro_card(member) -> str:
    user_info = member.user_info or {}

    # 1. Base canvas
    card = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(card)

    # 2. Gradient header
    _gradient(draw, 0, HEADER_H)

    # Texture layer
    texture = Image.new("RGBA", (W, HEADER_H), (0, 0, 0, 0))
    td = ImageDraw.Draw(texture)

    # Fine diagonal lines — linen-like weave
    for x in range(-HEADER_H, W + HEADER_H, 7):
        td.line([(x, 0), (x + HEADER_H, HEADER_H)], fill=(255, 255, 255, 9), width=1)

    # Soft highlight orb — top-right corner
    for i in range(18, 0, -1):
        a = int(20 * (i / 18) ** 2)
        r = int(200 * i / 18)
        td.ellipse([W - r, -r // 2, W + r // 2, r], fill=(255, 255, 255, a))

    # Soft secondary orb — bottom-left
    for i in range(12, 0, -1):
        a = int(14 * (i / 12) ** 2)
        r = int(160 * i / 12)
        td.ellipse([-r // 2, HEADER_H - r // 2, r, HEADER_H + r // 2],
                   fill=(255, 255, 255, a))

    # Diagonal shine sweep across left side
    td.polygon(
        [(0, 0), (int(W * 0.50), 0), (int(W * 0.22), HEADER_H), (0, HEADER_H)],
        fill=(255, 255, 255, 16),
    )

    header_region = card.crop((0, 0, W, HEADER_H)).convert("RGBA")
    header_region = Image.alpha_composite(header_region, texture)
    card.paste(header_region.convert("RGB"), (0, 0))
    draw = ImageDraw.Draw(card)

    # 3. Profile photo (centred, spanning header bottom)
    CX = W // 2
    CY = HEADER_H     # photo centre sits right at the header boundary

    # Shadow (offset downward, soft grey ellipse steps)
    for i in range(14, 0, -1):
        gray = int(SHADOW[0] + (BG[0] - SHADOW[0]) * (1 - i / 14))
        draw.ellipse([
            CX - OUTER_D // 2 - i + 5,
            CY - OUTER_D // 2 - i + 8,
            CX + OUTER_D // 2 + i + 5,
            CY + OUTER_D // 2 + i + 8,
        ], fill=(gray, gray - 4, gray - 2))

    # White ring
    draw.ellipse(
        [CX - OUTER_D // 2, CY - OUTER_D // 2,
         CX + OUTER_D // 2, CY + OUTER_D // 2],
        fill=WHITE,
    )

    # Photo itself
    photo_url = user_info.get("相片網址") or member.introduction_link
    if photo_url:
        try:
            resp  = requests.get(photo_url, timeout=12)
            resp.raise_for_status()
            photo = _circle_crop(Image.open(io.BytesIO(resp.content)), PHOTO_D)
            card.paste(photo, (CX - PHOTO_D // 2, CY - PHOTO_D // 2),
                       mask=photo.getchannel("A"))
        except Exception:
            draw.ellipse(
                [CX - PHOTO_D // 2, CY - PHOTO_D // 2,
                 CX + PHOTO_D // 2, CY + PHOTO_D // 2],
                fill=(210, 200, 205),
            )
    draw = ImageDraw.Draw(card)

    # 5. Name — display surname + 先生/小姐, not the full real name
    surname = (member.name or "")[0] if member.name else ""
    honorific = "先生" if member.gender == "M" else "小姐"
    display_name = f"{surname}{honorific}" if surname else honorific
    NAME_Y = CY + PHOTO_D // 2 + 80
    draw.text((W // 2, NAME_Y), display_name,
              font=_font("bold", 52), fill=DARK, anchor="mm")

    # 6. Divider
    DIV1_Y = NAME_Y + 58
    draw.line([(80, DIV1_Y), (W - 80, DIV1_Y)], fill=DIVIDER, width=1)

    # 7. Info grid  (出生年月 / 職業)  (身高 / 城市)
    birth = (f"{member.birthday.year}年{member.birthday.month}月"
             if member.birthday else "—")
    city_raw = user_info.get("可約會地區 (可複選)", "")
    city = city_raw.split(",")[0].strip() if city_raw else "—"

    rows = [
        [("出生年月", birth),               ("職業", user_info.get("會員之職業類別", "—"))],
        [("身高",     f"{member.height} cm" if member.height else "—"),
                                             ("城市", city)],
    ]

    fn_label = _font("regular", 22)
    fn_value = _font("medium",  31)
    ROW_H    = 110
    INFO_Y   = DIV1_Y + 48
    COL_X    = [90, 480]

    for row_i, row in enumerate(rows):
        for col_i, (label, value) in enumerate(row):
            y = INFO_Y + row_i * ROW_H
            x = COL_X[col_i]
            draw.text((x, y),      label, font=fn_label, fill=MUTED)
            draw.text((x, y + 28), value, font=fn_value, fill=DARK)

    # 8. Divider
    DIV2_Y = INFO_Y + len(rows) * ROW_H + 20
    draw.line([(80, DIV2_Y), (W - 80, DIV2_Y)], fill=DIVIDER, width=1)

    # 9. Interests pills
    interests = [i.strip() for i in user_info.get("興趣", "").split(",") if i.strip()]
    fn_pill   = _font("medium", 24)
    PIL_Y     = DIV2_Y + 48
    px        = 80
    for interest in interests:
        bbox = fn_pill.getbbox(interest)
        pw   = bbox[2] - bbox[0] + 40 + 14
        if px + pw > W - 80:
            px    = 80
            PIL_Y += 56
        px = _pill(draw, px, PIL_Y, interest, fn_pill)

    # 10. Bio card
    bio = user_info.get("簡單介紹自己", "").strip()
    BIO_Y = PIL_Y + 88
    if bio:
        fn_bio  = _font("regular", 27)
        lines   = _wrap(bio, fn_bio, W - 200)
        line_h  = 42
        bio_h   = len(lines) * line_h + 52
        draw.rounded_rectangle([80, BIO_Y, W - 80, BIO_Y + bio_h],
                                radius=16, fill=BIO_BG)
        for j, line in enumerate(lines):
            draw.text((80 + 28, BIO_Y + 26 + j * line_h), line,
                      font=fn_bio, fill=(95, 80, 88))
        BIO_Y += bio_h

    # 11. Footer
    draw.text((W // 2, H - 72), "CityLove 城遇",
              font=_font("medium", 28), fill=MUTED, anchor="mm")

    # 12. Upload to Cloudinary
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
