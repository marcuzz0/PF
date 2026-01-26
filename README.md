# PF Italia - Punti Fiduciali Catastali in WGS84

Sistema automatico per scaricare i Punti Fiduciali catastali di tutta Italia e convertirli in coordinate WGS84.

## Caratteristiche

- **Download automatico** dei file TAF (Tabella Attuale Punti Fiduciali) da tutte le 107 province italiane
- **Parser TAF** per il formato ASCII a larghezza fissa dell'Agenzia delle Entrate
- **Conversione coordinate** da sistemi catastali italiani a WGS84:
  - Gauss-Boaga Ovest (EPSG:3003)
  - Gauss-Boaga Est (EPSG:3004)
  - Cassini-Soldner (con 31 grandi origini predefinite)
  - Sanson-Flamsteed
  - UTM WGS84 Zone 32N/33N
- **Database spaziale** con SpatiaLite per query efficienti
- **API semplice** per cercare punti fiduciali per coordinata + buffer
- **Output GeoJSON** per integrazione con QGIS e altri GIS

## Installazione

```bash
# Clone repository
git clone https://github.com/marcuzz0/PF.git
cd PF

# Crea virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Installa dipendenze
pip install -e .

# Opzionale: installa SpatiaLite per query spaziali avanzate
# Ubuntu/Debian:
sudo apt-get install libsqlite3-mod-spatialite
```

## Uso Rapido

### Pipeline completa

```bash
# Scarica, parsa, converti e importa tutti i TAF
python run_pipeline.py

# Solo alcune province
python run_pipeline.py --province RM MI TO

# Usa file TAF gia' scaricati
python run_pipeline.py --skip-download
```

### Comandi singoli

```bash
# Scarica file TAF
python -m pf_italia download
python -m pf_italia download --province RM MI

# Importa nel database
python -m pf_italia import

# Cerca punti per coordinata
python -m pf_italia query 41.9028 12.4964 --buffer 500

# Statistiche
python -m pf_italia stats
```

### API Python

```python
from pf_italia import query_pf, get_pf_geojson

# Cerca punti entro 1km dal Colosseo
risultati = query_pf(
    lat=41.8902,
    lon=12.4922,
    buffer_m=1000
)

for pf in risultati:
    print(f"{pf['identificativo']}: {pf['distanza_m']:.0f}m")

# Output GeoJSON
geojson = get_pf_geojson(41.8902, 12.4922, buffer_m=500)
```

## Struttura Progetto

```
PF/
├── src/pf_italia/
│   ├── __init__.py
│   ├── models.py           # Modelli dati (PuntoFiduciale, OrigineCatastale)
│   ├── taf_parser.py       # Parser file TAF
│   ├── coordinate_converter.py  # Conversione coordinate
│   ├── downloader.py       # Download TAF
│   ├── database.py         # Database SpatiaLite
│   ├── query.py            # API query
│   └── cli.py              # Command line interface
├── tests/
├── data/                   # Directory dati (gitignored)
│   ├── taf/               # File TAF scaricati
│   └── pf_italia.db       # Database
├── run_pipeline.py         # Script orchestrazione
├── pyproject.toml
└── README.md
```

## Formato TAF

Il file TAF (Tabella Attuale Punti Fiduciali) e' un file ASCII a larghezza fissa con un record per ogni punto fiduciale:

| Campo | Posizione | Descrizione |
|-------|-----------|-------------|
| Codice comune | 0-3 | Codice catastale (es. H501 = Roma) |
| Sezione | 4 | Sezione censuaria |
| Foglio | 6-9 | Numero foglio catastale |
| Allegato | 11 | Allegato (0 o A-Z) |
| Numero PF | 15-16 | Numero punto fiduciale |
| Descrizione | 30-99 | Descrizione riferimento planimetrico |
| Nord | 102-113 | Coordinata Nord/X |
| Est | 116-124 | Coordinata Est/Y |
| Quota | 128-134 | Quota s.l.m. (9999 = non disponibile) |

## Sistemi di Coordinate

I file TAF possono contenere coordinate in diversi sistemi:

- **Gauss-Boaga**: Sistema nazionale, due fusi (Ovest/Est)
  - EPSG:3003 (Fuso Ovest): Est 1.400.000 - 1.800.000
  - EPSG:3004 (Fuso Est): Est 2.300.000 - 2.700.000

- **Cassini-Soldner**: Sistema storico policentrico
  - 31 grandi origini + 818 piccole origini
  - Coordinate relative all'origine locale

- **Sanson-Flamsteed**: Usato in alcune province
  - Modena, Reggio Emilia, Massa-Carrara, Lucca, La Spezia

## Origini Catastali

Il sistema include le 31 grandi origini catastali predefinite. Per supportare le 818 piccole origini, e' possibile fornire un file JSON aggiuntivo:

```json
{
  "CODICE_ORIGINE": {
    "nome": "Nome origine",
    "nord_gb": 4500000,
    "est_gb": 1500000,
    "fuso_gb": 1
  }
}
```

## Fonti Dati

- [Agenzia delle Entrate - Punti Fiduciali](https://www.agenziaentrate.gov.it/portale/schede/fabbricatiterreni/punti-fiduciali/)
- [fiduciali.altervista.org](http://fiduciali.altervista.org/) - Fonte alternativa gratuita
- [VisualTAF](https://visualtaf.it/) - WebGIS punti fiduciali

## Riferimenti

- [topog4qgis](https://github.com/marcolombardi-rm/topog4qgis) - Plugin QGIS per libretti Pregeo
- [ConveRgo](https://www.geoportale.regione.lombardia.it/) - Conversione coordinate CISIS
- [fiduciali.it](http://www.fiduciali.it/) - Database origini catastali

## Licenza

MIT License
