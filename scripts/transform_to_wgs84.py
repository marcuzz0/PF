#!/usr/bin/env python3
"""
Trasforma tutti i file TAF in coordinate WGS84.

Output:
- data/wgs84/punti_fiduciali.csv - CSV con tutti i punti
- data/wgs84/punti_fiduciali.geojson - GeoJSON per GIS
- data/wgs84/per_provincia/*.csv - CSV separati per provincia
"""

import csv
import json
import re
import sys
import zipfile
from io import BytesIO
from pathlib import Path

try:
    from pyproj import CRS, Transformer
except ImportError:
    print("Installa pyproj: pip install pyproj")
    sys.exit(1)


# Transformer Gauss-Boaga → WGS84
CRS_WGS84 = CRS.from_epsg(4326)
CRS_GB_OVEST = CRS.from_epsg(3003)
CRS_GB_EST = CRS.from_epsg(3004)

transformer_ovest = Transformer.from_crs(CRS_GB_OVEST, CRS_WGS84, always_xy=True)
transformer_est = Transformer.from_crs(CRS_GB_EST, CRS_WGS84, always_xy=True)

# Origini catastali per Cassini-Soldner: (Nord GB, Est GB, Fuso)
ORIGINI = {
    # Piemonte/Valle d'Aosta
    "TO": (4994000, 1402000, 1), "AT": (4994000, 1402000, 1), "CN": (4994000, 1402000, 1),
    "BI": (4994000, 1402000, 1), "VC": (4994000, 1402000, 1), "NO": (4994000, 1402000, 1),
    "VB": (4994000, 1402000, 1), "AO": (5068000, 1368000, 1), "AL": (4960000, 1470000, 1),
    # Lombardia
    "MI": (5032000, 1514000, 1), "CO": (5032000, 1514000, 1), "VA": (5032000, 1514000, 1),
    "LC": (5032000, 1514000, 1), "MB": (5032000, 1514000, 1), "LO": (5032000, 1514000, 1),
    "PV": (5032000, 1514000, 1), "SO": (5032000, 1514000, 1),
    "BG": (5042000, 1596000, 1), "BS": (5042000, 1596000, 1), "CR": (5042000, 1596000, 1),
    "MN": (4996000, 1632000, 1),
    # Veneto/Friuli
    "VE": (5034000, 2308000, 2), "PD": (5034000, 2308000, 2), "TV": (5034000, 2308000, 2),
    "BL": (5034000, 2308000, 2), "RO": (5034000, 2308000, 2),
    "VR": (5024000, 1660000, 1), "VI": (5024000, 1660000, 1),
    "UD": (5104000, 2382000, 2), "PN": (5104000, 2382000, 2), "GO": (5104000, 2382000, 2),
    "TS": (5104000, 2382000, 2),
    # Trentino
    "TN": (5105000, 1668000, 1), "BZ": (5105000, 1668000, 1),
    # Emilia-Romagna
    "BO": (4925000, 1686000, 1), "MO": (4925000, 1686000, 1), "RE": (4925000, 1686000, 1),
    "RA": (4925000, 1686000, 1), "FC": (4925000, 1686000, 1), "RN": (4925000, 1686000, 1),
    "FE": (4967000, 1726000, 1), "PR": (4960000, 1586000, 1), "PC": (4960000, 1586000, 1),
    # Liguria
    "GE": (4914000, 1492000, 1), "SP": (4914000, 1492000, 1), "SV": (4914000, 1492000, 1),
    "IM": (4914000, 1492000, 1),
    # Toscana
    "FI": (4850000, 1680000, 1), "PT": (4850000, 1680000, 1), "PO": (4850000, 1680000, 1),
    "AR": (4850000, 1680000, 1), "PI": (4843000, 1612000, 1), "LI": (4843000, 1612000, 1),
    "LU": (4843000, 1612000, 1), "MS": (4843000, 1612000, 1), "SI": (4800000, 1698000, 1),
    "GR": (4800000, 1698000, 1),
    # Umbria/Marche
    "PG": (4770000, 1782000, 1), "TR": (4770000, 1782000, 1),
    "AN": (4822000, 2376000, 2), "PU": (4822000, 2376000, 2), "MC": (4822000, 2376000, 2),
    "AP": (4822000, 2376000, 2), "FM": (4822000, 2376000, 2),
    # Lazio
    "RM": (4642000, 1788000, 1), "VT": (4642000, 1788000, 1), "RI": (4642000, 1788000, 1),
    "LT": (4642000, 1788000, 1), "FR": (4642000, 1788000, 1),
    # Abruzzo/Molise
    "AQ": (4688000, 2370000, 2), "TE": (4688000, 2370000, 2), "PE": (4688000, 2370000, 2),
    "CH": (4688000, 2370000, 2), "CB": (4610000, 2486000, 2), "IS": (4610000, 2486000, 2),
    # Campania
    "NA": (4526000, 2440000, 2), "CE": (4526000, 2440000, 2), "BN": (4526000, 2440000, 2),
    "AV": (4526000, 2440000, 2), "SA": (4498000, 2492000, 2),
    # Puglia
    "BA": (4560000, 2672000, 2), "FG": (4560000, 2672000, 2), "BT": (4560000, 2672000, 2),
    "TA": (4560000, 2672000, 2), "BR": (4560000, 2672000, 2), "LE": (4456000, 2778000, 2),
    # Basilicata
    "PZ": (4496000, 2566000, 2), "MT": (4496000, 2566000, 2),
    # Calabria
    "CZ": (4314000, 2634000, 2), "CS": (4314000, 2634000, 2), "KR": (4314000, 2634000, 2),
    "VV": (4314000, 2634000, 2), "RC": (4218000, 2564000, 2),
    # Sicilia
    "PA": (4222000, 2360000, 2), "TP": (4222000, 2360000, 2), "AG": (4222000, 2360000, 2),
    "CL": (4222000, 2360000, 2), "EN": (4222000, 2360000, 2), "CT": (4222000, 2360000, 2),
    "ME": (4222000, 2360000, 2), "SR": (4222000, 2360000, 2), "RG": (4222000, 2360000, 2),
    # Sardegna
    "CA": (4338000, 1512000, 1), "OR": (4338000, 1512000, 1), "NU": (4338000, 1512000, 1),
    "SS": (4338000, 1512000, 1), "SU": (4338000, 1512000, 1),
}


def parse_taf_line(line: str, provincia: str) -> dict | None:
    """Parsa una linea TAF ed estrae i dati."""
    if len(line) < 50:
        return None

    # Estrai identificativo (primi caratteri): FOGLIO NUMERO ALLEGATO
    id_match = re.match(r'^([A-Z0-9]+)\s+(\d+)\s+(\d+)', line)
    if not id_match:
        return None

    foglio = id_match.group(1)
    numero = id_match.group(2)
    allegato = id_match.group(3)
    identificativo = f"PF{allegato.zfill(2)}/{numero.zfill(4)}/{foglio}"

    # Trova coordinate - due numeri decimali consecutivi
    # Formato Gauss-Boaga: NNNNNNNN.NNN EEEEEEE.EE
    # Formato Cassini-Soldner: NNNN.NNN EEE.EEE (numeri più piccoli)
    coord_match = re.search(
        r'(-?\d{1,8}\.\d{1,3})\s+(-?\d{1,8}\.\d{1,3})\s+(\d{1,3})',
        line
    )

    if not coord_match:
        return None

    try:
        coord_nord = float(coord_match.group(1))
        coord_est = float(coord_match.group(2))
        quota = float(coord_match.group(3))

        return {
            "identificativo": identificativo,
            "provincia": provincia,
            "coord_nord": coord_nord,
            "coord_est": coord_est,
            "quota": quota,
        }
    except (ValueError, IndexError):
        return None


def convert_to_wgs84(coord_est: float, coord_nord: float, provincia: str = None) -> tuple[float, float] | None:
    """Converte coordinate in WGS84.

    Supporta:
    - Gauss-Boaga (coordinate grandi, >1M)
    - Cassini-Soldner (coordinate piccole, <100K) con origine catastale
    """
    try:
        # Gauss-Boaga Ovest (Est tra 1.3M e 2M, Nord > 4M)
        if 1_300_000 < coord_est < 1_999_999 and coord_nord > 4_000_000:
            lon, lat = transformer_ovest.transform(coord_est, coord_nord)
        # Gauss-Boaga Est (Est tra 2.2M e 2.9M, Nord > 4M)
        elif 2_200_000 < coord_est < 2_999_999 and coord_nord > 4_000_000:
            lon, lat = transformer_est.transform(coord_est, coord_nord)
        # Cassini-Soldner (coordinate piccole) - converti via origine catastale
        elif abs(coord_nord) < 100_000 and abs(coord_est) < 100_000:
            if not provincia or provincia not in ORIGINI:
                return None

            # Ottieni origine catastale per questa provincia
            origine_nord, origine_est, fuso = ORIGINI[provincia]

            # Converti da CS locale a Gauss-Boaga aggiungendo l'origine
            gb_nord = origine_nord + coord_nord
            gb_est = origine_est + coord_est

            # Trasforma in WGS84 usando il fuso corretto
            if fuso == 1:
                lon, lat = transformer_ovest.transform(gb_est, gb_nord)
            else:
                lon, lat = transformer_est.transform(gb_est, gb_nord)
        else:
            return None

        # Valida range Italia
        if 35.0 < lat < 48.0 and 6.0 < lon < 19.0:
            return (lat, lon)
        return None
    except Exception:
        return None


def process_taf_file(taf_path: Path) -> list[dict]:
    """Processa un file TAF e restituisce i punti con WGS84."""
    provincia = taf_path.stem.upper()
    punti = []

    try:
        raw_content = taf_path.read_bytes()

        # Se è un file ZIP, estrai il contenuto
        if raw_content[:2] == b"PK":
            try:
                with zipfile.ZipFile(BytesIO(raw_content)) as zf:
                    for name in zf.namelist():
                        if name.upper().endswith(".TAF"):
                            content = zf.read(name).decode('latin-1', errors='ignore')
                            break
                    else:
                        print(f"  Nessun .TAF trovato nel ZIP")
                        return punti
            except zipfile.BadZipFile:
                content = raw_content.decode('latin-1', errors='ignore')
        else:
            content = raw_content.decode('latin-1', errors='ignore')

        for line in content.splitlines():
            punto = parse_taf_line(line, provincia)
            if punto:
                wgs84 = convert_to_wgs84(punto["coord_est"], punto["coord_nord"], provincia)
                if wgs84:
                    punto["lat_wgs84"] = round(wgs84[0], 6)
                    punto["lon_wgs84"] = round(wgs84[1], 6)
                    punti.append(punto)
    except Exception as e:
        print(f"  Errore {provincia}: {e}")

    return punti


def save_csv(punti: list[dict], output_path: Path):
    """Salva i punti in formato CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["identificativo", "provincia", "lat_wgs84", "lon_wgs84", "quota", "coord_nord", "coord_est"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(punti)


def save_geojson(punti: list[dict], output_path: Path):
    """Salva i punti in formato GeoJSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    features = []
    for p in punti:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [p["lon_wgs84"], p["lat_wgs84"]]
            },
            "properties": {
                "id": p["identificativo"],
                "provincia": p["provincia"],
                "quota": p["quota"]
            }
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)


def main():
    taf_dir = Path(__file__).parent.parent / "data" / "taf"
    output_dir = Path(__file__).parent.parent / "data" / "wgs84"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("TRASFORMAZIONE TAF → WGS84")
    print("=" * 60)

    taf_files = list(taf_dir.glob("*.TAF"))
    print(f"File TAF trovati: {len(taf_files)}")
    print()

    tutti_punti = []

    for taf_path in sorted(taf_files):
        provincia = taf_path.stem.upper()
        print(f"[{provincia}] ", end="", flush=True)

        punti = process_taf_file(taf_path)
        print(f"{len(punti)} punti")

        if punti:
            # Salva CSV per provincia
            prov_csv = output_dir / "per_provincia" / f"{provincia}.csv"
            save_csv(punti, prov_csv)
            tutti_punti.extend(punti)

    print()
    print("=" * 60)
    print(f"TOTALE: {len(tutti_punti)} punti WGS84")
    print("=" * 60)

    # Salva CSV completo
    if tutti_punti:
        csv_path = output_dir / "punti_fiduciali.csv"
        save_csv(tutti_punti, csv_path)
        print(f"CSV: {csv_path}")

        # Salva GeoJSON
        geojson_path = output_dir / "punti_fiduciali.geojson"
        save_geojson(tutti_punti, geojson_path)
        print(f"GeoJSON: {geojson_path}")

    print()
    print("Completato!")


if __name__ == "__main__":
    main()
