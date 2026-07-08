"""
SteelFrameGenerator_qt_material.py
====================================
Version PySide6 + qt-material avec menu Paramètres (Thèmes + Langues + Configuration).
Interface graphique pour SteelFrameGenerator.
Crée une structure de portiques métalliques dans Advance Design via l'API REST.

Prérequis :
pip install PySide6 qt-material requests

Utilisation :
python SteelFrameGenerator_qt_material.py
"""

# =============================================================================
# CHANGELOG – SteelFrameGenerator_qt_material.py
# =============================================================================

# 1.24 (v24) - Ajout de la langue Polonais (polish.ini) dans le menu
#              Parametres > Langue
#            - Ajout de la cle lang_polonais dans french.ini et english.ini

# 1.23a (v23a) - Correction : config_sf.ini est desormais lu/ecrit dans le
#              repertoire de l'executable (PyInstaller) et non dans le
#              repertoire temporaire (_MEIPASS)

# 1.23 (v23) - Ajout du fichier config.ini pour sauvegarder de façon persistante :
#              le thème utilisé, la langue utilisée, le chemin de l'exécutable API
#            - Création automatique du fichier config.ini avec les valeurs par
#              défaut s'il n'existe pas
#            - Chargement du config.ini au démarrage de l'application
#            - Sauvegarde du config.ini à chaque changement de thème/langue/config
#              et à la fermeture de l'application

# 1.22 (v22) - Ajout du menu Fichier avec "À propos" et "Quitter"
#            - Ajout du sous-menu Configuration dans Paramètres pour régler
#              l'exécutable du serveur API (AD.API.Srv.exe)
#            - Ajout du bouton "Démarrer API" dans la carte Projet
#            - Gestion du démarrage/arrêt du serveur API depuis l'interface

# 1.21 (v21) - Démarrage en plein écran (maximized)
#            - Menu Paramètres > Fenêtre > Plein écran
#            - Suppression du centrage fixe et des dimensions limitées

# 1.20 (v20) - Menu Paramètres avec sous-menus Thèmes et Langues
#            - Suppression de l'encart Langue de la fenêtre principale
#            - Suppression du titre de l'interface principale (dans la barre de titre)
#            - Ajout de la constante VERSION
#            - Thèmes binaires : Clair (light_blue) / Sombre (dark_blue)
#            - Langues : Français / English
#            - Correction : nettoyage du menuBar lors du changement de langue

# 1.07 (v19) - Migration complète de tkinter vers PySide6 + qt-material
#            - Thème sombre par défaut (dark_teal.xml)
#            - UI responsive avec QSplitter, QScrollArea
#            - ComboBox en cascade pour les sections (famille → profil)
#            - Traductions externalisées (french.ini / english.ini)
#            - Support des thèmes qt-material dynamiques
#            - Sélecteur de thème intégré dans la carte Langue

# =============================================================================

import configparser
import math
import os
import socket
import subprocess
import sys
import threading
import urllib.parse
from pathlib import Path

try:
    from PySide6.QtCore import Qt, QTimer, Signal, QObject
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QFormLayout, QGroupBox, QLabel, QLineEdit, QComboBox,
        QCheckBox, QPushButton, QTextEdit, QSplitter, QScrollArea, QFrame,
        QFileDialog, QMessageBox, QProgressBar, QSpinBox, QDoubleSpinBox,
        QSizePolicy, QSpacerItem, QStatusBar, QMenuBar, QMenu, QToolButton,
        QDialog, QDialogButtonBox, QTabWidget, QStackedWidget
    )
    from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QAction
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PySide6", "qt-material"])
    from PySide6.QtCore import Qt, QTimer, Signal, QObject
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QFormLayout, QGroupBox, QLabel, QLineEdit, QComboBox,
        QCheckBox, QPushButton, QTextEdit, QSplitter, QScrollArea, QFrame,
        QFileDialog, QMessageBox, QProgressBar, QSpinBox, QDoubleSpinBox,
        QSizePolicy, QSpacerItem, QStatusBar, QMenuBar, QMenu, QToolButton,
        QDialog, QDialogButtonBox, QTabWidget, QStackedWidget
    )
    from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QAction

try:
    from qt_material import apply_stylesheet, list_themes
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "qt-material"])
    from qt_material import apply_stylesheet, list_themes

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# ---------------------------------------------------------------------------
# Constante de version
# ---------------------------------------------------------------------------

VERSION = "1.24"

# ---------------------------------------------------------------------------
# Thèmes qt-material binaires (Clair / Sombre)
# ---------------------------------------------------------------------------

THEME_SOMBRE = "dark_blue.xml"
THEME_CLAIR = "light_blue.xml"
DEFAULT_THEME = THEME_SOMBRE
CURRENT_THEME_FILE = DEFAULT_THEME

# ---------------------------------------------------------------------------
# Exécutable serveur API par défaut
# ---------------------------------------------------------------------------

DEFAULT_API_SERVER_EXE = r"C:\\Program Files\\Graitec\\Advance Design\\2027\\Bin\\AD.API.Srv.exe"

# ---------------------------------------------------------------------------
# Fichier de configuration persistant (config.ini)
# ---------------------------------------------------------------------------

DEFAULT_LANG_FOR_CONFIG = "fr"

def get_app_dir():
    """Retourne le répertoire de l'exécutable (PyInstaller) ou du script .py.
    Permet de lire/écrire config_sf.ini a cote de l'exe compile, et non dans
    le repertoire temporaire d'extraction (_MEIPASS) utilise par PyInstaller."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_FILE = os.path.join(get_app_dir(), "config_sf.ini")

DEFAULT_CONFIG = {
    "General": {
        "theme": DEFAULT_THEME,
        "language": DEFAULT_LANG_FOR_CONFIG,
        "api_server_exe": DEFAULT_API_SERVER_EXE,
    }
}


def load_config():
    """Charge le fichier config.ini. Le crée avec les valeurs par défaut
    s'il n'existe pas ou s'il est invalide/incomplet."""
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

    if "theme" not in section:
        section["theme"] = DEFAULT_CONFIG["General"]["theme"]
        needs_save = True
    if "language" not in section:
        section["language"] = DEFAULT_CONFIG["General"]["language"]
        needs_save = True
    if "api_server_exe" not in section:
        section["api_server_exe"] = DEFAULT_CONFIG["General"]["api_server_exe"]
        needs_save = True

    if needs_save:
        save_config_parser(parser)

    return {
        "theme": section.get("theme", DEFAULT_THEME),
        "language": section.get("language", DEFAULT_LANG_FOR_CONFIG),
        "api_server_exe": section.get("api_server_exe", DEFAULT_API_SERVER_EXE),
    }


def save_config_parser(parser):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            parser.write(f)
    except Exception:
        pass


def save_config(theme, language, api_server_exe):
    """Sauvegarde l'état courant (thème, langue, exécutable API) dans config.ini."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser["General"] = {
        "theme": theme,
        "language": language,
        "api_server_exe": api_server_exe,
    }
    save_config_parser(parser)


APP_CONFIG = load_config()

# ---------------------------------------------------------------------------
# Traductions externes (.ini)
# ---------------------------------------------------------------------------

LANG_FILES = {
    "fr": "french.ini",
    "en": "english.ini",
    "pl": "polish.ini",
}

DEFAULT_LANG = "fr"
CURRENT_LANG = DEFAULT_LANG
MESSAGES = {}
DISPLAY_VALUES = {}


def load_language(lang_code):
    global MESSAGES, CURRENT_LANG, DISPLAY_VALUES

    lang_code = lang_code if lang_code in LANG_FILES else DEFAULT_LANG
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ini_path = os.path.join(base_dir, LANG_FILES[lang_code])

    if not os.path.isfile(ini_path):
        if lang_code != DEFAULT_LANG:
            return load_language(DEFAULT_LANG)
        raise FileNotFoundError(f"Language file not found: {ini_path}")

    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(ini_path, encoding="utf-8")

    if "messages" not in parser:
        raise KeyError(f"Missing [messages] section in {ini_path}")

    MESSAGES = dict(parser["messages"])
    CURRENT_LANG = lang_code
    DISPLAY_VALUES = {
        "HINGED": MESSAGES.get("appui_hinged", "HINGED"),
        "FIXED": MESSAGES.get("appui_fixed", "FIXED"),
    }
    return MESSAGES


def M(key, **kw):
    value = MESSAGES.get(key, key)
    value = value.replace("\\n", "\n")
    return value.format(**kw) if kw else value


# Initialisation langue et thème depuis le config.ini
load_language(APP_CONFIG["language"])
CURRENT_THEME_FILE = APP_CONFIG["theme"] if APP_CONFIG["theme"] in (THEME_SOMBRE, THEME_CLAIR) else DEFAULT_THEME

# ---------------------------------------------------------------------------
# Constantes métier
# ---------------------------------------------------------------------------

DEFAULT_HOST = "http://localhost:52000"

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

# ---------------------------------------------------------------------------
# Relaxation Ry + Rz aux deux extrémités — connexion rotulée pour les pannes
# ---------------------------------------------------------------------------

RELAXATION_PANNES = {
    "startBoundaryConnection": {
        "relaxationTx": False,
        "relaxationTy": False,
        "relaxationTz": False,
        "relaxationRx": False,
        "relaxationRy": True,
        "relaxationRz": True,
    },
    "endBoundaryConnection": {
        "relaxationTx": False,
        "relaxationTy": False,
        "relaxationTz": False,
        "relaxationRx": False,
        "relaxationRy": True,
        "relaxationRz": True,
    },
}

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def check_port(host: str) -> None:
    parsed = urllib.parse.urlparse(host)
    hostname = parsed.hostname
    port = parsed.port
    if hostname is None:
        raise ValueError(M("err_url_invalide", host=host))
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    result = sock.connect_ex((hostname, port))
    sock.close()
    if result != 0:
        raise ConnectionError(M("err_port_inaccessible", hostname=hostname, port=port))


def _check(response: requests.Response, label: str) -> dict:
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        try:
            body = response.json()
        except Exception:
            body = response.text[:500]
        raise RuntimeError(M("err_http", label=label, status=response.status_code, body=body)) from e

    data = response.json()
    details = data.get("details", {})
    if not details.get("success", True):
        messages = "; ".join(d.get("message", "") for d in details.get("diagnostics", []))
        raise RuntimeError(M("err_api", label=label, messages=messages))
    return data


def new_project(host, fto_path):
    resp = requests.post(
        f"{host}/api/Model/management/NewProject",
        params={"filename": fto_path},
        json={},
        timeout=30
    )
    _check(resp, "NewProject")


def open_project(host, fto_path):
    resp = requests.post(
        f"{host}/api/Model/management/OpenProject",
        params={"filename": fto_path},
        json={},
        timeout=30
    )
    _check(resp, "OpenProject")


def close_project(host):
    try:
        requests.post(f"{host}/api/Model/management/CloseProject", json={}, timeout=15)
    except Exception:
        pass


def create_material(host, name):
    props = STEEL_PROPS[name]
    data = _check(
        requests.post(
            f"{host}/api/Model/materials/CreateMaterial",
            json={"$type": "MaterialSteel", "name": name, **props}
        ),
        "CreateMaterial"
    )
    return data["data"]["value"]


def create_section(host, section_name):
    data = _check(
        requests.post(
            f"{host}/api/Model/sections/CreateSection",
            params={"sectionName": section_name}
        ),
        f"CreateSection({section_name})"
    )
    return data["data"]["value"]


def create_linear_element(host, pt_start, pt_end, mat_id, sec_id,
                           beam_type="beamWStandardBending", relaxation=None):
    payload = {
        "$type": "ElementLinear",
        "geomPtStart": {"x": pt_start[0], "y": pt_start[1], "z": pt_start[2]},
        "geomPtEnd": {"x": pt_end[0], "y": pt_end[1], "z": pt_end[2]},
        "material": {"value": mat_id},
        "section": {"value": sec_id},
        "linearElementType": "eLinearElementFEMTypeGeneral",
        "generalBeamType": beam_type,
    }
    if relaxation is not None:
        payload["relaxationTotale"] = relaxation

    data = _check(
        requests.post(f"{host}/api/Model/elements/CreateElement", json=payload),
        "CreateElement(linear)"
    )
    return data["data"]["value"]


def create_support(host, pt, mat_id, type_appui):
    geom_pt = {"x": pt[0], "y": pt[1], "z": pt[2]}
    if type_appui == "FIXED":
        restraints = {"tx": True, "ty": True, "tz": True, "rx": True, "ry": True, "rz": True}
    else:
        restraints = {"tx": True, "ty": True, "tz": True, "rx": False, "ry": False, "rz": False}

    payload = {
        "$type": "ElementRigidPunctualSupport",
        "geomPt": geom_pt,
        "material": {"value": mat_id},
        "constraintsType": "other",
        "restraints": restraints,
    }
    data = _check(
        requests.post(f"{host}/api/Model/elements/CreateElement", json=payload),
        f"CreateSupport({type_appui})"
    )
    return data["data"]["value"]


def create_dead_load_case(host):
    fam_data = _check(
        requests.post(
            f"{host}/api/Model/elements/CreateInformationalElement",
            json={"$type": "LoadCaseFamily_DeadLoads", "name": M("ad_famille_g")},
        ),
        "CreateFamily(G)",
    )
    fam_eid = fam_data["data"]["value"]

    case_data = _check(
        requests.post(
            f"{host}/api/Model/elements/CreateInformationalElement",
            json={
                "$type": "LoadCase_DeadLoads",
                "name": M("ad_cas_g"),
                "loadCaseFamilyID": {"value": fam_eid},
                "field": {"x": 0.0, "y": 0.0, "z": -1.0},
            },
        ),
        "CreateCase(G1)",
    )
    case_eid = case_data["data"]["value"]
    return fam_eid, case_eid


def create_load_area(host, pts_list, label="LoadArea", span_direction=None):
    payload = {
        "$type": "ElementLoadArea",
        "geomPtsList": [{"x": p[0], "y": p[1], "z": p[2]} for p in pts_list],
    }
    if span_direction:
        payload["loadTransferProperties"] = {
            "loadTransferMethodType": "eLoadTransferMethodAuto",
            "loadTransferSpanDirectionType": span_direction,
        }
    data = _check(
        requests.post(f"{host}/api/Model/elements/CreateElement", json=payload),
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
    if not (2 <= p["n"] <= 25): errors.append(M("val_n"))
    if p["e"] <= 0: errors.append(M("val_e"))
    if p["Hg"] <= 0: errors.append(M("val_Hg"))
    if p["Hd"] <= 0: errors.append(M("val_Hd"))
    if p["L"] <= 0: errors.append(M("val_L"))
    if not (0 < p["AR"] < p["L"]): errors.append(M("val_AR"))
    if p["F"] <= 0: errors.append(M("val_F"))
    if p["M"] not in MATERIAUX_VALIDES: errors.append(M("val_materiau"))
    if p["TypeAppui"] not in APPUIS_VALIDES: errors.append(M("val_appui"))

    for key, role_key in (("Sp", "role_poteaux"), ("Sa", "role_arbaletriers"), ("Sn", "role_pannes")):
        if p[key] not in SECTIONS_VALIDES:
            errors.append(M("val_section", role=M(role_key), nom=p[key]))

    if p["Npg"] < 2: errors.append(M("val_Npg"))
    if p["Npd"] < 2: errors.append(M("val_Npd"))
    if p["Dbg"] < 0: errors.append(M("val_Dbg"))
    if p["Dbd"] < 0: errors.append(M("val_Dbd"))

    if not errors:
        H_faitage = max(p["Hg"], p["Hd"]) + p["F"]
        Lg = math.sqrt(p["AR"]**2 + (H_faitage - p["Hg"])**2)
        Ld = math.sqrt((p["L"] - p["AR"])**2 + (H_faitage - p["Hd"])**2)
        if p["Dbg"] >= Lg:
            errors.append(M("val_Dbg_long", dbg=p["Dbg"], lg=Lg))
        if p["Dbd"] >= Ld:
            errors.append(M("val_Dbd_long", dbd=p["Dbd"], ld=Ld))

    if errors:
        raise ValueError("\n".join(e for e in errors))


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def build_structure(host, p, log_cb):
    n, e_val = p["n"], p["e"]
    Hg, Hd, L, AR, F = p["Hg"], p["Hd"], p["L"], p["AR"], p["F"]
    Npg, Npd, Dbg, Dbd = p["Npg"], p["Npd"], p["Dbg"], p["Dbd"]
    type_appui = p["TypeAppui"]
    creer_parois = p.get("creer_parois", False)

    H_faitage = max(Hg, Hd) + F
    Lg = math.sqrt(AR**2 + (H_faitage - Hg)**2)
    Ld = math.sqrt((L - AR)**2 + (H_faitage - Hd)**2)

    log_cb(M("log_materiau", nom=p["M"]))
    mat_id = create_material(host, p["M"])
    log_cb(M("log_materiau_ok", nom=p["M"], eid=mat_id))

    log_cb(M("log_sections"))
    sec_poteau = create_section(host, p["Sp"])
    sec_arbal = create_section(host, p["Sa"])
    sec_panne = create_section(host, p["Sn"])
    log_cb(M("log_sections_ok", Sp=p["Sp"], eid_p=sec_poteau, Sa=p["Sa"], eid_a=sec_arbal, Sn=p["Sn"], eid_n=sec_panne))

    log_cb(M("log_cas_charge"))
    fam_g_eid, case_g_eid = create_dead_load_case(host)
    log_cb(M("log_cas_charge_ok", eid_fam=fam_g_eid, eid_cas=case_g_eid))

    counts = {"poteaux": 0, "arbaletriers": 0, "appuis": 0, "pannes_g": 0, "pannes_d": 0, "parois": 0}

    log_cb(M("log_portiques", n=n))
    for i in range(n):
        Yi = i * e_val
        pied_g = (0, Yi, 0); sommet_g = (0, Yi, Hg)
        pied_d = (L, Yi, 0); sommet_d = (L, Yi, Hd)
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

        log_cb(M("log_portique_ok", i=i+1, n=n))

    positions_g = [k * (Lg - Dbg) / (Npg - 1) for k in range(Npg)]
    positions_d = [k * (Ld - Dbd) / (Npd - 1) for k in range(Npd)]

    log_cb(M("log_pannes_g"))
    for i in range(n - 1):
        Yi0, Yi1 = i * e_val, (i + 1) * e_val
        sg0 = (0, Yi0, Hg); f0 = (AR, Yi0, H_faitage)
        sg1 = (0, Yi1, Hg); f1 = (AR, Yi1, H_faitage)
        for dist in positions_g:
            create_linear_element(
                host,
                point_on_rafter(sg0, f0, dist),
                point_on_rafter(sg1, f1, dist),
                mat_id, sec_panne,
                relaxation=RELAXATION_PANNES,
            )
            counts["pannes_g"] += 1

    log_cb(M("log_pannes_d"))
    for i in range(n - 1):
        Yi0, Yi1 = i * e_val, (i + 1) * e_val
        sd0 = (L, Yi0, Hd); f0 = (AR, Yi0, H_faitage)
        sd1 = (L, Yi1, Hd); f1 = (AR, Yi1, H_faitage)
        for dist in positions_d:
            create_linear_element(
                host,
                point_on_rafter(sd0, f0, dist),
                point_on_rafter(sd1, f1, dist),
                mat_id, sec_panne,
                relaxation=RELAXATION_PANNES,
            )
            counts["pannes_d"] += 1

    if creer_parois:
        log_cb(M("log_parois"))

        Y0 = 0
        Yn = (n - 1) * e_val

        pied_g0 = (0, Y0, 0); sommet_g0 = (0, Y0, Hg)
        pied_d0 = (L, Y0, 0); sommet_d0 = (L, Y0, Hd)
        faitage0 = (AR, Y0, H_faitage)

        pied_gN = (0, Yn, 0); sommet_gN = (0, Yn, Hg)
        pied_dN = (L, Yn, 0); sommet_dN = (L, Yn, Hd)
        faitageN = (AR, Yn, H_faitage)

        pts_pignon_1 = [sommet_g0, faitage0, sommet_d0, pied_d0, pied_g0]
        create_load_area(host, pts_pignon_1, "Pignon_1er_portique", span_direction="eFloorDeckLoadSpanDirectionX")
        counts["parois"] += 1
        log_cb(M("log_paroi_pignon1"))

        pts_pignon_N = [sommet_gN, faitageN, sommet_dN, pied_dN, pied_gN]
        create_load_area(host, pts_pignon_N, "Pignon_dernier_portique", span_direction="eFloorDeckLoadSpanDirectionX")
        counts["parois"] += 1
        log_cb(M("log_paroi_pignonN"))

        pts_facade_g = [pied_g0, pied_gN, sommet_gN, sommet_g0]
        create_load_area(host, pts_facade_g, "Facade_poteaux_gauche", span_direction="eFloorDeckLoadSpanDirectionX")
        counts["parois"] += 1
        log_cb(M("log_paroi_facade_g"))

        pts_facade_d = [pied_d0, pied_dN, sommet_dN, sommet_d0]
        create_load_area(host, pts_facade_d, "Facade_poteaux_droit", span_direction="eFloorDeckLoadSpanDirectionX")
        counts["parois"] += 1
        log_cb(M("log_paroi_facade_d"))

        longueur_longitudinale = Yn - Y0

        pts_versant_g = roof_quad_oriented(
            sommet_g0, faitage0, faitageN, sommet_gN,
            longueur_longitudinale, Lg
        )
        create_load_area(host, pts_versant_g, "Versant_arbaletriers_gauche", span_direction="eFloorDeckLoadSpanDirectionY")
        counts["parois"] += 1
        log_cb(M("log_paroi_toiture_g"))

        pts_versant_d = roof_quad_oriented(
            faitage0, sommet_d0, sommet_dN, faitageN,
            longueur_longitudinale, Ld
        )
        create_load_area(host, pts_versant_d, "Versant_arbaletriers_droit", span_direction="eFloorDeckLoadSpanDirectionY")
        counts["parois"] += 1
        log_cb(M("log_paroi_toiture_d"))

        log_cb(M("log_parois_ok", n=counts["parois"]))

    total = sum(counts.values())
    return counts, total, Lg, Ld, H_faitage


# ---------------------------------------------------------------------------
# Signaux pour thread-safe logging
# ---------------------------------------------------------------------------

class LogSignals(QObject):
    log_message = Signal(str, str)
    status_message = Signal(str)
    finished = Signal()
    error = Signal(str)


# ---------------------------------------------------------------------------
# Dialogues
# ---------------------------------------------------------------------------

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(M("menu_about"))
        self.setModal(True)
        self.resize(340, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Steel Frame Generator")
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(False)
        title.setStyleSheet("font-size:18px; font-weight:bold;")
        layout.addWidget(title)

        version = QLabel(f"Version : {VERSION}")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)

        desc = QLabel(M("about_description"))
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8899BB;")
        layout.addWidget(desc)

        links_html = ('<a href="https://github.com/Graitec-Group/advance-design-api">Depot GitHub de l API</a><br>'
                      '<a href="https://www.graitec.com">Site de Graitec</a>')
        links = QLabel(links_html)
        links.setAlignment(Qt.AlignCenter)
        links.setWordWrap(True)
        links.setTextFormat(Qt.RichText)
        links.setTextInteractionFlags(Qt.TextBrowserInteraction)
        links.setOpenExternalLinks(True)
        layout.addWidget(links)

        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons, alignment=Qt.AlignHCenter)


class ApiServerConfigDialog(QDialog):
    def __init__(self, api_server_exe: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(M("menu_configuration"))
        self.setModal(True)
        self.resize(640, 140)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(6)
        form.setHorizontalSpacing(12)
        layout.addLayout(form)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        self.exe_edit = QLineEdit(api_server_exe)
        browse_btn = QPushButton(M("ui_parcourir"))
        browse_btn.clicked.connect(self.browse_exe)

        row_layout.addWidget(self.exe_edit, 1)
        row_layout.addWidget(browse_btn)

        form.addRow(M("api_server_exe"), row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse_exe(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            M("browse_exe_title"),
            self.exe_edit.text().strip() or "",
            M("browse_exe_filter")
        )
        if filename:
            self.exe_edit.setText(os.path.normpath(filename))

    def get_value(self):
        return os.path.normpath(self.exe_edit.text().strip())


# ---------------------------------------------------------------------------
# Application principale (PySide6 + qt-material)
# ---------------------------------------------------------------------------

class PortiquesApp(QMainWindow):
    def __init__(self, app_ref):
        super().__init__()
        self.app_ref = app_ref
        self._running = False
        self.log_signals = LogSignals()
        self.log_signals.log_message.connect(self._on_log_message)
        self.log_signals.status_message.connect(self._on_status_message)
        self.log_signals.finished.connect(self._on_finished)
        self.log_signals.error.connect(self._on_error)

        self._build_vars()
        self._build_ui()
        self._toggle_nouveau_projet()
        self._show_maximized()

    def _build_vars(self):
        self.v_lang = CURRENT_LANG
        self.v_fto = ""
        self.v_host = DEFAULT_HOST
        self.v_n = 5
        self.v_e = 5.0
        self.v_Hg = 6.0
        self.v_Hd = 4.0
        self.v_L = 18.0
        self.v_AR = 7.0
        self.v_F = 1.2
        self.v_Sp = "HEA400"
        self.v_Sa = "IPE400"
        self.v_Sn = "IPE160"
        self.v_Sp_fam = "HEA"
        self.v_Sa_fam = "IPE"
        self.v_Sn_fam = "IPE"
        self.v_M = "S275"
        self.v_appui = "HINGED"
        self.v_Npg = 5
        self.v_Npd = 7
        self.v_Dbg = 0.3
        self.v_Dbd = 0.3
        self.v_nouveau_projet = True
        self.v_nouveau_nom = "nouveau_projet"
        self.v_creer_parois = True
        self.api_server_exe = APP_CONFIG.get("api_server_exe", DEFAULT_API_SERVER_EXE)
        self.api_server_process = None
        self.api_server_started_by_viewer = False

    def _save_config(self):
        """Sauvegarde l'état courant (thème, langue, exécutable API) dans config.ini."""
        save_config(CURRENT_THEME_FILE, CURRENT_LANG, self.api_server_exe)

    def _show_maximized(self):
        """Démarre la fenêtre en plein écran (maximisé)."""
        self.showMaximized()

    def _build_ui(self):
        self.setWindowTitle(f"{M('ui_fenetre')} — v{VERSION}")

        # Menu Bar
        self._build_menu_bar()

        # Widget central
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Séparateur principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, 1)

        # --- Panneau gauche : formulaire ---
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 12, 0)
        left_layout.setSpacing(16)

        self._build_file_card(left_layout)
        self._build_geo_card(left_layout)
        self._build_sections_card(left_layout)
        self._build_pannes_card(left_layout)
        left_layout.addStretch()

        left_scroll.setWidget(left_widget)
        splitter.addWidget(left_scroll)

        # --- Panneau droit : journal ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        log_header = QLabel(M("ui_card_journal"))
        log_header_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        log_header.setFont(log_header_font)
        right_layout.addWidget(log_header)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        right_layout.addWidget(self.log_text, 1)

        splitter.addWidget(right_widget)
        splitter.setSizes([520, 520])

        # Barre de statut
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(M("status_pret"))

        # Barre d'outils bas
        bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 8, 0, 0)
        bottom_layout.setSpacing(12)

        btn_container = QWidget()
        btn_hbox = QHBoxLayout(btn_container)
        btn_hbox.setContentsMargins(0, 0, 0, 0)
        btn_hbox.setSpacing(12)

        self.btn_clear = QPushButton(M("ui_btn_effacer"))
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.clicked.connect(self._clear_log)
        btn_hbox.addWidget(self.btn_clear)

        self.btn_run = QPushButton(M("ui_btn_creer"))
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.setMinimumWidth(180)
        self.btn_run.clicked.connect(self._on_run)
        btn_hbox.addWidget(self.btn_run)

        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_container)

        main_layout.addWidget(bottom_bar)

    def _clear_menu_bar(self):
        """Nettoie complètement la barre de menu."""
        menu_bar = self.menuBar()
        if menu_bar is not None:
            menu_bar.clear()

    def _build_menu_bar(self):
        menu_bar = self.menuBar()
        menu_bar.clear()

        # Menu Fichier
        menu_fichier = menu_bar.addMenu(M("menu_fichier"))

        act_about = QAction(M("menu_about"), self)
        act_about.triggered.connect(self._open_about_dialog)
        menu_fichier.addAction(act_about)

        menu_fichier.addSeparator()

        act_quit = QAction(M("menu_quit"), self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        menu_fichier.addAction(act_quit)

        # Menu Paramètres
        menu_params = menu_bar.addMenu(M("menu_parametres"))

        # Sous-menu Thèmes
        menu_themes = QMenu(M("menu_themes"), self)
        self.action_theme_sombre = QAction(M("menu_theme_sombre"), self, checkable=True)
        self.action_theme_sombre.setChecked(CURRENT_THEME_FILE == THEME_SOMBRE)
        self.action_theme_sombre.triggered.connect(lambda: self._set_theme(THEME_SOMBRE))
        menu_themes.addAction(self.action_theme_sombre)

        self.action_theme_clair = QAction(M("menu_theme_clair"), self, checkable=True)
        self.action_theme_clair.setChecked(CURRENT_THEME_FILE == THEME_CLAIR)
        self.action_theme_clair.triggered.connect(lambda: self._set_theme(THEME_CLAIR))
        menu_themes.addAction(self.action_theme_clair)

        menu_params.addMenu(menu_themes)
        menu_params.addSeparator()

        # Sous-menu Langues
        menu_langues = QMenu(M("menu_langues"), self)
        self.action_lang_fr = QAction("Français", self, checkable=True)
        self.action_lang_fr.setChecked(CURRENT_LANG == "fr")
        self.action_lang_fr.triggered.connect(lambda: self._set_language("fr"))
        menu_langues.addAction(self.action_lang_fr)

        self.action_lang_en = QAction("English", self, checkable=True)
        self.action_lang_en.setChecked(CURRENT_LANG == "en")
        self.action_lang_en.triggered.connect(lambda: self._set_language("en"))
        menu_langues.addAction(self.action_lang_en)

        self.action_lang_pl = QAction(M("lang_polonais"), self, checkable=True)
        self.action_lang_pl.setChecked(CURRENT_LANG == "pl")
        self.action_lang_pl.triggered.connect(lambda: self._set_language("pl"))
        menu_langues.addAction(self.action_lang_pl)

        menu_params.addMenu(menu_langues)
        menu_params.addSeparator()

        # Sous-menu Configuration
        menu_configuration = QMenu(M("menu_configuration"), self)
        act_api_server = QAction(M("menu_api_server"), self)
        act_api_server.triggered.connect(self._open_configuration_dialog)
        menu_configuration.addAction(act_api_server)
        menu_params.addMenu(menu_configuration)

    def _open_about_dialog(self):
        dlg = AboutDialog(self)
        dlg.exec()

    def _open_configuration_dialog(self):
        dlg = ApiServerConfigDialog(self.api_server_exe, self)
        if dlg.exec() == QDialog.Accepted:
            self.api_server_exe = dlg.get_value()
            self._save_config()

    def _set_theme(self, theme_file):
        global CURRENT_THEME_FILE
        CURRENT_THEME_FILE = theme_file
        is_light = theme_file.startswith("light_")
        apply_stylesheet(self.app_ref, theme=theme_file, invert_secondary=is_light)
        self._apply_custom_styles()
        self.action_theme_sombre.setChecked(theme_file == THEME_SOMBRE)
        self.action_theme_clair.setChecked(theme_file == THEME_CLAIR)
        self._save_config()

    def _apply_custom_styles(self):
        """Surcharge les styles qt-material pour réduire la hauteur des champs
        et corriger le padding des listes déroulantes."""

        from PySide6.QtWidgets import QListView

        for w in self.findChildren(QLineEdit):
            w.setFixedHeight(28)

        for w in self.findChildren(QSpinBox):
            w.setFixedHeight(28)

        for w in self.findChildren(QDoubleSpinBox):
            w.setFixedHeight(28)

        for w in self.findChildren(QComboBox):
            w.setFixedHeight(28)
            w.setView(QListView())
            w.setStyleSheet("""
                QComboBox {
                    padding-left: 4px;
                    padding-right: 4px;
                }
                QComboBox QAbstractItemView {
                    padding: 2px;
                    border: 1px solid #3a506b;
                }
                QComboBox QAbstractItemView::item {
                    padding-left: 4px;
                    padding-right: 4px;
                    min-height: 22px;
                    border: none;
                }
                QComboBox::drop-down {
                    width: 20px;
                    padding-right: 2px;
                }
            """)

        for w in self.findChildren(QGroupBox):
            w.setStyleSheet("""
                QGroupBox {
                    margin-top: 8px;
                    padding-top: 4px;
                    padding-left: 8px;
                    padding-right: 8px;
                    padding-bottom: 8px;
                }
            """)

    def _set_language(self, lang_code):
        if lang_code == CURRENT_LANG:
            return
        load_language(lang_code)
        self._rebuild_ui()
        self._save_config()

    def _make_group_box(self, title=""):
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3a506b;
                border-radius: 6px;
                margin-top: 0px;
                padding-top: 12px;
                padding-left: 12px;
                padding-right: 12px;
                padding-bottom: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
        """)
        return group

    def _make_card_title(self, text):
        """Crée un titre de carte à l'extérieur du cadre (comme JOURNAL)."""
        lbl = QLabel(text)
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        lbl.setFont(font)
        return lbl

    def _build_file_card(self, parent_layout):
        parent_layout.addWidget(self._make_card_title(M("ui_card_projet")))
        group = self._make_group_box()
        layout = QFormLayout(group)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.chk_nouveau = QCheckBox(M("ui_nouveau_fichier"))
        self.chk_nouveau.setChecked(self.v_nouveau_projet)
        self.chk_nouveau.stateChanged.connect(self._toggle_nouveau_projet)
        layout.addRow(self.chk_nouveau)

        self.entry_nouveau_nom = QLineEdit(self.v_nouveau_nom)
        layout.addRow(QLabel(""), self.entry_nouveau_nom)

        self.lbl_fto = QLabel(M("ui_fichier_existant"))
        layout.addRow(self.lbl_fto)

        hbox = QHBoxLayout()
        self.entry_fto = QLineEdit(self.v_fto)
        self.entry_fto.setReadOnly(True)
        hbox.addWidget(self.entry_fto, 1)

        self.btn_browse = QPushButton(M("ui_parcourir"))
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.clicked.connect(self._browse_fto)
        hbox.addWidget(self.btn_browse)
        layout.addRow(hbox)

        self.entry_host = QLineEdit(self.v_host)
        layout.addRow(M("ui_url_api"), self.entry_host)

        self.btn_start_api = QPushButton(M("start_api"))
        self.btn_start_api.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start_api.clicked.connect(self._toggle_api_server)
        layout.addRow(self.btn_start_api)

        parent_layout.addWidget(group)

    def _build_geo_card(self, parent_layout):
        parent_layout.addWidget(self._make_card_title(M("ui_card_geo")))
        group = self._make_group_box()
        layout = QFormLayout(group)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.spin_n = QSpinBox()
        self.spin_n.setRange(2, 25)
        self.spin_n.setValue(self.v_n)
        layout.addRow(M("ui_nb_portiques"), self.spin_n)

        self.spin_e = QDoubleSpinBox()
        self.spin_e.setRange(0.1, 999.9)
        self.spin_e.setDecimals(2)
        self.spin_e.setValue(self.v_e)
        self.spin_e.setSuffix(" m")
        layout.addRow(M("ui_entraxe"), self.spin_e)

        self.spin_Hg = QDoubleSpinBox()
        self.spin_Hg.setRange(0.1, 999.9)
        self.spin_Hg.setDecimals(2)
        self.spin_Hg.setValue(self.v_Hg)
        self.spin_Hg.setSuffix(" m")
        layout.addRow(M("ui_hg"), self.spin_Hg)

        self.spin_Hd = QDoubleSpinBox()
        self.spin_Hd.setRange(0.1, 999.9)
        self.spin_Hd.setDecimals(2)
        self.spin_Hd.setValue(self.v_Hd)
        self.spin_Hd.setSuffix(" m")
        layout.addRow(M("ui_hd"), self.spin_Hd)

        self.spin_L = QDoubleSpinBox()
        self.spin_L.setRange(0.1, 999.9)
        self.spin_L.setDecimals(2)
        self.spin_L.setValue(self.v_L)
        self.spin_L.setSuffix(" m")
        layout.addRow(M("ui_portee"), self.spin_L)

        self.spin_AR = QDoubleSpinBox()
        self.spin_AR.setRange(0.01, 999.9)
        self.spin_AR.setDecimals(2)
        self.spin_AR.setValue(self.v_AR)
        self.spin_AR.setSuffix(" m")
        layout.addRow(M("ui_ar"), self.spin_AR)

        self.spin_F = QDoubleSpinBox()
        self.spin_F.setRange(0.01, 999.9)
        self.spin_F.setDecimals(2)
        self.spin_F.setValue(self.v_F)
        self.spin_F.setSuffix(" m")
        layout.addRow(M("ui_fleche"), self.spin_F)

        self.combo_appui = QComboBox()
        for val in APPUIS_VALIDES:
            self.combo_appui.addItem(DISPLAY_VALUES.get(val, val), val)
        self.combo_appui.setCurrentIndex(0 if self.v_appui == "HINGED" else 1)
        layout.addRow(M("ui_type_appui"), self.combo_appui)

        self.chk_parois = QCheckBox(M("ui_creer_parois"))
        self.chk_parois.setChecked(self.v_creer_parois)
        layout.addRow(self.chk_parois)

        parent_layout.addWidget(group)

    def _build_sections_card(self, parent_layout):
        parent_layout.addWidget(self._make_card_title(M("ui_card_sections")))
        group = self._make_group_box()
        layout = QFormLayout(group)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        hbox_p = QHBoxLayout()
        self.combo_Sp_fam = QComboBox()
        self.combo_Sp_fam.addItems(FAMILLES)
        self.combo_Sp_fam.setCurrentText(self.v_Sp_fam)
        self.combo_Sp_fam.currentTextChanged.connect(self._update_Sp_profiles)
        hbox_p.addWidget(self.combo_Sp_fam)

        self.combo_Sp = QComboBox()
        self.combo_Sp.setMinimumWidth(120)
        hbox_p.addWidget(self.combo_Sp, 1)
        hbox_p.addStretch()
        layout.addRow(M("ui_sec_poteaux"), hbox_p)

        hbox_a = QHBoxLayout()
        self.combo_Sa_fam = QComboBox()
        self.combo_Sa_fam.addItems(FAMILLES)
        self.combo_Sa_fam.setCurrentText(self.v_Sa_fam)
        self.combo_Sa_fam.currentTextChanged.connect(self._update_Sa_profiles)
        hbox_a.addWidget(self.combo_Sa_fam)

        self.combo_Sa = QComboBox()
        self.combo_Sa.setMinimumWidth(120)
        hbox_a.addWidget(self.combo_Sa, 1)
        hbox_a.addStretch()
        layout.addRow(M("ui_sec_arbaletriers"), hbox_a)

        hbox_n = QHBoxLayout()
        self.combo_Sn_fam = QComboBox()
        self.combo_Sn_fam.addItems(FAMILLES)
        self.combo_Sn_fam.setCurrentText(self.v_Sn_fam)
        self.combo_Sn_fam.currentTextChanged.connect(self._update_Sn_profiles)
        hbox_n.addWidget(self.combo_Sn_fam)

        self.combo_Sn = QComboBox()
        self.combo_Sn.setMinimumWidth(120)
        hbox_n.addWidget(self.combo_Sn, 1)
        hbox_n.addStretch()
        layout.addRow(M("ui_sec_pannes"), hbox_n)

        self.combo_M = QComboBox()
        self.combo_M.addItems(MATERIAUX_VALIDES)
        self.combo_M.setCurrentText(self.v_M)
        layout.addRow(M("ui_materiau"), self.combo_M)

        self._update_Sp_profiles(self.v_Sp_fam)
        self._update_Sa_profiles(self.v_Sa_fam)
        self._update_Sn_profiles(self.v_Sn_fam)

        parent_layout.addWidget(group)

    def _update_Sp_profiles(self, fam):
        self.combo_Sp.clear()
        self.combo_Sp.addItems(SECTIONS_PAR_FAMILLE.get(fam, []))
        if self.v_Sp in SECTIONS_PAR_FAMILLE.get(fam, []):
            self.combo_Sp.setCurrentText(self.v_Sp)

    def _update_Sa_profiles(self, fam):
        self.combo_Sa.clear()
        self.combo_Sa.addItems(SECTIONS_PAR_FAMILLE.get(fam, []))
        if self.v_Sa in SECTIONS_PAR_FAMILLE.get(fam, []):
            self.combo_Sa.setCurrentText(self.v_Sa)

    def _update_Sn_profiles(self, fam):
        self.combo_Sn.clear()
        self.combo_Sn.addItems(SECTIONS_PAR_FAMILLE.get(fam, []))
        if self.v_Sn in SECTIONS_PAR_FAMILLE.get(fam, []):
            self.combo_Sn.setCurrentText(self.v_Sn)

    def _build_pannes_card(self, parent_layout):
        parent_layout.addWidget(self._make_card_title(M("ui_card_pannes")))
        group = self._make_group_box()
        layout = QFormLayout(group)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.spin_Npg = QSpinBox()
        self.spin_Npg.setRange(2, 99)
        self.spin_Npg.setValue(self.v_Npg)
        layout.addRow(M("ui_npg"), self.spin_Npg)

        self.spin_Npd = QSpinBox()
        self.spin_Npd.setRange(2, 99)
        self.spin_Npd.setValue(self.v_Npd)
        layout.addRow(M("ui_npd"), self.spin_Npd)

        self.spin_Dbg = QDoubleSpinBox()
        self.spin_Dbg.setRange(0.0, 999.9)
        self.spin_Dbg.setDecimals(2)
        self.spin_Dbg.setValue(self.v_Dbg)
        self.spin_Dbg.setSuffix(" m")
        layout.addRow(M("ui_dbg"), self.spin_Dbg)

        self.spin_Dbd = QDoubleSpinBox()
        self.spin_Dbd.setRange(0.0, 999.9)
        self.spin_Dbd.setDecimals(2)
        self.spin_Dbd.setValue(self.v_Dbd)
        self.spin_Dbd.setSuffix(" m")
        layout.addRow(M("ui_dbd"), self.spin_Dbd)

        parent_layout.addWidget(group)

    def _browse_fto(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            M("ui_browse_titre"),
            "",
            f"{M('ui_browse_filtre_ad')} (*.fto);;{M('ui_browse_filtre_tous')} (*.*)"
        )
        if path:
            self.v_fto = os.path.normpath(path)
            self.entry_fto.setText(self.v_fto)

    def _rebuild_ui(self):
        self._sync_vars_from_ui()
        self._clear_menu_bar()
        central = self.centralWidget()
        if central is not None:
            central.deleteLater()
        self.setCentralWidget(None)
        self._build_ui()
        self._apply_custom_styles()
        self._toggle_nouveau_projet()

    def _sync_vars_from_ui(self):
        self.v_lang = CURRENT_LANG
        self.v_fto = self.entry_fto.text() if hasattr(self, 'entry_fto') else self.v_fto
        self.v_host = self.entry_host.text() if hasattr(self, 'entry_host') else self.v_host
        self.v_n = self.spin_n.value() if hasattr(self, 'spin_n') else self.v_n
        self.v_e = self.spin_e.value() if hasattr(self, 'spin_e') else self.v_e
        self.v_Hg = self.spin_Hg.value() if hasattr(self, 'spin_Hg') else self.v_Hg
        self.v_Hd = self.spin_Hd.value() if hasattr(self, 'spin_Hd') else self.v_Hd
        self.v_L = self.spin_L.value() if hasattr(self, 'spin_L') else self.v_L
        self.v_AR = self.spin_AR.value() if hasattr(self, 'spin_AR') else self.v_AR
        self.v_F = self.spin_F.value() if hasattr(self, 'spin_F') else self.v_F
        self.v_Sp = self.combo_Sp.currentText() if hasattr(self, 'combo_Sp') else self.v_Sp
        self.v_Sa = self.combo_Sa.currentText() if hasattr(self, 'combo_Sa') else self.v_Sa
        self.v_Sn = self.combo_Sn.currentText() if hasattr(self, 'combo_Sn') else self.v_Sn
        self.v_Sp_fam = self.combo_Sp_fam.currentText() if hasattr(self, 'combo_Sp_fam') else self.v_Sp_fam
        self.v_Sa_fam = self.combo_Sa_fam.currentText() if hasattr(self, 'combo_Sa_fam') else self.v_Sa_fam
        self.v_Sn_fam = self.combo_Sn_fam.currentText() if hasattr(self, 'combo_Sn_fam') else self.v_Sn_fam
        self.v_M = self.combo_M.currentText() if hasattr(self, 'combo_M') else self.v_M
        self.v_appui = self.combo_appui.currentData() if hasattr(self, 'combo_appui') else self.v_appui
        self.v_Npg = self.spin_Npg.value() if hasattr(self, 'spin_Npg') else self.v_Npg
        self.v_Npd = self.spin_Npd.value() if hasattr(self, 'spin_Npd') else self.v_Npd
        self.v_Dbg = self.spin_Dbg.value() if hasattr(self, 'spin_Dbg') else self.v_Dbg
        self.v_Dbd = self.spin_Dbd.value() if hasattr(self, 'spin_Dbd') else self.v_Dbd
        self.v_nouveau_projet = self.chk_nouveau.isChecked() if hasattr(self, 'chk_nouveau') else self.v_nouveau_projet
        self.v_nouveau_nom = self.entry_nouveau_nom.text() if hasattr(self, 'entry_nouveau_nom') else self.v_nouveau_nom
        self.v_creer_parois = self.chk_parois.isChecked() if hasattr(self, 'chk_parois') else self.v_creer_parois

    def _toggle_nouveau_projet(self):
        nouveau = self.chk_nouveau.isChecked()
        self.entry_nouveau_nom.setEnabled(nouveau)
        self.entry_fto.setEnabled(not nouveau)
        self.btn_browse.setEnabled(not nouveau)
        self.lbl_fto.setEnabled(not nouveau)

    def _clear_log(self):
        self.log_text.clear()

    def _log(self, msg, tag="info"):
        color_map = {
            "ok": "#2CB67D",
            "warn": "#E8A840",
            "error": "#E05555",
            "info": "#8899BB",
            "head": "#4A7FE0",
        }
        color = color_map.get(tag, "#E8EBF0")
        html = f'<span style="color:{color}">{msg.replace(chr(10), "<br>")}</span>'
        self.log_text.append(html)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _set_status(self, msg):
        self.status_bar.showMessage(msg)

    def _collect_params(self):
        return {
            "fto": self.v_fto,
            "n": self.v_n,
            "e": self.v_e,
            "Hg": self.v_Hg,
            "Hd": self.v_Hd,
            "L": self.v_L,
            "AR": self.v_AR,
            "F": self.v_F,
            "Sp": self.v_Sp,
            "Sa": self.v_Sa,
            "Sn": self.v_Sn,
            "M": self.v_M,
            "TypeAppui": self.v_appui,
            "Npg": self.v_Npg,
            "Npd": self.v_Npd,
            "Dbg": self.v_Dbg,
            "Dbd": self.v_Dbd,
            "creer_parois": self.v_creer_parois,
        }

    def _update_api_button_state(self):
        running = bool(self.api_server_process and self.api_server_process.poll() is None)
        if self.btn_start_api is None:
            return
        if running:
            self.btn_start_api.setText(M("stop_api"))
            self.btn_start_api.setStyleSheet("background: #E05555; color: white; border: 1px solid #E05555;")
        else:
            self.btn_start_api.setText(M("start_api"))
            self.btn_start_api.setStyleSheet("")
            self.api_server_process = None
            self.api_server_started_by_viewer = False
        self.btn_start_api.style().unpolish(self.btn_start_api)
        self.btn_start_api.style().polish(self.btn_start_api)
        self.btn_start_api.update()

    def _start_api_server(self):
        exe_path = os.path.normpath(self.api_server_exe)

        if not exe_path or not os.path.isfile(exe_path):
            self._log(M("err_api_server_exe_not_found", path=exe_path), "error")
            QMessageBox.warning(self, M("menu_configuration"), M("err_api_server_exe_not_found", path=exe_path))
            return

        try:
            self._log(M("log_api_server_starting", path=exe_path), "info")
            self.api_server_process = subprocess.Popen([exe_path, "/console"], cwd=os.path.dirname(exe_path) or None)
            self.api_server_started_by_viewer = True
            self._update_api_button_state()
            self._log(M("log_api_server_started"), "ok")
        except Exception as e:
            details = str(e).strip() or e.__class__.__name__
            self._log(M("err_api_server_start_failed", details=details), "error")
            QMessageBox.critical(self, M("menu_configuration"), M("err_api_server_start_failed", details=details))

    def _stop_api_server(self, log_on_success: bool = True):
        try:
            if self.api_server_process and self.api_server_process.poll() is None:
                self.api_server_process.terminate()
                try:
                    self.api_server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.api_server_process.kill()
                if log_on_success:
                    self._log(M("log_api_server_stopped"), "ok")
        finally:
            self.api_server_process = None
            self.api_server_started_by_viewer = False
            self._update_api_button_state()

    def _toggle_api_server(self):
        running = bool(self.api_server_process and self.api_server_process.poll() is None)
        if running:
            self._stop_api_server(log_on_success=True)
        else:
            self._start_api_server()

    def _on_run(self):
        if self._running:
            return

        self._sync_vars_from_ui()

        params = self._collect_params()
        nouveau_projet = self.v_nouveau_projet
        params["nouveau_projet"] = nouveau_projet

        if nouveau_projet:
            nom = self.v_nouveau_nom.strip()
            if not nom:
                QMessageBox.critical(self, M("dlg_titre_nom"), M("dlg_msg_nom"))
                return
            if not nom.lower().endswith(".fto"):
                nom += ".fto"
            params["fto"] = os.path.join(os.getcwd(), nom)
            if os.path.exists(params["fto"]):
                QMessageBox.critical(self, M("dlg_titre_existe"), M("dlg_msg_existe", path=params["fto"]))
                return
        else:
            if not params["fto"]:
                QMessageBox.critical(self, M("dlg_titre_manquant"), M("dlg_msg_manquant"))
                return
            if not os.path.isfile(params["fto"]):
                QMessageBox.critical(self, M("dlg_titre_introuvable"), M("dlg_msg_introuvable", path=params["fto"]))
                return

        try:
            validate(params)
        except ValueError as ex:
            QMessageBox.critical(self, M("dlg_titre_params"), str(ex))
            return

        self._running = True
        self.btn_run.setEnabled(False)
        self.btn_run.setText(M("ui_btn_en_cours"))
        self._set_status(M("status_en_cours"))
        self._clear_log()

        thread = threading.Thread(target=self._run_thread, args=(params,), daemon=True)
        thread.start()

    def _run_thread(self, params):
        host = self.v_host.strip().rstrip("/")

        def log(msg, tag="info"):
            self.log_signals.log_message.emit(msg, tag)

        def status(msg):
            self.log_signals.status_message.emit(msg)

        try:
            log("=" * 48, "head")
            log(M("log_fichier", path=params["fto"]), "head")
            log(M("log_api", host=host), "head")
            log("=" * 48, "head")

            log(M("log_verif_port"))
            check_port(host)
            log(M("log_api_ok"), "ok")

            if params.get("nouveau_projet"):
                log(M("log_nouveau_projet", path=params["fto"]))
                new_project(host, params["fto"])
                log(M("log_nouveau_projet_ok"), "ok")
                status(M("status_nouveau_ok"))
            else:
                log(M("log_ouverture"))
                open_project(host, params["fto"])
                log(M("log_ouverture_ok"), "ok")
                status(M("status_ouvert_ok"))

            def log_cb(msg):
                tag = "ok" if "OK" in msg else "info"
                log(msg, tag)

            counts, total, Lg, Ld, H_faitage = build_structure(host, params, log_cb)

            log(M("log_fermeture"))
            close_project(host)
            log(M("log_fermeture_ok"), "ok")

            log("=" * 48, "head")
            log(M("syn_succes"), "ok")
            log("=" * 48, "head")

            def _s(label, value):
                return f" {label:<22}: {value}"

            log(_s(M("syn_portiques"), params["n"]), "info")
            log(_s(M("syn_entraxe"), M("syn_unite_m", val=params["e"])), "info")
            log(_s(M("syn_hg_hd"), M("syn_unite_m_m", vg=params["Hg"], vd=params["Hd"])), "info")
            log(_s(M("syn_portee"), M("syn_unite_m", val=params["L"])), "info")
            log(_s(M("syn_ar"), M("syn_unite_m", val=params["AR"])), "info")
            log(_s(M("syn_fleche"), M("syn_unite_m", val=params["F"])), "info")
            log(_s(M("syn_h_faitage"), M("syn_unite_m", val=f"{H_faitage:.3f}")), "info")
            log(_s(M("syn_lg"), M("syn_unite_m", val=f"{Lg:.3f}")), "info")
            log(_s(M("syn_ld"), M("syn_unite_m", val=f"{Ld:.3f}")), "info")
            log(_s(M("syn_appui"), DISPLAY_VALUES.get(params["TypeAppui"], params["TypeAppui"])), "info")
            log(_s(M("syn_poteaux", Sp=params["Sp"]), counts["poteaux"]), "info")
            log(_s(M("syn_arbaletriers", Sa=params["Sa"]), counts["arbaletriers"]), "info")
            log(_s(M("syn_pannes_g", Sn=params["Sn"]), counts["pannes_g"]), "info")
            log(_s(M("syn_pannes_d", Sn=params["Sn"]), counts["pannes_d"]), "info")
            log(_s(M("syn_appuis"), counts["appuis"]), "info")
            if params["creer_parois"]:
                log(_s(M("syn_parois"), counts["parois"]), "info")
            log(_s(M("syn_total"), total), "ok")
            log("=" * 48, "head")

            status(M("status_termine", n=total))
            self.log_signals.finished.emit()

        except (ConnectionError, RuntimeError, ValueError, Exception) as ex:
            log(M("log_erreur", ex=ex), "error")
            close_project(host)
            status(M("status_erreur"))
            self.log_signals.error.emit(str(ex))
            self.log_signals.finished.emit()

    def _on_log_message(self, msg, tag):
        self._log(msg, tag)

    def _on_status_message(self, msg):
        self._set_status(msg)

    def _on_finished(self):
        self._running = False
        self.btn_run.setEnabled(True)
        self.btn_run.setText(M("ui_btn_creer"))

    def _on_error(self, msg):
        QMessageBox.critical(self, M("dlg_titre_erreur"), msg)

    def closeEvent(self, event):
        try:
            if self.api_server_started_by_viewer and self.api_server_process and self.api_server_process.poll() is None:
                self.api_server_process.terminate()
                try:
                    self.api_server_process.wait(timeout=5)
                except Exception:
                    self.api_server_process.kill()
                self._log(M("log_api_server_stopped_on_exit"), "info")
        except (AttributeError, OSError):
            pass
        self._save_config()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme=CURRENT_THEME_FILE, invert_secondary=CURRENT_THEME_FILE.startswith("light_"))

    window = PortiquesApp(app)
    window._apply_custom_styles()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
