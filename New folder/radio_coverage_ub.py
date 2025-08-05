import os
import numpy as np
import matplotlib.pyplot as plt
import geopandas as gpd
import rasterio
import requests
import osmnx as ox
from shapely.geometry import box
import folium
from folium import plugins
import json

# --- 1. Define Area of Interest (Ulaanbaatar, Mongolia) ---
CITY_NAME = "Ulaanbaatar, Mongolia"

# --- 2. Download and Preprocess Data ---
def download_osm_data(city_name):
    """Download OSM data (buildings, roads, landuse) for the city."""
    # Placeholder: Use osmnx to get building footprints
    return ox.geometries_from_place(city_name, tags={"building": True})

def download_tower_data(city_name):
    """Download tower and antenna data from OSM."""
    # Download various tower types
    tower_tags = {
        "tower": True,
        "man_made": ["tower", "communications_tower", "antenna"],
        "building": ["tower", "communications_tower"],
        "amenity": "telephone"
    }
    
    towers = {}
    for tag_key, tag_value in tower_tags.items():
        try:
            if isinstance(tag_value, list):
                for value in tag_value:
                    data = ox.geometries_from_place(city_name, tags={tag_key: value})
                    if not data.empty:
                        towers[f"{tag_key}_{value}"] = data
            else:
                data = ox.geometries_from_place(city_name, tags={tag_key: tag_value})
                if not data.empty:
                    towers[f"{tag_key}_{tag_value}"] = data
        except Exception as e:
            print(f"Error downloading {tag_key}: {e}")
    
    return towers

def extract_tower_heights(osm_towers):
    """Extract height information from OSM tower data."""
    tower_heights = []
    
    for tower_type, tower_data in osm_towers.items():
        if tower_data.empty:
            continue
            
        for idx, tower in tower_data.iterrows():
            height_info = {}
            height_info['type'] = tower_type
            height_info['geometry'] = tower.geometry
            height_info['coordinates'] = (tower.geometry.centroid.y, tower.geometry.centroid.x)
            
            # Extract height from various possible tags
            height_tags = ['height', 'building:height', 'tower:height', 'ele']
            for tag in height_tags:
                if tag in tower and tower[tag] is not None:
                    try:
                        height_info['height_m'] = float(tower[tag])
                        break
                    except (ValueError, TypeError):
                        continue
            
            # If no height found, try to estimate from building levels
            if 'height_m' not in height_info:
                if 'building:levels' in tower and tower['building:levels'] is not None:
                    try:
                        levels = float(tower['building:levels'])
                        height_info['height_m'] = levels * 3.0  # Estimate 3m per level
                        height_info['estimated'] = True
                    except (ValueError, TypeError):
                        pass
            
            if 'height_m' in height_info:
                tower_heights.append(height_info)
    
    return tower_heights

def download_dem(city_name):
    """Download SRTM DEM data for the city area."""
    # Placeholder: Use SRTM or other DEM source
    # You can use 'elevation' or 'rasterio' with AWS S3
    return None

def download_population_data(city_name):
    """Download WorldPop or other open population data for the city area."""
    # Placeholder: Download and clip WorldPop raster
    return None

def download_satellite_imagery(city_name):
    """Download Sentinel-2 or Landsat imagery for the city area."""
    # Placeholder: Use SentinelHub, Google Earth Engine, or open API
    return None

# --- 3. Feature Extraction ---
def extract_land_cover(sat_image):
    """Extract land cover types from satellite imagery (simple thresholding or ML)."""
    # Placeholder: Use NDVI or simple color thresholding
    return None

def extract_buildings(osm_data):
    """Extract building footprints from OSM data."""
    # Placeholder: Filter building polygons
    return osm_data[osm_data.geometry.type == 'Polygon']

def analyze_tower_shadows(satellite_image, tower_locations):
    """Analyze satellite imagery to detect tower shadows for height estimation."""
    # This would require high-resolution satellite imagery
    # and shadow analysis algorithms
    # Placeholder for shadow-based height estimation
    return None

# --- 4. Radio Propagation Modeling ---
def hata_model(tx_height, rx_height, freq_mhz, distance_km, city_size='large'):
    """Hata model for urban areas (returns path loss in dB)."""
    # Correction factor for mobile antenna height (urban)
    a_hm = (1.1 * np.log10(freq_mhz) - 0.7) * rx_height - (1.56 * np.log10(freq_mhz) - 0.8)
    L = (
        69.55 + 26.16 * np.log10(freq_mhz)
        - 13.82 * np.log10(tx_height)
        - a_hm
        + (44.9 - 6.55 * np.log10(tx_height)) * np.log10(distance_km)
    )
    return L

def predict_coverage(dem, buildings, tx_location, tx_height, tx_power_dbm, freq_mhz):
    """Predict radio coverage over a grid using the Hata model."""
    # Define grid size and area (about 10x10 km around transmitter)
    lat0, lon0 = tx_location
    grid_size = 200  # 200x200 grid
    km_per_deg = 111  # Approximate
    area_km = 10
    dlat = area_km / km_per_deg
    dlon = area_km / (km_per_deg * np.cos(np.radians(lat0)))
    lats = np.linspace(lat0 - dlat/2, lat0 + dlat/2, grid_size)
    lons = np.linspace(lon0 - dlon/2, lon0 + dlon/2, grid_size)
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    # Calculate distance from transmitter to each grid point (in km)
    dists = np.sqrt(((lat_grid - lat0) * km_per_deg) ** 2 + ((lon_grid - lon0) * km_per_deg * np.cos(np.radians(lat0)) ) ** 2)
    dists[ dists < 0.01 ] = 0.01  # Avoid log(0)

    # Calculate path loss and received power
    rx_height = 1.5  # meters
    path_loss = hata_model(tx_height, rx_height, freq_mhz, dists)
    rx_power = tx_power_dbm - path_loss
    return {
        'lat_grid': lat_grid,
        'lon_grid': lon_grid,
        'rx_power': rx_power
    }

# --- 5. Visualization ---
def plot_coverage_map(coverage, city_name, buildings=None):
    """Plot and save a heatmap of radio coverage over the city."""
    plt.figure(figsize=(10, 8))
    if coverage is not None:
        plt.pcolormesh(coverage['lon_grid'], coverage['lat_grid'], coverage['rx_power'], cmap='hot', shading='auto')
        plt.colorbar(label='Received Power (dBm)')
    if buildings is not None and hasattr(buildings, 'plot'):
        buildings.plot(ax=plt.gca(), facecolor='none', edgecolor='blue', linewidth=0.5)
    plt.title(f"Radio Coverage Heatmap - {city_name}")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.savefig("coverage_heatmap.png")
    plt.close()

def create_tower_map(tower_heights, city_name):
    """Create an interactive map showing towers with their heights."""
    # Center map on Ulaanbaatar
    center_lat, center_lon = 47.9212, 106.9186
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
    
    for tower in tower_heights:
        lat, lon = tower['coordinates']
        height = tower.get('height_m', 'Unknown')
        tower_type = tower['type']
        estimated = tower.get('estimated', False)
        
        # Color code by height
        if isinstance(height, (int, float)):
            if height < 20:
                color = 'green'
            elif height < 50:
                color = 'orange'
            else:
                color = 'red'
        else:
            color = 'gray'
        
        # Create popup with tower information
        popup_text = f"""
        <b>Tower Type:</b> {tower_type}<br>
        <b>Height:</b> {height}m<br>
        <b>Estimated:</b> {'Yes' if estimated else 'No'}<br>
        <b>Coordinates:</b> {lat:.4f}, {lon:.4f}
        """
        
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_text, max_width=300),
            icon=folium.Icon(color=color, icon='tower', prefix='fa')
        ).add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Save the map
    m.save("tower_height_map.html")
    print("Interactive tower map saved as 'tower_height_map.html'")
    
    return m

def generate_tower_report(tower_heights):
    """Generate a summary report of detected towers."""
    if not tower_heights:
        print("No towers with height information found.")
        return
    
    heights = [t['height_m'] for t in tower_heights if 'height_m' in t and isinstance(t['height_m'], (int, float))]
    
    print(f"\n=== Tower Height Report ===")
    print(f"Total towers with height data: {len(heights)}")
    
    if heights:
        print(f"Average height: {np.mean(heights):.1f}m")
        print(f"Minimum height: {np.min(heights):.1f}m")
        print(f"Maximum height: {np.max(heights):.1f}m")
        print(f"Height distribution:")
        
        # Create height histogram
        plt.figure(figsize=(8, 6))
        plt.hist(heights, bins=10, edgecolor='black')
        plt.xlabel('Height (meters)')
        plt.ylabel('Number of Towers')
        plt.title('Tower Height Distribution')
        plt.savefig("tower_height_distribution.png")
        plt.close()
        print("Height distribution plot saved as 'tower_height_distribution.png'")

# --- 6. Main Workflow ---
def main():
    print(f"Processing area: {CITY_NAME}")
    
    # Download OSM data
    osm_data = download_osm_data(CITY_NAME)
    tower_data = download_tower_data(CITY_NAME)
    
    # Extract tower heights
    tower_heights = extract_tower_heights(tower_data)
    
    # Generate reports and visualizations
    if tower_heights:
        generate_tower_report(tower_heights)
        create_tower_map(tower_heights, CITY_NAME)
    else:
        print("No tower height data found. Consider:")
        print("1. Checking if towers exist in the area")
        print("2. Using satellite imagery analysis")
        print("3. Using LiDAR data if available")
        print("4. Manual height measurements")
    
    # Continue with existing workflow
    dem = download_dem(CITY_NAME)
    population = download_population_data(CITY_NAME)
    sat_image = download_satellite_imagery(CITY_NAME)

    buildings = extract_buildings(osm_data)
    land_cover = extract_land_cover(sat_image)

    # Example transmitter parameters
    tx_location = (47.9212, 106.9186)  # City center (lat, lon)
    tx_height = 30  # meters
    tx_power_dbm = 43  # 20W
    freq_mhz = 900

    coverage = predict_coverage(dem, buildings, tx_location, tx_height, tx_power_dbm, freq_mhz)
    plot_coverage_map(coverage, CITY_NAME, buildings)
    print("Coverage map saved as 'coverage_heatmap.png'.")

if __name__ == "__main__":
    main()