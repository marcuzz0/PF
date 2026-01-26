"""
Query on-demand dei Punti Fiduciali.

Invece di scaricare tutti i TAF in anticipo, questo modulo permette di
fare query scaricando solo i dati necessari al momento della richiesta.
"""

import logging
from pathlib import Path
from typing import Optional
import requests

from .taf_parser import TafParser
from .coordinate_converter import CoordinateConverter
from .database import PfDatabase

logger = logging.getLogger(__name__)

# Mapping provincia -> codice per il download
PROVINCE_CODES = {
    "RM": "Roma", "MI": "Milano", "TO": "Torino", "NA": "Napoli",
    "FI": "Firenze", "BO": "Bologna", "GE": "Genova", "PA": "Palermo",
    "BA": "Bari", "CT": "Catania", "VE": "Venezia", "VR": "Verona",
    # ... altre province
}


class OnDemandPFQuery:
    """
    Sistema di query on-demand per i Punti Fiduciali.

    Scarica e processa i TAF solo quando necessario, cachando localmente.
    """

    def __init__(
        self,
        cache_dir: str | Path = "data/taf",
        db_path: str | Path = "data/pf_italia.db"
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path)
        self.parser = TafParser()
        self.converter = CoordinateConverter()
        self._db: Optional[PfDatabase] = None
        self._loaded_provinces: set[str] = set()

    @property
    def db(self) -> PfDatabase:
        """Lazy-load del database."""
        if self._db is None:
            self._db = PfDatabase(self.db_path)
            self._db.init_schema()
        return self._db

    def _get_province_for_location(self, lat: float, lon: float) -> list[str]:
        """
        Determina quali province potrebbero contenere punti vicini alla posizione.

        Usa un mapping approssimativo lat/lon -> province.
        """
        # Mapping semplificato per le principali aree
        province = []

        # Roma e Lazio
        if 41.5 < lat < 42.5 and 11.5 < lon < 14.0:
            province.extend(["RM", "VT", "RI", "LT", "FR"])

        # Milano e Lombardia
        if 45.0 < lat < 46.5 and 8.5 < lon < 10.5:
            province.extend(["MI", "MB", "CO", "VA", "LC", "BG", "BS", "PV", "LO", "CR", "MN"])

        # Torino e Piemonte
        if 44.5 < lat < 46.0 and 7.0 < lon < 9.0:
            province.extend(["TO", "CN", "AT", "AL", "NO", "VC", "BI", "VB"])

        # Napoli e Campania
        if 40.5 < lat < 41.5 and 13.5 < lon < 15.5:
            province.extend(["NA", "CE", "BN", "AV", "SA"])

        # Firenze e Toscana
        if 42.5 < lat < 44.5 and 10.0 < lon < 12.5:
            province.extend(["FI", "AR", "SI", "GR", "LI", "PI", "LU", "MS", "PT", "PO"])

        # Bologna e Emilia-Romagna
        if 44.0 < lat < 45.0 and 10.0 < lon < 12.5:
            province.extend(["BO", "MO", "RE", "PR", "PC", "FE", "RA", "FC", "RN"])

        # Venezia e Veneto
        if 45.0 < lat < 46.5 and 10.5 < lon < 13.0:
            province.extend(["VE", "PD", "VR", "VI", "TV", "BL", "RO"])

        # Default: province più vicine in base alla longitudine
        if not province:
            if lon < 10:
                province = ["TO", "GE", "MI"]
            elif lon < 12:
                province = ["BO", "FI", "RM"]
            elif lon < 14:
                province = ["RM", "NA", "AN"]
            else:
                province = ["BA", "LE", "TA"]

        return province[:5]  # Max 5 province

    def _download_taf(self, provincia: str) -> bool:
        """Scarica il TAF per una provincia se non già presente."""
        taf_file = self.cache_dir / f"{provincia}.TAF"

        if taf_file.exists():
            logger.info(f"TAF {provincia} già in cache")
            return True

        logger.info(f"Download TAF {provincia}...")

        # Prova altervista
        try:
            response = requests.post(
                "http://fiduciali.altervista.org/download_taf.php",
                data={"provincia": provincia, "tipo": "taf"},
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            if response.status_code == 200 and len(response.content) > 500:
                # Verifica se è un ZIP
                if response.content[:2] == b"PK":
                    import zipfile
                    from io import BytesIO
                    with zipfile.ZipFile(BytesIO(response.content)) as zf:
                        for name in zf.namelist():
                            if name.upper().endswith(".TAF"):
                                taf_file.write_bytes(zf.read(name))
                                logger.info(f"TAF {provincia} scaricato (ZIP)")
                                return True
                else:
                    taf_file.write_bytes(response.content)
                    logger.info(f"TAF {provincia} scaricato")
                    return True
        except Exception as e:
            logger.warning(f"Download fallito per {provincia}: {e}")

        return False

    def _load_province(self, provincia: str) -> int:
        """Carica una provincia nel database se non già caricata."""
        if provincia in self._loaded_provinces:
            return 0

        taf_file = self.cache_dir / f"{provincia}.TAF"
        if not taf_file.exists():
            if not self._download_taf(provincia):
                return 0

        # Parsa e converti
        punti = list(self.parser.parse_file(taf_file, provincia=provincia))
        if not punti:
            return 0

        converted = self.converter.convert_batch(punti, update_in_place=True)

        # Inserisci nel DB
        inserted, _ = self.db.insert_punti(converted)
        self._loaded_provinces.add(provincia)

        logger.info(f"Caricati {inserted} punti da {provincia}")
        return inserted

    def query(
        self,
        lat: float,
        lon: float,
        buffer_m: float = 1000,
        auto_download: bool = True
    ) -> list[dict]:
        """
        Cerca punti fiduciali vicino a una posizione.

        Se auto_download=True, scarica automaticamente i TAF delle province
        potenzialmente interessate.

        Args:
            lat: Latitudine WGS84
            lon: Longitudine WGS84
            buffer_m: Raggio di ricerca in metri
            auto_download: Se True, scarica TAF mancanti automaticamente

        Returns:
            Lista di punti fiduciali ordinati per distanza
        """
        if auto_download:
            # Determina province da caricare
            province = self._get_province_for_location(lat, lon)
            for prov in province:
                self._load_province(prov)

        # Esegui query
        return self.db.query_by_location(lat, lon, buffer_m)

    def preload_provinces(self, province: list[str]) -> dict[str, int]:
        """
        Pre-carica una lista di province.

        Returns:
            Dict con conteggio punti per provincia
        """
        results = {}
        for prov in province:
            results[prov] = self._load_province(prov.upper())
        return results

    def close(self):
        """Chiude le connessioni."""
        if self._db:
            self._db.close()


def query_pf_online(
    lat: float,
    lon: float,
    buffer_m: float = 1000,
    cache_dir: str = "data/taf",
    db_path: str = "data/pf_online.db"
) -> list[dict]:
    """
    Funzione semplificata per query on-demand.

    Esempio:
        results = query_pf_online(41.9028, 12.4964, buffer_m=1000)
        for r in results:
            print(f"{r['identificativo']}: {r['distanza_m']:.0f}m")
    """
    query = OnDemandPFQuery(cache_dir=cache_dir, db_path=db_path)
    try:
        return query.query(lat, lon, buffer_m)
    finally:
        query.close()
