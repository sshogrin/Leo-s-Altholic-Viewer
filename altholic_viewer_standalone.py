import ctypes
import json
import re
import time
import tkinter as tk
import sys
import os
import winreg
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter import filedialog, messagebox
from tkinter import font as tkfont
from ctypes import wintypes
from builds_tab import BuildsTab

CONFIG_FILENAME = "LeoAltholicViewer_config.json"

def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller --onefile."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

# Force Windows taskbar to use our custom icon instead of grouping under Python/Tk's feather icon
if sys.platform == "win32":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LeosAltholic.StandaloneViewer.1")
    except Exception:
        pass

def get_windows_documents_dir() -> Path:
    """Queries the Windows Registry to find the true Documents path (handles OneDrive redirection)."""
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            raw_path, _ = winreg.QueryValueEx(key, "Personal")
            expanded_path = os.path.expandvars(raw_path)
            return Path(expanded_path)
    except Exception:
        # Fallback to standard user profile Documents folder
        return Path.home() / "Documents"

def find_eso_saved_vars(filename: str = "LeoAltholic.lua") -> Path | None:
    """Searches NA (live), EU (liveeu), and PTS folders for the target SavedVariables file."""
    docs_dir = get_windows_documents_dir()
    eso_base = docs_dir / "Elder Scrolls Online"
    
    # Check standard live, EU live, and PTS server directories in order
    for server in ("live", "liveeu", "pts"):
        candidate = eso_base / server / "SavedVariables" / filename
        if candidate.is_file():
            return candidate
            
    return None

def get_saved_vars_path() -> Path | None:
    return find_eso_saved_vars("LeoAltholic.lua")

def get_config_path(vars_path: Path | None = None) -> Path:
    """
    Returns the path to LeoAltholicViewer_config.json inside the SavedVariables folder
    so Minion add-on updates never erase user settings.
    """
    # 1. If a specific LeoAltholic.lua path was provided, save right next to it
    if vars_path and vars_path.parent.is_dir():
        return vars_path.parent / CONFIG_FILENAME

    # 2. Otherwise, check if we can auto-detect the ESO SavedVariables folder
    detected_lua = get_saved_vars_path()
    if detected_lua and detected_lua.parent.is_dir():
        return detected_lua.parent / CONFIG_FILENAME

    # 3. Standard default ESO SavedVariables path fallback (even if LeoAltholic.lua isn't created yet)
    default_sv_dir = Path.home() / "Documents" / "Elder Scrolls Online" / "live" / "SavedVariables"
    if default_sv_dir.is_dir():
        return default_sv_dir / CONFIG_FILENAME

    # 4. Final fallback: folder where the .exe (or script) lives (e.g., on a PC without ESO installed)
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
    else:
        app_dir = Path(__file__).resolve().parent
    return app_dir / CONFIG_FILENAME

def _read_config() -> dict:
    """Safely reads the full dictionary from LeoAltholicViewer_config.json."""
    config_file = get_config_path()
    if config_file.is_file():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            # If the saved path points to a custom/network SavedVariables folder,
            # check if a config file also exists in that custom folder and prefer it.
            saved_str = data.get("saved_vars_path")
            if saved_str:
                custom_config = get_config_path(Path(saved_str))
                if custom_config != config_file and custom_config.is_file():
                    return json.loads(custom_config.read_text(encoding="utf-8"))
            return data
        except Exception:
            pass
    return {}

def _write_config(data: dict) -> None:
    """Safely writes the full dictionary to LeoAltholicViewer_config.json."""
    saved_str = data.get("saved_vars_path")
    target_file = get_config_path(Path(saved_str)) if saved_str else get_config_path()
    
    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8"
        )
        
        # If saving to a custom/network folder, also mirror to the default SavedVariables
        # location so the app immediately knows where to find the custom path on next launch.
        default_file = get_config_path()
        if target_file != default_file and default_file.parent.is_dir():
            default_file.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8"
            )
    except Exception:
        pass

def load_saved_config_path() -> Path | None:
    """Reads the saved LeoAltholic.lua path from LeoAltholicViewer_config.json if it exists."""
    saved = _read_config().get("saved_vars_path")
    return Path(saved) if saved else None

def save_config_path(vars_path: Path) -> None:
    """Writes the valid LeoAltholic.lua path to LeoAltholicViewer_config.json without erasing other settings."""
    data = _read_config()
    data["saved_vars_path"] = str(vars_path)
    _write_config(data)

def load_window_geometry(
    win_obj,
    default_width: int = 1240,
    default_height: int = 785,
    key: str = "window"
) -> None:
    """Restores window size and position from config.json under the given key."""
    win = _read_config().get(key, {})
    x = win.get("x")
    y = win.get("y")
    w = win.get("width", default_width)
    h = win.get("height", default_height)

    if x is not None and y is not None:
        v_left = win_obj.winfo_vrootx()
        v_top = win_obj.winfo_vrooty()
        v_right = v_left + win_obj.winfo_vrootwidth()
        v_bottom = v_top + win_obj.winfo_vrootheight()

        if (v_left - 50) <= x <= (v_right - 50) and v_top <= y <= (v_bottom - 50):
            win_obj.geometry(f"{w}x{h}+{x}+{y}")
            return

    win_obj.geometry(f"{default_width}x{default_height}")

def save_window_geometry(win_obj, key: str = "window") -> None:
    """Saves the current window size and position to config.json under the given key."""
    try:
        win_obj.update_idletasks()
        if win_obj.state() == "normal":
            data = _read_config()
            data[key] = {
                "x": win_obj.winfo_x(),
                "y": win_obj.winfo_y(),
                "width": win_obj.winfo_width(),
                "height": win_obj.winfo_height()
            }
            _write_config(data)
    except Exception:
        pass

def load_view_state() -> dict:
    """Restores the last active tab and scroll positions from config.json."""
    return _read_config().get("view_state", {})

def save_view_state(state: dict) -> None:
    """Saves the active tab and scroll positions to config.json."""
    try:
        data = _read_config()
        data["view_state"] = state
        _write_config(data)
    except Exception:
        pass

def load_view_prefs() -> dict:
    """Loads saved server, account, and character sort preferences."""
    data = _read_config()
    server = data.get("selected_server", "ALL")
    sort_mode = data.get("character_sort", "Creation Order NA-EU" if server == "ALL" else "Creation Order")

    # Normalize sort_mode so it always matches the loaded server filter
    if server == "ALL" and sort_mode == "Creation Order":
        sort_mode = "Creation Order NA-EU"
    elif server != "ALL" and sort_mode in ("Creation Order NA-EU", "Creation Order EU-NA"):
        sort_mode = "Creation Order"

    return {
        "server": server,
        "account": data.get("selected_account", "ALL"),
        "sort": sort_mode,
    }

def save_view_prefs(server: str, account: str, sort_mode: str) -> None:
    """Persists the active server, account, and character sort selection."""
    data = _read_config()
    data["selected_server"] = server
    data["selected_account"] = account
    data["character_sort"] = sort_mode
    _write_config(data)

def get_app_version(default="1.0.0"):
    # 1. When running as a compiled .exe, read the embedded Windows FileVersion
    if getattr(sys, "frozen", False):
        try:
            exe_path = sys.executable
            version_dll = ctypes.windll.version
            size = version_dll.GetFileVersionInfoSizeW(exe_path, None)
            if size:
                buf = ctypes.create_string_buffer(size)
                if version_dll.GetFileVersionInfoW(exe_path, 0, size, buf):
                    p_val = ctypes.c_void_p()
                    val_len = wintypes.UINT()
                    # Query the root VS_FIXEDFILEINFO structure
                    if version_dll.VerQueryValueW(buf, "\\", ctypes.byref(p_val), ctypes.byref(val_len)):
                        # VS_FIXEDFILEINFO: dwFileVersionMS is at offset 8, dwFileVersionLS is at offset 12
                        ms = ctypes.c_uint32.from_address(p_val.value + 8).value
                        ls = ctypes.c_uint32.from_address(p_val.value + 12).value
                        major, minor = ms >> 16, ms & 0xFFFF
                        patch, build = ls >> 16, ls & 0xFFFF
                        return f"{major}.{minor}.{patch}" if build == 0 else f"{major}.{minor}.{patch}.{build}"
        except Exception:
            pass

    # 2. When running as a .py script (or fallback), parse FileVersion from version_info.txt
    try:
        vfile = Path(__file__).resolve().parent / "version_info.txt"
        if vfile.exists():
            text = vfile.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r"StringStruct\s*\(\s*['\"]FileVersion['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", text)
            if match:
                return match.group(1).strip()
    except Exception:
        pass

    return default

def parse_lua_table(text):
    text = re.sub(r"--.*", "", text)
    match = re.search(r"LeoAltholicSavedVariables\s*=\s*(\{.*\})", text, re.DOTALL)
    if not match:
        raise ValueError("Could not find LeoAltholicSavedVariables in the file.")
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
            return str_val
        if num_val != "":
            return float(num_val) if "." in num_val else int(num_val)
        if bool_val == "true":
            return True
        if bool_val == "false":
            return False
        return None

    return parse_value()

def format_timer_plain(timestamp):
    if not timestamp or not isinstance(timestamp, (int, float)) or timestamp == 0:
        return "Ready"
    diff = int(timestamp - time.time())
    if diff <= 0:
        return "READY NOW"
    days, rem = divmod(diff, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if mins > 0 or days > 0 or hours > 0:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")
    return " ".join(parts)

def find_nested_dict(d, target_key):
    if not isinstance(d, dict):
        return {}
    if target_key in d and isinstance(d[target_key], dict):
        return d[target_key]
    for val in d.values():
        if isinstance(val, dict):
            found = find_nested_dict(val, target_key)
            if found:
                return found
    return {}

def extract_characters(data):
    chars = []
    if not isinstance(data, dict):
        return chars

    for server, server_data in data.items():
        if not isinstance(server_data, dict):
            continue
        for account, acct_data in server_data.items():
            if not isinstance(acct_data, dict):
                continue
            acct_wide = acct_data.get("$AccountWide", acct_data)
            if not isinstance(acct_wide, dict):
                continue
            char_list = acct_wide.get("CharList", {})
            if isinstance(char_list, dict):
                for char_name, char_info in char_list.items():
                    if isinstance(char_info, dict):
                        char_info["_name"] = char_name
                        char_info["_server"] = server
                        char_info["_account"] = account
                        chars.append(char_info)
    return chars

def extract_banks(raw_data):
    banks = []
    if not isinstance(raw_data, dict):
        return banks

    curr_keys = ("money", "gold", "ap", "telvar", "writVoucher", "writvoucher")

    for server, server_data in raw_data.items():
        if not isinstance(server_data, dict):
            continue
        for account, acct_data in server_data.items():
            if not isinstance(acct_data, dict):
                continue
            acct_wide = acct_data.get("$AccountWide", acct_data)
            if not isinstance(acct_wide, dict):
                continue

            b_curr = {}
            if any(k in acct_wide for k in curr_keys):
                b_curr = acct_wide
            else:
                for sub_key, sub_val in acct_wide.items():
                    if sub_key in ("CharList", "settings", "checklist"):
                        continue
                    if isinstance(sub_val, dict) and any(k in sub_val for k in curr_keys):
                        b_curr = sub_val
                        break
                    if isinstance(sub_val, dict):
                        for deep_val in sub_val.values():
                            if isinstance(deep_val, dict) and any(k in deep_val for k in curr_keys):
                                b_curr = deep_val
                                break
                        if b_curr:
                            break

            if b_curr:
                raw_gold = b_curr.get("money", b_curr.get("gold", 0))
                gold = f"{raw_gold:,}" if isinstance(raw_gold, (int, float)) else "0"
                ap = f"{b_curr.get('ap', 0):,}" if isinstance(b_curr.get("ap"), (int, float)) else "0"
                telvar = f"{b_curr.get('telvar', 0):,}" if isinstance(b_curr.get("telvar"), (int, float)) else "0"
                raw_vouch = b_curr.get("writVoucher", b_curr.get("writvoucher", 0))
                vouchers = f"{raw_vouch:,}" if isinstance(raw_vouch, (int, float)) else "0"
                banks.append({
                    "_server": server,
                    "_account": account,
                    "values": (f"Bank ({server} - {account})", gold, ap, telvar, vouchers),
                })
    return banks

def clean_eso_text(text) -> str:
    if not text:
        return "-"
    cleaned = str(text).strip()
    # Strip ESO hex color codes like |c9af24b and |r
    cleaned = re.sub(r"\|c[0-9a-fA-F]{6}", "", cleaned)
    cleaned = cleaned.replace("|r", "")
    # Strip ESO grammar suffixes like ^p, ^n, ^f, ^m, ^ns, ^np
    cleaned = re.sub(r"\^[a-zA-Z]+", "", cleaned)
    # Strip leading/trailing "Enchantment" labels
    cleaned = re.sub(r"^Enchantment:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+Enchantment$", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    return cleaned if cleaned not in ("", "None") else "-"

def decode_eso_item_link(link_str, saved_trait=None, saved_enchant=None, item_name=""):
    """Uses saved trait/enchant from Lua when available, falling back to link decoding for gear only."""
    name_lower = clean_eso_text(item_name).lower()

    # 1. Block non-equippable items by name first
    non_gear_keywords = (
        "master writ", "sealed ", "recipe:", "diagram:", "design:", "formula:",
        "praxis:", "pattern:", "blueprint:", "sketch:", "motif", "page:",
        "potion", "draught", "sip", "tincture", "elixir", "panacea", "essence of",
        "poison", "damage health", "drain health", "ravage",
        "repair kit", "soul gem", "lockpick", "survey:", "treasure map",
        "transmute geode", "coffer", "box", "crate", "style page",
        "war torte", "torte", "scroll", "mystery verse", "verse",
        "chowder", "bisque", "broth", "porridge", "pudding", "cake", "bread",
        "sugar skulls", "camoran throne", "lava foot", "ghastly eye", "witchmother",
        "artaeum", "bi-stat", "tri-stat", "soup", "stew", "roast", "pie", "tart",
        "fillet", "steak", "brew", "tea", "tonic", "wine", "ale", "beer", "mead", "mazte"
    )
    if any(kw in name_lower for kw in non_gear_keywords):
        return ("-", "-")

    # 2. Block non-equippable items by item link structure (even before checking saved_trait)
    parts = None
    if link_str and "|H" in str(link_str):
        try:
            _, after_h = str(link_str).split("|H", 1)
            core, _ = after_h.split("|h", 1)
            parts = core.split(":")
            if len(parts) >= 5:
                sub_type = int(parts[3]) if parts[3].isdigit() else 0
                item_lvl = int(parts[4]) if parts[4].isdigit() else 0
                if sub_type < 25 or item_lvl == 0:
                    return ("-", "-")
        except Exception:
            parts = None

    # 3. Now safe to use saved Lua trait/enchant for actual gear
    clean_t = clean_eso_text(saved_trait)
    clean_e = clean_eso_text(saved_enchant)
    has_saved_t = clean_t != "-"
    has_saved_e = clean_e != "-"
    if has_saved_t and has_saved_e:
        return (clean_t, clean_e)

    if not parts or len(parts) < 9:
        return (
            clean_t if has_saved_t else "-",
            clean_e if has_saved_e else "-"
        )

    enchant_map = {
        0: "-",
        # Armor Enchants
        26580: "Max Health", 26582: "Max Magicka", 26588: "Max Stamina",
        68343: "Prismatic Defense (Tri-Stat)",
        # Jewelry Enchants
        45831: "Increase Physical Harm", 45832: "Increase Magical Harm",
        45833: "Magicka Recovery", 45834: "Stamina Recovery", 45835: "Health Recovery",
        45869: "Reduce Feat Cost", 45870: "Reduce Spell Cost",
        45871: "Decrease Physical Harm", 45872: "Decrease Spell Harm",
        45873: "Flame Resist", 45874: "Frost Resist", 45875: "Shock Resist",
        45876: "Poison Resist", 45877: "Disease Resist",
        45883: "Bash Damage", 45884: "Shielding",
        45885: "Potion Boost", 45886: "Potion Speed",
        68344: "Prismatic Recovery", 166047: "Reduce Skill Cost",
        # Weapon Enchants
        26848: "Flame Damage", 26849: "Frost Damage", 26850: "Shock Damage",
        26851: "Poison Damage", 26852: "Foulness (Disease)", 26853: "Crushing",
        26854: "Weakening", 26855: "Hardening", 26856: "Decrease Health",
        5364: "Absorb Health", 5365: "Absorb Stamina", 5366: "Absorb Magicka",
        40337: "Weapon/Spell Damage (Berserker)", 68345: "Prismatic Onslaught",
    }

    trait_map = {
        0: "-",
        # Weapons
        1: "Powered", 2: "Charged", 3: "Precise", 4: "Infused", 5: "Defending",
        6: "Training", 7: "Sharpened", 8: "Decisive", 9: "Intricate", 10: "Ornate",
        26: "Nirnhoned",
        # Armor
        11: "Sturdy", 12: "Impenetrable", 13: "Reinforced", 14: "Well-Fitted",
        15: "Training", 16: "Infused", 17: "Invigorating", 18: "Divines",
        19: "Ornate", 20: "Intricate", 25: "Nirnhoned",
        # Jewelry
        21: "Healthy", 22: "Arcane", 23: "Robust", 24: "Ornate", 27: "Intricate",
        28: "Swift", 29: "Harmony", 30: "Triune", 31: "Bloodthirsty",
        32: "Protective", 33: "Infused",
    }

    _, _, _, _, _, ench_raw, _, _, trait_raw, *rest = parts
    ench_id = int(ench_raw) if ench_raw.isdigit() else 0
    trait_id = int(trait_raw) if trait_raw.isdigit() else 0

    # Check secondary/transmuted/monster-helm trait slots (indices 18 and 19 -> rest[9] and rest[10])
    if trait_id == 0:
        for idx in (9, 10):
            if len(rest) > idx and rest[idx].isdigit():
                val = int(rest[idx])
                if val in trait_map and val != 0:
                    trait_id = val
                    break

    enchant_name = enchant_map.get(ench_id, f"Enchant #{ench_id}" if ench_id else "-")
    trait_name = trait_map.get(trait_id, f"Trait #{trait_id}" if trait_id else "-")

    final_trait = clean_t if has_saved_t else trait_name
    final_enchant = clean_e if has_saved_e else enchant_name
    return (final_trait, final_enchant)

def decode_eso_armor_weight(item_name: str, saved_weight=None) -> str:
    """Uses saved weight from Lua when available, falling back to ESO armor piece naming rules."""
    if saved_weight and str(saved_weight).strip() not in ("", "-", "None"):
        return str(saved_weight).strip()

    name_lower = str(item_name or "").lower()
    if not name_lower:
        return "-"

    light_terms = ("robe", "jerkin", "breeches", "shoes", "sash", "epaulets", "hat", "guise", "cowl", "hood", "gloves", "wraps")
    medium_terms = ("jack", "guards", "boots", "belt", "arm cops", "helmet", "visage", "bracers", "cop")
    heavy_terms = ("cuirass", "greaves", "sabatons", "girdle", "pauldrons", "helm", "gauntlets", "plate")

    for term in light_terms:
        if term in name_lower:
            return "Light"
    for term in medium_terms:
        if term in name_lower:
            return "Medium"
    for term in heavy_terms:
        if term in name_lower:
            return "Heavy"

    return "-"

def decode_eso_item_meta(link_str):
    """Returns (quality_label, level_str) from an ESO item link."""
    if not link_str or "|H" not in str(link_str):
        return ("Unknown", "")
    try:
        _, after_h = str(link_str).split("|H", 1)
        core, _ = after_h.split("|h", 1)
        parts = core.split(":")
        sub_type = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
        level = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
    except Exception:
        return ("Unknown", "")

    if sub_type <= 30:
        quality = "Trash"
    elif sub_type <= 359:
        quality = "Normal"
    elif sub_type <= 362:
        quality = "Fine"
    elif sub_type <= 365:
        quality = "Superior"
    elif sub_type <= 369:
        quality = "Epic"
    else:
        quality = "Legendary"

    if level == 50 and sub_type >= 300:
        cp = min(160, (sub_type - 300) * 10) if sub_type >= 350 else 160
        level_str = f"CP {cp}"
    else:
        level_str = f"Lvl {level}" if level > 0 else ""

    return (quality, level_str)

ALLIANCE_COLORS = {
    1: "#FFD700",  # Aldmeri Dominion (Yellow/Gold)
    2: "#FF5555",  # Ebonheart Pact (Red)
    3: "#5599FF",  # Daggerfall Covenant (Blue)
    "Aldmeri Dominion": "#FFD700",
    "Ebonheart Pact": "#FF5555",
    "Daggerfall Covenant": "#5599FF",
}

class AltholicApp:
    def __init__(self, root):
        self.root = root
        self.app_version = get_app_version()
        self.root.title(f"Leo's Altholic - Standalone Viewer v{self.app_version}")
        try:
            ico_file = resource_path("app_icon.ico")
            if os.path.exists(ico_file):
                self.root.iconbitmap(default=ico_file)
        except Exception:
            pass
        # Replace: self.root.geometry("1240x785")
        load_window_geometry(self.root, default_width=1240, default_height=785)
        self.root.minsize(1200, 620)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        
        self.root.configure(bg="#141417")
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LeoAltholic.StandaloneViewer.1.0")
        except Exception:
            pass
        icon_path = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "app_icon.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        self.chars = []
        self.char_alliances = {}
        self.banks = []
        self.raw_data = {}
        self.trees = {}
        self.top_character = ""
        self.text_tabs = []
        self.top_character = ""
        self._restoring_view = False

        self.setup_styles()
        self.build_ui()
        self.saved_vars_path = load_saved_config_path()
        self.load_data()
        self.restore_view_state(load_view_state())
        
        self.current_file_path = None
        self.last_mtime = 0
        self.auto_refresh_enabled = True  # Optional toggle state
        self.check_file_updates()         # Start the background watcher

    def on_close(self) -> None:
        """Saves main and popup window positions before closing."""
        if getattr(self, "inv_win", None) is not None and self.inv_win.winfo_exists():
            save_window_geometry(self.inv_win, key="inventory_window")
        save_window_geometry(self.root, key="window")
        save_view_state(self.capture_view_state())
        self.root.destroy()
        
    def _detect_top_character(self, txt) -> str:
        """Reads the character name at the top-left of the visible Text viewport."""
        try:
            top_index = txt.index("@0,18")
            line_str, _, _ = top_index.partition(".")
            top_line = int(line_str)

            # Walk upward up to 15 lines in case we scrolled mid-way through a multi-line character block
            for ln in range(top_line, max(0, top_line - 15), -1):
                line_text = txt.get(f"{ln}.0", f"{ln}.end")
                if not line_text or line_text.startswith("\t") or line_text.startswith(" "):
                    continue
                first_col, _, _ = line_text.partition("\t")
                name = first_col.strip()
                # Skip separator lines or bank header lines
                if name and not set(name) <= {"-", "=", "_"} and "Bank" not in name:
                    return name
        except Exception:
            pass
        return ""

    def _jump_to_character(self, txt, char_name: str) -> None:
        """Scrolls txt so that char_name's row is flush at the top of the viewport."""
        try:
            if not char_name:
                txt.yview_moveto(0.0)
                return
            # Search specifically for the character name at the start of a column followed by a tab
            pos = txt.search(f"{char_name}\t", "1.0", stopindex="end")
            if pos:
                line_str, _, _ = pos.partition(".")
                line_num = int(line_str)
                # yview(line_num - 1) places that exact line at the top edge
                txt.yview(max(0, line_num - 1))
        except Exception:
            pass

    def on_tab_changed(self, event=None):
        """Synchronizes the newly opened tab to self.top_character."""
        selected_id = self.notebook.select()
        if not selected_id:
            return
        tab_frame = self.notebook.nametowidget(selected_id)

        # Find which registered txt widget belongs to this tab
        target_txt = next((t for t in self.text_tabs if str(t).startswith(str(tab_frame))), None)
        if not target_txt:
            return

        self._restoring_view = True
        def sync_now():
            try:
                self._jump_to_character(target_txt, self.top_character)
            finally:
                self._restoring_view = False

        self.root.after_idle(sync_now)

    def capture_view_state(self) -> dict:
        """Returns the active tab name and the top visible character."""
        last_tab = ""
        if hasattr(self, "notebook"):
            selected_id = self.notebook.select()
            if selected_id:
                last_tab = self.notebook.tab(selected_id, "text")

        return {
            "last_tab": last_tab,
            "top_character": self.top_character,
        }

    def restore_view_state(self, view_state: dict) -> None:
        """Restores the last active tab and scrolls all tabs to top_character."""
        if not isinstance(view_state, dict):
            return

        self._restoring_view = True
        saved_char = view_state.get("top_character", "")
        if isinstance(saved_char, str):
            self.top_character = saved_char

        last_tab = view_state.get("last_tab")
        if last_tab and hasattr(self, "notebook"):
            for tab_id in self.notebook.tabs():
                if self.notebook.tab(tab_id, "text") == last_tab:
                    self.notebook.select(tab_id)
                    break

        def apply_all():
            try:
                for txt in self.text_tabs:
                    self._jump_to_character(txt, self.top_character)
            finally:
                self._restoring_view = False

        self.root.after(50, apply_all)

    def refresh_data(self):
        """Reloads SavedVariables while preserving the active tab and scroll positions."""
        view_state = self.capture_view_state()
        self.load_data()
        self.restore_view_state(view_state)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background="#1e1e24")
        style.configure("Header.TFrame", background="#282520")
        style.configure("Header.TLabel", background="#282520", foreground="#d4af37", font=("Segoe UI", 13, "bold"))
        style.configure("Sub.TLabel", background="#282520", foreground="#a89f91", font=("Segoe UI", 9))

        style.configure("TNotebook", background="#18181c", borderwidth=0)
        style.configure("TNotebook.Tab", background="#18181c", foreground="#a89f91", padding=[14, 8], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#2d2922")], foreground=[("selected", "#d4af37")])

        style.configure("Treeview", background="#1e1e24", foreground="#e2dcd0", fieldbackground="#1e1e24", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#24242b", foreground="#d4af37", font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", "#363127")], foreground=[("selected", "#ffffff")])

    def get_alliance_color(self, char_data, default="#FFFFFF"):
        bio = char_data.get("bio", {}) if isinstance(char_data, dict) else {}
        alliance = bio.get("alliance") or char_data.get("alliance")
        return ALLIANCE_COLORS.get(alliance, default)

    def setup_alliance_tags(self, tree):
        tree.tag_configure("alliance_1", foreground="#FFD700")
        tree.tag_configure("alliance_2", foreground="#FF5555")
        tree.tag_configure("alliance_3", foreground="#5599FF")

    def get_alliance_tag_from_row(self, row):
        # 1. Check explicit char_alliance key first (safe on Combat tab too)
        alliance = row.get("char_alliance")

        # 2. Fall back to row["alliance"] if it's a string or int (not a skill list)
        if alliance is None and not isinstance(row.get("alliance"), (list, dict)):
            alliance = row.get("alliance")

        # 3. Fall back to an app-wide lookup dict if you store one (e.g., self.char_alliances)
        if alliance is None and hasattr(self, "char_alliances"):
            alliance = self.char_alliances.get(row.get("name"))

        val = str(alliance or "").strip().lower()
        if val in ("1", "aldmeri", "aldmeri dominion"):
            return "alliance_1"
        if val in ("2", "pact", "ebonheart", "ebonheart pact"):
            return "alliance_2"
        if val in ("3", "daggerfall", "daggerfall covenant"):
            return "alliance_3"
        return None

    def set_first_col_width(self, txt_widget, new_width):
        widths = list(txt_widget.pixel_widths)
        widths[0] = max(widths[0], new_width)  # Never shrink narrower than the default width

        tab_stops = []
        pos = 0
        for w in widths[:-1]:
            pos += w
            tab_stops.append(pos)
        tabs_tuple = tuple(tab_stops)

        txt_widget.config(tabs=tabs_tuple)
        if hasattr(txt_widget, "hdr_txt"):
            txt_widget.hdr_txt.config(tabs=tabs_tuple)

    def create_uniform_text_tab(self, parent, cols, pixel_widths, font_size=9, line_spacing=8):
        tab_stops = []
        pos = 0
        for w in pixel_widths[:-1]:
            pos += w
            tab_stops.append(pos)
        tabs_tuple = tuple(tab_stops)

        # 1. Frozen 1-line Header Bar (exact same widget type, padding, and tab stops as body)
        hdr_frame = tk.Frame(parent, bg="#24242b")
        hdr_frame.pack(side="top", fill="x")

        hdr_txt = tk.Text(
            hdr_frame, height=1, bg="#24242b", fg="#d4af37", font=("Segoe UI", 10, "bold"),
            padx=10, pady=6, bd=0, highlightthickness=0,
            tabs=tabs_tuple, tabstyle="tabular", wrap="none"
        )
        hdr_txt.insert("1.0", "\t".join(cols))
        hdr_txt.config(state="disabled")
        # Leave space on the right matching the vertical scrollbar width
        hdr_txt.pack(side="left", fill="x", expand=True, padx=(0, 16))

        # 2. Scrollable Body
        body_frame = tk.Frame(parent, bg="#1e1e24")
        body_frame.pack(side="top", fill="both", expand=True)

        vsb = ttk.Scrollbar(body_frame, orient="vertical")
        hsb = ttk.Scrollbar(body_frame, orient="horizontal")

        def on_yscroll(first, last):
            vsb.set(first, last)
            if not getattr(self, "_restoring_view", False) and txt.winfo_ismapped():
                # Ignore (0.0, 1.0) which fires when a table is cleared during refresh
                if not (float(first) == 0.0 and float(last) == 1.0):
                    if float(first) <= 0.001:
                        self.top_character = ""
                    else:
                        found = self._detect_top_character(txt)
                        if found:
                            self.top_character = found

        txt = tk.Text(
            body_frame, bg="#1e1e24", fg="#e2dcd0", font=("Segoe UI", font_size),
            padx=10, pady=4, bd=0, highlightthickness=0,
            spacing1=line_spacing // 2, spacing3=line_spacing // 2,
            tabs=tabs_tuple, tabstyle="tabular",
            state="disabled", wrap="none",
            yscrollcommand=on_yscroll
        )

        # Sync horizontal scrolling across both the frozen header and the body
        def on_xscroll(first, last):
            hsb.set(first, last)
            hdr_txt.xview_moveto(first)

        def on_hbar(*args):
            txt.xview(*args)
            hdr_txt.xview(*args)

        txt.config(xscrollcommand=on_xscroll)
        vsb.config(command=txt.yview)
        hsb.config(command=on_hbar)

        txt.tag_configure("even", background="#1e1e24")
        txt.tag_configure("odd", background="#23232a")
        # Alliance color tags for character names across all tabs
        txt.tag_configure("alliance_1", foreground="#ffd700", font=("Segoe UI", font_size, "bold"))  # Aldmeri (Yellow)
        txt.tag_configure("alliance_2", foreground="#ff4d4d", font=("Segoe UI", font_size, "bold"))  # Pact (Red)
        txt.tag_configure("alliance_3", foreground="#4da6ff", font=("Segoe UI", font_size, "bold"))  # Daggerfall (Blue)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        txt.pack(side="left", fill="both", expand=True)
        txt.hdr_txt = hdr_txt
        txt.pixel_widths = list(pixel_widths)
        if not hasattr(self, "text_tabs"):
            self.text_tabs = []
        self.text_tabs.append(txt)
        return txt


    def build_bio_text(self, parent, cols):
        self.bio_cols = cols
        self.bio_text = self.create_uniform_text_tab(parent, cols, list((180, 110, 130, 145, 220)))
        self.bio_text.tag_configure("maxed", foreground="#4dff88", font=("Segoe UI", 9, "bold"))
        self.bio_text.tag_configure("sub50", foreground="#8c9eff", font=("Segoe UI", 9, "bold"))        # Lighter blue-violet for Lvl 1-49

        # Champion Point tier tags (matching Champion tab)
        self.bio_text.tag_configure("cp_gold", foreground="#d4af37", font=("Segoe UI", 9, "bold"))     # 3600+
        self.bio_text.tag_configure("cp_yellow", foreground="#ffd700", font=("Segoe UI", 9, "bold"))   # 3000-3599
        self.bio_text.tag_configure("cp_blue", foreground="#4da6ff", font=("Segoe UI", 9, "bold"))     # 1400-2999
        self.bio_text.tag_configure("cp_green", foreground="#4dff88", font=("Segoe UI", 9, "bold"))    # 800-1399
        self.bio_text.tag_configure("cp_red", foreground="#ff4d4d", font=("Segoe UI", 9, "bold"))      # 1-799

        # Class color tags
        self.bio_text.tag_configure("cls_dk", foreground="#ff8c1a", font=("Segoe UI", 9, "bold"))       # Dragonknight: Orange
        self.bio_text.tag_configure("cls_warden", foreground="#4da6ff", font=("Segoe UI", 9, "bold"))   # Warden: Blue
        self.bio_text.tag_configure("cls_nb", foreground="#ff4d4d", font=("Segoe UI", 9, "bold"))       # Nightblade: Red
        self.bio_text.tag_configure("cls_sorc", foreground="#b366ff", font=("Segoe UI", 9, "bold"))     # Sorcerer: Purple
        self.bio_text.tag_configure("cls_arc", foreground="#4dff88", font=("Segoe UI", 9, "bold"))      # Arcanist: Green
        self.bio_text.tag_configure("cls_temp", foreground="#ffd700", font=("Segoe UI", 9, "bold"))     # Templar: Yellow
        self.bio_text.tag_configure("cls_necro", foreground="#33ffff", font=("Segoe UI", 9, "bold"))    # Necromancer: Cyan

    def populate_bio_text(self, bio_rows):
        self.bio_text.config(state="normal")
        self.bio_text.delete("1.0", "end")
        # self.bio_text.insert("end", "\t".join(self.bio_cols) + "\n", ("header",))

        class_tag_map = {
            "dragonknight": "cls_dk",
            "warden": "cls_warden",
            "nightblade": "cls_nb",
            "sorcerer": "cls_sorc",
            "arcanist": "cls_arc",
            "templar": "cls_temp",
            "necromancer": "cls_necro",
        }

        def get_level_tag(level_text):
            s = str(level_text or "").strip().upper()
            if s.startswith("LVL "):
                return "sub50"
            if "CP" in s:
                digits = "".join(ch for ch in s if ch.isdigit())
                cp_val = int(digits) if digits else 0
                if cp_val >= 3600:
                    return "cp_gold"
                if cp_val >= 3000:
                    return "cp_yellow"
                if cp_val >= 1400:
                    return "cp_blue"
                if cp_val >= 800:
                    return "cp_green"
                if cp_val >= 1:
                    return "cp_red"
            return None

        for row_idx, row in enumerate(bio_rows):
            row_tag = "even" if row_idx % 2 == 0 else "odd"
            
            # Get alliance tag for the character name only
            alliance_tag = self.get_alliance_tag_from_row(row)
            name_tags = (row_tag, alliance_tag) if alliance_tag else (row_tag,)

            cls_raw = str(row["class"])
            cls_tag = class_tag_map.get(cls_raw.strip().lower())

            lvl_str = str(row["level"])
            lvl_tag = get_level_tag(lvl_str)
            lvl_tags = (row_tag, lvl_tag) if lvl_tag else (row_tag,)

            self.bio_text.insert("end", f"{row['name']}\t", name_tags)
            self.bio_text.insert("end", f"{lvl_str}\t", lvl_tags)
            self.bio_text.insert("end", f"{row['race']}\t", (row_tag,))
            self.bio_text.insert("end", cls_raw, (row_tag, cls_tag) if cls_tag else (row_tag,))
            self.bio_text.insert("end", f"\t{row['spd']}/{row['stam']}/{row['cap']} ", (row_tag,))

            status_str = f"({row['status']})\n"
            if row["status"] == "MAXED":
                self.bio_text.insert("end", status_str, (row_tag, "maxed"))
            else:
                self.bio_text.insert("end", status_str, (row_tag,))

        self.bio_text.config(state="disabled")

    def build_stats_grid(self, parent, cols):
        self.stats_cols = cols
        self.stats_text = self.create_uniform_text_tab(parent, cols, list((180, 155, 115, 115, 115, 165, 145)))
        self.stats_text.tag_configure("mag", foreground="#4da6ff", font=("Segoe UI", 9, "bold"))
        self.stats_text.tag_configure("stam", foreground="#4dff88", font=("Segoe UI", 9, "bold"))
        self.stats_text.tag_configure("hp", foreground="#ff4d4d", font=("Segoe UI", 9, "bold"))

    def populate_stats_grid(self, stats_rows):
        self.stats_text.config(state="normal")
        self.stats_text.delete("1.0", "end")
        # self.stats_text.insert("end", "\t".join(self.stats_cols) + "\n", ("header",))

        def fmt_num(val):
            return f"{val:,}" if isinstance(val, (int, float)) else str(val)

        for row_idx, row in enumerate(stats_rows):
            row_tag = "even" if row_idx % 2 == 0 else "odd"
            
            # Get alliance tag for the character name only
            alliance_tag = self.get_alliance_tag_from_row(row)
            name_tags = (row_tag, alliance_tag) if alliance_tag else (row_tag,)

            segments = [
                (f"{row['name']}\t", name_tags),
                (str(row["pts_mag"]), (row_tag, "mag")), (" / ", (row_tag,)),
                (str(row["pts_stam"]), (row_tag, "stam")), (" / ", (row_tag,)),
                (f"{row['pts_hp']}\t", (row_tag, "hp")),
                (f"{fmt_num(row['max_hp'])}\t", (row_tag, "hp")),
                (f"{fmt_num(row['max_mag'])}\t", (row_tag, "mag")),
                (f"{fmt_num(row['max_stam'])}\t", (row_tag, "stam")),
                (str(row["rec_mag"]), (row_tag, "mag")), (" / ", (row_tag,)),
                (str(row["rec_stam"]), (row_tag, "stam")), (" / ", (row_tag,)),
                (f"{row['rec_hp']}\t", (row_tag, "hp")),
                (f"{row['crit']}\n", (row_tag,)),
            ]
            for text, tags in segments:
                self.stats_text.insert("end", text, tags)

        self.stats_text.config(state="disabled")

    def build_champion_text(self, parent, cols):
        self.champion_cols = cols
        self.champion_text = self.create_uniform_text_tab(parent, cols, list((180, 110, 135, 135, 135)))
        self.champion_text.tag_configure("cp_gold", foreground="#d4af37", font=("Segoe UI", 9, "bold"))     # 3600+
        self.champion_text.tag_configure("cp_yellow", foreground="#ffd700", font=("Segoe UI", 9, "bold"))   # 3000-3599
        self.champion_text.tag_configure("cp_blue", foreground="#4da6ff", font=("Segoe UI", 9, "bold"))     # 1400-2999 & Warfare
        self.champion_text.tag_configure("cp_green", foreground="#4dff88", font=("Segoe UI", 9, "bold"))    # 800-1399 & Craft
        self.champion_text.tag_configure("cp_red", foreground="#ff4d4d", font=("Segoe UI", 9, "bold"))      # 1-799 & Fitness

    def populate_champion_text(self, champion_rows):
        self.champion_text.config(state="normal")
        self.champion_text.delete("1.0", "end")
        # self.champion_text.insert("end", "\t".join(self.champion_cols) + "\n", ("header",))

        def get_total_tag(val):
            try:
                num = int(val)
            except (ValueError, TypeError):
                return None
            if num >= 3600: return "cp_gold"
            if 3000 <= num <= 3599: return "cp_yellow"
            if 1400 <= num <= 2999: return "cp_blue"
            if 800 <= num <= 1399: return "cp_green"
            if 1 <= num <= 799: return "cp_red"
            return None

        for row_idx, row in enumerate(champion_rows):
            row_tag = "even" if row_idx % 2 == 0 else "odd"
            
            # Get alliance tag for the character name only
            alliance_tag = self.get_alliance_tag_from_row(row)
            name_tags = (row_tag, alliance_tag) if alliance_tag else (row_tag,)

            tot_tag = get_total_tag(row["total"])
            self.champion_text.insert("end", f"{row['name']}\t", name_tags)
            self.champion_text.insert("end", f"{row['total']}\t", (row_tag, tot_tag) if tot_tag else (row_tag,))
            self.champion_text.insert("end", f"{row['warfare']}\t", (row_tag, "cp_blue"))
            self.champion_text.insert("end", f"{row['fitness']}\t", (row_tag, "cp_red"))
            self.champion_text.insert("end", f"{row['craft']}\n", (row_tag, "cp_green"))

        self.champion_text.config(state="disabled")

    def build_combat_text(self, parent, cols):
        self.combat_cols = cols
        self.combat_text = self.create_uniform_text_tab(
            parent, cols, list((175, 195, 195, 165, 195, 185, 130)), line_spacing=4
        )
        # Class skill line colors + Gold for Class Mastery
        self.combat_text.tag_configure("cls_dk", foreground="#ff8c1a", font=("Segoe UI", 9, "bold"))     # Dragonknight: Orange
        self.combat_text.tag_configure("cls_warden", foreground="#4da6ff", font=("Segoe UI", 9, "bold")) # Warden: Blue
        self.combat_text.tag_configure("cls_nb", foreground="#ff4d4d", font=("Segoe UI", 9, "bold"))     # Nightblade: Red
        self.combat_text.tag_configure("cls_sorc", foreground="#b366ff", font=("Segoe UI", 9, "bold"))   # Sorcerer: Purple
        self.combat_text.tag_configure("cls_arc", foreground="#4dff88", font=("Segoe UI", 9, "bold"))    # Arcanist: Green
        self.combat_text.tag_configure("cls_temp", foreground="#ffd700", font=("Segoe UI", 9, "bold"))   # Templar: Yellow
        self.combat_text.tag_configure("cls_necro", foreground="#33ffff", font=("Segoe UI", 9, "bold"))  # Necromancer: Cyan
        self.combat_text.tag_configure("cls_mastery", foreground="#d4af37", font=("Segoe UI", 9, "bold"))# Class Mastery: Gold
        # Antiquarian Insight passive rank colors (1=Green, 2=Blue, 3=Purple, 4=Yellow, 5=Orange)
        self.combat_text.tag_configure("antiq_1", foreground="#4dff88", font=("Segoe UI", 9, "bold"))  # 1 pt: Green
        self.combat_text.tag_configure("antiq_2", foreground="#4da6ff", font=("Segoe UI", 9, "bold"))  # 2 pts: Blue
        self.combat_text.tag_configure("antiq_3", foreground="#b366ff", font=("Segoe UI", 9, "bold"))  # 3 pts: Purple
        self.combat_text.tag_configure("antiq_4", foreground="#ffd700", font=("Segoe UI", 9, "bold"))  # 4 pts: Yellow
        self.combat_text.tag_configure("antiq_5", foreground="#ff8c1a", font=("Segoe UI", 9, "bold"))  # 5 pts: Orange
        # Rank number color tags
        self.combat_text.tag_configure("rk_green", foreground="#4dff88", font=("Segoe UI", 9, "bold"))
        self.combat_text.tag_configure("rk_blue", foreground="#4da6ff", font=("Segoe UI", 9, "bold"))
        self.combat_text.tag_configure("rk_yellow", foreground="#ffd700", font=("Segoe UI", 9, "bold"))
        self.combat_text.tag_configure("rk_red", foreground="#ff4d4d", font=("Segoe UI", 9, "bold"))

    def populate_combat_text(self, combat_rows):
        self.combat_text.config(state="normal")
        self.combat_text.delete("1.0", "end")
        # self.combat_text.insert("end", "\t".join(self.combat_cols) + "\n", ("header",))

        skill_class_tag = {
            # Dragonknight (Orange)
            "ardent flame": "cls_dk", "draconic power": "cls_dk", "earthen heart": "cls_dk",
            # Warden (Blue)
            "animal companions": "cls_warden", "green balance": "cls_warden", "winter's embrace": "cls_warden",
            # Nightblade (Red)
            "assassination": "cls_nb", "shadow": "cls_nb", "siphoning": "cls_nb",
            # Sorcerer (Purple)
            "dark magic": "cls_sorc", "daedric summoning": "cls_sorc", "storm calling": "cls_sorc",
            # Arcanist (Green)
            "herald of the tome": "cls_arc", "soldier of apocrypha": "cls_arc", "curative runeforms": "cls_arc",
            # Templar (Yellow)
            "aedric spear": "cls_temp", "dawn's wrath": "cls_temp", "restoring light": "cls_temp",
            # Necromancer (Cyan)
            "grave lord": "cls_necro", "bone tyrant": "cls_necro", "living death": "cls_necro",
        }

        # Map non-50 skill lines to their true max rank (everything else defaults to 50)
        max_rank_map = {
            # Max 20
            "legerdemain": 20,
            # Max 12
            "thieves guild": 12,
            "dark brotherhood": 12,
            # Max 10
            "fighters guild": 10,
            "mages guild": 10,
            "undaunted": 10,
            "psijic order": 10,
            "vampire": 10,
            "werewolf": 10,
            "excavation": 10,
            "scrying": 10,
            "emperor": 10,
            "assault": 10,
            "support": 10,
            # Max 6
            "soul magic": 6,
        }

        def get_rank_color_tag(skill_name, rank_str):
            digits = "".join(ch for ch in rank_str if ch.isdigit())
            if not digits:
                return None
            r = int(digits)
            if r <= 0:
                return None
            
            low = skill_name.strip().lower()
            if "mastery" in low:
                return "cls_mastery"

            cap = max_rank_map.get(skill_name.strip().lower(), 50)

            if cap == 50:
                if r >= 50: return "rk_green"
                if 20 <= r <= 49: return "rk_blue"
                if 2 <= r <= 19: return "rk_yellow"
                return "rk_red"
            if cap == 20:
                if r >= 20: return "rk_green"
                if 6 <= r <= 19: return "rk_blue"
                if 2 <= r <= 5: return "rk_yellow"
                return "rk_red"
            elif cap == 12:
                if r >= 12: return "rk_green"
                if 6 <= r <= 11: return "rk_blue"
                if 2 <= r <= 5: return "rk_yellow"
                return "rk_red"
            elif cap == 10:
                if r >= 10: return "rk_green"
                if 5 <= r <= 9: return "rk_blue"
                if 2 <= r <= 4: return "rk_yellow"
                return "rk_red"
            elif cap == 6:
                if r >= 6: return "rk_green"
                if 2 <= r <= 5: return "rk_blue"
                return "rk_red"
            return None

        for row_idx, row in enumerate(combat_rows):
            row_tag = "even" if row_idx % 2 == 0 else "odd"
            alliance_tag = self.get_alliance_tag_from_row(row)
            antiq_rank = row.get("antiq_rank", 0)

            cols_data = [
                [(row["name"], "")],
                row["class"],
                row["weapon"],
                row["armor"],
                row["guild"],
                row["world"],
                row["alliance"],
            ]
            max_lines = max(len(c) for c in cols_data)

            for line_i in range(max_lines):
                for col_i in range(7):
                    sep = "\n" if col_i == 6 else "\t"
                    if line_i < len(cols_data[col_i]):
                        sname, srank = cols_data[col_i][line_i]

                        # 0. Character Name column gets alliance color
                        if col_i == 0:
                            name_tags = (row_tag, alliance_tag) if alliance_tag else (row_tag,)
                        # 1. Skill Name color (Class column gets class/mastery colors)
                        elif col_i == 1:
                            low = sname.strip().lower()
                            c_tag = "cls_mastery" if "mastery" in low else skill_class_tag.get(low)
                            name_tags = (row_tag, c_tag) if c_tag else (row_tag,)
                        # 5. World column: Scrying & Excavation colored by Antiquarian Insight rank (1-5)
                        elif col_i == 5 and sname.strip().lower() in ("scrying", "excavation") and 1 <= antiq_rank <= 5:
                            name_tags = (row_tag, f"antiq_{antiq_rank}")
                        else:
                            name_tags = (row_tag,)

                        self.combat_text.insert("end", sname, name_tags)

                        # 2. Rank Number color (Columns 1-6)
                        if col_i >= 1 and srank:
                            rk_tag = get_rank_color_tag(sname, srank)
                            rank_tags = (row_tag, rk_tag) if rk_tag else (row_tag,)
                            self.combat_text.insert("end", srank + sep, rank_tags)
                        else:
                            self.combat_text.insert("end", srank + sep, (row_tag,))
                    else:
                        self.combat_text.insert("end", sep, (row_tag,))

            # Subtle divider row between characters
            self.combat_text.insert("end", "\t\t\t\t\t\t\n", (row_tag,))

        self.combat_text.config(state="disabled")
        
    def build_craft_text(self, parent, cols):
        self.craft_cols = cols
        self.craft_text = self.create_uniform_text_tab(parent, cols, list((180, 115, 130, 115, 120, 115, 125, 125)))
        self.craft_text.tag_configure("rank_green", foreground="#4dff88", font=("Segoe UI", 9, "bold"))
        self.craft_text.tag_configure("rank_yellow", foreground="#ffd700", font=("Segoe UI", 9, "bold"))
        self.craft_text.tag_configure("rank_blue", foreground="#4da6ff", font=("Segoe UI", 9, "bold"))
        self.craft_text.tag_configure("rank_red", foreground="#ff4d4d", font=("Segoe UI", 9, "bold"))
        
    def populate_craft_text(self, craft_rows):
        self.craft_text.config(state="normal")
        self.craft_text.delete("1.0", "end")
        # self.craft_text.insert("end", "\t".join(self.craft_cols) + "\n", ("header",))

        prof_keys = list(("Alchemy", "Blacksmithing", "Clothing", "Enchanting", "Jewelry Crafting", "Provisioning", "Woodworking"))

        def get_rank_tag(rank_num):
            if not isinstance(rank_num, int) or rank_num <= 0: return None
            if rank_num >= 50: return "rank_green"
            if 40 <= rank_num <= 49: return "rank_yellow"
            if 20 <= rank_num <= 39: return "rank_blue"
            if 5 <= rank_num <= 19: return "rank_yellow"
            return "rank_red"

        for row_idx, row in enumerate(craft_rows):
            row_tag = "even" if row_idx % 2 == 0 else "odd"

            # Get alliance tag for the character name only
            alliance_tag = self.get_alliance_tag_from_row(row)
            name_tags = (row_tag, alliance_tag) if alliance_tag else (row_tag,)

            self.craft_text.insert("end", f"{row['name']}\t", name_tags)
            for idx, pk in enumerate(prof_keys):
                rank_num = row["ranks"].get(pk)
                label = f"Rank {rank_num}" if isinstance(rank_num, int) else "-"
                sep = "\n" if idx == len(prof_keys) - 1 else "\t"
                r_tag = get_rank_tag(rank_num)
                self.craft_text.insert("end", label + sep, (row_tag, r_tag) if r_tag else (row_tag,))

        self.craft_text.config(state="disabled")

    def build_currency_text(self, parent, cols):
        self.currency_cols = cols
        self.currency_text = self.create_uniform_text_tab(
            parent, cols, list((210, 155, 165, 155, 155))
        )

        # Bank highlight + Currency column colors
        self.currency_text.tag_configure("bank_row", background="#282520", foreground="#d4af37", font=("Segoe UI", 10, "bold"))
        self.currency_text.tag_configure("cur_gold", foreground="#d4af37", font=("Segoe UI", 9, "bold"))   # Gold
        self.currency_text.tag_configure("cur_ap", foreground="#4dff88", font=("Segoe UI", 9, "bold"))     # Green
        self.currency_text.tag_configure("cur_telvar", foreground="#4da6ff", font=("Segoe UI", 9, "bold")) # Blue
        self.currency_text.tag_configure("cur_writ", foreground="#d2b48c", font=("Segoe UI", 9, "bold"))   # Tan

    def populate_currency_text(self, bank_rows, currency_rows):
        # Measure the widest bank label or character name in column 0
        measure_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        all_labels = [str(b)[0] for b in bank_rows] + [str(r.get("name", "")) for r in currency_rows]
        max_px = max((measure_font.measure(lbl) for lbl in all_labels), default=160) + 24
        self.set_first_col_width(self.currency_text, max_px)
        
        self.currency_text.config(state="normal")
        self.currency_text.delete("1.0", "end")

        # 1. Bank rows pinned at the top of the Currency tab
        for b_vals in bank_rows:
            bank_label, gold_str, ap_str, telvar_str, writ_str = b_vals
            self.currency_text.insert("end", f"{bank_label}\t", ("bank_row",))
            self.currency_text.insert("end", f"{gold_str}\t", ("bank_row", "cur_gold"))
            self.currency_text.insert("end", f"{ap_str}\t", ("bank_row", "cur_ap"))
            self.currency_text.insert("end", f"{telvar_str}\t", ("bank_row", "cur_telvar"))
            self.currency_text.insert("end", f"{writ_str}\n", ("bank_row", "cur_writ"))

        # 2. Character currency rows
        for row_idx, row in enumerate(currency_rows):
            row_tag = "even" if row_idx % 2 == 0 else "odd"

            # Get alliance tag for the character name only
            alliance_tag = self.get_alliance_tag_from_row(row)
            name_tags = (row_tag, alliance_tag) if alliance_tag else (row_tag,)

            self.currency_text.insert("end", f"{row['name']}\t", name_tags)
            self.currency_text.insert("end", f"{row['gold']}\t", (row_tag, "cur_gold"))
            self.currency_text.insert("end", f"{row['ap']}\t", (row_tag, "cur_ap"))
            self.currency_text.insert("end", f"{row['telvar']}\t", (row_tag, "cur_telvar"))
            self.currency_text.insert("end", f"{row['writ']}\n", (row_tag, "cur_writ"))

        self.currency_text.config(state="disabled")

    def build_research_text(self, parent, cols):
        self.research_cols = cols
        self.research_text = self.create_uniform_text_tab(parent, cols, list((180, 260, 260, 260, 260)), line_spacing=4)
        self.research_text.tag_configure("completed", foreground="#4dff88", font=("Segoe UI", 9, "bold"))
        self.research_text.tag_configure("ready", foreground="#ff4d4d", font=("Segoe UI", 9, "bold"))
        
    def render_res_cell_live(self, cell_data):
        if isinstance(cell_data, str):
            return cell_data
        known, tot = cell_data["known"], cell_data["tot"]
        if cell_data["completed"]:
            return f"COMPLETED ({known}/{tot})"

        hdr = f"[{known}/{tot} traits]"
        timers = cell_data["timers"]
        if not timers:
            return f"{hdr} - READY NOW"

        lines = [hdr]
        for label, done_at in timers:
            lines.append(f"{label}: {format_timer_plain(done_at)}")
        return "\n".join(lines)
    
    def populate_research_text(self, research_rows):
        self.last_research_rows = research_rows

        y_pos = self.research_text.yview()
        x_pos = self.research_text.xview()

        self.research_text.config(state="normal")
        self.research_text.delete("1.0", "end")

        for row_idx, row in enumerate(research_rows):
            row_tag = "even" if row_idx % 2 == 0 else "odd"

            alliance_tag = self.get_alliance_tag_from_row(row)
            name_tags = (row_tag, alliance_tag) if alliance_tag else (row_tag,)

            col_lines = [
                [str(row["name"])],
                self.render_res_cell_live(row["bs"]).split("\n"),
                self.render_res_cell_live(row["cl"]).split("\n"),
                self.render_res_cell_live(row["ww"]).split("\n"),
                self.render_res_cell_live(row["jw"]).split("\n"),
            ]
            max_lines = max(len(lines) for lines in col_lines)
            for line_i in range(max_lines):
                for col_i in range(5):
                    text_part = col_lines[col_i][line_i] if line_i < len(col_lines[col_i]) else ""
                    sep = "\n" if col_i == 4 else "\t"

                    if col_i == 0 and text_part:
                        self.research_text.insert("end", text_part + sep, name_tags)
                    elif text_part.startswith("COMPLETED"):
                        self.research_text.insert("end", text_part + sep, (row_tag, "completed"))
                    elif "READY NOW" in text_part:
                        before, _, after = text_part.partition("READY NOW")
                        if before:
                            self.research_text.insert("end", before, (row_tag,))
                        self.research_text.insert("end", "READY NOW", (row_tag, "ready"))
                        self.research_text.insert("end", after + sep, (row_tag,))
                    else:
                        self.research_text.insert("end", text_part + sep, (row_tag,))

            self.research_text.insert("end", "\t\t\t\t\n", (row_tag,))

        self.research_text.config(state="disabled")

        self.research_text.yview_moveto(y_pos[0])
        self.research_text.xview_moveto(x_pos[0])

        if getattr(self, "_research_tick_id", None):
            self.root.after_cancel(self._research_tick_id)
        self._research_tick_id = self.root.after(1000, lambda: self.populate_research_text(self.last_research_rows))

    def build_inventory_text(self, parent, cols):
        self.inventory_cols = cols
        self.inventory_text = self.create_uniform_text_tab(
            parent, cols, list((200, 140, 820))
        )

        # Bag space fullness color tags
        self.inventory_text.tag_configure("bag_green", foreground="#4dff88", font=("Segoe UI", 9, "bold"))
        self.inventory_text.tag_configure("bag_yellow", foreground="#ffd700", font=("Segoe UI", 9, "bold"))
        self.inventory_text.tag_configure("bag_red", foreground="#ff4d4d", font=("Segoe UI", 9, "bold"))

    def populate_inventory_text(self, inventory_rows):
        self.inventory_text.config(state="normal")
        self.inventory_text.delete("1.0", "end")

        def get_bag_tag(used, size):
            if not isinstance(used, (int, float)) or not isinstance(size, (int, float)) or size <= 0:
                return None
            free = size - used
            if free <= 5:
                return "bag_red"
            if free <= 15:
                return "bag_yellow"
            return "bag_green"

        for row_idx, row in enumerate(inventory_rows):
            row_tag = "even" if row_idx % 2 == 0 else "odd"

            # Get alliance tag for the character name only
            alliance_tag = self.get_alliance_tag_from_row(row)
            name_tags = (row_tag, alliance_tag) if alliance_tag else (row_tag,)

            bag_tag = get_bag_tag(row["used"], row["size"])
            bag_tags = (row_tag, bag_tag) if bag_tag else (row_tag,)

            self.inventory_text.insert("end", f"{row['name']}\t", name_tags)
            self.inventory_text.insert("end", f"{row['bag_str']}\t", bag_tags)

            bag_items = row["bag_items"]
            worn_items = row["worn_items"]
            if bag_items or worn_items:
                btn = tk.Button(
                    self.inventory_text,
                    text=f"View Items (Bag: {len(bag_items)} | Worn: {len(worn_items)})",
                    command=lambda n=row["name"], b=row["bag_str"], bi=bag_items, wi=worn_items: self.open_inventory_popup(n, b, bi, wi),
                    bg="#2d2922", fg="#d4af37", activebackground="#3d372e", activeforeground="#ffffff",
                    relief="solid", bd=1, padx=8, pady=0, font=("Segoe UI", 8, "bold"), cursor="hand2"
                )
                self.inventory_text.window_create("end", window=btn, pady=2)
                self.inventory_text.insert("end", "\n", (row_tag,))
            else:
                self.inventory_text.insert("end", "Bag slot counts only\n", (row_tag,))

        self.inventory_text.config(state="disabled")

    def open_inventory_popup(self, char_name, bag_str, bag_items, worn_items):
        # If an inventory popup is already open, save its spot and close it first
        if getattr(self, "inv_win", None) is not None and self.inv_win.winfo_exists():
            save_window_geometry(self.inv_win, key="inventory_window")
            self.inv_win.destroy()

        win = tk.Toplevel(self.root)
        self.inv_win = win
        win.title(f"{char_name} - Gear & Inventory ({bag_str})")
        load_window_geometry(win, default_width=860, default_height=520, key="inventory_window")
        win.configure(bg="#141417")
        win.transient(self.root)

        def on_inv_close():
            save_window_geometry(win, key="inventory_window")
            self.inv_win = None
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_inv_close)
        win.bind("<Escape>", lambda event: on_inv_close())

        # Header & Live Search Filter Bar
        top = tk.Frame(win, bg="#282520", padx=12, pady=10)
        top.pack(fill="x")

        tk.Label(
            top, text=f"{char_name.upper()}  ({bag_str})",
            bg="#282520", fg="#d4af37", font=("Segoe UI", 11, "bold")
        ).pack(side="left")

        search_var = tk.StringVar()
        search_entry = tk.Entry(
            top, textvariable=search_var, bg="#1e1e24", fg="#e2dcd0",
            insertbackground="#d4af37", relief="solid", bd=1, width=26, font=("Segoe UI", 9)
        )
        search_entry.pack(side="right")
        tk.Label(top, text="Filter (Item / Weight / Trait / Enchant):", bg="#282520", fg="#a89f91", font=("Segoe UI", 9)).pack(side="right", padx=(0, 6))

        # Two-Tab Notebook: Inventory (Backpack) & Equipped (Worn)
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=12, pady=12)

        bag_frame = ttk.Frame(nb)
        worn_frame = ttk.Frame(nb)
        nb.add(bag_frame, text=f"Inventory ({len(bag_items)})")
        nb.add(worn_frame, text=f"Equipped ({len(worn_items)})")

        col_headers = ["Item Name", "Weight", "Trait", "Enchantment", "Qty"]
        col_widths = [270, 80, 125, 225, 65]

        def configure_gear_tags(txt_widget, qty_color):
            txt_widget.tag_configure("w_light", foreground="#66d9ff", font=("Segoe UI", 9, "bold"))
            txt_widget.tag_configure("w_medium", foreground="#77dd77", font=("Segoe UI", 9, "bold"))
            txt_widget.tag_configure("w_heavy", foreground="#ffb347", font=("Segoe UI", 9, "bold"))
            txt_widget.tag_configure("trait", foreground="#33ffff", font=("Segoe UI", 9, "bold"))
            txt_widget.tag_configure("ench", foreground="#ffd700", font=("Segoe UI", 9))
            txt_widget.tag_configure("qty", foreground=qty_color, font=("Segoe UI", 9, "bold"))

        bag_txt = self.create_uniform_text_tab(bag_frame, col_headers, col_widths, font_size=9, line_spacing=6)
        configure_gear_tags(bag_txt, "#4da6ff")

        worn_txt = self.create_uniform_text_tab(worn_frame, col_headers, col_widths, font_size=9, line_spacing=6)
        configure_gear_tags(worn_txt, "#4dff88")

        weight_tag_map = {
            "Light": "w_light",
            "Medium": "w_medium",
            "Heavy": "w_heavy",
        }

        def fill_tab(txt_widget, items, query):
            txt_widget.config(state="normal")
            txt_widget.delete("1.0", "end")
            shown = 0
            for item_tuple in items:
                iname, icount, itrait, iench, iweight = item_tuple
                if query and (
                    query not in iname.lower()
                    and query not in iweight.lower()
                    and query not in itrait.lower()
                    and query not in iench.lower()
                ):
                    continue
                r_tag = "even" if shown % 2 == 0 else "odd"
                w_tag = weight_tag_map.get(iweight)
                txt_widget.insert("end", f"{iname}\t", (r_tag,))
                txt_widget.insert("end", f"{iweight}\t", (r_tag, w_tag) if w_tag else (r_tag,))
                txt_widget.insert("end", f"{itrait}\t", (r_tag, "trait") if itrait != "-" else (r_tag,))
                txt_widget.insert("end", f"{iench}\t", (r_tag, "ench") if iench != "-" else (r_tag,))
                txt_widget.insert("end", f"x{icount}\n", (r_tag, "qty"))
                shown += 1
            if shown == 0:
                txt_widget.insert("end", "No items found.\n", ("even",))
            txt_widget.config(state="disabled")

        def render_all(*args):
            q = search_var.get().strip().lower()
            fill_tab(bag_txt, bag_items, q)
            fill_tab(worn_txt, worn_items, q)

        search_var.trace_add("write", render_all)
        render_all()
        search_entry.focus_set()
 
    def sync_sort_options(self):
        selected_server = self.server_var.get()
        current_sort = self.sort_var.get()

        if selected_server == "ALL":
            options = ["Creation Order NA-EU", "Creation Order EU-NA", "Name (A-Z)", "Name (Z-A)"]
            if current_sort == "Creation Order":
                self.sort_var.set("Creation Order NA-EU")
        else:
            options = ["Creation Order", "Name (A-Z)", "Name (Z-A)"]
            if current_sort in ("Creation Order NA-EU", "Creation Order EU-NA"):
                self.sort_var.set("Creation Order")

        self.sort_combo["values"] = options

    def on_filter_changed(self, event=None):
        self.sync_sort_options()
        save_view_prefs(
            self.server_var.get(),
            self.account_var.get(),
            self.sort_var.get(),
        )
        self.refresh_tables()
        if hasattr(self, "writ_timer_label"):
            self.update_writ_timer()
            
    def _get_active_writ_server(self):
        """Detects whether the currently viewed server/account is NA or EU."""
        if hasattr(self, "server_combo"):
            val = self.server_combo.get().upper()
            if "EU" in val:
                return "EU"
            if "NA" in val:
                return "NA"

        if hasattr(self, "account_combo"):
            val = self.account_combo.get().upper()
            if "EU" in val:
                return "EU"
            if "NA" in val:
                return "NA"

        return "ALL"

    def build_writs_text(self, parent, cols):
        self.writs_cols = cols
        self.writs_text = self.create_uniform_text_tab(parent, cols, [180, 105, 115, 105, 105, 105, 110, 115])
        self.writs_text.tag_configure("writ_done", foreground="#4dff88", font=("Segoe UI", 9, "bold"))    # Green: Done today
        self.writs_text.tag_configure("writ_active", foreground="#ffd700", font=("Segoe UI", 9, "bold"))  # Gold: In journal
        self.writs_text.tag_configure("writ_open", foreground="#ff4d4d", font=("Segoe UI", 9))           # Red: Not done today
        self.writs_text.tag_configure("writ_none", foreground="#777777", font=("Segoe UI", 9))           # Gray: Not certified

        # Upper-right corner inside the frozen header bar
        hdr_frame = self.writs_text.hdr_txt.master
        self.writ_timer_label = tk.Label(
            hdr_frame,
            text="Reset: --:--:--",
            bg="#24242b",
            fg="#d4af37",
            font=("Segoe UI", 10, "bold"),
            padx=12
        )
        self.writ_timer_label.pack(side="right")

        self._last_writ_reset_ts = None
        self.update_writ_timer()

    def populate_writs_text(self, writs_rows):
        self._last_writs_rows = writs_rows
        self.writs_text.config(state="normal")
        self.writs_text.delete("1.0", "end")

        craft_keys = ["Alchemy", "Blacksmithing", "Clothing", "Enchanting", "Jewelry", "Provisioning", "Woodworking"]
        tag_map = {
            "Done": "writ_done",
            "Active": "writ_active",
            "Open": "writ_open",
        }

        for row_idx, row in enumerate(writs_rows):
            row_tag = "even" if row_idx % 2 == 0 else "odd"
            alliance_tag = self.get_alliance_tag_from_row(row)
            name_tags = (row_tag, alliance_tag) if alliance_tag else (row_tag,)

            self.writs_text.insert("end", f"{row['name']}\t", name_tags)
            for i, craft in enumerate(craft_keys):
                val = row.get(craft) or row.get("Jewelry Crafting" if craft == "Jewelry" else craft, "—")
                w_tag = tag_map.get(val, "writ_none")
                sep = "\n" if i == len(craft_keys) - 1 else "\t"
                self.writs_text.insert("end", f"{val}{sep}", (row_tag, w_tag))

        self.writs_text.config(state="disabled")

    def _calc_reset_info(self, reset_hour, now_utc):
        """Returns (next_reset_datetime, 'HH:MM:SS') for a given UTC reset hour."""
        reset_today = now_utc.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
        next_reset = reset_today + timedelta(days=1) if now_utc >= reset_today else reset_today
        remaining = next_reset - now_utc
        total_seconds = max(0, int(remaining.total_seconds()))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return next_reset, f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def update_writ_timer(self):
        if getattr(self, "_writ_timer_job", None):
            self.writ_timer_label.after_cancel(self._writ_timer_job)

        mode = self._get_active_writ_server()
        now_utc = datetime.now(timezone.utc)

        na_next, na_str = self._calc_reset_info(10, now_utc)  # NA resets at 10:00 UTC
        eu_next, eu_str = self._calc_reset_info(3, now_utc)   # EU resets at 03:00 UTC

        # Track NA and EU rollovers independently so 'All' flips only the server that reset
        prev_targets = getattr(self, "_last_writ_reset_targets", {})
        if "NA" in prev_targets and na_next > prev_targets["NA"]:
            self._flip_done_writs_to_open(target_server="NA")
        if "EU" in prev_targets and eu_next > prev_targets["EU"]:
            self._flip_done_writs_to_open(target_server="EU")
        self._last_writ_reset_targets = {"NA": na_next, "EU": eu_next}

        if mode == "ALL":
            self.writ_timer_label.config(text=f"Reset: NA {na_str} | EU {eu_str}")
        elif mode == "EU":
            self.writ_timer_label.config(text=f"Reset: {eu_str}")
        else:
            self.writ_timer_label.config(text=f"Reset: {na_str}")

        self._writ_timer_job = self.writ_timer_label.after(1000, self.update_writ_timer)

    def _flip_done_writs_to_open(self, target_server=None):
        rows = getattr(self, "_last_writs_rows", None)
        if not rows:
            return
        craft_keys = ["Alchemy", "Blacksmithing", "Clothing", "Enchanting", "Jewelry", "Jewelry Crafting", "Provisioning", "Woodworking"]
        changed = False
        for row in rows:
            if target_server:
                row_srv = str(row.get("server", "")).upper()
                if row_srv and target_server not in row_srv:
                    continue
            for key in craft_keys:
                if row.get(key) == "Done":
                    row[key] = "Open"
                    changed = True
        if changed:
            self.populate_writs_text(rows)
       
    def build_ui(self):
        # Top Header Bar
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(16, 10))
        header.pack(fill="x")

        ttk.Label(header, text=f"LEO'S ALTHOLIC STANDALONE VIEWER v{self.app_version}", style="Header.TLabel").pack(side="left")

        controls = ttk.Frame(header, style="Header.TFrame")
        controls.pack(side="right")

        ttk.Label(controls, text="Server:", style="Sub.TLabel").pack(side="left", padx=(0, 4))
        self.server_var = tk.StringVar(value="ALL")
        self.server_combo = ttk.Combobox(controls, textvariable=self.server_var, state="readonly", width=18)
        self.server_combo.pack(side="left", padx=(0, 12))
        self.server_combo.bind("<<ComboboxSelected>>", self.on_filter_changed)

        ttk.Label(controls, text="Account:", style="Sub.TLabel").pack(side="left", padx=(0, 4))
        self.account_var = tk.StringVar(value="ALL")
        self.account_combo = ttk.Combobox(controls, textvariable=self.account_var, state="readonly", width=18)
        self.account_combo.pack(side="left", padx=(0, 12))
        self.account_combo.bind("<<ComboboxSelected>>", self.on_filter_changed)

        ttk.Label(controls, text="Sort:", style="Sub.TLabel").pack(side="left", padx=(0, 4))
        self.sort_var = tk.StringVar(value="Creation Order NA-EU")
        self.sort_combo = ttk.Combobox(
            controls,
            textvariable=self.sort_var,
            values=["Creation Order NA-EU", "Creation Order EU-NA", "Name (A-Z)", "Name (Z-A)"],
            state="readonly",
            width=21
        )
        self.sort_combo.pack(side="left", padx=(0, 12))
        self.sort_combo.bind("<<ComboboxSelected>>", self.on_filter_changed)

        refresh_btn = tk.Button(
            controls, text="Refresh", command=self.refresh_data,
            bg="#2d2922", fg="#d4af37", activebackground="#3d372e", activeforeground="#fff",
            relief="solid", bd=1, padx=10, pady=2, font=("Segoe UI", 9, "bold"), cursor="hand2"
        )

        refresh_btn.pack(side="left", padx=(0, 12))

        self.status_label = ttk.Label(controls, text="", style="Sub.TLabel")
        self.status_label.pack(side="left")

        # Main Notebook Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=12)

        tab_defs = [
            ("bio", "Bio & Riding", ["Character", "Level", "Race", "Class", "Riding (Spd/Stam/Cap)"], 32),
            ("stats", "Stats", ["Character", "Points (Mag/Stam/HP)", "Max Health", "Max Magicka", "Max Stamina", "Recovery (Mag/Stam/HP)", "Crit (Wep / Spell)"], 32),
            ("champion", "Champion", ["Character", "Total CP", "Warfare (Blue)", "Fitness (Red)", "Craft (Green)"], 32),
            ("combat", "Combat Skills", ["Character", "Class", "Weapon", "Armor", "Guild", "World / Racial", "Alliance"], 115),
            ("craft", "Crafting Skills", ["Character", "Alchemy", "Blacksmithing", "Clothing", "Enchanting", "Jewelry", "Provisioning", "Woodworking"], 32),
            ("currency", "Currency", ["Character", "Gold", "Alliance Points", "Tel Var", "Writ Vouchers"], 32),            
            ("research", "Research", ["Character", "Blacksmithing", "Clothing", "Woodworking", "Jewelry"], 65),
            ("inventory", "Inventory", ["Character", "Bag Space", "Stored Items"], 32),
            ("writs", "Writs", ["Character", "Alchemy", "Blacksmithing", "Clothing", "Enchanting", "Jewelry", "Provisioning", "Woodworking"], 32),

        ]

        for key, title, cols, row_h in tab_defs:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=title)
            
            if key == "bio":
                self.build_bio_text(frame, cols)
                continue
            if key == "stats":
                self.build_stats_grid(frame, cols)
                continue
            if key == "champion":
                self.build_champion_text(frame, cols)
                continue
            if key == "combat":
                self.build_combat_text(frame, cols)
                continue
            if key == "craft":
                self.build_craft_text(frame, cols)
                continue
            if key == "currency":
                self.build_currency_text(frame, cols)
                continue
            if key == "writs":
                self.build_writs_text(frame, cols)
                continue
            if key == "research":
                self.build_research_text(frame, cols)
                continue
            if key == "inventory":
                self.build_inventory_text(frame, cols)
                continue
            
        # Builds Tab (Class Sub-Tabs + PNG Build Card Export)
        self.builds_tab = BuildsTab(
            self.notebook,
            get_saved_vars_dir_fn=lambda: self.saved_vars_path.parent if self.saved_vars_path else None,
            )
        self.notebook.add(self.builds_tab, text="Builds")
        
        self._restoring_view = False
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def load_data(self):
        # 1. Reuse the path from memory or config.json if it still exists
        vars_path = self.saved_vars_path
        if vars_path is None or not vars_path.exists():
            vars_path = get_saved_vars_path()

        # 2. If still not found, ask the user to locate it manually
        if vars_path is None or not vars_path.exists():
            selected = filedialog.askopenfilename(
                title="Select LeoAltholic.lua SavedVariables File",
                initialdir=get_windows_documents_dir(),
                filetypes=[("Lua SavedVariables", "*.lua"), ("All Files", "*.*")]
            )
            if not selected:
                messagebox.showerror(
                    "File Not Found",
                    "Could not find LeoAltholic.lua.\n\nLog out or run /reloadui in ESO first, then select your SavedVariables file."
                )
                return
            vars_path = Path(selected)

        # Remember this valid path in memory AND persist it to config.json
        if self.saved_vars_path != vars_path:
            self.saved_vars_path = vars_path
            save_config_path(vars_path)

        # Record the file's current modification timestamp
        if vars_path.exists():
            self.last_mtime = vars_path.stat().st_mtime

        raw_lua = vars_path.read_text(encoding="utf-8", errors="ignore")
        self.raw_data = parse_lua_table(raw_lua)
        self.chars = extract_characters(self.raw_data)
        self.banks = extract_banks(self.raw_data)

        servers = ["ALL"] + sorted(list({c.get("_server", "Unknown") for c in self.chars}))
        accounts = ["ALL"] + sorted(list({c.get("_account", "Unknown") for c in self.chars}))
        self.server_combo["values"] = servers
        self.account_combo["values"] = accounts

        # Restore saved server, account, and character sort selections
        prefs = load_view_prefs()
        self.server_var.set(prefs["server"] if prefs["server"] in servers else "ALL")
        self.account_var.set(prefs["account"] if prefs["account"] in accounts else "ALL")

        # Update sort_combo["values"] to match the restored server BEFORE setting sort_var
        self.sync_sort_options()
        if prefs["sort"] in self.sort_combo["values"]:
            self.sort_var.set(prefs["sort"])

        updated = datetime.now().strftime("%H:%M:%S")
        self.status_label.config(text=f"Chars: {len(self.chars)} | Updated: {updated}")
        if hasattr(self, "builds_tab"):
             self.builds_tab.refresh_builds()

        self.refresh_tables()


    def check_file_updates(self):
        if getattr(self, "auto_refresh_enabled", True) and self.saved_vars_path:
            try:
                if self.saved_vars_path.exists():
                    current_mtime = self.saved_vars_path.stat().st_mtime

                    if current_mtime != getattr(self, "last_mtime", 0):
                        time.sleep(0.25)
                        view_state = self.capture_view_state()
                        self.load_data()
                        self.restore_view_state(view_state)

            except (OSError, PermissionError):
                pass

        self.root.after(3000, self.check_file_updates)

    def refresh_tables(self):
        for tree in self.trees.values():
            for item in tree.get_children():
                tree.delete(item)

        sel_srv = self.server_var.get()
        sel_acct = self.account_var.get()

        # Insert Bank rows at top of Currency tab
        bank_rows = []
        for b in self.banks:
            if (sel_srv == "ALL" or b["_server"] == sel_srv) and (sel_acct == "ALL" or b["_account"] == sel_acct):
                srv_raw = str(b.get("_server", ""))
                srv_short = "EU" if "EU" in srv_raw.upper() else ("NA" if "NA" in srv_raw.upper() else ("PTS" if "PTS" in srv_raw.upper() else srv_raw))
                short_label = f"Bank {srv_short} - {b.get('_account', '')}"
                _, gold_str, ap_str, telvar_str, writ_str = b["values"]
                bank_rows.append((short_label, gold_str, ap_str, telvar_str, writ_str))

        bio_rows = []
        stats_rows = []
        champion_rows = []
        combat_rows = []
        craft_rows = []
        research_rows = []
        currency_rows = []
        writs_rows = []
        inventory_rows = []
        visible_idx = 0

        # Daily writ reset helper (EU: 03:00 UTC | NA: 10:00 UTC)
        now_utc = datetime.now(timezone.utc)
        def get_last_reset_ts(server_str):
            is_eu = "eu" in str(server_str or "").lower() or (
                self.saved_vars_path and "liveeu" in str(self.saved_vars_path).lower()
            )
            reset_hour = 3 if is_eu else 10
            reset_dt = now_utc.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
            if now_utc < reset_dt:
                reset_dt -= timedelta(days=1)
            return int(reset_dt.timestamp())

        WRIT_CRAFT_IDS = {
            1: "Blacksmithing",
            2: "Clothing",
            3: "Enchanting",
            4: "Alchemy",
            5: "Provisioning",
            6: "Woodworking",
            7: "Jewelry Crafting",
        }

        SERVER_PRIORITY = {
            "NA Megaserver": 0,
            "EU Megaserver": 1,
            "NA": 0,
            "EU": 1,
        }
        
        sort_mode = self.sort_var.get() if hasattr(self, "sort_var") else "Creation Order"

        if sort_mode == "Name (A-Z)":
            ordered_chars = sorted(
                self.chars,
                key=lambda c: str(c.get("_name", "")).lower()
            )
        elif sort_mode == "Name (Z-A)":
            ordered_chars = sorted(
                self.chars,
                key=lambda c: str(c.get("_name", "")).lower(),
                reverse=True
            )
        else:  # Handles "Creation Order", "Creation Order NA-EU", and "Creation Order EU-NA"
            if sort_mode == "Creation Order EU-NA":
                server_priority = {"EU Megaserver": 0, "EU": 0, "NA Megaserver": 1, "NA": 1}
            else:
                server_priority = {"NA Megaserver": 0, "NA": 0, "EU Megaserver": 1, "EU": 1}

            ordered_chars = sorted(
                self.chars,
                key=lambda c: (
                    server_priority.get(str(c.get("_server") or c.get("server") or ""), 99),
                    (c.get("bio", {}) if isinstance(c.get("bio"), dict) else {}).get("charIndex") or 999,
                    str(c.get("_name", "")).lower()
                )
            )

        for c in ordered_chars:
            srv = c.get("_server", "Unknown")
            acct = c.get("_account", "Unknown")
            if (sel_srv != "ALL" and srv != sel_srv) or (sel_acct != "ALL" and acct != sel_acct):
                continue

            tag = "even" if visible_idx % 2 == 0 else "odd"
            visible_idx += 1

            name = c.get("_name", "Unknown")
            bio = c.get("bio", {}) if isinstance(c.get("bio"), dict) else {}
            attrs = c.get("attributes", {}) if isinstance(c.get("attributes"), dict) else {}
            riding = find_nested_dict(c, "riding")
            skills = c.get("skills", {}) if isinstance(c.get("skills"), dict) else {}
            curr = c.get("currency", {}) if isinstance(c.get("currency"), dict) else {}
            inv = c.get("inventory", {}) if isinstance(c.get("inventory"), dict) else {}
            research = c.get("research", {}) if isinstance(c.get("research"), dict) else {}
            champ = c.get("champion", {}) if isinstance(c.get("champion"), dict) else {}

            # ... (all your tabs 1 through 8, with # 2. Stats appending to stats_rows) ...

            # 1. Bio & Riding
            lvl = bio.get("level", 0)
            cp = bio.get("championPoints", 0)
            if isinstance(lvl, (int, float)) and 0 < lvl < 50:
                level_str = f"Lvl {int(lvl)}"
            elif cp:
                level_str = f"CP {int(cp)}"
            else:
                level_str = f"Lvl {lvl}"
            spd = riding.get("speed", 0)
            stam_r = riding.get("stamina", 0)
            cap = riding.get("capacity", 0)
            r_time = riding.get("time", 0)
            if spd >= 60 and stam_r >= 60 and cap >= 60:
                ride_status = "MAXED"
            elif isinstance(r_time, (int, float)) and r_time > 1000000:
                ride_status = format_timer_plain(r_time)
            elif isinstance(r_time, (int, float)) and r_time > 0:
                hrs, rem = divmod(int(r_time), 3600)
                mins, _ = divmod(rem, 60)
                ride_status = f"{hrs}h {mins}m"
            else:
                ride_status = "READY"
            alliance_data = bio.get("alliance")
            self.char_alliances[name] = alliance_data.get("id") if isinstance(alliance_data, dict) else alliance_data
            bio_rows.append({
                "name": name, "level": level_str,
                "race": bio.get("race", "-"), "class": bio.get("class", "-"),
                "spd": spd, "stam": stam_r, "cap": cap, "status": ride_status
            })

            # 2. Stats
            def get_attr(stat_k, sub_ks, flat_ks):
                obj = attrs.get(stat_k, {})
                if isinstance(obj, dict):
                    for sk in sub_ks:
                        if sk in obj and obj[sk] is not None:
                            return obj[sk]
                for fk in flat_ks:
                    if fk in attrs and attrs[fk] is not None:
                        return attrs[fk]
                return "-"

            hp = get_attr("health", ["max"], ["healthMax", "maxHealth"])
            mag = get_attr("magicka", ["max"], ["magickaMax", "maxMagicka"])
            stam = get_attr("stamina", ["max"], ["staminaMax", "maxStamina"])

            pts_mag = get_attr("magicka", ["points", "spent", "value"], ["magickaPoints"])
            pts_stam = get_attr("stamina", ["points", "spent", "value"], ["staminaPoints"])
            pts_hp = get_attr("health", ["points", "spent", "value"], ["healthPoints"])

            rec_mag = get_attr("magicka", ["recovery", "regen"], ["magickaRecovery"])
            rec_stam = get_attr("stamina", ["recovery", "regen"], ["staminaRecovery"])
            rec_hp = get_attr("health", ["recovery", "regen"], ["healthRecovery"])

            raw_wep = get_attr("weapon", ["criticalChance", "crit"], ["weaponCrit"])
            raw_spl = get_attr("spell", ["criticalChance", "crit"], ["spellCrit"])
            wep_crit = f"{round(float(raw_wep), 1)}%" if isinstance(raw_wep, (int, float)) else "-"
            spl_crit = f"{round(float(raw_spl), 1)}%" if isinstance(raw_spl, (int, float)) else "-"
            alliance_data = bio.get("alliance")
            self.char_alliances[name] = alliance_data.get("id") if isinstance(alliance_data, dict) else alliance_data
            stats_rows.append({
                "name": name,
                "pts_mag": pts_mag, "pts_stam": pts_stam, "pts_hp": pts_hp,
                "max_hp": hp, "max_mag": mag, "max_stam": stam,
                "rec_mag": rec_mag, "rec_stam": rec_stam, "rec_hp": rec_hp,
                "crit": f"{wep_crit} / {spl_crit}",
            })

            # 3. Champion
            cp_total = bio.get("championPoints", champ.get("points", "-"))
            def get_tree_pts(keys):
                for k in keys:
                    disc = champ.get(k)
                    if isinstance(disc, (int, float)):
                        return int(disc)
                    if isinstance(disc, dict):
                        for pk in ("spent", "total", "points", "value"):
                            if isinstance(disc.get(pk), (int, float)):
                                return int(disc[pk])
                        target = disc.get("stars", disc.get("list", disc))
                        if isinstance(target, dict):
                            tot, found = 0, False
                            for st in target.values():
                                if isinstance(st, dict) and isinstance(st.get("points", st.get("value")), (int, float)):
                                    tot += int(st.get("points", st.get("value")))
                                    found = True
                                elif isinstance(st, (int, float)):
                                    tot += int(st)
                                    found = True
                            if found:
                                return tot
                return 0
            alliance_data = bio.get("alliance")
            self.char_alliances[name] = alliance_data.get("id") if isinstance(alliance_data, dict) else alliance_data
            champion_rows.append({
                "name": name,
                "total": cp_total,
                "warfare": get_tree_pts(["warfare", "Warfare", 1, "1"]),
                "fitness": get_tree_pts(["fitness", "Fitness", 2, "2"]),
                "craft": get_tree_pts(["craft", "Craft", 3, "3"]),
            })

            # 4. Combat Skills
            def fmt_class_list():
                class_order = {
                    # Dragonknight
                    "ardent flame": 1, "draconic power": 2, "earthen heart": 3,
                    # Sorcerer
                    "dark magic": 1, "daedric summoning": 2, "storm calling": 3,
                    # Nightblade
                    "assassination": 1, "shadow": 2, "siphoning": 3,
                    # Templar
                    "aedric spear": 1, "dawn's wrath": 2, "restoring light": 3,
                    # Warden
                    "animal companions": 1, "green balance": 2, "winter's embrace": 3,
                    # Necromancer
                    "grave lord": 1, "bone tyrant": 2, "living death": 3,
                    # Arcanist
                    "herald of the tome": 1, "soldier of apocrypha": 2, "curative runeforms": 3,
                }
                entries = []
                cd = skills.get("class", {})
                if isinstance(cd, dict):
                    for idx_key, li in cd.items():
                        if isinstance(li, dict) and "name" in li:
                            sname = li["name"]
                            srank = li.get("rank", 0)
                            low = sname.strip().lower()
                            if "mastery" in low:
                                order = 4
                            elif low in class_order:
                                order = class_order[low]
                            else:
                                order = int(idx_key) if str(idx_key).isdigit() else 3
                            entries.append((order, sname, f" ({srank})"))
                entries.sort(key=lambda x: (x[0], x[1]))
                return [(x[1], x[2]) for x in entries] if entries else [("-", "")]

            def fmt_world_list():
                world_order = {
                    "excavation": 2,
                    "legerdemain": 3,
                    "scrying": 4,
                    "soul magic": 5,
                    "werewolf": 6,
                    "vampire": 7,
                }
                entries = []
                antiq_rank = 0

                for k in ("racial", "world"):
                    cd = skills.get(k, {})
                    if isinstance(cd, dict):
                        for li in cd.values():
                            if isinstance(li, dict) and "name" in li:
                                sname = li["name"]
                                srank = li.get("rank", 0)
                                low = sname.strip().lower()

                                # Racial lines go first (order 1)
                                if k == "racial" or "skills" in low:
                                    order = 1
                                else:
                                    order = world_order.get(low, 99)

                                # Extract Antiquarian Insight rank (1-5) from Scrying passives
                                if low == "scrying":
                                    ab_list = li.get("list", {})
                                    if isinstance(ab_list, dict):
                                        for ab in ab_list.values():
                                            if isinstance(ab, dict) and ab.get("plainName") == "Antiquarian Insight":
                                                antiq_rank = int(ab.get("level", 0) or 0)
                                                break

                                entries.append((order, sname, f" ({srank})"))

                entries.sort(key=lambda x: (x[0], x[1]))
                return ([(x[1], x[2]) for x in entries] if entries else [("-", "")]), antiq_rank

            def fmt_fixed_list(cat_k, defaults):
                ranks = {n: 0 for n in defaults}
                cd = skills.get(cat_k, {})
                if isinstance(cd, dict):
                    for li in cd.values():
                        if isinstance(li, dict) and "name" in li:
                            ranks[li["name"]] = li.get("rank", 0)
                return [(k, f" ({v})") for k, v in ranks.items()]

            world_entries, antiq_rank = fmt_world_list()
            ava_key = "alliance" if isinstance(skills.get("alliance"), dict) else "ava"
            alliance_data = bio.get("alliance")
            self.char_alliances[name] = alliance_data.get("id") if isinstance(alliance_data, dict) else alliance_data
            combat_rows.append({
                "name": name,
                "class": fmt_class_list(),
                "weapon": fmt_fixed_list("weapon", ["Two Handed", "One Hand and Shield", "Dual Wield", "Bow", "Destruction Staff", "Restoration Staff"]),
                "armor": fmt_fixed_list("armor", ["Light Armor", "Medium Armor", "Heavy Armor"]),
                "guild": fmt_fixed_list("guild", ["Fighters Guild", "Mages Guild", "Undaunted", "Psijic Order", "Thieves Guild", "Dark Brotherhood"]),
                "world": world_entries,
                "antiq_rank": antiq_rank,
                "alliance": fmt_fixed_list(ava_key, ["Assault", "Support"]),
            })
      
            # 5. Crafting Skills
            c_ranks = {p: None for p in ("Alchemy", "Blacksmithing", "Clothing", "Enchanting", "Jewelry Crafting", "Provisioning", "Woodworking")}
            if isinstance(skills.get("craft"), dict):
                for li in skills["craft"].values():
                    if isinstance(li, dict) and "name" in li:
                        cn, cr = li["name"], li.get("rank", 0)
                        if cn in c_ranks:
                            c_ranks[cn] = int(cr)
                        elif "Jewelry" in cn:
                            c_ranks["Jewelry Crafting"] = int(cr)
            alliance_data = bio.get("alliance")
            self.char_alliances[name] = alliance_data.get("id") if isinstance(alliance_data, dict) else alliance_data
            craft_rows.append({"name": name, "ranks": c_ranks})

            # 6. Currency
            c_src = inv if any(k in inv for k in ("money", "gold", "ap", "telvar", "writVoucher")) else curr
            rg = c_src.get("money", c_src.get("gold", 0))
            rv = c_src.get("writVoucher", c_src.get("writvoucher", 0))
            alliance_data = bio.get("alliance")
            self.char_alliances[name] = alliance_data.get("id") if isinstance(alliance_data, dict) else alliance_data
            currency_rows.append({
                "name": name,
                "gold": f"{rg:,}" if isinstance(rg, (int, float)) else "-",
                "ap": f"{c_src.get('ap', 0):,}" if isinstance(c_src.get("ap"), (int, float)) else "-",
                "telvar": f"{c_src.get('telvar', 0):,}" if isinstance(c_src.get("telvar"), (int, float)) else "-",
                "writ": f"{rv:,}" if isinstance(rv, (int, float)) else "-",
            })

            # 7. Research
            line_names = {
                1: {1: "Axe", 2: "Mace", 3: "Sword", 4: "Battle Axe", 5: "Maul", 6: "Greatsword", 7: "Dagger", 8: "Cuirass", 9: "Sabatons", 10: "Gauntlets", 11: "Helm", 12: "Greaves", 13: "Pauldrons", 14: "Girdle"},
                2: {1: "Robe/Jerkin", 2: "Shoes", 3: "Gloves", 4: "Hat", 5: "Breeches", 6: "Epaulets", 7: "Sash", 8: "Jack", 9: "Boots", 10: "Bracers", 11: "Helmet", 12: "Guards", 13: "Arm Cops", 14: "Belt"},
                6: {1: "Bow", 2: "Inferno Staff", 3: "Ice Staff", 4: "Lightning Staff", 5: "Restoration Staff", 6: "Shield"},
                7: {1: "Necklace", 2: "Ring"},
            }
            w_traits = {1: "Powered", 2: "Charged", 3: "Precise", 4: "Infused", 5: "Defending", 6: "Training", 7: "Sharpened", 8: "Decisive", 9: "Nirnhoned"}
            a_traits = {1: "Sturdy", 2: "Impenetrable", 3: "Reinforced", 4: "Well-Fitted", 5: "Training", 6: "Infused", 7: "Prosperous/Invig", 8: "Divines", 9: "Nirnhoned"}
            j_traits = {1: "Arcane", 2: "Healthy", 3: "Robust", 4: "Triune", 5: "Infused", 6: "Protective", 7: "Swift", 8: "Harmony", 9: "Bloodthirsty"}
            max_map = {1: 126, 2: 126, 6: 54, 7: 18}
            done_blk = research.get("done", {}) if isinstance(research.get("done"), dict) else {}
            doing_blk = research.get("doing", {}) if isinstance(research.get("doing"), dict) else {}

            def res_cell(cid):
                cdone = done_blk.get(cid) or done_blk.get(str(cid)) or {}
                known = 0
                if isinstance(cdone, dict):
                    for lk, td in cdone.items():
                        if (isinstance(lk, int) or (isinstance(lk, str) and lk.isdigit())) and isinstance(td, dict):
                            known += sum(1 for v in td.values() if v is True)
                tot = max_map.get(cid, 0)
                if tot > 0 and known >= tot:
                    return {"completed": True, "known": known, "tot": tot, "timers": []}

                cdoing = doing_blk.get(cid) or doing_blk.get(str(cid)) or {}
                timers = []
                if isinstance(cdoing, dict):
                    for si in cdoing.values():
                        if isinstance(si, dict) and "doneAt" in si:
                            lid, tid = si.get("line", 0), si.get("trait", 0)
                            ilabel = line_names.get(cid, {}).get(lid, f"Line {lid}")
                            if cid == 7:
                                tlabel = j_traits.get(tid, f"Trait {tid}")
                            elif (cid == 6 and lid <= 5) or (cid == 1 and lid <= 7):
                                tlabel = w_traits.get(tid, f"Trait {tid}")
                            else:
                                tlabel = a_traits.get(tid, f"Trait {tid}")
                            timers.append((f"{ilabel} ({tlabel})", si["doneAt"]))
                return {"completed": False, "known": known, "tot": tot, "timers": timers}

            alliance_data = bio.get("alliance")
            self.char_alliances[name] = alliance_data.get("id") if isinstance(alliance_data, dict) else alliance_data
            research_rows.append({
                "name": name,
                "bs": res_cell(1),
                "cl": res_cell(2),
                "ww": res_cell(6),
                "jw": res_cell(7),
            })

            # 8. Inventory
            used_slots = inv.get("used", "-")
            total_slots = inv.get("size", "-")
            bag_str = f"{used_slots} / {total_slots}"

            backpack_bag = inv.get(1) if isinstance(inv.get(1), dict) else inv.get("1")
            worn_bag = inv.get(0) if isinstance(inv.get(0), dict) else inv.get("0")

            def extract_bag_entries(bag_dict):
                entries = []
                if isinstance(bag_dict, dict):
                    for v in bag_dict.values():
                        if isinstance(v, dict) and "name" in v:
                            iname = clean_eso_text(v["name"])
                            icount = v.get("count", 1)
                            trait_str, ench_str = decode_eso_item_link(v.get("link"), v.get("trait"), v.get("enchant"), iname)
                            weight_str = decode_eso_armor_weight(iname, v.get("weight"))
                            entries.append((iname, icount, trait_str, ench_str, weight_str))
                entries.sort(key=lambda item: str(item).lower())
                return entries

            bag_items = extract_bag_entries(backpack_bag)
            worn_items = extract_bag_entries(worn_bag)
            alliance_data = bio.get("alliance")
            self.char_alliances[name] = alliance_data.get("id") if isinstance(alliance_data, dict) else alliance_data
            inventory_rows.append({
                "name": name,
                "used": used_slots,
                "size": total_slots,
                "bag_str": bag_str,
                "bag_items": bag_items,
                "worn_items": worn_items,
            })
            # 9. Writs
            last_reset_ts = get_last_reset_ts(c.get("_server"))
            w_status = {p: "—" for p in ("Alchemy", "Blacksmithing", "Clothing", "Enchanting", "Jewelry Crafting", "Provisioning", "Woodworking")}
            quests = c.get("quests", {}) if isinstance(c.get("quests"), dict) else {}
            writs_data = quests.get("writs", {}) if isinstance(quests.get("writs"), dict) else {}

            for k, w_entry in writs_data.items():
                if not isinstance(w_entry, dict):
                    continue
                # LeoAltholic keys writs by CraftingType ID (1-7) or craft name
                craft_col = WRIT_CRAFT_IDS.get(k) if isinstance(k, int) else None
                if not craft_col:
                    w_name = str(w_entry.get("name", k))
                    for col_name in w_status:
                        if col_name.split()[0].lower() in w_name.lower():
                            craft_col = col_name
                            break

                if craft_col:
                    last_done = w_entry.get("lastDone", 0)
                    is_active = w_entry.get("active", False) or w_entry.get("status") == "active"
                    if isinstance(last_done, (int, float)) and last_done >= last_reset_ts:
                        w_status[craft_col] = "Done"
                    elif is_active:
                        w_status[craft_col] = "Active"
                    elif isinstance(last_done, (int, float)) and last_done > 0:
                        w_status[craft_col] = "Open"

            writs_rows.append({"name": name, **w_status})
             
        self.populate_bio_text(bio_rows)   
        self.populate_stats_grid(stats_rows)
        self.populate_champion_text(champion_rows)
        self.populate_combat_text(combat_rows)
        self.populate_craft_text(craft_rows)
        self.populate_currency_text(bank_rows, currency_rows)
        self.populate_research_text(research_rows)
        self.populate_inventory_text(inventory_rows)
        self.populate_writs_text(writs_rows)
        
def main():
    root = tk.Tk()
    app = AltholicApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
