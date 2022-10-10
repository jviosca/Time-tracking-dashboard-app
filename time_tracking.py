import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time, timedelta
import matplotlib.pyplot as plt

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
#  AUX FUNCTIONS  #
#                 # 
###################

#store all tasks in a dataframe
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
    if period == 'current_week':
        start_date = date.today() - timedelta(days=date.today().weekday())
    if period == 'current_month':
        start_date = date(date.today().year, date.today().month, 1)
    if period == 'all_time':
        start_date = date(2022, 10, 1) #1st of october was when I started the personal workspace
    midnight = datetime.combine(start_date, time())
    start = int((midnight - reference_time).total_seconds() * 1000.0)
    end = int((datetime.now() - reference_time).total_seconds() * 1000.0)    
    return start,end


def pie_chart(df):
	fig,ax = plt.subplots()
	#ax.plot(df, marker='o', ms='12', color = color)
	#ax.legend([legend])
	#plt.xticks([i for i in range(0,len(df.index))], [i for i in df.index],rotation=30)
	#plt.ylabel(ylabel)
	#st.pyplot(fig)
	#st.table(df)
	#st.write(df.squeeze())
	ax.pie(df.to_numpy()[0])
	#colors = ['#FF0000', '#0000FF', '#FFFF00', '#ADFF2F', '#FFA500']
	#explode = (0.05, 0.05, 0.05, 0.05, 0.05)
	#plt.pie(df, colors=colors, labels=df.index, autopct='%1.1f%%', pctdistance=0.85, explode=explode)
	#centre_circle = plt.Circle((0, 0), 0.70, fc='white')
	#fig = plt.gcf()
	#fig.gca().add_artist(centre_circle)
	#plt.title('Bar chart')
	#st.pyplot(fig)

def get_time_entries(period):
    # get time entries within a time range
    # ref: https://clickup.com/api/clickupreference/operation/Gettimeentrieswithinadaterange/
    start,end = get_start_end(period)
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
        #print(data)
        data = data[['task.id','task.name','duration','at','task_location.space_name','task_location.folder_name','task_location.list_name','task.status']]
        data = data.rename(columns={'task.name':'task','duration':'miliseconds','at':'end_date','task_location.space_name':'space','task_location.folder_name':'folder','task_location.list_name':'list','task.status':'task_status'})
        #print(data)
        #print(pd.json_normalize(data['task_status'])['status'])
        data['task_status'] = pd.json_normalize(data['task_status'])['status']
        #print(data)
        data['end_date'] = pd.to_datetime(data['end_date'], unit='ms')
        data['folder'] = data['folder'].str.replace('hidden','-')
        data['miliseconds'] = pd.to_numeric(data['miliseconds'])
        if period == 'today':
            grouped = data.groupby(by=['task']).sum()
            merged = grouped.merge(data.groupby(by=['task']).first()['space'].to_frame(),on='task').merge(data.groupby(by=['task']).first()['folder'].to_frame(),on='task').merge(data.groupby(by=['task']).first()['list'].to_frame(),on='task').merge(data.groupby(by=['task']).first()['task.id'].to_frame(),on='task').merge(data.groupby(by=['task']).first()['task_status'].to_frame(),on='task')
            merged['main_task'] = merged.apply(lambda row:get_GrandParentName(merged, row['task.id']),axis=1)            
            #delete deleted tasks
            merged.drop(merged[merged.main_task == 'deleted'].index, inplace=True)
            #print(merged)
            merged = merged.sort_values(by=['space', 'folder', 'list', 'main_task'])
            merged.loc['Total'] = merged.sum()
            merged.loc['Total',['task_status','main_task','space','folder','list']] = '-'
            merged['hh:mm:ss'] = pd.to_datetime(merged['miliseconds'],unit='ms').dt.strftime('%H:%M:%S:%f').str[:-7] 
            report = merged[['task_status','main_task','space','folder','list','hh:mm:ss']]
            
        else:
            grouped = data.groupby(by=['space']).sum()
            grouped.loc['Total'] = grouped.sum()
            grouped['hh:mm:ss'] = pd.to_datetime(grouped['miliseconds'],unit='ms').dt.strftime('%H:%M:%S:%f').str[:-7] 
            report = grouped[['hh:mm:ss','miliseconds']]
    except: #da error si se borra una tarea de la que se ha registrado tiempo. Detectar
        report = "No time entries"
    return report




#######################
#                     # 
# USER AUTHENTICATION #
#                     # 
#######################

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

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
	st.subheader('Today')
	today = get_time_entries('today')
	if isinstance(today, pd.DataFrame):
		st.table(today[['hh:mm:ss']])
	else:
		st.write('No time entries')
	col1, col2, col3 = st.columns(3)
	with col1:
		st.subheader('Current week')
		current_week = get_time_entries('current_week')
		if isinstance(current_week, pd.DataFrame):
			st.table(current_week[['hh:mm:ss']])
			pie_chart(current_week[['miliseconds']].drop('Total'))
		else:
			st.write('No time entries')
	with col2:
		st.subheader('Current month')
		current_month = get_time_entries('current_month')
		if isinstance(current_month, pd.DataFrame):
			st.table(current_month[['hh:mm:ss']])
		else:
			st.write('No time entries')
	with col3:
		st.subheader('All time')
		st.table(get_time_entries('all_time')[['hh:mm:ss']])

