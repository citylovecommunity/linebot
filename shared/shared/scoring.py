from shared.database.models import Member, Line_Info
from sqlalchemy.sql.expression import exists


class UserProfileAdapter:
    """
    Wraps the raw JSON to provide clean, typed accessors.
    """

    def __init__(self, raw_data):
        self.raw = raw_data

    def _parse_int(self, key, default=0):
        try:
            val = self.raw.get(key, "")
            return int(val) if val and val.isdigit() else default
        except:
            return default

    def _parse_list(self, key):
        """Handles splitting by both ',' and '、'"""
        val = self.raw.get(key, "")
        if not val or val == "無" or val == '不限':
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


def get_eligible_matching_pool(session):
    """
    Returns a Query object containing ONLY users who have the 'Right to Enter'.
    Criteria:
    1. Member is active
    2. Web URL is provided
    3. Phone Number exists in LineInfo table
    """
    return session.query(Member).filter(
        # Rule 1: Active
        Member.is_active == True,

        # Rule 2: Has Web URL (Not Null and Not Empty)
        Member.user_info['會員介紹頁網址'].astext != None,
        Member.user_info['會員介紹頁網址'].astext != '',

        # Rule 3: Exists in Line Info (The Join Check)
        exists().where(Line_Info.phone_number == Member.phone_number)
    )


def calculate_match_score(me_adapter, candidate_adapter):
    """
    me_adapter: The UserProfileAdapter object for the person LOOKING
    candidate_adapter: The UserProfileAdapter object for the POTENTIAL MATCH
    """
    score = 60.0
    breakdown = {}

    # --- 1. RANKING (排約等級) ---
    # JSON Key: "排約等級一": "A"
    rank = candidate_adapter.raw.get("排約等級一", "B").strip().upper()

    if rank == "A":
        score += 40
        breakdown['rank_bonus'] = "+40 (Grade A)"
    elif rank == "C":
        score -= 30
        breakdown['rank_penalty'] = "-30 (Grade C)"
    # Grade B is neutral (no change)

    # --- 2. ATTRIBUTES (Skin, Appearance, etc.) ---
    # "Matches my preferences?"
    # (Assuming we have logic to parse '您期待認識的膚色' vs '會員本人的膚色')

    # Example: Skin Color Match
    # If I want "Fair" (白皙) and candidate is "Fair"
    desired_skin = me_adapter.raw.get("您期待認識的膚色", "")
    candidate_skin = candidate_adapter.raw.get("會員本人的膚色", "")

    if desired_skin != "不限" and desired_skin in candidate_skin:
        score += 10
        breakdown['skin_match'] = "+10"

    # --- 3. HOBBIES (Intersection) ---
    common = me_adapter.hobbies.intersection(candidate_adapter.hobbies)
    if common:
        points = min(len(common) * 3, 15)
        score += points
        breakdown['hobbies'] = f"+{points}"

    # --- 4. DEALBREAKERS (Safety Net) ---
    # Even if SQL filtered most, we double check here for complex ones
    # e.g. "Specific Job Types" or "Zodiac Signs" if you added those

    # 職業類別、飲食習慣、宗教信仰、約會地區
    if candidate_adapter.job in me_adapter.dealbreakers_job:
        score -= 20
        breakdown['job'] = f"-20"

    if candidate_adapter.diet in me_adapter.dealbreakers_diet:
        score -= 20
        breakdown['diet'] = f"-20"

    if candidate_adapter.religion in me_adapter.dealbreakers_religion:
        score -= 20
        breakdown['religion'] = f"-20"

    if len(candidate_adapter.datable_place) > 0 and len(candidate_adapter.datable_place) > 0\
            and len(candidate_adapter.datable_place.intersection(candidate_adapter.datable_place)) == 0:
        score -= 20
        breakdown['datable_place'] = f"-20"

    return score, breakdown
