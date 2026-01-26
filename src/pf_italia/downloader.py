"""
Downloader per i file TAF dall'Agenzia delle Entrate.

I file TAF sono disponibili sulle pagine degli uffici provinciali - Territorio.
Questo modulo gestisce il download automatico di tutti i 107 file TAF provinciali.
"""

import logging
import re
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

logger = logging.getLogger(__name__)


# Configurazione province italiane
# Formato: (sigla, nome, codice_ufficio)
PROVINCE_ITALIANE = [
    # Piemonte
    ("TO", "Torino", "KH5"),
    ("VC", "Vercelli", "KH6"),
    ("NO", "Novara", "KH2"),
    ("CN", "Cuneo", "KL4"),
    ("AT", "Asti", "KH7"),
    ("AL", "Alessandria", "KH1"),
    ("BI", "Biella", "KL2"),
    ("VB", "Verbano-Cusio-Ossola", "KL3"),
    # Valle d'Aosta
    ("AO", "Aosta", "KL1"),
    # Lombardia
    ("VA", "Varese", "KI5"),
    ("CO", "Como", "KI2"),
    ("SO", "Sondrio", "KI4"),
    ("MI", "Milano", "KH9"),
    ("BG", "Bergamo", "KI1"),
    ("BS", "Brescia", "KI6"),
    ("PV", "Pavia", "KH3"),
    ("CR", "Cremona", "KI3"),
    ("MN", "Mantova", "KI7"),
    ("LC", "Lecco", "KI8"),
    ("LO", "Lodi", "KI9"),
    ("MB", "Monza e Brianza", "KY1"),
    # Trentino-Alto Adige (gestione speciale)
    ("BZ", "Bolzano", None),  # Gestito da Provincia autonoma
    ("TN", "Trento", None),   # Gestito da Provincia autonoma
    # Veneto
    ("VR", "Verona", "KN5"),
    ("VI", "Vicenza", "KN6"),
    ("BL", "Belluno", "KN2"),
    ("TV", "Treviso", "KN4"),
    ("VE", "Venezia", "KM7"),
    ("PD", "Padova", "KN1"),
    ("RO", "Rovigo", "KN3"),
    # Friuli-Venezia Giulia
    ("UD", "Udine", "KP3"),
    ("GO", "Gorizia", "KP1"),
    ("TS", "Trieste", "KP2"),
    ("PN", "Pordenone", "KP4"),
    # Liguria
    ("IM", "Imperia", "KL6"),
    ("SV", "Savona", "KL8"),
    ("GE", "Genova", "KL5"),
    ("SP", "La Spezia", "KL7"),
    # Emilia-Romagna
    ("PC", "Piacenza", "KM3"),
    ("PR", "Parma", "KM2"),
    ("RE", "Reggio Emilia", "KM4"),
    ("MO", "Modena", "KM1"),
    ("BO", "Bologna", "KL9"),
    ("FE", "Ferrara", "KM5"),
    ("RA", "Ravenna", "KM6"),
    ("FC", "Forli-Cesena", "KM8"),
    ("RN", "Rimini", "KM9"),
    # Toscana
    ("MS", "Massa-Carrara", "KN9"),
    ("LU", "Lucca", "KN8"),
    ("PT", "Pistoia", "KO2"),
    ("FI", "Firenze", "KJ7"),
    ("LI", "Livorno", "KO1"),
    ("PI", "Pisa", "KO3"),
    ("AR", "Arezzo", "KJ6"),
    ("SI", "Siena", "KO4"),
    ("GR", "Grosseto", "KO5"),
    ("PO", "Prato", "KO6"),
    # Umbria
    ("PG", "Perugia", "KJ8"),
    ("TR", "Terni", "KJ9"),
    # Marche
    ("PU", "Pesaro e Urbino", "KK2"),
    ("AN", "Ancona", "KK1"),
    ("MC", "Macerata", "KK3"),
    ("AP", "Ascoli Piceno", "KK4"),
    ("FM", "Fermo", "KZ1"),
    # Lazio
    ("VT", "Viterbo", "KA5"),
    ("RI", "Rieti", "KA4"),
    ("RM", "Roma", "KA1"),
    ("LT", "Latina", "KA2"),
    ("FR", "Frosinone", "KA3"),
    # Abruzzo
    ("AQ", "L'Aquila", "KB1"),
    ("TE", "Teramo", "KB4"),
    ("PE", "Pescara", "KB2"),
    ("CH", "Chieti", "KB3"),
    # Molise
    ("CB", "Campobasso", "KC1"),
    ("IS", "Isernia", "KC2"),
    # Campania
    ("CE", "Caserta", "KD2"),
    ("BN", "Benevento", "KD1"),
    ("NA", "Napoli", "KD3"),
    ("AV", "Avellino", "KH8"),
    ("SA", "Salerno", "KD4"),
    # Puglia
    ("FG", "Foggia", "KE2"),
    ("BA", "Bari", "KE1"),
    ("TA", "Taranto", "KE4"),
    ("BR", "Brindisi", "KE5"),
    ("LE", "Lecce", "KE3"),
    ("BT", "Barletta-Andria-Trani", "KZ2"),
    # Basilicata
    ("PZ", "Potenza", "KF1"),
    ("MT", "Matera", "KF2"),
    # Calabria
    ("CS", "Cosenza", "KD5"),
    ("CZ", "Catanzaro", "KD6"),
    ("RC", "Reggio Calabria", "KD7"),
    ("KR", "Crotone", "KD8"),
    ("VV", "Vibo Valentia", "KD9"),
    # Sicilia
    ("TP", "Trapani", "KG8"),
    ("PA", "Palermo", "KG4"),
    ("ME", "Messina", "KG3"),
    ("AG", "Agrigento", "KG1"),
    ("CL", "Caltanissetta", "KG2"),
    ("EN", "Enna", "KG9"),
    ("CT", "Catania", "KG5"),
    ("RG", "Ragusa", "KG6"),
    ("SR", "Siracusa", "KG7"),
    # Sardegna
    ("SS", "Sassari", "KQ4"),
    ("NU", "Nuoro", "KQ2"),
    ("CA", "Cagliari", "KQ1"),
    ("OR", "Oristano", "KQ3"),
    ("SU", "Sud Sardegna", "KZ3"),
]


class TafDownloader:
    """
    Downloader per i file TAF dall'Agenzia delle Entrate.

    Esempio di utilizzo:
        downloader = TafDownloader(output_dir="data/taf")
        downloader.download_all()
    """

    # URL base per le pagine degli uffici provinciali
    BASE_URL = "https://www.agenziaentrate.gov.it"
    SEARCH_URL = f"{BASE_URL}/portale/it/web/guest/uffici"

    # User agent per le richieste
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Fonte alternativa: fiduciali.altervista.org
    ALTERVISTA_URL = "http://fiduciali.altervista.org"

    def __init__(
        self,
        output_dir: str | Path = "data/taf",
        use_altervista: bool = True,
        timeout: int = 60,
        retry_count: int = 3,
        retry_delay: float = 2.0,
    ):
        """
        Inizializza il downloader.

        Args:
            output_dir: Directory dove salvare i file TAF
            use_altervista: Se True, usa fiduciali.altervista.org come fonte (consigliato)
            timeout: Timeout per le richieste HTTP
            retry_count: Numero di tentativi in caso di errore
            retry_delay: Delay tra i tentativi (in secondi)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.use_altervista = use_altervista
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        })

        # Statistiche download
        self.stats = {
            "downloaded": 0,
            "failed": 0,
            "skipped": 0,
        }

    def download_all(
        self,
        province: Optional[list[str]] = None,
        force: bool = False,
        progress: bool = True,
    ) -> dict:
        """
        Scarica tutti i file TAF.

        Args:
            province: Lista sigle province da scaricare (None = tutte)
            force: Se True, riscarica anche file esistenti
            progress: Se True, mostra barra progresso

        Returns:
            Dizionario con statistiche download
        """
        self.stats = {"downloaded": 0, "failed": 0, "skipped": 0}

        # Filtra province se specificato
        province_list = PROVINCE_ITALIANE
        if province:
            province_upper = [p.upper() for p in province]
            province_list = [p for p in PROVINCE_ITALIANE if p[0] in province_upper]

        logger.info(f"Avvio download TAF per {len(province_list)} province")

        iterator = tqdm(province_list, desc="Download TAF") if progress else province_list

        for sigla, nome, codice in iterator:
            if progress:
                iterator.set_description(f"Download {sigla}")

            try:
                if self._download_provincia(sigla, nome, codice, force):
                    self.stats["downloaded"] += 1
                else:
                    self.stats["skipped"] += 1
            except Exception as e:
                logger.error(f"Errore download {sigla}: {e}")
                self.stats["failed"] += 1

            # Delay tra i download per non sovraccaricare il server
            time.sleep(0.5)

        logger.info(
            f"Download completato: {self.stats['downloaded']} scaricati, "
            f"{self.stats['skipped']} saltati, {self.stats['failed']} falliti"
        )

        return self.stats

    def _download_provincia(
        self,
        sigla: str,
        nome: str,
        codice_ufficio: Optional[str],
        force: bool
    ) -> bool:
        """
        Scarica il file TAF per una singola provincia.

        Returns:
            True se scaricato, False se saltato
        """
        output_file = self.output_dir / f"{sigla}.TAF"

        # Controlla se esiste gia'
        if output_file.exists() and not force:
            logger.debug(f"File {sigla}.TAF gia' presente, skip")
            return False

        # Gestione province speciali (Trento, Bolzano)
        if codice_ufficio is None:
            logger.warning(f"Provincia {sigla} gestita separatamente, skip")
            return False

        # Tenta download
        if self.use_altervista:
            success = self._download_from_altervista(sigla, output_file)
        else:
            success = self._download_from_ade(sigla, nome, codice_ufficio, output_file)

        return success

    def _download_from_altervista(self, sigla: str, output_file: Path) -> bool:
        """
        Scarica il TAF da fiduciali.altervista.org.

        Questo sito offre i TAF gia' estratti e organizzati per provincia.
        """
        # URL pattern per il download diretto
        # Il sito usa un form POST, quindi dobbiamo simulare la richiesta
        download_url = f"{self.ALTERVISTA_URL}/download_taf.php"

        for attempt in range(self.retry_count):
            try:
                # Prima richiesta per ottenere eventuali token
                response = self.session.post(
                    download_url,
                    data={"provincia": sigla},
                    timeout=self.timeout,
                    allow_redirects=True,
                )

                if response.status_code == 200:
                    content = response.content

                    # Verifica se e' un file ZIP
                    if content[:2] == b"PK":
                        # Estrai dal ZIP
                        with zipfile.ZipFile(BytesIO(content)) as zf:
                            for name in zf.namelist():
                                if name.upper().endswith(".TAF"):
                                    with zf.open(name) as f:
                                        output_file.write_bytes(f.read())
                                    logger.info(f"Scaricato {sigla}.TAF da Altervista (ZIP)")
                                    return True
                    elif len(content) > 100:
                        # File TAF diretto
                        output_file.write_bytes(content)
                        logger.info(f"Scaricato {sigla}.TAF da Altervista")
                        return True

                logger.warning(f"Risposta non valida per {sigla}, tentativo {attempt + 1}")

            except requests.RequestException as e:
                logger.warning(f"Errore download {sigla}: {e}, tentativo {attempt + 1}")

            if attempt < self.retry_count - 1:
                time.sleep(self.retry_delay * (attempt + 1))

        # Fallback ad AdE
        logger.info(f"Fallback ad AdE per {sigla}")
        return self._download_from_ade_direct(sigla, output_file)

    def _download_from_ade(
        self,
        sigla: str,
        nome: str,
        codice_ufficio: str,
        output_file: Path
    ) -> bool:
        """
        Scarica il TAF dal sito dell'Agenzia delle Entrate.

        Richiede navigazione e scraping della pagina provinciale.
        """
        return self._download_from_ade_direct(sigla, output_file)

    def _download_from_ade_direct(self, sigla: str, output_file: Path) -> bool:
        """
        Tenta download diretto da URL pattern AdE.

        Pattern osservato: i file TAF sono spesso disponibili con URL predefiniti.
        """
        # Pattern URL osservati
        url_patterns = [
            f"https://www.agenziaentrate.gov.it/portale/documents/{sigla}.TAF",
            f"https://www.agenziaentrate.gov.it/portale/documents/{sigla}.taf",
            f"https://www.agenziaentrate.gov.it/portale/documents/{sigla.lower()}.TAF",
        ]

        for url in url_patterns:
            for attempt in range(self.retry_count):
                try:
                    response = self.session.get(url, timeout=self.timeout)
                    if response.status_code == 200 and len(response.content) > 100:
                        # Verifica contenuto
                        content = response.content
                        if self._validate_taf_content(content):
                            output_file.write_bytes(content)
                            logger.info(f"Scaricato {sigla}.TAF da AdE")
                            return True

                except requests.RequestException:
                    pass

                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay)

        logger.error(f"Impossibile scaricare TAF per {sigla}")
        return False

    def _validate_taf_content(self, content: bytes) -> bool:
        """Verifica che il contenuto sia un file TAF valido."""
        try:
            # Decodifica e verifica struttura
            text = content.decode("latin-1", errors="ignore")
            lines = text.split("\n")

            # Un TAF valido ha righe di almeno 100 caratteri
            valid_lines = sum(1 for line in lines if len(line) >= 100)
            return valid_lines > 10

        except Exception:
            return False

    def get_downloaded_files(self) -> list[Path]:
        """Restituisce la lista dei file TAF scaricati."""
        return sorted(self.output_dir.glob("*.TAF")) + sorted(self.output_dir.glob("*.taf"))

    def get_missing_provinces(self) -> list[str]:
        """Restituisce la lista delle province mancanti."""
        downloaded = {f.stem.upper() for f in self.get_downloaded_files()}
        all_provinces = {p[0] for p in PROVINCE_ITALIANE}
        return sorted(all_provinces - downloaded)


def download_taf_provincia(
    sigla: str,
    output_dir: str | Path = "data/taf"
) -> Optional[Path]:
    """
    Funzione di convenienza per scaricare il TAF di una singola provincia.

    Args:
        sigla: Sigla provincia (es. "RM")
        output_dir: Directory output

    Returns:
        Path del file scaricato o None se fallito
    """
    downloader = TafDownloader(output_dir=output_dir)
    result = downloader.download_all(province=[sigla])

    if result["downloaded"] > 0:
        return Path(output_dir) / f"{sigla.upper()}.TAF"
    return None
