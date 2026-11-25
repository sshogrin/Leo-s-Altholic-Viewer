import os
import re
import io
import textwrap
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


ESO_CLASSES = [
    "All",
    "Arcanist",
    "Dragonknight",
    "Necromancer",
    "Nightblade",
    "Sorcerer",
    "Templar",
    "Warden",
]

CLASS_COLORS = {
    "dragonknight": "#ff8c1a",
    "warden": "#4da6ff",
    "nightblade": "#ff4d4d",
    "sorcerer": "#b366ff",
    "arcanist": "#4dff88",
    "templar": "#ffd700",
    "necromancer": "#33ffff",
}

CLASS_SHORT_MAP = {
    "arc": "Arcanist",
    "dra": "Dragonknight",
    "nec": "Necromancer",
    "nig": "Nightblade",
    "sor": "Sorcerer",
    "tem": "Templar",
    "war": "Warden",
}

EQUIP_SLOT_NAMES = [
    "Head",
    "Shoulders",
    "Chest",
    "Hands",
    "Waist",
    "Legs",
    "Feet",
    "Necklace",
    "Ring 1",
    "Ring 2",
    "Main Hand",
    "Off Hand",
    "Backup Main Hand",
    "Backup Off Hand",
]

MUNDUS_ID_MAP = {
    13940: "The Warrior",
    13941: "The Mage",
    13942: "The Serpent",
    13943: "The Thief",
    13944: "The Lady",
    13945: "The Steed",
    13946: "The Lord",
    13947: "The Apprentice",
    13948: "The Ritual",
    13949: "The Lover",
    13950: "The Atronach",
    13951: "The Shadow",
    13952: "The Tower",
}

ARMOR_TYPE_MAP = {
    1: "Light",
    2: "Medium",
    3: "Heavy",
}

WEAPON_TYPE_MAP = {
    0: "None",
    1: "Axe",
    2: "Mace",
    3: "Sword",
    4: "Greatsword",
    5: "Battle Axe",
    6: "Maul",
    7: "Prop",
    8: "Bow",
    9: "Restoration Staff",
    10: "Rune",
    11: "Dagger",
    12: "Inferno Staff",
    13: "Frost Staff",
    14: "Shield",
    15: "Lightning Staff",
}


TRAIT_TYPE_MAP = {
    1: "Powered",
    2: "Charged",
    3: "Precise",
    4: "Infused",
    5: "Defending",
    6: "Training",
    7: "Sharpened",
    8: "Decisive",
    9: "Intricate",
    10: "Ornate",
    11: "Sturdy",
    12: "Impenetrable",
    13: "Reinforced",
    14: "Well-Fitted",
    15: "Training",
    16: "Infused",
    17: "Invigorating",
    18: "Divines",
    19: "Ornate",
    20: "Intricate",
    21: "Healthy",
    22: "Arcane",
    23: "Robust",
    24: "Ornate",
    25: "Nirnhoned",
    26: "Nirnhoned",
    27: "Intricate",
    28: "Swift",
    29: "Harmony",
    30: "Triune",
    31: "Bloodthirsty",
    32: "Protective",
    33: "Infused",
}

ENCHANT_CATEGORY_MAP = {
    1: "Maximum Health",
    2: "Maximum Magicka",
    3: "Maximum Stamina",
    4: "Health Recovery",
    5: "Magicka Recovery",
    6: "Stamina Recovery",
    7: "Weapon Damage",
    8: "Spell Damage",
    9: "Physical Harm",
    10: "Magical Harm",
    11: "Flame Damage",
    12: "Frost Damage",
    13: "Shock Damage",
    14: "Poison Damage",
    15: "Foulness (Disease) Damage",
    16: "Absorb Health",
    17: "Absorb Magicka",
    18: "Absorb Stamina",
    19: "Hardening (Damage Shield)",
    20: "Crushing (Reduce Armor)",
    21: "Weakening (Reduce Power)",
    22: "Befouled (Reduce Healing)",
    23: "Prismatic Onslaught",
    24: "Prismatic Defense",
    25: "Reduce Feat Cost",
    26: "Reduce Spell Cost",
    27: "Potion Speed",
    28: "Potion Boost",
    29: "Bash Damage",
    30: "Shielding (Block Cost)",
    31: "Flame Resistance",
    32: "Frost Resistance",
    33: "Shock Resistance",
    34: "Poison Resistance",
    35: "Disease Resistance",
    36: "Spell Resistance",
    37: "Physical Resistance",
}

SLOT_LABEL_MAP = {
    "Main Hand": "Front Bar",
    "Off Hand": "Front Bar (Off-Hand)",
    "Backup Main Hand": "Backbar",
    "Backup Off Hand": "Backbar (Off-Hand)",
}

def format_weapon_slot(raw_slot: str, is_single_weapon: bool = True) -> str:
    if raw_slot == "Main Hand":
        return "Front Bar" if is_single_weapon else "Front Bar (Main Hand)"
    if raw_slot == "Off Hand":
        return "Front Bar (Off-Hand)"
    if raw_slot == "Backup Main Hand":
        return "Backbar" if is_single_weapon else "Backbar (Main Hand)"
    if raw_slot == "Backup Off Hand":
        return "Backbar (Off-Hand)"
    return raw_slot

def from_base36(token: str) -> int:
    token = (token or "").strip()
    if not token or token == "-":
        return 0
    try:
        return int(token, 36)
    except ValueError:
        return 0

def parse_shos_lua_table(text: str) -> dict:
    """Parses ShosBuildExporterSV from ShosBuildExporter.lua."""
    text = re.sub(r"(?m)^\s*--.*$", "", text)
    match = re.search(r"ShosBuildExporterSV\s*=\s*(\{.*\})", text, re.DOTALL)
    if not match:
        return {}
    lua_body = match.group(1)

    pattern = r'\["([^"\\]*(?:\\.[^"\\]*)*)"\]\s*=|\[(\d+)\]\s*=|([a-zA-Z_]\w*)\s*=|"([^"\\]*(?:\\.[^"\\]*)*)"|(-?\d+(?:\.\d+)?)|\b(true|false|nil)\b|(\{|\}|,)'
    tokens = re.findall(pattern, lua_body)
    idx = 0

    def parse_value():
        nonlocal idx
        if idx >= len(tokens):
            return None
        str_key, int_key, id_key, str_val, num_val, bool_val, sym = tokens[idx]
        idx += 1

        if sym == "{":
            obj = {}
            arr_idx = 1
            while idx < len(tokens):
                n_skey, n_ikey, n_idkey, n_sval, n_nval, n_bval, n_sym = tokens[idx]
                if n_sym == "}":
                    idx += 1
                    break
                if n_sym == ",":
                    idx += 1
                    continue
                if n_skey != "":
                    idx += 1
                    obj[n_skey] = parse_value()
                elif n_ikey != "":
                    idx += 1
                    obj[int(n_ikey)] = parse_value()
                elif n_idkey != "":
                    idx += 1
                    obj[n_idkey] = parse_value()
                else:
                    obj[arr_idx] = parse_value()
                    arr_idx += 1
            return obj

        if str_val != "":
            return str_val.replace("\\n", "\n").replace('\\"', '"')
        if num_val != "":
            return float(num_val) if "." in num_val else int(num_val)
        if bool_val == "true":
            return True
        if bool_val == "false":
            return False
        return None

    res = parse_value()
    return res if isinstance(res, dict) else {}


def decode_sbe2_code(code_str: str, meta: dict | None = None, name_db: dict | None = None) -> dict:
    """Decodes an [SBE2|...] compact code into structured data and readable display lines."""
    meta = meta or {}
    name_db = name_db or {}
    sets_db = name_db.get("sets", {}) if isinstance(name_db.get("sets"), dict) else {}
    ench_db = name_db.get("enchants", {}) if isinstance(name_db.get("enchants"), dict) else {}
    abil_db = name_db.get("abilities", {}) if isinstance(name_db.get("abilities"), dict) else {}
    scr_db = name_db.get("scripts", {}) if isinstance(name_db.get("scripts"), dict) else {}
    cp_db = name_db.get("cp", {}) if isinstance(name_db.get("cp"), dict) else {}

    cleaned = code_str.strip()
    m = re.search(r"\[SBE2\|+(.*?)\]", cleaned)
    if not m:
        return {
            "buildName": meta.get("name", "Build"),
            "charName": meta.get("char", "Unknown"),
            "race": meta.get("race", ""),
            "class": meta.get("class", "Unknown"),
            "code": cleaned,
            "formattedText": cleaned,
        }

    body = m.group(1).replace("||", "|")
    fields = body.split("|")
    while len(fields) < 8:
        fields.append("")

    cls_short, b_name, attr_str, mundus_str, gear_str, fb_str, bb_str, cp_str = fields[:8]

    full_class = meta.get("class") or CLASS_SHORT_MAP.get(cls_short.strip().lower(), cls_short or "Unknown")
    build_name = meta.get("name") or b_name or "Default"
    char_name = meta.get("char") or "Shared Build"
    race_name = meta.get("race") or ""

    # Attributes
    attr_parts = attr_str.split(".") if attr_str else list()
    mag = from_base36(attr_parts[0]) if len(attr_parts) > 0 else 0
    hp = from_base36(attr_parts[1]) if len(attr_parts) > 1 else 0
    stam = from_base36(attr_parts[2]) if len(attr_parts) > 2 else 0

    # Mundus
    mundus_names = list()
    if mundus_str and mundus_str != "0":
        for tok in mundus_str.split("."):
            mid = from_base36(tok)
            if mid in MUNDUS_ID_MAP:
                mundus_names.append(MUNDUS_ID_MAP[mid])
            elif mid > 0:
                mundus_names.append(f"Mundus #{mid}")
    mundus_text = ", ".join(mundus_names) if mundus_names else "None"

    # Gear (14 slots)
    gear_lines = list()
    g_tokens = gear_str.split(",") if gear_str else list()

    # Check if Front Bar or Backbar has an Off Hand equipped (for cleaner single-weapon labels)
    has_front_off = (
        len(g_tokens) > 11
        and g_tokens[11].strip() not in ("", "-")
    )
    has_back_off = (
        len(g_tokens) > 13
        and g_tokens[13].strip() not in ("", "-")
    )

    for idx, slot_name in enumerate(EQUIP_SLOT_NAMES):
        tok = g_tokens[idx].strip() if idx < len(g_tokens) else "-"

        # Format weapon slot labels cleanly ("Front Bar" / "Backbar")
        if slot_name in ("Main Hand", "Off Hand"):
            display_slot = format_weapon_slot(slot_name, is_single_weapon=not has_front_off)
        elif slot_name in ("Backup Main Hand", "Backup Off Hand"):
            display_slot = format_weapon_slot(slot_name, is_single_weapon=not has_back_off)
        else:
            display_slot = slot_name

        if not tok or tok == "-":
            # Skip empty Off Hand / Backbar (Off-Hand) lines if a 2H/Bow/Staff is equipped
            if slot_name in ("Off Hand", "Backup Off Hand"):
                continue
            gear_lines.append(f"{display_slot}: [Empty]")
            continue

        p = tok.split(".")
        set_id = from_base36(p[0]) if len(p) > 0 else 0
        sub_id = from_base36(p[1]) if len(p) > 1 else 0
        trait_id = from_base36(p[2]) if len(p) > 2 else 0
        ench_id = from_base36(p[3]) if len(p) > 3 else 0

        if sub_id >= 100:
            w_type = WEAPON_TYPE_MAP.get(sub_id - 100, f"Weapon #{sub_id - 100}")
        elif sub_id > 0:
            w_type = ARMOR_TYPE_MAP.get(sub_id, f"Armor #{sub_id}")
        else:
            w_type = ""

        set_label = (
            sets_db.get(str(set_id))
            or sets_db.get(set_id)
            or (f"Set #{set_id}" if set_id > 0 else "No Set")
        )
        trait_label = TRAIT_TYPE_MAP.get(trait_id, f"Trait #{trait_id}" if trait_id > 0 else "No Trait")
        ench_label = (
            ench_db.get(str(ench_id))
            or ench_db.get(ench_id)
            or ENCHANT_CATEGORY_MAP.get(ench_id)
            or (f"Enchant #{ench_id}" if ench_id > 0 else "No Enchant")
        )
        suffix = f" ({w_type})" if w_type else ""
        gear_lines.append(f"{display_slot}: {set_label}{suffix} | Trait: {trait_label} | Enchant: {ench_label}")

    # Skill Bars
    def format_bar(bar_str: str) -> list[str]:
        out = list()
        toks = bar_str.split(",") if bar_str else list()
        for i in range(6):
            label = "Ultimate" if i == 5 else f"Slot {i + 1}"
            tok = toks[i].strip() if i < len(toks) else "-"
            if not tok or tok == "-":
                out.append(f"{label}: [Empty]")
            elif tok.startswith("c"):
                cp = tok[1:].split(".")
                cid = from_base36(cp[0]) if len(cp) > 0 else 0
                f_id = from_base36(cp[1]) if len(cp) > 1 else 0
                s_id = from_base36(cp[2]) if len(cp) > 2 else 0
                a_id = from_base36(cp[3]) if len(cp) > 3 else 0
                c_name = abil_db.get(f"c{cid}") or f"Scribed Ability #{cid}"
                f_name = scr_db.get(str(f_id)) or scr_db.get(f_id) or f"Focus #{f_id}"
                s_name = scr_db.get(str(s_id)) or scr_db.get(s_id) or f"Sig #{s_id}"
                a_name = scr_db.get(str(a_id)) or scr_db.get(a_id) or f"Affix #{a_id}"
                out.append(f"{label}: {c_name} [Scribed] -> Focus: {f_name} | Signature: {s_name} | Affix: {a_name}")
            else:
                aid = from_base36(tok)
                a_name = abil_db.get(str(aid)) or abil_db.get(aid) or f"Ability #{aid}"
                out.append(f"{label}: {a_name}")
        return out

    fb_lines = format_bar(fb_str)
    bb_lines = format_bar(bb_str)

    # CP Slottables
    cp_lines = list()
    if cp_str:
        for idx, tok in enumerate(cp_str.split(","), start=1):
            tok = tok.strip()
            if tok and tok != "-":
                sid = from_base36(tok)
                if sid > 0:
                    c_name = cp_db.get(str(sid)) or cp_db.get(sid) or f"CP Star #{sid}"
                    cp_lines.append(f"Slot {idx}: {c_name}")
    if not cp_lines:
        cp_lines.append("No CP slottables assigned.")

    # Combat Passives (checks 9th [SBE2|...] field OR meta["passives"] / meta["formattedText"])
    passive_lines = list()
    skip_cats = ("CRAFT", "SCRY", "EXCAVAT", "LEGERDEMAIN", "THIEVES", "DARK BROTHERHOOD")

    pass_str = fields[8].strip() if len(fields) > 8 else ""
    if pass_str:
        # Decodes optional 9th field format: "Category:id1,id2;Category2:id3,id4" or "id1,id2,id3"
        for group in pass_str.split(";"):
            group = group.strip()
            if not group:
                continue
            if ":" in group:
                cat_part, ids_part = group.split(":", 1)
                cat_name = cat_part.strip()
                if any(sk in cat_name.upper() for sk in skip_cats):
                    continue
                p_names = list()
                for tok in ids_part.split(","):
                    tok = tok.strip()
                    if tok and tok != "-":
                        pid = from_base36(tok)
                        if pid > 0:
                            p_names.append(abil_db.get(str(pid)) or abil_db.get(pid) or f"Passive #{pid}")
                if p_names:
                    passive_lines.append(f"{cat_name}: {', '.join(p_names)}")
            else:
                p_names = list()
                for tok in group.split(","):
                    tok = tok.strip()
                    if tok and tok != "-":
                        pid = from_base36(tok)
                        if pid > 0:
                            p_names.append(abil_db.get(str(pid)) or abil_db.get(pid) or f"Passive #{pid}")
                if p_names:
                    passive_lines.append(f"Combat Passives: {', '.join(p_names)}")

    if not passive_lines and isinstance(meta.get("passives"), dict):
        for cat, items in meta["passives"].items():
            cat_str = str(cat).strip()
            if any(sk in cat_str.upper() for sk in skip_cats):
                continue
            if isinstance(items, dict):
                names = list()
                for v in items.values():
                    if isinstance(v, dict):
                        n = v.get("name") or v.get("skillName") or ""
                        if n:
                            names.append(str(n))
                    elif v:
                        names.append(str(v))
                if names:
                    passive_lines.append(f"{cat_str}: {', '.join(names)}")
            elif items:
                passive_lines.append(f"{cat_str}: {items}")

    if not passive_lines and isinstance(meta.get("formattedText"), str):
        in_pass = False
        for raw_line in meta["formattedText"].splitlines():
            s = raw_line.strip()
            if (s.startswith("===") and s.endswith("===")) or (s.startswith("---") and s.endswith("---")):
                in_pass = "PASSIVE" in s.upper()
                continue
            if in_pass and ":" in s:
                cat_part = s.split(":", 1)[0].strip().upper()
                if not any(sk in cat_part for sk in skip_cats):
                    passive_lines.append(s)

    passive_block = list()
    if passive_lines:
        passive_block = ["", "=== COMBAT PASSIVES ===", *passive_lines]

    lines = [
        f"=== BUILD: {build_name} ===",
        f"Character: {char_name} | Race: {race_name} | Class: {full_class}",
        "",
        "=== ATTRIBUTES ===",
        f"Magicka: {mag} | Health: {hp} | Stamina: {stam}",
        "",
        "=== MUNDUS STONE ===",
        mundus_text,
        "",
        "=== EQUIPPED GEAR ===",
        *gear_lines,
        "",
        "=== CHAMPION POINTS (SLOTTABLES) ===",
        *cp_lines,
        "",
        "=== FRONT BAR ===",
        *fb_lines,
        "",
        "=== BACK BAR ===",
        *bb_lines,
        *passive_block,
        "",
        "=== SHARE CODE ===",
        cleaned,
    ]

    return {
        "buildName": build_name,
        "charName": char_name,
        "race": race_name,
        "class": full_class,
        "code": cleaned,
        "formattedText": "\n".join(lines),
    }

def load_shos_builds(saved_vars_dir: Path | None) -> tuple[list[dict], dict]:
    """Loads all builds and the shared ID->Name lookup dict from ShosBuildExporter.lua."""
    merged_names = {
        "sets": {},
        "enchants": {},
        "abilities": {},
        "scripts": {},
        "cp": {},
    }
    if not saved_vars_dir or not saved_vars_dir.is_dir():
        return list(), merged_names

    sv_file = saved_vars_dir / "ShosBuildExporter.lua"
    if not sv_file.is_file():
        return list(), merged_names

    raw = sv_file.read_text(encoding="utf-8", errors="ignore")
    parsed = parse_shos_lua_table(raw)
    default_tbl = parsed.get("Default", {})
    if not isinstance(default_tbl, dict):
        return list(), merged_names

    builds = list()
    for account, acct_data in default_tbl.items():
        if not isinstance(acct_data, dict):
            continue
        acct_wide = acct_data.get("$AccountWide", {})
        if not isinstance(acct_wide, dict):
            continue

        acct_names = acct_wide.get("names", {})
        if isinstance(acct_names, dict):
            for category in merged_names:
                cat_dict = acct_names.get(category)
                if isinstance(cat_dict, dict):
                    merged_names[category].update(cat_dict)

        for key, record in acct_wide.items():
            if key in ("version", "names") or not isinstance(record, dict):
                continue

            if "code" in record:
                decoded = decode_sbe2_code(record["code"], record, name_db=merged_names)
                decoded["account"] = account
                decoded["key"] = str(key)
                builds.append(decoded)
            elif "formattedText" in record:
                char_info = record.get("character", {})
                builds.append({
                    "account": account,
                    "key": str(key),
                    "buildName": record.get("buildName") or char_info.get("buildName") or "Default",
                    "charName": char_info.get("name", str(key)),
                    "race": char_info.get("race", ""),
                    "class": char_info.get("class", "Unknown"),
                    "code": record.get("chatString", ""),
                    "formattedText": record.get("formattedText", ""),
                })

    builds.sort(key=lambda b: (b["class"].lower(), b["charName"].lower(), b["buildName"].lower()))
    return builds, merged_names


class BuildsTab(ttk.Frame):
    """Class-tabbed Build Viewer & PNG Card Generator styled to match Leo's Altholic Viewer."""

    def __init__(self, parent, get_saved_vars_dir_fn):
        super().__init__(parent)
        self.get_saved_vars_dir = get_saved_vars_dir_fn
        self.all_builds: list[dict] = list()
        self.name_db: dict = {}
        self.current_build: dict | None = None
        self.class_trees: dict[str, ttk.Treeview] = {}

        self._build_ui()

    def _build_ui(self):
        toolbar = tk.Frame(self, bg="#282520", padx=12, pady=8)
        toolbar.pack(fill="x")

        btn_style = dict(
            bg="#2d2922",
            fg="#d4af37",
            activebackground="#3d372e",
            activeforeground="#ffffff",
            relief="solid",
            bd=1,
            padx=10,
            pady=3,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )

        tk.Button(toolbar, text="Reload Builds", command=self.refresh_builds, **btn_style).pack(side="left")
        tk.Button(toolbar, text="Copy Build / Code", command=self.copy_current_text, **btn_style).pack(side="left", padx=8)
        tk.Button(toolbar, text="Paste Share Code", command=self.prompt_paste_code, **btn_style).pack(side="left")
        tk.Button(toolbar, text="Save Build as PNG", command=self.export_png, **btn_style).pack(side="left", padx=8)

        self.info_var = tk.StringVar(value="Select a class tab and build on the left.")
        tk.Label(toolbar, textvariable=self.info_var, bg="#282520", fg="#a89f91", font=("Segoe UI", 9)).pack(side="right")

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=8)

        left_frame = ttk.Frame(paned, width=560)
        right_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        paned.add(right_frame, weight=2)

        style = ttk.Style()
        style.configure("Class.TNotebook", background="#18181c", borderwidth=0)
        style.configure(
            "Class.TNotebook.Tab",
            background="#18181c",
            foreground="#a89f91",
            padding=(7, 5),
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Class.TNotebook.Tab",
            background=[("selected", "#2d2922")],
            foreground=[("selected", "#d4af37")],
        )

        self.class_notebook = ttk.Notebook(left_frame, style="Class.TNotebook")
        self.class_notebook.pack(fill="both", expand=True)

        for cls_name in ESO_CLASSES:
            tab = ttk.Frame(self.class_notebook)
            self.class_notebook.add(tab, text=cls_name)

            cols = ("build_name", "character", "race", "account")
            tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
            tree.heading("build_name", text="Build Name")
            tree.heading("character", text="Character")
            tree.heading("race", text="Race")
            tree.heading("account", text="Account")

            tree.column("build_name", width=135)
            tree.column("character", width=130)
            tree.column("race", width=85)
            tree.column("account", width=90)

            tree.tag_configure("even", background="#1e1e24")
            tree.tag_configure("odd", background="#23232a")
            for c_key, hex_col in CLASS_COLORS.items():
                tree.tag_configure(f"cls_{c_key}", foreground=hex_col, font=("Segoe UI", 9, "bold"))

            vsb = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            tree.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")

            tree.bind("<<TreeviewSelect>>", lambda e, t=tree: self._on_select_build(t))
            self.class_trees[cls_name] = tree

        text_scroll = ttk.Scrollbar(right_frame, orient="vertical")
        self.detail_text = tk.Text(
            right_frame,
            wrap="word",
            font=("Consolas", 10),
            bg="#1e1e24",
            fg="#e2dcd0",
            insertbackground="#ffffff",
            padx=14,
            pady=12,
            bd=0,
            highlightthickness=0,
            yscrollcommand=text_scroll.set,
        )
        text_scroll.config(command=self.detail_text.yview)
        self.detail_text.pack(side="left", fill="both", expand=True)
        text_scroll.pack(side="right", fill="y")

        self.detail_text.tag_configure("header", foreground="#d4af37", font=("Consolas", 11, "bold"))
        self.detail_text.tag_configure("scribed", foreground="#ffae42", font=("Consolas", 10, "bold"))
        self.detail_text.tag_configure("code", foreground="#8c9eff", font=("Consolas", 9))

    def refresh_builds(self):
        sv_dir = self.get_saved_vars_dir()
        self.all_builds, self.name_db = load_shos_builds(sv_dir)

        for cls_name, tree in self.class_trees.items():
            tree.delete(*tree.get_children())
            row_i = 0
            for idx, b in enumerate(self.all_builds):
                if cls_name == "All" or b["class"].lower() == cls_name.lower():
                    row_tag = "even" if row_i % 2 == 0 else "odd"
                    cls_tag = f"cls_{b['class'].lower()}"
                    tags = (row_tag, cls_tag) if b["class"].lower() in CLASS_COLORS else (row_tag,)
                    tree.insert(
                        "",
                        "end",
                        iid=f"{cls_name}_{idx}",
                        values=(b["buildName"], b["charName"], b["race"], b.get("account", "")),
                        tags=tags,
                    )
                    row_i += 1

        self.info_var.set(f"Loaded {len(self.all_builds)} build(s)")

    def _on_select_build(self, tree: ttk.Treeview):
        sel = tree.selection()
        if not sel:
            return
        idx = int(sel[0].split("_")[-1])
        self.current_build = self.all_builds[idx]
        self._render_build(self.current_build)

    def _render_build(self, b: dict):
        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", "end")

        for line in b.get("formattedText", "").splitlines():
            if line.startswith("==="):
                self.detail_text.insert("end", line + "\n", "header")
            elif "[Scribed]" in line:
                self.detail_text.insert("end", line + "\n", "scribed")
            elif line.startswith("[SBE2|"):
                self.detail_text.insert("end", line + "\n", "code")
            else:
                self.detail_text.insert("end", line + "\n")

        self.detail_text.config(state="disabled")

    def copy_current_text(self):
        if not self.current_build:
            return
        text = self.current_build.get("formattedText", "")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.info_var.set(f"Copied '{self.current_build['buildName']}' to clipboard.")

    def prompt_paste_code(self):
        win = tk.Toplevel(self)
        win.title("Import [SBE2|...] Share Code")
        win.geometry("620x210")
        win.configure(bg="#1e1e24")

        tk.Label(
            win,
            text="Paste an [SBE2|...] share code below to preview and save as PNG:",
            bg="#1e1e24",
            fg="#d4af37",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 6))

        entry = tk.Text(win, height=4, bg="#141417", fg="#e2dcd0", insertbackground="#fff", font=("Consolas", 10))
        entry.pack(fill="x", padx=14)
        entry.focus_set()

        def do_import():
            raw = entry.get("1.0", "end").strip()
            if not raw:
                return
            decoded = decode_sbe2_code(raw, name_db=self.name_db)
            self.current_build = decoded
            self._render_build(decoded)
            self.info_var.set(f"Previewing imported build: {decoded['buildName']}")
            win.destroy()

        tk.Button(
            win,
            text="Load Build",
            command=do_import,
            bg="#2d2922",
            fg="#d4af37",
            relief="solid",
            bd=1,
            padx=14,
            pady=4,
            font=("Segoe UI", 9, "bold"),
        ).pack(pady=12)

    def _parse_build_for_card(self, b: dict) -> dict:
        """Extracts structured card sections from self.current_build."""
        data = {
            "title": f"{b.get('class', '')} — {b.get('buildName', 'ESO Build')}".strip(" —"),
            "subtitle": f"{b.get('charName', '')}".strip(),
            "armor": [],
            "jewelry": [],
            "front_weapons": [],
            "back_weapons": [],
            "attributes": {
                "Magicka": str(b.get("magicka", "")),
                "Health": str(b.get("health", "")),
                "Stamina": str(b.get("stamina", "")),
            },
            "cp_total": str(b.get("cp", "")),
            "cp_slottables": {"Warfare": [], "Fitness": [], "Crafting": []},
            "front_bar": [],
            "back_bar": [],
            "mundus": b.get("mundus", "") or "None",
            "passives": {},
        }

        armor_slots = {"Head", "Shoulders", "Chest", "Hands", "Waist", "Legs", "Feet"}
        jewelry_slots = {"Neck", "Necklace", "Amulet", "Ring 1", "Ring 2"}
        section = ""

        for raw in b.get("formattedText", "").splitlines():
            line = raw.strip()
            if not line or line.startswith("[SBE2|"):
                continue

            # Detect section headers (handles === HEADER === or --- HEADER ---)
            if (line.startswith("===") and line.endswith("===")) or (line.startswith("---") and line.endswith("---")):
                section = line.strip("=- ").upper()
                continue

            # 1. Mundus Stone (matches "Mundus: The Thief" anywhere OR any line inside a MUNDUS section)
            if "MUNDUS" in section or (line.lower().startswith("mundus") and ":" in line):
                val = line.split(":", 1)[1].strip() if ":" in line else line.strip()
                if val:
                    data["mundus"] = val
                continue

            # 2. Champion Points (ONLY when inside CHAMPION/CP section!)
            if "CHAMPION" in section or "CP" in section:
                m = re.search(r"CP\s*(\d+)", line, re.IGNORECASE)
                if m:
                    data["cp_total"] = m.group(1)

                slot_match = re.match(r"^Slot\s*(\d+)\s*:\s*(.+)$", line, re.IGNORECASE)
                if slot_match:
                    slot_num = int(slot_match.group(1))
                    star_name = slot_match.group(2).strip()
                    if 1 <= slot_num <= 4:
                        data["cp_slottables"]["Crafting"].append(star_name)
                    elif 5 <= slot_num <= 8:
                        data["cp_slottables"]["Warfare"].append(star_name)
                    elif 9 <= slot_num <= 12:
                        data["cp_slottables"]["Fitness"].append(star_name)
                continue

            # 3. Parse Gear & Weapons ("Slot: Set (Type) | Trait: X | Enchant: Y")
            if "GEAR" in section and ":" in line:
                slot, rest = line.split(":", 1)
                slot = slot.strip()
                parts = [p.strip() for p in rest.split("|")]
                set_name = parts[0] if len(parts) > 0 else ""
                trait = parts[1].replace("Trait:", "").strip() if len(parts) > 1 else ""
                enchant = parts[2].replace("Enchant:", "").strip() if len(parts) > 2 else ""

                if slot in armor_slots:
                    data["armor"].append({"slot": slot, "set": set_name, "trait": trait, "enchant": enchant})
                elif slot in jewelry_slots:
                    display_jewelry = "Amulet" if slot in ("Neck", "Necklace") else slot
                    data["jewelry"].append({"slot": display_jewelry, "set": set_name, "trait": trait, "enchant": enchant})
                elif slot.startswith("Front Bar"):
                    hand = "Off Hand" if "Off-Hand" in slot else "Main Hand"
                    data["front_weapons"].append({"hand": hand, "name": set_name, "trait": trait, "enchant": enchant})
                elif slot.startswith("Backbar") or slot.startswith("Back Bar"):
                    hand = "Off Hand" if "Off-Hand" in slot else "Main Hand"
                    data["back_weapons"].append({"hand": hand, "name": set_name, "trait": trait, "enchant": enchant})
                    
            # 4. Parse Attributes (handles "Magicka: 64 | Health: 0 | Stamina: 0" or separate lines)
            if "ATTRIBUTE" in section or any(k in line.lower() for k in ("magicka:", "health:", "stamina:")):
                for stat in ("Magicka", "Health", "Stamina"):
                    m = re.search(rf"{stat}\s*:\s*(\d+)", line, re.IGNORECASE)
                    if m:
                        data["attributes"][stat] = m.group(1)
                if "ATTRIBUTE" in section:
                    continue

            # 5. Parse Skill Bars (handles "1. Skill", "Slot 1: Skill", "ULT. Skill", "Ultimate: Skill")
            if "FRONT BAR" in section:
                skill_name = re.sub(r"^(Slot\s*\d+\s*:|\d+\.|ULT(?:IMATE)?[\.:]?)\s*", "", line, flags=re.IGNORECASE).strip()
                if skill_name:
                    data["front_bar"].append(skill_name)
                continue
            if "BACK" in section and "BAR" in section:
                skill_name = re.sub(r"^(Slot\s*\d+\s*:|\d+\.|ULT(?:IMATE)?[\.:]?)\s*", "", line, flags=re.IGNORECASE).strip()
                if skill_name:
                    data["back_bar"].append(skill_name)
                continue

            # 6. Parse Passives
            if ("PASSIVE" in section or "COMBAT" in section) and ":" in line:
                cat, vals = line.split(":", 1)
                cat_upper = cat.strip().upper()
                if not any(skip in cat_upper for skip in ("CRAFT", "SCRY", "EXCAVAT", "LEGERDEMAIN", "THIEVES", "DARK BROTHERHOOD")):
                    data["passives"][cat_upper] = vals.strip()

        return data

    def export_png(self):
        if not self.current_build:
            messagebox.showinfo("No Build Selected", "Select or import a build first before saving as PNG.")
            return
        if not HAS_PIL:
            messagebox.showerror("Missing Pillow", "Install Pillow first:\n\npip install pillow")
            return

        b = self.current_build
        safe_name = re.sub(r"[^\w\-]+", "_", f"{b['class']}_{b['charName']}_{b['buildName']}")
        out_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
            initialfile=f"{safe_name}.png",
        )
        if not out_path:
            return

        card = self._parse_build_for_card(b)

        try:
            font_title = ImageFont.truetype("segoeuib.ttf", 26)
            font_header = ImageFont.truetype("segoeuib.ttf", 18)
            font_body = ImageFont.truetype("segoeui.ttf", 14)
            font_small = ImageFont.truetype("segoeui.ttf", 13)
        except Exception:
            font_title = font_header = font_body = font_small = ImageFont.load_default()

        def text_w(txt, fnt):
            if hasattr(fnt, "getlength"):
                return fnt.getlength(txt)
            bbox = fnt.getbbox(txt)
            return (bbox[2] - bbox[0]) if bbox else len(txt) * 8

        # Dynamically calculate armor trait column X & extra canvas width from longest armor set+weight
        # 1. Measure Armor sub-column (left side of Gear & Sets)
        max_armor_set_w = 0
        max_armor_trait_w = 0
        for item in card["armor"]:
            max_armor_set_w = max(max_armor_set_w, text_w(item.get("set", ""), font_body))
            max_armor_trait_w = max(max_armor_trait_w, text_w(item.get("trait", ""), font_small))

        armor_trait_x = max(310, int(120 + max_armor_set_w + 18))
        JEWELRY_X = max(440, int(armor_trait_x + max_armor_trait_w + 28))
        JEWELRY_SET_X = JEWELRY_X + 65

        # 2. Measure Jewelry & Weapon sub-column (right side of Gear & Sets)
        max_jewel_set_w = 0
        max_jewel_trait_w = 0
        for item in card["jewelry"]:
            max_jewel_set_w = max(max_jewel_set_w, text_w(item.get("set", ""), font_body))
            te_str = f"{item.get('trait', '')} / {item.get('enchant', '')}"
            max_jewel_trait_w = max(max_jewel_trait_w, text_w(te_str, font_small))

        JEWELRY_TRAIT_X = max(JEWELRY_SET_X + 200, int(JEWELRY_SET_X + max_jewel_set_w + 18))
        jewel_right_edge = JEWELRY_TRAIT_X + max_jewel_trait_w

        for w_list in (card["front_weapons"], card["back_weapons"]):
            for w in w_list:
                prefix = f"{w['hand']}: " if len(w_list) > 1 else ""
                w_line1 = text_w(f"{prefix}{w['name']}", font_small)
                w_line2 = text_w(f"{w['trait']} / {w['enchant']}", font_small)
                jewel_right_edge = max(jewel_right_edge, JEWELRY_X + max(w_line1, w_line2))

        DIVIDER_X = max(990, int(jewel_right_edge + 30))
        RIGHT_COL_X = DIVIDER_X + 35
        BACKBAR_X = RIGHT_COL_X + 400

        # Extract & deduplicate scribed skills from Front Bar + Back Bar
        scribed_defs = list()
        seen_scribed = set()

        def clean_bar_entries(bar_list):
            cleaned = list()
            for raw_entry in bar_list:
                if "[Scribed]" in raw_entry:
                    if "->" in raw_entry:
                        short_part, scripts_part = raw_entry.split("->", 1)
                        short_label = short_part.strip()
                        skill_name = short_label.replace("[Scribed]", "").strip()
                        def_line = f"{skill_name}: {scripts_part.strip()}"
                    else:
                        short_label = raw_entry.strip()
                        def_line = short_label
                    cleaned.append(short_label)
                    if def_line not in seen_scribed:
                        seen_scribed.add(def_line)
                        scribed_defs.append(def_line)
                else:
                    cleaned.append(raw_entry)
            return cleaned

        front_bar_clean = clean_bar_entries(card["front_bar"])
        back_bar_clean = clean_bar_entries(card["back_bar"])

        # Calculate extra vertical height needed for Scribed Skills + Combat Passives
        scribed_block_h = (36 + len(scribed_defs) * 24 + 14) if scribed_defs else 0
        passives_items = list(card["passives"].items())
        passive_rows = (len(passives_items) + 2) // 3
        passives_y = 315 + scribed_block_h
        needed_right_h = (passives_y + 32) + passive_rows * 78 + 30

        # Dynamic canvas dimensions
        W = DIVIDER_X + 850
        H = max(900, needed_right_h)
        extra_h = H - 900

        BG_COLOR = (17, 17, 19)
        PANEL_BG = (24, 24, 27)
        GOLD = (212, 175, 55)
        GOLD_DIM = (140, 115, 45)
        TEXT_LIGHT = (235, 235, 235)
        TEXT_MUTED = (170, 170, 175)

        img = Image.new("RGB", (W, H), BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Gold double border & center divider
        draw.rectangle([10, 10, W - 10, H - 10], outline=GOLD_DIM, width=2)
        draw.rectangle([16, 16, W - 16, H - 16], outline=GOLD, width=1)
        draw.line([(DIVIDER_X, 24), (DIVIDER_X, H - 24)], fill=GOLD_DIM, width=2)

        # --- LEFT COLUMN: HEADER, GEAR & SETS, MUNDUS, ATTRIBUTES, CP ---
        draw.text((40, 30), card["title"].upper(), fill=GOLD, font=font_title)
        if card["subtitle"]:
            draw.text((40, 64), card["subtitle"], fill=TEXT_LIGHT, font=font_header)

        draw.text((40, 105), "GEAR & SETS", fill=GOLD, font=font_header)
        draw.line([(170, 116), (DIVIDER_X - 25, 116)], fill=GOLD_DIM, width=1)

        # Armor (7 pieces on left sub-column, traits shifted dynamically to armor_trait_x)
        y = 138
        for item in card["armor"]:
            draw.text((40, y), f"{item['slot']}:", fill=GOLD, font=font_body)
            draw.text((120, y), item["set"], fill=TEXT_LIGHT, font=font_body)
            draw.text((armor_trait_x, y), item["trait"], fill=TEXT_MUTED, font=font_small)
            y += 32

        # Jewelry (Amulet, Ring 1, Ring 2 on right sub-column, shifted by extra_w)
        y_right = 138
        for item in card["jewelry"]:
            draw.text((JEWELRY_X, y_right), f"{item['slot']}:", fill=GOLD, font=font_body)
            draw.text((JEWELRY_SET_X, y_right), item["set"], fill=TEXT_LIGHT, font=font_body)
            draw.text((JEWELRY_TRAIT_X, y_right), f"{item['trait']} / {item['enchant']}", fill=TEXT_MUTED, font=font_small)
            y_right += 32

        # Front Bar Weapons
        y_right += 10
        draw.text((JEWELRY_X, y_right), "FRONT BAR", fill=GOLD, font=font_body)
        y_right += 24
        for w in card["front_weapons"]:
            prefix = f"{w['hand']}: " if len(card["front_weapons"]) > 1 else ""
            draw.text((JEWELRY_X, y_right), f"{prefix}{w['name']}", fill=TEXT_LIGHT, font=font_small)
            draw.text((JEWELRY_X, y_right + 16), f"{w['trait']} / {w['enchant']}", fill=TEXT_MUTED, font=font_small)
            y_right += 38

        # Backbar Weapons
        y_right += 4
        draw.text((JEWELRY_X, y_right), "BACKBAR", fill=GOLD, font=font_body)
        y_right += 24
        for w in card["back_weapons"]:
            prefix = f"{w['hand']}: " if len(card["back_weapons"]) > 1 else ""
            draw.text((JEWELRY_X, y_right), f"{prefix}{w['name']}", fill=TEXT_LIGHT, font=font_small)
            draw.text((JEWELRY_X, y_right + 16), f"{w['trait']} / {w['enchant']}", fill=TEXT_MUTED, font=font_small)
            y_right += 38

        # Mundus Stone
        mundus_y = 435 + extra_h
        draw.text((40, mundus_y), "MUNDUS STONE", fill=GOLD, font=font_header)
        draw.text((40, mundus_y + 28), card["mundus"], fill=TEXT_LIGHT, font=font_body)

        # Attributes
        attr_y = 520 + extra_h
        draw.text((40, attr_y), "ATTRIBUTES", fill=GOLD, font=font_header)
        attr_specs = [
            ("MAGICKA", (70, 130, 220), card["attributes"].get("Magicka") or "0"),
            ("HEALTH", (200, 65, 65), card["attributes"].get("Health") or "0"),
            ("STAMINA", (75, 175, 80), card["attributes"].get("Stamina") or "0"),
        ]
        for idx, (stat_label, stat_col, stat_val) in enumerate(attr_specs):
            ax = 40 + idx * 130
            ay = attr_y + 30
            draw.rectangle([ax, ay, ax + 118, ay + 48], fill=PANEL_BG, outline=stat_col, width=1)
            draw.text((ax + 10, ay + 6), stat_label, fill=stat_col, font=font_small)
            draw.text((ax + 10, ay + 24), str(stat_val), fill=TEXT_LIGHT, font=font_body)

        # Champion Points (Slottables)
        cp_y = 640 + extra_h
        cp_label = f"CHAMPION POINTS (SLOTTABLES)   CP {card['cp_total']}".strip()
        draw.text((40, cp_y), cp_label, fill=GOLD, font=font_header)

        trees = [
            ("WARFARE", (70, 130, 220), card["cp_slottables"].get("Warfare", list())),
            ("FITNESS", (200, 65, 65), card["cp_slottables"].get("Fitness", list())),
            ("CRAFTING", (75, 175, 80), card["cp_slottables"].get("Crafting", list())),
        ]
        box_w = 295
        for idx, (tree_name, accent, stars) in enumerate(trees):
            bx = 40 + idx * (box_w + 18)
            by = cp_y + 32
            draw.rectangle([bx, by, bx + box_w, by + 185], fill=PANEL_BG, outline=accent, width=2)
            draw.text((bx + 12, by + 10), tree_name, fill=accent, font=font_header)
            for s_idx, star in enumerate(stars[:4]):
                draw.text((bx + 12, by + 44 + s_idx * 30), f"{s_idx + 1}. {star}", fill=TEXT_LIGHT, font=font_body)

        # --- RIGHT COLUMN: SKILL BARS, SCRIBED DEFINITIONS & COMBAT PASSIVES ---
        draw.text((RIGHT_COL_X, 30), "SKILL BARS", fill=GOLD, font=font_header)
        draw.line([(RIGHT_COL_X + 120, 41), (W - 35, 41)], fill=GOLD_DIM, width=1)

        draw.text((RIGHT_COL_X, 66), "FRONT BAR", fill=GOLD, font=font_body)
        draw.text((BACKBAR_X, 66), "BACKBAR", fill=GOLD, font=font_body)

        for i in range(6):
            label = "ULT." if i == 5 else f"{i + 1}."
            fb_skill = front_bar_clean[i] if i < len(front_bar_clean) else ""
            bb_skill = back_bar_clean[i] if i < len(back_bar_clean) else ""
            row_y = 96 + i * 32
            draw.text((RIGHT_COL_X, row_y), f"{label} {fb_skill}", fill=TEXT_LIGHT, font=font_body)
            draw.text((BACKBAR_X, row_y), f"{label} {bb_skill}", fill=TEXT_LIGHT, font=font_body)

        # Scribed Skills Definitions
        if scribed_defs:
            scribed_y = 305
            draw.text((RIGHT_COL_X, scribed_y), "SCRIBED SKILLS", fill=GOLD, font=font_header)
            draw.line([(RIGHT_COL_X + 155, scribed_y + 11), (W - 35, scribed_y + 11)], fill=GOLD_DIM, width=1)
            for s_idx, def_text in enumerate(scribed_defs):
                sy = scribed_y + 30 + s_idx * 24
                if ":" in def_text:
                    s_name, s_scripts = def_text.split(":", 1)
                    draw.text((RIGHT_COL_X, sy), f"{s_name}:", fill=GOLD, font=font_body)
                    name_w = text_w(f"{s_name}: ", font_body)
                    draw.text((RIGHT_COL_X + name_w, sy), s_scripts.strip(), fill=TEXT_LIGHT, font=font_body)
                else:
                    draw.text((RIGHT_COL_X, sy), def_text, fill=TEXT_LIGHT, font=font_body)

        # Combat Passives
        draw.text((RIGHT_COL_X, passives_y), "COMBAT PASSIVES", fill=GOLD, font=font_header)
        draw.line([(RIGHT_COL_X + 185, passives_y + 11), (W - 35, passives_y + 11)], fill=GOLD_DIM, width=1)

        col_width = 262
        for idx, (cat, text_val) in enumerate(passives_items):
            col = idx % 3
            row = idx // 3
            px = RIGHT_COL_X + col * col_width
            py = (passives_y + 32) + row * 78
            draw.text((px, py), f"{cat}:", fill=GOLD, font=font_small)
            wrapped = textwrap.wrap(text_val, width=35)
            for w_idx, w_line in enumerate(wrapped[:3]):
                color = TEXT_LIGHT if w_idx == 0 else TEXT_MUTED
                draw.text((px, py + 16 + w_idx * 15), w_line, fill=color, font=font_small)

        out_path = os.path.normpath(out_path)
        parent_dir = os.path.dirname(out_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        with open(out_path, "wb") as f:
            f.write(buf.getvalue())

        self.info_var.set(f"Saved PNG: {os.path.basename(out_path)}")
