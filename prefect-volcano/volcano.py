import requests
import json
from datetime import datetime, timedelta
from prefect import flow, task, get_run_logger
from prefect.blocks.notifications import SlackWebhook
from prefect.tasks import task_input_hash

api_url = 'https://api.geonet.org.nz/volcano/val'
headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.108 Safari/537.36'
}
notify_block = ""

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
def get_volcano_status(data):
    volcano_hazards = []
    for feature in data['features']:
        if feature['properties']['level'] > 0:
            volcano_hazards.append(feature['properties'])
    return volcano_hazards

@task(cache_key_fn=task_input_hash, cache_expiration=timedelta(days=7))
def log_volcano_hazards(hazards):
    slack_webhook = SlackWebhook.load(notify_block)
    logger = get_run_logger()

    msgs = [":volcano: *Volcano Hazard Alerts* :volcano:\n\n"]

    for hazard in hazards:
        color = hazard['acc'].lower()
        haz_msg = f":large_{color}_circle: {hazard['volcanoTitle']} at level {hazard['level']} - {hazard['activity']}\n\n"
        msgs.append(haz_msg)
    
    msgs.append(f"See the <https://www.geonet.org.nz/volcano|GeoNet Volcanic Alert Levels dashboard> for details.\n\nLast updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    log_msg = ''.join(msgs)

    logger.info(log_msg)
    slack_webhook.notify(log_msg, subject="Volcano Hazard Alert")

@flow(name="NZ Volcano Status Alerts")
def monitor_volcanoes():
    resp = get_data_from_api()
    data = get_json(resp)
    volcano_hazards = get_volcano_status(data)
    if len(volcano_hazards) > 0:
        log_volcano_hazards(volcano_hazards)

# if __name__ == "__main__":
#     monitor_volcanoes()