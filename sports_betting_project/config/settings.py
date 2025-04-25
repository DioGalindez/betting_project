
#MANTIENE EL CÓDIGO LIMPIO Y SEPARADO DE LA LÓGICA DEL PROYECTO


"""____________________________________________________________________________________"""

# Configuración de la API de OddsAPI

API_KEY = "7929bccf637b136fd702bd8b14cd0168"
SPORT = "soccer_spain_la_liga"  # Liga de fútbol (ajústalo si necesitas otra)
REGION = "eu"  # Regiones: us, uk, eu, au
MARKETS = ["h2h", "spreads", "totals"]   #1X2, Handicap, Over/Under
BOOKMAKERS = [ 
    "bet365",
    "betfair",
    "betway",
    "pinnacle",
    "williamhill",
    "bwin",
    "unibet",
    "ladbrokes",
    "888sport",
    "skybet",
    "marathonbet",
    "betsson"]  # Casas de apuestas de referencia
MIN_EDGE = 0.02  # Margen mínimo para considerar una Value Bet

"""____________________________________________________________________________________"""

# Configuración de la API de FootballData.org

FD_API_KEY = '95381170175b45cf88e1efb5e9d293b3' # Cambia esto por tu clave de API
FD_BASE_URL = 'https://api.football-data.org/v4/' # URL base de la API
LEAGUES = {   
    'la_liga': 'PD',  # La Liga
    #'bundesliga': 'BL1',  # Bundesliga
    #'serie_a': 'SA',  # Serie A
    #'eredivisie': 'DED',  # Eredivisie
    #'premier_league': 'PL',  # Premier League
}
DEFAULT_SEASON = 2024 # Temporada por defecto

