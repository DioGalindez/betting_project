import unidecode  # Asegura que los nombres sean uniformes eliminando acentos
from typing import Dict, List, Set, Any

TEAM_ALIASES = {
    "Athletic Bilbao": "Athletic Club",
    "Athletic bilbao": "Athletic Club",
    "Athletic": "Athletic Club",

    "Las Palmas": "UD Las Palmas",
    "Las palmas": "UD Las Palmas",

    "Celta Vigo": "RC Celta",
    "Celta vigo": "RC Celta",
    "Celta": "RC Celta",

    "Real Sociedad": "Real Sociedad",
    "Real sociedad": "Real Sociedad",

    "Atletico Madrid": "Atlético de Madrid",
    "Atletico madrid": "Atlético de Madrid",
    "Atlético Madrid": "Atlético de Madrid",

    "Real Betis": "Real Betis Balompié",
    "Real betis": "Real Betis Balompié",
    "Betis": "Real Betis Balompié",

    "Valladolid": "Real Valladolid",
    "valladolid": "Real Valladolid",

    "Leganes": "CD Leganés",
    "leganes": "CD Leganés",

    "Espanyol": "RCD Espanyol",
    "espanyol": "RCD Espanyol",

    "Getafe": "Getafe CF",
    "getafe": "Getafe CF",

    "Osasuna": "CA Osasuna",
    "CA Osasuna": "CA Osasuna",
    "osasuna": "CA Osasuna",

    "Alaves": "Deportivo Alavés",
    "alaves": "Deportivo Alavés",

    "Girona": "Girona FC",
    "girona": "Girona FC",

    "Mallorca": "RCD Mallorca",
    "mallorca": "RCD Mallorca",

    "Real Madrid": "Real Madrid CF",
    "real madrid": "Real Madrid CF",
    "Madrid": "Real Madrid CF",

    "Barcelona": "FC Barcelona",
    "barcelona": "FC Barcelona",

    "Sevilla": "Sevilla FC",
    "sevilla": "Sevilla FC",

    "Valencia": "Valencia CF",
    "valencia": "Valencia CF",

    "Villarreal": "Villarreal CF",
    "villarreal": "Villarreal CF"
}

def normalize_team_name(name: str) -> str:
    """Normaliza el nombre del equipo para evitar problemas de coincidencia."""
    return TEAM_ALIASES.get(name.strip(), name.strip())

def calculate_implied_probability(odds: float) -> float:
    """Calcula la probabilidad implícita a partir de las cuotas."""
    return 1/odds if odds > 0 else 0

def get_teams_in_match(match: Dict[str, Any]) -> Set[str]:
    """Extrae los equipos que aparecen en el partido."""
    teams = set()
    for bookmaker in match.get('bookmakers', []):
        for market in bookmaker.get('markets', []):
            if market.get('key') == 'h2h':
                for outcome in market.get('outcomes', []):
                    if outcome.get('name', []).lower() != 'draw':
                        teams.add(normalize_team_name(outcome.get('name', '')))                   
    return teams          
    

def find_matching_game_id(teams_in_match: Set[str], estimated_probabilities: Dict[str, Any]) -> str:
    """Busca el game_id que coincide con los equipos en el partido."""
    for game_id, teams_probs in estimated_probabilities.items():
        estimated_teams = {normalize_team_name(t) for t in teams_probs.keys()}
        if estimated_teams == teams_in_match:
            print(f"✅ ¡Match encontrado! Usaremos {game_id}")
            return game_id
    return None  # Si no se encuentra coincidencia  

def filter_duplicate_bets(value_bets: List[Dict]) -> List[Dict]:
    """Filtra las apuestas duplicadas."""
    best_bets = {}
    for bet in value_bets:
        key = (bet['game_id'], bet['team'])  # Agrupa por partido y equipo
        if key not in best_bets or bet['edge'] > best_bets[key]['edge']:  
            best_bets[key] = bet
    return list(best_bets.values())