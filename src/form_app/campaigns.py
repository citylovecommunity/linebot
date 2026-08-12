"""
Campaign config for the /join/<slug> flow.

New campaigns should be created via the admin panel (Admin → 操作 → 活動管理), which
stores them in the `campaign` DB table and lets the PM edit wording without a deploy.

CAMPAIGNS below is a legacy fallback: slugs launched before the DB-backed editor
existed. Keep it as-is for backward compatibility; don't add new entries here.
"""

from dataclasses import dataclass, field


@dataclass
class StaticCampaign:
    slug: str
    badge: str
    title: str          # can include \n for line breaks
    subtitle: str
    features: list      # list of {"icon": "...", "text": "..."}
    note: str = "填寫約 5 分鐘"
    cta: str = "開始填寫個人資料"


CAMPAIGNS: dict[str, StaticCampaign] = {
    "pickle_ball": StaticCampaign(
        slug="pickle_ball",
        badge="本季活動",
        title="一起相約打皮克球\n一起抽機票",
        subtitle="參加活動集章，即可獲得來回頭等艙機票資格",
        features=[
            {"icon": "✨", "text": "每週為你驚喜安排 1～3 位單身新朋友一起出發"},
            {"icon": "💬", "text": "可以一對一深度聊聊，也能多人一起出遊，內向外向都自在"},
            {"icon": "🔒", "text": "注重個人隱私，安全放心交友"},
            {"icon": "🎉", "text": "每季都有不同主題活動，認識新朋友更有趣"},
        ],
        note="填寫約 5 分鐘",
        cta="開始填寫個人資料",
    ),
    "story": StaticCampaign(
        slug="story",
        badge="本季活動",
        title="說故事大賽\n一起抽機票",
        subtitle="用 8 張故事卡，跟新朋友一起玩出最精彩的故事",
        features=[
            {"icon": "📖", "text": "每週隨機配對 1 位新朋友，一起出去用 8 張數位故事卡創作故事"},
            {"icon": "🎯", "text": "集滿 3 個故事即可獲得抽機票資格"},
            {"icon": "🔒", "text": "注重個人隱私，安全放心交友"},
            {"icon": "🎉", "text": "季末票選投票，抽出來回頭等艙機票"},
        ],
        note="填寫約 5 分鐘",
        cta="開始填寫個人資料",
    ),
    "dating": StaticCampaign(
        slug="dating",
        badge="本季活動",
        title="有趣約會\n一起抽機票",
        subtitle="每週幫你配對新朋友，一起腦力激盪做點瘋狂有趣的事",
        features=[
            {"icon": "🎲", "text": "每週隨機配對新朋友，一起腦力激盪想超有趣無理頭的事情做"},
            {"icon": "💡", "text": "每週提供隨機任務靈感，不知道要做什麼也沒關係"},
            {"icon": "🎯", "text": "累積 3 次有趣約會即可獲得抽機票資格"},
            {"icon": "🎉", "text": "季末票選投票，抽出來回頭等艙機票"},
        ],
        note="填寫約 5 分鐘",
        cta="開始填寫個人資料",
    ),
    "casual": StaticCampaign(
        slug="casual",
        badge="本季活動",
        title="輕鬆認識新朋友",
        subtitle="純粹認識人，城遇幫你配同齡人，自己約時間、自己決定怎麼玩",
        features=[
            {"icon": "👥", "text": "城遇依年齡幫你配對新朋友"},
            {"icon": "📅", "text": "自己約時間、自己決定怎麼玩，彈性自在"},
            {"icon": "🔒", "text": "注重個人隱私，安全放心交友"},
            {"icon": "✨", "text": "沒有任務壓力，單純認識新朋友"},
        ],
        note="填寫約 5 分鐘",
        cta="開始填寫個人資料",
    ),
    "default": StaticCampaign(
        slug="default",
        badge="CityLove 城遇",
        title="遇見志同道合的夥伴",
        subtitle="每週精心配對，讓緣分自然發生",
        features=[
            {"icon": "🎯", "text": "每週為你量身安排最合適的配對"},
            {"icon": "💬", "text": "一對一深度交流，輕鬆自在"},
            {"icon": "🔒", "text": "注重個人隱私，安全放心交友"},
            {"icon": "✨", "text": "每季都有不同主題活動，認識新朋友更有趣"},
        ],
    ),
}


def get_campaign(slug: str | None):
    """Return the campaign for the given slug: DB-backed (admin-created) first,
    then the legacy static fallback, then the default."""
    if slug:
        from form_app.database import get_db
        from form_app.models import Campaign

        db_campaign = get_db().query(Campaign).filter_by(slug=slug, is_active=True).first()
        if db_campaign:
            return db_campaign
        if slug in CAMPAIGNS:
            return CAMPAIGNS[slug]
    return CAMPAIGNS["default"]
