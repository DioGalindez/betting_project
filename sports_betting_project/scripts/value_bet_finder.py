import pandas as pd
import numpy as np
from scipy.stats import poisson
import requests
from datetime import datetime
from config.settings import FD_API_KEY, FD_BASE_URL, LEAGUES, DEFAULT_SEASON, API_KEY, SPORT, REGION, MARKETS, BOOKMAKERS

class ValueBetFinder:
    def __init__(self):
        self.odds_data = None
        self.historial_data = None
        self.team_name_mapping = {
            'Atletico Madrid': 'Atlético Madrid',
            'Alaves': 'Alavés',
            'Leganes': 'Leganés'
            # Agrega más mapeos según sea necesario
        }

    def normalize_team_name(self, name):
        """Normaliza nombres de equipos para consistencia"""
        return self.team_name_mapping.get(name, name)

    def get_odds(self):
        """Obtiene las cuotas desde la API de Odds"""
        url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/?regions={REGION}&markets={','.join(MARKETS)}&bookmakers={','.join(BOOKMAKERS)}&apiKey={API_KEY}"
        response = requests.get(url)

        if response.status_code == 200:
            self.odds_data = response.json()
            print("✅ Odds obtenidas correctamente")
            return True
        else:
            print(f"❌ Error al obtener odds: {response.status_code}")
            return False

    def get_historical_data(self, league):
        """Obtiene historial de partidos desde Football Data API"""
        url = f'{FD_BASE_URL}competitions/{league}/matches?season={DEFAULT_SEASON}'
        headers = {'X-Auth-Token': FD_API_KEY}

        try:
            response = requests.get(url, headers=headers, timeout=15)
            data = response.json()

            matches = []
            for match in data['matches']:
                if match['status'] == 'FINISHED':
                    home_team = self.normalize_team_name(match['homeTeam']['name'])
                    away_team = self.normalize_team_name(match['awayTeam']['name'])
                    
                    matches.append({
                        'fecha': match['utcDate'],
                        'equipo_local': home_team,
                        'equipo_visitante': away_team,
                        'goles_local': match['score']['fullTime']['home'] if match['score']['fullTime']['home'] is not None else 0,
                        'goles_visitante': match['score']['fullTime']['away'] if match['score']['fullTime']['away'] is not None else 0,
                        'resultado': self._determine_result(match['score']['fullTime']['home'], match['score']['fullTime']['away'])
                    })

            self.historial_data = pd.DataFrame(matches)
            self.historial_data['fecha'] = pd.to_datetime(self.historial_data['fecha'])
            print(f"✅ Historial de {league} obtenido ({len(self.historial_data)} partidos)")
            return True

        except Exception as e:
            print(f"❌ Error obteniendo historial: {str(e)}")
            return False

    def _determine_result(self, home_goals, away_goals):
        """Determina el resultado del partido (1, X, 2)"""
        if home_goals is None or away_goals is None:
            return None
        if home_goals > away_goals:
            return '1'
        elif home_goals == away_goals:
            return 'X'
        else:
            return '2'

    def process_odds(self):
        """Procesa las odds crudas a un DataFrame estructurado"""
        partidos = []

        for evento in self.odds_data:
            home_team = self.normalize_team_name(evento['home_team'])
            away_team = self.normalize_team_name(evento['away_team'])
            partido = f"{home_team} - {away_team}"
            fecha = datetime.fromisoformat(evento['commence_time'][:-1]).strftime('%Y-%m-%d %H:%M')

            for bookmaker in evento['bookmakers']:
                casa = bookmaker['key']
                odds = {'local': None, 'empate': None, 'visitante': None}

                for market in bookmaker['markets']:
                    if market['key'] == 'h2h':
                        for outcome in market['outcomes']:
                            if outcome['name'] == evento['home_team']:
                                odds['local'] = outcome['price']
                            elif outcome['name'] == evento['away_team']:
                                odds['visitante'] = outcome['price']
                            elif outcome['name'] == 'Draw':
                                odds['empate'] = outcome['price']

                if None not in odds.values():
                    partidos.append({
                        'partido': partido,
                        'casa_apuestas': casa,
                        'odd_local': odds['local'],
                        'odd_empate': odds['empate'],
                        'odd_visitante': odds['visitante'],
                        'fecha': fecha
                    })

        return pd.DataFrame(partidos)

    def calculate_probabilities(self, home_team, away_team):
        """Calcula probabilidades usando modelo Poisson mejorado con regresión a la media"""
        # Obtenemos últimos 10 partidos como local y visitante
        home_local = self.historial_data[
            (self.historial_data['equipo_local'] == home_team)
        ].tail(10)
        
        away_away = self.historial_data[
            (self.historial_data['equipo_visitante'] == away_team)
        ].tail(10)

        # Promedios de la liga
        avg_home_goals = self.historial_data['goles_local'].mean()
        avg_away_goals = self.historial_data['goles_visitante'].mean()

        # Ataque y defensa con regresión a la media
        home_attack = (home_local['goles_local'].mean() * 0.7 + avg_home_goals * 0.3) if not home_local.empty else avg_home_goals
        away_defense = (away_away['goles_local'].mean() * 0.7 + avg_home_goals * 0.3) if not away_away.empty else avg_home_goals
        
        away_attack = (away_away['goles_visitante'].mean() * 0.7 + avg_away_goals * 0.3) if not away_away.empty else avg_away_goals
        home_defense = (home_local['goles_visitante'].mean() * 0.7 + avg_away_goals * 0.3) if not home_local.empty else avg_away_goals

        # Calculamos lambdas con ajuste por localía
        lambda_home = 1.3 * (home_attack / avg_home_goals) * (away_defense / avg_home_goals) * avg_home_goals
        lambda_away = 1.0 * (away_attack / avg_away_goals) * (home_defense / avg_away_goals) * avg_away_goals

        # Simulación Monte Carlo
        np.random.seed(42)  # Para reproducibilidad
        home_goals = np.random.poisson(lambda_home, 10000)
        away_goals = np.random.poisson(lambda_away, 10000)

        prob_home = np.mean(home_goals > away_goals)
        prob_draw = np.mean(home_goals == away_goals)
        prob_away = np.mean(home_goals < away_goals)

        # Normalizamos para que sumen 1
        total = prob_home + prob_draw + prob_away
        return {
            'local': prob_home / total,
            'empate': prob_draw / total,
            'visitante': prob_away / total
        }

    def calculate_confidence(self, home_team, away_team, market):
        """Cálculo mejorado de confianza con múltiples factores"""
        # Datos de rendimiento reciente
        home_local = self.historial_data[
            (self.historial_data['equipo_local'] == home_team)
        ].tail(5)
        
        away_away = self.historial_data[
            (self.historial_data['equipo_visitante'] == away_team)
        ].tail(5)

        # Si no hay suficientes datos, confianza mínima
        if len(home_local) < 3 or len(away_away) < 3:
            return 0.3

        # 1. Factor de rendimiento (diferencia de goles)
        home_perf = home_local['goles_local'].mean() - home_local['goles_visitante'].mean()
        away_perf = away_away['goles_visitante'].mean() - away_away['goles_local'].mean()

        # 2. Factor de consistencia (% de resultados esperados)
        if market == '1':
            consistency = (home_local['resultado'] == '1').mean()
            perf_factor = home_perf * 0.15
        elif market == '2':
            consistency = (away_away['resultado'] == '2').mean()
            perf_factor = away_perf * 0.15
        else:  # Empate
            consistency = 0.3  # Los empates son menos consistentes
            perf_factor = -abs(home_perf - away_perf) * 0.1

        # 3. Factor de forma (últimos 5 partidos)
        home_form = home_local['goles_local'].mean() / self.historial_data['goles_local'].mean()
        away_form = away_away['goles_visitante'].mean() / self.historial_data['goles_visitante'].mean()

        # Cálculo final de confianza
        if market == '1':
            confidence = 0.4 + perf_factor + (consistency * 0.3) + (home_form * 0.1)
        elif market == '2':
            confidence = 0.4 + perf_factor + (consistency * 0.3) + (away_form * 0.1)
        else:
            confidence = 0.4 + perf_factor + (consistency * 0.2)

        return max(0.3, min(0.9, confidence))

    def find_value_bets(self, min_edge=0.03, max_odd=5.0, min_prob=0.30, min_confidence=0.35):
        """Busca value bets con múltiples filtros y ordenamiento"""
        if not self.odds_data or self.historial_data.empty:
            print("❌ Primero carga datos de odds e historial")
            return None

        odds_df = self.process_odds()
        value_bets = []

        for partido in odds_df['partido'].unique():
            home_team, away_team = partido.split(' - ')

            try:
                probs = self.calculate_probabilities(home_team, away_team)
                match_odds = odds_df[odds_df['partido'] == partido]

                for _, row in match_odds.iterrows():
                    for market in ['local', 'empate', 'visitante']:
                        odd = row[f'odd_{market}']
                        prob = probs[market]

                        if odd and prob:
                            implied_prob = 1 / odd
                            edge = prob - implied_prob
                            expected_value = prob * odd - 1
                            market_code = '1' if market == 'local' else ('X' if market == 'empate' else '2')
                            confidence = self.calculate_confidence(home_team, away_team, market_code)
                            
                            if (edge >= min_edge and 
                                odd <= max_odd and 
                                prob >= min_prob and
                                confidence >= min_confidence):
                                
                                value_bets.append({
                                    'Fecha': row['fecha'],
                                    'Partido': partido,
                                    'Mercado': market_code,
                                    'Casa': row['casa_apuestas'],
                                    'Odd': odd,
                                    'Prob. Real': f"{prob*100:.1f}%",
                                    'Prob. Implícita': f"{implied_prob*100:.1f}%",
                                    'Edge': f"{edge*100:.1f}%",
                                    'Valor Esperado': f"{expected_value*100:.1f}%",
                                    'Confianza': f"{confidence*100:.1f}%"
                                })
            except Exception as e:
                print(f"⚠️ Error procesando {partido}: {str(e)}")
                continue

        if value_bets:
            df = pd.DataFrame(value_bets)
            # Convertimos a valores numéricos para ordenar
            df['Confianza_num'] = df['Confianza'].str.replace('%', '').astype(float)
            df['Valor_Esperado_num'] = df['Valor Esperado'].str.replace('%', '').astype(float)
            df['Prob_Real_num'] = df['Prob. Real'].str.replace('%', '').astype(float)
            
            # Ordenamos por combinación de factores
            df = df.sort_values(
                ['Confianza_num', 'Prob_Real_num', 'Valor_Esperado_num'], 
                ascending=[False, False, False]
            )
            df = df.drop(columns=['Confianza_num', 'Valor_Esperado_num', 'Prob_Real_num'])
            
            return df
        else:
            return None

def main():
    print("🔍 Iniciando Value Bet Finder - Versión Optimizada")
    vbf = ValueBetFinder()

    # Parámetros ajustables
    PARAMETROS = {
        'conservador': {'min_edge': 0.05, 'max_odd': 4.0, 'min_prob': 0.35, 'min_confidence': 0.45},
        'equilibrado': {'min_edge': 0.03, 'max_odd': 5.0, 'min_prob': 0.30, 'min_confidence': 0.35},
        'agresivo': {'min_edge': 0.02, 'max_odd': 6.0, 'min_prob': 0.25, 'min_confidence': 0.30}
    }

    # 1. Obtener datos
    print("\n📡 Obteniendo datos de apuestas...")
    if not vbf.get_odds():
        exit()

    print("\n📊 Obteniendo historial de partidos...")
    liga = list(LEAGUES.values())[0]
    if not vbf.get_historical_data(liga):
        exit()

    # 2. Búsqueda por niveles
    print("\n🔎 Buscando value bets...")
    for nivel, params in PARAMETROS.items():
        print(f"\n⚙️ Probando parámetros {nivel}:")
        print(f"- Edge mínimo: {params['min_edge']*100:.0f}%")
        print(f"- Odd máxima: {params['max_odd']}")
        print(f"- Prob. mínima: {params['min_prob']*100:.0f}%")
        print(f"- Confianza mínima: {params['min_confidence']*100:.0f}%")
        
        value_bets = vbf.find_value_bets(**params)
        
        if value_bets is not None:
            print(f"\n🎯 {len(value_bets)} VALUE BETS ENCONTRADOS (nivel {nivel}):")
            print(value_bets[['Fecha', 'Partido', 'Mercado', 'Casa', 'Odd', 'Prob. Real', 'Edge', 'Confianza']])
            
            # Guardar resultados
            filename = f"data/value_bets_{nivel}.csv"
            value_bets.to_csv(filename, index=False)
            print(f"\n💾 Resultados guardados en {filename}")
            
            # Mostrar análisis
            print("\n📊 Análisis:")
            print("- Odd promedio:", round(value_bets['Odd'].astype(float).mean(), 2))
            print("- Edge promedio:", round(value_bets['Edge'].str.replace('%','').astype(float).mean(), 1), "%")
            print("- Confianza promedio:", round(value_bets['Confianza'].str.replace('%','').astype(float).mean(), 1), "%")
            print("\nDistribución de mercados:")
            print(value_bets['Mercado'].value_counts(normalize=True).apply(lambda x: f"{x*100:.1f}%"))
            
            if input("\n¿Continuar con siguiente nivel? (s/n): ").lower() != 's':
                break
        else:
            print(f"⚠️ No se encontraron value bets con parámetros {nivel}")

if __name__ == "__main__":
    main()