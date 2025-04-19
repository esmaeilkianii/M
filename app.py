import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
from folium import plugins
import datetime
import time
import json
import os
import plotly.express as px
from dateutil.relativedelta import relativedelta

# ==============================================================================
# Configuration and Initialization
# ==============================================================================

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="داشبورد مانیتورینگ مزارع نیشکر دهخدا",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Constants ---
CSV_FILE_PATH = 'output (1).csv'  # Path to your CSV file
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json' # Path to your GEE Service Account JSON file
DEFAULT_LATITUDE = 31.534442
DEFAULT_LONGITUDE = 48.724416
INITIAL_ZOOM = 11
DATE_FORMAT = "%Y-%m-%d"

# --- GEE Authentication ---
@st.cache_resource(show_spinner="در حال اتصال به Google Earth Engine...")
def authenticate_gee(service_account_file):
    """Authenticates to Google Earth Engine using a service account."""
    try:
        # Check if the service account file exists
        if not os.path.exists(service_account_file):
            st.error(f"فایل Service Account در مسیر '{service_account_file}' یافت نشد.")
            st.stop()

        # Load credentials from the file
        with open(service_account_file) as f:
            credentials_dict = json.load(f)

        credentials = ee.ServiceAccountCredentials(
            email=credentials_dict['client_email'],
            key_data=json.dumps(credentials_dict) # Pass the whole dict as key_data
        )
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Authenticated Successfully using Service Account.")
        return True # Indicate success
    except ee.EEException as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.error("لطفاً از صحت فایل Service Account و فعال بودن آن اطمینان حاصل کنید.")
        return False
    except FileNotFoundError:
        st.error(f"فایل Service Account در مسیر '{service_account_file}' یافت نشد.")
        return False
    except json.JSONDecodeError:
        st.error(f"فایل Service Account ('{service_account_file}') معتبر نیست یا فرمت JSON صحیحی ندارد.")
        return False
    except Exception as e:
        st.error(f"خطای پیش‌بینی نشده در اتصال به GEE: {e}")
        return False

# Perform authentication
if not authenticate_gee(SERVICE_ACCOUNT_FILE):
    st.stop() # Stop execution if authentication fails

# --- Load Data ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data(csv_path):
    """Loads farm data from the CSV file."""
    try:
        df = pd.read_csv(csv_path)
        # Basic validation
        required_columns = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته', 'coordinates_missing']
        if not all(col in df.columns for col in required_columns):
            st.error(f"فایل CSV باید شامل ستون‌های {required_columns} باشد.")
            st.stop()
        # Convert coordinate columns to numeric, coercing errors
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        # Handle missing coordinates flag more robustly
        df['coordinates_missing'] = df['coordinates_missing'].fillna(False).astype(bool) | df['طول جغرافیایی'].isna() | df['عرض جغرافیایی'].isna()

        # Filter out farms with missing coordinates for mapping/GEE analysis
        df_valid_coords = df[~df['coordinates_missing']].copy()
        df_valid_coords['geometry'] = df_valid_coords.apply(
            lambda row: ee.Geometry.Point([row['طول جغرافیایی'], row['عرض جغرافیایی']]), axis=1
        )
        return df, df_valid_coords
    except FileNotFoundError:
        st.error(f"فایل CSV در مسیر '{csv_path}' یافت نشد.")
        st.stop()
    except Exception as e:
        st.error(f"خطا در بارگذاری یا پردازش فایل CSV: {e}")
        st.stop()

farm_data_full, farm_data_valid = load_farm_data(CSV_FILE_PATH)

# ==============================================================================
# GEE Functions
# ==============================================================================

# --- Cloud Masking ---
def mask_s2_clouds(image):
    """Masks clouds in Sentinel-2 images."""
    qa = image.select('QA60')
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0) \
             .And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000) # Scale factor for S2

def mask_landsat_clouds(image):
    """Masks clouds in Landsat 8/9 images using the QA_PIXEL band."""
    qa_pixel = image.select('QA_PIXEL')
    # Bits 3 and 4 are cloud shadow and cloud, respectively.
    cloud_shadow_bit = 1 << 3
    cloud_bit = 1 << 4
    # Mask is clear if both bits are 0.
    mask = qa_pixel.bitwiseAnd(cloud_shadow_bit).eq(0) \
                   .And(qa_pixel.bitwiseAnd(cloud_bit).eq(0))
    return image.updateMask(mask).select("SR_B.*").multiply(0.0000275).add(-0.2) # Apply scale factors for Landsat Collection 2 SR


# --- Image Collection Retrieval ---
def get_image_collection(aoi, start_date, end_date, source='Sentinel-2'):
    """Gets a cloud-masked image collection for a given AOI and date range."""
    if source == 'Sentinel-2':
        collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                       .filterBounds(aoi) \
                       .filterDate(start_date, end_date) \
                       .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
                       .map(mask_s2_clouds)
    elif source == 'Landsat': # Combine Landsat 8 and 9
         collection_l9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2') \
            .filterBounds(aoi) \
            .filterDate(start_date, end_date) \
            .map(mask_landsat_clouds)
         collection_l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
            .filterBounds(aoi) \
            .filterDate(start_date, end_date) \
            .map(mask_landsat_clouds)
         collection = collection_l8.merge(collection_l9).sort('system:time_start')
    else:
        raise ValueError("منبع تصویر نامعتبر است. 'Sentinel-2' یا 'Landsat' را انتخاب کنید.")

    return collection

# --- Index Calculation Functions ---
def calculate_ndvi(image, source='Sentinel-2'):
    if source == 'Sentinel-2':
        nir = image.select('B8')
        red = image.select('B4')
    elif source == 'Landsat':
        nir = image.select('SR_B5')
        red = image.select('SR_B4')
    else:
        raise ValueError("منبع نامعتبر")
    return image.addBands(nir.subtract(red).divide(nir.add(red)).rename('NDVI'))

def calculate_ndmi(image, source='Sentinel-2'):
    if source == 'Sentinel-2':
        nir = image.select('B8')
        swir1 = image.select('B11')
    elif source == 'Landsat':
        nir = image.select('SR_B5')
        swir1 = image.select('SR_B6')
    else:
        raise ValueError("منبع نامعتبر")
    return image.addBands(nir.subtract(swir1).divide(nir.add(swir1)).rename('NDMI'))

def calculate_evi(image, source='Sentinel-2'):
    if source == 'Sentinel-2':
        nir = image.select('B8')
        red = image.select('B4')
        blue = image.select('B2')
        evi = image.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                'NIR': nir, 'RED': red, 'BLUE': blue
            }).rename('EVI')
    elif source == 'Landsat':
        nir = image.select('SR_B5')
        red = image.select('SR_B4')
        blue = image.select('SR_B2')
        evi = image.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                'NIR': nir, 'RED': red, 'BLUE': blue
            }).rename('EVI')
    else:
        raise ValueError("منبع نامعتبر")
    return image.addBands(evi)

def calculate_msi(image, source='Sentinel-2'):
    # Moisture Stress Index
    if source == 'Sentinel-2':
        swir1 = image.select('B11')
        nir = image.select('B8')
    elif source == 'Landsat':
        swir1 = image.select('SR_B6')
        nir = image.select('SR_B5')
    else:
        raise ValueError("منبع نامعتبر")
    return image.addBands(swir1.divide(nir).rename('MSI'))

# Placeholder functions for complex indices - require more specific algorithms/data
def calculate_lai(image, source='Sentinel-2'):
    # Simple LAI estimation using NDVI (needs calibration)
    # Example: LAI = a * exp(b * NDVI) - adjust coefficients a, b
    # Or use established GEE LAI products if available (e.g., MODIS)
    ndvi = calculate_ndvi(image.select([]).addBands(image), source).select('NDVI') # Ensure NDVI is calculated first
    # Using a generic formula for demonstration - replace with a calibrated one
    lai = ndvi.multiply(5.0).exp().multiply(0.1).rename('LAI') # Example: 0.1 * exp(5.0 * NDVI)
    return image.addBands(lai)

def calculate_biomass(image, source='Sentinel-2'):
    # Simple Biomass estimation using LAI (needs calibration)
    # Example: Biomass = a * LAI + b - adjust coefficients a, b
    lai = calculate_lai(image.select([]).addBands(image), source).select('LAI') # Ensure LAI is calculated first
    # Using generic coefficients for demonstration
    a = 1.5 # Example coefficient
    b = 0.5 # Example coefficient
    biomass = lai.multiply(a).add(b).rename('Biomass')
    return image.addBands(biomass)

def calculate_et(image, source='Sentinel-2'):
    # Evapotranspiration - Very complex. Using NDVI as a proxy indicator for demonstration.
    # Real ET requires meteorological data and models (e.g., Penman-Monteith, SSEBop).
    # Consider using MODIS ET product ('MODIS/061/MOD16A2') if temporal/spatial resolution fits.
    ndvi = calculate_ndvi(image.select([]).addBands(image), source).select('NDVI')
    # Simple proxy: Higher NDVI often correlates with higher ET in vegetated areas
    et_proxy = ndvi.multiply(10).rename('ET_Proxy') # Scale NDVI to an arbitrary ET range
    return image.addBands(et_proxy)

def calculate_chlorophyll(image, source='Sentinel-2'):
    # Chlorophyll Index - Example using MCARI (Modified Chlorophyll Absorption Ratio Index)
    # MCARI = ((REdge - Red) - 0.2 * (REdge - Green)) * (REdge / Red)
    # Requires Red Edge bands (available in Sentinel-2)
    if source == 'Sentinel-2':
        red = image.select('B4')
        green = image.select('B3')
        red_edge = image.select('B5') # Using B5 as a representative Red Edge band
        mcari = ((red_edge.subtract(red)).subtract(red_edge.subtract(green).multiply(0.2))).multiply(red_edge.divide(red))
        return image.addBands(mcari.rename('Chlorophyll'))
    elif source == 'Landsat':
        # Landsat doesn't have the same Red Edge bands. Use a different index or proxy.
        # Example: Using NDVI as a simple proxy for chlorophyll content
        ndvi = calculate_ndvi(image.select([]).addBands(image), source).select('NDVI')
        return image.addBands(ndvi.rename('Chlorophyll_Proxy'))
    else:
        raise ValueError("منبع نامعتبر")

# --- Index Dictionary ---
INDEX_FUNCTIONS = {
    'NDVI': calculate_ndvi,
    'NDMI': calculate_ndmi,
    'EVI': calculate_evi,
    'MSI': calculate_msi,
    'LAI': calculate_lai,          # Placeholder/Simple Estimation
    'Biomass': calculate_biomass,  # Placeholder/Simple Estimation
    'ET': calculate_et,            # Placeholder/Proxy
    'Chlorophyll': calculate_chlorophyll # Placeholder/Proxy for Landsat
}

INDEX_PALETTES = {
    'NDVI': '006400, FFFF00, FF0000', # Green, Yellow, Red
    'NDMI': '0000FF, FFFF00, FF0000', # Blue, Yellow, Red (Wet to Dry)
    'EVI': '006400, FFFF00, FF0000', # Green, Yellow, Red
    'MSI': 'FF0000, FFFF00, 0000FF', # Red, Yellow, Blue (Stressed to Wet)
    'LAI': 'F0FFF0, 00FF00, 006400', # Honeydew, Green, DarkGreen (Low to High LAI)
    'Biomass': 'F5DEB3, 90EE90, 008000', # Wheat, LightGreen, Green (Low to High Biomass)
    'ET_Proxy': 'ADD8E6, FFFF00, FF4500', # LightBlue, Yellow, OrangeRed (Low to High ET Proxy)
    'Chlorophyll': 'FFFFE0, 90EE90, 006400', # LightYellow, LightGreen, DarkGreen (Low to High Chlorophyll)
    'Chlorophyll_Proxy': 'FFFFE0, 90EE90, 006400' # Same as above
}

INDEX_RANGES = { # Approximate ranges for visualization, adjust as needed
    'NDVI': {'min': 0, 'max': 1},
    'NDMI': {'min': -1, 'max': 1},
    'EVI': {'min': 0, 'max': 1},
    'MSI': {'min': 0, 'max': 3}, # Higher values indicate more moisture stress
    'LAI': {'min': 0, 'max': 8},
    'Biomass': {'min': 0, 'max': 15}, # Units depend on calibration (e.g., t/ha)
    'ET_Proxy': {'min': 0, 'max': 10}, # Arbitrary units based on NDVI proxy
    'Chlorophyll': {'min': 0, 'max': 1}, # MCARI range can vary
    'Chlorophyll_Proxy': {'min': 0, 'max': 1} # NDVI range
}

# --- Get Time Series Data ---
@st.cache_data(show_spinner="در حال محاسبه سری زمانی...", ttl=3600) # Cache for 1 hour
def get_time_series_for_farm(_farm_name, farm_geometry, index_name, start_date, end_date, source):
    """Calculates the time series for a given index and farm."""
    try:
        collection = get_image_collection(farm_geometry.buffer(100), start_date, end_date, source) # Buffer slightly

        if index_name not in INDEX_FUNCTIONS:
            st.error(f"تابع محاسبه برای شاخص '{index_name}' تعریف نشده است.")
            return None

        index_func = INDEX_FUNCTIONS[index_name]

        def calculate_index_stat(image):
            # Calculate the specific index
            img_with_index = index_func(image, source)
            # Select the band corresponding to the index name (handle proxy names)
            index_band_name = index_name
            if index_name == 'ET' and source == 'Sentinel-2': index_band_name = 'ET_Proxy'
            if index_name == 'Chlorophyll' and source == 'Landsat': index_band_name = 'Chlorophyll_Proxy'

            stat = img_with_index.select(index_band_name).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=farm_geometry,
                scale=30, # Adjust scale based on source and desired precision
                maxPixels=1e9
            )
            # Return feature with null geometry, index value, and date
            return ee.Feature(None, {
                'date': image.date().format(DATE_FORMAT),
                index_band_name: stat.get(index_band_name)
            })

        # Filter out images where the calculation might fail (e.g., no valid pixels)
        def map_func(img):
            indexed_img = index_func(img, source)
            index_band_name = index_name
            if index_name == 'ET' and source == 'Sentinel-2': index_band_name = 'ET_Proxy'
            if index_name == 'Chlorophyll' and source == 'Landsat': index_band_name = 'Chlorophyll_Proxy'
            # Check if the band exists before calculating stats
            return indexed_img.set('system:time_start', img.get('system:time_start')) # Keep timestamp

        valid_collection = collection.map(map_func)

        # Calculate stats only if the collection is not empty
        if valid_collection.size().getInfo() == 0:
            # st.warning(f"هیچ تصویر معتبری برای محاسبه سری زمانی {index_name} در بازه زمانی مشخص شده یافت نشد.")
            print(f"Warning: No valid images found for time series {index_name} between {start_date} and {end_date}")
            return pd.DataFrame(columns=['date', index_name]) # Return empty dataframe


        stats = valid_collection.map(calculate_index_stat).filter(ee.Filter.notNull([index_name if not (index_name == 'ET' and source == 'Sentinel-2') and not (index_name == 'Chlorophyll' and source == 'Landsat') else ('ET_Proxy' if index_name == 'ET' else 'Chlorophyll_Proxy')]))

        # Convert to Pandas DataFrame
        data = stats.getInfo()['features']
        dates = [item['properties']['date'] for item in data]
        # Handle potential proxy names when extracting values
        index_band_name_prop = index_name
        if index_name == 'ET' and source == 'Sentinel-2': index_band_name_prop = 'ET_Proxy'
        if index_name == 'Chlorophyll' and source == 'Landsat': index_band_name_prop = 'Chlorophyll_Proxy'

        values = [item['properties'][index_band_name_prop] for item in data]

        df = pd.DataFrame({'date': pd.to_datetime(dates), index_name: values})
        df = df.sort_values(by='date').reset_index(drop=True)
        return df

    except ee.EEException as e:
        st.error(f"خطای GEE در محاسبه سری زمانی برای {index_name}: {e}")
        return None
    except Exception as e:
        st.error(f"خطای پیش‌بینی نشده در محاسبه سری زمانی: {e}")
        return None

# --- Get Map Image ---
@st.cache_data(show_spinner="در حال تولید نقشه...", ttl=3600)
def get_map_image(_farm_name, farm_geometry, index_name, date, source):
    """Generates a GEE Image for the selected index and date."""
    try:
        # Get collection for a small window around the date to increase chances of getting an image
        start_date = (date - datetime.timedelta(days=3)).strftime(DATE_FORMAT)
        end_date = (date + datetime.timedelta(days=1)).strftime(DATE_FORMAT) # Include the selected date
        collection = get_image_collection(farm_geometry.buffer(500), start_date, end_date, source) # Wider buffer for context

        if collection.size().getInfo() == 0:
            # st.warning(f"هیچ تصویری در حدود تاریخ {date.strftime(DATE_FORMAT)} برای {index_name} یافت نشد.")
            print(f"Warning: No image found near {date.strftime(DATE_FORMAT)} for {index_name}")
            return None, None # Return None for image and actual date

        # Use the image closest to the target date
        image = ee.Image(collection.sort('system:time_start', False).first()) # Get latest first within window
        actual_date = ee.Date(image.get('system:time_start')).format(DATE_FORMAT).getInfo()

        if index_name not in INDEX_FUNCTIONS:
            st.error(f"تابع محاسبه برای شاخص '{index_name}' تعریف نشده است.")
            return None, None

        index_func = INDEX_FUNCTIONS[index_name]
        map_image = index_func(image, source)

        # Select the correct band name (handle proxies)
        index_band_name = index_name
        if index_name == 'ET' and source == 'Sentinel-2': index_band_name = 'ET_Proxy'
        if index_name == 'Chlorophyll' and source == 'Landsat': index_band_name = 'Chlorophyll_Proxy'

        return map_image.select(index_band_name), actual_date

    except ee.EEException as e:
        st.error(f"خطای GEE در تولید نقشه برای {index_name}: {e}")
        return None, None
    except Exception as e:
        st.error(f"خطای پیش‌بینی نشده در تولید نقشه: {e}")
        return None, None

# --- Calculate Weekly Average ---
@st.cache_data(show_spinner="در حال محاسبه میانگین هفتگی...", ttl=3600)
def calculate_weekly_average(_farm_name_list, farm_geometries_dict, index_name, end_date_dt, source):
    """Calculates the average index value over the last week for multiple farms."""
    start_date_dt = end_date_dt - datetime.timedelta(days=7)
    start_date = start_date_dt.strftime(DATE_FORMAT)
    end_date = end_date_dt.strftime(DATE_FORMAT)

    farm_results = {}

    # Combine geometries for potentially faster initial filtering (optional)
    # combined_aoi = ee.Geometry.MultiPoint([geom.centroid(maxError=1) for geom in farm_geometries_dict.values()]).bounds()
    # Use a large bounding box instead if MultiPoint is too complex
    all_lons = [geom.centroid(maxError=1).coordinates().get(0).getInfo() for geom in farm_geometries_dict.values()]
    all_lats = [geom.centroid(maxError=1).coordinates().get(1).getInfo() for geom in farm_geometries_dict.values()]
    combined_aoi = ee.Geometry.Rectangle([min(all_lons), min(all_lats), max(all_lons), max(all_lats)])


    try:
        collection = get_image_collection(combined_aoi, start_date, end_date, source)

        if index_name not in INDEX_FUNCTIONS:
            st.error(f"تابع محاسبه برای شاخص '{index_name}' تعریف نشده است.")
            return {}

        index_func = INDEX_FUNCTIONS[index_name]

        # Calculate the index for the entire collection
        def add_index(image):
            return index_func(image, source)
        indexed_collection = collection.map(add_index)

        # Select the correct band name
        index_band_name = index_name
        if index_name == 'ET' and source == 'Sentinel-2': index_band_name = 'ET_Proxy'
        if index_name == 'Chlorophyll' and source == 'Landsat': index_band_name = 'Chlorophyll_Proxy'

        # Calculate the mean over the time period
        mean_image = indexed_collection.select(index_band_name).mean()

        # Calculate mean value for each farm geometry
        for farm_name, geom in farm_geometries_dict.items():
            try:
                stat = mean_image.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geom,
                    scale=30,
                    maxPixels=1e9
                )
                # Use .get() with a default value (e.g., None)
                mean_value = stat.get(index_band_name).getInfo()
                farm_results[farm_name] = mean_value if mean_value is not None else float('nan') # Handle null results
            except ee.EEException as e:
                # Log error for specific farm but continue
                print(f"Error calculating weekly average for {farm_name}: {e}")
                farm_results[farm_name] = float('nan') # Assign NaN on error
            except Exception as e:
                 print(f"Unexpected error calculating weekly average for {farm_name}: {e}")
                 farm_results[farm_name] = float('nan') # Assign NaN on error


        return farm_results

    except ee.EEException as e:
        st.error(f"خطای GEE در محاسبه میانگین هفتگی برای {index_name}: {e}")
        return {name: float('nan') for name in _farm_name_list} # Return NaN for all on major error
    except Exception as e:
        st.error(f"خطای پیش‌بینی نشده در محاسبه میانگین هفتگی: {e}")
        return {name: float('nan') for name in _farm_name_list} # Return NaN for all on major error


# ==============================================================================
# Streamlit UI Layout
# ==============================================================================

st.title("🌾 داشبورد هوشمند مانیتورینگ مزارع نیشکر دهخدا")
st.markdown("مانیتورینگ هفتگی وضعیت مزارع با استفاده از تصاویر ماهواره‌ای و Google Earth Engine")

# --- Sidebar ---
st.sidebar.header("تنظیمات نمایش")

# Data Source Selection
data_source = st.sidebar.radio("منبع داده ماهواره‌ای:", ('Sentinel-2', 'Landsat'), index=0, horizontal=True)

# Farm Selection
available_farms = sorted(farm_data_valid['مزرعه'].unique())
selected_farm_name = st.sidebar.selectbox("انتخاب مزرعه:", available_farms)

# Filter farms based on selected farm name
selected_farm_data = farm_data_valid[farm_data_valid['مزرعه'] == selected_farm_name].iloc[0]
selected_farm_geometry = selected_farm_data['geometry']
selected_farm_coords = (selected_farm_data['عرض جغرافیایی'], selected_farm_data['طول جغرافیایی'])

# Day of the Week Filter (Filters the *list* of farms for comparison/ranking)
available_days = sorted(farm_data_full['روزهای هفته'].unique())
selected_day = st.sidebar.selectbox("فیلتر مزارع بر اساس روز هفته (برای جداول):", ["همه"] + available_days)

# Filter farm_data_valid based on the selected day for ranking/comparison
if selected_day == "همه":
    filtered_farm_data = farm_data_valid.copy()
else:
    filtered_farm_data = farm_data_valid[farm_data_valid['روزهای هفته'] == selected_day].copy()

filtered_farm_names = filtered_farm_data['مزرعه'].tolist()
filtered_farm_geometries = {row['مزرعه']: row['geometry'] for index, row in filtered_farm_data.iterrows()}


# Index Selection
available_indices = list(INDEX_FUNCTIONS.keys())
selected_index = st.sidebar.selectbox("انتخاب شاخص کشاورزی:", available_indices)

# Date Selection (for map display) - Default to today
today = datetime.date.today()
selected_date = st.sidebar.date_input("انتخاب تاریخ برای نقشه:", today)

# Time Series Date Range
st.sidebar.markdown("---")
st.sidebar.markdown("**محدوده زمانی سری زمانی:**")
col1_ts, col2_ts = st.sidebar.columns(2)
default_start_ts = today - relativedelta(years=1) # Default to one year back
ts_start_date = col1_ts.date_input("تاریخ شروع:", default_start_ts)
ts_end_date = col2_ts.date_input("تاریخ پایان:", today) # Default to today

# Validate date range
if ts_start_date > ts_end_date:
    st.sidebar.error("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد.")
    st.stop()


# --- Main Panel ---
col1_map, col2_info = st.columns([3, 1]) # Map takes more space

with col1_map:
    st.subheader(f"نقشه شاخص {selected_index} برای مزرعه {selected_farm_name}")
    st.markdown(f"تاریخ تقریبی تصویر: {selected_date.strftime(DATE_FORMAT)}")

    # Initialize map centered on the selected farm or default coordinates
    map_center = selected_farm_coords if selected_farm_name else (DEFAULT_LATITUDE, DEFAULT_LONGITUDE)
    m = geemap.Map(center=map_center, zoom=INITIAL_ZOOM + 2, add_google_map=False) # Start zoomed closer
    m.add_basemap("HYBRID") # Use Google Satellite Hybrid

    # Add Farm Boundary Layer
    try:
        # Create a buffer around the point geometry to represent the farm area visually
        # Adjust buffer size as needed (e.g., 500 meters)
        farm_boundary_viz = selected_farm_geometry.buffer(500) # 500m buffer
        m.add_ee_layer(farm_boundary_viz, {'color': 'FFFF00', 'fillColor': 'FFFF0050'}, f'مرز مزرعه {selected_farm_name}')
    except Exception as e:
        st.warning(f"خطا در افزودن مرز مزرعه: {e}")


    # Get and Add Index Layer
    map_image, actual_image_date = get_map_image(selected_farm_name, selected_farm_geometry, selected_index, selected_date, data_source)

    if map_image:
        index_vis_params = INDEX_RANGES.get(selected_index, {'min': 0, 'max': 1})
        index_palette = INDEX_PALETTES.get(selected_index, '00FF00') # Default to green if not found
        index_vis_params['palette'] = index_palette.split(', ') # Split palette string into list

        # Determine the correct band name for visualization
        index_band_name_viz = selected_index
        if selected_index == 'ET' and data_source == 'Sentinel-2': index_band_name_viz = 'ET_Proxy'
        if selected_index == 'Chlorophyll' and data_source == 'Landsat': index_band_name_viz = 'Chlorophyll_Proxy'

        try:
            m.add_ee_layer(map_image, index_vis_params, f"{selected_index} ({actual_image_date})")
            m.add_colorbar(index_vis_params, label=selected_index, layer_name=f"{selected_index} ({actual_image_date})")
            st.info(f"نقشه نمایش داده شده مربوط به نزدیک‌ترین تصویر موجود در تاریخ {actual_image_date} است.")
        except ee.EEException as e:
             st.error(f"خطای GEE هنگام افزودن لایه نقشه {selected_index}: {e}")
        except Exception as e:
             st.error(f"خطای نامشخص هنگام افزودن لایه نقشه یا کالربار: {e}")

    else:
        st.warning(f"تصویری برای نمایش شاخص {selected_index} در تاریخ {selected_date.strftime(DATE_FORMAT)} یافت نشد.")

    # Add Layer Control
    m.add_layer_control()

    # Display Map
    m.to_streamlit(height=500)

    # Map Download Button (Placeholder - geemap download needs refinement for server-side)
    # st.download_button(
    #     label="📥 دانلود نقشه (PNG)",
    #     data=m.to_png() if map_image else "", # Needs geemap's download functionality properly implemented
    #     file_name=f"map_{selected_farm_name}_{selected_index}_{selected_date.strftime('%Y%m%d')}.png",
    #     mime="image/png",
    #     disabled=not map_image
    # )
    st.caption("قابلیت دانلود نقشه در حال توسعه است.")


with col2_info:
    st.subheader(f"اطلاعات مزرعه: {selected_farm_name}")
    farm_info = farm_data_full[farm_data_full['مزرعه'] == selected_farm_name].iloc[0]
    # Display farm details - handle potential missing data gracefully
    st.markdown(f"""
    - **کانال:** {farm_info.get('کانال', 'N/A')}
    - **اداره:** {farm_info.get('اداره', 'N/A')}
    - **مساحت داشت:** {farm_info.get('مساحت داشت', 'N/A')} هکتار
    - **واریته:** {farm_info.get('واریته', 'N/A')}
    - **سن:** {farm_info.get('سن', 'N/A')}
    - **مختصات:** ({farm_info.get('عرض جغرافیایی', 'N/A'):.5f}, {farm_info.get('طول جغرافیایی', 'N/A'):.5f})
    - **وضعیت داده مختصات:** {'موجود' if not farm_info.get('coordinates_missing', True) else 'گمشده'}
    - **روز هفته (فیلتر):** {farm_info.get('روزهای هفته', 'N/A')}
    """)
    st.markdown("---")
    st.subheader("راهنمای رنگ نقشه")
    palette_name = INDEX_PALETTES.get(selected_index, '')
    if palette_name:
        colors = palette_name.split(', ')
        if len(colors) == 3: # Assuming Green/Yellow/Red or similar 3-color scheme
             st.markdown(f"""
             - <span style='color:#{colors[2]};'>■</span> : وضعیت نامطلوب / استرس / مقدار پایین
             - <span style='color:#{colors[1]};'>■</span> : وضعیت متوسط
             - <span style='color:#{colors[0]};'>■</span> : وضعیت خوب / سالم / مقدار بالا
             """, unsafe_allow_html=True)
        else: # Generic legend for other palettes
            st.markdown(f"پالت رنگ: {palette_name}")
            st.markdown("مقادیر پایین‌تر به سمت رنگ اول و مقادیر بالاتر به سمت رنگ آخر گرایش دارند.")
    else:
        st.markdown("پالت رنگی برای این شاخص تعریف نشده است.")


st.markdown("---")

# --- Time Series Chart ---
st.subheader(f"نمودار سری زمانی شاخص {selected_index} برای مزرعه {selected_farm_name}")
st.markdown(f"بازه زمانی: {ts_start_date.strftime(DATE_FORMAT)} تا {ts_end_date.strftime(DATE_FORMAT)}")

# Add a placeholder while data is loading
ts_chart_placeholder = st.empty()
ts_chart_placeholder.info("در حال بارگذاری داده‌های سری زمانی...")

ts_df = get_time_series_for_farm(
    selected_farm_name,
    selected_farm_geometry,
    selected_index,
    ts_start_date.strftime(DATE_FORMAT),
    ts_end_date.strftime(DATE_FORMAT),
    data_source
)

if ts_df is not None and not ts_df.empty:
    # Determine the correct column name (handle proxies)
    index_col_name_ts = selected_index
    if selected_index == 'ET' and data_source == 'Sentinel-2': index_col_name_ts = 'ET_Proxy'
    if selected_index == 'Chlorophyll' and data_source == 'Landsat': index_col_name_ts = 'Chlorophyll_Proxy'

    if index_col_name_ts in ts_df.columns:
        fig = px.line(ts_df, x='date', y=index_col_name_ts, title=f'روند زمانی {selected_index}', markers=True)
        fig.update_layout(xaxis_title='تاریخ', yaxis_title=selected_index)
        ts_chart_placeholder.plotly_chart(fig, use_container_width=True)
    else:
         ts_chart_placeholder.warning(f"داده‌ای برای ستون '{index_col_name_ts}' در سری زمانی یافت نشد.")

elif ts_df is not None and ts_df.empty:
    ts_chart_placeholder.warning(f"هیچ داده‌ای برای سری زمانی {selected_index} در بازه زمانی مشخص شده برای مزرعه {selected_farm_name} یافت نشد.")
else:
    ts_chart_placeholder.error("خطا در دریافت داده‌های سری زمانی.")


st.markdown("---")

# --- Farm Ranking and Comparison ---
st.subheader(f"تحلیل و مقایسه مزارع بر اساس شاخص {selected_index}")
st.markdown(f"تاریخ مرجع برای تحلیل هفتگی: {today.strftime(DATE_FORMAT)}")
if selected_day != "همه":
    st.markdown(f"فیلتر شده برای مزارع با روز هفته: **{selected_day}**")


# --- Weekly Ranking Table ---
ranking_col, comparison_col = st.columns(2)

with ranking_col:
    st.markdown(f"**رتبه‌بندی مزارع (میانگین ۷ روز اخیر)**")
    ranking_placeholder = st.empty()
    ranking_placeholder.info(f"در حال محاسبه میانگین هفتگی {selected_index}...")

    # Calculate average for the last 7 days ending today
    weekly_avg_today = calculate_weekly_average(
        filtered_farm_names,
        filtered_farm_geometries,
        selected_index,
        today,
        data_source
    )

    if weekly_avg_today:
        ranking_df = pd.DataFrame(list(weekly_avg_today.items()), columns=['مزرعه', f'میانگین {selected_index}'])
        ranking_df = ranking_df.dropna() # Remove farms where calculation failed
        # Sort descending for beneficial indices (NDVI, EVI, LAI, Biomass, Chlorophyll, ET_Proxy)
        # Sort ascending for stress indices (MSI)
        ascending_sort = selected_index in ['MSI']
        ranking_df = ranking_df.sort_values(by=f'میانگین {selected_index}', ascending=ascending_sort).reset_index(drop=True)
        ranking_df.index += 1 # Start ranking from 1
        ranking_placeholder.dataframe(ranking_df.style.format({f'میانگین {selected_index}': "{:.3f}"}), use_container_width=True)
    else:
        ranking_placeholder.warning("محاسبه میانگین هفتگی با خطا مواجه شد یا داده‌ای یافت نشد.")


# --- Weekly Comparison ---
with comparison_col:
    st.markdown(f"**مقایسه هفتگی (۷ روز اخیر در مقابل ۷ روز قبل)**")
    comparison_placeholder = st.empty()
    comparison_placeholder.info(f"در حال محاسبه مقایسه هفتگی {selected_index}...")

    # Calculate average for the 7 days before the last 7 days
    previous_week_end_date = today - datetime.timedelta(days=7)
    weekly_avg_previous = calculate_weekly_average(
        filtered_farm_names,
        filtered_farm_geometries,
        selected_index,
        previous_week_end_date,
        data_source
    )

    if weekly_avg_today and weekly_avg_previous:
        compare_data = []
        report_lines = [f"**گزارش تحلیلی مقایسه هفتگی برای شاخص {selected_index}:**",
                        f"(مقایسه میانگین {today - datetime.timedelta(days=6)} تا {today} با {previous_week_end_date - datetime.timedelta(days=6)} تا {previous_week_end_date})",
                        ""] # Add empty line

        increased_farms = []
        decreased_farms = []
        no_change_farms = []

        for farm_name in filtered_farm_names:
            current_avg = weekly_avg_today.get(farm_name)
            previous_avg = weekly_avg_previous.get(farm_name)

            if current_avg is not None and previous_avg is not None and not pd.isna(current_avg) and not pd.isna(previous_avg):
                change = current_avg - previous_avg
                change_pct = (change / previous_avg) * 100 if previous_avg != 0 else 0
                compare_data.append({
                    'مزرعه': farm_name,
                    'میانگین هفته اخیر': current_avg,
                    'میانگین هفته قبل': previous_avg,
                    'تغییر': change,
                    'درصد تغییر': change_pct
                })
                # Add to report lists
                if abs(change_pct) < 1: # Threshold for significant change (e.g., 1%)
                     no_change_farms.append(farm_name)
                elif change > 0:
                    increased_farms.append(f"{farm_name} ({change_pct:+.1f}%)")
                else:
                    decreased_farms.append(f"{farm_name} ({change_pct:+.1f}%)")

            else:
                 # Add row with N/A if data is missing for comparison
                 compare_data.append({
                    'مزرعه': farm_name,
                    'میانگین هفته اخیر': current_avg if current_avg is not None else 'N/A',
                    'میانگین هفته قبل': previous_avg if previous_avg is not None else 'N/A',
                    'تغییر': 'N/A',
                    'درصد تغییر': 'N/A'
                })


        compare_df = pd.DataFrame(compare_data)
        comparison_placeholder.dataframe(compare_df.style.format({
            'میانگین هفته اخیر': "{:.3f}",
            'میانگین هفته قبل': "{:.3f}",
            'تغییر': "{:+.3f}",
            'درصد تغییر': "{:+.1f}%"
        }), use_container_width=True)

        # --- Generate Text Report ---
        st.markdown("---")
        st.subheader("گزارش تحلیلی هفتگی")
        report_placeholder = st.empty()
        report_placeholder.info("در حال تولید گزارش...")

        # Interpretation based on index type
        positive_change_is_good = selected_index not in ['MSI'] # Higher MSI is generally worse (more stress)

        if positive_change_is_good:
            if increased_farms:
                report_lines.append(f"📈 **بهبود وضعیت ({selected_index}):** مزارع {', '.join(increased_farms)} در هفته اخیر نسبت به هفته قبل بهبود نشان داده‌اند.")
            if decreased_farms:
                report_lines.append(f"📉 **کاهش وضعیت ({selected_index}):** مزارع {', '.join(decreased_farms)} در هفته اخیر نسبت به هفته قبل کاهش نشان داده‌اند و نیاز به بررسی بیشتر دارند.")
        else: # For stress indices like MSI
             if increased_farms: # Increase in MSI is bad
                report_lines.append(f"📈 **افزایش استرس ({selected_index}):** مزارع {', '.join(increased_farms)} در هفته اخیر نسبت به هفته قبل افزایش استرس (یا کاهش رطوبت برای NDMI) نشان داده‌اند و نیاز به بررسی فوری دارند.")
             if decreased_farms: # Decrease in MSI is good
                report_lines.append(f"📉 **کاهش استرس ({selected_index}):** مزارع {', '.join(decreased_farms)} در هفته اخیر نسبت به هفته قبل کاهش استرس (یا افزایش رطوبت برای NDMI) نشان داده‌اند.")

        if no_change_farms:
             report_lines.append(f"📊 **وضعیت پایدار ({selected_index}):** مزارع {', '.join(no_change_farms)} تغییر قابل توجهی نسبت به هفته قبل نداشته‌اند.")

        if not increased_farms and not decreased_farms and not no_change_farms:
             report_lines.append("داده کافی برای مقایسه هفتگی مزارع فیلتر شده وجود ندارد.")

        report_placeholder.markdown("\n".join(report_lines))


    else:
        comparison_placeholder.warning("محاسبه مقایسه هفتگی با خطا مواجه شد یا داده‌ای برای هر دو دوره یافت نشد.")
        st.markdown("---")
        st.subheader("گزارش تحلیلی هفتگی")
        st.warning("امکان تولید گزارش تحلیلی به دلیل عدم وجود داده‌های مقایسه‌ای وجود ندارد.")


# --- Footer ---
st.markdown("---")
st.caption("طراحی و توسعه توسط هوش مصنوعی | داده‌های ماهواره‌ای: Sentinel-2 (ESA), Landsat 8/9 (NASA/USGS) | پردازش: Google Earth Engine")

