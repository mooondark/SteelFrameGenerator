"""
steel_frame_web.py
==================
Version Streamlit de SteelFrameGenerator.

Prérequis :
    pip install streamlit requests plotly

Lancement :
    streamlit run steel_frame_web.py
    ou double-cliquer sur lancer.bat
"""

# =============================================================================
# IMPORTS
# =============================================================================

import configparser
import math
import os
import socket
import subprocess
import sys
import urllib.parse

import streamlit as st

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

try:
    import plotly  # noqa: F401
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "plotly"])

# Session HTTP réutilisée : keep-alive + pooling de connexions.
# Évite un handshake TCP par requête (des centaines lors d'une génération).
_SESSION = requests.Session()
_adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=8)
_SESSION.mount("http://", _adapter)
_SESSION.mount("https://", _adapter)

# Sentinelle d'environnement pour le worker Streamlit en mode PyInstaller.
_SFG_STREAMLIT_WORKER = "_SFG_STREAMLIT_WORKER"

# =============================================================================
# CONSTANTES
# =============================================================================

VERSION = "1.27"
DEFAULT_HOST = "http://localhost:52000"
DEFAULT_API_SERVER_EXE = r"C:\Program Files\Graitec\Advance Design\2027\Bin\AD.API.Srv.exe"
DEFAULT_LANG = "fr"

MATERIAUX_VALIDES = ["S235", "S275", "S355"]
APPUIS_VALIDES = ["HINGED", "FIXED"]

SECTIONS_HEA = [f"HEA{x}" for x in [100,120,140,160,180,200,220,240,260,280,300,320,340,360,400,450,500,550,600,650,700,800,900,1000]]
SECTIONS_HEB = [f"HEB{x}" for x in [100,120,140,160,180,200,220,240,260,280,300,320,340,360,400,450,500,550,600,650,700,800,900,1000]]
SECTIONS_IPE = [f"IPE{x}" for x in [100,120,140,160,180,200,220,240,270,300,330,360,400,450,500,550,600]]
SECTIONS_IPN = [f"IPN{x}" for x in [120,140,160,180,200,220,240,260,280,300,320,340,360,380,400,450,500,550]]
SECTIONS_VALIDES = set(SECTIONS_HEA + SECTIONS_HEB + SECTIONS_IPE + SECTIONS_IPN)

FAMILLES = ["HEA", "HEB", "IPE", "IPN"]
SECTIONS_PAR_FAMILLE = {
    "HEA": SECTIONS_HEA,
    "HEB": SECTIONS_HEB,
    "IPE": SECTIONS_IPE,
    "IPN": SECTIONS_IPN,
}

STEEL_PROPS = {
    "S235": {"e": 210_000_000, "ro": 7850, "nu": 0.3, "damping": 0.02, "alpha": 1.2e-5, "sigmaE": 235_000},
    "S275": {"e": 210_000_000, "ro": 7850, "nu": 0.3, "damping": 0.02, "alpha": 1.2e-5, "sigmaE": 275_000},
    "S355": {"e": 210_000_000, "ro": 7850, "nu": 0.3, "damping": 0.02, "alpha": 1.2e-5, "sigmaE": 355_000},
}

RELAXATION_PANNES = {
    "startBoundaryConnection": {
        "relaxationTx": False, "relaxationTy": False, "relaxationTz": False,
        "relaxationRx": False, "relaxationRy": True,  "relaxationRz": True,
    },
    "endBoundaryConnection": {
        "relaxationTx": False, "relaxationTy": False, "relaxationTz": False,
        "relaxationRx": False, "relaxationRy": True,  "relaxationRz": True,
    },
}

# =============================================================================
# CONFIGURATION PERSISTANTE (config_sf.ini)
# =============================================================================

def get_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(get_app_dir(), "config_sf.ini")

def load_config():
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    needs_save = False
    if os.path.isfile(CONFIG_FILE):
        try:
            parser.read(CONFIG_FILE, encoding="utf-8")
        except Exception:
            parser = configparser.ConfigParser(interpolation=None)
            parser.optionxform = str
            needs_save = True
    else:
        needs_save = True

    if "General" not in parser:
        parser["General"] = {}
        needs_save = True

    section = parser["General"]
    if "language"       not in section: section["language"]       = DEFAULT_LANG;            needs_save = True
    if "api_server_exe" not in section: section["api_server_exe"] = DEFAULT_API_SERVER_EXE; needs_save = True

    if needs_save:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                parser.write(f)
        except Exception:
            pass

    return {
        "language":       section.get("language",       DEFAULT_LANG),
        "api_server_exe": section.get("api_server_exe", DEFAULT_API_SERVER_EXE),
    }

def save_config(language, api_server_exe):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser["General"] = {"language": language, "api_server_exe": api_server_exe}
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            parser.write(f)
    except Exception:
        pass

# =============================================================================
# TRADUCTIONS (.ini)
# =============================================================================

LANG_FILES = {"fr": "french.ini", "en": "english.ini", "pl": "polish.ini"}
LANG_LABELS = {"fr": "🇫🇷 Français", "en": "🇬🇧 English", "pl": "🇵🇱 Polski"}

_MESSAGES: dict = {}
_DISPLAY_VALUES: dict = {}

def load_language(lang_code: str) -> dict:
    global _MESSAGES, _DISPLAY_VALUES
    lang_code = lang_code if lang_code in LANG_FILES else DEFAULT_LANG
    base_dir  = get_app_dir()
    ini_path  = os.path.join(base_dir, LANG_FILES[lang_code])

    if not os.path.isfile(ini_path):
        if lang_code != DEFAULT_LANG:
            return load_language(DEFAULT_LANG)
        # Fichier absent : messages de secours en français codés en dur
        _MESSAGES = {}
        _DISPLAY_VALUES = {"HINGED": "Rotule", "FIXED": "Encastrement"}
        return _MESSAGES

    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(ini_path, encoding="utf-8")

    _MESSAGES = dict(parser["messages"]) if parser.has_section("messages") else {}
    _DISPLAY_VALUES = {
        "HINGED": _MESSAGES.get("appui_hinged", "HINGED"),
        "FIXED":  _MESSAGES.get("appui_fixed",  "FIXED"),
    }
    return _MESSAGES

def T(key: str, **kw) -> str:
    """Retourne la traduction de 'key', avec substitutions optionnelles."""
    value = _MESSAGES.get(key, key)
    value = value.replace("\\n", "\n")
    return value.format(**kw) if kw else value


def _native_pick(save: bool, initial: str = ""):
    """Boite de dialogue systeme (tkinter) pour choisir un fichier .fto.
    Retourne le chemin, '' si annule, None si tkinter indisponible."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None

    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    kw = {
        "title": T("browse_title_fto") or "Fichier projet Advance Design",
        "filetypes": [("Advance Design (*.fto)", "*.fto"), ("*.*", "*.*")],
    }
    if initial:
        d = os.path.dirname(initial)
        if os.path.isdir(d):
            kw["initialdir"] = d
        if os.path.basename(initial):
            kw["initialfile"] = os.path.basename(initial)
    if save:
        path = filedialog.asksaveasfilename(defaultextension=".fto", **kw)
    else:
        path = filedialog.askopenfilename(**kw)
    root.destroy()
    return os.path.normpath(path) if path else ""


@st.cache_data(show_spinner=False)
def _schema_data_uri() -> str:
    """Encode schema_portique.png en data-URI, une seule fois (mis en cache)."""
    import base64
    path = os.path.join(get_app_dir(), "schema_portique.png")
    if not os.path.isfile(path):
        return ""
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def _wireframe_segments(p):
    """Reconstruit la geometrie filaire (sans appel API) : memes formules que build_structure."""
    n = int(p["n"]); e = float(p["e"])
    Hg, Hd, L, AR, F = float(p["Hg"]), float(p["Hd"]), float(p["L"]), float(p["AR"]), float(p["F"])
    Npg, Npd = int(p["Npg"]), int(p["Npd"])
    Dbg, Dbd = float(p["Dbg"]), float(p["Dbd"])

    H_faitage = max(Hg, Hd) + F
    Lg = math.sqrt(AR ** 2 + (H_faitage - Hg) ** 2)
    Ld = math.sqrt((L - AR) ** 2 + (H_faitage - Hd) ** 2)
    if Lg <= 0 or Ld <= 0 or Npg < 2 or Npd < 2 or Dbg >= Lg or Dbd >= Ld:
        raise ValueError("geometrie invalide")

    portiques, pannes, supports = [], [], []
    for i in range(n):
        Yi = i * e
        pied_g, sommet_g = (0, Yi, 0), (0, Yi, Hg)
        pied_d, sommet_d = (L, Yi, 0), (L, Yi, Hd)
        faitage = (AR, Yi, H_faitage)
        portiques += [(pied_g, sommet_g), (pied_d, sommet_d),
                      (sommet_g, faitage), (sommet_d, faitage)]
        supports += [pied_g, pied_d]

    pos_g = [k * (Lg - Dbg) / (Npg - 1) for k in range(Npg)]
    pos_d = [k * (Ld - Dbd) / (Npd - 1) for k in range(Npd)]
    for i in range(n - 1):
        Y0, Y1 = i * e, (i + 1) * e
        sg0, f0 = (0, Y0, Hg), (AR, Y0, H_faitage)
        sg1, f1 = (0, Y1, Hg), (AR, Y1, H_faitage)
        sd0, fd0 = (L, Y0, Hd), (AR, Y0, H_faitage)
        sd1, fd1 = (L, Y1, Hd), (AR, Y1, H_faitage)
        for d in pos_g:
            pannes.append((point_on_rafter(sg0, f0, d), point_on_rafter(sg1, f1, d)))
        for d in pos_d:
            pannes.append((point_on_rafter(sd0, fd0, d), point_on_rafter(sd1, fd1, d)))

    return portiques, pannes, supports


def _preview_figure(p):
    """Vue 3D filaire isometrique interactive (rotation / zoom via Plotly)."""
    import plotly.graph_objects as go

    portiques, pannes, supports = _wireframe_segments(p)

    def _lines(segs, color, name, width):
        xs, ys, zs = [], [], []
        for a, b in segs:
            xs += [a[0], b[0], None]
            ys += [a[1], b[1], None]
            zs += [a[2], b[2], None]
        return go.Scatter3d(x=xs, y=ys, z=zs, mode="lines",
                            line=dict(color=color, width=width), name=name,
                            hoverinfo="skip")

    fig = go.Figure([
        _lines(portiques, "#4A7FE0", "Poteaux / arbaletriers", 5),
        _lines(pannes, "#2CB67D", "Pannes", 2),
        go.Scatter3d(
            x=[s[0] for s in supports], y=[s[1] for s in supports], z=[s[2] for s in supports],
            mode="markers", name="Appuis", hoverinfo="skip",
            marker=dict(size=4, color="#E8A840", symbol="diamond"),
        ),
    ])
    fig.update_layout(
        height=340,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        scene=dict(
            aspectmode="data",
            xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
            camera=dict(projection=dict(type="orthographic"),
                        eye=dict(x=1.6, y=-1.6, z=1.1)),
        ),
    )
    return fig

# =============================================================================
# LOGIQUE MÉTIER — API ADVANCE DESIGN (inchangée vs version PySide6)
# =============================================================================

def check_port(host: str) -> None:
    parsed   = urllib.parse.urlparse(host)
    hostname = parsed.hostname
    port     = parsed.port
    if hostname is None:
        raise ValueError(f"URL invalide : {host}")
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    result = sock.connect_ex((hostname, port))
    sock.close()
    if result != 0:
        raise ConnectionError(f"Port inaccessible : {hostname}:{port}")


def _check(response: requests.Response, label: str) -> dict:
    try:
        data = response.json()
    except ValueError:
        data = None

    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        body = data if data is not None else response.text[:500]
        raise RuntimeError(f"[{label}] HTTP {response.status_code} — {body}") from e

    if data is None:
        raise RuntimeError(f"[{label}] Réponse non-JSON — {response.text[:500]}")
    details = data.get("details", {})
    if not details.get("success", True):
        messages = "; ".join(d.get("message", "") for d in details.get("diagnostics", []))
        raise RuntimeError(f"[{label}] Erreur API — {messages}")
    return data


def new_project(host, fto_path):
    resp = _SESSION.post(
        f"{host}/api/Model/management/NewProject",
        params={"filename": fto_path}, json={}, timeout=30
    )
    _check(resp, "NewProject")


def open_project(host, fto_path):
    resp = _SESSION.post(
        f"{host}/api/Model/management/OpenProject",
        params={"filename": fto_path}, json={}, timeout=30
    )
    _check(resp, "OpenProject")


def close_project(host):
    try:
        _SESSION.post(f"{host}/api/Model/management/CloseProject", json={}, timeout=15)
    except Exception:
        pass


def create_material(host, name):
    props = STEEL_PROPS[name]
    data  = _check(
        _SESSION.post(f"{host}/api/Model/materials/CreateMaterial",
                      json={"$type": "MaterialSteel", "name": name, **props}),
        "CreateMaterial"
    )
    return data["data"]["value"]


def create_section(host, section_name):
    data = _check(
        _SESSION.post(f"{host}/api/Model/sections/CreateSection",
                      params={"sectionName": section_name}),
        f"CreateSection({section_name})"
    )
    return data["data"]["value"]


def create_linear_element(host, pt_start, pt_end, mat_id, sec_id,
                           beam_type="beamWStandardBending", relaxation=None):
    payload = {
        "$type":          "ElementLinear",
        "geomPtStart":    {"x": pt_start[0], "y": pt_start[1], "z": pt_start[2]},
        "geomPtEnd":      {"x": pt_end[0],   "y": pt_end[1],   "z": pt_end[2]},
        "material":       {"value": mat_id},
        "section":        {"value": sec_id},
        "linearElementType": "eLinearElementFEMTypeGeneral",
        "generalBeamType":   beam_type,
    }
    if relaxation is not None:
        payload["relaxationTotale"] = relaxation
    data = _check(
        _SESSION.post(f"{host}/api/Model/elements/CreateElement", json=payload),
        "CreateElement(linear)"
    )
    return data["data"]["value"]


def create_support(host, pt, mat_id, type_appui):
    if type_appui == "FIXED":
        restraints = {"tx": True, "ty": True, "tz": True, "rx": True,  "ry": True,  "rz": True}
    else:
        restraints = {"tx": True, "ty": True, "tz": True, "rx": False, "ry": False, "rz": False}
    payload = {
        "$type":           "ElementRigidPunctualSupport",
        "geomPt":          {"x": pt[0], "y": pt[1], "z": pt[2]},
        "material":        {"value": mat_id},
        "constraintsType": "other",
        "restraints":      restraints,
    }
    data = _check(
        _SESSION.post(f"{host}/api/Model/elements/CreateElement", json=payload),
        f"CreateSupport({type_appui})"
    )
    return data["data"]["value"]


def create_dead_load_case(host):
    fam_data = _check(
        _SESSION.post(f"{host}/api/Model/elements/CreateInformationalElement",
                      json={"$type": "LoadCaseFamily_DeadLoads", "name": T("ad_famille_g") or "Permanentes"}),
        "CreateFamily(G)"
    )
    fam_eid  = fam_data["data"]["value"]
    case_data = _check(
        _SESSION.post(
            f"{host}/api/Model/elements/CreateInformationalElement",
            json={
                "$type":             "LoadCase_DeadLoads",
                "name":              T("ad_cas_g") or "G1",
                "loadCaseFamilyID":  {"value": fam_eid},
                "field":             {"x": 0.0, "y": 0.0, "z": -1.0},
            },
        ),
        "CreateCase(G1)"
    )
    case_eid = case_data["data"]["value"]
    return fam_eid, case_eid


def create_load_area(host, pts_list, label="LoadArea", span_direction=None):
    payload = {
        "$type":       "ElementLoadArea",
        "geomPtsList": [{"x": p[0], "y": p[1], "z": p[2]} for p in pts_list],
    }
    if span_direction:
        payload["loadTransferProperties"] = {
            "loadTransferMethodType":         "eLoadTransferMethodAuto",
            "loadTransferSpanDirectionType":  span_direction,
        }
    data = _check(
        _SESSION.post(f"{host}/api/Model/elements/CreateElement", json=payload),
        f"CreateLoadArea({label})"
    )
    return data["data"]["value"]


def roof_quad_oriented(pt_a0, pt_b0, pt_b1, pt_a1, longitudinal_length, transverse_length):
    if longitudinal_length >= transverse_length:
        return [pt_a0, pt_a1, pt_b1, pt_b0]
    return [pt_a0, pt_b0, pt_b1, pt_a1]


def point_on_rafter(pt_base, pt_faitage, dist_from_base):
    dx = pt_faitage[0] - pt_base[0]
    dy = pt_faitage[1] - pt_base[1]
    dz = pt_faitage[2] - pt_base[2]
    length = math.sqrt(dx*dx + dy*dy + dz*dz)
    t = dist_from_base / length
    return (pt_base[0] + t*dx, pt_base[1] + t*dy, pt_base[2] + t*dz)


def validate(p):
    errors = []
    if not (2 <= p["n"] <= 25):             errors.append(T("val_n")    or "Nombre de portiques : 2 à 25")
    if p["e"]  <= 0:                         errors.append(T("val_e")    or "Entraxe > 0")
    if p["Hg"] <= 0:                         errors.append(T("val_Hg")   or "Hg > 0")
    if p["Hd"] <= 0:                         errors.append(T("val_Hd")   or "Hd > 0")
    if p["L"]  <= 0:                         errors.append(T("val_L")    or "Portée > 0")
    if not (0 < p["AR"] < p["L"]):           errors.append(T("val_AR")   or "AR doit être dans ]0, L[")
    if p["F"]  <= 0:                         errors.append(T("val_F")    or "Flèche > 0")
    if p["M"]  not in MATERIAUX_VALIDES:     errors.append(T("val_materiau") or "Matériau invalide")
    if p["TypeAppui"] not in APPUIS_VALIDES: errors.append(T("val_appui")    or "Type d'appui invalide")

    for key, role_key in (("Sp", "role_poteaux"), ("Sa", "role_arbaletriers"), ("Sn", "role_pannes")):
        if p[key] not in SECTIONS_VALIDES:
            errors.append(T("val_section", role=T(role_key) or key, nom=p[key]) or f"Section {p[key]} invalide")

    if p["Npg"] < 2: errors.append(T("val_Npg") or "Npg ≥ 2")
    if p["Npd"] < 2: errors.append(T("val_Npd") or "Npd ≥ 2")
    if p["Dbg"] < 0: errors.append(T("val_Dbg") or "Dbg ≥ 0")
    if p["Dbd"] < 0: errors.append(T("val_Dbd") or "Dbd ≥ 0")

    if not errors:
        H_faitage = max(p["Hg"], p["Hd"]) + p["F"]
        Lg = math.sqrt(p["AR"]**2 + (H_faitage - p["Hg"])**2)
        Ld = math.sqrt((p["L"] - p["AR"])**2 + (H_faitage - p["Hd"])**2)
        if p["Dbg"] >= Lg:
            errors.append(T("val_Dbg_long", dbg=p["Dbg"], lg=round(Lg,3)) or f"Dbg ({p['Dbg']}) ≥ Lg ({Lg:.3f})")
        if p["Dbd"] >= Ld:
            errors.append(T("val_Dbd_long", dbd=p["Dbd"], ld=round(Ld,3)) or f"Dbd ({p['Dbd']}) ≥ Ld ({Ld:.3f})")

    if errors:
        raise ValueError("\n".join(errors))


def build_structure(host, p, log_cb):
    n, e_val = p["n"], p["e"]
    Hg, Hd, L, AR, F = p["Hg"], p["Hd"], p["L"], p["AR"], p["F"]
    Npg, Npd, Dbg, Dbd = p["Npg"], p["Npd"], p["Dbg"], p["Dbd"]
    type_appui   = p["TypeAppui"]
    creer_parois = p.get("creer_parois", False)

    H_faitage = max(Hg, Hd) + F
    Lg = math.sqrt(AR**2 + (H_faitage - Hg)**2)
    Ld = math.sqrt((L - AR)**2 + (H_faitage - Hd)**2)

    log_cb(T("log_materiau", nom=p["M"]) or f"Création matériau {p['M']}…")
    mat_id = create_material(host, p["M"])
    log_cb(T("log_materiau_ok", nom=p["M"], eid=mat_id) or f"✓ Matériau {p['M']} — eid={mat_id}", "ok")

    log_cb(T("log_sections") or "Création des sections…")
    sec_poteau = create_section(host, p["Sp"])
    sec_arbal  = create_section(host, p["Sa"])
    sec_panne  = create_section(host, p["Sn"])
    log_cb(T("log_sections_ok", Sp=p["Sp"], eid_p=sec_poteau,
             Sa=p["Sa"], eid_a=sec_arbal, Sn=p["Sn"], eid_n=sec_panne)
           or f"✓ Sections créées", "ok")

    log_cb(T("log_cas_charge") or "Création cas de charge…")
    fam_g_eid, case_g_eid = create_dead_load_case(host)
    log_cb(T("log_cas_charge_ok", eid_fam=fam_g_eid, eid_cas=case_g_eid)
           or f"✓ Cas de charge — fam={fam_g_eid}, cas={case_g_eid}", "ok")

    counts = {"poteaux": 0, "arbaletriers": 0, "appuis": 0, "pannes_g": 0, "pannes_d": 0, "parois": 0}

    log_cb(T("log_portiques", n=n) or f"Création de {n} portique(s)…")
    for i in range(n):
        Yi      = i * e_val
        pied_g  = (0, Yi, 0);  sommet_g = (0, Yi, Hg)
        pied_d  = (L, Yi, 0);  sommet_d = (L, Yi, Hd)
        faitage = (AR, Yi, H_faitage)

        create_linear_element(host, pied_g, sommet_g, mat_id, sec_poteau, "bar")
        create_linear_element(host, pied_d, sommet_d, mat_id, sec_poteau, "bar")
        counts["poteaux"] += 2

        create_linear_element(host, sommet_g, faitage, mat_id, sec_arbal)
        create_linear_element(host, sommet_d, faitage, mat_id, sec_arbal)
        counts["arbaletriers"] += 2

        create_support(host, pied_g, mat_id, type_appui)
        create_support(host, pied_d, mat_id, type_appui)
        counts["appuis"] += 2

        log_cb(T("log_portique_ok", i=i+1, n=n) or f"  Portique {i+1}/{n} OK")

    positions_g = [k * (Lg - Dbg) / (Npg - 1) for k in range(Npg)]
    positions_d = [k * (Ld - Dbd) / (Npd - 1) for k in range(Npd)]

    log_cb(T("log_pannes_g") or "Création pannes versant gauche…")
    for i in range(n - 1):
        Yi0, Yi1 = i * e_val, (i + 1) * e_val
        sg0 = (0, Yi0, Hg);  f0 = (AR, Yi0, H_faitage)
        sg1 = (0, Yi1, Hg);  f1 = (AR, Yi1, H_faitage)
        for dist in positions_g:
            create_linear_element(
                host,
                point_on_rafter(sg0, f0, dist),
                point_on_rafter(sg1, f1, dist),
                mat_id, sec_panne, relaxation=RELAXATION_PANNES,
            )
            counts["pannes_g"] += 1

    log_cb(T("log_pannes_d") or "Création pannes versant droit…")
    for i in range(n - 1):
        Yi0, Yi1 = i * e_val, (i + 1) * e_val
        sd0 = (L, Yi0, Hd);  f0 = (AR, Yi0, H_faitage)
        sd1 = (L, Yi1, Hd);  f1 = (AR, Yi1, H_faitage)
        for dist in positions_d:
            create_linear_element(
                host,
                point_on_rafter(sd0, f0, dist),
                point_on_rafter(sd1, f1, dist),
                mat_id, sec_panne, relaxation=RELAXATION_PANNES,
            )
            counts["pannes_d"] += 1

    if creer_parois:
        log_cb(T("log_parois") or "Création des parois…")
        Y0 = 0;  Yn = (n - 1) * e_val

        pied_g0  = (0, Y0, 0);  sommet_g0 = (0, Y0, Hg);  faitage0  = (AR, Y0, H_faitage)
        pied_d0  = (L, Y0, 0);  sommet_d0 = (L, Y0, Hd)
        pied_gN  = (0, Yn, 0);  sommet_gN = (0, Yn, Hg);  faitageN  = (AR, Yn, H_faitage)
        pied_dN  = (L, Yn, 0);  sommet_dN = (L, Yn, Hd)

        create_load_area(host, [sommet_g0, faitage0, sommet_d0, pied_d0, pied_g0],
                         "Pignon_1er_portique", "eFloorDeckLoadSpanDirectionX")
        counts["parois"] += 1

        create_load_area(host, [sommet_gN, faitageN, sommet_dN, pied_dN, pied_gN],
                         "Pignon_dernier_portique", "eFloorDeckLoadSpanDirectionX")
        counts["parois"] += 1

        create_load_area(host, [pied_g0, pied_gN, sommet_gN, sommet_g0],
                         "Facade_poteaux_gauche", "eFloorDeckLoadSpanDirectionX")
        counts["parois"] += 1

        create_load_area(host, [pied_d0, pied_dN, sommet_dN, sommet_d0],
                         "Facade_poteaux_droit", "eFloorDeckLoadSpanDirectionX")
        counts["parois"] += 1

        longueur_longitudinale = Yn - Y0
        pts_versant_g = roof_quad_oriented(sommet_g0, faitage0, faitageN, sommet_gN,
                                           longueur_longitudinale, Lg)
        create_load_area(host, pts_versant_g, "Versant_arbaletriers_gauche",
                         "eFloorDeckLoadSpanDirectionY")
        counts["parois"] += 1

        pts_versant_d = roof_quad_oriented(faitage0, sommet_d0, sommet_dN, faitageN,
                                           longueur_longitudinale, Ld)
        create_load_area(host, pts_versant_d, "Versant_arbaletriers_droit",
                         "eFloorDeckLoadSpanDirectionY")
        counts["parois"] += 1

        log_cb(T("log_parois_ok", n=counts["parois"]) or f"✓ {counts['parois']} parois créées", "ok")

    total = sum(counts.values())
    return counts, total, Lg, Ld, H_faitage


# =============================================================================
# INTERFACE STREAMLIT
# =============================================================================

def _init_session():
    """Initialise les valeurs de session par défaut au premier chargement."""
    cfg = load_config()
    defaults = {
        "lang":           cfg.get("language", DEFAULT_LANG),
        "api_server_exe": cfg.get("api_server_exe", DEFAULT_API_SERVER_EXE),
        "host":           DEFAULT_HOST,
        "nouveau_projet": True,
        "nouveau_nom":    "nouveau_projet",
        "fto":            "",
        "n":              5,
        "e":              5.0,
        "Hg":             6.0,
        "Hd":             4.0,
        "L":              18.0,
        "AR":             7.0,
        "F":              1.2,
        "Sp_fam":         "HEA",
        "Sp":             "HEA400",
        "Sa_fam":         "IPE",
        "Sa":             "IPE400",
        "Sn_fam":         "IPE",
        "Sn":             "IPE160",
        "M":              "S275",
        "TypeAppui":      "HINGED",
        "Npg":            5,
        "Npd":            7,
        "Dbg":            0.3,
        "Dbd":            0.3,
        "creer_parois":   True,
        "log_lines":      [],   # liste de (texte, tag)
        "running":        False,
        "api_proc":       None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _append_log(msg: str, tag: str = "info"):
    st.session_state.log_lines.append((msg, tag))


def _run_generation(params: dict, host: str):
    """Exécution synchrone (sous st.spinner) : remplit st.session_state.log_lines."""
    st.session_state.running = True
    st.session_state.log_lines = []

    def log(msg, tag="info"):
        _append_log(msg, tag)

    try:
        log("=" * 52, "head")
        log(f"Fichier : {params.get('fto','')}", "head")
        log(f"API     : {host}", "head")
        log("=" * 52, "head")

        log("Vérification du port API…")
        check_port(host)
        log("✓ API accessible", "ok")

        if params.get("nouveau_projet"):
            log(f"Création du projet : {params['fto']}")
            new_project(host, params["fto"])
            log("✓ Projet créé", "ok")
        else:
            log(f"Ouverture du projet : {params['fto']}")
            open_project(host, params["fto"])
            log("✓ Projet ouvert", "ok")

        counts, total, Lg, Ld, H_faitage = build_structure(host, params, log)

        log("Fermeture du projet…")
        close_project(host)
        log("✓ Projet fermé", "ok")

        log("=" * 52, "head")
        log("GÉNÉRATION RÉUSSIE", "ok")
        log("=" * 52, "head")
        log(f"  {'Portiques':<24}: {params['n']}")
        log(f"  {'Entraxe':<24}: {params['e']} m")
        log(f"  {'Hg / Hd':<24}: {params['Hg']} / {params['Hd']} m")
        log(f"  {'Portée':<24}: {params['L']} m")
        log(f"  {'Abscisse faîtage':<24}: {params['AR']} m")
        log(f"  {'Flèche':<24}: {params['F']} m")
        log(f"  {'H faîtage':<24}: {H_faitage:.3f} m")
        log(f"  {'Lg (versant G)':<24}: {Lg:.3f} m")
        log(f"  {'Ld (versant D)':<24}: {Ld:.3f} m")
        log(f"  {'Type appui':<24}: {params['TypeAppui']}")
        log(f"  {'Poteaux ({Sp})':<24}: {counts['poteaux']}".replace("{Sp}", params['Sp']))
        log(f"  {'Arbalétriers ({Sa})':<24}: {counts['arbaletriers']}".replace("{Sa}", params['Sa']))
        log(f"  {'Pannes G ({Sn})':<24}: {counts['pannes_g']}".replace("{Sn}", params['Sn']))
        log(f"  {'Pannes D ({Sn})':<24}: {counts['pannes_d']}".replace("{Sn}", params['Sn']))
        log(f"  {'Appuis':<24}: {counts['appuis']}")
        if params["creer_parois"]:
            log(f"  {'Parois':<24}: {counts['parois']}")
        log(f"  {'TOTAL éléments':<24}: {total}", "ok")
        log("=" * 52, "head")

    except Exception as ex:
        log(f"ERREUR : {ex}", "error")
        try:
            close_project(host)
        except Exception:
            pass
    finally:
        st.session_state.running = False


# ---------------------------------------------------------------------------
# PAGE PRINCIPALE
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="Steel Frame Generator",
        page_icon="🏗️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _init_session()

    # Charge la langue depuis la session
    load_language(st.session_state.lang)

    # ------------------------------------------------------------------ CSS
    st.markdown("""
    <style>
        /* Sidebar inutilisée */
        [data-testid="collapsedControl"] { display: none; }
        section[data-testid="stSidebar"] { display: none; }

        /* ---- Espacement global réduit ---- */
        /* Réduit le gap vertical entre blocs Streamlit */
        .block-container { padding-top: 1.7rem !important; padding-bottom: 0.5rem !important; }
        div[data-testid="stVerticalBlock"] > div { gap: 0.35rem !important; }

        /* Titre de section */
        .sfg-card-title {
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: .09em;
            text-transform: uppercase;
            color: #6b82a8;
            margin: 6px 0 2px 0;
            padding: 0;
        }

        /* ---- Champs de saisie compacts ---- */
        /* number_input, text_input, selectbox : hauteur réduite */
        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextInput"] input {
            padding-top: 4px !important;
            padding-bottom: 4px !important;
            height: 34px !important;
            font-size: 0.88rem !important;
        }
        div[data-testid="stNumberInput"] > div,
        div[data-testid="stTextInput"]   > div { min-height: 34px !important; }

        /* Boutons +/- du number_input */
        div[data-testid="stNumberInput"] button {
            height: 34px !important;
            padding: 0 6px !important;
        }

        /* Selectbox compact */
        div[data-testid="stSelectbox"] > div > div {
            padding-top: 4px !important;
            padding-bottom: 4px !important;
            min-height: 34px !important;
            font-size: 0.88rem !important;
        }

        /* Options du dropdown selectbox : moins d'espace vertical */
        li[role="option"] {
            padding-top: 4px !important;
            padding-bottom: 4px !important;
            font-size: 0.88rem !important;
            min-height: 28px !important;
        }

        /* Label des champs : serré */
        div[data-testid="stNumberInput"] label,
        div[data-testid="stTextInput"]   label,
        div[data-testid="stSelectbox"]   label {
            font-size: 0.8rem !important;
            margin-bottom: 1px !important;
            padding-bottom: 0 !important;
        }

        /* Checkbox compact */
        div[data-testid="stCheckbox"] { margin-top: 4px !important; margin-bottom: 2px !important; }
        div[data-testid="stCheckbox"] label { font-size: 0.88rem !important; }

        /* Divider invisible — remplacé par l'espacement naturel */
        hr[data-testid="stDivider"] { display: none !important; }

        /* Journal */
        .sfg-log {
            font-family: 'Consolas', 'Menlo', monospace;
            font-size: 0.82rem;
            background: #111827;
            border-radius: 6px;
            padding: 10px 12px;
            height: calc(50vh - 260px);
            min-height: 120px;
            overflow-y: auto;
            line-height: 1.5;
            border: 1px solid #2d3a50;
        }
        .sfg-log .ok    { color: #2CB67D; }
        .sfg-log .error { color: #E05555; }
        .sfg-log .warn  { color: #E8A840; }
        .sfg-log .head  { color: #4A7FE0; }
        .sfg-log .info  { color: #8899BB; }

        /* Bouton principal */
        div[data-testid="stButton"] > button[kind="primary"] {
            background: #1d4ed8;
            border: none;
            font-weight: 600;
            padding: 0.4rem 2rem;
            border-radius: 6px;
            height: 36px !important;
        }
        div[data-testid="stButton"] > button[kind="primary"]:hover { background: #2563eb; }

        /* Expander compact */
        details summary { padding: 6px 10px !important; font-size: 0.88rem !important; }

        /* Footer */
        footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

    # ------------------------------------------------------------------ EN-TÊTE
    st.markdown(
        "<h2 style='margin:0 0 2px 0; font-size:1.35rem;'>🏗️ Steel Frame Generator</h2>"
        f"<p style='color:#6b82a8; margin:0 0 16px 0; font-size:0.8rem;'>"
        f"Génération de portiques métalliques via l'API Advance Design — v{VERSION}</p>",
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------ COLONNES 2/3 | 1/3
    col_form, col_log = st.columns([2, 1], gap="medium")

    # ==================================================================
    # COLONNE GAUCHE — Formulaire (2/3)
    # ==================================================================
    with col_form:

        # ---- Paramètres ----
        with st.expander(T("ui_params_expander") or "⚙️ Paramètres (langue, API, serveur)", expanded=False):
            pc1, pc2 = st.columns([1, 2])
            with pc1:
                lang_choice = st.selectbox(
                    T("ui_language") or "Langue",
                    options=list(LANG_LABELS.keys()),
                    format_func=lambda k: LANG_LABELS[k],
                    index=list(LANG_LABELS.keys()).index(st.session_state.lang),
                    key="_lang_select",
                )
                if lang_choice != st.session_state.lang:
                    st.session_state.lang = lang_choice
                    save_config(lang_choice, st.session_state.api_server_exe)
                    st.rerun()
            with pc2:
                st.session_state.host = st.text_input(
                    T("ui_url_api_ad") or "URL API Advance Design",
                    value=st.session_state.host,
                    key="_host_input",
                )

            st.session_state.api_server_exe = st.text_input(
                T("ui_chemin_exe") or "Chemin AD.API.Srv.exe",
                value=st.session_state.api_server_exe,
                key="_exe_input",
            )
            save_config(st.session_state.lang, st.session_state.api_server_exe)



        # ---- Projet ----
        st.markdown('<div class="sfg-card-title">📁 Projet</div>', unsafe_allow_html=True)
        pj1, pj2, pj3 = st.columns([1, 2, 1])
        with pj1:
            st.session_state.nouveau_projet = st.checkbox(
                T("ui_nouveau_fichier") or "Nouveau fichier",
                value=st.session_state.nouveau_projet,
            )
        with pj2:
            is_new = st.session_state.nouveau_projet
            field = "nouveau_nom" if is_new else "fto"
            tc, bc = st.columns([5, 1])
            with tc:
                if is_new:
                    st.session_state.nouveau_nom = st.text_input(
                        T("ui_nouveau_nom") or "Nom du nouveau projet",
                        value=st.session_state.nouveau_nom,
                    )
                else:
                    st.session_state.fto = st.text_input(
                        T("ui_fichier_existant") or "Chemin du fichier .fto",
                        value=st.session_state.fto,
                        placeholder=r"C:\Projets\mon_projet.fto",
                    )
            with bc:
                st.markdown("<div style='height:1.6rem;'></div>", unsafe_allow_html=True)
                if st.button("📂", key="browse_fto",
                             help=T("ui_btn_parcourir") or "Parcourir…", width="stretch"):
                    res = _native_pick(save=is_new, initial=st.session_state[field])
                    if res is None:
                        st.warning(T("ui_dialog_indispo")
                                   or "Boîte de dialogue indisponible sur ce système.")
                    elif res:
                        st.session_state[field] = res
                        st.rerun()
        with pj3:
            proc = st.session_state.api_proc
            api_running = proc is not None and proc.poll() is None
            if api_running:
                st.success(T("ui_api_active") or "API active", icon="✅")
                if st.button(T("ui_btn_stop_api") or "⏹ Arrêter l'API", width="stretch"):
                    try:
                        proc.terminate()
                        proc.wait(timeout=5)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                    st.session_state.api_proc = None
                    st.rerun()
            else:
                st.caption(T("ui_api_inactive") or "API inactive")
                if st.button(T("ui_btn_start_api") or "▶ Démarrer l'API", width="stretch"):
                    exe = os.path.normpath(st.session_state.api_server_exe)
                    if not os.path.isfile(exe):
                        st.error(T("err_api_server_exe_not_found", path=exe) or f"Introuvable :\n{exe}")
                    else:
                        try:
                            p = subprocess.Popen([exe, "/console"], cwd=os.path.dirname(exe) or None)
                            st.session_state.api_proc = p
                            st.rerun()
                        except Exception as e:
                            st.error(T("err_api_server_start_failed", details=str(e)) or f"Erreur : {e}")


        # ---- Géométrie ----
        st.markdown('<div class="sfg-card-title">📐 Géométrie</div>', unsafe_allow_html=True)
        g1, g2, g3, g4 = st.columns(4)
        with g1:
            st.number_input(T("ui_nb_portiques") or "Nb portiques",  min_value=2,    max_value=25,    step=1,               key="n")
            st.number_input(T("ui_portee") or "Portée L (m)",        min_value=0.1,  max_value=999.0, step=0.1,  format="%.2f", key="L")
        with g2:
            st.number_input(T("ui_entraxe") or "Entraxe e (m)",      min_value=0.1,  max_value=999.0, step=0.1,  format="%.2f", key="e")
            st.number_input(T("ui_ar") or "Abscisse faîtage AR (m)", min_value=0.01, max_value=999.0, step=0.1,  format="%.2f", key="AR")
        with g3:
            st.number_input(T("ui_hg") or "Hg (m)",                  min_value=0.1,  max_value=999.0, step=0.1,  format="%.2f", key="Hg")
            st.number_input(T("ui_fleche") or "Flèche F (m)",        min_value=0.01, max_value=999.0, step=0.01, format="%.2f", key="F")
        with g4:
            st.number_input(T("ui_hd") or "Hd (m)",                  min_value=0.1,  max_value=999.0, step=0.1,  format="%.2f", key="Hd")
            appui_idx = APPUIS_VALIDES.index(st.session_state.TypeAppui) if st.session_state.TypeAppui in APPUIS_VALIDES else 0
            st.session_state.TypeAppui = st.selectbox(
                T("ui_type_appui") or "Type d'appui",
                options=APPUIS_VALIDES,
                format_func=lambda v: _DISPLAY_VALUES.get(v, v),
                index=appui_idx,
            )

        st.session_state.creer_parois = st.checkbox(
            T("ui_creer_parois") or "Créer les parois",
            value=st.session_state.creer_parois,
        )


        # ---- Sections & Matériau ----
        st.markdown('<div class="sfg-card-title">🔩 Sections & Matériau</div>', unsafe_allow_html=True)
        s1, s2, s3, s4 = st.columns([1, 2, 1, 2])
        with s1:
            st.session_state.Sp_fam = st.selectbox(
                T("ui_sec_poteaux") or "Poteaux – Famille",
                FAMILLES, index=FAMILLES.index(st.session_state.Sp_fam), key="sp_fam")
        with s2:
            sp_list = SECTIONS_PAR_FAMILLE[st.session_state.Sp_fam]
            sp_idx  = sp_list.index(st.session_state.Sp) if st.session_state.Sp in sp_list else 0
            st.session_state.Sp = st.selectbox("Profil poteau", sp_list, index=sp_idx, key="sp_profil",
                                               label_visibility="hidden")
        with s3:
            st.session_state.Sa_fam = st.selectbox(
                T("ui_sec_arbaletriers") or "Arbalétriers – Famille",
                FAMILLES, index=FAMILLES.index(st.session_state.Sa_fam), key="sa_fam")
        with s4:
            sa_list = SECTIONS_PAR_FAMILLE[st.session_state.Sa_fam]
            sa_idx  = sa_list.index(st.session_state.Sa) if st.session_state.Sa in sa_list else 0
            st.session_state.Sa = st.selectbox("Profil arbalétrier", sa_list, index=sa_idx, key="sa_profil",
                                               label_visibility="hidden")

        sn1, sn2, sm1, sm2 = st.columns([1, 2, 1, 2])
        with sn1:
            st.session_state.Sn_fam = st.selectbox(
                T("ui_sec_pannes") or "Pannes – Famille",
                FAMILLES, index=FAMILLES.index(st.session_state.Sn_fam), key="sn_fam")
        with sn2:
            sn_list = SECTIONS_PAR_FAMILLE[st.session_state.Sn_fam]
            sn_idx  = sn_list.index(st.session_state.Sn) if st.session_state.Sn in sn_list else 0
            st.session_state.Sn = st.selectbox("Profil panne", sn_list, index=sn_idx, key="sn_profil",
                                               label_visibility="hidden")
        with sm1:
            mat_idx = MATERIAUX_VALIDES.index(st.session_state.M) if st.session_state.M in MATERIAUX_VALIDES else 1
            st.session_state.M = st.selectbox(T("ui_materiau") or "Matériau",
                                              MATERIAUX_VALIDES, index=mat_idx)
        with sm2:
            st.empty()


        # ---- Distribution des pannes ----
        st.markdown('<div class="sfg-card-title">📏 Distribution des pannes</div>', unsafe_allow_html=True)
        p1, p2, p3, p4 = st.columns(4)
        with p1:
            st.number_input(T("ui_npg") or "Npg – versant G", min_value=2,   max_value=99,    step=1,               key="Npg")
        with p2:
            st.number_input(T("ui_dbg") or "Dbg (m)",         min_value=0.0, max_value=999.0, step=0.05, format="%.2f", key="Dbg")
        with p3:
            st.number_input(T("ui_npd") or "Npd – versant D", min_value=2,   max_value=99,    step=1,               key="Npd")
        with p4:
            st.number_input(T("ui_dbd") or "Dbd (m)",         min_value=0.0, max_value=999.0, step=0.05, format="%.2f", key="Dbd")


        # ---- Boutons d'action ----
        btn_c1, btn_c2, btn_c3 = st.columns([3, 1, 3])
        with btn_c1:
            btn_create = st.button(
                "▶ " + (T("ui_btn_creer") or "Générer la structure"),
                type="primary",
                disabled=st.session_state.running,
                width="stretch",
            )
        with btn_c2:
            if st.button("🗑", help=T("ui_btn_effacer") or "Effacer le journal", width="stretch"):
                st.session_state.log_lines = []
                st.rerun()
        with btn_c3:
            if st.session_state.running:
                st.markdown(
                    f"<span style='line-height:36px; font-size:0.88rem; color:#E8A840;'>"
                    f"⏳ {T('ui_generation_en_cours') or 'Génération en cours…'}</span>",
                    unsafe_allow_html=True,
                )

    # ==================================================================
    # COLONNE DROITE — Journal (1/3)
    # ==================================================================
    with col_log:
        # Vue 3D filaire isométrique (dynamique) ; repli sur le schéma fixe si géométrie invalide
        try:
            _preview_p = {k: st.session_state[k]
                          for k in ("n", "e", "Hg", "Hd", "L", "AR", "F",
                                    "Npg", "Npd", "Dbg", "Dbd")}
            st.plotly_chart(_preview_figure(_preview_p), width="stretch",
                            config={"displayModeBar": False})
        except Exception:
            _schema_uri = _schema_data_uri()
            if _schema_uri:
                st.markdown(
                    f'<img src="{_schema_uri}" '
                    f'style="width:100%; border-radius:6px; margin-bottom:6px;" '
                    f'alt="{T("ui_schema_alt") or "Schéma géométrique portique"}">',
                    unsafe_allow_html=True,
                )
        st.markdown(f'<div class="sfg-card-title">{T("ui_journal_execution") or "📋 Journal d\'exécution"}</div>', unsafe_allow_html=True)

        lines_html = "".join(
            f'<div class="{tag}">'
            f'{msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")}</div>'
            for msg, tag in st.session_state.log_lines
        )

        st.markdown(
            f'<div class="sfg-log">{lines_html}</div>',
            unsafe_allow_html=True,
        )

        if st.session_state.log_lines:
            last_tags = [tag for _, tag in st.session_state.log_lines]
            if "error" in last_tags:
                st.error(T("ui_generation_echouee") or "Génération échouée.")
            elif any("RÉUSSIE" in msg or "succes" in msg.lower() or "REUSSIE" in msg.upper() for msg, _ in st.session_state.log_lines):
                st.success(T("ui_generation_reussie") or "Structure générée avec succès.")

    # ==================================================================
    # LANCEMENT
    # ==================================================================
    if btn_create and not st.session_state.running:
        if st.session_state.nouveau_projet:
            nom = st.session_state.nouveau_nom.strip()
            if not nom:
                st.error(T("ui_projet_obligatoire") or "Le nom du projet est obligatoire.")
                st.stop()
            if not nom.lower().endswith(".fto"):
                nom += ".fto"
            fto_path = os.path.join(os.getcwd(), nom)
        else:
            fto_path = st.session_state.fto.strip()
            if not fto_path:
                st.error(T("ui_chemin_obligatoire") or "Veuillez saisir le chemin du fichier .fto.")
                st.stop()

        fto_path = os.path.normpath(fto_path)  # l'API AD exige des separateurs "\"

        params = {
            "fto":            fto_path,
            "nouveau_projet": st.session_state.nouveau_projet,
            "n":              st.session_state.n,
            "e":              st.session_state.e,
            "Hg":             st.session_state.Hg,
            "Hd":             st.session_state.Hd,
            "L":              st.session_state.L,
            "AR":             st.session_state.AR,
            "F":              st.session_state.F,
            "Sp":             st.session_state.Sp,
            "Sa":             st.session_state.Sa,
            "Sn":             st.session_state.Sn,
            "M":              st.session_state.M,
            "TypeAppui":      st.session_state.TypeAppui,
            "Npg":            st.session_state.Npg,
            "Npd":            st.session_state.Npd,
            "Dbg":            st.session_state.Dbg,
            "Dbd":            st.session_state.Dbd,
            "creer_parois":   st.session_state.creer_parois,
        }

        try:
            validate(params)
        except ValueError as ex:
            st.error(str(ex))
            st.stop()

        host = st.session_state.host.strip().rstrip("/")

        with st.spinner(T("ui_generation_en_cours") or "Génération en cours…"):
            _run_generation(params, host)

        st.rerun()

    # ------------------------------------------------------------------ PIED DE PAGE
    st.markdown(
        "<hr style='border-color:#2d3a50; margin-top:24px;'>"
        "<p style='text-align:center; color:#3d4f6b; font-size:0.75rem;'>"
        "Steel Frame Generator — Interface web Streamlit · "
        "<a href='https://github.com/Graitec-Group/advance-design-api' style='color:#4A7FE0;'>GitHub API</a> · "
        "<a href='https://www.graitec.com' style='color:#4A7FE0;'>Graitec</a>"
        "</p>",
        unsafe_allow_html=True,
    )


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

def _launch_as_exe():
    """
    Point d'entrée PyInstaller (processus lanceur).
    - Positionne la sentinelle d'environnement.
    - Relancel'exe lui-même via Popen : cette fois le worker voit la
      sentinelle et appelle main() → Streamlit démarre normalement.
    - Ouvre le navigateur après 3 s.
    - Attend la fin du worker.
    """
    import threading
    import time
    import webbrowser
    import subprocess as _sp

    port = 8501
    url  = f"http://localhost:{port}"

    # Environnement du sous-processus : sentinelle + options Streamlit
    # Seule la sentinelle est transmise — les options Streamlit
    # sont passées en argv dans le worker pour éviter tout conflit
    env = os.environ.copy()
    env[_SFG_STREAMLIT_WORKER] = "1"
    # Forcer le mode non-développement pour éviter le conflit server.port
    env["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

    # sys.executable est l'exe lui-même — on le relance avec la sentinelle
    _proc = _sp.Popen([sys.executable], env=env)

    # Ouvre le navigateur après que Streamlit soit prêt
    def _open_browser():
        time.sleep(4)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()

    try:
        _proc.wait()
    except KeyboardInterrupt:
        _proc.terminate()


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        # Mode PyInstaller
        if os.environ.get(_SFG_STREAMLIT_WORKER) == "1":
            # Sous-processus worker : lancer Streamlit directement via CLI
            # On passe les options en argv pour éviter les conflits
            # avec les variables d'environnement STREAMLIT_*
            from streamlit.web import cli as _st_cli
            script = os.path.join(sys._MEIPASS, "steel_frame_web.py")
            sys.argv = [
                "streamlit", "run", script,
                "--server.port",                        "8501",
                "--server.address",                     "localhost",
                "--server.headless",                    "true",
                "--global.developmentMode",             "false",
                "--browser.gatherUsageStats",           "false",
                "--theme.base",                         "dark",
                "--theme.primaryColor",                 "#1d4ed8",
                "--theme.backgroundColor",              "#0f1623",
                "--theme.secondaryBackgroundColor",     "#1e2634",
                "--theme.textColor",                    "#e2e8f0",
            ]
            _st_cli.main(standalone_mode=False)
        else:
            # Processus principal : lanceur + ouverture navigateur
            _launch_as_exe()
    else:
        # Mode normal : streamlit run steel_frame_web.py
        main()
