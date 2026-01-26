"""
API per query sui Punti Fiduciali.

Funzioni principali:
- query_pf(lat, lon, buffer_m) -> lista punti
- get_pf_geojson(lat, lon, buffer_m) -> GeoJSON FeatureCollection
"""

import json
from pathlib import Path
from typing import Optional, Union

from .database import PfDatabase


def query_pf(
    lat: float,
    lon: float,
    buffer_m: float = 1000,
    db_path: str | Path = "data/pf_italia.db",
    limit: int = 100,
) -> list[dict]:
    """
    Cerca punti fiduciali entro un buffer da una coordinata WGS84.

    Args:
        lat: Latitudine WGS84
        lon: Longitudine WGS84
        buffer_m: Raggio di ricerca in metri (default 1000m)
        db_path: Percorso database
        limit: Numero massimo risultati

    Returns:
        Lista di dizionari con i punti trovati, ordinati per distanza

    Esempio:
        >>> risultati = query_pf(41.9028, 12.4964, buffer_m=500)
        >>> for pf in risultati:
        ...     print(f"{pf['identificativo']}: {pf['distanza_m']:.0f}m")
    """
    with PfDatabase(db_path) as db:
        return db.query_by_location(lat, lon, buffer_m, limit)


def get_pf_geojson(
    lat: float,
    lon: float,
    buffer_m: float = 1000,
    db_path: str | Path = "data/pf_italia.db",
    limit: int = 100,
    include_search_area: bool = True,
) -> dict:
    """
    Cerca punti fiduciali e restituisce un GeoJSON FeatureCollection.

    Args:
        lat: Latitudine WGS84
        lon: Longitudine WGS84
        buffer_m: Raggio di ricerca in metri
        db_path: Percorso database
        limit: Numero massimo risultati
        include_search_area: Se True, include un poligono con l'area di ricerca

    Returns:
        GeoJSON FeatureCollection con i punti trovati

    Esempio:
        >>> geojson = get_pf_geojson(41.9028, 12.4964, buffer_m=500)
        >>> with open("risultati.geojson", "w") as f:
        ...     json.dump(geojson, f, indent=2)
    """
    punti = query_pf(lat, lon, buffer_m, db_path, limit)

    features = []

    # Aggiungi area di ricerca come cerchio approssimato
    if include_search_area:
        features.append(_create_search_area_feature(lat, lon, buffer_m))

    # Aggiungi punto centrale di ricerca
    features.append({
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat]
        },
        "properties": {
            "type": "search_center",
            "buffer_m": buffer_m,
        }
    })

    # Aggiungi punti fiduciali
    for pf in punti:
        if pf.get("lat_wgs84") and pf.get("lon_wgs84"):
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [pf["lon_wgs84"], pf["lat_wgs84"]]
                },
                "properties": {
                    "type": "punto_fiduciale",
                    "id": pf["identificativo"],
                    "provincia": pf.get("provincia"),
                    "comune": pf.get("codice_comune"),
                    "foglio": pf.get("foglio"),
                    "numero": pf.get("numero"),
                    "quota": pf.get("quota"),
                    "distanza_m": round(pf.get("distanza_m", 0), 1),
                    "attendibilita": pf.get("attendibilita_plan"),
                    "ha_monografia": bool(pf.get("ha_monografia")),
                    "descrizione": pf.get("descrizione_plan", ""),
                }
            })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "query": {
                "lat": lat,
                "lon": lon,
                "buffer_m": buffer_m,
            },
            "results": len(punti),
        }
    }


def _create_search_area_feature(
    lat: float,
    lon: float,
    buffer_m: float,
    num_points: int = 32
) -> dict:
    """Crea un poligono circolare approssimato per l'area di ricerca."""
    from math import cos, sin, radians, pi

    # Converti buffer in gradi (approssimazione)
    # 1 grado lat ~ 111 km
    buffer_lat = buffer_m / 111000.0
    # 1 grado lon dipende dalla latitudine
    buffer_lon = buffer_m / (111000.0 * cos(radians(lat)))

    # Genera punti del cerchio
    coordinates = []
    for i in range(num_points + 1):  # +1 per chiudere il cerchio
        angle = 2 * pi * i / num_points
        point_lat = lat + buffer_lat * sin(angle)
        point_lon = lon + buffer_lon * cos(angle)
        coordinates.append([point_lon, point_lat])

    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [coordinates]
        },
        "properties": {
            "type": "search_area",
            "buffer_m": buffer_m,
        }
    }


def query_by_foglio(
    provincia: str,
    codice_comune: str,
    foglio: str,
    db_path: str | Path = "data/pf_italia.db",
) -> list[dict]:
    """
    Cerca tutti i punti fiduciali di un foglio catastale.

    Args:
        provincia: Sigla provincia (es. "RM")
        codice_comune: Codice catastale comune (es. "H501")
        foglio: Numero foglio (es. "001")
        db_path: Percorso database

    Returns:
        Lista di dizionari con i punti del foglio
    """
    with PfDatabase(db_path) as db:
        return db.query_by_foglio(provincia, codice_comune, foglio)


def get_statistics(db_path: str | Path = "data/pf_italia.db") -> dict:
    """
    Restituisce statistiche sul database dei punti fiduciali.

    Args:
        db_path: Percorso database

    Returns:
        Dizionario con statistiche
    """
    with PfDatabase(db_path) as db:
        return db.get_stats()


def export_geojson(
    output_path: str | Path,
    provincia: Optional[str] = None,
    db_path: str | Path = "data/pf_italia.db",
) -> int:
    """
    Esporta punti fiduciali in un file GeoJSON.

    Args:
        output_path: Percorso file output
        provincia: Se specificato, esporta solo questa provincia
        db_path: Percorso database

    Returns:
        Numero di punti esportati
    """
    output_path = Path(output_path)

    with PfDatabase(db_path) as db:
        conn = db.connect()
        cursor = conn.cursor()

        if provincia:
            cursor.execute("""
                SELECT * FROM punti_fiduciali
                WHERE provincia = ? AND lat_wgs84 IS NOT NULL
            """, (provincia.upper(),))
        else:
            cursor.execute("""
                SELECT * FROM punti_fiduciali
                WHERE lat_wgs84 IS NOT NULL
            """)

        features = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row_dict["lon_wgs84"], row_dict["lat_wgs84"]]
                },
                "properties": {
                    "id": row_dict["identificativo"],
                    "provincia": row_dict["provincia"],
                    "comune": row_dict["codice_comune"],
                    "foglio": row_dict["foglio"],
                    "numero": row_dict["numero"],
                    "quota": row_dict["quota"],
                    "attendibilita_plan": row_dict["attendibilita_plan"],
                    "ha_monografia": bool(row_dict["ha_monografia"]),
                }
            })

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)

    return len(features)
