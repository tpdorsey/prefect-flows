# Prefect 1 flow

import requests
import json
import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from prefect import task, Flow

# define some baseline parameters
pd_start = datetime.datetime(2020, 3, 11).date() # who declares start of pandemic
q_days = 10                                      # cdc quarantine recommendation
day_slice = 60

img_path = ""

# https://geodata.vermont.gov/datasets/vt-covid-19-daily-counts-table/data
covid_data_endpoint = 'https://services1.arcgis.com/BkFxaEFNwHqX3tAw/arcgis/rest/services/VIEW_EPI_DailyCount_PUBLIC_r3/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=json'
# https://geodata.vermont.gov/datasets/vt-covid-19-hospitalizations-by-date-emr/data
hosp_data_endpoint = 'https://services1.arcgis.com/BkFxaEFNwHqX3tAw/arcgis/rest/services/VIEW_EMR_Hospitalization_PUBLIC_r2/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=json'

headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.108 Safari/537.36'
}

date_labels = [
    [2020, 3,  11, "who declares pandemic", 'dimgrey'],
    [2020, 3,  18, "closures begin",        'black'],
    [2020, 5,  18, "re-openings begin",     'black'],
    [2020, 12, 11, "pfizer eua",            'black'],
    [2020, 12, 18, "moderna eua",           'black'],
    [2021, 3,  11, "pandemic year 2",       'dimgrey'],
    [2021, 5,  10, "pfizer expanded eua",   'black'],
    [2021, 5,  17, "cdc ends mask guidance",'black'],
    [2021, 7,  27, "cdc resumes mask guidance", 'black'],
    [2021, 11, 22, "moderna expanded eua",  'black'],
    [2022, 2,  21, "cdc ends mask guidance",'black'],
    [2022, 3,   11, "pandemic year 3",       'dimgrey'],
]

@task
def get_pd_days(pd_start):
    # number of days since start of pandemic
    return (datetime.datetime.now().date() - pd_start).days

def get_date(esri_datestamp):
    a_datetime = datetime.datetime.fromtimestamp(esri_datestamp / 1000)
    return datetime.datetime.date(a_datetime)

@task(max_retries=3, retry_delay=datetime.timedelta(seconds=1))
def get_data(api_url):
    session = requests.Session()
    response = session.get(api_url, headers=headers)
    data = response.text
    return data

@task
def get_cases(data):
    cases = []
    for feature in data["features"]:
        cases.append(feature["attributes"])
    return cases

@task
def get_json(resp):
    data = json.loads(resp)
    return data

@task
def cases_dataframe(case_data):
    cases = pd.DataFrame(case_data)
    # cases['date'] = cases['date'].map(get_date)
    return cases

@task
def merge_dataframes(dfc, dfh):
    df_all_data = pd.merge_asof(dfc[[
                                    'date', 
                                    'positive_cases', 
                                    'cumulative_positives', 
                                    'total_deaths', 
                                    'daily_deaths', 
                                    'daily_recovered', 
                                    'total_recovered', 
                                    'confirmed_cases', 
                                    'probable_cases']], 
                                dfh[[
                                    'date', 
                                    'current_hospitalizations', 
                                    'all_confirmed_ICU']], 
                                on="date")
    df_all_data['date'] = df_all_data['date'].map(get_date)
    return df_all_data

@task
def rolling_mean(dataframe):
    return dataframe.positive_cases.rolling(7).mean()

@task
def active_cases(dataframe):
    return dataframe.positive_cases.rolling(q_days).sum()

@task
def plot_cases(df_all_data, pos_cases_avg, pd_days, date_labels):
    # Overall case reporting with 7-day average
    plt.figure(figsize=[15,10])
    plt.grid(False)
    # plot data
    plt.plot(df_all_data.date, pos_cases_avg, label='cases 7 day avg', color="gold")
    plt.bar(df_all_data.date, df_all_data.positive_cases, label='daily postive cases', color="cornsilk")
    plt.plot(df_all_data.date, df_all_data.current_hospitalizations, label='in hospital', color="cornflowerblue")
    plt.bar(df_all_data.date, df_all_data.daily_deaths, label='daily deaths', color='lightcoral')
    plt.plot(df_all_data.date, df_all_data.total_deaths, label='total deaths', color='indianred')
    # axis formatting
    plt.xlabel("date")
    plt.ylabel("cases")
    # space date ticks two weeks apart
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=14))
    plt.xticks(rotation=90)
    # title and annotations
    plt.title("vt doh covid-19 reporting - pandemic day " + 
              str(pd_days) + 
              "\ncase reporting reflects state-recognized pcr tests only")
    # labels
    for label in date_labels:
        plt.text(datetime.datetime(label[0], label[1], label[2]), 100, label[3], rotation=90, color=label[4])

    plt.legend(loc=2)
    plt.savefig(img_path + 'vt-covid-reporting.png')

@task
def plot_infections(df_all_data, pos_cases_avg, active_cases_est, pd_days, date_labels):
    # Overall positive cases, hospitalizations, and estimated current infections
    plt.figure(figsize=[15,10])
    plt.grid(False)

    plt.plot(df_all_data.date, pos_cases_avg, label='cases 7 day avg', color="gold")
    plt.bar(df_all_data.date, df_all_data.positive_cases, label='daily postive cases', color="cornsilk")
    plt.plot(df_all_data.date, df_all_data.current_hospitalizations, label='in hospital', color="cornflowerblue")
    plt.plot(df_all_data.date, active_cases_est, label='est active cases', color="orange")

    plt.xlabel("date")
    plt.ylabel("cases")
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=14))
    plt.xticks(rotation=90)

    plt.title("vt doh covid-19 reporting - pandemic day " + 
              str(pd_days) + 
              "\nestimate of daily active cases based on cdc quarantine window")

    # labels
    for label in date_labels:
        plt.text(datetime.datetime(label[0], label[1], label[2]), 50, label[3], rotation=90, color=label[4])

    plt.legend(loc=2)
    plt.savefig(img_path + 'vt-covid-active-cases.png')

@task
def plot_hospitalizations(df_all_data, pd_days, date_labels):
    # Hospitalizations, ICU, and deaths
    plt.figure(figsize=[15,10])
    plt.grid(False)

    # plot data
    plt.plot(df_all_data.date, df_all_data.current_hospitalizations, label='in hospital', color="cornflowerblue")
    plt.bar(df_all_data.date, df_all_data.daily_deaths, label='daily deaths', color='lightcoral')
    plt.plot(df_all_data.date, df_all_data.total_deaths, label='total deaths', color='indianred')
    plt.plot(df_all_data.date, df_all_data.all_confirmed_ICU, label='in icu', color='orange')

    # axis formatting
    plt.xlabel("date")
    plt.ylabel("cases")

    # space date ticks two weeks apart
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=14))
    plt.xticks(rotation=90)

    # title and annotations
    plt.title("vt doh covid-19 reporting - pandemic day " + str(pd_days) + "\nhospitalizations, icu, and deaths")
    # labels
    for label in date_labels:
        plt.text(datetime.datetime(label[0], label[1], label[2]), 30, label[3], rotation=90, color=label[4])
    plt.legend(loc=2)
    plt.savefig(img_path + 'vt-covid-hospitalizations.png')


with Flow("vt-covid-report") as flow:
    
    pd_days = get_pd_days(pd_start)

    covid_response = get_data(covid_data_endpoint)
    covid_data = get_json(covid_response)

    hospital_response = get_data(hosp_data_endpoint)
    hospital_data = get_json(hospital_response)

    positive_cases = get_cases(covid_data)
    df_covid = cases_dataframe(positive_cases)

    hospital_cases = get_cases(hospital_data)        
    df_hospital = cases_dataframe(hospital_cases)

    df_all_data = merge_dataframes(df_covid, df_hospital)

    pos_cases_avg = rolling_mean(df_all_data)
    active_cases_est = active_cases(df_all_data)

    plot_cases(df_all_data, pos_cases_avg, pd_days, date_labels)
    plot_infections(df_all_data, pos_cases_avg, active_cases_est, pd_days, date_labels)
    plot_hospitalizations(df_all_data, pd_days, date_labels)

flow.register(project_name="vtcvd_data")

# flow.run()
