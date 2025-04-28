import ee
import numpy as np
import pandas as pd
import streamlit as st
import geemap.foliumap as geemap
import folium
import datetime
import plotly.express as px
import plotly.graph_objects as go

# Constants for ET calculations
ALBEDO_COEFFICIENTS = {
    'MODIS': {'a': 0.160, 'b': 0.291},  # For MODIS data
    'Landsat': {'a': 0.356, 'b': 0.130}  # For Landsat data
}

STEFAN_BOLTZMANN = 5.67e-8  # Stefan-Boltzmann constant

# Function to initialize Earth Engine
def initialize_ee(service_account_file):
    """Initialize Earth Engine with service account."""
    try:
        credentials = ee.ServiceAccountCredentials(None, key_file=service_account_file)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        return True
    except Exception as e:
        st.error(f"Error initializing Earth Engine: {e}")
        return False

# Function to mask clouds in MODIS imagery
def mask_modis_clouds(image):
    """Mask clouds in MODIS imagery using quality bands."""
    qa = image.select('state_1km')
    cloud_mask = qa.bitwiseAnd(1 << 10).eq(0)  # Cloud state bit
    return image.updateMask(cloud_mask)

# Function to mask clouds in Landsat imagery
def mask_landsat_clouds(image):
    """Mask clouds in Landsat imagery using QA band."""
    qa = image.select('QA_PIXEL')
    cloud_mask = qa.bitwiseAnd(1 << 3).eq(0)  # Cloud bit
    return image.updateMask(cloud_mask)

# Function to calculate albedo from MODIS data
def calculate_albedo_modis(image):
    """Calculate albedo from MODIS reflectance bands."""
    # Use MODIS bands for albedo calculation
    coeffs = ALBEDO_COEFFICIENTS['MODIS']
    albedo = image.expression(
        'a + b * (0.215*b1 + 0.215*b2 + 0.242*b3 + 0.129*b4 + 0.101*b5 + 0.062*b6 + 0.036*b7)',
        {
            'a': coeffs['a'],
            'b': coeffs['b'],
            'b1': image.select('sur_refl_b01'),
            'b2': image.select('sur_refl_b02'),
            'b3': image.select('sur_refl_b03'),
            'b4': image.select('sur_refl_b04'),
            'b5': image.select('sur_refl_b05'),
            'b6': image.select('sur_refl_b06'),
            'b7': image.select('sur_refl_b07')
        }
    ).rename('albedo')
    return image.addBands(albedo)

# Function to calculate albedo from Landsat data
def calculate_albedo_landsat(image):
    """Calculate albedo from Landsat reflectance bands."""
    # Use Landsat bands for albedo calculation
    coeffs = ALBEDO_COEFFICIENTS['Landsat']
    albedo = image.expression(
        'a + b * (0.254*b2 + 0.149*b3 + 0.147*b4 + 0.311*b5 + 0.103*b6 + 0.036*b7)',
        {
            'a': coeffs['a'],
            'b': coeffs['b'],
            'b2': image.select('SR_B2'),  # Blue
            'b3': image.select('SR_B3'),  # Green
            'b4': image.select('SR_B4'),  # Red
            'b5': image.select('SR_B5'),  # NIR
            'b6': image.select('SR_B6'),  # SWIR1
            'b7': image.select('SR_B7')   # SWIR2
        }
    ).rename('albedo')
    return image.addBands(albedo)

# Function to calculate NDVI
def calculate_ndvi(image, sensor):
    """Calculate NDVI based on sensor type."""
    if sensor == 'MODIS':
        ndvi = image.normalizedDifference(['sur_refl_b02', 'sur_refl_b01']).rename('NDVI')
    elif sensor == 'Landsat':
        ndvi = image.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI')
    return image.addBands(ndvi)

# Function to calculate land surface temperature (LST)
def calculate_lst(image, sensor):
    """Calculate land surface temperature based on sensor type."""
    if sensor == 'MODIS':
        # MODIS LST is already provided in Kelvin
        lst = image.select('LST_Day_1km').multiply(0.02).rename('LST')
    elif sensor == 'Landsat':
        # Calculate LST from Landsat thermal band
        thermal = image.select('ST_B10').multiply(0.00341802).add(149.0)
        # Apply emissivity correction
        ndvi = image.select('NDVI')
        emissivity = ndvi.expression(
            'where(NDVI < 0, 0.985, where(NDVI > 0.7, 0.99, 0.985 + 0.007 * NDVI))',
            {'NDVI': ndvi}
        )
        lst = thermal.divide(emissivity.pow(0.25)).rename('LST')
    return image.addBands(lst)

# Function to calculate net radiation (Rn)
def calculate_net_radiation(image):
    """Calculate net radiation using surface reflectance and temperature."""
    # Get albedo and LST
    albedo = image.select('albedo')
    lst = image.select('LST')
    
    # Calculate incoming solar radiation (Rs↓) - simplified approach
    # In a real implementation, this would use solar zenith angle and atmospheric transmissivity
    rs_down = ee.Number(1000)  # Approximate value for clear sky conditions (W/m²)
    
    # Calculate outgoing longwave radiation (Rl↑)
    rl_up = image.expression(
        'STEFAN_BOLTZMANN * LST^4',
        {
            'STEFAN_BOLTZMANN': STEFAN_BOLTZMANN,
            'LST': lst
        }
    )
    
    # Calculate incoming longwave radiation (Rl↓) - simplified approach
    # In a real implementation, this would use air temperature and vapor pressure
    rl_down = ee.Number(300)  # Approximate value (W/m²)
    
    # Calculate net radiation
    rn = image.expression(
        '(1 - albedo) * Rs_down + Rl_down - Rl_up',
        {
            'albedo': albedo,
            'Rs_down': rs_down,
            'Rl_down': rl_down,
            'Rl_up': rl_up
        }
    ).rename('Rn')
    
    return image.addBands(rn)

# Function to calculate soil heat flux (G)
def calculate_soil_heat_flux(image):
    """Calculate soil heat flux as a fraction of net radiation."""
    rn = image.select('Rn')
    ndvi = image.select('NDVI')
    lst = image.select('LST')
    albedo = image.select('albedo')
    
    # G/Rn ratio based on SEBAL model
    g_rn_ratio = image.expression(
        '(LST - 273.15) / Rn * (0.0038 + 0.0074 * albedo) * (1 - 0.98 * NDVI^4)',
        {
            'LST': lst,
            'Rn': rn,
            'albedo': albedo,
            'NDVI': ndvi
        }
    )
    
    # Calculate G
    g = rn.multiply(g_rn_ratio).rename('G')
    
    return image.addBands(g)

# Function to calculate sensible heat flux (H) using SEBAL approach
def calculate_sensible_heat_flux(image, dem):
    """Calculate sensible heat flux using SEBAL approach."""
    # This is a simplified implementation of SEBAL
    # In a real implementation, this would require iterative calculation and anchor pixels
    
    # Add DEM to the image
    image = image.addBands(dem)
    
    # Get required bands
    lst = image.select('LST')
    ndvi = image.select('NDVI')
    elevation = image.select('elevation')
    
    # Define cold and hot pixels (simplified approach)
    # In a real implementation, these would be selected based on NDVI and LST
    cold_pixel_temp = ee.Number(290)  # Example value (K)
    hot_pixel_temp = ee.Number(315)   # Example value (K)
    
    # Calculate temperature difference (dT) based on LST
    dt = image.expression(
        'a + b * (LST - 273.15)',
        {
            'a': ee.Number(-2),
            'b': ee.Number(0.1),
            'LST': lst
        }
    ).rename('dT')
    
    # Calculate air density (ρ) based on elevation
    rho = image.expression(
        '1.225 * (1 - 2.2569e-5 * elevation)^5.2553',
        {'elevation': elevation}
    ).rename('rho')
    
    # Calculate aerodynamic resistance (rah) - simplified
    rah = ee.Image(10).rename('rah')  # Example value (s/m)
    
    # Calculate sensible heat flux
    h = image.expression(
        'rho * 1004 * dT / rah',
        {
            'rho': rho,
            'dT': dt,
            'rah': rah
        }
    ).rename('H')
    
    return image.addBands(h)

# Function to calculate latent heat flux (LE) and evapotranspiration (ET)
def calculate_et(image):
    """Calculate latent heat flux and evapotranspiration."""
    # Get energy balance components
    rn = image.select('Rn')
    g = image.select('G')
    h = image.select('H')
    
    # Calculate latent heat flux as residual of energy balance
    le = rn.subtract(g).subtract(h).rename('LE')
    
    # Convert LE to ET (mm/day)
    # LE (W/m²) to ET (mm/day): ET = LE * 0.0864 / 2450
    # where 0.0864 converts W/m² to MJ/m²/day and 2450 is latent heat of vaporization (J/g)
    et = le.multiply(0.0864).divide(2450).rename('ET')
    
    # Ensure ET is not negative
    et = et.max(0)
    
    return image.addBands(le).addBands(et)

# Main function to calculate ET using SEBAL/METRIC approach
def calculate_et_sebal(geometry, start_date, end_date, sensor='MODIS'):
    """Calculate evapotranspiration using SEBAL/METRIC approach."""
    # Get DEM data
    dem = ee.Image('USGS/SRTMGL1_003').select('elevation')
    
    # Get satellite imagery based on sensor type
    if sensor == 'MODIS':
        # Get MODIS data
        collection = ee.ImageCollection('MODIS/006/MOD11A1') \
            .filterDate(start_date, end_date) \
            .filterBounds(geometry)
        
        # Get MODIS surface reflectance data
        collection_sr = ee.ImageCollection('MODIS/006/MOD09GA') \
            .filterDate(start_date, end_date) \
            .filterBounds(geometry) \
            .map(mask_modis_clouds)
        
        # Join the collections
        joined = ee.ImageCollection(ee.Join.inner().apply({
            'primary': collection,
            'secondary': collection_sr,
            'condition': ee.Filter.equals({
                'leftField': 'system:time_start',
                'rightField': 'system:time_start'
            })
        })).map(lambda pair: ee.Image(pair.get('primary')).addBands(ee.Image(pair.get('secondary'))))
        
    elif sensor == 'Landsat':
        # Get Landsat 8 Collection 2 data
        collection = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
            .filterDate(start_date, end_date) \
            .filterBounds(geometry) \
            .map(mask_landsat_clouds)
        
        joined = collection  # No need to join for Landsat
    
    # Apply ET calculation steps to each image
    et_collection = joined.map(lambda image: {
        # Calculate albedo
        image = calculate_albedo_modis(image) if sensor == 'MODIS' else calculate_albedo_landsat(image)
        
        # Calculate NDVI
        image = calculate_ndvi(image, sensor)
        
        # Calculate LST
        image = calculate_lst(image, sensor)
        
        # Calculate net radiation
        image = calculate_net_radiation(image)
        
        # Calculate soil heat flux
        image = calculate_soil_heat_flux(image)
        
        # Calculate sensible heat flux
        image = calculate_sensible_heat_flux(image, dem.clip(geometry))
        
        # Calculate latent heat flux and ET
        image = calculate_et(image)
        
        return image
    })
    
    # Calculate median ET over the period
    median_et = et_collection.select('ET').median()
    
    return {
        'et_image': median_et,
        'et_collection': et_collection,
        'count': et_collection.size().getInfo()
    }

# Function to get time series of ET for a point
def get_et_time_series(point_geometry, start_date, end_date, sensor='MODIS'):
    """Get time series of ET values for a specific point."""
    # Calculate ET for the period
    et_result = calculate_et_sebal(point_geometry, start_date, end_date, sensor)
    et_collection = et_result['et_collection']
    
    # Function to extract ET value at the point for each image
    def extract_et(image):
        et_value = image.select('ET').reduceRegion(
            reducer=ee.Reducer.first(),
            geometry=point_geometry,
            scale=1000 if sensor == 'MODIS' else 30  # Scale based on sensor resolution
        ).get('ET')
        
        return ee.Feature(None, {
            'date': image.date().format('YYYY-MM-dd'),
            'ET': et_value
        })
    
    # Map over the collection and extract ET values
    et_features = et_collection.map(extract_et)
    
    # Get the time series data as a list of dictionaries
    et_data = et_features.reduceColumns(
        reducer=ee.Reducer.toList(2),
        selectors=['date', 'ET']
    ).get('list').getInfo()
    
    # Convert to pandas DataFrame
    if et_data:
        et_df = pd.DataFrame(et_data, columns=['date', 'ET'])
        et_df['date'] = pd.to_datetime(et_df['date'])
        et_df = et_df.sort_values('date')
        return et_df
    else:
        return pd.DataFrame(columns=['date', 'ET'])

# Function to create ET visualization
def visualize_et(et_image, geometry, map_object=None):
    """Add ET visualization to a map."""
    if map_object is None:
        map_object = geemap.Map()
    
    # Define visualization parameters for ET
    et_vis_params = {
        'min': 0,
        'max': 10,  # Adjust based on expected ET range
        'palette': ['#d73027', '#fc8d59', '#fee090', '#e0f3f8', '#91bfdb', '#4575b4']
    }
    
    # Add ET layer to the map
    map_object.addLayer(
        et_image.clip(geometry),
        et_vis_params,
        'Evapotranspiration (mm/day)'
    )
    
    # Add a legend
    map_object.add_colorbar(et_vis_params, label='ET (mm/day)')
    
    return map_object

# Function to analyze ET trends
def analyze_et_trends(et_df):
    """Analyze ET trends and generate statistics."""
    if et_df.empty:
        return {
            'mean_et': None,
            'max_et': None,
            'min_et': None,
            'trend': None,
            'water_stress_days': None
        }
    
    # Calculate basic statistics
    mean_et = et_df['ET'].mean()
    max_et = et_df['ET'].max()
    min_et = et_df['ET'].min()
    
    # Determine trend (simple linear regression)
    if len(et_df) > 1:
        x = np.arange(len(et_df))
        y = et_df['ET'].values
        slope = np.polyfit(x, y, 1)[0]
        trend = 'increasing' if slope > 0.05 else ('decreasing' if slope < -0.05 else 'stable')
    else:
        trend = 'insufficient data'
    
    # Count days with potential water stress (ET < 50% of max)
    water_stress_threshold = max_et * 0.5 if not np.isnan(max_et) else 0
    water_stress_days = (et_df['ET'] < water_stress_threshold).sum() if not np.isnan(water_stress_threshold) else 0
    
    return {
        'mean_et': mean_et,
        'max_et': max_et,
        'min_et': min_et,
        'trend': trend,
        'water_stress_days': water_stress_days
    }

# Function to create ET time series plot
def plot_et_time_series(et_df, farm_name=None):
    """Create a time series plot of ET values."""
    if et_df.empty:
        return None
    
    title = f'Evapotranspiration Time Series for {farm_name}' if farm_name else 'Evapotranspiration Time Series'
    
    fig = px.line(
        et_df, 
        x='date', 
        y='ET',
        title=title,
        labels={'ET': 'ET (mm/day)', 'date': 'Date'},
        markers=True
    )
    
    # Add a reference line for average ET
    mean_et = et_df['ET'].mean()
    fig.add_hline(
        y=mean_et,
        line_dash='dash',
        line_color='red',
        annotation_text=f'Mean: {mean_et:.2f} mm/day',
        annotation_position='bottom right'
    )
    
    # Improve layout
    fig.update_layout(
        xaxis_title='Date',
        yaxis_title='ET (mm/day)',
        hovermode='x unified'
    )
    
    return fig

# Function to create water requirement cards
def create_water_requirement_cards(et_analysis, farm_area=1.0):
    """Create cards showing water requirements based on ET analysis."""
    if et_analysis['mean_et'] is None:
        return None
    
    # Calculate water requirements
    daily_water_req = et_analysis['mean_et'] * farm_area * 10  # mm/day * ha * 10 = m³/day
    weekly_water_req = daily_water_req * 7  # m³/week
    
    # Create cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Daily Water Requirement",
            value=f"{daily_water_req:.1f} m³",
            delta=None
        )
    
    with col2:
        st.metric(
            label="Weekly Water Requirement",
            value=f"{weekly_water_req:.1f} m³",
            delta=None
        )
    
    with col3:
        status = "Normal"
        if et_analysis['trend'] == 'increasing':
            status = "Increasing Demand"
            delta_color = "inverse"
        elif et_analysis['trend'] == 'decreasing':
            status = "Decreasing Demand"
            delta_color = "normal"
        else:
            status = "Stable Demand"
            delta_color = "off"
            
        st.metric(
            label="Water Demand Trend",
            value=status,
            delta=et_analysis['trend'],
            delta_color=delta_color
        )
    
    return True