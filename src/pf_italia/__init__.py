"""
PF Italia - Download automatico Punti Fiduciali catastali Italia in WGS84

Questo pacchetto permette di:
- Scaricare i file TAF (Tabella Attuale Punti Fiduciali) da tutte le province italiane
- Parsare i file TAF in formato ASCII a larghezza fissa
- Convertire le coordinate da Gauss-Boaga/Cassini-Soldner a WGS84
- Creare un database spaziale unificato
- Effettuare query spaziali per coordinata + buffer
"""

__version__ = "0.1.0"

from .taf_parser import TafParser, PuntoFiduciale
from .coordinate_converter import CoordinateConverter
from .downloader import TafDownloader
from .database import PfDatabase
from .query import query_pf, get_pf_geojson

__all__ = [
    "TafParser",
    "PuntoFiduciale",
    "CoordinateConverter",
    "TafDownloader",
    "PfDatabase",
    "query_pf",
    "get_pf_geojson",
]
