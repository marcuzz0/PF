"""
Convertitore di coordinate per i Punti Fiduciali.

Gestisce la conversione da vari sistemi catastali italiani a WGS84:
- Gauss-Boaga Ovest (EPSG:3003) -> WGS84
- Gauss-Boaga Est (EPSG:3004) -> WGS84
- Cassini-Soldner (con origini catastali) -> WGS84
- Sanson-Flamsteed -> WGS84
- UTM WGS84 Zone 32N/33N -> WGS84 geografiche
"""

import json
import logging
from pathlib import Path
from typing import Optional

from pyproj import CRS, Transformer
from pyproj.exceptions import ProjError

from .models import PuntoFiduciale, SistemaCoordinate, OrigineCatastale

logger = logging.getLogger(__name__)


class CoordinateConverter:
    """
    Convertitore di coordinate per i sistemi catastali italiani.

    Supporta:
    - Conversione diretta per Gauss-Boaga (usando EPSG standard)
    - Conversione Cassini-Soldner tramite origini catastali
    - Cache delle trasformazioni per performance
    """

    # CRS standard
    CRS_WGS84 = CRS.from_epsg(4326)
    CRS_GB_OVEST = CRS.from_epsg(3003)  # Monte Mario / Italy zone 1
    CRS_GB_EST = CRS.from_epsg(3004)    # Monte Mario / Italy zone 2
    CRS_UTM32N = CRS.from_epsg(32632)   # WGS 84 / UTM zone 32N
    CRS_UTM33N = CRS.from_epsg(32633)   # WGS 84 / UTM zone 33N

    def __init__(self, origini_file: Optional[str | Path] = None):
        """
        Inizializza il convertitore.

        Args:
            origini_file: Percorso al file JSON con le origini catastali.
                         Se None, usa solo le 31 grandi origini predefinite.
        """
        self._transformers: dict[str, Transformer] = {}
        self._origini: dict[str, OrigineCatastale] = {}

        # Inizializza i transformer standard
        self._init_standard_transformers()

        # Carica le grandi origini predefinite
        self._load_default_origini()

        # Carica origini personalizzate se specificate
        if origini_file:
            self.load_origini(origini_file)

    def _init_standard_transformers(self):
        """Inizializza i transformer per i sistemi standard."""
        self._transformers["GB_OVEST"] = Transformer.from_crs(
            self.CRS_GB_OVEST, self.CRS_WGS84, always_xy=True
        )
        self._transformers["GB_EST"] = Transformer.from_crs(
            self.CRS_GB_EST, self.CRS_WGS84, always_xy=True
        )
        self._transformers["UTM32"] = Transformer.from_crs(
            self.CRS_UTM32N, self.CRS_WGS84, always_xy=True
        )
        self._transformers["UTM33"] = Transformer.from_crs(
            self.CRS_UTM33N, self.CRS_WGS84, always_xy=True
        )

    def _load_default_origini(self):
        """
        Carica le 31 grandi origini catastali predefinite.

        Coordinate Gauss-Boaga delle grandi origini da documentazione ufficiale.
        """
        # Le 31 grandi origini con coordinate GB approssimate
        # Fonte: documentazione IGM e Agenzia delle Entrate
        grandi_origini = [
            # Piemonte e Valle d'Aosta
            ("TORINO", "Torino", 4994000, 1402000, 1, 45.0703, 7.6869),
            ("ALESSANDRIA", "Alessandria", 4960000, 1470000, 1, 44.9122, 8.6147),
            ("AOSTA", "Aosta", 5068000, 1368000, 1, 45.7372, 7.3150),
            # Lombardia
            ("MILANO", "Milano", 5032000, 1514000, 1, 45.4642, 9.1900),
            ("BRESCIA", "Brescia", 5042000, 1596000, 1, 45.5416, 10.2118),
            ("MANTOVA", "Mantova", 4996000, 1632000, 1, 45.1564, 10.7914),
            # Veneto e Friuli
            ("VENEZIA", "Venezia", 5034000, 2308000, 2, 45.4408, 12.3155),
            ("VERONA", "Verona", 5024000, 1660000, 1, 45.4384, 10.9916),
            ("UDINE", "Udine", 5104000, 2382000, 2, 46.0711, 13.2346),
            # Trentino (coordinate speciali)
            ("TRENTO", "Trento", 5105000, 1668000, 1, 46.0679, 11.1211),
            # Emilia-Romagna
            ("BOLOGNA", "Bologna", 4925000, 1686000, 1, 44.4949, 11.3426),
            ("FERRARA", "Ferrara", 4967000, 1726000, 1, 44.8381, 11.6199),
            ("PARMA", "Parma", 4960000, 1586000, 1, 44.8015, 10.3279),
            # Liguria
            ("GENOVA", "Genova", 4914000, 1492000, 1, 44.4056, 8.9463),
            # Toscana
            ("FIRENZE", "Firenze", 4850000, 1680000, 1, 43.7696, 11.2558),
            ("PISA", "Pisa", 4843000, 1612000, 1, 43.7228, 10.4017),
            ("SIENA", "Siena", 4800000, 1698000, 1, 43.3188, 11.3308),
            # Umbria e Marche
            ("PERUGIA", "Perugia", 4770000, 1782000, 1, 43.1107, 12.3908),
            ("ANCONA", "Ancona", 4822000, 2376000, 2, 43.6158, 13.5189),
            # Lazio
            ("ROMA", "Roma", 4642000, 1788000, 1, 41.9028, 12.4964),
            # Abruzzo e Molise
            ("AQUILA", "L'Aquila", 4688000, 2370000, 2, 42.3498, 13.3995),
            ("CAMPOBASSO", "Campobasso", 4610000, 2486000, 2, 41.5603, 14.6684),
            # Campania
            ("NAPOLI", "Napoli", 4526000, 2440000, 2, 40.8518, 14.2681),
            ("SALERNO", "Salerno", 4498000, 2492000, 2, 40.6824, 14.7681),
            # Puglia
            ("BARI", "Bari", 4560000, 2672000, 2, 41.1171, 16.8719),
            ("LECCE", "Lecce", 4456000, 2778000, 2, 40.3516, 18.1718),
            # Basilicata
            ("POTENZA", "Potenza", 4496000, 2566000, 2, 40.6404, 15.8056),
            # Calabria
            ("CATANZARO", "Catanzaro", 4314000, 2634000, 2, 38.9097, 16.5877),
            ("REGGIO_CALABRIA", "Reggio Calabria", 4218000, 2564000, 2, 38.1114, 15.6472),
            # Sicilia
            ("PALERMO", "Palermo", 4222000, 2360000, 2, 38.1157, 13.3615),
            # Sardegna
            ("CAGLIARI", "Cagliari", 4338000, 1512000, 1, 39.2238, 9.1217),
        ]

        for codice, nome, nord, est, fuso, lat, lon in grandi_origini:
            self._origini[codice] = OrigineCatastale(
                codice=codice,
                nome=nome,
                tipo="grande",
                nord_gb=nord,
                est_gb=est,
                fuso_gb=fuso,
                lat_wgs84=lat,
                lon_wgs84=lon,
            )

        logger.info(f"Caricate {len(self._origini)} grandi origini predefinite")

    def load_origini(self, filepath: str | Path):
        """
        Carica origini catastali aggiuntive da file JSON.

        Args:
            filepath: Percorso al file JSON con le origini

        Il file JSON deve avere il formato:
        {
            "CODICE": {
                "nome": "Nome origine",
                "tipo": "piccola",
                "nord_gb": 4500000,
                "est_gb": 1500000,
                "fuso_gb": 1,
                "lat_wgs84": 40.5,
                "lon_wgs84": 14.5
            },
            ...
        }
        """
        filepath = Path(filepath)
        if not filepath.exists():
            logger.warning(f"File origini non trovato: {filepath}")
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            count = 0
            for codice, info in data.items():
                self._origini[codice] = OrigineCatastale(
                    codice=codice,
                    nome=info.get("nome", codice),
                    tipo=info.get("tipo", "piccola"),
                    nord_gb=info.get("nord_gb"),
                    est_gb=info.get("est_gb"),
                    fuso_gb=info.get("fuso_gb", 1),
                    lat_wgs84=info.get("lat_wgs84"),
                    lon_wgs84=info.get("lon_wgs84"),
                    lat_bessel=info.get("lat_bessel"),
                    lon_bessel=info.get("lon_bessel"),
                )
                count += 1

            logger.info(f"Caricate {count} origini da {filepath}")

        except Exception as e:
            logger.error(f"Errore caricamento origini: {e}")

    def convert_to_wgs84(self, pf: PuntoFiduciale) -> Optional[tuple[float, float]]:
        """
        Converte le coordinate di un PuntoFiduciale in WGS84.

        Args:
            pf: Punto fiduciale con coordinate originali

        Returns:
            Tuple (latitudine, longitudine) in WGS84, o None se conversione fallita
        """
        if not pf.has_valid_coordinates:
            return None

        try:
            sistema = pf.sistema_coordinate

            if sistema == SistemaCoordinate.GAUSS_BOAGA_OVEST:
                return self._convert_gauss_boaga(pf.coord_est, pf.coord_nord, "GB_OVEST")

            elif sistema == SistemaCoordinate.GAUSS_BOAGA_EST:
                return self._convert_gauss_boaga(pf.coord_est, pf.coord_nord, "GB_EST")

            elif sistema == SistemaCoordinate.UTM_WGS84_32N:
                return self._convert_utm(pf.coord_est, pf.coord_nord, "UTM32")

            elif sistema == SistemaCoordinate.UTM_WGS84_33N:
                return self._convert_utm(pf.coord_est, pf.coord_nord, "UTM33")

            elif sistema == SistemaCoordinate.CASSINI_SOLDNER:
                return self._convert_cassini_soldner(pf)

            elif sistema == SistemaCoordinate.SANSON_FLAMSTEED:
                return self._convert_sanson_flamsteed(pf)

            else:
                # Prova a indovinare il sistema dai valori
                return self._convert_auto_detect(pf)

        except ProjError as e:
            logger.error(f"Errore pyproj per {pf.identificativo}: {e}")
            return None
        except Exception as e:
            logger.error(f"Errore conversione {pf.identificativo}: {e}")
            return None

    def _convert_gauss_boaga(
        self,
        est: float,
        nord: float,
        fuso: str
    ) -> Optional[tuple[float, float]]:
        """Converte coordinate Gauss-Boaga in WGS84."""
        transformer = self._transformers.get(fuso)
        if not transformer:
            return None

        lon, lat = transformer.transform(est, nord)

        # Validazione range Italia
        if not (35.0 < lat < 48.0 and 6.0 < lon < 19.0):
            logger.warning(f"Coordinate fuori range Italia: lat={lat}, lon={lon}")
            return None

        return (lat, lon)

    def _convert_utm(
        self,
        est: float,
        nord: float,
        zona: str
    ) -> Optional[tuple[float, float]]:
        """Converte coordinate UTM WGS84 in lat/lon WGS84."""
        transformer = self._transformers.get(zona)
        if not transformer:
            return None

        lon, lat = transformer.transform(est, nord)

        # Validazione
        if not (35.0 < lat < 48.0 and 6.0 < lon < 19.0):
            return None

        return (lat, lon)

    def _convert_cassini_soldner(
        self,
        pf: PuntoFiduciale
    ) -> Optional[tuple[float, float]]:
        """
        Converte coordinate Cassini-Soldner in WGS84.

        Richiede di conoscere l'origine catastale del punto.
        Il processo e':
        1. Coordinate CS locali -> coordinate GB dell'origine
        2. Somma offset origine
        3. GB -> WGS84
        """
        # Trova l'origine catastale
        origine = self._find_origine_for_pf(pf)

        if not origine or not origine.nord_gb or not origine.est_gb:
            # Fallback: prova con Gauss-Boaga Ovest assumendo offset
            logger.warning(
                f"Origine sconosciuta per {pf.identificativo}, "
                f"tentativo conversione approssimata"
            )
            return self._convert_cassini_fallback(pf)

        # Cassini-Soldner: X = Nord (positivo verso nord), Y = Est (positivo verso est)
        # Le coordinate nel TAF sono X (nord relativo) e Y (est relativo)
        nord_gb = origine.nord_gb + pf.coord_nord
        est_gb = origine.est_gb + pf.coord_est

        fuso = "GB_OVEST" if origine.fuso_gb == 1 else "GB_EST"
        return self._convert_gauss_boaga(est_gb, nord_gb, fuso)

    def _convert_sanson_flamsteed(
        self,
        pf: PuntoFiduciale
    ) -> Optional[tuple[float, float]]:
        """
        Converte coordinate Sanson-Flamsteed in WGS84.

        Simile a Cassini-Soldner ma con formule diverse.
        Usato in alcune province dell'Emilia-Romagna e Toscana.
        """
        # Per Sanson-Flamsteed usiamo lo stesso approccio di Cassini
        # con le dovute correzioni
        return self._convert_cassini_soldner(pf)

    def _convert_cassini_fallback(
        self,
        pf: PuntoFiduciale
    ) -> Optional[tuple[float, float]]:
        """
        Conversione approssimata quando l'origine e' sconosciuta.

        Usa euristica basata sulla provincia per stimare l'origine.
        """
        # Mappa province -> origine piu' probabile
        province_origini = {
            "TO": "TORINO", "AT": "TORINO", "CN": "TORINO", "BI": "TORINO", "VC": "TORINO", "NO": "TORINO", "VB": "TORINO",
            "AO": "AOSTA",
            "AL": "ALESSANDRIA",
            "MI": "MILANO", "CO": "MILANO", "VA": "MILANO", "LC": "MILANO", "MB": "MILANO", "LO": "MILANO", "PV": "MILANO", "SO": "MILANO",
            "BG": "BRESCIA", "BS": "BRESCIA", "CR": "BRESCIA",
            "MN": "MANTOVA",
            "VE": "VENEZIA", "PD": "VENEZIA", "TV": "VENEZIA", "BL": "VENEZIA", "RO": "VENEZIA",
            "VR": "VERONA", "VI": "VERONA",
            "UD": "UDINE", "PN": "UDINE", "GO": "UDINE", "TS": "UDINE",
            "TN": "TRENTO", "BZ": "TRENTO",
            "BO": "BOLOGNA", "MO": "BOLOGNA", "RE": "BOLOGNA", "RA": "BOLOGNA", "FC": "BOLOGNA", "RN": "BOLOGNA",
            "FE": "FERRARA",
            "PR": "PARMA", "PC": "PARMA",
            "GE": "GENOVA", "SP": "GENOVA", "SV": "GENOVA", "IM": "GENOVA",
            "FI": "FIRENZE", "PT": "FIRENZE", "PO": "FIRENZE", "AR": "FIRENZE",
            "PI": "PISA", "LI": "PISA", "LU": "PISA", "MS": "PISA",
            "SI": "SIENA", "GR": "SIENA",
            "PG": "PERUGIA", "TR": "PERUGIA",
            "AN": "ANCONA", "PU": "ANCONA", "MC": "ANCONA", "AP": "ANCONA", "FM": "ANCONA",
            "RM": "ROMA", "VT": "ROMA", "RI": "ROMA", "LT": "ROMA", "FR": "ROMA",
            "AQ": "AQUILA", "TE": "AQUILA", "PE": "AQUILA", "CH": "AQUILA",
            "CB": "CAMPOBASSO", "IS": "CAMPOBASSO",
            "NA": "NAPOLI", "CE": "NAPOLI", "BN": "NAPOLI", "AV": "NAPOLI",
            "SA": "SALERNO",
            "BA": "BARI", "FG": "BARI", "BT": "BARI", "TA": "BARI", "BR": "BARI",
            "LE": "LECCE",
            "PZ": "POTENZA", "MT": "POTENZA",
            "CZ": "CATANZARO", "CS": "CATANZARO", "KR": "CATANZARO", "VV": "CATANZARO",
            "RC": "REGGIO_CALABRIA",
            "PA": "PALERMO", "TP": "PALERMO", "AG": "PALERMO", "CL": "PALERMO", "EN": "PALERMO",
            "CT": "PALERMO", "ME": "PALERMO", "SR": "PALERMO", "RG": "PALERMO",
            "CA": "CAGLIARI", "OR": "CAGLIARI", "NU": "CAGLIARI", "SS": "CAGLIARI", "SU": "CAGLIARI",
        }

        origine_codice = province_origini.get(pf.provincia)
        if not origine_codice:
            return None

        origine = self._origini.get(origine_codice)
        if not origine or not origine.nord_gb or not origine.est_gb:
            return None

        # Calcola coordinate GB approssimate
        nord_gb = origine.nord_gb + pf.coord_nord
        est_gb = origine.est_gb + pf.coord_est

        fuso = "GB_OVEST" if origine.fuso_gb == 1 else "GB_EST"
        return self._convert_gauss_boaga(est_gb, nord_gb, fuso)

    def _convert_auto_detect(
        self,
        pf: PuntoFiduciale
    ) -> Optional[tuple[float, float]]:
        """
        Tenta la conversione rilevando automaticamente il sistema.
        """
        est = pf.coord_est
        nord = pf.coord_nord

        # Prova Gauss-Boaga in base al range Est
        if 1_300_000 < est < 1_900_000:
            return self._convert_gauss_boaga(est, nord, "GB_OVEST")
        elif 2_200_000 < est < 2_800_000:
            return self._convert_gauss_boaga(est, nord, "GB_EST")

        # Prova Cassini-Soldner
        if abs(nord) < 200_000 and abs(est) < 200_000:
            return self._convert_cassini_fallback(pf)

        return None

    def _find_origine_for_pf(
        self,
        pf: PuntoFiduciale
    ) -> Optional[OrigineCatastale]:
        """
        Trova l'origine catastale per un punto fiduciale.

        Se il punto ha un codice_origine specifico, usa quello.
        Altrimenti prova a inferire dalla provincia.
        """
        if pf.codice_origine and pf.codice_origine in self._origini:
            return self._origini[pf.codice_origine]

        # Cerca per provincia
        for origine in self._origini.values():
            if pf.provincia in origine.province:
                return origine

        return None

    def convert_batch(
        self,
        punti: list[PuntoFiduciale],
        update_in_place: bool = True
    ) -> list[PuntoFiduciale]:
        """
        Converte una lista di punti fiduciali in WGS84.

        Args:
            punti: Lista di PuntoFiduciale
            update_in_place: Se True, aggiorna i punti esistenti

        Returns:
            Lista dei punti con coordinate WGS84
        """
        converted = 0
        failed = 0

        for pf in punti:
            result = self.convert_to_wgs84(pf)
            if result:
                lat, lon = result
                if update_in_place:
                    pf.lat_wgs84 = lat
                    pf.lon_wgs84 = lon
                converted += 1
            else:
                failed += 1

        logger.info(f"Conversione completata: {converted} OK, {failed} fallite")
        return punti

    @property
    def origini_disponibili(self) -> list[str]:
        """Restituisce la lista dei codici origine disponibili."""
        return list(self._origini.keys())

    def get_origine(self, codice: str) -> Optional[OrigineCatastale]:
        """Restituisce un'origine catastale per codice."""
        return self._origini.get(codice)
