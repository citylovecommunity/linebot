"""
Create and register the LINE Rich Menu for City Love.

Run:
    uv run python scripts/setup_rich_menu.py               # set as default for ALL users
    uv run python scripts/setup_rich_menu.py --user-only   # link to LINE_TEST_USER_ID only
    uv run python scripts/setup_rich_menu.py --delete      # delete ALL rich menus
    APP_ENV=production uv run python scripts/setup_rich_menu.py
"""
import argparse
import io
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PIL import Image, ImageDraw, ImageFont
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessageAction,
    MessagingApi,
    MessagingApiBlob,
    RichMenuArea,
    RichMenuBounds,
    RichMenuRequest,
    RichMenuSize,
    URIAction,
)

from form_app.config import settings

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
W, H = 2500, 843          # half-height rich menu (LINE standard)
COLS, ROWS = 3, 2
CELL_W = W // COLS        # 833
CELL_H = H // ROWS        # 421

# ---------------------------------------------------------------------------
# Visual design
# ---------------------------------------------------------------------------
BG_LIGHT  = "#FFF0F5"    # lavender blush
BG_WHITE  = "#FFFFFF"
DIVIDER   = "#E8C8D4"
TEXT_DARK = "#4A1020"    # deep rose
ACCENT    = "#C0506A"    # mid rose

CELLS = [
    # row 0
    {"row": 0, "col": 0, "label": "綁定電話", "icon": "phone"},
    {"row": 0, "col": 1, "label": "我的配對", "icon": "people"},
    {"row": 0, "col": 2, "label": "任務提案", "icon": "calendar"},
    # row 1
    {"row": 1, "col": 0, "label": "修改偏好", "icon": "gear"},
    {"row": 1, "col": 1, "label": "個人主頁", "icon": "person"},
    {"row": 1, "col": 2, "label": "聯絡我們", "icon": "chat"},
]


def _try_font(paths: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Icon drawing helpers
# cx, cy = icon centre; s = half bounding-box size; bg = cell background color
# ---------------------------------------------------------------------------
def _draw_phone(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color: str) -> None:
    w, h = s * 0.55, s
    x0, y0 = cx - w / 2, cy - h / 2
    draw.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=s * 0.15, outline=color, width=9)
    draw.line([(x0 + s * 0.08, y0 + h * 0.77), (x0 + w - s * 0.08, y0 + h * 0.77)], fill=color, width=7)


def _draw_people(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color: str) -> None:
    for offset in (-s * 0.26, s * 0.26):
        ox = cx + offset
        hr = s * 0.16
        draw.ellipse([ox - hr, cy - s * 0.5 - hr, ox + hr, cy - s * 0.5 + hr], fill=color)
        bw = s * 0.38
        draw.rounded_rectangle([ox - bw / 2, cy - s * 0.25, ox + bw / 2, cy + s * 0.35],
                               radius=bw / 2, fill=color)


def _draw_calendar(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color: str) -> None:
    w, h = s * 0.88, s * 0.82
    x0, y0 = cx - w / 2, cy - h / 2
    draw.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=s * 0.08, outline=color, width=8)
    draw.rectangle([x0, y0, x0 + w, y0 + h * 0.3], fill=color)
    for tx in (x0 + w * 0.3, x0 + w * 0.7):
        draw.rounded_rectangle([tx - s * 0.05, y0 - s * 0.1, tx + s * 0.05, y0 + h * 0.15],
                               radius=s * 0.04, fill=color)
    r = s * 0.05
    for row in range(2):
        for col in range(3):
            dx = x0 + w * (0.2 + col * 0.3)
            dy = y0 + h * (0.52 + row * 0.27)
            draw.ellipse([dx - r, dy - r, dx + r, dy + r], fill=color)


def _draw_gear(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color: str, bg: str = BG_WHITE) -> None:
    teeth, outer_r, inner_r = 8, s * 0.46, s * 0.33
    pts = []
    for i in range(teeth * 4):
        angle = math.radians(i * 360 / (teeth * 4) - 90)
        r = outer_r if i % 4 < 2 else inner_r
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(pts, fill=color)
    hr = s * 0.17
    draw.ellipse([cx - hr, cy - hr, cx + hr, cy + hr], fill=bg)


def _draw_person(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color: str) -> None:
    hr = s * 0.2
    draw.ellipse([cx - hr, cy - s * 0.52 - hr, cx + hr, cy - s * 0.52 + hr], fill=color)
    bw = s * 0.55
    draw.rounded_rectangle([cx - bw / 2, cy - s * 0.22, cx + bw / 2, cy + s * 0.4],
                           radius=bw / 2, fill=color)


def _draw_chat(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color: str) -> None:
    w, h = s * 0.9, s * 0.65
    x0, y0 = cx - w / 2, cy - h / 2 - s * 0.08
    draw.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=s * 0.18, fill=color)
    tail = [(cx - s * 0.05, y0 + h - 2), (cx + s * 0.22, y0 + h - 2), (cx - s * 0.1, y0 + h + s * 0.25)]
    draw.polygon(tail, fill=color)
    lc = "#FFE0EC"
    for oy in (-s * 0.09, s * 0.09):
        draw.rounded_rectangle([x0 + s * 0.12, cy + oy - s * 0.04, x0 + w - s * 0.12, cy + oy + s * 0.04],
                               radius=s * 0.04, fill=lc)


def generate_menu_image() -> bytes:
    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    zh_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    label_font = _try_font(zh_paths, 68)

    icon_fns = {
        "phone":    _draw_phone,
        "people":   _draw_people,
        "calendar": _draw_calendar,
        "person":   _draw_person,
        "chat":     _draw_chat,
    }

    for cell in CELLS:
        r, c = cell["row"], cell["col"]
        x0, y0 = c * CELL_W, r * CELL_H
        cx, cy = x0 + CELL_W / 2, y0 + CELL_H / 2
        bg = BG_LIGHT if (r + c) % 2 == 0 else BG_WHITE

        draw.rectangle([x0, y0, x0 + CELL_W, y0 + CELL_H], fill=bg)

        icon = cell["icon"]
        if icon == "gear":
            _draw_gear(draw, cx, cy - 60, 115, ACCENT, bg=bg)
        elif icon in icon_fns:
            icon_fns[icon](draw, cx, cy - 60, 115, ACCENT)

        draw.text((cx, cy + 120), cell["label"], font=label_font, fill=TEXT_DARK, anchor="mm")

    for col in range(1, COLS):
        draw.line([(col * CELL_W, 0), (col * CELL_W, H)], fill=DIVIDER, width=4)
    draw.line([(0, CELL_H), (W, CELL_H)], fill=DIVIDER, width=4)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Rich menu definition
# ---------------------------------------------------------------------------
def build_rich_menu(app_url: str, liff_id: str | None) -> RichMenuRequest:
    bind_url = f"https://liff.line.me/{liff_id}" if liff_id else f"{app_url}/liff/bind"
    action_grid = [
        [
            URIAction(uri=bind_url,                label="綁定電話"),
            URIAction(uri=f"{app_url}/dashboard/", label="我的配對"),
            URIAction(uri=f"{app_url}/dashboard/", label="任務提案"),
        ],
        [
            MessageAction(text="修改偏好",          label="修改偏好"),
            MessageAction(text="個人主頁",          label="個人主頁"),
            MessageAction(text="聯絡客服",          label="聯絡我們"),
        ],
    ]

    areas = [
        RichMenuArea(
            bounds=RichMenuBounds(x=col * CELL_W, y=row * CELL_H, width=CELL_W, height=CELL_H),
            action=action_grid[row][col],
        )
        for row in range(ROWS)
        for col in range(COLS)
    ]

    return RichMenuRequest(
        size=RichMenuSize(width=W, height=H),
        selected=True,
        name="City Love Main Menu",
        chat_bar_text="選單",
        areas=areas,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Manage City Love LINE Rich Menu")
    parser.add_argument("--delete", action="store_true", help="Delete all existing rich menus and exit")
    parser.add_argument("--user-only", action="store_true",
                        help="Link to LINE_TEST_USER_ID only instead of setting as global default")
    args = parser.parse_args()

    import certifi
    configuration = Configuration(
        access_token=settings.LINE_CHANNEL_ACCESS_TOKEN,
        ssl_ca_cert=certifi.where(),
    )

    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        blob_api = MessagingApiBlob(api_client)

        existing = messaging_api.get_rich_menu_list()
        if existing.richmenus:
            print(f"Deleting {len(existing.richmenus)} existing rich menu(s)...")
            for menu in existing.richmenus:
                messaging_api.delete_rich_menu(menu.rich_menu_id)
                print(f"  Deleted: {menu.rich_menu_id}  ({menu.name})")
        else:
            print("No existing rich menus found.")

        if args.delete:
            print("Done (--delete mode).")
            return

        rich_menu = build_rich_menu(settings.APP_URL, settings.LIFF_ID)
        response = messaging_api.create_rich_menu(rich_menu)
        menu_id = response.rich_menu_id
        print(f"\nCreated rich menu: {menu_id}")

        print("Generating and uploading menu image...")
        image_bytes = generate_menu_image()
        blob_api.set_rich_menu_image(
            rich_menu_id=menu_id,
            body=image_bytes,
            _headers={"Content-Type": "image/jpeg"},
        )
        print(f"Uploaded image ({len(image_bytes) // 1024} KB)")

        if args.user_only:
            test_user_id = settings.LINE_TEST_USER_ID
            if not test_user_id:
                print("ERROR: LINE_TEST_USER_ID is not set in .env")
                return
            messaging_api.link_rich_menu_id_to_user(test_user_id, menu_id)
            print(f"Linked to test user {test_user_id} only (not set as global default).")
        else:
            messaging_api.set_default_rich_menu(menu_id)
            print("Set as default rich menu for all users.")

        print(f"\nDone. Rich menu ID: {menu_id}")


if __name__ == "__main__":
    main()
