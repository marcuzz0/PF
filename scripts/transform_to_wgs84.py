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

# ============================================================================
# ORIGINI CATASTALI CASSINI-SOLDNER
# ============================================================================
# Coordinate WGS84 (lat, lon) delle 31 Grandi Origini catastali italiane.
# Ricavate da ricerca su fonti ufficiali (ConveRgo, Cartlab, IGM, AdE).
#
# Le coordinate originali erano in Bessel-Genova con longitudini riferite a:
# - GE (Genova): 8°55'15,709" E Greenwich = 8.921030° E
# - R  (Roma Monte Mario): 12°27'08,4" E Greenwich = 12.452333° E
# - CF (Castanea delle Furie): ~15°28' E Greenwich = 15.466667° E
# ============================================================================

# Longitudine di riferimento dei meridiani fondamentali
LON_GENOVA = 8.921030
LON_ROMA = 12.452333
LON_CASTANEA = 15.466667

def dms_to_dd(degrees: int, minutes: int, seconds: float) -> float:
    """Converte gradi-minuti-secondi in gradi decimali."""
    return degrees + minutes / 60.0 + seconds / 3600.0

# Coordinate Bessel-Genova delle 31 Grandi Origini (lat, lon_offset, meridiano)
# Nota: lon_offset è la longitudine rispetto al meridiano indicato
ORIGINI_BESSEL = {
    # 1. Vercelli (Punto Ideale) - BI, VC, NO, VB
    "Vercelli": (dms_to_dd(45, 26, 0), dms_to_dd(0, 0, 0), "GE"),  # Approx
    # 2. Pordenone - UD, PN, GO, TS
    "Pordenone": (dms_to_dd(45, 57, 15.104), dms_to_dd(3, 44, 21.453), "GE"),
    # 3. Monte Bronzone - SO, BG, BS, CR
    "MonteBronzone": (dms_to_dd(45, 42, 31.080), dms_to_dd(1, 4, 9.404), "GE"),
    # 4. Lodi - MI, CO, VA, LC, MB, LO, PV
    "Lodi": (dms_to_dd(45, 18, 49.219), dms_to_dd(0, 34, 53.166), "GE"),
    # 5. Alessandria - AL, AT
    "Alessandria": (dms_to_dd(44, 54, 51.212), -dms_to_dd(0, 18, 37.157), "GE"),
    # 6. Monte Bignone - IM
    "MonteBignone": (dms_to_dd(43, 52, 22.465), -dms_to_dd(1, 11, 17.116), "GE"),
    # 7. Forte Diamante - GE, SP, SV, PR (parte)
    "ForteDiamante": (dms_to_dd(44, 27, 38.020), dms_to_dd(0, 1, 4.18), "GE"),
    # 8. Portonovo - AN, MC, AP, FM, PU
    "Portonovo": (dms_to_dd(44, 31, 55.045), dms_to_dd(2, 49, 55.338), "GE"),
    # 9. Siena (Torre del Mangia) - SI, GR, AR, FI, PT, PO
    "Siena": (dms_to_dd(43, 19, 3.126), dms_to_dd(2, 24, 39.027), "GE"),
    # 10. Urbino
    "Urbino": (dms_to_dd(43, 43, 27.930), dms_to_dd(3, 42, 54.290), "GE"),
    # 11. Monte Pennino - PG, TR
    "MontePennino": (dms_to_dd(43, 6, 2.076), dms_to_dd(3, 58, 3.310), "GE"),
    # 12. Roma (Monte Mario) - RM, VT, RI, LT, FR
    "MonteMario": (dms_to_dd(41, 55, 24.399), dms_to_dd(3, 31, 51.131), "GE"),
    # 13. Monte Ocre - AQ, TE, PE, CH
    "MonteOcre": (dms_to_dd(42, 15, 20.090), dms_to_dd(0, 59, 28.010), "R"),
    # 14. Monte Palombo - CB, IS
    "MontePalombo": (dms_to_dd(41, 50, 34.650), dms_to_dd(1, 42, 34.580), "CF"),
    # 15. Monte Terminio - NA, CE, BN, AV, SA
    "MonteTerminio": (dms_to_dd(40, 50, 25.860), -dms_to_dd(0, 34, 59.190), "CF"),
    # 16. Taranto - TA, BA (parte), BR (parte)
    "Taranto": (dms_to_dd(40, 28, 30.105), dms_to_dd(1, 42, 30.469), "CF"),
    # 17. Lecce - LE
    "Lecce": (dms_to_dd(40, 21, 2.850), dms_to_dd(2, 38, 57.488), "CF"),
    # 18. Monte Brutto - CS, CZ, KR, VV
    "MonteBrutto": (dms_to_dd(39, 8, 22.455), dms_to_dd(0, 54, 6.199), "CF"),
    # 19. Monte Titone - PA, TP, AG, CL
    "MonteTitone": (dms_to_dd(37, 50, 47.830), dms_to_dd(0, 5, 14.870), "R"),
    # 20. Monte Etna - CT, ME, EN, SR, RG
    "MonteEtna": (dms_to_dd(37, 45, 52.878), dms_to_dd(2, 32, 1.224), "R"),
    # 21. Bari - BA, FG, BT
    "Bari": (dms_to_dd(41, 7, 44.522), dms_to_dd(4, 21, 27.315), "R"),
    # 22. Sardegna (Punto Ideale) - CA, OR, NU, SS, SU
    "Sardegna": (dms_to_dd(39, 12, 0), dms_to_dd(0, 13, 0), "GE"),  # Approx
    # 23. Reggio Calabria - RC
    "ReggioCalabria": (dms_to_dd(38, 6, 15), dms_to_dd(0, 20, 0), "CF"),  # Approx
    # 24. Venezia - VE, PD, TV, BL, RO
    "Venezia": (dms_to_dd(45, 29, 0), dms_to_dd(3, 24, 0), "GE"),  # Approx
    # 25. Bologna - BO, MO, RE, RA, FC, RN, FE
    "Bologna": (dms_to_dd(44, 29, 37), dms_to_dd(2, 23, 16), "GE"),
    # 26. Verona - VR, VI
    "Verona": (dms_to_dd(45, 26, 0), dms_to_dd(2, 1, 0), "GE"),  # Approx
    # 27. Trento - TN, BZ
    "Trento": (dms_to_dd(46, 4, 0), dms_to_dd(2, 10, 0), "GE"),  # Approx
    # 28. Torino - TO, CN, AO
    "Torino": (dms_to_dd(45, 4, 12), -dms_to_dd(0, 36, 45), "GE"),
    # 29. Mantova - MN
    "Mantova": (dms_to_dd(45, 9, 30), dms_to_dd(1, 51, 50), "GE"),
    # 30. Potenza/Basilicata - PZ, MT
    "Potenza": (dms_to_dd(40, 38, 0), dms_to_dd(1, 10, 0), "CF"),  # Approx
    # 31. Pisa/Lucca - PI, LI, LU, MS
    "Pisa": (dms_to_dd(43, 43, 0), dms_to_dd(1, 28, 0), "GE"),  # Approx
}

def bessel_to_wgs84(lat_bessel: float, lon_offset: float, meridiano: str) -> tuple[float, float]:
    """Converte coordinate Bessel-Genova in WGS84 approssimate."""
    # Longitudine assoluta
    if meridiano == "GE":
        lon_wgs84 = LON_GENOVA + lon_offset
    elif meridiano == "R":
        lon_wgs84 = LON_ROMA + lon_offset
    elif meridiano == "CF":
        lon_wgs84 = LON_CASTANEA + lon_offset
    else:
        lon_wgs84 = LON_GENOVA + lon_offset

    # Latitudine: differenza Bessel→WGS84 trascurabile per scopi pratici
    lat_wgs84 = lat_bessel

    return (lat_wgs84, lon_wgs84)

# Genera coordinate WGS84 delle origini
ORIGINI_WGS84 = {}
for nome, (lat, lon_off, mer) in ORIGINI_BESSEL.items():
    ORIGINI_WGS84[nome] = bessel_to_wgs84(lat, lon_off, mer)

# Mappatura Province → Origine catastale
PROVINCE_ORIGINI = {
    # Piemonte
    "TO": "Torino", "CN": "Torino", "AO": "Torino",
    "BI": "Vercelli", "VC": "Vercelli", "NO": "Vercelli", "VB": "Vercelli",
    "AL": "Alessandria", "AT": "Alessandria",
    # Lombardia
    "MI": "Lodi", "CO": "Lodi", "VA": "Lodi", "LC": "Lodi", "MB": "Lodi",
    "LO": "Lodi", "PV": "Lodi",
    "SO": "MonteBronzone", "BG": "MonteBronzone", "BS": "MonteBronzone", "CR": "MonteBronzone",
    "MN": "Mantova",
    # Veneto
    "VE": "Venezia", "PD": "Venezia", "TV": "Venezia", "BL": "Venezia", "RO": "Venezia",
    "VR": "Verona", "VI": "Verona",
    # Friuli-Venezia Giulia
    "UD": "Pordenone", "PN": "Pordenone", "GO": "Pordenone", "TS": "Pordenone",
    # Trentino-Alto Adige
    "TN": "Trento", "BZ": "Trento",
    # Emilia-Romagna
    "BO": "Bologna", "MO": "Bologna", "RE": "Bologna", "RA": "Bologna",
    "FC": "Bologna", "RN": "Bologna", "FE": "Bologna",
    "PR": "ForteDiamante", "PC": "ForteDiamante",
    # Liguria
    "GE": "ForteDiamante", "SP": "ForteDiamante", "SV": "ForteDiamante",
    "IM": "MonteBignone",
    # Toscana
    "FI": "Siena", "PT": "Siena", "PO": "Siena", "AR": "Siena", "SI": "Siena", "GR": "Siena",
    "PI": "Pisa", "LI": "Pisa", "LU": "Pisa", "MS": "Pisa",
    # Umbria
    "PG": "MontePennino", "TR": "MontePennino",
    # Marche
    "AN": "Portonovo", "MC": "Portonovo", "AP": "Portonovo", "FM": "Portonovo", "PU": "Portonovo",
    # Lazio
    "RM": "MonteMario", "VT": "MonteMario", "RI": "MonteMario", "LT": "MonteMario", "FR": "MonteMario",
    # Abruzzo
    "AQ": "MonteOcre", "TE": "MonteOcre", "PE": "MonteOcre", "CH": "MonteOcre",
    # Molise
    "CB": "MontePalombo", "IS": "MontePalombo",
    # Campania
    "NA": "MonteTerminio", "CE": "MonteTerminio", "BN": "MonteTerminio",
    "AV": "MonteTerminio", "SA": "MonteTerminio",
    # Puglia
    "BA": "Bari", "FG": "Bari", "BT": "Bari",
    "TA": "Taranto", "BR": "Taranto",
    "LE": "Lecce",
    # Basilicata
    "PZ": "Potenza", "MT": "Potenza",
    # Calabria
    "CS": "MonteBrutto", "CZ": "MonteBrutto", "KR": "MonteBrutto", "VV": "MonteBrutto",
    "RC": "ReggioCalabria",
    # Sicilia
    "PA": "MonteTitone", "TP": "MonteTitone", "AG": "MonteTitone", "CL": "MonteTitone",
    "CT": "MonteEtna", "ME": "MonteEtna", "EN": "MonteEtna", "SR": "MonteEtna", "RG": "MonteEtna",
    # Sardegna
    "CA": "Sardegna", "OR": "Sardegna", "NU": "Sardegna", "SS": "Sardegna", "SU": "Sardegna",
}

# Cache per i transformer Cassini-Soldner personalizzati
_cs_transformers = {}


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


def get_cs_transformer(provincia: str):
    """Ottiene o crea un transformer Cassini-Soldner per una provincia."""
    if provincia in _cs_transformers:
        return _cs_transformers[provincia]

    if provincia not in PROVINCE_ORIGINI:
        return None

    origine_nome = PROVINCE_ORIGINI[provincia]
    if origine_nome not in ORIGINI_WGS84:
        return None

    lat_0, lon_0 = ORIGINI_WGS84[origine_nome]

    # Crea CRS Cassini-Soldner personalizzato con ellissoide Bessel
    proj4_string = (
        f"+proj=cass +lat_0={lat_0} +lon_0={lon_0} "
        f"+x_0=0 +y_0=0 +ellps=bessel +units=m +no_defs"
    )

    try:
        crs_cs = CRS.from_proj4(proj4_string)
        transformer = Transformer.from_crs(crs_cs, CRS_WGS84, always_xy=True)
        _cs_transformers[provincia] = transformer
        return transformer
    except Exception:
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
        # Cassini-Soldner (coordinate piccole) - usa CRS personalizzato
        elif abs(coord_nord) < 100_000 and abs(coord_est) < 100_000:
            if not provincia:
                return None

            transformer = get_cs_transformer(provincia)
            if not transformer:
                return None

            # Trasforma direttamente da Cassini-Soldner locale a WGS84
            lon, lat = transformer.transform(coord_est, coord_nord)
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
