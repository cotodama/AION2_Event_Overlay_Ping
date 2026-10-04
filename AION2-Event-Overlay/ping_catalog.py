"""Existing user endpoint map. Range candidates are NOT a verified world-to-IP map."""
import ipaddress
DEFAULT_PORT=13328
LOGIN_PORT=13700

REGION_ORDER = [
    "KR Server",
    "TW Server",
    "NA West",
    "NA East",
    "South America",
    "Central Europe",
    "Japan",
]

SERVER_NAME_PAIRS = [
    (("Siel", "SIE", "シエル"), ("Israphel", "ISR", "イズラフェル")),
    (("Nezekan", "NEZ", "ネザカン"), ("Zikel", "ZIK", "ジケル")),
    (("Vaizel", "VAI", "バイゼル"), ("Triniel", "TRI", "トリニエル")),
    (("Kaisinel", "KAI", "カイジネル"), ("Lumiel", "LUM", "ルミエル")),
    (("Yustiel", "YUS", "ユスティエル"), ("Marchutan", "MAR", "マルクタン")),
    (("Ariel", "ARI", "アリエル"), ("Azphel", "AZP", "アスフェル")),
    (("Fregion", "FRE", "フレギオン"), ("Ereshkigal", "ERE", "エレシュキガル")),
    (("Meslamtaeda", "MES", "メスラムタエダ"), ("Beritra", "BER", "ベリトラ")),
    (("Hithanya", "HIT", "ヒタニャ"), ("Nemon", "NEM", "ネモン")),
    (("Nania", "NAN", "ナニア"), ("Hadala", "HAD", "ハダラ")),
    (("Tahavatha", "TAH", "タハバタ"), ("Ludra", "LUD", "ルドラ")),
    (("Luteros", "LUT", "ルテロス"), ("Ulgorn", "ULG", "ウルゴルン")),
    (("Phernos", "PHE", "フェルノス"), ("Munin", "MUN", "ムニン")),
    (("Daminu", "DAM", "ダミヌ"), ("Odar", "ODA", "オダル")),
    (("Kasaka", "KAS", "カサカ"), ("Zemurru", "ZEM", "ゼムール")),
    (("Bakarma", "BAK", "バカルマ"), ("Kromede", "KRO", "クロメデ")),
    (("Tsenka", "TSE", "ツェンカ"), ("Quai", "QUA", "クァイ")),
    (("Kochi", "KOC", "コチ"), ("Baba", "BAB", "ババ")),
    (("Ishtar", "ISH", "イシュタル"), ("Fafnir", "FAF", "ファフニール")),
    (("Tiamat", "TIA", "ティアマト"), ("Indnath", "IND", "インドナト")),
    (("Poeta", "POE", "ポエタ"), ("Ishalgen", "ISH", "イシュハルゲン")),
    (("Lamuatan", "LAM", "ラムアタン"), ("Heladrir", "HEL", "ヘラドリル")),
    (("Nathara", "NAT", "ナタラ"), ("Agnita", "AGN", "アグニタ")),
    (("Talisra", "TAL", "タリスラ"), ("Atiel", "ATI", "アティエル")),
    (("Zumion", "ZUM", "ズミオン"), ("Valdemar", "VA1", "ヴァルデマー")),
    (("Nahid", "NAH", "ナヒド"), ("Lagta", "LAG", "ラグタ")),
    (("Asahr", "ASA", "アサール"), ("Gerod", "GER", "ゲロド")),
    (("Caelid", "CAE", "カエリド"), ("Urd", "URD", "ウルド")),
    (("Laveis", "LAV", "ラヴェイス"), ("Ecco", "ECC", "エッコ")),
    (("Perion", "PER", "ペリオン"), ("Giselle", "GIS", "ジゼル")),
    (("Dramata", "DRA", "ドラマタ"), ("Kashapa", "KA1", "カシャパ")),
    (("Reda", "RED", "レダ"), ("Stof", "STO", "ストフ")),
    (("Auldor", "AUL", "オルドール"), ("Berk", "BE1", "ベルク")),
    (("Vakron", "VAK", "ヴァクロン"), ("Nuakum", "NUA", "ヌアクム")),
    (("Narun", "NAR", "ナルン"), ("Grisilla", "GRI", "グリシラ")),
    (("Gartua", "GAR", "ガルトゥア"), ("Santras", "SAN", "サントラス")),
    (("Chloris", "CHL", "クロリス"), ("Reuben", "REU", "ルーベン")),
    (("Ione", "ION", "イオネ"), ("Hugo", "HUG", "ヒューゴ")),
    (("Teina", "TEI", "テイナ"), ("Kraki", "KRA", "クラキ")),
    (("Dymones", "DYM", "ディモネス"), ("Hystan", "HYS", "ヒスタン")),
    (("Bargott", "BAR", "バルゴット"), ("Rathman", "RAT", "ラスマン")),
    (("Atheron", "ATH", "アセロン"), ("Sigebert", "SIG", "シゲベルト")),
    (("Lutilis", "LU1", "ルティリス"), ("Nazmun", "NAZ", "ナズムン")),
    (("Siliator", "SIL", "シリアトル"), ("Gelcos", "GEL", "ゲルコス")),
    (("Idris", "IDR", "イドリス"), ("Paton", "PAT", "パトン")),
    (("Satia", "SAT", "サティア"), ("Pelleir", "PEL", "ペレイル")),
    (("Estian", "EST", "エスティアン"), ("Elvida", "ELV", "エルヴィダ")),
    (("Rahu", "RAH", "ラーフ"), ("Ketu", "KET", "ケトゥ")),
    (("Rhanman", "RHA", "ランマン"), ("Pydeon", "PYD", "パイデオン")),
    (("Hebran", "HEB", "ヘブラン"), ("Notun", "NOT", "ノトゥン")),
    (("Urahum", "URA", "ウラフム"), ("Murute", "MUR", "ムルテ")),
    (("Lakshmi", "LAK", "ラクシュミ"), ("Rotan", "ROT", "ロタン")),
    (("Thamon", "THA", "タモン"), ("Kwapo", "KWA", "クワポ")),
    (("Tiere", "TIE", "ティエレ"), ("Duanka", "DUA", "ドゥアンカ")),
    (("Duduri", "DUD", "ドゥドゥリ"), ("Brok", "BRO", "ブロク")),
    (("Derkos", "DER", "デルコス"), ("Valter", "VAL", "ヴァルター")),
    (("Dundu", "DUN", "ドゥンドゥ"), ("Purakhi", "PUR", "プラキ")),
    (("Holyaul", "HOL", "ホリヤウル"), ("Ignus", "IGN", "イグナス")),
]

def build_server_catalog():
    catalog = []
    for elyos, asmo in SERVER_NAME_PAIRS:
        catalog.append({"name": elyos[0], "code": elyos[1], "jp": elyos[2], "faction": "Elyos"})
        catalog.append({"name": asmo[0], "code": asmo[1], "jp": asmo[2], "faction": "Asmodians"})
    return catalog

SERVER_CATALOG = build_server_catalog()

CATALOG_BY_NAME = {item["name"].casefold(): item for item in SERVER_CATALOG}

def server_entry(region, faction, name, host, port=DEFAULT_PORT):
    catalog_item = CATALOG_BY_NAME.get(name.casefold(), {})
    return {
        "id": f"{region}:{faction}:{name}",
        "faction": faction,
        "name": name,
        "code": catalog_item.get("code", ""),
        "jp": catalog_item.get("jp", ""),
        "host": host,
        "port": int(port),
    }

def build_default_profiles():
    kr_elyos = [
        ("Siel", "206.127.156.141"), ("Nezekan", "206.127.156.142"),
        ("Vaizel", "206.127.156.143"), ("Kaisinel", "206.127.156.144"),
        ("Yustiel", "206.127.156.145"), ("Ariel", "206.127.156.146"),
        ("Fregion", "206.127.156.147"), ("Meslamtaeda", "206.127.156.148"),
        ("Hithanya", "206.127.156.149"), ("Nania", "206.127.156.150"),
        ("Tahavatha", "206.127.156.151"), ("Luteros", "206.127.156.152"),
        ("Phernos", "206.127.156.153"), ("Daminu", "206.127.156.154"),
        ("Kasaka", "206.127.156.155"), ("Bakarma", "206.127.156.156"),
        ("Tsenka", "206.127.156.157"), ("Kochi", "206.127.156.158"),
        ("Ishtar", "206.127.156.159"), ("Tiamat", "206.127.156.160"),
        ("Poeta", "206.127.156.161"),
    ]
    kr_asmo = [
        ("Israphel", "206.127.156.101"), ("Zikel", "206.127.156.102"),
        ("Triniel", "206.127.156.103"), ("Lumiel", "206.127.156.104"),
        ("Marchutan", "206.127.156.105"), ("Azphel", "206.127.156.106"),
        ("Ereshkigal", "206.127.156.107"), ("Beritra", "206.127.156.108"),
        ("Nemon", "206.127.156.109"), ("Hadala", "206.127.156.110"),
        ("Ludra", "206.127.156.111"), ("Ulgorn", "206.127.156.112"),
        ("Munin", "206.127.156.113"), ("Odar", "206.127.156.114"),
        ("Zemurru", "206.127.156.115"), ("Kromede", "206.127.156.116"),
        ("Quai", "206.127.156.117"), ("Baba", "206.127.156.118"),
        ("Fafnir", "206.127.156.119"), ("Indnath", "206.127.156.120"),
        ("Ishalgen", "206.127.156.121"),
    ]
    tw_elyos = [
        ("Vaizel", "210.242.123.130"), ("Kaisinel", "210.242.123.131"),
        ("Yustiel", "210.242.123.132"), ("Ariel", "210.242.123.133"),
        ("Fregion", "210.242.123.134"), ("Meslamtaeda", "210.242.123.135"),
        ("Hithanya", "210.242.123.136"), ("Nania", "210.242.123.137"),
        ("Tahavatha", "210.242.123.138"), ("Luteros", "210.242.123.139"),
        ("Phernos", "210.242.123.140"), ("Daminu", "210.242.123.141"),
        ("Kasaka", "210.242.123.142"), ("Bakarma", "210.242.123.143"),
        ("Tsenka", "210.242.123.144"), ("Kochi", "210.242.123.146"),
    ]
    tw_asmo = [
        ("Lumiel", "210.242.123.172"), ("Marchutan", "210.242.123.173"),
        ("Azphel", "210.242.123.174"), ("Ereshkigal", "210.242.123.175"),
        ("Beritra", "210.242.123.176"), ("Nemon", "210.242.123.177"),
        ("Hadala", "210.242.123.178"), ("Ludra", "210.242.123.179"),
        ("Ulgorn", "210.242.123.180"), ("Munin", "210.242.123.181"),
        ("Odar", "210.242.123.182"), ("Zemurru", "210.242.123.183"),
        ("Kromede", "210.242.123.184"), ("Quai", "210.242.123.185"),
        ("Baba", "210.242.123.186"),
    ]

    profiles = {region: {"default_port": DEFAULT_PORT, "servers": []} for region in REGION_ORDER}
    for name, host in kr_elyos:
        profiles["KR Server"]["servers"].append(server_entry("KR Server", "Elyos", name, host))
    for name, host in kr_asmo:
        profiles["KR Server"]["servers"].append(server_entry("KR Server", "Asmodians", name, host))
    profiles["KR Server"]["servers"].append(
        server_entry("KR Server", "Common", "LoginServer", "206.127.153.34", LOGIN_PORT)
    )

    for name, host in tw_elyos:
        profiles["TW Server"]["servers"].append(server_entry("TW Server", "Elyos", name, host))
    for name, host in tw_asmo:
        profiles["TW Server"]["servers"].append(server_entry("TW Server", "Asmodians", name, host))
    profiles["TW Server"]["servers"].append(
        server_entry("TW Server", "Common", "LoginServer", "210.242.123.91", LOGIN_PORT)
    )
    # Existing endpoint-map ranges from the earlier local tool, not an official
    # live world roster. Names after the saved worlds remain unverified candidates.
    global_blocks = [
        ("Japan", "193.202.112.198", "193.202.112.199", "193.202.112.207", 8),
        ("NA West", "193.202.112.47", "193.202.112.48", "193.202.112.60", 12),
        ("NA East", "193.202.112.1", "193.202.112.2", "193.202.112.14", 12),
        ("Central Europe", "193.202.112.93", "193.202.112.94", "193.202.112.112", 18),
        ("South America", "193.202.112.160", "193.202.112.161", "193.202.112.171", 10),
    ]
    for region, login, elyos, asmo, count in global_blocks:
        for faction, start, pair_index in (("Elyos", elyos, 0), ("Asmodians", asmo, 1)):
            for index in range(count):
                name = SERVER_NAME_PAIRS[index][pair_index][0]
                server = server_entry(region, faction, name, str(ipaddress.ip_address(start) + index))
                server["endpoint_note"] = "既存範囲データの候補・対応未検証"
                profiles[region]["servers"].append(server)
        server = server_entry(region, "Common", "LoginServer", login, LOGIN_PORT)
        server["endpoint_note"] = "既存データ・ポート未検証"
        profiles[region]["servers"].append(server)
    return profiles
