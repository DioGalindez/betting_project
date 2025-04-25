import requests
import json 
from config.settings import API_KEY, SPORT, REGION, MARKETS, BOOKMAKERS


def get_odds():
     """Obtiene las cuotas de la API y las guarda en un archivo JSON."""
     url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/?regions={REGION}&markets={','.join(MARKETS)}&bookmakers={','.join(BOOKMAKERS)}&apiKey={API_KEY}"
     response = requests.get(url)

     if response.status_code == 200:
        data = response.json()

        #Guardar en un archivo JSON
        
        with open(r"data\odds.json", "w") as file:
            json.dump(data, file, indent=4)
        
        print("✅ Cuotas guardadas en 'data\\odds.json'")
        return data

     else:
        print(f"❌ Error al obtener cuotas: {response.status_code}")

if __name__ == "__main__":
    get_odds()