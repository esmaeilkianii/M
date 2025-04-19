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
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"خطا: فایل Service Account در مسیر '{SERVICE_ACCOUNT_FILE}' یافت نشد.")
            st.stop()
        credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Initialized Successfully using Service Account.")
        return True
    except ee.EEException as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.error("لطفاً از صحت فایل Service Account و فعال بودن آن در پروژه GEE اطمینان حاصل کنید.")
        st.stop()
    except Exception as e:
        st.error(f"خطای غیرمنتظره هنگام اتصال به GEE: {e}")
        st.stop()

# --- Data Loading ---
@st.cache_data # Cache the loaded data
def load_data(csv_path):
    """Loads farm data from the CSV file."""
    try:
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'], inplace=True)
        df['مساحت داشت'] = pd.to_numeric(df['مساحت داشت'], errors='coerce')
        df['مزرعه'] = df['مزرعه'].str.strip()
        for col in ['کانال', 'اداره', 'واریته', 'سن ', 'روزهای هفته']:
             if col in df.columns:
                df[col] = df[col].fillna('نامشخص').astype(str)
        print(f"Data loaded successfully. Shape: {df.shape}")
        return df
    except FileNotFoundError:
        st.error(f"خطا: فایل CSV در مسیر '{csv_path}' یافت نشد.")
        st.stop()
    except Exception as e:
        st.error(f"خطا در بارگذاری یا پردازش فایل CSV: {e}")
        st.stop()
COMMON_BAND_NAMES = ['Blue', 'Green', 'Red', 'RedEdge1', 'NIR', 'SWIR1', 'SWIR2']

# --- Masking Functions ---
# (Keep mask_s2_clouds and mask_landsat_clouds as they were in the previous corrected version)
def mask_s2_clouds(image):
    """Masks clouds in Sentinel-2 SR images using QA60.
       Returns scaled, masked data bands ONLY (B2, B3, B4, B5, B8, B11, B12).
    """
    qa = image.select('QA60')
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
             qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    # Select necessary data bands using original names, apply mask, scale
    data_bands = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12'] # S2 bands needed for indices
    # Ensure image is treated as an Image before selecting/masking
    img_ee = ee.Image(image)
    return img_ee.select(data_bands).updateMask(mask).divide(10000.0)\
        .copyProperties(img_ee, ["system:time_start"])

def mask_landsat_clouds(image):
    """Masks clouds in Landsat 8/9 SR images using QA_PIXEL.
       Returns scaled, masked data bands ONLY (SR_B2-SR_B7).
    """
    # Ensure image is treated as an Image
    img_ee = ee.Image(image)
    qa = img_ee.select('QA_PIXEL')
    # Bits 3 (Cloud Shadow), 4 (Snow), 5 (Cloud)
    cloud_shadow_bit = 1 << 3
    snow_bit = 1 << 4
    cloud_bit = 1 << 5
    mask = qa.bitwiseAnd(cloud_shadow_bit).eq(0)\
             .And(qa.bitwiseAnd(snow_bit).eq(0))\
             .And(qa.bitwiseAnd(cloud_bit).eq(0))

    # Select SR bands (optical/SWIR), apply scaling, apply mask
    sr_bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'] # L8/9 bands needed
    scaled_bands = img_ee.select(sr_bands).multiply(0.0000275).add(-0.2)

    return scaled_bands.updateMask(mask)\
        .copyProperties(img_ee, ["system:time_start"])


# --- Index Calculation Functions ---
# These functions now expect images with COMMON band names
# Ensure they return the calculated index band *with the correct name*.

def calculate_ndvi(image):
    # Explicitly cast input to ee.Image
    img_ee = ee.Image(image)
    # Calculate the index first
    ndvi = img_ee.normalizedDifference(['NIR', 'Red'])
    # Rename the *result* of the calculation
    return ndvi.rename('NDVI')

def calculate_evi(image):
    img_ee = ee.Image(image)
    evi = img_ee.expression(
        '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
            'NIR': img_ee.select('NIR'),
            'RED': img_ee.select('Red'),
            'BLUE': img_ee.select('Blue')
        })
    return evi.rename('EVI')

def calculate_ndmi(image):
    img_ee = ee.Image(image)
    ndmi = img_ee.normalizedDifference(['NIR', 'SWIR1'])
    return ndmi.rename('NDMI')

def calculate_msi(image):
    img_ee = ee.Image(image)
    msi = img_ee.expression('SWIR1 / NIR', {
        'SWIR1': img_ee.select('SWIR1'),
        'NIR': img_ee.select('NIR')
    })
    return msi.rename('MSI')

def calculate_lai_simple(image):
    img_ee = ee.Image(image)
    try:
        # Attempt EVI calculation (which includes select)
        evi = img_ee.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                'NIR': img_ee.select('NIR'),
                'RED': img_ee.select('Red'),
                'BLUE': img_ee.select('Blue')
            })
        lai = evi.multiply(3.5).add(0.1)
    except Exception: # More general exception catch if select fails
        st.warning("EVI calculation failed for LAI (Blue band might be missing), using NDVI.", icon="⚠️")
        ndvi = img_ee.normalizedDifference(['NIR', 'Red'])
        lai = ndvi.multiply(5.0).add(0.1) # Placeholder NDVI-based LAI
    # Rename the final LAI calculation
    return lai.clamp(0, 8).rename('LAI')


def calculate_biomass_simple(image):
    img_ee = ee.Image(image)
    # Calculate LAI first (which handles its own renaming)
    lai_image = calculate_lai_simple(img_ee) # This returns an image named 'LAI'
    # Select the 'LAI' band from the result
    lai = lai_image.select('LAI')
    a = 1.5
    b = 0.2
    biomass = lai.multiply(a).add(b)
    # Rename the final biomass calculation
    return biomass.clamp(0, 50).rename('Biomass')

def calculate_chlorophyll_mcari(image):
    img_ee = ee.Image(image)
    try:
        # Check if RedEdge1 exists by selecting it
        img_ee.select('RedEdge1')
        mcari = img_ee.expression(
            '((RE1 - RED) - 0.2 * (RE1 - GREEN)) * (RE1 / RED)', {
                'RE1': img_ee.select('RedEdge1'),
                'RED': img_ee.select('Red'),
                'GREEN': img_ee.select('Green')
            })
        # Rename the result
        return mcari.rename('Chlorophyll')
    except ee.EEException:
         st.warning("MCARI requires Sentinel-2 Red Edge band. Using NDVI as Chlorophyll proxy.", icon="⚠️")
         # Calculate NDVI and rename the result
         ndvi = img_ee.normalizedDifference(['NIR', 'Red'])
         return ndvi.rename('Chlorophyll') # Ensure fallback also renames correctly


def calculate_et_placeholder(image):
    img_ee = ee.Image(image)
    st.warning("ET calculation is complex. Using NDMI as a proxy for moisture status.", icon="⚠️")
    # Calculate NDMI and rename the result
    ndmi = img_ee.normalizedDifference(['NIR', 'SWIR1'])
    return ndmi.rename('ET_proxy')


# (INDEX_FUNCTIONS dictionary remains the same)
INDEX_FUNCTIONS = {
    'NDVI': {'func': calculate_ndvi, 'vis': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}},
    'EVI': {'func': calculate_evi, 'vis': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}},
    'NDMI': {'func': calculate_ndmi, 'vis': {'min': -0.5, 'max': 0.8, 'palette': ['brown', 'white', 'blue']}},
    'MSI': {'func': calculate_msi, 'vis': {'min': 0.5, 'max': 2.5, 'palette': ['green', 'yellow', 'red']}},
    'LAI': {'func': calculate_lai_simple, 'vis': {'min': 0, 'max': 8, 'palette': ['white', 'lightgreen', 'darkgreen']}},
    'Biomass': {'func': calculate_biomass_simple, 'vis': {'min': 0, 'max': 30, 'palette': ['beige', 'yellow', 'brown']}},
    'Chlorophyll': {'func': calculate_chlorophyll_mcari, 'vis': {'min': 0, 'max': 1, 'palette': ['yellow', 'lightgreen', 'darkgreen']}},
    'ET_proxy': {'func': calculate_et_placeholder, 'vis': {'min': -0.5, 'max': 0.8, 'palette': ['brown', 'white', 'blue']}}
}

# --- GEE Data Retrieval ---
def get_image_collection(start_date, end_date, geometry=None, sensor='Sentinel-2'):
    """Gets, filters, masks, scales, and renames Sentinel-2 or Landsat images."""
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    bands_to_select_orig = []
    bands_to_rename_to = []
    mask_func = None
    collection = None

    if sensor == 'Sentinel-2':
        collection_id = 'COPERNICUS/S2_SR_HARMONIZED'
        mask_func = mask_s2_clouds
        bands_to_select_orig = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12', 'QA60']
        bands_to_rename_to = ['Blue', 'Green', 'Red', 'RedEdge1', 'NIR', 'SWIR1', 'SWIR2']
        collection = ee.ImageCollection(collection_id)

    elif sensor == 'Landsat':
        l9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
        l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        collection = l9.merge(l8)
        mask_func = mask_landsat_clouds
        bands_to_select_orig = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'QA_PIXEL']
        bands_to_rename_to = ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2']

    else:
        st.error("Sensor not supported")
        return None

    collection = collection.filterDate(start_date_str, end_date_str)
    if geometry:
        collection = collection.filterBounds(geometry)

    initial_count = collection.size().getInfo()
    if initial_count == 0:
        st.warning(f"No images found for the selected period and area using {sensor} before cloud masking.")
        return None

    # --- Processing Function ---
    def process_image(image_element):
        # Explicitly cast the input element to ee.Image
        image = ee.Image(image_element)

        # 1. Select original bands
        img_selected_orig = image.select(bands_to_select_orig)

        # 2. Apply masking and scaling
        img_processed = mask_func(img_selected_orig) # mask_func should return ee.Image

        # Ensure img_processed is an image before renaming
        img_processed_safe = ee.Image(img_processed)

        # 3. Rename the processed bands
        img_renamed = img_processed_safe.rename(bands_to_rename_to)

        # 4. Copy properties from the *original* image element
        return img_renamed.copyProperties(image, ["system:time_start"])

    # Map the processing function
    processed_collection = collection.map(process_image)

    # Check count after processing
    count = processed_collection.size().getInfo()
    if count == 0:
        st.warning(f"No cloud-free images found for the selected period and area using {sensor}.")
        return None

    # Verify bands in the first image (optional but good practice)
    try:
        first_image = processed_collection.first()
        if first_image is None:
             st.error("Collection became empty after processing map function.")
             return None
        final_bands = ee.Image(first_image).bandNames().getInfo() # Cast just in case
        print(f"Final bands in processed collection: {final_bands}")
        # Basic check (adjust for Landsat vs S2)
        expected_check = bands_to_rename_to
        if not all(name in final_bands for name in expected_check):
            st.warning(f"Warning: Not all expected common bands ({expected_check}) found. Available: {final_bands}", icon="⚠️")
    except ee.EEException as e:
        st.error(f"Error verifying processed bands: {e}")
        return None

    return processed_collection


def calculate_indices_for_collection(collection, index_list):
    """Maps index calculation functions over a processed collection."""
    if collection is None:
        st.warning("Input collection is None in calculate_indices_for_collection")
        return None

    calculated_collection = collection # Start with the input collection
    try:
        first_image = collection.first()
        if first_image is None:
            st.warning("Collection is empty in calculate_indices_for_collection")
            return None # Return None if collection is empty
        bands_available = ee.Image(first_image).bandNames().getInfo()
        print(f"Bands available for index calculation: {bands_available}")
    except ee.EEException as e:
        st.error(f"GEE error checking bands in calculate_indices_for_collection: {e}")
        return None # Return None if there's an error checking bands


    # Check if bands_available is usable
    if not isinstance(bands_available, list):
        st.error(f"Could not retrieve valid band list: {bands_available}")
        return None


    for index_name in index_list:
        if index_name in INDEX_FUNCTIONS:
            # Function to apply the specific index calculation
            index_function = INDEX_FUNCTIONS[index_name]['func']

            # Add a mapping step to the collection
            # The index function itself now handles renaming
            try:
                 print(f"Mapping function for {index_name}...")
                 # Important: the result of map replaces the previous collection
                 # The index function should add the new band OR return only the index band
                 # Let's assume functions ADD the band
                 calculated_collection = calculated_collection.map(
                     lambda img: ee.Image(img).addBands(index_function(img))
                     )
                 # Verify the band was added (optional check)
                 # check_bands = ee.Image(calculated_collection.first()).bandNames().getInfo()
                 # print(f"Bands after adding {index_name}: {check_bands}")

                 print(f"Calculated and added band for {index_name}")
            except ee.EEException as e:
                 st.warning(f"GEE Error mapping function for {index_name}: {e}. Skipping.", icon="⚠️")
                 # Continue with the collection as it was before this failed index
            except Exception as e:
                 st.warning(f"Non-GEE Error mapping function for {index_name}: {e}. Skipping.", icon="⚠️")

        else:
            st.warning(f"Index function for '{index_name}' not defined.")

    return calculated_collection


# --- get_timeseries_for_farm ---
@st.cache_data(ttl=3600)
def get_timeseries_for_farm(_farm_geom_geojson, start_date, end_date, index_name, sensor):
    """Retrieves the time series for a specific index and farm geometry."""
    farm_geom = ee.Geometry(json.loads(_farm_geom_geojson))

    collection = get_image_collection(start_date, end_date, farm_geom, sensor)
    if collection is None:
        return pd.DataFrame(columns=['Date', index_name])

    # Calculate *only* the required index
    index_func_detail = INDEX_FUNCTIONS.get(index_name)
    if not index_func_detail:
         st.error(f"Index function for {index_name} not found.")
         return pd.DataFrame(columns=['Date', index_name])

    # Check if calculation is feasible *before* mapping
    try:
        first_img = collection.first()
        if not first_img:
            st.warning("Collection is empty before index calculation for timeseries.", icon="⚠️")
            return pd.DataFrame(columns=['Date', index_name])
        # You might add more sophisticated band checks here if needed
    except ee.EEException as e:
        st.error(f"GEE error checking collection before timeseries calculation: {e}")
        return pd.DataFrame(columns=['Date', index_name])


    # Map the function to calculate the index - it should return an image with the index band
    try:
        indexed_collection = collection.map(index_func_detail['func'])
    except Exception as e:
        st.error(f"Error mapping index function '{index_name}' for timeseries: {e}")
        return pd.DataFrame(columns=['Date', index_name])


    # Check if the target index band exists after mapping
    try:
         first_img_check = indexed_collection.first()
         if first_img_check is None or index_name not in ee.Image(first_img_check).bandNames().getInfo():
              st.warning(f"Index band '{index_name}' not found after calculation for timeseries.", icon="⚠️")
              return pd.DataFrame(columns=['Date', index_name])
    except ee.EEException as e:
         st.error(f"GEE Error checking index band for timeseries: {e}")
         return pd.DataFrame(columns=['Date', index_name])

    # Define the extraction function (remains the same)
    def extract_value(image):
        # Ensure operating on an image
        img_ee = ee.Image(image)
        stats = img_ee.select(index_name).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=farm_geom,
            scale=30,
            maxPixels=1e9,
            tileScale=4
        )
        val = stats.get(index_name)
        # Ensure time is retrieved from the image element
        time_ms = img_ee.get('system:time_start')
        return ee.Feature(None, {
            'time': time_ms,
            index_name: ee.Algorithms.If(val, val, -9999) # Use placeholder for null
            })

    # Execute the extraction
    try:
        ts_info = indexed_collection.map(extract_value).getInfo()
    except ee.EEException as e:
        st.error(f"Error extracting timeseries values (reduceRegion): {e}")
        st.info("This might be due to GEE memory limits or timeouts. Try a smaller date range or area.")
        return pd.DataFrame(columns=['Date', index_name])

    # Process results (remains the same)
    data = []
    if 'features' in ts_info:
        for feature in ts_info['features']:
            value = feature.get('properties', {}).get(index_name)
            time_ms = feature.get('properties', {}).get('time')
            if value not in [None, -9999] and time_ms is not None:
                try:
                    dt = datetime.datetime.fromtimestamp(time_ms / 1000.0)
                    data.append([dt, value])
                except (TypeError, ValueError) as time_e:
                     st.warning(f"Skipping invalid timestamp ({time_ms}): {time_e}", icon="⚠️")
    else:
         st.warning("No 'features' key found in timeseries getInfo result.")


    if not data:
        return pd.DataFrame(columns=['Date', index_name])

    ts_df = pd.DataFrame(data, columns=['Date', index_name])
    ts_df = ts_df.sort_values(by='Date')
    return ts_df

# --- get_latest_index_for_ranking ---
# (Keep get_latest_index_for_ranking similar to the previous version,
# ensuring it calls the updated get_image_collection and index functions correctly.
# Add explicit ee.Image casts if needed within its reduceRegions part, although less likely there.)
@st.cache_data(ttl=3600)
def get_latest_index_for_ranking(_farms_df_json, selected_day, start_date, end_date, index_name, sensor):
    """Gets the median index value for ranking farms active on a selected day."""
    farms_df = pd.read_json(_farms_df_json)
    if selected_day != "همه روزها":
        farms_df_filtered = farms_df[farms_df['روزهای هفته'] == selected_day].copy()
    else:
        farms_df_filtered = farms_df.copy()

    if farms_df_filtered.empty:
        return pd.DataFrame(columns=['مزرعه', index_name])

    features = []
    for idx, row in farms_df_filtered.iterrows():
        try:
             # Check for valid coordinates before creating geometry
             lon = row['طول جغرافیایی']
             lat = row['عرض جغرافیایی']
             if pd.notna(lon) and pd.notna(lat):
                 geom = ee.Geometry.Point([lon, lat])
                 buffered_geom = geom.buffer(50)
                 feature = ee.Feature(buffered_geom, {'farm_id': row['مزرعه']})
                 features.append(feature)
             else:
                  st.warning(f"Skipping farm {row.get('مزرعه', 'Unknown')} due to invalid coordinates.", icon="⚠️")
        except Exception as e:
             st.warning(f"Skipping farm {row.get('مزرعه', 'Unknown')} due to geometry error: {e}", icon="⚠️")

    if not features:
         st.warning("No valid farm geometries found for ranking.", icon="⚠️")
         return pd.DataFrame(columns=['مزرعه', index_name])

    farm_fc = ee.FeatureCollection(features)

    collection = get_image_collection(start_date, end_date, farm_fc.geometry(), sensor)
    if collection is None:
        st.warning("Base image collection is None for ranking.")
        return pd.DataFrame(columns=['مزرعه', index_name])

    # Calculate only the required index
    index_func_detail = INDEX_FUNCTIONS.get(index_name)
    if not index_func_detail:
        st.error(f"Index function for {index_name} not found for ranking.")
        return pd.DataFrame(columns=['مزرعه', index_name])

    # Check feasibility before mapping
    try:
        first_img = collection.first()
        if not first_img:
            st.warning("Collection is empty before index calculation for ranking.", icon="⚠️")
            return pd.DataFrame(columns=['مزرعه', index_name])
        # Add band checks if needed
    except ee.EEException as e:
        st.error(f"GEE error checking collection before ranking calculation: {e}")
        return pd.DataFrame(columns=['مزرعه', index_name])

    # Map the function to calculate the index
    try:
        indexed_collection = collection.map(index_func_detail['func'])
    except Exception as e:
        st.error(f"Error mapping index function '{index_name}' for ranking: {e}")
        return pd.DataFrame(columns=['مزرعه', index_name])


    # Check if the target index band exists after mapping
    try:
         first_img_check = indexed_collection.first()
         if first_img_check is None:
             st.warning(f"Indexed collection is empty for ranking ('{index_name}').", icon="⚠️")
             return pd.DataFrame(columns=['مزرعه', index_name])
         # Cast to ee.Image for safety before getInfo
         if index_name not in ee.Image(first_img_check).bandNames().getInfo():
              st.warning(f"Index band '{index_name}' not found after calculation for ranking.", icon="⚠️")
              return pd.DataFrame(columns=['مزرعه', index_name])
    except ee.EEException as e:
         st.error(f"GEE Error checking index band for ranking: {e}")
         return pd.DataFrame(columns=['مزرعه', index_name])


    # Create a median composite over the period
    # Select the specific index band *before* compositing
    median_image = indexed_collection.select(index_name).median()

    # Reduce the composite image over the farm geometries
    try:
        farm_values = median_image.reduceRegions(
            collection=farm_fc,
            reducer=ee.Reducer.mean(),
            scale=30,
            tileScale=8 # Use larger tileScale
        ).getInfo()
    except ee.EEException as e:
        st.error(f"Error during reduceRegions for ranking: {e}")
        st.warning("Could not calculate farm rankings. Try reducing the date range or number of farms.")
        return pd.DataFrame(columns=['مزرعه', index_name])

    # Extract results (remains the same)
    ranking_data = []
    if 'features' in farm_values:
        for feature in farm_values['features']:
            farm_id = feature.get('properties', {}).get('farm_id')
            value = feature.get('properties', {}).get('mean') # Default output name
            if farm_id is not None and value is not None:
                ranking_data.append({'مزرعه': farm_id, index_name: value})
            else:
                # Log farms where reduction failed?
                 pass
    else:
        st.warning("No 'features' key found in ranking getInfo result.")


    if not ranking_data:
         st.warning("No ranking data could be extracted after GEE processing.", icon="⚠️")
         return pd.DataFrame(columns=['مزرعه', index_name])

    ranking_df = pd.DataFrame(ranking_data)
    ascending_sort = False if index_name not in ['MSI'] else True
    ranking_df = ranking_df.sort_values(by=index_name, ascending=ascending_sort, na_position='last').reset_index(drop=True)

    return ranking_df

# --- Streamlit App Layout ---
# (The Streamlit layout part (st.set_page_config, sidebar, columns, map display, details, ranking table)
# can remain largely the same as the previous version, as the core logic changes were in the GEE functions)
# Ensure the map display part correctly calls get_image_collection and processes the result.
# It should select the final index band from the median image for display.

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

# Initialize GEE
if initialize_gee():
    # Load data
    farm_data_df = load_data(CSV_FILE_PATH)

    # --- Sidebar ---
    st.sidebar.header("تنظیمات نمایش")
    default_end_date = datetime.date.today()
    default_start_date = default_end_date - datetime.timedelta(days=7)
    start_date = st.sidebar.date_input("تاریخ شروع", value=default_start_date, max_value=default_end_date)
    end_date = st.sidebar.date_input("تاریخ پایان", value=default_end_date, min_value=start_date, max_value=default_end_date)
    days_list = ["همه روزها"] + sorted(farm_data_df['روزهای هفته'].unique().tolist())
    selected_day = st.sidebar.selectbox("فیلتر بر اساس روز هفته", options=days_list)

    if selected_day == "همه روزها":
        filtered_df = farm_data_df.copy()
    else:
        filtered_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day].copy()

    farm_list = ["همه مزارع"] + sorted(filtered_df['مزرعه'].unique().tolist())
    selected_farm = st.sidebar.selectbox("انتخاب مزرعه", options=farm_list)
    available_indices = list(INDEX_FUNCTIONS.keys())
    selected_index = st.sidebar.selectbox("انتخاب شاخص", options=available_indices)
    selected_sensor = st.sidebar.radio("انتخاب سنسور ماهواره", ('Sentinel-2', 'Landsat'), index=0, key='sensor_select')

    # --- Main Panel ---
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader("نقشه وضعیت مزارع")
        map_placeholder = st.empty() # Placeholder for the map

        # Initialize Map
        m = geemap.Map(center=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False)
        m.add_basemap('HYBRID')

        vis_params = INDEX_FUNCTIONS.get(selected_index, {}).get('vis')
        if not vis_params:
            st.error(f"Visualization parameters not found for index: {selected_index}")
            vis_params = {'min': 0, 'max': 1, 'palette': ['white', 'gray']} # Basic default

        # Determine display geometry
        display_geom = None
        target_object_for_map = None
        farm_info_for_popup = None # Store farm info if single farm selected

        if selected_farm == "همه مزارع":
            if not filtered_df.empty:
                min_lon, min_lat = filtered_df['طول جغرافیایی'].min(), filtered_df['عرض جغرافیایی'].min()
                max_lon, max_lat = filtered_df['طول جغرافیایی'].max(), filtered_df['عرض جغرافیایی'].max()
                if pd.notna([min_lon, min_lat, max_lon, max_lat]).all():
                    display_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
                    target_object_for_map = display_geom
                else:
                    st.warning("Could not determine valid bounds for selected farms.", icon="⚠️")
            else:
                 st.info("هیچ مزرعه‌ای برای نمایش با فیلترهای انتخاب شده یافت نشد.")
        else: # Single farm
            farm_info_rows = filtered_df[filtered_df['مزرعه'] == selected_farm]
            if not farm_info_rows.empty:
                 farm_info_for_popup = farm_info_rows.iloc[0] # Save for later use
                 farm_lat = farm_info_for_popup['عرض جغرافیایی']
                 farm_lon = farm_info_for_popup['طول جغرافیایی']
                 if pd.notna(farm_lat) and pd.notna(farm_lon):
                     farm_geom = ee.Geometry.Point([farm_lon, farm_lat])
                     display_geom = farm_geom.buffer(150) # Buffer for visualization
                     target_object_for_map = farm_geom # Center on the point
                 else:
                      st.warning(f"مختصات نامعتبر برای مزرعه {selected_farm}.", icon="⚠️")
                      farm_info_for_popup = None # Invalidate popup info
            else:
                 st.warning(f"اطلاعات مزرعه {selected_farm} یافت نشد.", icon="⚠️")

        # Fetch data and display on map
        if display_geom:
            with st.spinner(f"در حال پردازش تصویر {selected_index} برای منطقه/مزرعه..."):
                 collection = get_image_collection(start_date, end_date, display_geom, selected_sensor)

                 if collection:
                     # Calculate the selected index
                     index_func_detail = INDEX_FUNCTIONS.get(selected_index)
                     if index_func_detail:
                         try:
                            # Map the function to calculate the index
                            indexed_collection = collection.map(index_func_detail['func'])

                            # Check if the index band exists
                            first_img_check = indexed_collection.first()
                            if first_img_check and selected_index in ee.Image(first_img_check).bandNames().getInfo():
                                # Create median composite, selecting only the index band
                                median_image = indexed_collection.select(selected_index).median()

                                # Clip layer if single farm selected
                                layer_image = median_image.clip(display_geom) if selected_farm != "همه مزارع" else median_image

                                # Add layer to map
                                m.addLayer(layer_image, vis_params, f'{selected_index} (Median)')
                                try:
                                    m.add_legend(title=f'{selected_index}', builtin_legend=None, palette=vis_params['palette'], min=vis_params['min'], max=vis_params['max'])
                                except Exception as legend_e:
                                    st.warning(f"Could not add legend: {legend_e}", icon="⚠️")

                                # Add download button
                                try:
                                    thumb_url = median_image.getThumbURL({ # Use median_image which has only the index band
                                        'region': display_geom.toGeoJson(),
                                        'bands': selected_index, # Already selected this band
                                        'palette': vis_params['palette'],
                                        'min': vis_params['min'],
                                        'max': vis_params['max'],
                                        'dimensions': 512
                                    })
                                    response = requests.get(thumb_url)
                                    if response.status_code == 200:
                                        img_bytes = BytesIO(response.content)
                                        st.sidebar.download_button(
                                            label=f"دانلود نقشه ({selected_index})",
                                            data=img_bytes,
                                            file_name=f"map_{selected_farm if selected_farm != 'همه مزارع' else 'all'}_{selected_index}.png",
                                            mime="image/png",
                                            key=f"download_{selected_index}_{selected_farm}" # More specific key
                                        )
                                    else:
                                        st.sidebar.warning(f"Download link failed (Status: {response.status_code}).", icon="⚠️")
                                except Exception as thumb_e:
                                    st.sidebar.warning(f"Error generating download link: {thumb_e}", icon="⚠️")

                            else:
                                st.warning(f"Index band '{selected_index}' not found after calculation for map.", icon="⚠️")

                         except Exception as map_calc_e:
                              st.error(f"Error calculating index '{selected_index}' for map: {map_calc_e}")

                     else:
                          st.error(f"Index function definition missing for {selected_index}")
                 else:
                    st.warning(f"No suitable satellite images found for the selected period/area.", icon="⚠️")


            # Add markers AFTER potentially adding the layer
            if selected_farm == "همه مزارع" and not filtered_df.empty:
                 for idx, row in filtered_df.iterrows():
                      if pd.notna(row['عرض جغرافیایی']) and pd.notna(row['طول جغرافیایی']):
                           popup_html = f"<b>مزرعه:</b> {row['مزرعه']}<br><b>کانال:</b> {row['کانال']}<br><b>مساحت:</b> {row['مساحت داشت']:.2f}<br><b>واریته:</b> {row['واریته']}"
                           folium.Marker(
                               location=[row['عرض جغرافیایی'], row['طول جغرافیایی']],
                               popup=folium.Popup(popup_html, max_width=200),
                               tooltip=f"مزرعه {row['مزرعه']}",
                               icon=folium.Icon(color='blue', icon='info-sign')
                           ).add_to(m)
            elif farm_info_for_popup is not None: # Single farm selected and info is valid
                farm_info = farm_info_for_popup # Use the saved info
                popup_html = f"<b>مزرعه:</b> {farm_info['مزرعه']}<br><b>کانال:</b> {farm_info['کانال']}<br><b>اداره:</b> {farm_info['اداره']}<br><b>مساحت:</b> {farm_info['مساحت داشت']:.2f}<br><b>واریته:</b> {farm_info['واریته']}<br><b>سن:</b> {farm_info['سن ']}"
                folium.Marker(
                    location=[farm_info['عرض جغرافیایی'], farm_info['طول جغرافیایی']],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"مزرعه {farm_info['مزرعه']}",
                    icon=folium.Icon(color='red', icon='star')
                ).add_to(m)

            # Center the map
            if target_object_for_map:
                zoom_level = INITIAL_ZOOM + 2 if selected_farm != "همه مزارع" else INITIAL_ZOOM
                m.center_object(target_object_for_map, zoom=zoom_level)

        # Render the map
        with map_placeholder:
             m.to_streamlit(height=500)

    # --- Column 2: Details / Ranking ---
    with col2:
        if selected_farm != "همه مزارع":
            # Display details (using farm_info_for_popup if valid)
            st.subheader(f"جزئیات مزرعه: {selected_farm}")
            if farm_info_for_popup is not None:
                farm_info = farm_info_for_popup
                st.metric("کانال", str(farm_info['کانال']))
                st.metric("اداره", str(farm_info['اداره']))
                st.metric("مساحت داشت (هکتار)", f"{farm_info['مساحت داشت']:.2f}" if pd.notna(farm_info['مساحت داشت']) else "N/A")
                st.metric("واریته", str(farm_info['واریته']))
                st.metric("سن", str(farm_info['سن ']))
                st.metric("روز آبیاری", str(farm_info['روزهای هفته']))
                st.metric("وضعیت مختصات", "موجود" if farm_info['coordinates_missing'] == 0 else "گمشده")

                # Timeseries Chart
                st.subheader(f"روند شاخص {selected_index}")
                if pd.notna(farm_info['عرض جغرافیایی']) and pd.notna(farm_info['طول جغرافیایی']):
                    with st.spinner(f"در حال دریافت سری زمانی {selected_index} برای مزرعه {selected_farm}..."):
                        farm_geom = ee.Geometry.Point([farm_info['طول جغرافیایی'], farm_info['عرض جغرافیایی']])
                        ts_df = get_timeseries_for_farm(farm_geom.toGeoJsonString(), start_date, end_date, selected_index, selected_sensor)

                    if not ts_df.empty:
                        fig = px.line(ts_df, x='Date', y=selected_index, title=f"روند زمانی {selected_index}", markers=True)
                        fig.update_layout(xaxis_title="تاریخ", yaxis_title=selected_index)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning(f"داده‌ای برای نمایش نمودار روند زمانی {selected_index} یافت نشد.", icon="📉")
                else:
                    st.warning("مختصات نامعتبر برای دریافت سری زمانی.", icon="📍")
            else:
                 st.info("اطلاعات این مزرعه برای روز هفته یا انتخاب فعلی موجود نیست.")

        else: # "همه مزارع" is selected - Display Ranking
            st.subheader(f"رتبه‌بندی مزارع بر اساس {selected_index}")
            st.info(f"نمایش میانگین مقدار شاخص '{selected_index}' در بازه زمانی برای مزارع فعال در '{selected_day}'.")
            with st.spinner(f"در حال محاسبه رتبه‌بندی مزارع بر اساس {selected_index}..."):
                ranking_df = get_latest_index_for_ranking(filtered_df.to_json(), selected_day, start_date, end_date, selected_index, selected_sensor)

            if not ranking_df.empty:
                if selected_index in ranking_df.columns:
                     st.dataframe(ranking_df.style.format({selected_index: "{:.3f}"}), use_container_width=True)
                else:
                     st.dataframe(ranking_df, use_container_width=True)
                csv = ranking_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                   label=f"دانلود جدول رتبه‌بندی ({selected_index})",
                   data=csv,
                   file_name=f'ranking_{selected_index}_{selected_day}.csv',
                   mime='text/csv',
                   key='download_ranking'
                 )
            else:
                st.warning("اطلاعاتی برای رتبه‌بندی مزارع یافت نشد.", icon="📊")

else:
    st.warning("لطفا صبر کنید تا اتصال به Google Earth Engine برقرار شود یا خطاهای نمایش داده شده را بررسی کنید.", icon="⏳")

# Footer
st.sidebar.markdown("---")
st.sidebar.info("راهنما: از منوها برای انتخاب بازه زمانی، روز هفته، مزرعه و شاخص استفاده کنید.")