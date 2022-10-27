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

#store all tasks in a dataframe. Se utiliza para no mostrar time entries de tareas eliminadas y tambien para obtener la Parent Task
#@st.cache()
def get_tasks(page):
    # ref: https://clickup.com/api/clickupreference/operation/GetFilteredTeamTasks/
    url = "https://api.clickup.com/api/v2/team/" + team_id + "/task"
    query = {
        "page": page,
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
    #st.table(tasks) 
    return tasks


def get_all_tasks():
    result = pd.DataFrame()
    page = 0
    df = get_tasks(page)
    result = pd.concat([result,df])
    #while len(result) == 100:
    while len(result) % 100 == 0: # resto de division es 0 si es multiplo
        try: #si solo hay 99 entradas pero no hay dos paginas, evitar error
            page = page + 1
            df = get_tasks(page)
            result = pd.concat([result,df])
        except:
            break
    return result


def get_ParentID_old(task_id):
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


def get_ParentID(task_id):
    if task_id in tasks['id'].unique().tolist():
        parentID = tasks.loc[tasks['id'] == task_id]['parent'].values[0]
    else:
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
    grouped['main_task'] = grouped.apply(lambda row:get_GrandParentName(grouped, row['task.id']),axis=1)            
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
    grouped = data.groupby(by=['task']).agg({'miliseconds':sum,'space':'first','folder':'first', 'list':'first', 'task.id':'first', 'task_status':'first'})
    grouped['main_task'] = grouped.apply(lambda row:get_GrandParentName(grouped, row['task.id']),axis=1)            
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



def create_download_link(val, filename):
    b64 = base64.b64encode(val)  # val looks like b'...'
    return f'<a href="data:application/octet-stream;base64,{b64.decode()}" download="{filename}.pdf">Download file</a>'


def create_pdf_report(report_figs, report_tables):
    pdf = FPDF(orientation = 'P', unit = 'mm', format='A4')
    pdf.set_font("Arial", size=12)
    if len(report_figs)>0:
        pdf.add_page()
    for fig in report_figs:
        #pdf.add_page()
        pdf.cell(0,h=20,txt = "Current month:", align = 'C', ln=2)
        with NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
            fig.savefig(tmpfile.name)
            #pdf.image(tmpfile.name, 10, 10, 200, 100)
            pdf.image(tmpfile.name, w= 200)
    for df in report_tables:
        pdf.set_fill_color(230)
        pdf.add_page()
        pdf.cell(0,h=20,txt = "Tasks at selected day: " + str(date_selected), align = 'C', ln=2)
        pdf.set_font("Times", size=8)
        df = df.reset_index()
        line_height = pdf.font_size * 2.5
        table_width = pdf.w - (2 * pdf.l_margin)
        col_width = table_width / df.shape[1]  # distribute content evenly
        top = pdf.y
        x_col = 0     
        #colocamos nombres columnas               
        for column in df.columns: 
            pdf.y = top
            pdf.x = pdf.x + (x_col * col_width)
            #pdf.multi_cell(col_width, line_height, str(column), border = 1, align = 'L', fill = True)
            pdf.multi_cell(col_width, line_height, column, border = 1, align = 'L', fill = True)
            x_col = x_col + 1
        #colocamos valores df
        x_col = 0
        top = top + line_height # bajamos top la altura de la fila anterior con los nombres de columnas
        
        # ref https://github.com/PyFPDF/fpdf2/issues/91
        line_height = pdf.font_size * 1.5 # smaller cell height for tasks
        for row in range(df.shape[0]):
            row_height_lines = 1
            lines_in_row = []
            for column in range(df.shape[1]): # determine height of highest cell
                output = pdf.multi_cell(col_width, line_height, df.iloc[row,column], border=1, align = 'L', split_only=True)
                lines_in_row.append(len(output))
                if len(output) > row_height_lines:
                    row_height_lines = len(output)
            if top + row_height_lines > 270: # si el cursor baja mucho, insertamos pagina y reseteamos el cursor a la parte superior del pdf (A4 tiene 297 mm de altura)
                pdf.add_page()
                top = 10
            x_col = 0
            for tlines,column in zip(lines_in_row,range(df.shape[1])):
                text = df.iloc[row,column].rstrip('\n') + (1 + row_height_lines - tlines) * '\n'
                text = text.replace(u"\u2018", "'").replace(u"\u2019", "'")
                pdf.y = top
                pdf.x = pdf.x + (x_col * col_width)
                pdf.set_fill_color(245)
                if column == (df.shape[1] - 1) or row == (df.shape[0] - 1): # fill cells in column hh:mm and row Totals
                    pdf.multi_cell(col_width, line_height, text, border=1, align = 'L', fill = True)
                else:
                    pdf.multi_cell(col_width, line_height, text, border=1, align = 'L')

                x_col = x_col + 1
            x_col = 0
            top = pdf.y
        
    try:
        html = create_download_link(pdf.output(dest="S").encode("latin-1"), "report")
    except:
        html = create_download_link(pdf.output(dest="S").encode("cp1252","ignore"), "report")
    st.markdown(html, unsafe_allow_html=True)


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
            fig = pie_chart(current_week['miliseconds'].drop('Total'))
            st.pyplot(fig)
        else:
            st.write('No time entries')
    with col2:
        st.subheader('Current month')
        current_month = process_data_period('current_month',all_data)
        if isinstance(current_month, pd.DataFrame):
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
        create_pdf_report(report_figs, report_tables)
    
        

