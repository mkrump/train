import datetime

import plotly.graph_objs as go
import dash
import dash_core_components as dcc
import dash_html_components as html
import requests
from dash.dependencies import Input, Output
from flask_caching import Cache
import pandas as pd
import logging

app = dash.Dash(__name__)
app.title = 'Blocked Crossings'
server = app.server
server.config.from_object("settings")
logging.basicConfig(level='INFO')

cache = Cache()
cache.init_app(
    app.server,
    config={
        "CACHE_DIR": server.config["CACHE_DIR"],
        "CACHE_TYPE": server.config["CACHE_TYPE"],
        "CACHE_DEFAULT_TIMEOUT": server.config["CACHE_DEFAULT_TIMEOUT"],
    }
)

MARKDOWN = '''
#### 
This dashboard summarizes the data found at [fra.dot.gov/blockedcrossings/](https://www.fra.dot.gov/blockedcrossings),
which is a site created by the Federal Railway Administration (FRA) that allows the public and law enforcement to report 
rail caused traffic blockages. The information gathered at [fra.dot.gov/blockedcrossings/](https://www.fra.dot.gov/blockedcrossings) is being used to 
track the location and impact of these events. **_So the next time you're waiting for the train to pass make sure to visit 
the FRA site to report it!_**

Select a city to view a summary of the incident reports for that particular city. 
Clear the city filter to see a national summary of the incident reports. 
'''

app.layout = html.Div(
    style={"marginTop": "5rem"},
    className="container",
    children=
    [
        html.Div(
            className="row app-row",
            children=[
                html.H1("Blocked Crossings"),
                dcc.Markdown(MARKDOWN)
            ],
        ),
        # TODO fix size of text on mobile?
        html.Div(
            className="row app-row",
            children=[
                html.Div(
                    className="one-half column",
                    children=[
                        html.Label("Select a City", className="select-city-label"),
                        dcc.Dropdown(id='demo-dropdown'),

                    ],
                )],
        ),
        html.Div(id='graph-container', className="u-max-full-width"),
        html.Div(id='ticker-text', className="row ticker-text"),
        dcc.Interval(id='interval', interval=server.config["UPDATE_INTERVAL"], n_intervals=0),
    ],
)


@cache.memoize()
def update_metrics():
    now = datetime.datetime.now().isoformat()
    logging.info("update_metrics - time: {0}".format(now))
    data = fetch_data()
    orig_df = pd.DataFrame(data)
    orig_df.dateTime = pd.to_datetime(orig_df.dateTime)
    orig_df.city = orig_df.city.str.title()
    orig_df["city_state"] = orig_df.city.str.title() + ", " + orig_df.state.str.upper()
    orig_df["labels"] = orig_df['city'] + "  (" + orig_df["state"] + ")"
    orig_df.street = orig_df.street.str.title()
    return orig_df, now


@app.callback(Output('ticker-text', 'children'),
              [Input('interval', 'n_intervals')])
def update_date(n_intervals):
    # call once and chain other dependent calls of this, so not making
    # api calls on every update
    _, now = update_metrics()
    return [html.P(f"Last update: {now}")]


@app.callback(
    Output('demo-dropdown', "options"),
    [Input('ticker-text', "children")])
def update_dropdown(children):
    orig_df, _ = update_metrics()
    # TODO would be nice not do this each time probably can cache too
    df = orig_df.drop_duplicates(subset=['city_state']).dropna()
    values = [{"label": label, "value": value} for label, value in zip(df['labels'], df['city_state']) if label]
    return sorted(values, key=lambda k: k['label'])


@app.callback(
    Output('graph-container', "children"),
    [
        Input('demo-dropdown', "value"),
        Input('ticker-text', "children")
    ]
)
def update_figure(city_state, _):
    figures = []
    now = datetime.datetime.now().isoformat()
    logging.info("update_figure {0}".format(now))
    orig_df, _ = update_metrics()
    if city_state is None:
        fig = top(orig_df, 25)
        figures.append(dcc.Graph(id="top_n", figure=fig, className="plot"))
        fig = by_day_scatter(orig_df)
        figures.append(dcc.Graph(id="by_day", figure=fig, className="plot"))
        fig = histogram(orig_df, "railroad",
                        layout_overrides={"title": "<b>Total Reports by Railroad Responsible for Blockage</b>"})
        figures.append(dcc.Graph(id="railroad", figure=fig, className="plot"))
        return figures

    dff = orig_df[orig_df["city_state"] == city_state]
    fig = by_day_scatter(dff)
    figures.append(dcc.Graph(id="by_day", figure=fig, className="plot"))
    fig = histogram(dff, "duration", layout_overrides={"title": "<b>Delay due to Blocked Crossing</b>"})
    figures.append(dcc.Graph(id="duration", figure=fig, className="plot"))
    fig = histogram(dff, "street", layout_overrides={"title": "<b>Street Where Blocked Crossing Reported</b>"})
    figures.append(dcc.Graph(id="street", figure=fig, className="plot"))
    fig = histogram(dff, "railroad",
                    layout_overrides={"title": "<b>Total Reports by Railroad Responsible for Blockage</b>"})
    figures.append(dcc.Graph(id="railroad", figure=fig, className="plot"))
    return figures


def fetch_data():
    # See https://www.reddit.com/r/learnpython/comments/6miped/help_python_ssl_validation_not_working_with_for_a/
    # Server looks to be mis-configured notice incomplete certificate chain
    # at https://www.ssllabs.com/ssltest/analyze.html?d=www.fra.dot.gov&s=204.68.196.100
    # Just downloaded and added full certificate chain.
    url = "https://www.fra.dot.gov/blockedcrossings/api/incidents"
    cert_path = server.config["FRA_DOT_GOV_CERT_PATH"]
    now = datetime.datetime.now().isoformat()
    r = requests.get(url, verify=cert_path)
    logging.info("fetch_data - time: {0}".format(now))
    return r.json()


def top(df, n):
    top_n = df[df.city_state.isin(df.city_state.value_counts().nlargest(n).index)]
    fig = go.Figure({
        "data": [
            {
                "x": top_n["city_state"],
                "type": "histogram",
            }
        ],
        "layout": {
            "title": {"text": f"<b>Blocked Crossings Reported by City (Top {n})</b>"},
            "xaxis": {"automargin": True},
            "yaxis": {
                "automargin": True,
                "title": {"text": "Count"}
            },
        },
    })
    fig.update_xaxes(categoryorder="total descending")
    return fig


def by_day_scatter(df, layout_overrides=None):
    by_day = df['dateTime'].dt.date.value_counts()
    by_day.index = pd.to_datetime(by_day.index)
    by_day = by_day.resample("D").sum().fillna(0)
    by_day = by_day.sort_index()
    layout = {
        "title": {"text": f"<b>Total Blocked Crossings Reported by Day</b>"},
        "xaxis": {"automargin": True},
        "yaxis": {
            "automargin": True,
            "title": {"text": "Count"}
        },
    }
    if layout_overrides:
        layout.update(layout_overrides)
    fig = go.Figure({
        "data": [
            {
                "type": "scatter",
                "x": by_day.index,
                "y": by_day,
                "mode": "lines+markers"
            }
        ],
        "layout": layout,
    })
    return fig


def histogram(df, column, layout_overrides=None):
    layout = {
        "xaxis": {"automargin": True},
        "yaxis": {
            "automargin": True,
            "title": {"text": "Count"}
        },
    }
    if layout_overrides:
        layout.update(layout_overrides)
    fig = go.Figure({
        "data": [
            {
                "x": df[column],
                "type": "histogram",
            }
        ],
        "layout": layout,
    })
    fig.update_xaxes(categoryorder="total descending")
    return fig


if __name__ == '__main__':
    app.run_server(host=server.config["HOST"], debug=server.config["DEBUG"], port=server.config["PORT"])
