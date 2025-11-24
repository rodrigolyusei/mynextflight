import json
import logging
import os
import urllib.request
import uuid
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
    try:
        body = json.loads(event['body'])
        if 'message' not in body or 'text' not in body['message']:
            return {'statusCode': 200}

        chat_id = str(body['message']['chat']['id'])
        text = body['message']['text'].strip()
        
        if text == '/start' or text == '/ajuda':
            help_command(chat_id)
        elif text == '/lista':
            list_command(chat_id)
        elif text.startswith('/adiciona'):
            add_command(chat_id, text)
        elif text.startswith('/remove'):
            remove_command(chat_id, text)
        else:
            send_message(chat_id, "Comando não reconhecido.\nUse /ajuda para listar os comandos!")

        return {'statusCode': 200}

    except Exception as e:
        logger.error(f"Exceção não tratada: {e}")
        return {'statusCode': 500}

def help_command(chat_id):
    logger.info("Executando o comando help_command")

    msg = (
        "✈️ MyNextFlight\n\n"
        "Configure alertas de preços de passagens aéreas e receba notificações quando os preços caírem!\n\n"
        "Comandos disponíveis:\n"
        "1️⃣ /lista - Lista das notificações cadastradas\n"
        "2️⃣ /adiciona - Cadastra uma nova notificação\n"
        "3️⃣ /remove - Remove uma notificação existente\n"
    )
    send_message(chat_id, msg)

def list_command(chat_id):
    logger.info("Executando o comando list_command")

    response = ALERTS_TABLE.query(
        KeyConditionExpression=Key('user_id').eq(chat_id)
    )
    items = response.get('Items', [])
    
    if not items:
        send_message(chat_id, "Você não tem alertas ativos.")
        return

    msg = f"📋 Seus Alertas ({len(items)}/6):\n\n"
    for item in items:
        msg += f"🆔 {item['alert_id']}\n"
        msg += f"✈️ {item['origin']} ➔ {item['destination']}\n"
        msg += f"📅 {item['date']}\n"
        msg += f"💰 < R$ {item['max_price']}\n"
        msg += "---------------------\n"
    
    send_message(chat_id, msg)

def add_command(chat_id, text):
    logger.info("Executando o comando add_command")

    parts = text.split()
    if len(parts) != 5:
        send_message(chat_id, 
            "⚠️ Formato inválido!\n"
            "Use: /adiciona ORIGEM DESTINO DATA PRECO\n"
            "Ex: /adiciona SAO JFK 2025-12-25 3500"
        )
        return

    response = ALERTS_TABLE.query(
        KeyConditionExpression=Key('user_id').eq(chat_id),
        Select='COUNT'
    )

    qtd_atual = response['Count']
    if qtd_atual >= 6:
        send_message(chat_id, 
            f"🚫 Limite Atingido ({qtd_atual}/6)\n"
            "Você já possui o máximo de alertas ativos.\n"
            "Use /lista para verificar as alertas e /remove para liberar espaço."
        )
        return

    _, origin, dest, date, price_str = parts
    
    # Precisa validar outros parametros tambem!
    try:
        price = Decimal(price_str)

    except ValueError:
        send_message(chat_id, "Erro: O preço deve ser um número (ex: 3500.50).")
        return

    alert_id = str(uuid.uuid4())[:8]
    
    ALERTS_TABLE.put_item(Item={
        'user_id': chat_id,
        'alert_id': alert_id,
        'origin': origin.upper(),
        'destination': dest.upper(),
        'date': date,
        'max_price': price
    })
    
    send_message(chat_id, f"✅ Alerta criado! ID: {alert_id}\nMonitorando {origin}->{dest} em {date} por menos de R$ {price}.")

def remove_command(chat_id, text):
    logger.info("Executando o comando remove_command")

    parts = text.split()
    
    if len(parts) != 2:
        send_message(chat_id,
            "⚠️ Formato inválido!\n"
            "Uso: /remove ID_DO_ALERTA (veja o ID no comando /lista)"
        )
        return
    
    alert_id_to_remove = parts[1]
    
    try:
        response = ALERTS_TABLE.delete_item(
            Key={
                'user_id': chat_id,
                'alert_id': alert_id_to_remove
            },
            ReturnValues='ALL_OLD' 
        )
        
        if 'Attributes' in response:
            old_item = response['Attributes']
            origem = old_item.get('origin', '???')
            destino = old_item.get('destination', '???')
            
            send_message(chat_id, 
                f"🗑️ Alerta removido! ID: {alert_id_to_remove}\nO alerta de {origem} ➔ {destino} foi removido."
            )
        else:
            send_message(chat_id, 
                f"⚠️ Não encontrei nenhum alerta com o ID `{alert_id_to_remove}`.\n"
                "Use /lista para ver os IDs corretos."
            )

    except Exception as e:
        logger.error(f"Exceção não tratada: {e}")
        send_message(chat_id, "Ocorreu um erro ao tentar remover.")

def send_message(chat_id, text):
    data = {"chat_id": chat_id, "text": text}
    params = json.dumps(data).encode('utf8')
    req = urllib.request.Request(URL, data=params, headers={'content-type': 'application/json'})
    urllib.request.urlopen(req)