import json
import pandas as pd
import numpy as np
from scipy.stats import poisson
from typing import List, Dict, Union
from datetime import datetime, timedelta
import pytz
from utils import normalize_team_name, filter_duplicate_bets
from config.settings import BOOKMAKERS, MIN_EDGE

# ----------------------------
# 1. CARGAR Y PREPROCESAR DATOS
# ----------------------------
def load_data():
    """Carga datos de partidos y cuotas con validación robusta"""
    try:
        with open('data/odds.json') as f:
            odds_data = json.load(f)
        
        league_data = pd.read_csv('data/la_liga_2024_matches.csv')
        league_data['date'] = pd.to_datetime(league_data['date'], errors='coerce')
        league_data = league_data.dropna(subset=['date'])
        
        # Normalizar nombres
        league_data['home_team'] = league_data['home_team'].apply(normalize_team_name)
        league_data['away_team'] = league_data['away_team'].apply(normalize_team_name)
        
        return odds_data, league_data
    except Exception as e:
        print(f"❌ Error cargando datos: {str(e)}")
        raise

# ----------------------------
# 2. MODELOS DE PROBABILIDAD
# ----------------------------
def calculate_h2h_probabilities(home_team: str, away_team: str, league_data: pd.DataFrame) -> Dict[str, float]:
    """Calcula probabilidades para el mercado 1X2 usando modelo Dixon-Coles simplificado"""
    recent_matches = get_recent_matches(league_data, days=180)
    
    # Obtener fuerza ofensiva/defensiva
    home_attack = recent_matches[recent_matches['home_team'] == home_team]['home_score'].mean()
    home_defense = recent_matches[recent_matches['home_team'] == home_team]['away_score'].mean()
    away_attack = recent_matches[recent_matches['away_team'] == away_team]['away_score'].mean()
    away_defense = recent_matches[recent_matches['away_team'] == away_team]['home_score'].mean()
    
    # Ajustar por promedio general (evitar divisiones por cero)
    avg_home = league_data['home_score'].mean()
    avg_away = league_data['away_score'].mean()
    
    home_str = (home_attack / avg_home) * (away_defense / avg_away) * avg_home
    away_str = (away_attack / avg_away) * (home_defense / avg_home) * avg_away
    
    # Normalizar probabilidades
    total = home_str + away_str + 0.3 * (home_str + away_str)  # Empate como 30% del total
    return {
        home_team: max(min(home_str / total, 0.85), 0.15),
        away_team: max(min(away_str / total, 0.85), 0.15),
        'draw': max(min(0.3 * (home_str + away_str) / total, 0.35), 0.05)
    }

def calculate_over_under_probability(home_team: str, away_team: str, league_data: pd.DataFrame, line: float = 2.5) -> Dict[str, float]:
    """Modelo Poisson para Over/Under"""
    recent_matches = get_recent_matches(league_data, days=180)
    
    # Lambda (promedio de goles)
    home_avg = recent_matches[recent_matches['home_team'] == home_team]['home_score'].mean()
    away_avg = recent_matches[recent_matches['away_team'] == away_team]['away_score'].mean()
    total_avg = (home_avg + away_avg) * 0.95  # Factor de ajuste
    
    # Calcular probabilidades
    prob_over = 1 - poisson.cdf(line, total_avg)
    return {
        f"over_{line}": prob_over,
        f"under_{line}": 1 - prob_over
    }

def calculate_btts_probability(home_team: str, away_team: str, league_data: pd.DataFrame) -> Dict[str, float]:
    """Probabilidad de Both Teams to Score (BTTS)"""
    recent_matches = get_recent_matches(league_data, days=180)
    
    # Filtrar partidos relevantes
    home_games = recent_matches[
        (recent_matches['home_team'] == home_team) | 
        (recent_matches['away_team'] == home_team)
    ]
    away_games = recent_matches[
        (recent_matches['home_team'] == away_team) | 
        (recent_matches['away_team'] == away_team)
    ]
    
    # Calcular frecuencia de BTTS
    home_btts = (home_games['home_score'] > 0) & (home_games['away_score'] > 0)
    away_btts = (away_games['home_score'] > 0) & (away_games['away_score'] > 0)
    
    prob_yes = np.mean([home_btts.mean(), away_btts.mean()])
    return {'yes': prob_yes, 'no': 1 - prob_yes}

# ----------------------------
# 3. DETECCIÓN DE VALUE BETS
# ----------------------------
def find_value_bets(odds_data: List[Dict], league_data: pd.DataFrame) -> List[Dict]:
    """Busca value bets en todos los mercados disponibles"""
    value_bets = []
    
    for match in odds_data:
        home_team = normalize_team_name(match['home_team'])
        away_team = normalize_team_name(match['away_team'])
        
        # Calcular todas las probabilidades
        probs = {
            'h2h': calculate_h2h_probabilities(home_team, away_team, league_data),
            'totals': calculate_over_under_probability(home_team, away_team, league_data),
            'btts': calculate_btts_probability(home_team, away_team, league_data)
        }
        
        for bookmaker in match['bookmakers']:
            if bookmaker['title'] not in BOOKMAKERS:
                continue
                
            for market in bookmaker['markets']:
                market_key = market['key']
                if market_key not in probs:
                    continue
                    
                for outcome in market['outcomes']:
                    process_outcome(outcome, market_key, home_team, away_team, probs[market_key], bookmaker['title'], value_bets)
    
    return value_bets

def process_outcome(outcome: Dict, market_key: str, home_team: str, away_team: str, probs: Dict, bookmaker: str, value_bets: List):
    """Evalúa si una cuota es value bet"""
    odds = outcome.get('price', 0)
    if odds <= 1:
        return
    
    # Mapear nombres de outcomes a claves de probabilidades
    selection_map = {
        'h2h': lambda x: normalize_team_name(x),
        'totals': lambda x: x.lower().replace(" ", "_"),
        'btts': lambda x: x.lower()
    }
    
    selection = selection_map[market_key](outcome['name'])
    implied_prob = 1 / odds
    real_prob = probs.get(selection, 0)
    edge = real_prob - implied_prob
    
    if edge > MIN_EDGE and real_prob >= 0.30:  # Umbral mínimo de probabilidad
        value_bets.append({
            'match': f"{home_team} vs {away_team}",
            'market': market_key,
            'selection': selection,
            'bookmaker': bookmaker,
            'odds': odds,
            'edge': round(edge, 4),
            'implied_prob': round(implied_prob, 4),
            'real_prob': round(real_prob, 4),
            'expected_value': round((odds * real_prob) - 1, 4)  # EV = (Odds * Prob) - 1
        })

# ----------------------------
# 4. EJECUCIÓN PRINCIPAL
# ----------------------------
if __name__ == "__main__":
    try:
        print("⏳ Cargando datos...")
        odds_data, league_data = load_data()
        
        print("🔍 Analizando value bets...")
        value_bets = find_value_bets(odds_data, league_data)
        final_bets = filter_duplicate_bets(value_bets)
        
        if not final_bets:
            print("⚠️ No se encontraron value bets. Revisa:")
            print("- MIN_EDGE (actual: {})".format(MIN_EDGE))
            print("- Calidad de los datos históricos")
        else:
            print(f"✅ {len(final_bets)} value bets encontradas!")
            with open('data/value_bets.json', 'w') as f:
                json.dump(final_bets, f, indent=2)
            print("📊 Resultados guardados en 'data/value_bets.json'")
            
    except Exception as e:
        print(f"❌ Error crítico: {str(e)}")