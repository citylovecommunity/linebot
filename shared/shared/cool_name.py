import random

# 1. 個性與氣質 (Character & Vibe)
personality_adjectives = [
    "古靈精怪", "傲嬌", "佛系", "腹黑", "戲精",
    "溫潤如玉", "厭世", "軟萌", "硬派", "灑脫",
    "神經質", "天然呆", "高冷", "悶騷", "樂天派",
    "特立獨行", "與世無爭", "犀利", "ㄎㄧㄤ", "社恐"
]

# 2. 外觀與意境 (Appearance & Atmosphere)
aesthetic_adjectives = [
    "光怪陸離", "斑駁", "晶瑩剔透", "賽博朋克", "煙霧繚繞",
    "頹廢", "絢爛", "朦朧", "復古", "極簡",
    "油膩", "絲滑", "毛茸茸", "粗獷", "前衛",
    "老靈魂", "超現實", "夢幻", "陰森", "質感"
]

# 3. 狀態與感覺 (Status & Feeling)
feeling_adjectives = [
    "腦洞大開", "崩潰", "療癒", "尷尬", "熱血",
    "虛無", "酥麻", "暈船", "炸裂", "emo",
    "眼神死", "心累", "雀躍", "窒息", "違和",
    "魔性", "超派", "芭比Q", "Chill", "微醺"
]

cute_animals = [
    "水豚", "柯基", "小海豹", "兔兔", "企鵝",
    "小熊貓", "柴犬", "倉鼠", "龍貓", "獨角獸",
    "蜜蜂", "北極熊", "招財貓", "海獺", "文鳥"
]

# 2. 溫馨角色 (Lovely Roles)
# 讓人感到安心或神奇的角色
lovely_roles = [
    "小天使", "幸運星", "魔法少女", "探險家", "園丁",
    "甜點師", "守護神", "勇者", "太空人", "精靈",
    "嚮導", "發明家", "聖誕老人", "花仙子", "小幫手"
]

# 3. 療癒小物 & 美食 (Cozy Objects & Food)
# 看著就覺得舒服、甜甜的東西
cozy_objects = [
    "棉花糖", "舒芙蕾", "暖暖包", "抱枕", "泡泡",
    "彈珠汽水", "甜甜圈", "雲朵", "萬花筒", "任意門",
    "仙女棒", "布丁", "風鈴", "熱可可", "水晶球"
]

# 4. 正向概念 (Positive Vibes)
# 充滿希望與美好想像的詞
positive_abstract = [
    "美夢", "奇蹟", "靈感", "彩虹", "勇氣",
    "陽光", "魔法", "快樂", "腦洞", "緣分",
    "初心", "微風", "銀河", "寶藏", "旋律"
]

# 5. 全部合體 (Master List)
all_nouns = cute_animals + lovely_roles + cozy_objects
all_adjectives = personality_adjectives + \
    aesthetic_adjectives + feeling_adjectives + positive_abstract


def generate_funny_name():
    adj = random.choice(all_adjectives)
    noun = random.choice(all_nouns)
    combo = f"{adj}的{noun}"
    return combo
