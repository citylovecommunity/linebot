
import re

from dataclasses import dataclass
from typing import List

import pandas as pd


@dataclass
class Grade:
    member_id: int
    grader_id: int
    big_add: List[str]
    add_pt: List[str]
    minus_pt: List[str]
    dead: List[str]
    member_info: pd.Series
    grader_info: pd.Series

    def __str__(self):
        return f"Grade(member_id={self.member_id}, grader_id={self.grader_id}, big_add={self.big_add}, add_pt={self.add_pt}, minus_pt={self.minus_pt}, dead={self.dead})"


def place_string_formatter(place_string):

    place_list = re.split(r'[,、]', place_string)
    if '不限' in place_list:
        place_list.remove('不限')

    return set(place_list)


def unbearable_alarm(sub_unbearable, obj_info):
    sub_unbearable_list = re.split(r'[,、]', sub_unbearable)

    # 壞習慣
    bad_habit_list = re.split(r'[,、]', obj_info["您是否有以下的特徵/嗜好 (可複選)"])
    if not set(bad_habit_list).isdisjoint(set(sub_unbearable_list)):
        return True

    # 小孩
    if '有小孩' in sub_unbearable_list and obj_info['您有無小孩需要扶養'] == '有小孩':
        return True

    # 離婚
    if '離婚' in sub_unbearable_list and obj_info['您目前的感情狀況'] == '離婚':
        return True

    # 全數通過，return false
    return False


def grading(subjective, objective):
    "create a grading object, which can be ordered."

    big_add = []
    add_pt = []
    minus_pt = []
    dead = []

    # 加50
    # 身高, 年紀命中, 體態

    # 加分一個加30
    # 膚色配對成功,  長相類型, 休閒興趣, 排約等級A

    # 扣分，一個扣50
    # 身高, 約會地區不合,  職業, 排約等級B

    # 死亡，一個扣100分
    # 飲食習慣, 宗教, 年紀不合, 對象條件, 排約等級C

    sub_info = subjective.user_info
    obj_info = objective.user_info

    if obj_info['排約等級一'] == 'A':
        add_pt.append('level')
    elif obj_info['排約等級一'] == 'B':
        minus_pt.append('level')
    elif obj_info['排約等級一'] == 'C':
        dead.append('level')

    # 膚色
    if obj_info["會員本人的膚色"] in sub_info['您期待認識的膚色']:
        add_pt.append('skin')

    # 身形體態
    if multi_choice_intersection(sub_info['您期待認識的身型體態'], obj_info["會員本人的身材樣貌"]):
        big_add.append('shape')

    # 長相
    if multi_choice_intersection(sub_info['您期待認識的長相類型'], obj_info["會員本人的長相類型"]):
        add_pt.append('appearance')

    # 休閒興趣
    if multi_choice_intersection(sub_info['您的休閒興趣 (可複選)'], obj_info["您的休閒興趣 (可複選)"]):
        add_pt.append('interest')

    # 身高
    if (float(obj_info["您的身高 (CM)"]) <= float(sub_info["您期待認識的對象最高身高"])
            and float(obj_info["您的身高 (CM)"]) >= float(sub_info["您期待認識的對象最低身高"])):
        big_add.append('height')
    else:
        minus_pt.append('height')

    # 年紀

    obj_year = int(obj_info["您的出生年月日"][:4])
    sub_year = int(sub_info["您的出生年月日"][:4])
    max_year = int(sub_info["您期待認識的對象最大年紀"])
    min_year = int(sub_info["您期待認識的對象最小年紀"])
    if max_year <= obj_year and obj_year <= min_year:
        big_add.append('year')
    elif abs(sub_year-obj_year) < 7:
        add_pt.append('year')
    else:
        dead.append('year')

    # 約會地區
    sub_places_str = sub_info['可約會地區 (可複選)']
    obj_places_str = obj_info['可約會地區 (可複選)']

    sub_places_set = place_string_formatter(sub_places_str)
    obj_places_set = place_string_formatter(obj_places_str)

    if (sub_places_str != '不限' and obj_places_str != '不限' and
            sub_places_set.isdisjoint(obj_places_set)):
        minus_pt.append('place')

    # 飲食習慣
    if obj_info['您的飲食習慣'] in sub_info['不能接受的飲食習慣']:
        dead.append('diet')

    # 職業
    if obj_info["會員之職業類別"] in sub_info["無法接受之職業類別"]:
        minus_pt.append('job')

    # 宗教
    if obj_info["宗教信仰"] in sub_info["無法接受的宗教信仰"]:
        dead.append('religion')

    # 對象條件
    if unbearable_alarm(sub_info['您完全無法接受的對象條件 (可複選)'], obj_info):
        dead.append('condition')

    return Grade(member_id=objective.id,
                 member_info=objective,
                 grader_info=subjective,
                 add_pt=add_pt,
                 minus_pt=minus_pt,
                 big_add=big_add,
                 dead=dead,
                 grader_id=subjective.id)


def grading_metric(grade: Grade):
    return len(grade.big_add) * 50 + len(grade.add_pt) * 30 - len(grade.minus_pt) * 50 - len(grade.dead) * 100


def get_member_grading_list(member, member_df, matching_table):
    # 非同性別、不出現在自己或別人的發送紀錄中
    blacklist = (matching_table['object_id'][matching_table['subject_id'] == member.id].to_list() +
                 matching_table['subject_id'][matching_table['object_id'] == member.id].to_list())

    df = member_df.query(
        """ gender != @member.gender and id not in @blacklist""")
    return df


def multi_choice_intersection(sub_str, obj_str):
    sub_list = re.split(r'[,、]', sub_str)
    obj_list = re.split(r'[,、]', obj_str)
    return not set(sub_list).isdisjoint(set(obj_list))


def find_best_match(subject_member, candidate_df, excluded_ids) -> Grade:
    """
    Given one user (subject) and a pool of candidates, returns the best Grade object.
    """
    # Filter candidates
    candidates = candidate_df[~candidate_df['id'].isin(excluded_ids)]
    candidates = candidates[candidates['id'] != subject_member['id']]

    all_grades = []
    for _, objective_member in candidates.iterrows():
        grade = grading(subject_member, objective_member)
        all_grades.append(grade)

    if not all_grades:
        return None

    return max(all_grades, key=grading_metric)


def pack_scoring(match: Grade):

    CITIES = ["伊斯坦堡", "莫斯科", "倫敦", "聖彼得堡", "柏林", "馬德里", "基輔", "羅馬", "巴黎", "巴庫", "明斯克", "維也納", "漢堡", "布加勒斯特", "華沙", "布達佩斯", "巴塞隆納", "慕尼黑", "哈爾科夫", "米蘭", "貝爾格勒", "布拉格", "喀山", "下諾夫哥羅德", "索菲亞", "布魯塞爾", "提比里斯", "薩馬拉", "伯明罕", "頓河畔羅斯托夫", "烏法", "科隆", "葉里溫", "沃羅涅日", "彼爾姆", "敖德薩", "伏爾加格勒", "第聶伯羅", "斯德哥爾摩", "那不勒斯", "克拉斯諾達爾", "頓涅茨克", "阿姆斯特丹", "都靈", "馬賽", "薩拉托夫", "札格雷布", "瓦倫西亞", "里茲", "克拉科夫", "美因河畔法蘭克福", "扎波羅熱", "利沃夫",
              "陶里亞蒂", "奧斯陸", "塞維利亞", "基希訥烏", "羅茲", "薩拉戈薩", "雅典", "巴勒摩", "赫爾辛基", "鹿特丹", "伊熱夫斯克", "弗羅茨瓦夫", "斯圖加特", "格拉斯哥", "哥本哈根", "烏里揚諾夫斯克", "里加", "杜塞道夫", "克里維里赫", "雅羅斯拉夫爾", "馬哈奇卡拉", "萊比錫", "多特蒙德", "謝菲爾德", "哥德堡", "埃森", "馬拉加", "熱那亞", "奧倫堡", "不萊梅", "維爾紐斯", "地拉那", "德勒斯登", "都柏林", "曼徹斯特", "海牙", "布拉福", "梁贊", "漢諾威", "波茲南", "卡馬河畔切爾內", "阿斯特拉罕", "安特衛普", "愛丁堡", "奔薩", "里昂", "紐倫堡", "基洛夫", "戈梅利", "史高比耶", "里斯本", "利佩茨克", "巴拉希哈",
              "紐約", "洛杉磯", "芝加哥", "休士頓", "鳳凰城", "費城", "聖安東尼奧", "聖地牙哥", "達拉斯", "聖荷西", "奧斯汀", "傑克孫維", "沃斯堡", "哥倫布", "印第安納波利斯", "夏洛特", "舊金山", "西雅圖", "丹佛", "華盛頓哥倫比亞特區", "納許維爾", "奧克拉荷馬市", "艾爾帕索", "波士頓", "波特蘭", "拉斯維加斯", "底特律", "曼菲斯", "路易維爾", "巴爾的摩", "密爾瓦基", "阿布奎基", "土桑", "佛雷斯諾", "沙加緬度", "堪薩斯市", "梅薩", "亞特蘭大", "奧馬哈", "科羅拉多斯普林斯", "羅里", "長灘", "維吉尼亞海灘", "邁阿密", "奧克蘭", "明尼亞波利斯", "土爾沙", "貝克斯菲爾德", "威奇托", "阿靈頓", "奧羅拉", "坦帕", "紐奧良", "克里夫蘭", "檀香山", "安那翰", "列克星敦", "史塔克頓",
              "聖體市", "亨德森", "里弗賽德", "紐華克", "聖保羅", "聖安娜", "辛辛那提", "爾灣", "奧蘭多", "匹茲堡", "聖路易", "格林斯伯勒", "澤西市", "安克拉治", "林肯", "普萊諾", "德罕", "水牛城", "錢德勒", "丘拉維斯塔", "托萊多", "麥迪遜", "吉爾伯特", "雷諾", "韋恩堡", "北拉斯維加斯", "聖彼德斯堡", "拉伯克", "歐林", "拉雷多", "溫斯頓-撒冷", "切薩皮克", "格蘭岱爾", "加蘭", "斯科茨代爾", "諾福克", "波夕", "佛利蒙", "斯波坎", "聖塔克拉利塔", "巴頓魯治", "里奇蒙", "海厄利亞", "聖貝納迪諾", "塔科馬", "莫德斯托", "亨茨維爾", "狄蒙", "揚克斯", "羅徹斯特", "莫雷諾谷", "費耶特維爾", "方塔納", "哥倫布", "伍斯特", "聖露西港", "小岩城", "奧古斯塔", "奧克斯納德", "伯明罕",
              "蒙哥馬利", "弗里斯科", "阿馬里洛", "鹽湖城", "大急流城", "亨廷頓比奇", "歐弗蘭帕克", "格倫代爾", "塔拉赫西", "大草原城", "麥金尼", "開普科勒爾", "蘇瀑", "皮歐立亞", "普洛威頓斯", "溫哥華", "諾克斯維爾", "阿克倫", "什里夫波特", "莫比爾", "布朗斯維爾", "紐波特紐斯", "羅德岱堡", "查塔努加", "坦佩", "奧羅拉", "聖塔羅莎", "尤金", "埃爾克格羅夫", "塞勒姆", "安大略", "卡瑞", "庫卡蒙格牧場", "歐申賽德", "蘭開斯特", "加登格羅夫", "彭布羅克派恩斯", "科林斯堡", "棕櫚谷", "春田市", "克拉克斯維爾", "薩利納斯", "海沃德", "帕特森", "亞歷山德里亞", "梅肯", "科洛納", "堪薩斯市", "萊克伍德", "春田市", "森尼韋爾", "傑克森", "基林", "好萊塢", "默弗里斯伯勒", "帕薩迪納",
              "柏衛", "波莫納", "埃斯孔迪多", "喬利埃特", "查爾斯頓", "梅斯基特", "內珀維爾", "羅克福德", "橋港", "錫拉丘茲", "薩凡納", "羅斯維爾", "托倫斯", "富勒頓", "瑟普賴斯", "麥卡倫", "桑頓", "維塞利亞", "奧拉西", "蓋恩斯維爾", "西瓦利城", "橙市", "登頓", "沃倫", "帕薩迪納", "韋科", "錫達拉皮茲", "代頓", "伊莉莎白", "漢普頓", "哥倫比亞", "肯特", "史丹佛", "萊克伍德鎮", "維克多維爾", "米拉馬爾", "科勒爾斯普林斯", "史特靈海茨", "紐哈芬", "卡羅爾頓", "密德蘭", "諾曼", "聖塔克拉拉", "雅典", "千橡市", "托彼卡", "西米谷", "哥倫比亞", "瓦列霍", "法哥", "阿倫敦", "皮爾蘭", "康科德", "阿比林", "阿瓦達", "柏克萊", "安娜堡", "獨立城", "羅徹斯特", "拉法葉", "哈特福", "大學城",
              "克洛維斯", "費爾菲爾德", "棕櫚灣", "理查森", "朗德羅克", "劍橋", "梅里迪恩", "西棕櫚灘", "埃文斯維爾", "清水", "比靈斯", "西喬丹", "里奇蒙", "威斯敏斯特", "曼徹斯特", "洛厄爾", "威明頓", "安條克", "博蒙特", "普若佛", "北查爾斯頓", "埃爾金", "卡爾斯巴德", "敖德薩", "沃特伯里", "春田市", "利格城", "唐尼", "格雷舍姆", "海波因特", "斷箭城", "皮歐立亞", "蘭辛", "萊克蘭", "龐帕諾比奇", "科斯塔梅薩", "普韋布洛", "劉易斯維爾", "邁阿密加登斯", "拉斯克魯塞斯", "舒格蘭", "穆列塔", "文圖拉", "埃弗里特", "特曼庫拉", "迪爾伯恩", "聖瑪麗亞", "西科維納", "艾爾蒙地", "格里利", "斯帕克斯", "森特尼爾", "波德", "桑迪斯普林斯", "英格爾伍德", "愛迪生", "南富爾頓", "綠灣", "伯班克",
              "倫頓", "希爾斯伯勒", "埃爾卡洪", "泰勒", "戴維", "聖馬刁", "布羅克頓", "康科德", "朱魯帕谷", "戴利城", "艾倫", "里約蘭町", "里亞托", "伍德布里奇", "南本德", "斯波坎谷", "諾沃克", "門尼菲", "瓦卡維爾", "威奇托福爾斯", "達文波特", "昆西", "奇科", "林恩", "利斯薩米特", "新貝德福德", "費德勒爾韋", "柯林頓鎮", "愛丁堡", "楠帕", "羅阿諾克"]

    import random
    import secrets
    match_data = {
        "subject_id": match.grader_id,
        "object_id": match.member_id,
        'grading_metric': grading_metric(match),
        'obj_grading_metric': grading_metric(grading(match.member_info, match.grader_info)),
        'current_state': "invitation_sending",
        'city': random.choice(CITIES),
        "access_token": secrets.token_urlsafe(16)
    }
    return match_data
