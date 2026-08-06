from form_app.services.scoring import UserProfileAdapter

_SKIP_VALUES = {'不限', '無', '無宗教信仰', ''}


def _shared_reasons(v: UserProfileAdapter, p: UserProfileAdapter) -> list[str]:
    """Collect up to 3 human-readable reasons the two profiles fit each other."""
    reasons = []

    shared_hobbies = v.hobbies & p.hobbies
    if shared_hobbies:
        items = sorted(shared_hobbies)[:2]
        if len(items) == 1:
            reasons.append(f"你們都喜歡{items[0]}")
        else:
            reasons.append(f"你們都喜歡{items[0]}和{items[1]}")

    shared_regions = v.datable_place & p.datable_place
    if shared_regions:
        reasons.append(f"都可以在{sorted(shared_regions)[0]}見面")

    if (v.diet and p.diet and v.diet == p.diet
            and v.diet.strip() not in _SKIP_VALUES):
        reasons.append(f"飲食習慣一致（{v.diet}）")

    if (v.religion and p.religion and v.religion == p.religion
            and v.religion.strip() not in _SKIP_VALUES):
        reasons.append(f"信仰相同（{v.religion}）")

    if (v.pref_min_height and p.height and p.height >= v.pref_min_height
            and not any('身高' in r for r in reasons)):
        reasons.append("顧問認為你們很合適")

    return reasons


def generate_match_intro(viewer, partner) -> str:
    """
    Short 1-sentence card subtitle used on the dashboard list and detail page.
    """
    reasons = _shared_reasons(
        UserProfileAdapter.from_member(viewer),
        UserProfileAdapter.from_member(partner),
    )
    if not reasons:
        return "期待你們擦出火花！✨"
    return "，".join(reasons[:2]) + "！✨"
