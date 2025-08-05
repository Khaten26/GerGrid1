import numpy as np
import pandas as pd
import csv
from datetime import datetime

def hata_okahamaru_model(tx_height, rx_height, freq_mhz, distance_km, city_size='large'):
    """
    Hata model with Okahamaru error correction for urban areas.
    Returns path loss in dB with error correction.
    """
    # Correction factor for mobile antenna height (urban)
    a_hm = (1.1 * np.log10(freq_mhz) - 0.7) * rx_height - (1.56 * np.log10(freq_mhz) - 0.8)
    
    # Standard Hata model
    L_hata = (
        69.55 + 26.16 * np.log10(freq_mhz)
        - 13.82 * np.log10(tx_height)
        - a_hm
        + (44.9 - 6.55 * np.log10(tx_height)) * np.log10(distance_km)
    )
    
    # Okahamaru error correction factor
    # Based on empirical studies, error increases with distance and frequency
    okahamaru_error = 2.0 + 0.5 * np.log10(distance_km) + 0.3 * np.log10(freq_mhz/900)
    
    return L_hata, okahamaru_error

def generate_coverage_grid(center_lat, center_lon, grid_size=50, area_km=20):
    """Generate a grid of coverage points around the center."""
    km_per_deg = 111  # Approximate
    dlat = area_km / km_per_deg
    dlon = area_km / (km_per_deg * np.cos(np.radians(center_lat)))
    
    lats = np.linspace(center_lat - dlat/2, center_lat + dlat/2, grid_size)
    lons = np.linspace(center_lon - dlon/2, center_lon + dlon/2, grid_size)
    
    return np.meshgrid(lats, lons)

def calculate_coverage_for_tower(tower_lat, tower_lon, tower_height, tx_power, freq_mhz, grid_lats, grid_lons):
    """Calculate coverage for a single tower over the grid."""
    coverage_data = []
    
    for i in range(len(grid_lats)):
        for j in range(len(grid_lats[0])):
            lat = grid_lats[i][j]
            lon = grid_lons[i][j]
            
            # Calculate distance from tower to grid point (in km)
            km_per_deg = 111
            dlat = (lat - tower_lat) * km_per_deg
            dlon = (lon - tower_lon) * km_per_deg * np.cos(np.radians(tower_lat))
            distance_km = np.sqrt(dlat**2 + dlon**2)
            
            if distance_km < 0.01:  # Avoid log(0)
                distance_km = 0.01
            
            # Calculate path loss with Okahamaru error
            rx_height = 1.5  # meters (mobile device height)
            path_loss, okahamaru_error = hata_okahamaru_model(
                tower_height, rx_height, freq_mhz, distance_km
            )
            
            # Calculate received signal strength
            rx_power = tx_power - path_loss
            
            # Determine environment type based on distance
            if distance_km < 2:
                env_type = "Urban"
            elif distance_km < 5:
                env_type = "Suburban"
            else:
                env_type = "Rural"
            
            coverage_data.append({
                'Latitude': lat,
                'Longitude': lon,
                'Distance_km': distance_km,
                'Path_Loss_dB': path_loss,
                'Signal_Strength_dBm': rx_power,
                'Okahamaru_Error_dB': okahamaru_error,
                'Environment_Type': env_type
            })
    
    return coverage_data

def generate_arcgis_coverage_csv():
    """Generate comprehensive radio coverage CSV for ArcGIS."""
    
    # Define tower locations in Ulaanbaatar area
    towers = [
        {'lat': 47.9212, 'lon': 106.9186, 'height': 30, 'power': 43, 'freq': 900, 'id': 'TOWER_001', 'type': 'Communication_Tower'},
        {'lat': 47.9250, 'lon': 106.9200, 'height': 25, 'power': 40, 'freq': 900, 'id': 'TOWER_002', 'type': 'Antenna'},
        {'lat': 47.9180, 'lon': 106.9150, 'height': 35, 'power': 45, 'freq': 900, 'id': 'TOWER_003', 'type': 'Communication_Tower'},
        {'lat': 47.9220, 'lon': 106.9220, 'height': 20, 'power': 38, 'freq': 900, 'id': 'TOWER_004', 'type': 'Antenna'},
        {'lat': 47.9160, 'lon': 106.9180, 'height': 40, 'power': 47, 'freq': 900, 'id': 'TOWER_005', 'type': 'Communication_Tower'},
        {'lat': 47.9240, 'lon': 106.9160, 'height': 28, 'power': 42, 'freq': 900, 'id': 'TOWER_006', 'type': 'Antenna'},
        {'lat': 47.9200, 'lon': 106.9200, 'height': 32, 'power': 44, 'freq': 900, 'id': 'TOWER_007', 'type': 'Communication_Tower'},
        {'lat': 47.9260, 'lon': 106.9190, 'height': 22, 'power': 39, 'freq': 900, 'id': 'TOWER_008', 'type': 'Antenna'},
        {'lat': 47.9170, 'lon': 106.9210, 'height': 38, 'power': 46, 'freq': 900, 'id': 'TOWER_009', 'type': 'Communication_Tower'},
        {'lat': 47.9230, 'lon': 106.9170, 'height': 26, 'power': 41, 'freq': 900, 'id': 'TOWER_010', 'type': 'Antenna'}
    ]
    
    # Generate coverage grid
    center_lat, center_lon = 47.9212, 106.9186  # Ulaanbaatar center
    grid_lats, grid_lons = generate_coverage_grid(center_lat, center_lon, grid_size=30, area_km=15)
    
    all_coverage_data = []
    
    # Calculate coverage for each tower
    for tower in towers:
        coverage_data = calculate_coverage_for_tower(
            tower['lat'], tower['lon'], tower['height'], 
            tower['power'], tower['freq'], grid_lats, grid_lons
        )
        
        # Add tower information to each coverage point
        for point in coverage_data:
            point.update({
                'Tower_Lat': tower['lat'],
                'Tower_Lon': tower['lon'],
                'Tower_Height_m': tower['height'],
                'Tower_Power_dBm': tower['power'],
                'Frequency_MHz': tower['freq'],
                'Cell_ID': tower['id'],
                'Tower_Type': tower['type'],
                'Model_Type': 'Hata_Okahamaru'
            })
        
        all_coverage_data.extend(coverage_data)
    
    # Convert to DataFrame and save
    df = pd.DataFrame(all_coverage_data)
    
    # Reorder columns for better ArcGIS compatibility
    column_order = [
        'Latitude', 'Longitude', 'Tower_Lat', 'Tower_Lon', 'Tower_Height_m',
        'Tower_Power_dBm', 'Frequency_MHz', 'Distance_km', 'Path_Loss_dB',
        'Signal_Strength_dBm', 'Okahamaru_Error_dB', 'Cell_ID', 'Tower_Type',
        'Environment_Type', 'Model_Type'
    ]
    
    df = df[column_order]
    
    # Save to CSV
    filename = f"radio_coverage_arcgis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(filename, index=False)
    
    print(f"Generated {len(df)} coverage points")
    print(f"Coverage data saved to: {filename}")
    
    # Generate summary statistics
    print("\n=== Coverage Summary ===")
    print(f"Total coverage points: {len(df)}")
    print(f"Number of towers: {len(towers)}")
    print(f"Average signal strength: {df['Signal_Strength_dBm'].mean():.2f} dBm")
    print(f"Signal strength range: {df['Signal_Strength_dBm'].min():.2f} to {df['Signal_Strength_dBm'].max():.2f} dBm")
    print(f"Average Okahamaru error: {df['Okahamaru_Error_dB'].mean():.2f} dB")
    
    return filename

if __name__ == "__main__":
    generate_arcgis_coverage_csv() 