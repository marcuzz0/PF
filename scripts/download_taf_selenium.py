#!/usr/bin/env python3
"""
Script per scaricare i file TAF usando Selenium (per siti con JavaScript).

Questo script usa Selenium per automatizzare il download dai siti che
richiedono interazione JavaScript o hanno protezioni anti-bot.

Requisiti:
    pip install selenium webdriver-manager

Uso:
    python download_taf_selenium.py --province RM MI FI
    python download_taf_selenium.py --all --headless
"""

import argparse
import os
import sys
import time
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("Installa le dipendenze: pip install selenium webdriver-manager")
    sys.exit(1)


PROVINCE = {
    "AG": "Agrigento", "AL": "Alessandria", "AN": "Ancona", "AO": "Aosta",
    "AR": "Arezzo", "AP": "Ascoli Piceno", "AT": "Asti", "AV": "Avellino",
    "BA": "Bari", "BT": "Barletta-Andria-Trani", "BL": "Belluno", "BN": "Benevento",
    "BG": "Bergamo", "BI": "Biella", "BO": "Bologna", "BZ": "Bolzano",
    "BS": "Brescia", "BR": "Brindisi", "CA": "Cagliari", "CL": "Caltanissetta",
    "CB": "Campobasso", "CE": "Caserta", "CT": "Catania", "CZ": "Catanzaro",
    "CH": "Chieti", "CO": "Como", "CS": "Cosenza", "CR": "Cremona",
    "KR": "Crotone", "CN": "Cuneo", "EN": "Enna", "FM": "Fermo",
    "FE": "Ferrara", "FI": "Firenze", "FG": "Foggia", "FC": "Forli-Cesena",
    "FR": "Frosinone", "GE": "Genova", "GO": "Gorizia", "GR": "Grosseto",
    "IM": "Imperia", "IS": "Isernia", "SP": "La Spezia", "AQ": "L'Aquila",
    "LT": "Latina", "LE": "Lecce", "LC": "Lecco", "LI": "Livorno",
    "LO": "Lodi", "LU": "Lucca", "MC": "Macerata", "MN": "Mantova",
    "MS": "Massa-Carrara", "MT": "Matera", "ME": "Messina", "MI": "Milano",
    "MO": "Modena", "MB": "Monza e Brianza", "NA": "Napoli", "NO": "Novara",
    "NU": "Nuoro", "OR": "Oristano", "PD": "Padova", "PA": "Palermo",
    "PR": "Parma", "PV": "Pavia", "PG": "Perugia", "PU": "Pesaro e Urbino",
    "PE": "Pescara", "PC": "Piacenza", "PI": "Pisa", "PT": "Pistoia",
    "PN": "Pordenone", "PZ": "Potenza", "PO": "Prato", "RG": "Ragusa",
    "RA": "Ravenna", "RC": "Reggio Calabria", "RE": "Reggio Emilia",
    "RI": "Rieti", "RN": "Rimini", "RM": "Roma", "RO": "Rovigo",
    "SA": "Salerno", "SS": "Sassari", "SV": "Savona", "SI": "Siena",
    "SR": "Siracusa", "SO": "Sondrio", "SU": "Sud Sardegna", "TA": "Taranto",
    "TE": "Teramo", "TR": "Terni", "TO": "Torino", "TP": "Trapani",
    "TN": "Trento", "TV": "Treviso", "TS": "Trieste", "UD": "Udine",
    "VA": "Varese", "VE": "Venezia", "VB": "Verbano-Cusio-Ossola",
    "VC": "Vercelli", "VR": "Verona", "VV": "Vibo Valentia",
    "VI": "Vicenza", "VT": "Viterbo",
}


def setup_driver(headless: bool = True, download_dir: str = None) -> webdriver.Chrome:
    """Configura il WebDriver Chrome."""
    options = Options()

    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    # Configura download automatico
    if download_dir:
        prefs = {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def download_from_visualtaf(driver: webdriver.Chrome, sigla: str, output_dir: Path) -> bool:
    """
    Scarica TAF da VisualTAF.it usando Selenium.

    Nota: VisualTAF potrebbe non offrire download diretto dei TAF.
    """
    try:
        url = f"https://visualtaf.it/?provincia={sigla}"
        driver.get(url)
        time.sleep(3)

        # Cerca link/pulsante download
        try:
            download_btn = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '.TAF') or contains(@href, 'download')]"))
            )
            download_btn.click()
            time.sleep(5)
            print(f"  [OK] {sigla} da VisualTAF")
            return True
        except Exception:
            print(f"  [SKIP] VisualTAF non offre download diretto per {sigla}")
            return False

    except Exception as e:
        print(f"  [ERRORE] VisualTAF: {e}")
        return False


def download_from_altervista(driver: webdriver.Chrome, sigla: str, output_dir: Path) -> bool:
    """Scarica TAF da fiduciali.altervista.org usando Selenium."""
    try:
        url = "http://fiduciali.altervista.org/download_taf.php"
        driver.get(url)
        time.sleep(2)

        # Seleziona provincia
        try:
            select_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "provincia"))
            )
            select = Select(select_element)
            select.select_by_value(sigla)

            # Clicca download
            submit_btn = driver.find_element(By.XPATH, "//input[@type='submit']")
            submit_btn.click()
            time.sleep(5)

            print(f"  [OK] {sigla} da Altervista")
            return True
        except Exception as e:
            print(f"  [SKIP] Altervista: {e}")
            return False

    except Exception as e:
        print(f"  [ERRORE] Altervista: {e}")
        return False


def download_taf(driver: webdriver.Chrome, sigla: str, output_dir: Path, force: bool = False) -> bool:
    """Scarica il file TAF per una provincia."""
    output_file = output_dir / f"{sigla}.TAF"

    if output_file.exists() and not force:
        print(f"  [SKIP] {sigla}.TAF esiste già")
        return True

    # Prova le varie fonti
    sources = [
        ("Altervista", download_from_altervista),
        ("VisualTAF", download_from_visualtaf),
    ]

    for source_name, download_func in sources:
        print(f"  Provo {source_name}...", end=" ", flush=True)
        if download_func(driver, sigla, output_dir):
            return True

    print(f"  [FALLITO] {sigla}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Scarica file TAF con Selenium")
    parser.add_argument(
        "--province", "-p",
        nargs="+",
        help="Sigle province da scaricare"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Scarica tutte le province"
    )
    parser.add_argument(
        "--output", "-o",
        default="data/taf",
        help="Directory output"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Riscarica anche file esistenti"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Esegui in modalità headless (default: True)"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Mostra browser durante il download"
    )

    args = parser.parse_args()

    if not args.province and not args.all:
        parser.error("Specifica --province o --all")

    output_dir = Path(args.output).absolute()
    output_dir.mkdir(parents=True, exist_ok=True)

    province_list = list(PROVINCE.keys()) if args.all else [p.upper() for p in args.province]

    headless = args.headless and not args.no_headless

    print(f"Download TAF per {len(province_list)} province")
    print(f"Output: {output_dir}")
    print(f"Modalità: {'headless' if headless else 'visibile'}")
    print()

    driver = setup_driver(headless=headless, download_dir=str(output_dir))

    try:
        success = 0
        failed = 0

        for sigla in province_list:
            if sigla not in PROVINCE:
                print(f"[WARN] Provincia sconosciuta: {sigla}")
                continue

            print(f"[{sigla}] {PROVINCE[sigla]}")

            if download_taf(driver, sigla, output_dir, args.force):
                success += 1
            else:
                failed += 1

            time.sleep(2)  # Rate limiting

        print()
        print(f"Completato: {success} scaricati, {failed} falliti")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
