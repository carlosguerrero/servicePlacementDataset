import os
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# Find the latest simulation folder dynamically based on script location
current_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "Simulations_raw"))
sim_folders = [f for f in os.listdir(base_dir) if f.startswith("Sim_")]
sim_folders.sort()
latest_sim_folder = os.path.join(base_dir, sim_folders[-1])

events = []

for filename in os.listdir(latest_sim_folder):
    if filename.startswith("Simulation") and filename.endswith(".json"):
        filepath = os.path.join(latest_sim_folder, filename)
        with open(filepath, 'r') as f:
            data = json.load(f)
            if "action" in data and "action" in data["action"]:
                act = data["action"]["action"]
                if act is not None:
                    events.append(act)

# Sort by time
events.sort(key=lambda x: x["time"])

# Group lanes
swimlane_map = {
    "user": "Usuarios",
    "app": "Aplicaciones",
    "graph": "Infraestructura"
}

# Colors
def get_color(action_name):
    action_name = action_name.lower()
    if any(x in action_name for x in ["new", "resume", "revive", "restore", "clear", "create"]):
        return "green"
    elif any(x in action_name for x in ["remove", "disable", "drop"]):
        return "red"
    else:
        return "orange"

records = []
lines_x = []
lines_y = []
lines_hover = []
transient_starts = {}

for e in events:
    lane = swimlane_map.get(e["type_object"], "Infraestructura")
    color = get_color(e["action"])
    act = e["action"]
    obj_id = e.get("object_id")
    msg = e.get("message", "")
    
    # Tooltip text
    hover_text = f"<b>Tipo:</b> {act}<br><b>Detalle:</b> {msg}<br><b>Entidad:</b> {obj_id if obj_id else 'N/A'}"
    
    records.append({
        "Tiempo": e["time"],
        "Carril": lane,
        "Evento": act,
        "Hover": hover_text,
        "Color": color
    })

    # Track transient events to draw connecting lines
    unique_key = str(obj_id)
    if act in ["degrade_random_node", "restore_node", "disable_random_node", "revive_node"]:
        match = re.search(r"Node (\d+)", msg)
        if match:
            unique_key = f"{obj_id}_node_{match.group(1)}"
    elif act in ["congest_random_edge", "clear_edge", "disable_random_edge", "revive_edge"]:
        match = re.search(r"Edge (\([^)]+\))", msg)
        if match:
            unique_key = f"{obj_id}_edge_{match.group(1)}"
    elif act in ["suspend_user", "suspend_random_user", "resume_user"]:
        # obj_id para usuarios ya es único, pero podemos asegurar
        unique_key = f"{obj_id}_user"

    if act in ["surge_popularity", "drop_popularity", "degrade_random_node", "congest_random_edge", "disable_random_node", "disable_random_edge", "suspend_user", "suspend_random_user"] and ("Transient" in msg or "Scheduled" in msg or "suspend" in act):
        transient_starts[unique_key] = e
    elif act in ["restore_popularity", "restore_node", "clear_edge", "revive_node", "revive_edge", "resume_user"] and unique_key in transient_starts:
        start_e = transient_starts.pop(unique_key)
        lines_x.extend([start_e["time"], e["time"], None])
        lines_y.extend([lane, lane, None])
        lines_hover.extend([
            f"Duración: {e['time'] - start_e['time']:.2f}s ({start_e['action']} -> {act})",
            f"Duración: {e['time'] - start_e['time']:.2f}s ({start_e['action']} -> {act})",
            None
        ])

df = pd.DataFrame(records)

fig = go.Figure()

name_map = {"green": "Creación/Recuperación", "orange": "Modificación/Movilidad", "red": "Destrucción/Caída"}
colors = {"green": "#2ca02c", "orange": "#ff7f0e", "red": "#d62728"}

if lines_x:
    fig.add_trace(go.Scatter(
        x=lines_x,
        y=lines_y,
        mode="lines",
        line=dict(color="purple", width=4, dash="dot"),
        name="Eventos Transitorios",
        text=lines_hover,
        hoverinfo="text"
    ))

for color in ["green", "orange", "red"]:
    df_color = df[df["Color"] == color]
    if df_color.empty:
        continue
    
    fig.add_trace(go.Scatter(
        x=df_color["Tiempo"],
        y=df_color["Carril"],
        mode="markers",
        marker=dict(size=12, color=colors[color], opacity=0.7, line=dict(width=1, color="white")),
        name=name_map[color],
        text=df_color["Hover"], # Text for hover
        hoverinfo="x+y+text"
    ))

fig.update_layout(
    title="Swimlane Scatter Plot - Eventos del Computing Continuum",
    xaxis_title="Tiempo de Simulación (Unidades)",
    yaxis_title="Capa / Entidad",
    yaxis=dict(categoryorder="array", categoryarray=["Infraestructura", "Aplicaciones", "Usuarios"]),
    xaxis=dict(showgrid=True, gridwidth=1, gridcolor='LightGrey'),
    plot_bgcolor='white',
    hovermode="closest",
    font=dict(family="Arial, sans-serif", size=14)
)

# Export to HTML
output_file = os.path.join(latest_sim_folder, "grafica_eventos.html")
fig.write_html(output_file)
print(f"Gráfica interactiva generada con éxito en:\n{output_file}")
