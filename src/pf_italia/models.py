"""
Modelli dati per i Punti Fiduciali.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class SistemaCoordinate(Enum):
    """Sistema di coordinate utilizzato nel file TAF."""
    GAUSS_BOAGA_OVEST = "GB_OVEST"  # EPSG:3003 - Fuso Ovest
    GAUSS_BOAGA_EST = "GB_EST"      # EPSG:3004 - Fuso Est
    CASSINI_SOLDNER = "CS"          # Sistema locale con origine catastale
    SANSON_FLAMSTEED = "SF"         # Usato in alcune province (Modena, Reggio Emilia, etc.)
    UTM_WGS84_32N = "UTM32"         # EPSG:32632
    UTM_WGS84_33N = "UTM33"         # EPSG:32633
    UNKNOWN = "UNKNOWN"


class AttendibilitaPlanimetrica(Enum):
    """Codici di attendibilita planimetrica del punto fiduciale."""
    OTTIMA = "01"           # Vertice trigonometrico o GPS con precisione < 0.10 m
    BUONA = "02"            # Punto ben definito, precisione 0.10-0.50 m
    SUFFICIENTE = "03"      # Precisione 0.50-1.00 m
    SCARSA = "04"           # Precisione > 1.00 m o non determinata
    NON_DISPONIBILE = "99"  # Dato non disponibile


class AttendibilitaAltimetrica(Enum):
    """Codici di attendibilita altimetrica del punto fiduciale."""
    OTTIMA = "01"           # Quota da livellazione geometrica, precisione < 0.05 m
    BUONA = "02"            # Quota GPS o trigonometrica, precisione 0.05-0.20 m
    SUFFICIENTE = "03"      # Precisione 0.20-1.00 m
    SCARSA = "04"           # Precisione > 1.00 m o convenzionale (9999)
    NON_DISPONIBILE = "99"  # Dato non disponibile


@dataclass
class PuntoFiduciale:
    """
    Rappresenta un singolo Punto Fiduciale catastale.

    Identificazione: PFxx/yyyz/CCCC dove:
    - xx: numero del punto fiduciale (01-99)
    - yyy: foglio catastale (001-999)
    - z: allegato (0 o A-Z)
    - CCCC: codice catastale del comune (es. H501 per Roma)
    """

    # Identificazione
    provincia: str                          # Sigla provincia (es. "RM")
    codice_comune: str                      # Codice catastale comune (es. "H501")
    sezione: str = ""                       # Sezione censuaria (opzionale)
    foglio: str = ""                        # Numero foglio (es. "001")
    allegato: str = "0"                     # Allegato foglio (0 o A-Z)
    numero: str = ""                        # Numero PF (es. "01")

    # Coordinate originali (dal file TAF)
    coord_nord: float = 0.0                 # N (GB) o X (CS) o Y (SF)
    coord_est: float = 0.0                  # E (GB) o Y (CS) o X (SF)
    quota: float = 9999.0                   # Quota s.l.m. in metri (9999 = non disponibile)

    # Sistema di coordinate originale
    sistema_coordinate: SistemaCoordinate = SistemaCoordinate.UNKNOWN
    codice_origine: Optional[str] = None    # Codice origine catastale (per Cassini-Soldner)

    # Coordinate convertite in WGS84
    lat_wgs84: Optional[float] = None       # Latitudine WGS84
    lon_wgs84: Optional[float] = None       # Longitudine WGS84

    # Attendibilita
    attendibilita_plan: AttendibilitaPlanimetrica = AttendibilitaPlanimetrica.NON_DISPONIBILE
    attendibilita_altim: AttendibilitaAltimetrica = AttendibilitaAltimetrica.NON_DISPONIBILE

    # Descrizione
    descrizione_plan: str = ""              # Descrizione riferimento planimetrico
    descrizione_altim: str = ""             # Descrizione riferimento altimetrico

    # Monografia
    ha_monografia: bool = False
    data_monografia: Optional[str] = None

    # Aggiornamento
    causale_aggiornamento: Optional[str] = None  # Protocollo atto aggiornamento

    @property
    def identificativo(self) -> str:
        """Restituisce l'identificativo completo del PF nel formato standard."""
        sez = self.sezione if self.sezione.strip() else ""
        return f"PF{self.numero:0>2}/{self.foglio:0>3}{self.allegato}/{self.codice_comune}{sez}"

    @property
    def identificativo_breve(self) -> str:
        """Restituisce l'identificativo breve del PF."""
        return f"PF{self.numero:0>2}/{self.foglio}"

    @property
    def has_valid_coordinates(self) -> bool:
        """Verifica se il punto ha coordinate valide."""
        return self.coord_nord != 0.0 and self.coord_est != 0.0

    @property
    def has_wgs84_coordinates(self) -> bool:
        """Verifica se il punto ha coordinate WGS84."""
        return self.lat_wgs84 is not None and self.lon_wgs84 is not None

    @property
    def has_valid_quota(self) -> bool:
        """Verifica se il punto ha una quota valida (non convenzionale)."""
        return self.quota != 9999.0 and self.quota != 0.0

    def to_dict(self) -> dict:
        """Converte il punto in dizionario."""
        return {
            "identificativo": self.identificativo,
            "provincia": self.provincia,
            "codice_comune": self.codice_comune,
            "sezione": self.sezione,
            "foglio": self.foglio,
            "allegato": self.allegato,
            "numero": self.numero,
            "coord_nord": self.coord_nord,
            "coord_est": self.coord_est,
            "quota": self.quota if self.has_valid_quota else None,
            "sistema_coordinate": self.sistema_coordinate.value,
            "codice_origine": self.codice_origine,
            "lat_wgs84": self.lat_wgs84,
            "lon_wgs84": self.lon_wgs84,
            "attendibilita_plan": self.attendibilita_plan.value,
            "attendibilita_altim": self.attendibilita_altim.value,
            "descrizione_plan": self.descrizione_plan,
            "descrizione_altim": self.descrizione_altim,
            "ha_monografia": self.ha_monografia,
        }

    def to_geojson_feature(self) -> Optional[dict]:
        """Converte il punto in GeoJSON Feature (richiede coordinate WGS84)."""
        if not self.has_wgs84_coordinates:
            return None

        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [self.lon_wgs84, self.lat_wgs84]
            },
            "properties": {
                "id": self.identificativo,
                "provincia": self.provincia,
                "comune": self.codice_comune,
                "foglio": self.foglio,
                "numero": self.numero,
                "quota": self.quota if self.has_valid_quota else None,
                "attendibilita_plan": self.attendibilita_plan.value,
                "ha_monografia": self.ha_monografia,
            }
        }


@dataclass
class OrigineCatastale:
    """
    Rappresenta un'origine catastale (centro di emanazione) per il sistema Cassini-Soldner.

    Esistono 31 grandi origini e 818 piccole origini che coprono tutto il territorio italiano.
    """

    codice: str                             # Codice univoco origine
    nome: str                               # Nome completo origine
    tipo: str = "piccola"                   # "grande" o "piccola"

    # Coordinate geografiche Bessel su Genova (per trasformazione)
    lat_bessel: Optional[float] = None      # Latitudine Bessel
    lon_bessel: Optional[float] = None      # Longitudine Bessel (da Genova)

    # Coordinate Gauss-Boaga dell'origine
    nord_gb: Optional[float] = None         # Coordinata Nord Gauss-Boaga
    est_gb: Optional[float] = None          # Coordinata Est Gauss-Boaga
    fuso_gb: int = 1                        # Fuso Gauss-Boaga (1=Ovest, 2=Est)

    # Coordinate WGS84 dell'origine
    lat_wgs84: Optional[float] = None
    lon_wgs84: Optional[float] = None

    # Grandi traslazioni (per alcune origini)
    trasl_x: float = 0.0
    trasl_y: float = 0.0

    # Province coperte da questa origine
    province: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Converte l'origine in dizionario."""
        return {
            "codice": self.codice,
            "nome": self.nome,
            "tipo": self.tipo,
            "lat_bessel": self.lat_bessel,
            "lon_bessel": self.lon_bessel,
            "nord_gb": self.nord_gb,
            "est_gb": self.est_gb,
            "fuso_gb": self.fuso_gb,
            "lat_wgs84": self.lat_wgs84,
            "lon_wgs84": self.lon_wgs84,
            "province": self.province,
        }
