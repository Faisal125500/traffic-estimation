from flask import Flask, request, jsonify, render_template, send_from_directory
import os
import osmnx as ox
import networkx as nx
import folium
import requests

app = Flask(__name__)

# Preload and cache the map for Dhaka
MAP_FILE = "graph_dhaka.graphml"
if not os.path.exists(MAP_FILE):
    G = ox.graph_from_place("Dhaka, Bangladesh", network_type="drive")
    ox.save_graphml(G, MAP_FILE)
else:
    G = ox.load_graphml(MAP_FILE)

# OpenWeatherMap API key (replace with your own key)
WEATHER_API_KEY = "3606c35bf23931a5a86ec656c90c8865"

# Function to fetch weather data
def get_weather_factor():
    weather_url = f"http://api.openweathermap.org/data/2.5/weather?lat=23.7291&lon=90.4112&appid={WEATHER_API_KEY}"
    try:
        response = requests.get(weather_url)
        response.raise_for_status()
        weather = response.json().get('weather', [{}])[0].get('main', 'Clear')
        if weather == "Rain":
            return 1.3  # Increased travel time during rain
        elif weather == "Clear":
            return 1.0
        else:
            return 1.1
    except Exception as e:
        print(f"Weather fetch failed: {e}")
        return 1.0  # Default weather factor

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/calculate", methods=["POST"])
def calculate():
    try:
        data = request.json
        source_lat = float(data["source_lat"])
        source_lon = float(data["source_lon"])
        dest_lat = float(data["dest_lat"])
        dest_lon = float(data["dest_lon"])

        # Get the nearest nodes
        source_node = ox.distance.nearest_nodes(G, source_lon, source_lat)
        dest_node = ox.distance.nearest_nodes(G, dest_lon, dest_lat)

        # Calculate shortest path and distance
        shortest_path = nx.shortest_path(G, source_node, dest_node, weight="length")
        travel_distance = nx.shortest_path_length(G, source_node, dest_node, weight="length")

        # Adjust travel time based on weather
        base_speed_kmh = 30  # Average speed in km/h
        base_time_seconds = (travel_distance / 1000) / (base_speed_kmh / 60) * 60  # Convert to seconds
        base_time = base_time_seconds/60
        weather_factor = get_weather_factor()
        adjusted_time_seconds = base_time_seconds * weather_factor
        travel_time_minutes = adjusted_time_seconds / 60

        # Generate the route map
        m = folium.Map(location=[source_lat, source_lon], zoom_start=12)
        route_coords = [(G.nodes[node]['y'], G.nodes[node]['x']) for node in shortest_path]
        folium.PolyLine(route_coords, color="blue", weight=5, opacity=0.8).add_to(m)
        folium.Marker([source_lat, source_lon], popup="Source", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker([dest_lat, dest_lon], popup="Destination", icon=folium.Icon(color="red")).add_to(m)
        map_file = "static/route_map.html"
        m.save(map_file)

        return jsonify({
            "travel_time": f"{travel_time_minutes:.2f} minutes",
            'base_time': f"{base_time:.2f}minutes",

            "map_url": "/static/route_map.html"  # Send the relative path of the map
        })
    except Exception as e:
        return jsonify({"error": str(e)})

# Ensure static files can be served
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

if __name__ == "__main__":
    app.run(debug=True)
