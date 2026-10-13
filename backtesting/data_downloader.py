"""
ArbitragePro NextGen - Historical Multi-Season Data Ingestion
Descarga y gestiona datasets oficiales de football-data.co.uk (LaLiga, Premier League).
Cuenta con fallback offline automático para garantizar funcionamiento autónomo y reproducible.
"""

import os
import urllib.request
from typing import List, Dict, Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "historical")

HISTORICAL_FEEDS = [
    {
        "league": "LaLiga",
        "season": "2024-2025",
        "code": "SP1",
        "filename": "laliga_2024_2025.csv",
        "url": "https://www.football-data.co.uk/mmz4281/2425/SP1.csv"
    },
    {
        "league": "LaLiga",
        "season": "2023-2024",
        "code": "SP1",
        "filename": "laliga_2023_2024.csv",
        "url": "https://www.football-data.co.uk/mmz4281/2324/SP1.csv"
    },
    {
        "league": "PremierLeague",
        "season": "2024-2025",
        "code": "E0",
        "filename": "premier_2024_2025.csv",
        "url": "https://www.football-data.co.uk/mmz4281/2425/E0.csv"
    },
    {
        "league": "PremierLeague",
        "season": "2023-2024",
        "code": "E0",
        "filename": "premier_2023_2024.csv",
        "url": "https://www.football-data.co.uk/mmz4281/2324/E0.csv"
    }
]

class HistoricalDataDownloader:
    """Descargador resiliente de datasets deportivos oficiales."""

    @classmethod
    def ensure_data_directory(cls) -> str:
        os.makedirs(DATA_DIR, exist_ok=True)
        return DATA_DIR

    @classmethod
    def download_feed(cls, feed: Dict[str, str], timeout: float = 6.0) -> bool:
        """Descarga un archivo CSV con headers HTTP legítimos."""
        cls.ensure_data_directory()
        filepath = os.path.join(DATA_DIR, feed["filename"])
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
            return True

        req = urllib.request.Request(
            feed["url"],
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ArbitragePro/2.0"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    content = response.read()
                    with open(filepath, "wb") as f:
                        f.write(content)
                    print(f"[DATA DOWNLOAD] {feed['league']} {feed['season']} descargado ({len(content)} bytes).")
                    return True
        except Exception as e:
            print(f"[DATA DOWNLOAD AVISO] No se pudo descargar {feed['url']}: {e}")
            return False

    @classmethod
    def download_all(cls) -> List[str]:
        """Descarga todas las fuentes configuradas y retorna los archivos disponibles."""
        cls.ensure_data_directory()
        available_files = []
        for feed in HISTORICAL_FEEDS:
            success = cls.download_feed(feed)
            filepath = os.path.join(DATA_DIR, feed["filename"])
            if success and os.path.exists(filepath):
                available_files.append(filepath)

        if not available_files:
            # Fallback offline si no hay conexión a internet
            cls._create_offline_fallback()
            fallback_path = os.path.join(DATA_DIR, "offline_multiseason.csv")
            if os.path.exists(fallback_path):
                available_files.append(fallback_path)

        return available_files

    @classmethod
    def _create_offline_fallback(cls):
        """Crea dataset multitemporada offline enriquecido si la red no está disponible."""
        cls.ensure_data_directory()
        filepath = os.path.join(DATA_DIR, "offline_multiseason.csv")
        if os.path.exists(filepath):
            return

        header = "Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A,PSH,PSD,PSA\n"
        rows = [
            "01/09/2024,Real Madrid,Real Betis,2,0,H,1.28,5.75,10.00,1.30,5.85,10.50",
            "01/09/2024,Barcelona,Valladolid,7,0,H,1.22,6.50,12.00,1.24,6.70,12.80",
            "14/09/2024,Real Sociedad,Real Madrid,0,2,A,5.25,3.80,1.68,5.40,3.90,1.71",
            "15/09/2024,Girona,Barcelona,1,4,A,4.00,4.20,1.75,4.15,4.30,1.78",
            "17/09/2024,Real Madrid,Stuttgart,3,1,H,1.30,6.00,8.50,1.32,6.10,8.80",
            "19/09/2024,Monaco,Barcelona,2,1,H,4.50,4.00,1.72,4.65,4.10,1.75",
            "21/09/2024,Real Madrid,Espanyol,4,1,H,1.18,7.50,15.00,1.20,7.60,16.00",
            "22/09/2024,Villarreal,Barcelona,1,5,A,3.75,4.00,1.85,3.85,4.10,1.89",
            "24/09/2024,Real Madrid,Alaves,3,2,H,1.20,6.50,14.00,1.22,6.60,14.50",
            "25/09/2024,Barcelona,Getafe,1,0,H,1.25,6.00,11.00,1.26,6.20,11.80",
            "29/09/2024,Atletico Madrid,Real Madrid,1,1,D,2.75,3.40,2.50,2.80,3.45,2.55",
            "01/10/2024,Arsenal,Paris SG,2,0,H,1.75,3.80,4.50,1.78,3.85,4.60",
            "01/10/2024,Barcelona,Young Boys,5,0,H,1.08,12.00,23.00,1.10,12.50,25.00",
            "02/10/2024,Lille,Real Madrid,1,0,H,5.50,4.20,1.57,5.65,4.30,1.60",
            "05/10/2024,Real Madrid,Villarreal,2,0,H,1.25,6.50,10.00,1.27,6.60,10.50",
            "06/10/2024,Alaves,Barcelona,0,3,A,5.75,4.33,1.55,5.90,4.40,1.58",
            "19/10/2024,Celta Vigo,Real Madrid,1,2,A,5.00,4.20,1.62,5.15,4.30,1.65",
            "20/10/2024,Barcelona,Sevilla,5,1,H,1.30,5.75,9.00,1.32,5.90,9.50",
            "22/10/2024,Real Madrid,Dortmund,5,2,H,1.50,4.75,5.50,1.53,4.85,5.70",
            "23/10/2024,Barcelona,Bayern Munich,4,1,H,2.30,3.90,2.75,2.35,3.95,2.80",
            "26/10/2024,Real Madrid,Barcelona,0,4,A,2.05,3.80,3.20,2.10,3.85,3.25",
            "02/11/2024,Valencia,Real Madrid,1,2,A,4.80,3.90,1.70,4.95,4.00,1.73",
            "03/11/2024,Barcelona,Espanyol,3,1,H,1.12,9.50,19.00,1.14,9.80,20.00",
            "05/11/2024,Real Madrid,AC Milan,1,3,A,1.50,4.50,6.00,1.53,4.60,6.20",
            "06/11/2024,Red Star,Barcelona,2,5,A,13.00,7.00,1.20,13.50,7.20,1.22",
            "09/11/2024,Real Madrid,Osasuna,4,0,H,1.20,7.00,13.00,1.22,7.20,13.50",
            "10/11/2024,Real Sociedad,Barcelona,1,0,H,4.50,4.20,1.70,4.65,4.30,1.73",
            "23/11/2024,Celta Vigo,Barcelona,2,2,D,4.75,4.33,1.65,4.90,4.40,1.68",
            "24/11/2024,Leganes,Real Madrid,0,3,A,7.50,4.75,1.42,7.80,4.85,1.44",
            "26/11/2024,Barcelona,Brest,3,0,H,1.15,8.50,16.00,1.16,8.80,17.00",
            "27/11/2024,Liverpool,Real Madrid,2,0,H,1.90,3.80,3.75,1.94,3.85,3.85"
        ]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(header + "\n".join(rows) + "\n")
        print(f"[DATA DOWNLOAD] Fallback multitemporada generado en: {filepath}")

if __name__ == "__main__":
    files = HistoricalDataDownloader.download_all()
    print(f"Archivos históricos listos: {files}")
