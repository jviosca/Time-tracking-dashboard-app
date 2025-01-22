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
from dateutil.relativedelta import relativedelta
import pytz
import sys
import os

# Añadir el directorio raíz del proyecto a sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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

###################
#                 #
#  AUX FUNCTIONS  #
#                 # 
###################


def filter_finished_subtasks(subtasks_id):
    list_subtasks = []
    list_subtasks_ids = subtasks_id.split(',')
    for subtask_id in list_subtasks_ids:
        subtask_status = tasks.loc[tasks['id'] == subtask_id]['status'].values[0]
        if  subtask_status == 'done' or subtask_status == 'completed': #devolvemos solo si la subtarea esta terminada
            if subtask_id not in tasks['parent'].unique().tolist() and tasks.loc[tasks['id'] == subtask_id]['parent'].values[0] != None: #devolvemos solo si la subtask no es main_task o no tiene subtareas
                list_subtasks.append(tasks.loc[tasks['id'] == subtask_id]['name'].values[0])
    list_subtasks = list(set(list_subtasks))
    list_subtasks_str = '; '.join(list_subtasks)
    return list_subtasks_str


#@st.cache #cache is not worth for this function
def get_start_end_month(year,month):
    reference_time = datetime.utcfromtimestamp(0)
    if year == date.today().year and month == date.today().month:
        start_date = date(date.today().year, date.today().month, 1)
        end = int((datetime.now() - reference_time).total_seconds() * 1000.0)  
        midnight = datetime.combine(start_date, time())
        start = int((midnight - reference_time).total_seconds() * 1000.0)        
    else:
        start_date = date(year,month,1)
        end_date = date(year,month,1) + relativedelta(day=31)
        midnight_start = datetime.combine(start_date, time())
        midnight_end = datetime.combine(end_date, time())
        start = int((midnight_start - reference_time).total_seconds() * 1000.0)
        end = int((midnight_end - reference_time).total_seconds() * 1000.0)
    return start,end


def get_hh_mm_from_ms_column(miliseconds):
    hours, minutes = get_hh_mm_from_ms(miliseconds)
    return str(hours) + ':' + f"{minutes:02}"


def pie_chart(df):
    fig,ax = plt.subplots()
    x = df.values
    explode = []
    for i in range(len(x)):
        explode.append(0.05)
    total_time = sum(df.values)
    df = df.to_frame()
    plt.pie(x, labels=df.index.tolist(), autopct=lambda pcg: get_hh_mm_from_pcg(pcg, total_time), pctdistance=0.72, explode=explode) 
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
    

def get_time_entries_month(year,month):
    # get time entries within a time range
    # ref: https://clickup.com/api/clickupreference/operation/Gettimeentrieswithinadaterange/
    
    start,end = get_start_end_month(year,month)
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
        data = data[['task.id','task.name','duration','start','end','at','task_location.space_name','task_location.folder_name','task_location.list_name','task.status']]
        data = data.rename(columns={'task.name':'task','duration':'miliseconds','start':'start_date','end':'end_date','at':'at_date','task_location.space_name':'space','task_location.folder_name':'folder','task_location.list_name':'list','task.status':'task_status'})
        #print(data)
        #print(pd.json_normalize(data['task_status'])['status'])
        data['task_status'] = pd.json_normalize(data['task_status'])['status']
        #print(data)
        data['at_date'] = pd.to_datetime(data['at_date'], unit='ms', utc=True).map(lambda x: x.tz_convert('Europe/Madrid'))
        data['start_date'] = pd.to_datetime(data['start_date'], unit='ms', utc=True).map(lambda x: x.tz_convert('Europe/Madrid'))
        data['end_date'] = pd.to_datetime(data['end_date'], unit='ms', utc=True).map(lambda x: x.tz_convert('Europe/Madrid'))
        #data['end_date'] = pd.to_numeric(data['end_date'])
        data['folder'] = data['folder'].str.replace('hidden','-')
        data['miliseconds'] = pd.to_numeric(data['miliseconds'])
    except: #da error si se borra una tarea de la que se ha registrado tiempo. Detectar
        data = "No time entries"
    #return merged
    return data


@st.cache_data()
def process_data_month(data,report_type):
    st.write(data)
    data['main_task'] = data.apply(lambda row:get_GrandParentName(data, row['task.id'], tasks),axis=1)
    data['location'] = data.apply(lambda row: row['space'] + '-' + row['folder'] if row['folder'] != '-' else row['space'], axis=1)
    data['tasks (locations)'] = data['main_task'] + ' (' + data['location'] + ')'
    data.drop(data[data.main_task == 'deleted'].index, inplace=True)
    if report_type == 'Grouped by days':
        #st.table(data)
        data = data.set_index('at_date')
        #grouped = data.resample('D').agg({'miliseconds':sum,'start_date':'first','end_date':'last','main_task':lambda x: '; '.join(set(x)) if len(set(x))>0 else "", 'location':lambda x:'; '.join(set(x))}) 
        grouped = data.resample('D').agg({'miliseconds':sum,'start_date':'first','end_date':'last','tasks (locations)':lambda x: '; '.join(set(x)) if len(set(x))>0 else "-"}) 
        grouped = grouped.rename(columns={'main_task':'main_tasks'})
        grouped.index = grouped.index.strftime('%d/%m/%Y')
        grouped.loc['Total'] = grouped.sum()
        grouped['hh:mm'] = pd.to_datetime(grouped['miliseconds'],unit='ms').dt.strftime('%H:%M:%S:%f').str[:-10] 
        grouped['start_time'] = grouped['start_date'].dt.strftime('%H:%M:%S:%f').str[:-10]
        grouped['end_time'] = grouped['end_date'].dt.strftime('%H:%M:%S:%f').str[:-10]
        grouped.loc['Total',['start_time','end_time','main_tasks','tasks (locations)']] = '-'
        hours, minutes = get_hh_mm_from_ms(grouped.loc['Total', 'miliseconds'])
        grouped.loc['Total', 'hh:mm'] = str(hours) + ':' + f"{minutes:02}"
        grouped = grouped.fillna('-')
        report = grouped[['hh:mm','start_time','end_time','tasks (locations)']]
    elif report_type == 'Grouped by tasks':
        #procesamos
        data['at_date'] = data['at_date'].dt.strftime('%d')
        #st.table(data)
        #grouped = data.groupby(by=['main_task']).agg({'miliseconds':sum, 'task_status':'first', 'space':'first','folder':'first', 'list':'first', 'task.id':'first','at_date':lambda x:','.join(set(x))})
        grouped = data.groupby(by=['main_task']).agg({'miliseconds':sum, 'space':'first','folder':'first', 'list':'first','at_date':lambda x:','.join(set(x)), 'task.id': lambda x: ','.join(set(x))})
        grouped = grouped.rename(columns={'task.id':'subtasks_id'})
        grouped['at_date'] = grouped['at_date'].str.split(',').apply(sorted).str.join(', ')
        grouped['subtasks_finished'] = grouped.apply(lambda row: filter_finished_subtasks(row['subtasks_id']),axis=1)
        #st.table(grouped.drop(columns='subtasks_id'))
        merged = grouped.merge(tasks[['name','status']], left_on ='main_task', right_on ='name', how='left')
        merged = merged.rename(columns={'name':'main_task'})
        merged = merged.set_index('main_task')
        #st.table(merged.drop(columns='subtasks_id'))
        #merged = merged.drop_duplicates()
        #st.table(merged)
        #st.table(grouped)
        merged = merged.sort_values(by=['space', 'folder', 'list', 'status','miliseconds','main_task'])
        #st.table(merged)
        #merged = merged.fillna('-')
        merged.loc['Total'] = merged.sum()
        #st.table(merged)
        #merged['hh:mm'] = pd.to_datetime(merged['miliseconds'],unit='ms').dt.strftime('%H:%M:%S:%f').str[:-10] 
        merged['hh:mm'] = merged.apply(lambda row: get_hh_mm_from_ms_column(row['miliseconds']),axis=1)
        hours, minutes = get_hh_mm_from_ms(merged.loc['Total', 'miliseconds'])
        merged.loc['Total', 'hh:mm'] = str(hours) + ':' + f"{minutes:02}"
        merged.loc['Total',['status','space','folder','list','at_date', 'subtasks_finished','main_task']] = '-' 
        report = merged[['status','subtasks_finished','space','folder','list','at_date','hh:mm']]   
        report = report.fillna('-')    
        
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
    report_figs = []
    report_tables = []
    if st.button('Reload'):
        st.experimental_rerun()
    st.subheader('Monthly report: ')
    CurrentYear = datetime.now().year
    CurrentMonth = datetime.now().month
    #st.write()
    #months = {1:'January',10:'October',11:'November'}
    #st.write(months[10])
    report_type = None
    col1, col2, col3 = st.columns(3)
    with col1:
        year = st.selectbox('Choose a year', range(2022, CurrentYear + 1))
    with col2:
        if year:
            if CurrentYear == 2022:
                month = st.selectbox('Choose a month', range(10, CurrentMonth + 1), index = len(range(10, CurrentMonth)))
            else:
                month = st.selectbox('Choose a month', range(1, CurrentMonth + 1), index = len(range(1, CurrentMonth)))
    with col3:
        if month:
            month_data = get_time_entries_month(year,month)
            if isinstance(month_data, pd.DataFrame):
                #st.table(tasks)
                #st.table(month_data)
                report_type = st.selectbox('Choose a report type', ('Grouped by days','Grouped by tasks'), index = 0)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write('Month/Year selected: ' + str(month) + '/' + str(year))
    with col3:
        if report_type:
            st.write('Report selected: ' + str(report_type))
        else:
            st.write('No report type selected.')
    month_data_processed = process_data_month(month_data,report_type)
    st.table(month_data_processed)
    report_tables.append(month_data_processed)
    
    export_as_pdf = st.button("Export Report")
    if export_as_pdf:
        create_pdf_report(report_figs, report_tables)
        

