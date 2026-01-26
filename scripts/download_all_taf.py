#!/usr/bin/env python3
"""
Script per scaricare TUTTI i file TAF delle 107 province italiane.

Esegui questo script sulla tua macchina locale:
    python scripts/download_all_taf.py

Dopo il download, pusha i file su GitHub:
    git add data/taf/*.TAF
    git commit -m "chore: Add all TAF files"
    git push
"""

import os
import sys
import time
import zipfile
import subprocess
from io import BytesIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    print("Installa requests: pip install requests")
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


def download_taf(sigla: str, output_dir: Path, session: requests.Session) -> tuple[str, bool, str]:
    """Scarica TAF per una provincia. Ritorna (sigla, success, message)."""
    output_file = output_dir / f"{sigla}.TAF"

    if output_file.exists():
        return (sigla, True, "già esistente")

    # AdE (Agenzia delle Entrate) - fonte ufficiale
    # URL: https://www1.agenziaentrate.gov.it/servizi/TafDis/download.php?&tipofile=TAF&iduff=AG1
    iduff = f"{sigla}1"
    url = f"https://www1.agenziaentrate.gov.it/servizi/TafDis/download.php?&tipofile=TAF&iduff={iduff}"

    # Riprova più volte - il server AdE è instabile
    for attempt in range(5):
        try:
            time.sleep(3)  # Delay tra tentativi
            response = session.get(url, timeout=60)

            if response.status_code == 200 and len(response.content) > 500:
                content = response.content

                # Verifica che sia un TAF valido (inizia con codice foglio)
                if content[:1].isalpha() or content[:1].isdigit():
                    output_file.write_bytes(content)
                    return (sigla, True, f"{output_file.stat().st_size/1024:.1f}KB (AdE)")

                # ZIP file
                if content[:2] == b"PK":
                    with zipfile.ZipFile(BytesIO(content)) as zf:
                        for name in zf.namelist():
                            if name.upper().endswith(".TAF"):
                                with zf.open(name) as f:
                                    output_file.write_bytes(f.read())
                                return (sigla, True, f"{output_file.stat().st_size/1024:.1f}KB (AdE)")

        except Exception:
            time.sleep(3)  # Pausa extra in caso di errore
            continue

    # Fallback: Altervista
    url = "http://fiduciali.altervista.org/download_taf.php"
    try:
        response = session.post(
            url,
            data={"provincia": sigla, "tipo": "taf"},
            timeout=60,
        )

        if response.status_code == 200 and len(response.content) > 500:
            content = response.content

            if content[:2] == b"PK":
                with zipfile.ZipFile(BytesIO(content)) as zf:
                    for name in zf.namelist():
                        if name.upper().endswith(".TAF"):
                            with zf.open(name) as f:
                                output_file.write_bytes(f.read())
                            return (sigla, True, f"{output_file.stat().st_size/1024:.1f}KB")
            else:
                output_file.write_bytes(content)
                return (sigla, True, f"{output_file.stat().st_size/1024:.1f}KB")

    except Exception as e:
        pass

    return (sigla, False, "nessuna fonte disponibile")


def main():
    output_dir = Path(__file__).parent.parent / "data" / "taf"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("DOWNLOAD TAF - Punti Fiduciali Italia")
    print("=" * 60)
    print(f"Province: {len(PROVINCE)}")
    print(f"Output: {output_dir.absolute()}")
    print()

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        "Referer": "http://fiduciali.altervista.org/",
    })

    success = 0
    failed = []

    # Download sequenziale con progress
    for i, (sigla, nome) in enumerate(PROVINCE.items(), 1):
        print(f"[{i:3d}/107] {sigla} ({nome})... ", end="", flush=True)

        sig, ok, msg = download_taf(sigla, output_dir, session)

        if ok:
            print(f"OK ({msg})")
            success += 1
        else:
            print(f"FALLITO ({msg})")
            failed.append(sigla)

        time.sleep(2)  # Rate limiting - il server AdE richiede pause più lunghe

    print()
    print("=" * 60)
    print(f"COMPLETATO: {success}/107 scaricati")

    if failed:
        print(f"FALLITI: {', '.join(failed)}")

    # Calcola dimensione totale
    total_size = sum(f.stat().st_size for f in output_dir.glob("*.TAF"))
    print(f"Dimensione totale: {total_size/1024/1024:.1f} MB")
    print()

    # Suggerisci push
    print("Per caricare su GitHub:")
    print("  git add data/taf/*.TAF")
    print('  git commit -m "chore: Add TAF files for all provinces"')
    print("  git push")


if __name__ == "__main__":
    main()
