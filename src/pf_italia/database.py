"""
Database spaziale per i Punti Fiduciali.

Utilizza SpatiaLite (SQLite con estensione spaziale) per:
- Archiviazione efficiente dei punti
- Query spaziali (ricerca per coordinata + buffer)
- Indici spaziali R-Tree
"""

import logging
import sqlite3
from pathlib import Path
from typing import Iterator, Optional

from .models import PuntoFiduciale, SistemaCoordinate

logger = logging.getLogger(__name__)


class PfDatabase:
    """
    Database spaziale per i Punti Fiduciali.

    Utilizza SQLite con estensione SpatiaLite per query spaziali efficienti.

    Esempio:
        db = PfDatabase("data/pf_italia.db")
        db.init_schema()
        db.insert_punti(punti_convertiti)
        risultati = db.query_by_location(41.9, 12.5, buffer_m=1000)
    """

    def __init__(self, db_path: str | Path = "data/pf_italia.db"):
        """
        Inizializza il database.

        Args:
            db_path: Percorso al file database SQLite
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: Optional[sqlite3.Connection] = None
        self._spatialite_loaded = False

    def connect(self) -> sqlite3.Connection:
        """Apre la connessione al database."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._load_spatialite()

        return self._conn

    def _load_spatialite(self):
        """Carica l'estensione SpatiaLite."""
        if self._spatialite_loaded:
            return

        conn = self._conn
        conn.enable_load_extension(True)

        # Prova a caricare SpatiaLite da vari percorsi
        spatialite_paths = [
            "mod_spatialite",
            "mod_spatialite.so",
            "/usr/lib/x86_64-linux-gnu/mod_spatialite.so",
            "/usr/lib/mod_spatialite.so",
            "/usr/local/lib/mod_spatialite.so",
        ]

        for path in spatialite_paths:
            try:
                conn.load_extension(path)
                self._spatialite_loaded = True
                logger.info(f"SpatiaLite caricato da: {path}")
                return
            except sqlite3.OperationalError:
                continue

        logger.warning(
            "SpatiaLite non disponibile. "
            "Le query spaziali useranno calcoli approssimati."
        )

    def close(self):
        """Chiude la connessione."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def init_schema(self):
        """Inizializza lo schema del database."""
        conn = self.connect()
        cursor = conn.cursor()

        # Inizializza metadati SpatiaLite se disponibile
        if self._spatialite_loaded:
            try:
                cursor.execute("SELECT InitSpatialMetaData(1)")
            except sqlite3.OperationalError:
                pass  # Gia' inizializzato

        # Tabella principale punti fiduciali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS punti_fiduciali (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identificativo TEXT UNIQUE NOT NULL,
                provincia TEXT NOT NULL,
                codice_comune TEXT NOT NULL,
                sezione TEXT,
                foglio TEXT NOT NULL,
                allegato TEXT DEFAULT '0',
                numero TEXT NOT NULL,
                coord_nord REAL,
                coord_est REAL,
                quota REAL,
                sistema_coordinate TEXT,
                codice_origine TEXT,
                lat_wgs84 REAL,
                lon_wgs84 REAL,
                attendibilita_plan TEXT,
                attendibilita_altim TEXT,
                descrizione_plan TEXT,
                descrizione_altim TEXT,
                ha_monografia INTEGER DEFAULT 0,
                data_monografia TEXT,
                causale_aggiornamento TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indici per ricerche comuni
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pf_provincia
            ON punti_fiduciali(provincia)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pf_comune
            ON punti_fiduciali(codice_comune)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pf_foglio
            ON punti_fiduciali(provincia, codice_comune, foglio)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pf_coords
            ON punti_fiduciali(lat_wgs84, lon_wgs84)
        """)

        # Colonna geometria se SpatiaLite disponibile
        if self._spatialite_loaded:
            try:
                cursor.execute("""
                    SELECT AddGeometryColumn('punti_fiduciali', 'geom', 4326, 'POINT', 'XY')
                """)
                cursor.execute("""
                    SELECT CreateSpatialIndex('punti_fiduciali', 'geom')
                """)
            except sqlite3.OperationalError:
                pass  # Colonna gia' esistente

        # Tabella origini catastali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS origini_catastali (
                codice TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                tipo TEXT DEFAULT 'piccola',
                lat_bessel REAL,
                lon_bessel REAL,
                nord_gb REAL,
                est_gb REAL,
                fuso_gb INTEGER DEFAULT 1,
                lat_wgs84 REAL,
                lon_wgs84 REAL,
                province TEXT
            )
        """)

        # Tabella statistiche per provincia
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS statistiche_provincia (
                provincia TEXT PRIMARY KEY,
                totale_pf INTEGER DEFAULT 0,
                pf_con_wgs84 INTEGER DEFAULT 0,
                pf_con_monografia INTEGER DEFAULT 0,
                ultimo_aggiornamento TIMESTAMP
            )
        """)

        conn.commit()
        logger.info("Schema database inizializzato")

    def insert_punto(self, pf: PuntoFiduciale) -> bool:
        """
        Inserisce un singolo punto fiduciale.

        Args:
            pf: Punto fiduciale da inserire

        Returns:
            True se inserito, False se errore o duplicato
        """
        conn = self.connect()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO punti_fiduciali (
                    identificativo, provincia, codice_comune, sezione,
                    foglio, allegato, numero, coord_nord, coord_est, quota,
                    sistema_coordinate, codice_origine, lat_wgs84, lon_wgs84,
                    attendibilita_plan, attendibilita_altim,
                    descrizione_plan, descrizione_altim,
                    ha_monografia, data_monografia, causale_aggiornamento,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                pf.identificativo,
                pf.provincia,
                pf.codice_comune,
                pf.sezione,
                pf.foglio,
                pf.allegato,
                pf.numero,
                pf.coord_nord,
                pf.coord_est,
                pf.quota if pf.has_valid_quota else None,
                pf.sistema_coordinate.value,
                pf.codice_origine,
                pf.lat_wgs84,
                pf.lon_wgs84,
                pf.attendibilita_plan.value,
                pf.attendibilita_altim.value,
                pf.descrizione_plan,
                pf.descrizione_altim,
                1 if pf.ha_monografia else 0,
                pf.data_monografia,
                pf.causale_aggiornamento,
            ))

            # Aggiorna geometria se disponibile
            if self._spatialite_loaded and pf.has_wgs84_coordinates:
                cursor.execute("""
                    UPDATE punti_fiduciali
                    SET geom = MakePoint(?, ?, 4326)
                    WHERE identificativo = ?
                """, (pf.lon_wgs84, pf.lat_wgs84, pf.identificativo))

            conn.commit()
            return True

        except sqlite3.Error as e:
            logger.error(f"Errore inserimento {pf.identificativo}: {e}")
            return False

    def insert_punti(
        self,
        punti: Iterator[PuntoFiduciale],
        batch_size: int = 1000
    ) -> tuple[int, int]:
        """
        Inserisce multipli punti fiduciali in batch.

        Args:
            punti: Iteratore di punti fiduciali
            batch_size: Dimensione batch per commit

        Returns:
            Tuple (inseriti, errori)
        """
        conn = self.connect()
        cursor = conn.cursor()

        inserted = 0
        errors = 0
        batch = []

        for pf in punti:
            batch.append(pf)

            if len(batch) >= batch_size:
                ins, err = self._insert_batch(cursor, batch)
                inserted += ins
                errors += err
                batch = []
                conn.commit()

        # Ultimo batch
        if batch:
            ins, err = self._insert_batch(cursor, batch)
            inserted += ins
            errors += err
            conn.commit()

        logger.info(f"Inseriti {inserted} punti, {errors} errori")
        return inserted, errors

    def _insert_batch(
        self,
        cursor: sqlite3.Cursor,
        batch: list[PuntoFiduciale]
    ) -> tuple[int, int]:
        """Inserisce un batch di punti."""
        inserted = 0
        errors = 0

        for pf in batch:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO punti_fiduciali (
                        identificativo, provincia, codice_comune, sezione,
                        foglio, allegato, numero, coord_nord, coord_est, quota,
                        sistema_coordinate, codice_origine, lat_wgs84, lon_wgs84,
                        attendibilita_plan, attendibilita_altim,
                        descrizione_plan, descrizione_altim,
                        ha_monografia, data_monografia, causale_aggiornamento,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    pf.identificativo,
                    pf.provincia,
                    pf.codice_comune,
                    pf.sezione,
                    pf.foglio,
                    pf.allegato,
                    pf.numero,
                    pf.coord_nord,
                    pf.coord_est,
                    pf.quota if pf.has_valid_quota else None,
                    pf.sistema_coordinate.value,
                    pf.codice_origine,
                    pf.lat_wgs84,
                    pf.lon_wgs84,
                    pf.attendibilita_plan.value,
                    pf.attendibilita_altim.value,
                    pf.descrizione_plan,
                    pf.descrizione_altim,
                    1 if pf.ha_monografia else 0,
                    pf.data_monografia,
                    pf.causale_aggiornamento,
                ))
                inserted += 1

            except sqlite3.Error as e:
                errors += 1
                logger.debug(f"Errore batch insert: {e}")

        # Aggiorna geometrie
        if self._spatialite_loaded:
            cursor.execute("""
                UPDATE punti_fiduciali
                SET geom = MakePoint(lon_wgs84, lat_wgs84, 4326)
                WHERE geom IS NULL AND lat_wgs84 IS NOT NULL AND lon_wgs84 IS NOT NULL
            """)

        return inserted, errors

    def query_by_location(
        self,
        lat: float,
        lon: float,
        buffer_m: float = 1000,
        limit: int = 100
    ) -> list[dict]:
        """
        Cerca punti fiduciali entro un buffer da una coordinata.

        Args:
            lat: Latitudine WGS84
            lon: Longitudine WGS84
            buffer_m: Raggio di ricerca in metri
            limit: Numero massimo risultati

        Returns:
            Lista di dizionari con i punti trovati
        """
        conn = self.connect()
        cursor = conn.cursor()

        if self._spatialite_loaded:
            # Query spaziale con SpatiaLite
            cursor.execute("""
                SELECT
                    identificativo, provincia, codice_comune, foglio, numero,
                    lat_wgs84, lon_wgs84, quota, attendibilita_plan, ha_monografia,
                    descrizione_plan,
                    ST_Distance(geom, MakePoint(?, ?, 4326), 1) as distanza_m
                FROM punti_fiduciali
                WHERE geom IS NOT NULL
                AND ST_Distance(geom, MakePoint(?, ?, 4326), 1) <= ?
                ORDER BY distanza_m
                LIMIT ?
            """, (lon, lat, lon, lat, buffer_m, limit))

        else:
            # Query approssimata con formula di Haversine semplificata
            # 1 grado lat ~ 111 km, 1 grado lon ~ 111 * cos(lat) km
            buffer_deg = buffer_m / 111000.0  # Approssimazione

            cursor.execute("""
                SELECT
                    identificativo, provincia, codice_comune, foglio, numero,
                    lat_wgs84, lon_wgs84, quota, attendibilita_plan, ha_monografia,
                    descrizione_plan
                FROM punti_fiduciali
                WHERE lat_wgs84 IS NOT NULL
                AND lat_wgs84 BETWEEN ? AND ?
                AND lon_wgs84 BETWEEN ? AND ?
                LIMIT ?
            """, (
                lat - buffer_deg,
                lat + buffer_deg,
                lon - buffer_deg,
                lon + buffer_deg,
                limit * 2  # Sovracampiona per compensare approssimazione
            ))

        results = []
        for row in cursor.fetchall():
            result = dict(row)

            # Calcola distanza se non fornita da SpatiaLite
            if "distanza_m" not in result and result.get("lat_wgs84"):
                result["distanza_m"] = self._haversine_distance(
                    lat, lon, result["lat_wgs84"], result["lon_wgs84"]
                )

            # Filtra per distanza effettiva
            if result.get("distanza_m", 0) <= buffer_m:
                results.append(result)

        # Ordina per distanza e limita
        results.sort(key=lambda x: x.get("distanza_m", 0))
        return results[:limit]

    def _haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """Calcola distanza in metri usando formula di Haversine."""
        from math import radians, sin, cos, sqrt, atan2

        R = 6371000  # Raggio Terra in metri

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c

    def query_by_foglio(
        self,
        provincia: str,
        codice_comune: str,
        foglio: str
    ) -> list[dict]:
        """
        Cerca tutti i PF di un foglio catastale.

        Args:
            provincia: Sigla provincia
            codice_comune: Codice catastale comune
            foglio: Numero foglio

        Returns:
            Lista di dizionari con i punti
        """
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM punti_fiduciali
            WHERE provincia = ?
            AND codice_comune = ?
            AND foglio = ?
            ORDER BY numero
        """, (provincia.upper(), codice_comune.upper(), foglio))

        return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> dict:
        """Restituisce statistiche del database."""
        conn = self.connect()
        cursor = conn.cursor()

        stats = {}

        # Totale punti
        cursor.execute("SELECT COUNT(*) FROM punti_fiduciali")
        stats["totale_pf"] = cursor.fetchone()[0]

        # Punti con WGS84
        cursor.execute(
            "SELECT COUNT(*) FROM punti_fiduciali WHERE lat_wgs84 IS NOT NULL"
        )
        stats["pf_con_wgs84"] = cursor.fetchone()[0]

        # Per provincia
        cursor.execute("""
            SELECT provincia, COUNT(*) as count
            FROM punti_fiduciali
            GROUP BY provincia
            ORDER BY count DESC
        """)
        stats["per_provincia"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Per sistema coordinate
        cursor.execute("""
            SELECT sistema_coordinate, COUNT(*) as count
            FROM punti_fiduciali
            GROUP BY sistema_coordinate
        """)
        stats["per_sistema"] = {row[0]: row[1] for row in cursor.fetchall()}

        return stats

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
