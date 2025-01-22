import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time, timedelta, timezone
import matplotlib.pyplot as plt
from fpdf import FPDF
import base64
import numpy as np
from tempfile import NamedTemporaryFile
#import textwrap as twp

from common_functions import (
    get_hh_mm_from_pcg,
    get_hh_mm_from_ms,
    df2report,
    create_download_link,
    create_pdf_report,
    get_tasks,
    get_all_tasks,
    get_ParentID,
    get_GrandParentID,
    get_GrandParentName
)

st.set_page_config(layout="wide", initial_sidebar_state="auto", page_title="ClickUp time tracking dashboard", page_icon="chart_with_upwards_trend")

#################################################################
#                                                               #  
# Access to ClickUp personal workspace (see streamlit secrets)  #
#                                                               #
#################################################################
team_id = st.secrets["team_id"] #workspace personal
API_KEY = st.secrets["API_KEY"]

###################
#                 #
#  PLOT STYLE  #
#                 # 
###################

plt.style.use(['ggplot'])
palette = plt.rcParams['axes.prop_cycle'].by_key()['color']
    

###################
#                 #
#  AUX FUNCTIONS  #
#                 # 
###################




def get_spaces():
    # ref: https://clickup.com/api/clickupreference/operation/GetSpaces/
    url = "https://api.clickup.com/api/v2/team/" + team_id + "/space"
    query = {
        "archived": "false"
    }
    headers = {"Authorization": API_KEY}
    response = requests.get(url, headers=headers, params=query)
    data = response.json()
    data = data['spaces']
    data = pd.json_normalize(data)
    spaces = data[['name']].values.tolist()
    return spaces


#@st.cache #cache is not worth for this function
def get_start_end(period):
    reference_time = datetime.utcfromtimestamp(0)
    if period == 'today':
        start_date = date.today()
        end = int((datetime.now() - reference_time).total_seconds() * 1000.0)    
        midnight = datetime.combine(start_date, time())
        start = int((midnight - reference_time).total_seconds() * 1000.0)
    elif period == 'current_week':
        start_date = date.today() - timedelta(days=date.today().weekday())
        end = int((datetime.now() - reference_time).total_seconds() * 1000.0)   
        midnight = datetime.combine(start_date, time())
        start = int((midnight - reference_time).total_seconds() * 1000.0) 
    elif period == 'current_month':
        start_date = date(date.today().year, date.today().month, 1)
        end = int((datetime.now() - reference_time).total_seconds() * 1000.0)  
        midnight = datetime.combine(start_date, time())
        start = int((midnight - reference_time).total_seconds() * 1000.0)
    elif period == 'all_time':
        start_date = date(2022, 10, 1) #1st of october was when I started the personal workspace
        end = int((datetime.now() - reference_time).total_seconds() * 1000.0)    
        midnight = datetime.combine(start_date, time())
        start = int((midnight - reference_time).total_seconds() * 1000.0)
    else: #is a datetime.date (single day)
        if period == date.today():
            start_date = date.today()
            end = int((datetime.now() - reference_time).total_seconds() * 1000.0)    
            midnight = datetime.combine(start_date, time())
            start = int((midnight - reference_time).total_seconds() * 1000.0)
        else:
            start_date = period
            end_date = period + timedelta(days=1)
            midnight_start = datetime.combine(start_date, time())
            midnight_end = datetime.combine(end_date, time())
            start = int((midnight_start - reference_time).total_seconds() * 1000.0)
            end = int((midnight_end - reference_time).total_seconds() * 1000.0)

    #if isinstance(period, type(datetime.date)):
     #   st.write('es date')
      #  start_date = period #esto provoca un error, hay que formatearlo bien

    
    return start,end


def set_pie_colors():
    colors = {}
    for count,space in enumerate(spaces):
        colors[space[0]] = palette[count+2] #adding numbers here changes the pallette shown in pie charts
    return colors
    
def pie_chart(df):
    fig,ax = plt.subplots()
    x = df.values
    explode = []
    for i in range(len(x)):
        explode.append(0.05)
    total_time = sum(df.values)
    df = df.to_frame()
    colors = set_pie_colors()
    labels = df.index.tolist()
    plt.pie(x, labels = labels, colors = [colors[key] for key in labels], autopct=lambda pcg: get_hh_mm_from_pcg(pcg, total_time), pctdistance=0.72, explode=explode) 
        
    centre_circle = plt.Circle((0, 0), 0.50, fc='white', label='anotate')
    fig = plt.gcf()
    fig.gca().add_artist(centre_circle)
    #plt.title('Chart title')
    #ax.text(0, 0, 'Total = ' + str(datetime.fromtimestamp(total_time/1000.0,tz=timezone.utc).strftime("%H:%M:%S")), ha='center')
    #ax.text(0, 1, 'Total = ' + str(round(total_time/1000,1)), ha='center')
    hours, minutes = get_hh_mm_from_ms(total_time)
    ax.text(0, 0, 'Total = ' + str(hours) + ':' + f"{minutes:02}", ha='center')
    #st.pyplot(fig)
    return fig
    

def get_time_entries(period):
    # get time entries within a time range
    # ref: https://clickup.com/api/clickupreference/operation/Gettimeentrieswithinadaterange/
    
    #hacemos una consulta para today que es rapido
    #st.write(isinstance(period,type(datetime.date)))
    #st.write(period)
    #st.write(type(period))
    #st.write(type(datetime.date))

    if period == 'current_week' or period == 'current_month' or period == 'all_time':
        #st.write('Collecting all time entries')
        start,end = get_start_end('all_time')
        url = "https://api.clickup.com/api/v2/team/" + team_id + "/time_entries"
        query = {
            "start_date": start,
            "end_date": end,
            "include_task_tags": "true",
            "include_location_names": "true",
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": API_KEY
        } 
    #if period == 'today' or isinstance(period,type(datetime.date)):
    #if isinstance(period,datetime.date):
    else: #if is datetime.date
        #st.write("Time entries for " + str(period) + ':')
        start,end = get_start_end(period)
        #start,end = get_start_end("today")
        url = "https://api.clickup.com/api/v2/team/" + team_id + "/time_entries"
        query = {
            "start_date": start,
            "end_date": end,
            "include_task_tags": "true",
            "include_location_names": "true",
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": API_KEY
        }
    try:
        response = requests.get(url, headers=headers, params=query)
        data = response.json()
        #print(data)
        data = data['data']
        data = pd.json_normalize(data,max_level=1)
        #print(data.dtypes)
        #st.write(data.columns)
        #print(data)
        data = data[['task.id','task.name','duration','at','task_location.space_name','task_location.folder_name','task_location.list_name','task.status']]
        data = data.rename(columns={'task.name':'task','duration':'miliseconds','at':'end_date','task_location.space_name':'space','task_location.folder_name':'folder','task_location.list_name':'list','task.status':'task_status'})
        #print(data)
        #print(pd.json_normalize(data['task_status'])['status'])
        data['task_status'] = pd.json_normalize(data['task_status'])['status']
        #print(data)
        data['end_date'] = pd.to_datetime(data['end_date'], unit='ms')
        #data['end_date'] = pd.to_numeric(data['end_date'])
        data['folder'] = data['folder'].str.replace('hidden','-')
        data['miliseconds'] = pd.to_numeric(data['miliseconds'])
        
    except: #da error si se borra una tarea de la que se ha registrado tiempo. Detectar
        data = "No time entries"
    #return merged
    #st.table(data)
    return data

#@st.cache()
def process_data_day(date,data):
    # filtramos para el periodo seleccionado (period start date < time entry 'end_date' value < now)
    start_ts, end_ts = get_start_end(date)
    #start_date = datetime.fromtimestamp(start_ts/1000.0)
    start_datetime = pd.to_datetime(start_ts, unit='ms')
    #st.write(isinstance(period,type(datetime.date)))

    #procesamos
    grouped = data.groupby(by=['task']).agg({'miliseconds':sum,'space':'first','folder':'first', 'list':'first', 'task.id':'first', 'task_status':'first'})
    #st.table(grouped)
    grouped['main_task'] = grouped.apply(lambda row:get_GrandParentName(grouped, row['task.id'], tasks),axis=1)            
    #st.table(grouped)
    #delete deleted tasks
    grouped.drop(grouped[grouped.main_task == 'deleted'].index, inplace=True)
    #st.table(merged)
    #print(merged)
    grouped = grouped.sort_values(by=['space', 'folder', 'list', 'main_task'])

    grouped.loc['Total'] = grouped.sum()
    #st.table(merged)
    grouped.loc['Total',['task_status','main_task','space','folder','list']] = '-'
    #st.table(merged)
    #merged['hh:mm:ss'] = pd.to_datetime(merged['miliseconds'],unit='ms').dt.strftime('%H:%M:%S:%f').str[:-7] 
    grouped['hh:mm'] = pd.to_datetime(grouped['miliseconds'],unit='ms').dt.strftime('%H:%M:%S:%f').str[:-10] 
    report = grouped[['task_status','main_task','space','folder','list','hh:mm']]
    #st.table(report)
    return report


@st.cache_data()
def process_data_period(period, data):
    # filtramos para el periodo seleccionado (period start date < time entry 'end_date' value < now)
    start_ts, end_ts = get_start_end(period)
    #start_date = datetime.fromtimestamp(start_ts/1000.0)
    start_datetime = pd.to_datetime(start_ts, unit='ms')
    #st.write(isinstance(period,type(datetime.date)))
    if period == 'current_week' or period == 'current_month' or period == 'all_time':   # if today or a single day, data is already filtered
        data = data.loc[data['end_date'] > start_datetime]  #seleccionamos time entries que terminan despues del primer dia seleccionado
    #procesamos
    grouped = data.groupby(by=['task']).agg({'miliseconds':sum,'space':'first','folder':'first', 'list':'first', 'task.id':'first', 'task_status':'first'})
    grouped['main_task'] = grouped.apply(lambda row:get_GrandParentName(grouped, row['task.id'], tasks), axis=1)            
    #delete deleted tasks
    grouped.drop(grouped[grouped.main_task == 'deleted'].index, inplace=True)
    #print(merged)
    grouped = grouped.sort_values(by=['space', 'folder', 'list', 'main_task'])
    #st.write(period)
    #st.write(type(period))
    #if period == 'today' or isinstance(period,type(datetime.date)):

    grouped_2 = grouped.groupby(by=['space']).sum()
    grouped_2.loc['Total'] = grouped_2.sum()
    #grouped['hh:mm:ss'] = pd.to_datetime(grouped['miliseconds'],unit='ms').dt.strftime('%H:%M:%S:%f').str[:-7] 
    grouped_2['hh:mm'] = pd.to_datetime(grouped_2['miliseconds'],unit='ms').dt.strftime('%H:%M:%S:%f').str[:-10] 
    report = grouped_2[['hh:mm','miliseconds']]       
    return report



#######################
#                     # 
# USER AUTHENTICATION #
#                     # 
#######################

def password_entered():
    """Checks whether a password entered by the user is correct."""
    if st.session_state["password"] == st.secrets["password"]:
        st.session_state["password_correct"] = True
        #del st.session_state["password"]  # don't store password
    else:
        st.session_state["password_correct"] = False


def check_password():
    """Returns `True` if the user had the correct password."""

    #def password_entered():
    #    """Checks whether a password entered by the user is correct."""
     #   if st.session_state["password"] == st.secrets["password"]:
      #      st.session_state["password_correct"] = True
       #     del st.session_state["password"]  # don't store password
        #else:
         #   st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct.
        return True



#############
#           #
#   LAYOUT  #
#           #
#############

if check_password():
    st.header('ClickUp time tracking dashboard')    
    tasks = get_all_tasks()
    #st.table(tasks)
    spaces = get_spaces()
    #st.table(spaces)
    report_figs = []
    report_tables = []
    if st.button('Reload'):
        st.experimental_rerun()
    st.subheader('Time at tasks in Day')
    date_selected = st.date_input("Choose a day",value=date.today(), min_value = date(2022,10,7), max_value = date.today())
    day_data = get_time_entries(date_selected)
    if isinstance(day_data, pd.DataFrame):
        day_data_processed = process_data_day(date_selected,day_data)
        report_tables.append(day_data_processed)
        st.table(day_data_processed)
    else:
        st.write('No time entries')
    
    all_data = get_time_entries('all_time')
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader('Current week')
        current_week = process_data_period('current_week',all_data)
        if isinstance(current_week, pd.DataFrame):
            #st.table(current_week)
            fig = pie_chart(current_week['miliseconds'].drop('Total'))
            st.pyplot(fig)
        else:
            st.write('No time entries')
    with col2:
        st.subheader('Current month')
        current_month = process_data_period('current_month',all_data)
        if isinstance(current_month, pd.DataFrame):
            #st.table(current_month)
            fig = pie_chart(current_month['miliseconds'].drop('Total'))
            st.pyplot(fig)
            report_figs.append(fig)            
        else:
            st.write('No time entries')
    with col3:
        st.subheader('All time')
        #st.table(get_time_entries('all_time')[['hh:mm:ss']])
        #pie_chart(process_data_period('all_time',all_data)['miliseconds'].drop('Total'))
        all_time = process_data_period('all_time',all_data)
        #st.table(all_time)
        fig = pie_chart(all_time['miliseconds'].drop('Total'))
        st.pyplot(fig)
        #report_items.append(fig)
    
    export_as_pdf = st.button("Export Report")
    if export_as_pdf:
        create_pdf_report(report_figs, report_tables)
    
        

