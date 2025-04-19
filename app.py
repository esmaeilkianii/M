import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
import json
import datetime
import plotly.express as px
import os
from io import BytesIO
import requests # Needed for getThumbUrl download

# --- Configuration ---
APP_TITLE = "داشبورد مانیتورینگ مزارع نیشکر دهخدا"
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 12

# --- File Paths (Relative to the script location in Hugging Face) ---
CSV_FILE_PATH = 'output (1).csv'
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'

# --- GEE Authentication ---
@st.cache_resource # Cache the GEE initialization
def initialize_gee():
    """Initializes Google Earth Engine using the Service Account."""
    try:
        # Check if the service account file exists
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"خطا: فایل Service Account در مسیر '{SERVICE_ACCOUNT_FILE}' یافت نشد.")
            st.stop()

        # Use the Service Account file directly for authentication
        credentials = ee.ServiceAccountCredentials(
            # The email address is not strictly needed when using the key file,
            # but it's good practice to include it for clarity.
            # Extract email from the key file content if needed, or hardcode if stable.
            # Let's try reading it from the file first.
             None, # Let the library infer from the key file
             key_file=SERVICE_ACCOUNT_FILE
        )

        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Initialized Successfully using Service Account.")
        return True # Indicate success
    except ee.EEException as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.error("لطفاً از صحت فایل Service Account و فعال بودن آن در پروژه GEE اطمینان حاصل کنید.")
        st.stop() # Stop execution if GEE fails
    except Exception as e:
        st.error(f"خطای غیرمنتظره هنگام اتصال به GEE: {e}")
        st.stop()

# --- Data Loading ---
@st.cache_data # Cache the loaded data
def load_data(csv_path):
    """Loads farm data from the CSV file."""
    try:
        df = pd.read_csv(csv_path)
        # Clean column names (remove potential leading/trailing spaces)
        df.columns = df.columns.str.strip()
        # Ensure coordinates are numeric, coerce errors to NaN
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        # Drop rows with missing coordinates as they cannot be mapped
        df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'], inplace=True)
        # Convert area to numeric if needed
        df['مساحت داشت'] = pd.to_numeric(df['مساحت داشت'], errors='coerce')
        # Standardize farm IDs if needed (e.g., remove leading/trailing spaces)
        df['مزرعه'] = df['مزرعه'].str.strip()
        # Fill potential NaN in categorical columns with a placeholder
        for col in ['کانال', 'اداره', 'واریته', 'سن ', 'روزهای هفته']:
             if col in df.columns:
                df[col] = df[col].fillna('نامشخص').astype(str)

        print(f"Data loaded successfully. Shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        return df
    except FileNotFoundError:
        st.error(f"خطا: فایل CSV در مسیر '{csv_path}' یافت نشد.")
        st.stop()
    except Exception as e:
        st.error(f"خطا در بارگذاری یا پردازش فایل CSV: {e}")
        st.stop()

# --- GEE Image Processing Functions ---

def mask_s2_clouds(image):
    """Masks clouds in Sentinel-2 SR images using the QA60 band."""
    qa = image.select('QA60')
    # Bits 10 and 11 are clouds and cirrus, respectively.
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    # Both flags should be set to zero, indicating clear conditions.
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
             qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    # Scale factor for Sentinel-2 SR data
    return image.updateMask(mask).divide(10000).copyProperties(image, ["system:time_start"])

def mask_landsat_clouds(image):
    """Masks clouds in Landsat 8/9 SR images using the pixel_qa band."""
    # Different Landsat collections have different QA band names and bit interpretations.
    # This example uses typical values for Collection 2 Level 2
    qa = image.select('QA_PIXEL')
    # Bit 3: Cloud shadow, Bit 4: Snow, Bit 5: Cloud
    cloud_shadow_bit = 1 << 3
    snow_bit = 1 << 4
    cloud_bit = 1 << 5
    # We want pixels that are clear (not cloud, shadow, or snow)
    mask = qa.bitwiseAnd(cloud_shadow_bit).eq(0).And(
             qa.bitwiseAnd(snow_bit).eq(0)).And(
             qa.bitwiseAnd(cloud_bit).eq(0))
    # Apply scaling factors for Landsat Collection 2 Level 2
    optical_bands = image.select('SR_B.').multiply(0.0000275).add(-0.2)
    thermal_bands = image.select('ST_B.*').multiply(0.00341802).add(149.0)
    return image.addBands(optical_bands, None, True)\
                .addBands(thermal_bands, None, True)\
                .updateMask(mask)\
                .copyProperties(image, ["system:time_start"])


# Index Calculation Functions
def calculate_ndvi(image):
    """Calculates NDVI. Assumes NIR and Red bands are available."""
    return image.normalizedDifference(['NIR', 'Red']).rename('NDVI')

def calculate_evi(image):
    """Calculates EVI. Assumes NIR, Red, and Blue bands are available."""
    return image.expression(
        '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
            'NIR': image.select('NIR'),
            'RED': image.select('Red'),
            'BLUE': image.select('Blue')
        }).rename('EVI')

def calculate_ndmi(image):
    """Calculates NDMI (Normalized Difference Moisture Index). Assumes NIR and SWIR1 bands."""
    # Sentinel-2: B8 (NIR), B11 (SWIR1)
    # Landsat 8/9: B5 (NIR), B6 (SWIR1)
    return image.normalizedDifference(['NIR', 'SWIR1']).rename('NDMI')

def calculate_msi(image):
    """Calculates MSI (Moisture Stress Index). Assumes SWIR1 and NIR bands."""
    # Sentinel-2: B11 (SWIR1), B8 (NIR)
    # Landsat 8/9: B6 (SWIR1), B5 (NIR)
    # Note: Sometimes MSI is defined as SWIR1/NIR. Ensure formula consistency.
    return image.expression('SWIR1 / NIR', {
        'SWIR1': image.select('SWIR1'),
        'NIR': image.select('NIR')
    }).rename('MSI')

def calculate_lai_simple(image):
    """Calculates a simple LAI proxy based on NDVI. Needs calibration."""
    # Example: LAI = a * exp(b * NDVI). Coefficients (a, b) need field calibration.
    # Using a very simple linear relationship for demonstration. Replace with a calibrated model.
    # return image.expression('3.0 * NDVI + 0.1', {'NDVI': image.select('NDVI')}).rename('LAI')
    # More common approximation using SAVI or EVI. Let's use EVI if available.
    evi = calculate_evi(image).select('EVI') # Calculate EVI first
    # Example relationship (highly approximate, needs calibration specific to sugarcane & region):
    lai = evi.multiply(3.5).add(0.1).rename('LAI') # Placeholder values
    # Clamp LAI to reasonable bounds (e.g., 0 to 8)
    return lai.clamp(0, 8)

def calculate_biomass_simple(image):
    """Calculates a simple Biomass proxy based on LAI. Needs calibration."""
    lai = calculate_lai_simple(image).select('LAI') # Requires LAI calculation first
    # Example linear relationship: Biomass = a * LAI + b
    # Coefficients (a, b) are placeholders and NEED calibration for sugarcane in the specific region.
    a = 1.5  # Placeholder (e.g., tonnes/ha per unit LAI)
    b = 0.2  # Placeholder (e.g., baseline biomass tonnes/ha)
    biomass = lai.multiply(a).add(b).rename('Biomass')
    return biomass.clamp(0, 50) # Clamp to reasonable max biomass (e.g., 50 t/ha)

def calculate_chlorophyll_mcari(image):
    """Calculates MCARI (Modified Chlorophyll Absorption Ratio Index)."""
    # Requires RedEdge1 (B5), Red (B4), Green (B3) for Sentinel-2
    # Landsat does not have RedEdge bands readily available for this specific formula.
    # This will only work reliably with Sentinel-2 data.
    try:
        mcari = image.expression(
            '((RE1 - RED) - 0.2 * (RE1 - GREEN)) * (RE1 / RED)', {
                'RE1': image.select('RedEdge1'), # Sentinel-2 B5
                'RED': image.select('Red'),      # Sentinel-2 B4
                'GREEN': image.select('Green')    # Sentinel-2 B3
            }).rename('Chlorophyll')
        return mcari
    except Exception:
         # Fallback or signal unavailability if bands missing
         # Return a dummy band or use a different index? Let's return NDVI as proxy for now.
         # A better approach would be conditional logic based on sensor.
         st.warning("MCARI requires Sentinel-2 Red Edge bands. Using NDVI as Chlorophyll proxy.")
         return calculate_ndvi(image).rename('Chlorophyll') # Placeholder

# Placeholder for ET - requires complex models or external data usually
def calculate_et_placeholder(image):
    """Placeholder for ET calculation. Returns NDMI as a proxy for moisture status."""
    st.warning("ET calculation is complex. Using NDMI as a proxy for moisture status.")
    return calculate_ndmi(image).rename('ET_proxy')


# Dictionary mapping index names to functions and standard band names
# Adapting band names for Sentinel-2 and Landsat
S2_BANDS = {'Blue': 'B2', 'Green': 'B3', 'Red': 'B4', 'RedEdge1': 'B5', 'NIR': 'B8', 'SWIR1': 'B11', 'SWIR2': 'B12', 'QA': 'QA60'}
L8L9_BANDS = {'Blue': 'SR_B2', 'Green': 'SR_B3', 'Red': 'SR_B4', 'NIR': 'SR_B5', 'SWIR1': 'SR_B6', 'SWIR2': 'SR_B7', 'QA': 'QA_PIXEL'}


INDEX_FUNCTIONS = {
    'NDVI': {'func': calculate_ndvi, 'vis': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}},
    'EVI': {'func': calculate_evi, 'vis': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}},
    'NDMI': {'func': calculate_ndmi, 'vis': {'min': -0.5, 'max': 0.8, 'palette': ['brown', 'white', 'blue']}},
    'MSI': {'func': calculate_msi, 'vis': {'min': 0.5, 'max': 2.5, 'palette': ['green', 'yellow', 'red']}}, # Higher MSI can indicate stress
    'LAI': {'func': calculate_lai_simple, 'vis': {'min': 0, 'max': 8, 'palette': ['white', 'lightgreen', 'darkgreen']}},
    'Biomass': {'func': calculate_biomass_simple, 'vis': {'min': 0, 'max': 30, 'palette': ['beige', 'yellow', 'brown']}}, # Max adjusted
    'Chlorophyll': {'func': calculate_chlorophyll_mcari, 'vis': {'min': 0, 'max': 1, 'palette': ['yellow', 'lightgreen', 'darkgreen']}}, # Adjust range based on index used
    'ET_proxy': {'func': calculate_et_placeholder, 'vis': {'min': -0.5, 'max': 0.8, 'palette': ['brown', 'white', 'blue']}} # Same as NDMI
}

# --- GEE Data Retrieval ---
def get_image_collection(start_date, end_date, geometry=None, sensor='Sentinel-2'):
    """Gets, filters, masks, and selects bands for Sentinel-2 or Landsat."""
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    if sensor == 'Sentinel-2':
        collection_id = 'COPERNICUS/S2_SR_HARMONIZED'
        bands = S2_BANDS
        mask_func = mask_s2_clouds
        required_bands = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'QA60'] # Blue, Green, Red, RedEdge1, NIR, SWIR1, QA
        band_mapping = {v: k for k, v in bands.items()} # Map S2 bands to common names

    elif sensor == 'Landsat':
        # Combine Landsat 8 and 9
        l9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
        l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        collection_id = l9.merge(l8) # Merge collections
        bands = L8L9_BANDS
        mask_func = mask_landsat_clouds
        required_bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'QA_PIXEL'] # Blue, Green, Red, NIR, SWIR1, QA
        band_mapping = {v: k for k, v in bands.items()} # Map L8/9 bands to common names
    else:
        st.error("Sensor not supported")
        return None

    collection = ee.ImageCollection(collection_id).filterDate(start_date_str, end_date_str)

    if geometry:
        collection = collection.filterBounds(geometry)

    # Select necessary bands and rename to common names BEFORE masking/calculations
    # Handle cases where a band might be missing (e.g., RedEdge in Landsat)
    available_bands_in_coll = ee.Image(collection.first()).bandNames().getInfo()
    select_bands = [b for b in required_bands if b in available_bands_in_coll]
    rename_map = {b: band_mapping[b] for b in select_bands if b in band_mapping}

    if not select_bands:
         st.warning(f"No required bands found in the first image of {sensor} collection.")
         return None # Or handle error appropriately

    # Apply renaming and masking
    processed_collection = collection.map(lambda img: img.select(select_bands).rename(rename_map))
    processed_collection = processed_collection.map(mask_func)


    # Check if collection is empty after filtering
    count = processed_collection.size().getInfo()
    if count == 0:
        st.warning(f"No cloud-free images found for the selected period and area using {sensor}.")
        return None

    return processed_collection


def calculate_indices_for_collection(collection, index_list):
    """Maps index calculation functions over a collection."""
    if collection is None:
        return None

    # Check available bands after masking/renaming
    first_image_bands = ee.Image(collection.first()).bandNames().getInfo()
    print(f"Bands available for index calculation: {first_image_bands}")

    calculated_collection = collection # Start with the masked collection

    for index_name in index_list:
        if index_name in INDEX_FUNCTIONS:
            # Check if required bands for the index are present
            # (This requires more complex introspection of the functions or predefined band lists per index)
            # Simple check: Assume functions handle missing bands gracefully or we've pre-filtered
            try:
                 # Map the function
                 calculated_collection = calculated_collection.map(INDEX_FUNCTIONS[index_name]['func'])
                 print(f"Calculated {index_name}")
            except Exception as e:
                 st.warning(f"Could not calculate {index_name}. Error: {e}. Required bands might be missing.")
                 # Add a dummy band to avoid errors later if needed
                 calculated_collection = calculated_collection.map(lambda img: img.addBands(ee.Image(0).rename(index_name)))

        else:
            st.warning(f"Index function for '{index_name}' not defined.")

    return calculated_collection

@st.cache_data(ttl=3600) # Cache for 1 hour
def get_timeseries_for_farm(_farm_geom_geojson, start_date, end_date, index_name, sensor):
    """Retrieves the time series for a specific index and farm geometry."""
    farm_geom = ee.Geometry(json.loads(_farm_geom_geojson)) # Convert GeoJSON string back to GEE object

    collection = get_image_collection(start_date, end_date, farm_geom, sensor)
    if collection is None:
        return pd.DataFrame(columns=['Date', index_name]) # Return empty dataframe

    indexed_collection = calculate_indices_for_collection(collection, [index_name])
    if indexed_collection is None or index_name not in ee.Image(indexed_collection.first()).bandNames().getInfo():
         st.warning(f"Index '{index_name}' could not be calculated or is missing.")
         return pd.DataFrame(columns=['Date', index_name])

    def extract_value(image):
        # Reduce region returns a dictionary. Extract the value.
        stats = image.select(index_name).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=farm_geom,
            scale=10,  # Scale in meters (e.g., 10m for Sentinel-2)
            maxPixels=1e9
        )
        # Ensure the index value exists in the dictionary before accessing
        val = stats.get(index_name)
        # Return a feature with null geometry, time, and the value
        # Use ee.Algorithms.If to handle potential null values from reducer
        return ee.Feature(None, {
            'time': image.get('system:time_start'),
            index_name: ee.Algorithms.If(val, val, -9999) # Use a placeholder for nulls
            })

    ts_info = indexed_collection.map(extract_value).getInfo()

    # Process the results into a pandas DataFrame
    data = []
    for feature in ts_info['features']:
        if feature['properties'][index_name] != -9999: # Filter out null placeholders
            dt = datetime.datetime.fromtimestamp(feature['properties']['time'] / 1000.0)
            data.append([dt, feature['properties'][index_name]])

    if not data:
        return pd.DataFrame(columns=['Date', index_name])

    ts_df = pd.DataFrame(data, columns=['Date', index_name])
    ts_df = ts_df.sort_values(by='Date')
    return ts_df

@st.cache_data(ttl=3600) # Cache for 1 hour
def get_latest_index_for_ranking(_farms_df_json, selected_day, start_date, end_date, index_name, sensor):
    """Gets the latest valid index value for ranking farms active on a selected day."""
    farms_df = pd.read_json(_farms_df_json) # Convert JSON back to DataFrame
    if selected_day != "همه روزها":
        farms_df_filtered = farms_df[farms_df['روزهای هفته'] == selected_day].copy()
    else:
        farms_df_filtered = farms_df.copy()

    if farms_df_filtered.empty:
        return pd.DataFrame(columns=['مزرعه', index_name])

    # Create a FeatureCollection from the filtered farms DataFrame
    features = []
    for idx, row in farms_df_filtered.iterrows():
        geom = ee.Geometry.Point([row['طول جغرافیایی'], row['عرض جغرافیایی']])
        # Buffer the point slightly to represent the farm area for reduction
        buffered_geom = geom.buffer(50) # Buffer by 50 meters (adjust as needed)
        feature = ee.Feature(buffered_geom, {'farm_id': row['مزرعه']})
        features.append(feature)

    if not features:
         return pd.DataFrame(columns=['مزرعه', index_name])

    farm_fc = ee.FeatureCollection(features)

    # Get the image collection and calculate the index
    collection = get_image_collection(start_date, end_date, farm_fc.geometry(), sensor) # Filter by overall bounds
    if collection is None:
        return pd.DataFrame(columns=['مزرعه', index_name])

    indexed_collection = calculate_indices_for_collection(collection, [index_name])
    if indexed_collection is None or index_name not in ee.Image(indexed_collection.first()).bandNames().getInfo():
        st.warning(f"Index '{index_name}' could not be calculated or is missing for ranking.")
        return pd.DataFrame(columns=['مزرعه', index_name])

    # Create a single composite image (e.g., median) over the period for ranking
    # Or get the latest image? Median is often more robust to noise/outliers.
    composite_image = indexed_collection.select(index_name).median() # Use median for stability

    # Reduce the composite image over the farm geometries
    try:
        farm_values = composite_image.reduceRegions(
            collection=farm_fc,
            reducer=ee.Reducer.mean(),
            scale=10 # Match resolution
        ).getInfo()
    except ee.EEException as e:
        st.error(f"Error during reduceRegions for ranking: {e}")
        # Try reducing scale or handling potential memory issues
        st.warning("Trying reduceRegions with larger scale (30m)")
        try:
            farm_values = composite_image.reduceRegions(
                collection=farm_fc,
                reducer=ee.Reducer.mean(),
                scale=30 # Increase scale if needed
            ).getInfo()
        except ee.EEException as e2:
             st.error(f"ReduceRegions failed again: {e2}")
             return pd.DataFrame(columns=['مزرعه', index_name])


    # Extract results into a DataFrame
    ranking_data = []
    for feature in farm_values['features']:
        farm_id = feature['properties']['farm_id']
        value = feature['properties'].get('mean', None) # 'mean' is the default output band name
        if value is not None:
            ranking_data.append({'مزرعه': farm_id, index_name: value})

    ranking_df = pd.DataFrame(ranking_data)

    # Merge with original farm data to get other attributes if needed later
    # ranking_df = pd.merge(ranking_df, farms_df_filtered[['مزرعه', 'کانال', 'اداره', 'واریته', 'سن ']], on='مزرعه', how='left')

    # Sort by index value (descending for NDVI/EVI/Biomass, ascending for MSI?)
    ascending_sort = False if index_name not in ['MSI'] else True # Adjust logic based on index meaning
    ranking_df = ranking_df.sort_values(by=index_name, ascending=ascending_sort).reset_index(drop=True)

    return ranking_df


# --- Streamlit App Layout ---
st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

# Initialize GEE
if initialize_gee():
    # Load data after successful GEE initialization
    farm_data_df = load_data(CSV_FILE_PATH)

    # --- Sidebar ---
    st.sidebar.header("تنظیمات نمایش")

    # Date Range Selector
    default_end_date = datetime.date.today()
    default_start_date = default_end_date - datetime.timedelta(days=30) # Default to last 30 days
    start_date = st.sidebar.date_input("تاریخ شروع", value=default_start_date, max_value=default_end_date)
    end_date = st.sidebar.date_input("تاریخ پایان", value=default_end_date, min_value=start_date, max_value=default_end_date)

    # Day of the Week Filter
    days_list = ["همه روزها"] + sorted(farm_data_df['روزهای هفته'].unique().tolist())
    selected_day = st.sidebar.selectbox("فیلتر بر اساس روز هفته", options=days_list)

    # Filter DataFrame based on selected day
    if selected_day == "همه روزها":
        filtered_df = farm_data_df.copy()
    else:
        filtered_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day].copy()

    # Farm Selection Dropdown
    farm_list = ["همه مزارع"] + sorted(filtered_df['مزرعه'].unique().tolist())
    selected_farm = st.sidebar.selectbox("انتخاب مزرعه", options=farm_list)

    # Index Selection Dropdown
    selected_index = st.sidebar.selectbox("انتخاب شاخص", options=list(INDEX_FUNCTIONS.keys()))

    # Sensor Selection
    selected_sensor = st.sidebar.radio("انتخاب سنسور ماهواره", ('Sentinel-2', 'Landsat'), index=0)


    # --- Main Panel ---
    col1, col2 = st.columns([3, 1]) # Map column wider than details/chart column

    with col1:
        st.subheader("نقشه وضعیت مزارع")

        # Initialize Map
        m = geemap.Map(center=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False)
        m.add_basemap('HYBRID') # Add satellite basemap

        # Get visualization parameters for the selected index
        vis_params = INDEX_FUNCTIONS[selected_index]['vis']
        index_func = INDEX_FUNCTIONS[selected_index]['func']

        # --- Display Logic ---
        if selected_farm == "همه مزارع":
            if not filtered_df.empty:
                 # Get collection for the bounds of all filtered farms
                 min_lon, min_lat = filtered_df['طول جغرافیایی'].min(), filtered_df['عرض جغرافیایی'].min()
                 max_lon, max_lat = filtered_df['طول جغرافیایی'].max(), filtered_df['عرض جغرافیایی'].max()
                 bounds_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])

                 # Display composite index layer for the whole area
                 with st.spinner(f"در حال پردازش تصویر {selected_index} برای منطقه..."):
                     collection = get_image_collection(start_date, end_date, bounds_geom, selected_sensor)
                     if collection:
                         indexed_collection = calculate_indices_for_collection(collection, [selected_index])
                         if indexed_collection and selected_index in ee.Image(indexed_collection.first()).bandNames().getInfo():
                             median_image = indexed_collection.select(selected_index).median()
                             m.addLayer(median_image, vis_params, f'{selected_index} (Median)')
                             m.add_legend(title=f'{selected_index} Legend', builtin_legend=None, palette=vis_params['palette'], min=vis_params['min'], max=vis_params['max'])
                             # Add download button for the composite map layer
                             try:
                                 thumb_url = median_image.getThumbURL({
                                     'region': bounds_geom.toGeoJson(), # Use the bounds geometry
                                     'bands': selected_index,
                                     'palette': vis_params['palette'],
                                     'min': vis_params['min'],
                                     'max': vis_params['max'],
                                     'dimensions': 512 # Adjust dimension for quality/size trade-off
                                 })
                                 # Download using requests
                                 response = requests.get(thumb_url)
                                 if response.status_code == 200:
                                     img_bytes = BytesIO(response.content)
                                     st.sidebar.download_button(
                                         label=f"دانلود نقشه {selected_index} (PNG)",
                                         data=img_bytes,
                                         file_name=f"map_{selected_index}_{start_date}_to_{end_date}.png",
                                         mime="image/png"
                                     )
                                 else:
                                     st.sidebar.warning(f"امکان ایجاد لینک دانلود نقشه وجود ندارد (وضعیت: {response.status_code}).")
                             except Exception as thumb_e:
                                 st.sidebar.warning(f"خطا در ایجاد لینک دانلود نقشه: {thumb_e}")


                         else:
                              st.warning(f"امکان محاسبه یا نمایش شاخص '{selected_index}' وجود ندارد.")

                 # Add markers for each farm
                 for idx, row in filtered_df.iterrows():
                      popup_html = f"""
                        <b>مزرعه:</b> {row['مزرعه']}<br>
                        <b>کانال:</b> {row['کانال']}<br>
                        <b>اداره:</b> {row['اداره']}<br>
                        <b>مساحت:</b> {row['مساحت داشت']:.2f} هکتار<br>
                        <b>واریته:</b> {row['واریته']}<br>
                        <b>سن:</b> {row['سن ']}<br>
                        <b>روز هفته:</b> {row['روزهای هفته']}
                      """
                      # Use folium directly for more popup control within geemap context
                      folium.Marker(
                          location=[row['عرض جغرافیایی'], row['طول جغرافیایی']],
                          popup=folium.Popup(popup_html, max_width=250),
                          tooltip=f"مزرعه {row['مزرعه']}",
                          icon=folium.Icon(color='blue', icon='info-sign')
                      ).add_to(m)
                 # Adjust map bounds to fit all markers if many farms
                 if len(filtered_df) > 1:
                     m.center_object(bounds_geom, zoom=INITIAL_ZOOM -1 ) # Zoom out slightly if many farms

            else:
                 st.info("هیچ مزرعه‌ای برای نمایش با فیلترهای انتخاب شده یافت نشد.")

        else: # Single farm selected
            farm_info = filtered_df[filtered_df['مزرعه'] == selected_farm].iloc[0]
            farm_lat = farm_info['عرض جغرافیایی']
            farm_lon = farm_info['طول جغرافیایی']
            farm_geom = ee.Geometry.Point([farm_lon, farm_lat])
            # Buffer the point to better visualize the area for the index map layer
            farm_buffer_geom = farm_geom.buffer(150) # Adjust buffer size as needed

            # Center map on the selected farm
            m.center_object(farm_geom, zoom=INITIAL_ZOOM + 2) # Zoom in closer

            # Display index layer clipped to the farm buffer
            with st.spinner(f"در حال پردازش تصویر {selected_index} برای مزرعه {selected_farm}..."):
                collection = get_image_collection(start_date, end_date, farm_buffer_geom, selected_sensor)
                if collection:
                    indexed_collection = calculate_indices_for_collection(collection, [selected_index])
                    if indexed_collection and selected_index in ee.Image(indexed_collection.first()).bandNames().getInfo():
                        median_image = indexed_collection.select(selected_index).median().clip(farm_buffer_geom) # Clip to buffer
                        m.addLayer(median_image, vis_params, f'{selected_index} (مزرعه {selected_farm})')
                        m.add_legend(title=f'{selected_index} Legend', builtin_legend=None, palette=vis_params['palette'], min=vis_params['min'], max=vis_params['max'])
                        # Add download button for the specific farm map layer
                        try:
                             thumb_url = median_image.getThumbURL({
                                 'region': farm_buffer_geom.toGeoJson(), # Use the buffer geometry
                                 'bands': selected_index,
                                 'palette': vis_params['palette'],
                                 'min': vis_params['min'],
                                 'max': vis_params['max'],
                                 'dimensions': 256
                             })
                             # Download using requests
                             response = requests.get(thumb_url)
                             if response.status_code == 200:
                                 img_bytes = BytesIO(response.content)
                                 st.sidebar.download_button(
                                     label=f"دانلود نقشه {selected_farm} (PNG)",
                                     data=img_bytes,
                                     file_name=f"map_{selected_farm}_{selected_index}_{start_date}_to_{end_date}.png",
                                     mime="image/png"
                                 )
                             else:
                                 st.sidebar.warning(f"امکان ایجاد لینک دانلود نقشه مزرعه وجود ندارد (وضعیت: {response.status_code}).")
                        except Exception as thumb_e:
                             st.sidebar.warning(f"خطا در ایجاد لینک دانلود نقشه مزرعه: {thumb_e}")

                    else:
                        st.warning(f"امکان محاسبه یا نمایش شاخص '{selected_index}' برای این مزرعه وجود ندارد.")
                else:
                    st.warning(f"هیچ تصویر ماهواره‌ای مناسبی در بازه زمانی انتخابی برای مزرعه {selected_farm} یافت نشد.")


            # Add a marker for the specific farm
            popup_html = f"""
                <b>مزرعه:</b> {farm_info['مزرعه']}<br>
                <b>کانال:</b> {farm_info['کانال']}<br>
                <b>اداره:</b> {farm_info['اداره']}<br>
                <b>مساحت:</b> {farm_info['مساحت داشت']:.2f} هکتار<br>
                <b>واریته:</b> {farm_info['واریته']}<br>
                <b>سن:</b> {farm_info['سن ']}<br>
                <b>روز هفته:</b> {farm_info['روزهای هفته']}
            """
            folium.Marker(
                location=[farm_lat, farm_lon],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"مزرعه {farm_info['مزرعه']}",
                icon=folium.Icon(color='red', icon='star') # Different icon for selected farm
            ).add_to(m)

        # Render the map in Streamlit
        m.to_streamlit(height=500)

    with col2:
        if selected_farm != "همه مزارع":
            st.subheader(f"جزئیات مزرعه: {selected_farm}")
            farm_info = filtered_df[filtered_df['مزرعه'] == selected_farm].iloc[0]
            st.metric("کانال", farm_info['کانال'])
            st.metric("اداره", farm_info['اداره'])
            st.metric("مساحت داشت (هکتار)", f"{farm_info['مساحت داشت']:.2f}")
            st.metric("واریته", farm_info['واریته'])
            st.metric("سن", farm_info['سن '])
            st.metric("روز آبیاری", farm_info['روزهای هفته'])
            st.metric("وضعیت مختصات", "موجود" if farm_info['coordinates_missing'] == 0 else "گمشده")

            st.subheader(f"روند شاخص {selected_index}")
            with st.spinner(f"در حال دریافت سری زمانی {selected_index} برای مزرعه {selected_farm}..."):
                 # Pass farm geometry as GeoJSON string to allow caching
                farm_geom = ee.Geometry.Point([farm_info['طول جغرافیایی'], farm_info['عرض جغرافیایی']])
                ts_df = get_timeseries_for_farm(farm_geom.toGeoJsonString(), start_date, end_date, selected_index, selected_sensor)

            if not ts_df.empty:
                fig = px.line(ts_df, x='Date', y=selected_index, title=f"روند زمانی {selected_index} برای مزرعه {selected_farm}", markers=True)
                fig.update_layout(xaxis_title="تاریخ", yaxis_title=selected_index)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"داده‌ای برای نمایش نمودار روند زمانی {selected_index} یافت نشد.")

        else: # "همه مزارع" is selected
            st.subheader(f"رتبه‌بندی مزارع بر اساس {selected_index}")
            st.info(f"نمایش میانگین مقدار شاخص '{selected_index}' در بازه زمانی انتخاب شده برای مزارع فعال در '{selected_day}'.")

            with st.spinner(f"در حال محاسبه رتبه‌بندی مزارع بر اساس {selected_index}..."):
                 # Pass DataFrame as JSON to allow caching
                ranking_df = get_latest_index_for_ranking(filtered_df.to_json(), selected_day, start_date, end_date, selected_index, selected_sensor)

            if not ranking_df.empty:
                st.dataframe(ranking_df.style.format({selected_index: "{:.3f}"}), use_container_width=True)
                # Allow downloading ranking data
                csv = ranking_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                   label=f"دانلود جدول رتبه‌بندی ({selected_index})",
                   data=csv,
                   file_name=f'ranking_{selected_index}_{selected_day}_{start_date}_to_{end_date}.csv',
                   mime='text/csv',
                 )
            else:
                st.warning("اطلاعاتی برای رتبه‌بندی مزارع یافت نشد.")

else:
    st.warning("لطفا صبر کنید تا اتصال به Google Earth Engine برقرار شود یا خطاهای نمایش داده شده را بررسی کنید.")

# Add a footer or instructions
st.sidebar.markdown("---")
st.sidebar.info("راهنما: از منوهای بالا برای انتخاب بازه زمانی، روز هفته، مزرعه و شاخص مورد نظر استفاده کنید. نقشه و نمودارها به‌روز خواهند شد.")