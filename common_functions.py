import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
from tempfile import NamedTemporaryFile
import base64
from datetime import datetime

#################################################################
#                                                               #  
# Access to ClickUp personal workspace (see streamlit secrets)  #
#                                                               #
#################################################################
team_id = st.secrets["team_id"] #workspace personal
API_KEY = st.secrets["API_KEY"]

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
    #st.table(str(data.dtypes))
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


def get_ParentID(task_id, tasks):
    if task_id in tasks['id'].unique().tolist():
        parentID = tasks.loc[tasks['id'] == task_id]['parent'].values[0]
    else:
        parentID = None
    return parentID
    
    

def get_GrandParentID(task_id, tasks):
    #print("get_GrandParentID, received : " + str(task_id))
    IDs = []
    parentID = get_ParentID(task_id, tasks)
    #print(parentID)
    IDs.append(parentID)
    while parentID != None:
        parentID = get_ParentID(parentID, tasks)
        IDs.append(parentID)
    if len(IDs)>1:
        GrandParentID = IDs[-2]
    else:
        GrandParentID = task_id
    #print("get_GrandParentID, returned : " + str(GrandParentID))
    return GrandParentID
    
    
def get_GrandParentName(df,task_id, tasks):
    #print("get_GrandParentName, received : " + str(task_id))
    GrandParentID = get_GrandParentID(task_id, tasks)
    #print(GrandParentID)
    if task_id in tasks['id'].unique().tolist():
        GrandParentName = tasks.loc[tasks['id'] == GrandParentID]['name'].values[0]
    else: #if task has been deleted
        GrandParentName = 'deleted'
    #print("get_GrandParentName, returned : " + str(GrandParentName))
    return GrandParentName


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

def df2report(df):
    fig, ax = plt.subplots()
    ax.set_axis_off()
    the_table = ax.table(cellText=df.values, rowLabels=df.index, colLabels=df.columns)
    the_table.auto_set_font_size(False)
    the_table.set_fontsize(8)
    st.pyplot(fig)
    return fig
    
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
            if top + row_height_lines > 260 or row_height_lines > 50: # si el cursor baja mucho, insertamos pagina y reseteamos el cursor a la parte superior del pdf (A4 tiene 297 mm de altura)
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
