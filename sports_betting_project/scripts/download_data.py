import requests 
import pandas as pd
import os 
from typing import Dict, List, Optional
from config.settings import FD_API_KEY, FD_BASE_URL, LEAGUES, DEFAULT_SEASON
# from config.settings import API_KEY, SPORT, REGION, MARKETS, BOOKMAKERS, MIN_EDGE

def fetch_matches(competition: str, season: int = DEFAULT_SEASON) -> None:
    """ Obtiene los partidos finalizados de una competición y temporada determinadas,
    y los guarda en un archivo CSV.

    Args:
    competición: Código de competición (por defecto: "PL" para Premier League)
    season: Año de la temporada (por defecto: 2023) """

    url = f'{FD_BASE_URL}competitions/{LEAGUES['la_liga']}/matches?season={DEFAULT_SEASON}'
    headers = {
        'X-Auth-Token': FD_API_KEY} # Usas la clave de API de FootballData.org para autenticarte

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Lanza un error si la respuesta no es exitosa 
        data = response.json()

        matches = [
            {
                'date': match['utcDate'],
                'home_team': match['homeTeam']['name'],
                'away_team': match['awayTeam']['name'],
                'home_score': match['score']['fullTime']['home'],
                'away_score': match['score']['fullTime']['away'],
            }
            for match in data['matches']
            if match['status'] == 'FINISHED'
        ]    

        df = pd.DataFrame(matches)

        #  Convierte la fecha a tipo datetime y ordena
        df['date'] = pd.to_datetime(df['date'])
        df.sort_values(by='date', inplace=True)

        # Guardar el DataFrame a un archivo CSV
        os.makedirs('data', exist_ok=True)
        league_name = [k for k, v in LEAGUES.items() if v == competition][0]
        csv_path = f'data/{league_name}_{season}_matches.csv'
        df.to_csv(csv_path, index=False)
        print(f"✅ Datos de partidos guardados en {csv_path}")
        return df

    except Exception as e:
        print(f"❌ Error al descargar {competition}: {str (e)}")
        return None
    
if __name__ == '__main__':
    
    # Descargar datos para todas la ligas configuradas
    for league_name, league_code in LEAGUES.items():
        print(f"\n⏳ Descargando partidos de {league_name}...")
        fetch_matches(competition=league_code, season=DEFAULT_SEASON)
        print(f"✅ Partidos de {league_name} descargados y guardados.")
        print("____________________________________________________________________________________")