#$ pip install -r requirements.txt
#%%
import pandas as pd
import dash
from dash import html
from dash import dcc
from dash.dependencies import Output, Input, State
from datetime import date, timedelta, datetime
from dash import dash_table
import plotly.express as px
import plotly.graph_objects as go
import plotly.subplots as ps
import myfitnesspal
#%%
macro_cols = ['fat','carbohydrates','protein']
#%%
def mfp_df_cleanup(df):
    df.dropna(axis='columns',how='all',inplace=True)
    col_list = df.columns.to_list()
    col_list.remove('date')
    col_list.remove('meal')
    col_list_set = set(col_list)
    if 'description' in col_list_set:
        col_list.remove('description')
    df[col_list] = df[col_list].astype('float64')
    return df
#%%
def mfp_dash(df, meal):
    df['DATEINDEX'] = pd.to_datetime(df['date'])
    df = df.set_index(['DATEINDEX'])
    macro_df = df.groupby(['date','meal']).sum()
    date_macro_df = macro_df.groupby(['date']).sum()
    mean_macro_df = macro_df.groupby('meal')[macro_cols].mean()
    date_macro_df.reset_index(inplace=True)
    return date_macro_df, mean_macro_df
#%%
def make_c_df(client, s_date):
    c_df = pd.DataFrame()
    c_dict = {}
    c_day = client.get_date(s_date)
    c_meal = c_day.keys()
    c_date_value = {'date': c_day.date.strftime('%Y-%m-%d')}
    c_dict.update(c_date_value)
    i = 0
    while i < len(c_meal):
        if len(c_day.meals[i]) > 0:
            c_meal_value = {'meal': c_meal[i]}
            c_dict.update(c_meal_value)
            j = 0
            while j < len(c_day.meals[i].entries):
                c_item = {'description': c_day.meals[i].entries[j].name}
                c_dict.update(c_item)
                c_dict.update(c_day.meals[i].entries[j].totals)
                c_df = c_df.append(c_dict, ignore_index=True)
                j +=1
        i +=1

    c_df = mfp_df_cleanup(c_df)
    c_df_col_list = c_df.columns.to_list()
    c_df_col_list.remove('date')
    c_df_col_list.remove('meal')
    c_df_col_list.remove('description')
    c_df_col_list.insert(0,'date')
    c_df_col_list.insert(1,'meal')
    c_df_col_list.insert(2,'description')
    c_df = c_df[c_df_col_list]
    columns = [{'name': col, 'id': col} for col in c_df.columns]
    data = c_df.to_dict(orient='records')
    return columns, data
#%%
def conn(user, pwd):
    conn = myfitnesspal.Client(user, password=pwd)
    return conn
#%%
def get_weight(conn,s_date, e_date):
    w_df = pd.DataFrame()
    weight = conn.get_measurements('Weight',s_date,e_date)
    w_df = w_df.append(weight,ignore_index=True)
    w_df = w_df.transpose()
    return w_df
#%%
def get_cals(conn, s_date, e_date):
    df = pd.DataFrame(columns=['date','meal','calories','carbohydrates','fat','protein','sodium','fiber','sugar'])
    delta = timedelta(days=1)

    temp_dict = {}

    while s_date <= e_date:
        day = conn.get_date(s_date)
        meal = day.keys()
        date_value = {'date': day.date.strftime('%Y-%m-%d')}
        temp_dict.update(date_value)
        i = 0
        while i < len(meal):
            meal_value = {'meal': meal[i]}
            temp_dict.update(meal_value)
            if len(day.meals[i]) == 0:
                for key in temp_dict.keys():
                    if key not in ['date','meal']:
                        temp_dict[key] = 0
            else:
                temp_dict.update(day.meals[i].totals)
            df = df.append(temp_dict, ignore_index=True)
            i += 1
        s_date += delta

    return df, meal
#%%
app = dash.Dash(__name__,suppress_callback_exceptions=True)

app.layout = html.Div([
    html.H1('MFP Dashboard', style={
        'text-align':'center',
        'display':'inline-block',
        'padding':'1%'
    }
            ),
    html.Div([
        html.I('Please enter your login for MyFitnessPal and select a date range:', style={'padding':'1%'}),
        html.Div([
            html.Br([]),
            html.H4('Username: ', style={'padding':'1%',  'display':'inline-block'}),
            dcc.Input(id="mfp_user", type="text", placeholder="", style={'padding':'1%',  'display':'inline-block'}),
            html.H4('Password: ', style={'padding':'1%',  'display':'inline-block'}),
            dcc.Input(id="mfp_pass", type="password", placeholder="", style={'padding':'1%',  'display':'inline-block'}),
            html.H4('Date Range: ', style={'padding':'1%',  'display':'inline-block'}),
            dcc.DatePickerRange(
                id='date_range_picker',
                style={'padding':'1%',  'display':'inline-block'}
            ),
            html.Button(id='submit-button-state', n_clicks=0, children='Get Data', style={'padding':'2%',  'display':'inline-block'})
        ],           style={'width':'90%'}
        )
    ]),
    html.Br([]),
    html.Div(
        children=[
            html.Div(
                children=[
                    dcc.Graph(id='w_graph', style={'width':'65%', 'padding':'1%',  'display':'inline-block'}),
                    dcc.Graph(id='macro_bar', style={'width':'25%', 'padding':'1%',  'display':'inline-block'})
                ],
            ),
            html.Div(children=[dash_table.DataTable(id='mfp_table', data = [{}])], style={'display':'block', 'width':'90%', 'padding':'1%'}),

        ],
        style={'padding':'1%','border':'1px solid black'})
])

@app.callback(
    Output(component_id='w_graph', component_property='figure'),
    Output(component_id='macro_bar', component_property='figure'),
    Input(component_id='submit-button-state', component_property='n_clicks'),
    State(component_id='mfp_user', component_property='value'),
    State(component_id='mfp_pass', component_property='value'),
    State(component_id='date_range_picker', component_property='start_date'),
    State(component_id='date_range_picker', component_property='end_date')
)

def load_graphs(n_clicks, mfp_user, mfp_pass, start_date, end_date):
    s_date = datetime.date(datetime.strptime(start_date,'%Y-%m-%d'))
    e_date = datetime.date(datetime.strptime(end_date,'%Y-%m-%d'))
    client = conn(mfp_user, mfp_pass)
    w_df = get_weight(client, s_date, e_date)

    df, meal = get_cals(client,s_date,e_date)

    df = mfp_df_cleanup(df)
    date_macro_df, mean_macro_df = mfp_dash(df,meal)

    macro_bar = px.bar(mean_macro_df)
    macro_bar.update_layout(yaxis_title='Grams (g)', xaxis_title='Meal', title={'text':'Avg. Macros by Meal','y':0.95,'x':0.5,'xanchor': 'center','yanchor': 'top'})

    w_fig = ps.make_subplots(specs=[[{"secondary_y": True}]])
    w_fig.add_trace(go.Bar(
        x = date_macro_df['date'],
        y = date_macro_df['calories'],
        name='Calories'),
        secondary_y=False
    )
    w_fig.add_trace(go.Scatter(
        x=w_df.index,
        y=w_df[0],
        name='Weight (lbs)'),
        secondary_y=True
    )
    w_fig.update_yaxes(title_text="Calories", secondary_y=False)
    w_fig.update_yaxes(title_text="Weight (lbs)", secondary_y=True)
    w_fig.update_layout(title={'text':'Daily Calories and Weight','y':0.95,'x':0.5,'xanchor': 'center','yanchor': 'top'})

    return w_fig, macro_bar

@app.callback(
    Output(component_id='mfp_table', component_property='data'),
    Output(component_id='mfp_table', component_property='columns'),
    Input(component_id='w_graph', component_property='hoverData'),
    State(component_id='mfp_user', component_property='value'),
    State(component_id='mfp_pass', component_property='value'),
    prevent_initial_call=True
)

def update_table(hoverData, mfp_user, mfp_pass):
    if hoverData:
        hover_date = hoverData['points'][0]['x']
        hover_date = datetime.strptime(hover_date,'%Y-%m-%d')
        client = conn(mfp_user, mfp_pass)
        columns, data = make_c_df(client, hover_date)

        return data, columns

if __name__ == '__main__':
    app.run_server()