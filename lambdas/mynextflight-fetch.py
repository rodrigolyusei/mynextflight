import json
import logging
import os
import urllib.parse
import urllib.request
from boto3 import resource
from boto3.dynamodb.conditions import Key
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

API_KEY = os.environ.get('SERPAPI_KEY')
ALERTS_TABLE = resource('dynamodb').Table(os.environ.get('TABLE_NAME'))
TOKEN = os.environ.get('TELEGRAM_TOKEN')
URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def lambda_handler(event, context):
    logger.info("Iniciando verificacao de alertas de voo")

    response = ALERTS_TABLE.scan()
    alerts = response.get('Items', [])
    
    for alert in alerts:
        try:
            check_flight_and_notify(alert)
        except Exception as e:
            logger.error(f"Erro ao processar alerta {alert['alert_id']}: {str(e)}")

def check_flight_and_notify(alert):
    base_url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_flights",
        "departure_id": alert['origin'],
        "arrival_id": alert['destination'],
        "outbound_date": alert['date'],
        "currency": "BRL",
        "hl": "pt",
        "api_key": API_KEY
    }
    
    query_string = urllib.parse.urlencode(params)
    url = f"{base_url}?{query_string}"
    
    with urllib.request.urlopen(url) as response:
        results = json.loads(response.read().decode())
    
    if 'error' in results:
        logger.error(f"Erro na API Serp: {results['error']}")
        return

    if 'best_flights' not in results:
        logger.info(f"Nenhum voo encontrado para {alert['origin']}->{alert['destination']}")
        return
    
    price = Decimal(results['best_flights'][0]['price'])
    
    if price <= alert['max_price']:
        send_message(
            chat_id=alert['user_id'],
            msg=f"✈️ Alerta! Voo para {alert['destination']} encontrado por R$ {price}!\n"
                f"Data: {alert['date']}\n"
                f"Link: {results['search_metadata']['google_flights_url']}"
        )

def send_message(chat_id, text):
    data = {"chat_id": chat_id, "text": text}
    params = json.dumps(data).encode('utf8')
    req = urllib.request.Request(URL, data=params, headers={'content-type': 'application/json'})
    urllib.request.urlopen(req)