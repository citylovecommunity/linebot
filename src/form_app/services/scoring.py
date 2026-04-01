from collections import defaultdict

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import exists

from form_app.models import Line_Info, Member, UserMatchScore

# Returned when a hard dealbreaker is triggered — ensures the pair is excluded
# by the score <= 0 check in generate_weekly_matches
HARD_EXCLUDE = -9999


class UserProfileAdapter:
    """
    Wraps the raw JSON to provide clean, typed accessors.
    """

    def __init__(self, raw_data):
        self.raw = raw_data

    @classmethod
    def from_member(cls, member: "Member"):
        """
        Creates an adapter that fills in sparse user_info (admin-created members)
        with values from the member's dedicated DB columns.
        """
        info = dict(member.user_info or {})
        # Height
        if member.height:
            info.setdefault('您的身高 (CM)', str(member.height))
        # Marital status
        if member.marital_status:
            info.setdefault('您目前的感情狀況', member.marital_status)
        # Birthday → birth year used by adapter
        if member.birthday:
            info.setdefault('您的出生年月日', member.birthday.strftime('%Y/%m/%d'))
        # Rank
        if member.rank:
            info.setdefault('排約等級一', member.rank)
        # Height preferences
        if member.pref_min_height:
            info.setdefault('您期待認識的對象最低身高', str(member.pref_min_height))
        if member.pref_max_height:
            info.setdefault('您期待認識的對象最高身高', str(member.pref_max_height))
        if member.pref_oldest_birth_year:
            info.setdefault('您期待認識的對象最大年紀', str(member.pref_oldest_birth_year))
        if member.pref_youngest_birth_year:
            info.setdefault('您期待認識的對象最小年紀', str(member.pref_youngest_birth_year))
        return cls(info)

    def _parse_int(self, key, default=0):
        try:
            val = self.raw.get(key, "")
            return int(val) if val and str(val).isdigit() else default
        except:
            return default

    def _parse_list(self, key):
        """Handles splitting by both ',' and '、'"""
        val = self.raw.get(key, "")
        if not val or val in ("無", "不限", "不設限"):
            return set()
        # Replace ideographic comma with standard comma, then split
        normalized = val.replace("、", ",").replace("，", ",")
        items = [x.strip() for x in normalized.split(",") if x.strip()]
        return set(items)

    @property
    def birth_year(self):
        # Format: "1993/6/1" -> 1993
        dob = self.raw.get("您的出生年月日", "")
        if dob and "/" in dob:
            return int(dob.split("/")[0])
        return 0

    @property
    def gender(self):
        # "F 女生" -> "F"
        val = self.raw.get("您的性別", "")
        return "F" if "F" in val else "M"

    @property
    def height(self):
        return self._parse_int("您的身高 (CM)")

    @property
    def diet(self):
        return self.raw.get("您的飲食習慣")

    @property
    def marital_status(self):
        return self.raw.get("您目前的感情狀況")

    @property
    def has_children(self):
        val = self.raw.get("您有無小孩需要扶養", "沒有")
        return bool(val and val.strip() not in ("沒有", "無", ""))

    @property
    def job(self):
        return self.raw.get("會員之職業類別")

    @property
    def religion(self):
        return self.raw.get('宗教信仰')

    @property
    def location_prefs(self):
        return self._parse_list("可約會地區 (可複選)")

    @property
    def hobbies(self):
        return self._parse_list("您的休閒興趣 (可複選)")

    @property
    def dealbreakers(self):
        return self._parse_list("您完全無法接受的對象條件 (可複選)")

    @property
    def dealbreakers_diet(self):
        return self._parse_list("不能接受的飲食習慣")

    @property
    def dealbreakers_job(self):
        return self._parse_list("無法接受之職業類別")

    @property
    def dealbreakers_religion(self):
        return self._parse_list("無法接受的宗教信仰")

    @property
    def datable_place(self):
        return self._parse_list("可約會地區 (可複選)")

    # --- Match Preferences ---

    @property
    def pref_min_height(self):
        return self._parse_int("您期待認識的對象最低身高", 0)

    @property
    def pref_max_height(self):
        return self._parse_int("您期待認識的對象最高身高", 250)

    @property
    def pref_oldest_birth_year(self):
        # Logic check: "最大年紀" value is "1982".
        # Someone born in 1982 is OLDER than someone born in 2000.
        return self._parse_int("您期待認識的對象最大年紀", 1900)

    @property
    def pref_youngest_birth_year(self):
        return self._parse_int("您期待認識的對象最小年紀", 2030)


def get_eligible_matching_pool(session: Session):
    """
    Returns a Query object containing ONLY users who have the 'Right to Enter'.
    Criteria:
    1. Member is active and not a test account
    2. Web URL is provided
    3. Phone Number exists in LineInfo table
    4. Membership is not expired (expiration_date is null OR >= today)
    5. Matching window: matching_start_date is null OR <= today
    6. Matching window: matching_end_date is null OR >= today
    """
    from datetime import date
    today = date.today()

    return session.query(Member).filter(
        Member.is_active == True,
        Member.is_test == False,

        Member.introduction_link != None,
        Member.introduction_link != '',

        exists().where(Line_Info.phone_number == Member.phone_number),

        # Rule 4: Not expired
        (Member.expiration_date == None) | (Member.expiration_date >= today),

        # Rule 5: Matching window has started
        (Member.matching_start_date == None) | (Member.matching_start_date <= today),

        # Rule 6: Matching window has not ended
        (Member.matching_end_date == None) | (Member.matching_end_date >= today),
    ).all()


def calculate_match_score(me_adapter, candidate_adapter):
    """
    me_adapter: The UserProfileAdapter object for the person LOOKING
    candidate_adapter: The UserProfileAdapter object for the POTENTIAL MATCH

    Returns (score, breakdown). A score of HARD_EXCLUDE means the pair must
    never be matched — the caller is expected to discard such pairs.
    """
    score = 80.0
    breakdown = {}

    # --- 1. HARD DEALBREAKERS (immediate exclusion) ---
    # These come from "您完全無法接受的對象條件" — the user literally said they
    # cannot accept these under any circumstances.
    my_hard_dealbreakers = me_adapter.dealbreakers

    if "離婚" in my_hard_dealbreakers and "離婚" in (candidate_adapter.marital_status or ""):
        return HARD_EXCLUDE, {'hard_dealbreaker': '離婚'}

    if "有小孩" in my_hard_dealbreakers and candidate_adapter.has_children:
        return HARD_EXCLUDE, {'hard_dealbreaker': '有小孩'}

    # "無法接受之職業類別" / "不能接受的飲食習慣" / "無法接受的宗教信仰"
    # are also labelled "cannot accept" — treat as hard exclusions
    if candidate_adapter.job and candidate_adapter.job in me_adapter.dealbreakers_job:
        return HARD_EXCLUDE, {'hard_dealbreaker': f'job:{candidate_adapter.job}'}

    if candidate_adapter.diet and candidate_adapter.diet in me_adapter.dealbreakers_diet:
        return HARD_EXCLUDE, {'hard_dealbreaker': f'diet:{candidate_adapter.diet}'}

    if candidate_adapter.religion and candidate_adapter.religion in me_adapter.dealbreakers_religion:
        return HARD_EXCLUDE, {'hard_dealbreaker': f'religion:{candidate_adapter.religion}'}

    # --- 2. AGE RANGE (hard — user specified a range they expect) ---
    oldest_ok = me_adapter.pref_oldest_birth_year   # e.g. 1985 → want someone born >= 1985
    youngest_ok = me_adapter.pref_youngest_birth_year  # e.g. 2000 → want someone born <= 2000
    cand_year = candidate_adapter.birth_year

    if cand_year and oldest_ok and cand_year < oldest_ok:
        return HARD_EXCLUDE, {'hard_dealbreaker': 'too_old'}

    if cand_year and youngest_ok and cand_year > youngest_ok:
        return HARD_EXCLUDE, {'hard_dealbreaker': 'too_young'}

    # --- 3. RANKING (排約等級) ---
    rank = candidate_adapter.raw.get("排約等級一", "B").strip().upper()

    if rank == "A":
        score += 20
        breakdown['rank_bonus'] = "+20 (Grade A)"
    elif rank == "C":
        score -= 20
        breakdown['rank_penalty'] = "-20 (Grade C)"

    # --- 4. ATTRIBUTES ---
    desired_skin = me_adapter.raw.get("您期待認識的膚色", "")
    candidate_skin = candidate_adapter.raw.get("會員本人的膚色", "")

    if desired_skin and desired_skin != "不限" and desired_skin in candidate_skin:
        score += 10
        breakdown['skin_match'] = "+10"

    # --- 5. HOBBIES (Intersection) ---
    common = me_adapter.hobbies.intersection(candidate_adapter.hobbies)
    if common:
        points = min(len(common) * 3, 15)
        score += points
        breakdown['hobbies'] = f"+{points}"

    # --- 6. HEIGHT (soft preference penalty) ---
    if me_adapter.pref_min_height and candidate_adapter.height and \
            candidate_adapter.height < me_adapter.pref_min_height:
        score -= 20
        breakdown['min_height'] = "-20"

    # --- 7. DATABLE REGIONS (soft penalty if zero overlap) ---
    if candidate_adapter.datable_place and me_adapter.datable_place and \
            len(candidate_adapter.datable_place.intersection(me_adapter.datable_place)) == 0:
        score -= 20
        breakdown['datable_place'] = "-20"

    return score, breakdown


def run_matching_score_optimized(active_users, session: Session):
    # --- STAGE 0: PRE-PROCESSING (Memory) ---
    users_by_gender = defaultdict(list)
    adapters_map = {}

    print(f"Pre-loading {len(active_users)} profiles...")

    for user in active_users:
        users_by_gender[user.gender].append(user)
        # Use from_member so DB columns fill in sparse user_info (admin-created members)
        adapters_map[user.id] = UserProfileAdapter.from_member(user)

    match_records = []

    # --- STAGE 1: PAIRING & SCORING ---
    for me in active_users:
        my_adapter = adapters_map[me.id]
        candidates = users_by_gender['F'] if me.gender == 'M' else users_by_gender['M']

        for candidate in candidates:
            if me.id == candidate.id:
                continue

            cand_adapter = adapters_map[candidate.id]
            score, breakdown = calculate_match_score(my_adapter, cand_adapter)

            match_records.append({
                "source_user_id": me.id,
                "target_user_id": candidate.id,
                "score": score,
                "breakdown": breakdown,
            })

    # --- STAGE 2: BATCH WRITING (Bulk Upsert) ---
    if match_records:
        print(f"Bulk upserting {len(match_records)} records...")

        chunk_size = 5000
        for i in range(0, len(match_records), chunk_size):
            chunk = match_records[i: i + chunk_size]

            stmt = pg_insert(UserMatchScore).values(chunk)
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=['source_user_id', 'target_user_id'],
                set_={
                    "score": stmt.excluded.score,
                    "breakdown": stmt.excluded.breakdown
                }
            )
            session.execute(upsert_stmt)

    print("Weekly matching complete.")
