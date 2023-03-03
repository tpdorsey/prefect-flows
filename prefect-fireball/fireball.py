import requests
import json
import pandas as pd
from datetime import datetime, timedelta
from prefect import flow, task, get_run_logger
from prefect.blocks.notifications import SlackWebhook

api_url = 'https://ssd-api.jpl.nasa.gov/fireball.api?limit=5'
headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.108 Safari/537.36'
}

@task(retries=3, retry_delay_seconds=10)
def get_data_from_api():
    session = requests.Session()
    response = session.get(api_url, headers=headers)
    response.raise_for_status()
    data = response.text
    return data

@task
def get_json(resp):
    data = json.loads(resp)
    return data

@task
def get_fireballs(data):
    columns = data["fields"]
    fireballs = pd.DataFrame(data["data"], columns=columns)
    fireballs['date'] = pd.to_datetime(fireballs['date'])
    return fireballs

@task
def recent_fireballs(df, hours):
    df_recent = df[df["date"] > datetime.now() - timedelta(hours=hours)]
    return df_recent

@task
def log_fireballs(df):
    fireballs = df.to_dict(orient="records")
    
    logger = get_run_logger()
    for fb in fireballs:
        log_msg =   (f"Fireball record on {fb['date']} - "
                    f"Altitude {fb['alt']}km - {fb['lat']}{fb['lat-dir']} {fb['lon']}{fb['lon-dir']}"
                    )
        logger.info(log_msg)

@task
def notify_fireballs(df):
    fireballs = df.to_dict(orient="records")
    slack_webhook = SlackWebhook.load("slack-flow-alerts")
    
    logger = get_run_logger()
    for fb in fireballs:
        log_msg =   (f"Fireball hit the atmosphere on {fb['date']} \n\n"
                    f"Total Radiated Energy {fb['energy']}J\n"
                    f"Altitude {fb['alt']}km\n"
                    f"Latitude {fb['lat']}{fb['lat-dir']}\n"
                    f"Longitude {fb['lon']}{fb['lon-dir']}"
                    )
        logger.info(log_msg)
        slack_webhook.notify(log_msg, subject="Fireball Alert")

@flow(name="Fireballs from Outer Space")
def monitor_fireballs():
    resp = get_data_from_api()
    data = get_json(resp)
    fireballs = get_fireballs(data)
    daily_fireballs = recent_fireballs(fireballs, 36)
    log_fireballs(fireballs)
    if len(daily_fireballs) > 0:
        notify_fireballs(daily_fireballs)

# if __name__ == "__main__":
#     monitor_fireballs()