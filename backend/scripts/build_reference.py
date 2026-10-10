"""Regenerate app/data/{airports,airlines}.json from public datasets.

Sources (downloaded into memory, only filtered JSON is written to disk):
- OurAirports airports.csv (public domain): https://davidmegginson.github.io/ourairports-data/airports.csv
- OpenFlights airlines.dat (ODbL 1.0): https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat

Run from backend/:
    ./.venv/bin/python scripts/build_reference.py
"""

import csv
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
AIRLINES_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"

AIRPORT_TYPES = {"large_airport", "medium_airport", "small_airport"}
IATA_RE = re.compile(r"^[A-Z0-9]{3}$")
AIRLINE_IATA_RE = re.compile(r"^[A-Z0-9]{2}$")
USER_AGENT = "Azmark-reference-builder (+https://github.com/)"

# OpenFlights 数据更新时间较旧，部分航司已改名/被并入。这里维护字段覆盖，
# 保证重建数据后仍显示当前正确信息（IATA 代码不变）。
AIRLINE_OVERRIDES: dict[str, dict[str, str]] = {
    "TR": {"name": "Scoot"},  # 酷航（原 Tiger Airways，2012 年更名）
    "AZ": {"name": "ITA Airways", "icao": "ITY"},  # 意大利航空（原 Alitalia）
}

# 常用航司/机场中文名（数据层提供，前端按 locale 显示；未收录的回退英文）。
# 来源为公开通用译名；维护到这里，方便一键重建。
AIRLINE_ZH = {
    "CA": "中国国际航空",
    "MU": "中国东方航空",
    "CZ": "中国南方航空",
    "HU": "海南航空",
    "MF": "厦门航空",
    "3U": "四川航空",
    "ZH": "深圳航空",
    "SC": "山东航空",
    "HO": "吉祥航空",
    "9C": "春秋航空",
    "KN": "中国联合航空",
    "FM": "上海航空",
    "GS": "天津航空",
    "JD": "首都航空",
    "8L": "祥鹏航空",
    "PN": "西部航空",
    "EU": "成都航空",
    "KY": "昆明航空",
    "G5": "华夏航空",
    "BK": "奥凯航空",
    "CX": "国泰航空",
    "KA": "国泰港龙航空",
    "HX": "香港航空",
    "UO": "香港快运航空",
    "BR": "长荣航空",
    "CI": "中华航空",
    "AE": "华信航空",
    "FE": "远东航空",
    "B7": "立荣航空",
    "JL": "日本航空",
    "NH": "全日空",
    "GK": "捷星日本",
    "BC": "天马航空",
    "OZ": "韩亚航空",
    "KE": "大韩航空",
    "TW": "德威航空",
    "7C": "济州航空",
    "LJ": "真航空",
    "TG": "泰国国际航空",
    "FD": "泰国亚洲航空",
    "VZ": "泰越捷航空",
    "MH": "马来西亚航空",
    "AK": "亚洲航空",
    "D7": "亚洲航空X",
    "SQ": "新加坡航空",
    "TR": "酷航",
    "3K": "捷星亚洲",
    "BI": "文莱皇家航空",
    "PR": "菲律宾航空",
    "5J": "宿务太平洋航空",
    "VN": "越南航空",
    "BL": "越捷航空",
    "QF": "澳洲航空",
    "VA": "维珍澳大利亚航空",
    "JQ": "捷星航空",
    "NZ": "新西兰航空",
    "UA": "美国联合航空",
    "AA": "美国航空",
    "DL": "达美航空",
    "AS": "阿拉斯加航空",
    "HA": "夏威夷航空",
    "B6": "捷蓝航空",
    "WN": "西南航空",
    "AC": "加拿大航空",
    "WS": "西捷航空",
    "AM": "墨西哥航空",
    "AV": "哥伦比亚航空",
    "LA": "智利航空",
    "CM": "巴拿马航空",
    "TK": "土耳其航空",
    "LH": "汉莎航空",
    "OS": "奥地利航空",
    "LX": "瑞士国际航空",
    "BA": "英国航空",
    "VS": "维珍航空",
    "AF": "法国航空",
    "KL": "荷兰皇家航空",
    "AZ": "意大利航空",
    "IB": "西班牙航空",
    "AY": "芬兰航空",
    "SK": "北欧航空",
    "DY": "挪威航空",
    "U2": "易捷航空",
    "FR": "瑞安航空",
    "TP": "葡萄牙航空",
    "SN": "布鲁塞尔航空",
    "QR": "卡塔尔航空",
    "EK": "阿联酋航空",
    "EY": "阿提哈德航空",
    "GF": "海湾航空",
    "SV": "沙特阿拉伯航空",
    "KU": "科威特航空",
    "RJ": "约旦皇家航空",
    "ME": "中东航空",
    "MS": "埃及航空",
    "ET": "埃塞俄比亚航空",
    "KQ": "肯尼亚航空",
    "SA": "南非航空",
    "AT": "摩洛哥皇家航空",
    "SU": "俄罗斯航空",
    "S7": "西伯利亚航空",
    "A3": "爱琴海航空",
    "LO": "波兰航空",
    "OK": "捷克航空",
    "RO": "罗马尼亚航空",
    "AI": "印度航空",
    "6E": "靛蓝航空",
    "9W": "捷特航空",
    "UK": "维斯塔拉航空",
    "PK": "巴基斯坦航空",
    "UL": "斯里兰卡航空",
    "BG": "孟加拉航空",
    "WY": "阿曼航空",
    "IR": "伊朗航空",
    "LY": "以色列航空",
}

# 三大航空联盟成员（对应方案 #38 的联盟标注）。名单为常用主流成员，
# 以 IATA 码为键，方便 build_airlines() 反查补入 alliance 字段。
AIRLINE_ALLIANCES: dict[str, tuple[str, ...]] = {
    "star_alliance": (
        "A3",
        "AC",
        "AD",
        "AI",
        "AV",
        "BR",
        "CA",
        "CM",
        "ET",
        "LO",
        "LH",
        "LX",
        "MS",
        "NH",
        "NZ",
        "OS",
        "OU",
        "OZ",
        "SA",
        "SK",
        "SN",
        "SQ",
        "TA",
        "TH",
        "TK",
        "UA",
    ),
    "skyteam": (
        "AF",
        "AM",
        "AR",
        "CI",
        "CZ",
        "DL",
        "GA",
        "KE",
        "KL",
        "KQ",
        "ME",
        "MF",
        "MU",
        "RO",
        "SU",
        "SV",
        "VN",
    ),
    "oneworld": (
        "AA",
        "AS",
        "AY",
        "BA",
        "CX",
        "FI",
        "IB",
        "JL",
        "LA",
        "MH",
        "QF",
        "QR",
        "RJ",
    ),
}

# IATA -> (机场名中文, 城市中文)
AIRPORT_ZH = {
    "PEK": ("北京首都国际机场", "北京"),
    "PKX": ("北京大兴国际机场", "北京"),
    "PVG": ("上海浦东国际机场", "上海"),
    "SHA": ("上海虹桥国际机场", "上海"),
    "CAN": ("广州白云国际机场", "广州"),
    "SZX": ("深圳宝安国际机场", "深圳"),
    "HGH": ("杭州萧山国际机场", "杭州"),
    "NKG": ("南京禄口国际机场", "南京"),
    "WUH": ("武汉天河国际机场", "武汉"),
    "CKG": ("重庆江北国际机场", "重庆"),
    "CTU": ("成都双流国际机场", "成都"),
    "TFU": ("成都天府国际机场", "成都"),
    "KMG": ("昆明长水国际机场", "昆明"),
    "XIY": ("西安咸阳国际机场", "西安"),
    "TSN": ("天津滨海国际机场", "天津"),
    "HAK": ("海口美兰国际机场", "海口"),
    "SYX": ("三亚凤凰国际机场", "三亚"),
    "XMN": ("厦门高崎国际机场", "厦门"),
    "FOC": ("福州长乐国际机场", "福州"),
    "KWL": ("桂林两江国际机场", "桂林"),
    "CSX": ("长沙黄花国际机场", "长沙"),
    "ZUH": ("珠海金湾机场", "珠海"),
    "SHE": ("沈阳桃仙国际机场", "沈阳"),
    "DLC": ("大连周水子国际机场", "大连"),
    "TAO": ("青岛胶东国际机场", "青岛"),
    "WNZ": ("温州龙湾国际机场", "温州"),
    "NGB": ("宁波栎社国际机场", "宁波"),
    "LXA": ("拉萨贡嘎机场", "拉萨"),
    "URC": ("乌鲁木齐地窝堡国际机场", "乌鲁木齐"),
    "HET": ("呼和浩特白塔国际机场", "呼和浩特"),
    "TYN": ("太原武宿国际机场", "太原"),
    "SJW": ("石家庄正定国际机场", "石家庄"),
    "NNG": ("南宁吴圩国际机场", "南宁"),
    "YNT": ("烟台蓬莱国际机场", "烟台"),
    "HKG": ("香港国际机场", "香港"),
    "MFM": ("澳门国际机场", "澳门"),
    "TPE": ("台北桃园国际机场", "台北"),
    "TSA": ("台北松山机场", "台北"),
    "KHH": ("高雄国际机场", "高雄"),
    "RMQ": ("台中清泉岗机场", "台中"),
    "HND": ("东京羽田机场", "东京"),
    "NRT": ("东京成田国际机场", "东京"),
    "KIX": ("大阪关西国际机场", "大阪"),
    "ITM": ("大阪伊丹机场", "大阪"),
    "NGO": ("名古屋中部国际机场", "名古屋"),
    "CTS": ("札幌新千岁机场", "札幌"),
    "OKA": ("那霸机场", "冲绳"),
    "FUK": ("福冈机场", "福冈"),
    "ICN": ("首尔仁川国际机场", "首尔"),
    "GMP": ("首尔金浦国际机场", "首尔"),
    "PUS": ("釜山金海国际机场", "釜山"),
    "SIN": ("新加坡樟宜机场", "新加坡"),
    "KUL": ("吉隆坡国际机场", "吉隆坡"),
    "BKI": ("亚庇国际机场", "亚庇"),
    "PEN": ("槟城国际机场", "槟城"),
    "BKK": ("曼谷素万那普国际机场", "曼谷"),
    "DMK": ("曼谷廊曼国际机场", "曼谷"),
    "CNX": ("清迈国际机场", "清迈"),
    "HKT": ("普吉国际机场", "普吉"),
    "DAD": ("岘港国际机场", "岘港"),
    "SGN": ("新山一国际机场", "胡志明市"),
    "HAN": ("内排国际机场", "河内"),
    "MNL": ("尼诺伊·阿基诺国际机场", "马尼拉"),
    "DEL": ("英迪拉·甘地国际机场", "新德里"),
    "BOM": ("贾特拉帕蒂·希瓦吉国际机场", "孟买"),
    "BLR": ("班加罗尔国际机场", "班加罗尔"),
    "MAA": ("金奈国际机场", "金奈"),
    "DXB": ("迪拜国际机场", "迪拜"),
    "AUH": ("阿布扎比国际机场", "阿布扎比"),
    "DOH": ("哈马德国际机场", "多哈"),
    "JED": ("阿卜杜勒-阿齐兹国王国际机场", "吉达"),
    "RUH": ("哈立德国王国际机场", "利雅得"),
    "KWI": ("科威特国际机场", "科威特城"),
    "BAH": ("巴林国际机场", "麦纳麦"),
    "MCT": ("马斯喀特国际机场", "马斯喀特"),
    "IST": ("伊斯坦布尔机场", "伊斯坦布尔"),
    "SAW": ("萨比哈·格克琴机场", "伊斯坦布尔"),
    "LHR": ("希思罗机场", "伦敦"),
    "LGW": ("盖特威克机场", "伦敦"),
    "LTN": ("卢顿机场", "伦敦"),
    "STN": ("斯坦斯特德机场", "伦敦"),
    "CDG": ("巴黎戴高乐机场", "巴黎"),
    "ORY": ("巴黎奥利机场", "巴黎"),
    "FRA": ("法兰克福机场", "法兰克福"),
    "MUC": ("慕尼黑机场", "慕尼黑"),
    "ZRH": ("苏黎世机场", "苏黎世"),
    "GVA": ("日内瓦机场", "日内瓦"),
    "VIE": ("维也纳国际机场", "维也纳"),
    "AMS": ("史基浦机场", "阿姆斯特丹"),
    "BRU": ("布鲁塞尔机场", "布鲁塞尔"),
    "MAD": ("马德里巴拉哈斯机场", "马德里"),
    "BCN": ("巴塞罗那机场", "巴塞罗那"),
    "LIS": ("里斯本机场", "里斯本"),
    "FCO": ("菲乌米奇诺机场", "罗马"),
    "MXP": ("马尔彭萨机场", "米兰"),
    "VCE": ("马可·波罗机场", "威尼斯"),
    "HEL": ("赫尔辛基万塔机场", "赫尔辛基"),
    "ARN": ("斯德哥尔摩阿兰达机场", "斯德哥尔摩"),
    "OSL": ("奥斯陆加勒穆恩机场", "奥斯陆"),
    "CPH": ("哥本哈根凯斯楚普机场", "哥本哈根"),
    "DUB": ("都柏林机场", "都柏林"),
    "WAW": ("华沙肖邦机场", "华沙"),
    "PRG": ("布拉格瓦茨拉夫·哈维尔机场", "布拉格"),
    "BUD": ("布达佩斯李斯特·费伦茨机场", "布达佩斯"),
    "ATH": ("雅典国际机场", "雅典"),
    "SVO": ("谢列梅捷沃国际机场", "莫斯科"),
    "DME": ("多莫杰多沃机场", "莫斯科"),
    "TLV": ("本-古里安机场", "特拉维夫"),
    "CAI": ("开罗国际机场", "开罗"),
    "CPT": ("开普敦国际机场", "开普敦"),
    "JNB": ("奥利弗·坦博国际机场", "约翰内斯堡"),
    "NBO": ("乔莫·肯雅塔国际机场", "内罗毕"),
    "ADD": ("亚的斯亚贝巴博莱机场", "亚的斯亚贝巴"),
    "CMN": ("穆罕默德五世国际机场", "卡萨布兰卡"),
    "YYZ": ("多伦多皮尔逊国际机场", "多伦多"),
    "YVR": ("温哥华国际机场", "温哥华"),
    "YUL": ("蒙特利尔特鲁多机场", "蒙特利尔"),
    "JFK": ("约翰·肯尼迪国际机场", "纽约"),
    "EWR": ("纽瓦克自由国际机场", "纽约"),
    "LGA": ("拉瓜迪亚机场", "纽约"),
    "LAX": ("洛杉矶国际机场", "洛杉矶"),
    "SFO": ("旧金山国际机场", "旧金山"),
    "SEA": ("西雅图-塔科马国际机场", "西雅图"),
    "PDX": ("波特兰国际机场", "波特兰"),
    "PHX": ("菲尼克斯天港国际机场", "凤凰城"),
    "DEN": ("丹佛国际机场", "丹佛"),
    "DFW": ("达拉斯-沃斯堡国际机场", "达拉斯"),
    "IAH": ("乔治·布什洲际机场", "休斯顿"),
    "ATL": ("哈茨菲尔德-杰克逊机场", "亚特兰大"),
    "MIA": ("迈阿密国际机场", "迈阿密"),
    "ORD": ("奥黑尔国际机场", "芝加哥"),
    "MDW": ("芝加哥中途国际机场", "芝加哥"),
    "BOS": ("波士顿洛根国际机场", "波士顿"),
    "PHL": ("费城国际机场", "费城"),
    "IAD": ("杜勒斯国际机场", "华盛顿"),
    "DCA": ("罗纳德·里根国家机场", "华盛顿"),
    "MCO": ("奥兰多国际机场", "奥兰多"),
    "LAS": ("哈利·里德国际机场", "拉斯维加斯"),
    "SAN": ("圣地亚哥国际机场", "圣地亚哥"),
    "HNL": ("丹尼尔·井上国际机场", "檀香山"),
    "ANC": ("泰德·史蒂文斯国际机场", "安克雷奇"),
    "SYD": ("悉尼金斯福德·史密斯机场", "悉尼"),
    "MEL": ("墨尔本机场", "墨尔本"),
    "BNE": ("布里斯班机场", "布里斯班"),
    "PER": ("珀斯机场", "珀斯"),
    "ADL": ("阿德莱德机场", "阿德莱德"),
    "AKL": ("奥克兰机场", "奥克兰"),
    "CHC": ("基督城机场", "基督城"),
    "WLG": ("惠灵顿机场", "惠灵顿"),
}


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def build_airports() -> list[dict]:
    rows = csv.DictReader(io.StringIO(fetch(AIRPORTS_URL)))
    by_iata: dict[str, dict] = {}
    skipped_type = 0
    skipped_code = 0
    for row in rows:
        iata = (row.get("iata_code") or "").strip().upper()
        if not IATA_RE.match(iata):
            skipped_code += 1
            continue
        if row.get("type") not in AIRPORT_TYPES:
            skipped_type += 1
            continue
        if iata in by_iata:
            continue
        icao = (row.get("gps_code") or "").strip().upper()
        try:
            lat = float(row["latitude_deg"])
            lon = float(row["longitude_deg"])
        except (KeyError, ValueError):
            continue
        name_zh, city_zh = AIRPORT_ZH.get(iata, (None, None))
        by_iata[iata] = {
            "iata": iata,
            "icao": icao if re.match(r"^[A-Z0-9]{4}$", icao) else None,
            "name": (row.get("name") or "").strip(),
            "name_zh": name_zh,
            "city": clean(row.get("municipality")),
            "city_zh": city_zh,
            "country": clean(row.get("iso_country")),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
        }
    airports = sorted(by_iata.values(), key=lambda a: a["iata"])
    print(
        f"airports: {len(airports)} kept, {skipped_type} without scheduled-service type, "
        f"{skipped_code} without valid IATA"
    )
    return airports


def build_airlines() -> list[dict]:
    rows = csv.reader(io.StringIO(fetch(AIRLINES_URL)))
    by_iata: dict[str, dict] = {}
    for fields in rows:
        if len(fields) < 8:
            continue
        _id, name, _alias, iata, icao, _callsign, country, active = (
            field.strip() for field in fields[:8]
        )
        iata = iata.upper()
        if active != "Y" or not AIRLINE_IATA_RE.match(iata):
            continue
        if not name or name.startswith("(") or name.lower().startswith("unnamed"):
            continue
        if iata in by_iata:
            continue  # controlled duplicates: keep the first (primary) holder
        override = AIRLINE_OVERRIDES.get(iata, {})
        if override.get("name"):
            name = override["name"]
        icao = (override.get("icao") or icao).upper()
        by_iata[iata] = {
            "iata": iata,
            "icao": icao if re.match(r"^[A-Z0-9]{3}$", icao) else None,
            "name": name,
            "name_zh": AIRLINE_ZH.get(iata),
            "country": clean(country),
            "alliance": next(
                (key for key, codes in AIRLINE_ALLIANCES.items() if iata in codes),
                None,
            ),
        }
    airlines = sorted(by_iata.values(), key=lambda a: a["iata"])
    print(f"airlines: {len(airlines)} kept (active with IATA)")
    return airlines


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "airports.json": build_airports,
        "airlines.json": build_airlines,
    }
    for filename, builder in outputs.items():
        data = builder()
        path = DATA_DIR / filename
        path.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        print(
            f"wrote {path.relative_to(DATA_DIR.parent.parent)} ({path.stat().st_size} bytes, "
            f"{len(data)} entries)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
