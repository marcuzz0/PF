#!/usr/bin/env python3
"""
Script per scaricare TUTTI i file DIS (Distanze Misurate) delle province italiane.
"""

import os
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path

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

# Codici ufficio AdE alternativi
CODICI_UFFICIO_ADE = {
    "AR": ["AR1"],
    "FC": ["FO1"],
    "PU": ["PS1"],
    "BZ": ["BZ1"],
    "TN": ["TN1"],
}

# Province nuove i cui dati sono nelle province madri
PROVINCE_NUOVE = {
    "BT": "BA",
    "FM": "AP",
    "MB": "MI",
    "SU": "CA",
}


def download_dis(sigla: str, output_dir: Path, session: requests.Session) -> tuple[str, bool, str]:
    """Scarica DIS per una provincia."""
    output_file = output_dir / f"{sigla}.DIS"

    if output_file.exists():
        return (sigla, True, "già esistente")

    if sigla in PROVINCE_NUOVE:
        madre = PROVINCE_NUOVE[sigla]
        return (sigla, False, f"dati in {madre}")

    # AdE - tipofile=DIST (non DIS!)
    codici = CODICI_UFFICIO_ADE.get(sigla, [f"{sigla}1"])

    for iduff in codici:
        url = f"http://www1.agenziaentrate.gov.it/servizi/TafDis/download.php?&tipofile=DIST&iduff={iduff}"

        for attempt in range(5):
            try:
                time.sleep(1)
                response = session.get(url, timeout=60)

                if response.status_code == 200 and len(response.content) > 100:
                    content = response.content

                    # ZIP file
                    if content[:2] == b"PK":
                        with zipfile.ZipFile(BytesIO(content)) as zf:
                            for name in zf.namelist():
                                with zf.open(name) as f:
                                    output_file.write_bytes(f.read())
                                return (sigla, True, f"{output_file.stat().st_size/1024:.1f}KB (AdE {iduff})")

                    # File di testo (non HTML)
                    if not content.startswith(b'<!') and not content.startswith(b'<html') and not content.startswith(b'<HTML'):
                        output_file.write_bytes(content)
                        return (sigla, True, f"{output_file.stat().st_size/1024:.1f}KB (AdE {iduff})")

            except Exception as e:
                continue

    return (sigla, False, "nessuna fonte disponibile")


def main():
    output_dir = Path(__file__).parent.parent / "data" / "dis"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("DOWNLOAD DIS - Distanze Misurate Italia")
    print("=" * 60)

    esistenti = {f.stem.upper() for f in output_dir.glob("*.DIS")}
    tutte = set(PROVINCE.keys())
    mancanti = sorted(tutte - esistenti)

    print(f"Province totali: {len(PROVINCE)}")
    print(f"Già scaricate:   {len(esistenti)}")
    print(f"Da scaricare:    {len(mancanti)}")
    print(f"Output: {output_dir.absolute()}")
    print()

    if not mancanti:
        print("Tutti i file DIS sono già scaricati!")
        total_size = sum(f.stat().st_size for f in output_dir.glob("*.DIS"))
        print(f"Dimensione totale: {total_size/1024/1024:.1f} MB")
        return

    print(f"Province mancanti: {', '.join(mancanti)}")
    print()

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    })

    success = 0
    failed = []

    for i, sigla in enumerate(mancanti, 1):
        nome = PROVINCE.get(sigla, sigla)
        print(f"[{i:3d}/{len(mancanti)}] {sigla} ({nome})... ", end="", flush=True)

        sig, ok, msg = download_dis(sigla, output_dir, session)

        if ok:
            print(f"OK ({msg})")
            success += 1
        else:
            print(f"FALLITO ({msg})")
            failed.append(sigla)

        time.sleep(1)

    print()
    print("=" * 60)
    print(f"SCARICATI: {success}/{len(mancanti)}")

    if failed:
        print(f"FALLITI: {', '.join(failed)}")

    totale_scaricati = len(list(output_dir.glob("*.DIS")))
    total_size = sum(f.stat().st_size for f in output_dir.glob("*.DIS"))
    print(f"TOTALE PROVINCE: {totale_scaricati}/103")
    print(f"Dimensione totale: {total_size/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
