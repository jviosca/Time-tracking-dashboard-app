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

#store all tasks in a dataframe
#@st.cache()
def get_tasks():
    # ref: https://clickup.com/api/clickupreference/operation/GetFilteredTeamTasks/
    url = "https://api.clickup.com/api/v2/team/" + team_id + "/task"
    query = {
        "reverse": "true",
        "subtasks": "true",
        "include_closed": "true",
        "team_id": team_id
    }
    headers = {"Authorization": API_KEY}
    response = requests.get(url, headers=headers, params=query)
    data = response.json()
    data = data['tasks']
    data = pd.json_normalize(data)
    #print(data.dtypes)
    tasks = data[['id','name','archived','status.status','time_spent','parent','start_date','due_date']]
    tasks = tasks.rename(columns={'status.status':'status'})
    #procesar columna id y name para que sea string y no object
    #tasks['id'] = tasks['id'].astype('string')
    #tasks['name'] = tasks['name'].astype('string')
    #tasks['parent'] = tasks['parent'].astype('string')
    #procesar columna start_date y due_date para que sea una fecha y no un object
    tasks['start_date'] = pd.to_datetime(tasks['start_date'], unit='ms')
    tasks['due_date'] = pd.to_datetime(tasks['due_date'], unit='ms')
    #tasks.dtypes
    #tasks    
    return tasks


def get_ParentID(task_id):
    # ref: https://clickup.com/api/clickupreference/operation/GetTask/
    #print("get_ParentID, received : " + str(task_id))
    url = "https://api.clickup.com/api/v2/task/" + task_id

    query = {
        "custom_task_ids": "true",
        "team_id": team_id,
        "include_subtasks": "true"
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": API_KEY
    }

    try:
        response = requests.get(url, headers=headers, params=query)
        data = response.json()
        data = pd.json_normalize(data)
        #data.dtypes
        #print(data)
        task_subtasks = data[['id','name','orderindex', 'parent', 'linked_tasks']]
        parentID = task_subtasks['parent'].values[0]
    except: #if subtask is deleted
        parentID = None
    return parentID


def get_GrandParentID(task_id):
    #print("get_GrandParentID, received : " + str(task_id))
    IDs = []
    parentID = get_ParentID(task_id)
    #print(parentID)
    IDs.append(parentID)
    while parentID != None:
        parentID = get_ParentID(parentID)
        IDs.append(parentID)
    if len(IDs)>1:
        GrandParentID = IDs[-2]
    else:
        GrandParentID = task_id
    #print("get_GrandParentID, returned : " + str(GrandParentID))
    return GrandParentID
    
    
def get_GrandParentName(df,task_id):
    #print("get_GrandParentName, received : " + str(task_id))
    GrandParentID = get_GrandParentID(task_id)
    #print(GrandParentID)
    if task_id in tasks['id'].unique().tolist():
        GrandParentName = tasks.loc[tasks['id'] == GrandParentID]['name'].values[0]
    else: #if task has been deleted
        GrandParentName = 'deleted'
    #print("get_GrandParentName, returned : " + str(GrandParentName))
    return GrandParentName

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

def get_hh_mm_from_pcg(pcg,total):
    #st.write(datetime.fromtimestamp(total/1000.0,tz=timezone.utc).strftime("%H:%M:%S"))
    #st.write(pcg)
    miliseconds = pcg * total / 100
    #processed = datetime.fromtimestamp(miliseconds/1000.0,tz=timezone.utc).strftime("%H:%M:%S")
    #processed = timedelta(hours = 36)
    totsec = int(miliseconds / 1000)
    h = totsec//3600
    m = (totsec%3600) // 60
    sec =(totsec%3600)%60 #just for reference
    #print "%d:%d" %(h,m)
    #st.write(processed)
    #return "{}\n({}%)".format(processed,int(pcg))
    return "{}:{:02}\n({}%)".format(h,m,int(pcg))

def get_hh_mm_from_ms(ms):
    totsec = int(ms / 1000)
    h = totsec//3600
    m = (totsec%3600) // 60
    sec =(totsec%3600)%60 #just for reference
    return h,m

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


def df2report(df):
    fig, ax = plt.subplots()
    ax.set_axis_off()
    the_table = ax.table(cellText=df.values, rowLabels=df.index, colLabels=df.columns)
    the_table.auto_set_font_size(False)
    the_table.set_fontsize(8)
    st.pyplot(fig)
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
    return data

@st.cache()
def process_data_day(date,data):
    # filtramos para el periodo seleccionado (period start date < time entry 'end_date' value < now)
    start_ts, end_ts = get_start_end(date)
    #start_date = datetime.fromtimestamp(start_ts/1000.0)
    start_datetime = pd.to_datetime(start_ts, unit='ms')
    #st.write(isinstance(period,type(datetime.date)))

    #procesamos
    grouped = data.groupby(by=['task']).sum()
    merged = grouped.merge(data.groupby(by=['task']).first()['space'].to_frame(),on='task').merge(data.groupby(by=['task']).first()['folder'].to_frame(),on='task').merge(data.groupby(by=['task']).first()['list'].to_frame(),on='task').merge(data.groupby(by=['task']).first()['task.id'].to_frame(),on='task').merge(data.groupby(by=['task']).first()['task_status'].to_frame(),on='task')
    merged['main_task'] = merged.apply(lambda row:get_GrandParentName(merged, row['task.id']),axis=1)            
    #delete deleted tasks
    merged.drop(merged[merged.main_task == 'deleted'].index, inplace=True)
    #print(merged)
    merged = merged.sort_values(by=['space', 'folder', 'list', 'main_task'])
    #st.write(period)
    #st.write(type(period))
    #if period == 'today' or isinstance(period,type(datetime.date)):

    merged.loc['Total'] = merged.sum()
    merged.loc['Total',['task_status','main_task','space','folder','list']] = '-'
    #merged['hh:mm:ss'] = pd.to_datetime(merged['miliseconds'],unit='ms').dt.strftime('%H:%M:%S:%f').str[:-7] 
    merged['hh:mm'] = pd.to_datetime(merged['miliseconds'],unit='ms').dt.strftime('%H:%M:%S:%f').str[:-10] 
    report = merged[['task_status','main_task','space','folder','list','hh:mm']]
     
    return report


@st.cache()
def process_data_period(period, data):
    # filtramos para el periodo seleccionado (period start date < time entry 'end_date' value < now)
    start_ts, end_ts = get_start_end(period)
    #start_date = datetime.fromtimestamp(start_ts/1000.0)
    start_datetime = pd.to_datetime(start_ts, unit='ms')
    #st.write(isinstance(period,type(datetime.date)))
    if period == 'current_week' or period == 'current_month' or period == 'all_time':   # if today or a single day, data is already filtered
        data = data.loc[data['end_date'] > start_datetime]  #seleccionamos time entries que terminan despues del primer dia seleccionado
    #procesamos
    grouped = data.groupby(by=['task']).sum()
    merged = grouped.merge(data.groupby(by=['task']).first()['space'].to_frame(),on='task').merge(data.groupby(by=['task']).first()['folder'].to_frame(),on='task').merge(data.groupby(by=['task']).first()['list'].to_frame(),on='task').merge(data.groupby(by=['task']).first()['task.id'].to_frame(),on='task').merge(data.groupby(by=['task']).first()['task_status'].to_frame(),on='task')
    merged['main_task'] = merged.apply(lambda row:get_GrandParentName(merged, row['task.id']),axis=1)            
    #delete deleted tasks
    merged.drop(merged[merged.main_task == 'deleted'].index, inplace=True)
    #print(merged)
    merged = merged.sort_values(by=['space', 'folder', 'list', 'main_task'])
    #st.write(period)
    #st.write(type(period))
    #if period == 'today' or isinstance(period,type(datetime.date)):

    grouped = merged.groupby(by=['space']).sum()
    grouped.loc['Total'] = grouped.sum()
    #grouped['hh:mm:ss'] = pd.to_datetime(grouped['miliseconds'],unit='ms').dt.strftime('%H:%M:%S:%f').str[:-7] 
    grouped['hh:mm'] = pd.to_datetime(grouped['miliseconds'],unit='ms').dt.strftime('%H:%M:%S:%f').str[:-10] 
    report = grouped[['hh:mm','miliseconds']]       
    return report



def create_download_link(val, filename):
    b64 = base64.b64encode(val)  # val looks like b'...'
    return f'<a href="data:application/octet-stream;base64,{b64.decode()}" download="{filename}.pdf">Download file</a>'





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
    tasks = get_tasks()
    report_figs = []
    report_tables = []
    #if "load_state" not in st.session_state:
     #   st.session_state.load_state = False
    #st.write(st.session_state.load_state)
    if st.button('Reload'):
        #st.session_state.load_state = True
        #st.stop()
        st.experimental_rerun()
    st.subheader('Time at tasks in Day')
    date_selected = st.date_input("Choose a day",value=date.today(), min_value = date(2022,10,7), max_value = date.today())
    #if date_selected == date.today():
    #    day_data = get_time_entries('today')
     #   if isinstance(day_data,pd.DataFrame): #si hay time entries
      #      day_data_processed = process_data('today',day_data)
    #else: #date_selected no es today
     #   day_data = get_time_entries(date_selected)
     #   day_data_processed = process_data(date_selected,day_data)
    day_data = get_time_entries(date_selected)
    if isinstance(day_data, pd.DataFrame):
    #day_data_processed = process_data(date_selected,day_data)
        day_data_processed = process_data_day(date_selected,day_data)
        #report_tables.append(df2report(day_data_processed))
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
            #st.table(current_week[['hh:mm:ss']])
            #pie_chart(current_week['miliseconds'].drop('Total'))
            fig = pie_chart(current_week['miliseconds'].drop('Total'))
            st.pyplot(fig)
            #report_items.append(fig)
        else:
            st.write('No time entries')
    with col2:
        st.subheader('Current month')
        current_month = process_data_period('current_month',all_data)
        if isinstance(current_month, pd.DataFrame):
            #st.table(current_month[['hh:mm:ss']])
            #pie_chart(current_month['miliseconds'].drop('Total'))
            fig = pie_chart(current_month['miliseconds'].drop('Total'))
            st.pyplot(fig)
            report_figs.append(fig)            
        else:
            st.write('No time entries')
    with col3:
        st.subheader('All time')
        #st.table(get_time_entries('all_time')[['hh:mm:ss']])
        #pie_chart(process_data_period('all_time',all_data)['miliseconds'].drop('Total'))
        fig = pie_chart(process_data_period('all_time',all_data)['miliseconds'].drop('Total'))
        st.pyplot(fig)
        #report_items.append(fig)
    export_as_pdf = st.button("Export Report")
    if export_as_pdf:
        pdf = FPDF(orientation = 'P', unit = 'mm', format='A4')
        pdf.set_font("Times", size=8)
        #pdf.add_page()
        for fig in report_figs:
            pdf.add_page()
            with NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
                fig.savefig(tmpfile.name)
                #pdf.image(tmpfile.name, 10, 10, 200, 100)
                pdf.image(tmpfile.name, w= 200)
        for df in report_tables:
            df = df.reset_index()
            pdf.add_page()
            line_height = pdf.font_size * 2.5
            epw = pdf.w - (2 * pdf.l_margin)
            col_width = epw / 7  # distribute content evenly
            x_col = 0
            top = pdf.y
            #colocamos los nombres de las columnas
            #for column_name,column_content in df.items():
             #   offset = pdf.x + (x_col * col_width)
              #  pdf.y = top                
               # pdf.x = offset
               # pdf.multi_cell(col_width, line_height, column_name, border=1) #first row
               # pdf.ln(line_height)
               # for item in column_content:
               #     pdf.y = top                
                #    pdf.x = offset
                 #   pdf.multi_cell(col_width, line_height, item, border=1)
                #x_col = x_col + 1
            
            #x_col = 0
            #top = pdf.y + line_height            
            #for column_name,column_content in df.items():
            #    offset = pdf.x + (x_col * col_width)
            #    pdf.y = top                
            #    pdf.x = offset
            #    pdf.multi_cell(col_width, line_height, column_content[1], border=1)
            #    pdf.ln(line_height)
            #    x_col = x_col + 1                
            #for column_name,column_content in df.items():
             #   offset = pdf.x + (x_col * col_width)
              #  pdf.y = top                
               # pdf.x = offset
                #pdf.multi_cell(col_width, line_height, column_content[0] + ' | ' + column_content[1] + ' | ' + column_content[2], border=1)
                #pdf.ln(line_height)
                #x_col = x_col + 1
            #x_col = 0
            #top = pdf.y + line_height                                    
            #for rowIndex, row in df.iterrows(): #iterate over rows
             #   offset = pdf.x + (x_col * col_width)
             #   pdf.y = top
             #   for columnIndex, value in row.items():
              #      pdf.x = offset
               #     pdf.multi_cell(col_width, line_height, value, border=1)
               # pdf.ln(line_height)
                #x_col = x_col + 1
            columns = list(df)
            for i in columns:
                rows = list(df[i]):
                for j in rows:
                    offset = pdf.x + (x_col * col_width)
                    pdf.y = top                
                    pdf.x = offset
                    pdf.multi_cell(col_width, line_height, df[i][j], border=1) 
                    pdf.ln(line_height)
                    x_col = x_col + 1
        html = create_download_link(pdf.output(dest="S").encode("latin-1"), "report")
        st.markdown(html, unsafe_allow_html=True)
        

