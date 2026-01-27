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
    """Converte coordinate in WGS84."""
    try:
        # Gauss-Boaga Ovest (Est tra 1.3M e 2M, Nord > 4M)
        if 1_300_000 < coord_est < 1_999_999 and coord_nord > 4_000_000:
            lon, lat = transformer_ovest.transform(coord_est, coord_nord)
        # Gauss-Boaga Est (Est tra 2.2M e 2.9M, Nord > 4M)
        elif 2_200_000 < coord_est < 2_999_999 and coord_nord > 4_000_000:
            lon, lat = transformer_est.transform(coord_est, coord_nord)
        # Cassini-Soldner (coordinate piccole) - richiede origine
        elif abs(coord_nord) < 100_000 and abs(coord_est) < 100_000:
            # Per Cassini-Soldner servono le origini catastali
            # TODO: implementare conversione completa
            return None
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
                wgs84 = convert_to_wgs84(punto["coord_est"], punto["coord_nord"])
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
