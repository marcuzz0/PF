#!/usr/bin/env python3
"""
Script per scaricare manualmente i file TAF.

Esegui questo script sulla tua macchina locale (non in ambiente sandbox)
per scaricare i file TAF dall'Agenzia delle Entrate o da fonti alternative.

Uso:
    python download_taf_manual.py --province RM MI FI
    python download_taf_manual.py --all
"""

import argparse
import os
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Installa le dipendenze: pip install requests beautifulsoup4")
    sys.exit(1)


# Province italiane con codici ufficio AdE
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


def download_from_altervista(sigla: str, output_dir: Path, session: requests.Session) -> bool:
    """Scarica TAF da fiduciali.altervista.org"""
    url = "http://fiduciali.altervista.org/download_taf.php"

    try:
        # Il sito usa un form POST
        response = session.post(
            url,
            data={"provincia": sigla, "tipo": "taf"},
            timeout=60,
            allow_redirects=True,
        )

        if response.status_code == 200 and len(response.content) > 500:
            content = response.content

            # Verifica se ZIP
            if content[:2] == b"PK":
                with zipfile.ZipFile(BytesIO(content)) as zf:
                    for name in zf.namelist():
                        if name.upper().endswith(".TAF"):
                            output_file = output_dir / f"{sigla}.TAF"
                            with zf.open(name) as f:
                                output_file.write_bytes(f.read())
                            print(f"  [OK] {sigla}.TAF (da ZIP)")
                            return True
            else:
                # File diretto
                output_file = output_dir / f"{sigla}.TAF"
                output_file.write_bytes(content)
                print(f"  [OK] {sigla}.TAF")
                return True

    except Exception as e:
        print(f"  [ERRORE] Altervista: {e}")

    return False


def download_from_laterramisurata(sigla: str, output_dir: Path, session: requests.Session) -> bool:
    """Scarica TAF da laterramisurata.com"""
    # Questo sito richiede registrazione, quindi skippiamo
    return False


def download_taf(sigla: str, output_dir: Path, session: requests.Session, force: bool = False) -> bool:
    """Scarica il file TAF per una provincia."""
    output_file = output_dir / f"{sigla}.TAF"

    if output_file.exists() and not force:
        print(f"  [SKIP] {sigla}.TAF esiste già")
        return True

    # Prova le varie fonti
    sources = [
        ("Altervista", download_from_altervista),
    ]

    for source_name, download_func in sources:
        print(f"  Provo {source_name}...", end=" ", flush=True)
        if download_func(sigla, output_dir, session):
            return True
        print("fallito")

    print(f"  [FALLITO] {sigla}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Scarica file TAF dei Punti Fiduciali")
    parser.add_argument(
        "--province", "-p",
        nargs="+",
        help="Sigle province da scaricare (es. RM MI FI)"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Scarica tutte le province"
    )
    parser.add_argument(
        "--output", "-o",
        default="data/taf",
        help="Directory output (default: data/taf)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Riscarica anche file esistenti"
    )

    args = parser.parse_args()

    if not args.province and not args.all:
        parser.error("Specifica --province o --all")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    province_list = list(PROVINCE.keys()) if args.all else [p.upper() for p in args.province]

    print(f"Download TAF per {len(province_list)} province")
    print(f"Output: {output_dir.absolute()}")
    print()

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    success = 0
    failed = 0

    for sigla in province_list:
        if sigla not in PROVINCE:
            print(f"[WARN] Provincia sconosciuta: {sigla}")
            continue

        print(f"[{sigla}] {PROVINCE[sigla]}")

        if download_taf(sigla, output_dir, session, args.force):
            success += 1
        else:
            failed += 1

        time.sleep(1)  # Rate limiting

    print()
    print(f"Completato: {success} scaricati, {failed} falliti")
    print()
    print("Ora puoi eseguire la pipeline:")
    print(f"  python run_pipeline.py --skip-download")


if __name__ == "__main__":
    main()
