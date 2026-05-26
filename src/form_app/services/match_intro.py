from form_app.services.scoring import UserProfileAdapter


def generate_match_intro(viewer, partner) -> str:
    """
    Return a 1–2 sentence personalised intro explaining why viewer and partner
    are a good match.  Pulls directly from user_info via UserProfileAdapter so
    the text references concrete shared values rather than abstract scores.
    """
    v = UserProfileAdapter.from_member(viewer)
    p = UserProfileAdapter.from_member(partner)

    bullets = []

    # Shared hobbies — most personal, show up to 2
    shared_hobbies = v.hobbies & p.hobbies
    if shared_hobbies:
        items = sorted(shared_hobbies)[:2]
        if len(items) == 1:
            bullets.append(f"你們都喜歡{items[0]}")
        else:
            bullets.append(f"你們都喜歡{items[0]}和{items[1]}")

    # Overlapping datable regions
    shared_regions = v.datable_place & p.datable_place
    if shared_regions:
        region = sorted(shared_regions)[0]
        bullets.append(f"都可以在{region}約會")

    # Same diet (skip generic "不限")
    if (v.diet and p.diet and v.diet == p.diet
            and v.diet.strip() not in ('不限', '無', '')):
        bullets.append(f"飲食習慣相同（{v.diet}）")

    # Same religion (skip generic values)
    if (v.religion and p.religion and v.religion == p.religion
            and v.religion.strip() not in ('無', '不限', '無宗教信仰', '')):
        bullets.append(f"信仰相同（{v.religion}）")

    # Partner's height fits viewer's preference
    if (v.pref_min_height and p.height
            and p.height >= v.pref_min_height
            and not any('身高' in b for b in bullets)):
        bullets.append("對方身高符合你的偏好")

    if not bullets:
        return "期待你們擦出火花！✨"

    # Build sentence: max 2 bullets joined with "，"
    sentence = "，".join(bullets[:2])
    return f"{sentence}！✨"
