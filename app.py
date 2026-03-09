import fastf1
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import os

from dash import Dash, dcc, html, Input, Output
import dash_bootstrap_components as dbc

# -----------------------------
# FASTF1 CACHE
# -----------------------------

# create cache folder if it doesn't exist
if not os.path.exists("cache"):
    os.makedirs("cache")

fastf1.Cache.enable_cache("./cache")

YEAR = 2025

circuits = [
    "Australia","Bahrain","Saudi Arabia","Azerbaijan","Miami","Monaco",
    "Spain","Canada","Austria","Britain","Hungary","Belgium","Netherlands",
    "Italy","Singapore","Japan","Qatar","United States","Mexico","Brazil","Abu Dhabi"
]

# -----------------------------
# DASH APP
# -----------------------------

app = Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])

app.layout = dbc.Container([

    html.H1(
        "F1 Telemetry Analytics Dashboard",
        style={"textAlign":"center"}
    ),

    # CIRCUIT SELECTOR
    dbc.Row([
        dbc.Col([
            html.Label("Select Circuit"),
            dcc.Dropdown(
                id="circuit",
                options=[{"label":c, "value":c} for c in circuits],
                value="Brazil",
                clearable=False
            )
        ])
    ]),

    html.Br(),

    # DRIVER SELECTORS
    dbc.Row([
        dbc.Col([
            html.Label("Driver 1"),
            dcc.Dropdown(id="driver1")
        ]),
        dbc.Col([
            html.Label("Driver 2"),
            dcc.Dropdown(id="driver2")
        ])
    ]),

    html.Br(),

    dcc.Graph(id="track_map", style={"height":"650px"}),

    html.Div(id="sector_table"),

    dbc.Row([
        dbc.Col(dcc.Graph(id="speed_graph")),
        dbc.Col(dcc.Graph(id="delta_graph"))
    ]),

    dcc.Graph(id="position_graph"),

    dcc.Graph(id="tyre_graph")

], fluid=True)

# -----------------------------
# DRIVER DROPDOWN UPDATE
# -----------------------------

@app.callback(
    [
        Output("driver1","options"),
        Output("driver2","options"),
        Output("driver1","value"),
        Output("driver2","value")
    ],
    Input("circuit","value")
)
def update_driver_dropdown(circuit):

    session = fastf1.get_session(YEAR, circuit, "R")
    session.load()

    drivers = sorted(session.laps['Driver'].unique())
    options = [{"label":d, "value":d} for d in drivers]

    return options, options, drivers[0], drivers[1]


# -----------------------------
# MAIN DASHBOARD CALLBACK
# -----------------------------

@app.callback(
    [
        Output("track_map","figure"),
        Output("sector_table","children"),
        Output("speed_graph","figure"),
        Output("delta_graph","figure"),
        Output("position_graph","figure"),
        Output("tyre_graph","figure")
    ],
    [
        Input("circuit","value"),
        Input("driver1","value"),
        Input("driver2","value")
    ]
)

def update_dashboard(circuit, driver1, driver2):

    try:

        session = fastf1.get_session(YEAR, circuit, "R")
        session.load()

        laps1 = session.laps.pick_drivers(driver1)
        laps2 = session.laps.pick_drivers(driver2)

        lap1 = laps1.pick_fastest()
        lap2 = laps2.pick_fastest()

        tel1 = lap1.get_car_data().add_distance().dropna()
        tel2 = lap2.get_car_data().add_distance().dropna()

        pos = lap1.get_pos_data()

        # ---------------- TRACK PERFORMANCE MAP ----------------

        speed1 = np.interp(
            np.linspace(0,1,len(pos)),
            np.linspace(0,1,len(tel1)),
            tel1["Speed"]
        )

        speed2 = np.interp(
            np.linspace(0,1,len(pos)),
            np.linspace(0,1,len(tel2)),
            tel2["Speed"]
        )

        speed_diff = speed1 - speed2

        track_fig = go.Figure()

        track_fig.add_trace(go.Scatter(
            x = pos["X"],
            y = pos["Y"],
            mode="markers",
            marker=dict(
                size=7,
                color=speed_diff,
                colorscale="RdBu",
                cmin=-20,
                cmax=20,
                colorbar=dict(title="Speed Advantage km/h")
            )
        ))

        track_fig.update_layout(
            title="Track Performance Map (Red=Driver1 Faster | Blue=Driver2 Faster)",
            template="plotly_dark"
        )

        track_fig.update_yaxes(scaleanchor="x", scaleratio=1)

        # ---------------- SECTOR TABLE ----------------

        s1 = lap1["Sector1Time"].total_seconds()
        s2 = lap1["Sector2Time"].total_seconds()
        s3 = lap1["Sector3Time"].total_seconds()

        s1b = lap2["Sector1Time"].total_seconds()
        s2b = lap2["Sector2Time"].total_seconds()
        s3b = lap2["Sector3Time"].total_seconds()

        df = pd.DataFrame({
            "Sector":["Sector 1","Sector 2","Sector 3"],
            driver1:[round(s1,3),round(s2,3),round(s3,3)],
            driver2:[round(s1b,3),round(s2b,3),round(s3b,3)]
        })

        sector_table = dbc.Table.from_dataframe(
            df,
            striped=True,
            bordered=True,
            hover=True
        )

        # ---------------- SPEED GRAPH ----------------

        speed_fig = go.Figure()

        speed_fig.add_trace(go.Scatter(
            x=tel1["Distance"],
            y=tel1["Speed"],
            name=driver1
        ))

        speed_fig.add_trace(go.Scatter(
            x=tel2["Distance"],
            y=tel2["Speed"],
            name=driver2
        ))

        speed_fig.update_layout(
            title="Speed Telemetry Comparison",
            template="plotly_dark"
        )

        # ---------------- DELTA TIME ----------------

        delta = tel2["Time"] - tel1["Time"]
        delta = delta.dt.total_seconds()

        delta_fig = go.Figure()

        delta_fig.add_trace(go.Scatter(
            x=tel1["Distance"],
            y=delta,
            name="Delta Time"
        ))

        delta_fig.update_layout(
            title="Delta Time",
            template="plotly_dark"
        )

        # ---------------- POSITION EVOLUTION ----------------

        pos_fig = go.Figure()

        for drv in [driver1, driver2]:

            drv_laps = session.laps[session.laps["Driver"] == drv]

            drv_laps = drv_laps.sort_values("LapNumber")

            pos_fig.add_trace(go.Scatter(
                x=drv_laps["LapNumber"],
                y=drv_laps["Position"],
                mode="lines+markers",
                name=drv
    ))

        pos_fig.update_layout(
        title="Race Position Evolution",
        template="plotly_dark",
        yaxis=dict(
            autorange="reversed",
            title="Position"
        ),
        xaxis_title="Lap"
)

        # ---------------- TYRE DEGRADATION ----------------

        tyre_fig = go.Figure()

        tyre_fig.add_trace(go.Scatter(
            x=laps1["LapNumber"],
            y=laps1["LapTime"].dt.total_seconds(),
            name=driver1
        ))

        tyre_fig.add_trace(go.Scatter(
            x=laps2["LapNumber"],
            y=laps2["LapTime"].dt.total_seconds(),
            name=driver2
        ))

        tyre_fig.update_layout(
            title="Tyre Degradation (Lap Time Trend)",
            template="plotly_dark"
        )

        return track_fig, sector_table, speed_fig, delta_fig, pos_fig, tyre_fig

    except Exception as e:

        print(e)

        return (
            go.Figure(),
            html.Div("Error loading data"),
            go.Figure(),
            go.Figure(),
            go.Figure(),
            go.Figure()
        )


# -----------------------------
# RUN APP
# -----------------------------

import os

server = app.server

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)