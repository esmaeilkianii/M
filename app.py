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
import math # Import math for isnan check

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
def authenticate_gee(_service_account_file):
    """Authenticates to Google Earth Engine using a service account."""
    try:
        # Check if the service account file exists
        if not os.path.exists(_service_account_file):
            st.error(f"فایل Service Account در مسیر '{_service_account_file}' یافت نشد.")
            st.stop()

        # Load credentials from the file
        with open(_service_account_file) as f:
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
        st.error(f"فایل Service Account در مسیر '{_service_account_file}' یافت نشد.")
        return False
    except json.JSONDecodeError:
        st.error(f"فایل Service Account ('{_service_account_file}') معتبر نیست یا فرمت JSON صحیحی ندارد.")
        return False
    except Exception as e:
        st.error(f"خطای پیش‌بینی نشده در اتصال به GEE: {e}")
        return False

# Perform authentication
if not authenticate_gee(SERVICE_ACCOUNT_FILE):
    st.stop() # Stop execution if authentication fails

# --- Load Data ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data(_csv_path):
    """Loads farm data from the CSV file."""
    try:
        df = pd.read_csv(_csv_path)
        # Basic validation
        required_columns = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته', 'coordinates_missing']
        if not all(col in df.columns for col in required_columns):
            st.error(f"فایل CSV باید شامل ستون‌های {required_columns} باشد.")
            st.stop()
        # Convert coordinate columns to numeric, coercing errors
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        # Handle missing coordinates flag more robustly
        # Treat blank strings in 'coordinates_missing' as False before converting to bool
        df['coordinates_missing'] = df['coordinates_missing'].replace('', False).fillna(False).astype(bool) | df['طول جغرافیایی'].isna() | df['عرض جغرافیایی'].isna()


        # Filter out farms with missing coordinates for mapping/GEE analysis
        df_valid_coords = df[~df['coordinates_missing']].copy()

        # --- Create GEE Geometry Objects ---
        # This part should NOT be cached directly with the dataframe if geometries cause issues.
        # We create geometries AFTER loading/caching the raw data.
        geometries = {}
        for index, row in df_valid_coords.iterrows():
             # Ensure coordinates are valid numbers before creating geometry
             lon = row['طول جغرافیایی']
             lat = row['عرض جغرافیایی']
             if lon is not None and lat is not None and not (math.isnan(lon) or math.isnan(lat)):
                 geometries[row['مزرعه']] = ee.Geometry.Point([lon, lat])
             else:
                 print(f"Skipping geometry creation for farm {row['مزرعه']} due to invalid coordinates.")


        return df, df_valid_coords, geometries

    except FileNotFoundError:
        st.error(f"فایل CSV در مسیر '{_csv_path}' یافت نشد.")
        st.stop()
    except Exception as e:
        st.error(f"خطا در بارگذاری یا پردازش فایل CSV: {e}")
        st.stop()

# Load data and create geometries separately
farm_data_full, farm_data_valid, farm_geometries = load_farm_data(CSV_FILE_PATH)

# ==============================================================================
# GEE Functions
# ==============================================================================

# --- Cloud Masking ---
# (No changes needed in cloud masking functions)
def mask_s2_clouds(image):
    """Masks clouds in Sentinel-2 images."""
    qa = image.select('QA60')
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0) \
             .And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    # Ensure division happens only if image is not empty
    return image.updateMask(mask).divide(10000).copyProperties(image, ['system:time_start'])

def mask_landsat_clouds(image):
    """Masks clouds in Landsat 8/9 images using the QA_PIXEL band."""
    qa_pixel = image.select('QA_PIXEL')
    # Bits 3 (Cloud Shadow) and 5 (Cloud) are relevant for SR. Previous used bit 4 (Cirrus for T1_L1)
    # Let's stick to Cloud Shadow (bit 3) and Cloud (bit 5) based on Collection 2 specs
    cloud_shadow_bit = 1 << 3
    cloud_bit = 1 << 5 # Bit 5 is Dilated Cloud in C2 L2SP QA_PIXEL, let's use Cloud (Bit 3)
    # Let's re-evaluate based on documentation: Bits 1 (Dilated Cloud), 3 (Cloud), 4 (Cloud Shadow)
    # Masking out pixels where any of these are set.
    dilated_cloud_bit = 1 << 1
    cloud_bit = 1 << 3 # Cloud bit
    cloud_shadow_bit = 1 << 4 # Cloud shadow bit

    # Mask is clear if all relevant bits are 0.
    mask = qa_pixel.bitwiseAnd(dilated_cloud_bit).eq(0) \
                   .And(qa_pixel.bitwiseAnd(cloud_bit).eq(0)) \
                   .And(qa_pixel.bitwiseAnd(cloud_shadow_bit).eq(0))

    # Apply scale factors for Landsat Collection 2 SR bands
    optical_bands = image.select('SR_B.').multiply(0.0000275).add(-0.2)
    thermal_bands = image.select('ST_B.*').multiply(0.00341802).add(149.0) # Scale factors for ST bands if needed

    return image.addBands(optical_bands, None, True)\
                .addBands(thermal_bands, None, True)\
                .updateMask(mask)\
                .copyProperties(image, ['system:time_start'])


# --- Image Collection Retrieval ---
def get_image_collection(_aoi, start_date, end_date, source='Sentinel-2'):
    """Gets a cloud-masked image collection for a given AOI and date range.
       _aoi is prefixed with underscore to avoid hashing issues if it's a complex ee object.
    """
    collection = None # Initialize collection
    if source == 'Sentinel-2':
        try:
            collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                           .filterBounds(_aoi) \
                           .filterDate(start_date, end_date) \
                           .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)) \
                           .map(lambda img: ee.Algorithms.If(img.bandNames().contains('QA60'), mask_s2_clouds(img), img)) # Corrected Indentation

        except ee.EEException as e:
            st.warning(f"Could not retrieve Sentinel-2 collection: {e}")
            collection = ee.ImageCollection([]) # Return empty collection on error

    elif source == 'Landsat': # Combine Landsat 8 and 9
        try:
            collection_l9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2') \
                .filterBounds(_aoi) \
                .filterDate(start_date, end_date) \
                .map(lambda img: ee.Algorithms.If(img.bandNames().contains('QA_PIXEL'), mask_landsat_clouds(img), img)) # Corrected Indentation

            collection_l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
                .filterBounds(_aoi) \
                .filterDate(start_date, end_date) \
                .map(lambda img: ee.Algorithms.If(img.bandNames().contains('QA_PIXEL'), mask_landsat_clouds(img), img)) # Corrected Indentation

            collection = collection_l8.merge(collection_l9).sort('system:time_start')
        except ee.EEException as e:
            st.warning(f"Could not retrieve Landsat collection: {e}")
            collection = ee.ImageCollection([]) # Return empty collection on error
    else:
        st.error("منبع تصویر نامعتبر است. 'Sentinel-2' یا 'Landsat' را انتخاب کنید.")
        collection = ee.ImageCollection([]) # Return empty collection

    # Ensure collection is an ImageCollection even if errors occurred
    return collection if collection is not None else ee.ImageCollection([])


# --- Index Calculation Functions ---
# (No changes needed in index calculation logic itself)
def calculate_ndvi(image, source='Sentinel-2'):
    nir, red = None, None
    if source == 'Sentinel-2':
        nir = image.select('B8', None) # Use default value None if band missing
        red = image.select('B4', None)
    elif source == 'Landsat':
        nir = image.select('SR_B5', None)
        red = image.select('SR_B4', None)

    if nir and red: # Proceed only if bands exist
        # Add a small epsilon to denominator to avoid division by zero
        return image.addBands(nir.subtract(red).divide(nir.add(red).max(1e-9)).rename('NDVI'))
    else:
        return image # Return original image if bands are missing

def calculate_ndmi(image, source='Sentinel-2'):
    nir, swir1 = None, None
    if source == 'Sentinel-2':
        nir = image.select('B8', None)
        swir1 = image.select('B11', None)
    elif source == 'Landsat':
        nir = image.select('SR_B5', None)
        swir1 = image.select('SR_B6', None)

    if nir and swir1:
        return image.addBands(nir.subtract(swir1).divide(nir.add(swir1).max(1e-9)).rename('NDMI'))
    else:
        return image

def calculate_evi(image, source='Sentinel-2'):
    nir, red, blue = None, None, None
    if source == 'Sentinel-2':
        nir = image.select('B8', None)
        red = image.select('B4', None)
        blue = image.select('B2', None)
    elif source == 'Landsat':
        nir = image.select('SR_B5', None)
        red = image.select('SR_B4', None)
        blue = image.select('SR_B2', None)

    if nir and red and blue:
        evi = image.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                'NIR': nir, 'RED': red, 'BLUE': blue
            }).rename('EVI')
        return image.addBands(evi)
    else:
        return image

def calculate_msi(image, source='Sentinel-2'):
    swir1, nir = None, None
    if source == 'Sentinel-2':
        swir1 = image.select('B11', None)
        nir = image.select('B8', None)
    elif source == 'Landsat':
        swir1 = image.select('SR_B6', None)
        nir = image.select('SR_B5', None)

    if swir1 and nir:
         # Add a small epsilon to denominator to avoid division by zero
        return image.addBands(swir1.divide(nir.max(1e-9)).rename('MSI'))
    else:
        return image

def calculate_lai(image, source='Sentinel-2'):
    img_with_ndvi = calculate_ndvi(image, source)
    ndvi = img_with_ndvi.select('NDVI', None)
    if ndvi:
        # Using a generic formula for demonstration - replace with a calibrated one
        lai = ndvi.multiply(5.0).exp().multiply(0.1).rename('LAI') # Example: 0.1 * exp(5.0 * NDVI)
        return image.addBands(lai)
    else:
        return image

def calculate_biomass(image, source='Sentinel-2'):
    img_with_lai = calculate_lai(image, source) # LAI calculation includes NDVI check
    lai = img_with_lai.select('LAI', None)
    if lai:
        # Using generic coefficients for demonstration
        a = 1.5 # Example coefficient
        b = 0.5 # Example coefficient
        biomass = lai.multiply(a).add(b).rename('Biomass')
        return image.addBands(biomass)
    else:
        return image

def calculate_et(image, source='Sentinel-2'):
    img_with_ndvi = calculate_ndvi(image, source)
    ndvi = img_with_ndvi.select('NDVI', None)
    if ndvi:
        # Simple proxy: Higher NDVI often correlates with higher ET in vegetated areas
        et_proxy = ndvi.multiply(10).rename('ET_Proxy') # Scale NDVI to an arbitrary ET range
        return image.addBands(et_proxy)
    else:
        return image

def calculate_chlorophyll(image, source='Sentinel-2'):
    if source == 'Sentinel-2':
        red = image.select('B4', None)
        green = image.select('B3', None)
        red_edge = image.select('B5', None) # Using B5 as a representative Red Edge band
        if red and green and red_edge:
             # Add small epsilon to denominator
            mcari = ((red_edge.subtract(red)).subtract(red_edge.subtract(green).multiply(0.2))).multiply(red_edge.divide(red.max(1e-9)))
            return image.addBands(mcari.rename('Chlorophyll'))
        else:
            return image # Return original if bands missing
    elif source == 'Landsat':
        img_with_ndvi = calculate_ndvi(image, source)
        ndvi = img_with_ndvi.select('NDVI', None)
        if ndvi:
            return image.addBands(ndvi.rename('Chlorophyll_Proxy'))
        else:
            return image # Return original if NDVI failed
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
    'Chlorophyll': {'min': -0.5, 'max': 1}, # MCARI range can be negative, adjust based on typical values
    'Chlorophyll_Proxy': {'min': 0, 'max': 1} # NDVI range
}

# --- Get Time Series Data ---
@st.cache_data(show_spinner="در حال محاسبه سری زمانی...", ttl=3600) # Cache for 1 hour
def get_time_series_for_farm(farm_name, _farm_geometry, index_name, start_date, end_date, source):
    """
    Calculates the time series for a given index and farm.
    _farm_geometry is ignored by Streamlit cache. farm_name, index_name, dates, source are used as cache keys.
    """
    # Validate geometry before proceeding
    if not isinstance(_farm_geometry, ee.Geometry):
         st.error(f"Invalid geometry provided for farm {farm_name}.")
         return pd.DataFrame(columns=['date', index_name]) # Return empty DataFrame

    try:
        # Buffer the geometry slightly for robustness in reduceRegion
        buffered_geometry = _farm_geometry.buffer(10)
        collection = get_image_collection(buffered_geometry, start_date, end_date, source)

        if index_name not in INDEX_FUNCTIONS:
            st.error(f"تابع محاسبه برای شاخص '{index_name}' تعریف نشده است.")
            return pd.DataFrame(columns=['date', index_name])

        index_func = INDEX_FUNCTIONS[index_name]

        # Determine the expected band name after calculation
        index_band_name = index_name
        if index_name == 'ET' and source == 'Sentinel-2': index_band_name = 'ET_Proxy'
        if index_name == 'Chlorophyll' and source == 'Landsat': index_band_name = 'Chlorophyll_Proxy'

        def calculate_index_stat(image):
            # Calculate the specific index; function now returns image even if bands missing
            img_with_index = index_func(image, source)

            # Check if the expected index band was actually added
            if not img_with_index.bandNames().contains(index_band_name):
                return ee.Feature(None, {'date': image.date().format(DATE_FORMAT), index_band_name: None})

            # Proceed with reduceRegion if band exists
            stat = img_with_index.select(index_band_name).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffered_geometry, # Use buffered geometry
                scale=30, # Adjust scale based on source and desired precision
                maxPixels=1e9,
                bestEffort=True, # Use bestEffort to avoid computation timeouts on complex geometries
                tileScale=4 # Increase tileScale to potentially manage memory
            )
            # Get the value, default to None if calculation fails or returns no result
            value = stat.get(index_band_name)
            return ee.Feature(None, {'date': image.date().format(DATE_FORMAT), index_band_name: value})


        # Calculate stats safely, handling potential errors in mapping
        stats = collection.map(calculate_index_stat)

        # Filter out null results AFTER mapping
        filtered_stats = stats.filter(ee.Filter.notNull([index_band_name]))

        # Fetch data from GEE server
        try:
            data = filtered_stats.getInfo()['features']
        except ee.EEException as e:
            st.error(f"خطای GEE هنگام دریافت نتایج سری زمانی برای {farm_name} ({index_name}): {e}")
            return pd.DataFrame(columns=['date', index_name]) # Return empty dataframe on fetch error

        # Process results into DataFrame
        dates = [item['properties']['date'] for item in data if item.get('properties')]
        values = [item['properties'][index_band_name] for item in data if item.get('properties')]

        # Create DataFrame, converting dates and handling potential None values in 'values'
        df = pd.DataFrame({'date': pd.to_datetime(dates), index_name: values})
        df = df.dropna(subset=[index_name]) # Drop rows where index calculation resulted in None
        df = df.sort_values(by='date').reset_index(drop=True)

        if df.empty:
             print(f"Warning: No valid data points found for time series {farm_name} ({index_name}) between {start_date} and {end_date}")

        return df

    except ee.EEException as e:
        st.error(f"خطای GEE در محاسبه سری زمانی برای {farm_name} ({index_name}): {e}")
        return pd.DataFrame(columns=['date', index_name]) # Return empty dataframe
    except Exception as e:
        st.error(f"خطای پیش‌بینی نشده در محاسبه سری زمانی برای {farm_name} ({index_name}): {e}")
        return pd.DataFrame(columns=['date', index_name]) # Return empty dataframe


# --- Get Map Image ---
@st.cache_data(show_spinner="در حال تولید نقشه...", ttl=3600)
def get_map_image(farm_name, _farm_geometry, index_name, date, source):
    """
    Generates a GEE Image for the selected index and date.
    _farm_geometry is ignored by Streamlit cache. farm_name, index_name, date, source are used as cache keys.
    """
     # Validate geometry before proceeding
    if not isinstance(_farm_geometry, ee.Geometry):
         st.error(f"Invalid geometry provided for farm {farm_name}.")
         return None, None # Return Nones

    try:
        # Get collection for a small window around the date
        start_date = (date - datetime.timedelta(days=3)).strftime(DATE_FORMAT)
        end_date = (date + datetime.timedelta(days=1)).strftime(DATE_FORMAT) # Include the selected date
        # Use a slightly larger buffer for context, but use original geometry for calculation if needed later
        aoi_for_collection = _farm_geometry.buffer(500)
        collection = get_image_collection(aoi_for_collection, start_date, end_date, source)

        # Check if the collection is empty right after retrieval
        collection_size = collection.size().getInfo()
        if collection_size == 0:
            print(f"Warning: No images found near {date.strftime(DATE_FORMAT)} for {farm_name} ({index_name})")
            return None, None # Return None for image and actual date

        # Create a mosaic of the best available pixels (e.g., median) within the window
        # This is often more robust than taking the 'first' image which might have partial cloud cover missed by filter
        # mosaic = collection.median() # Or .qualityMosaic('NDVI') if NDVI is relevant

        # Alternative: Sort by cloud cover (if available and reliable) and take the best one
        # Or stick to simplest: latest image in the window
        image = ee.Image(collection.sort('system:time_start', False).first()) # Get latest first within window

        # Ensure the selected image is valid
        if not image.bandNames().size().getInfo() > 0:
             print(f"Warning: Selected image for {farm_name} ({index_name}) near {date.strftime(DATE_FORMAT)} has no bands.")
             return None, None


        actual_date = ee.Date(image.get('system:time_start')).format(DATE_FORMAT).getInfo()

        if index_name not in INDEX_FUNCTIONS:
            st.error(f"تابع محاسبه برای شاخص '{index_name}' تعریف نشده است.")
            return None, None

        index_func = INDEX_FUNCTIONS[index_name]
        map_image_with_all_bands = index_func(image, source) # Calculate the index

        # Determine the correct band name (handle proxies)
        index_band_name = index_name
        if index_name == 'ET' and source == 'Sentinel-2': index_band_name = 'ET_Proxy'
        if index_name == 'Chlorophyll' and source == 'Landsat': index_band_name = 'Chlorophyll_Proxy'

        # Select only the calculated index band for visualization
        final_map_image = map_image_with_all_bands.select(index_band_name, None) # Use default value None

        # Check if the band exists in the final image
        if final_map_image is None or not final_map_image.bandNames().contains(index_band_name).getInfo():
             print(f"Warning: Index band '{index_band_name}' could not be calculated or selected for {farm_name} near {actual_date}.")
             return None, actual_date # Return None image, but maybe date is known

        return final_map_image, actual_date

    except ee.EEException as e:
        st.error(f"خطای GEE در تولید نقشه برای {farm_name} ({index_name}): {e}")
        return None, None
    except Exception as e:
        st.error(f"خطای پیش‌بینی نشده در تولید نقشه برای {farm_name} ({index_name}): {e}")
        return None, None

# --- Calculate Weekly Average ---
@st.cache_data(show_spinner="در حال محاسبه میانگین هفتگی...", ttl=3600)
def calculate_weekly_average(farm_name_list, _farm_geometries_dict, index_name, end_date_dt, source):
    """
    Calculates the average index value over the last week for multiple farms.
    _farm_geometries_dict is ignored by Streamlit cache. farm_name_list, index_name, end_date, source are used as cache keys.
    """
    start_date_dt = end_date_dt - datetime.timedelta(days=7)
    start_date = start_date_dt.strftime(DATE_FORMAT)
    end_date = end_date_dt.strftime(DATE_FORMAT)

    farm_results = {}
    valid_geometries = {name: geom for name, geom in _farm_geometries_dict.items() if isinstance(geom, ee.Geometry)}

    if not valid_geometries:
        st.warning("هیچ هندسه معتبری برای محاسبه میانگین هفتگی یافت نشد.")
        return {name: float('nan') for name in farm_name_list}

    # Create a combined geometry for initial filtering (more efficient)
    # Use FeatureCollection for robustness with many points
    features = [ee.Feature(geom, {'name': name}) for name, geom in valid_geometries.items()]
    fc = ee.FeatureCollection(features)
    combined_aoi = fc.geometry().bounds() # Get the bounding box of all valid geometries


    try:
        collection = get_image_collection(combined_aoi, start_date, end_date, source)

        if index_name not in INDEX_FUNCTIONS:
            st.error(f"تابع محاسبه برای شاخص '{index_name}' تعریف نشده است.")
            return {name: float('nan') for name in farm_name_list}

        index_func = INDEX_FUNCTIONS[index_name]

        # Determine the expected band name
        index_band_name = index_name
        if index_name == 'ET' and source == 'Sentinel-2': index_band_name = 'ET_Proxy'
        if index_name == 'Chlorophyll' and source == 'Landsat': index_band_name = 'Chlorophyll_Proxy'

        # Calculate the index for the entire collection safely
        def add_index(image):
            img_with_index = index_func(image, source)
            # Return only if the specific index band was created
            return ee.Algorithms.If(
                img_with_index.bandNames().contains(index_band_name),
                img_with_index.select(index_band_name), # Select only the needed band
                None # Return None if index calculation failed for this image
            )
        # Use ee.ImageCollection.fromImages to handle potential nulls from map
        indexed_collection = ee.ImageCollection.fromImages(collection.map(add_index, opt_dropNulls=True))


        # Calculate the mean over the time period, only if collection is not empty
        if indexed_collection.size().getInfo() > 0:
            mean_image = indexed_collection.mean() # Calculate mean of the single band

            # Calculate mean value for each farm geometry using reduceRegions
            # This is generally more efficient than mapping reduceRegion individually
            reduced_stats = mean_image.reduceRegions(
                collection=fc, # Use the feature collection of valid farms
                reducer=ee.Reducer.mean(),
                scale=30,
                tileScale=4
            )

            # Extract results from the FeatureCollection
            try:
                results_list = reduced_stats.getInfo()['features']
                for feature in results_list:
                    farm_name = feature['properties']['name']
                    # The reducer output band name is typically 'mean'
                    mean_value = feature['properties'].get('mean')
                    farm_results[farm_name] = mean_value if mean_value is not None else float('nan')

                # Fill missing farms (those filtered out or failed reduction) with NaN
                for name in farm_name_list:
                    if name not in farm_results:
                        farm_results[name] = float('nan')

            except ee.EEException as e:
                 st.error(f"خطای GEE هنگام دریافت نتایج میانگین هفتگی ({index_name}): {e}")
                 # Assign NaN to all farms in case of major fetch error
                 farm_results = {name: float('nan') for name in farm_name_list}

        else:
            print(f"Warning: No valid images found for weekly average calculation ({index_name}) between {start_date} and {end_date}")
            farm_results = {name: float('nan') for name in farm_name_list}


        return farm_results

    except ee.EEException as e:
        st.error(f"خطای GEE در محاسبه میانگین هفتگی برای {index_name}: {e}")
        return {name: float('nan') for name in farm_name_list} # Return NaN for all on major error
    except Exception as e:
        st.error(f"خطای پیش‌بینی نشده در محاسبه میانگین هفتگی ({index_name}): {e}")
        return {name: float('nan') for name in farm_name_list} # Return NaN for all on major error


# ==============================================================================
# Streamlit UI Layout
# ==============================================================================

st.title("🌾 داشبورد هوشمند مانیتورینگ مزارع نیشکر دهخدا")
st.markdown("مانیتورینگ هفتگی وضعیت مزارع با استفاده از تصاویر ماهواره‌ای و Google Earth Engine")

# --- Sidebar ---
st.sidebar.header("تنظیمات نمایش")

# Data Source Selection
data_source = st.sidebar.radio("منبع داده ماهواره‌ای:", ('Sentinel-2', 'Landsat'), index=0, horizontal=True, key='data_source_radio')

# Farm Selection
available_farms = sorted([name for name in farm_geometries.keys()]) # Use names from geometries dict
if not available_farms:
    st.error("هیچ مزرعه‌ای با مختصات معتبر برای نمایش یافت نشد. لطفاً فایل CSV را بررسی کنید.")
    st.stop()

selected_farm_name = st.sidebar.selectbox("انتخاب مزرعه:", available_farms, key='farm_select')

# Get selected farm's geometry and data
selected_farm_geometry = farm_geometries.get(selected_farm_name)
selected_farm_data = farm_data_valid[farm_data_valid['مزرعه'] == selected_farm_name].iloc[0]
selected_farm_coords = (selected_farm_data['عرض جغرافیایی'], selected_farm_data['طول جغرافیایی'])


# Day of the Week Filter (Filters the *list* of farms for comparison/ranking)
# Ensure 'روزهای هفته' exists and handle potential NaN values before getting unique days
if 'روزهای هفته' in farm_data_full.columns:
    available_days = sorted(farm_data_full['روزهای هفته'].dropna().unique())
else:
    available_days = []
    st.sidebar.warning("ستون 'روزهای هفته' در فایل CSV یافت نشد. فیلتر روز غیرفعال است.")

# Add "همه" option only if there are available days
day_options = ["همه"] + available_days if available_days else ["همه"]
selected_day = st.sidebar.selectbox(
    "فیلتر مزارع بر اساس روز هفته (برای جداول):",
    day_options,
    key='day_select',
    disabled=not available_days # Disable if column missing
    )

# Filter farm_data_valid based on the selected day for ranking/comparison
if selected_day == "همه" or not available_days:
    # Include only farms that have valid geometries
    filtered_farm_names = available_farms
else:
    # Filter names based on the day AND ensure they have valid geometry
    filtered_farm_names = sorted([
        name for name in available_farms
        if farm_data_full[farm_data_full['مزرعه'] == name].iloc[0]['روزهای هفته'] == selected_day
    ])

# Create the geometries dictionary only for the filtered farms
filtered_farm_geometries = {name: farm_geometries[name] for name in filtered_farm_names if name in farm_geometries}


# Index Selection
available_indices = list(INDEX_FUNCTIONS.keys())
selected_index = st.sidebar.selectbox("انتخاب شاخص کشاورزی:", available_indices, key='index_select')

# Date Selection (for map display) - Default to today
today = datetime.date.today()
selected_date = st.sidebar.date_input("انتخاب تاریخ برای نقشه:", today, key='map_date_select')

# Time Series Date Range
st.sidebar.markdown("---")
st.sidebar.markdown("**محدوده زمانی سری زمانی:**")
col1_ts, col2_ts = st.sidebar.columns(2)
default_start_ts = today - relativedelta(years=1) # Default to one year back
ts_start_date = col1_ts.date_input("تاریخ شروع:", default_start_ts, key='ts_start')
ts_end_date = col2_ts.date_input("تاریخ پایان:", today, key='ts_end') # Default to today

# Validate date range
if ts_start_date > ts_end_date:
    st.sidebar.error("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد.")
    st.stop()


# --- Main Panel ---
col1_map, col2_info = st.columns([3, 1]) # Map takes more space

with col1_map:
    st.subheader(f"نقشه شاخص {selected_index} برای مزرعه {selected_farm_name}")
    st.markdown(f"تاریخ درخواستی: {selected_date.strftime(DATE_FORMAT)}")

    # Initialize map centered on the selected farm or default coordinates
    map_center = selected_farm_coords if selected_farm_name and not (math.isnan(selected_farm_coords[0]) or math.isnan(selected_farm_coords[1])) else (DEFAULT_LATITUDE, DEFAULT_LONGITUDE)
    m = geemap.Map(center=map_center, zoom=INITIAL_ZOOM + 2, add_google_map=False) # Start zoomed closer
    m.add_basemap("HYBRID") # Use Google Satellite Hybrid

    # Add Farm Boundary Layer (only if geometry is valid)
    if selected_farm_geometry and isinstance(selected_farm_geometry, ee.Geometry):
        try:
            # Create a buffer around the point geometry to represent the farm area visually
            farm_boundary_viz = selected_farm_geometry.buffer(500) # 500m buffer
            m.add_ee_layer(farm_boundary_viz, {'color': 'FFFF00', 'fillColor': 'FFFF0050'}, f'مرز مزرعه {selected_farm_name}')
            # Center map on the selected farm
            m.centerObject(selected_farm_geometry, INITIAL_ZOOM + 3)
        except Exception as e:
            st.warning(f"خطا در افزودن مرز مزرعه {selected_farm_name}: {e}")
    else:
         st.warning(f"مختصات معتبری برای نمایش مرز مزرعه {selected_farm_name} وجود ندارد.")


    # Get and Add Index Layer
    map_image, actual_image_date = get_map_image(selected_farm_name, selected_farm_geometry, selected_index, selected_date, data_source)

    if map_image and actual_image_date:
        # Ensure vis_params are correctly fetched
        index_vis_params = INDEX_RANGES.get(selected_index, {'min': 0, 'max': 1}).copy() # Copy to avoid modifying original dict
        index_palette = INDEX_PALETTES.get(selected_index, '00FF00') # Default to green if not found
        index_vis_params['palette'] = index_palette.split(', ') # Split palette string into list

        # Determine the correct band name for visualization (redundant check, but safe)
        index_band_name_viz = selected_index
        if selected_index == 'ET' and data_source == 'Sentinel-2': index_band_name_viz = 'ET_Proxy'
        if selected_index == 'Chlorophyll' and data_source == 'Landsat': index_band_name_viz = 'Chlorophyll_Proxy'

        try:
            # Clip the image to the farm boundary for focused visualization
            clipped_image = map_image.clip(selected_farm_geometry.buffer(500)) # Clip to buffered area

            m.add_ee_layer(clipped_image, index_vis_params, f"{selected_index} ({actual_image_date})")
            # Add color bar only if visualization parameters are valid
            if 'palette' in index_vis_params and 'min' in index_vis_params and 'max' in index_vis_params:
                 m.add_colorbar(index_vis_params, label=f"{selected_index} ({actual_image_date})", layer_name=f"{selected_index} ({actual_image_date})")
            else:
                 st.warning(f"پارامترهای نمایش (min, max, palette) برای {selected_index} کامل نیستند. Colorbar اضافه نشد.")

            st.info(f"نقشه نمایش داده شده مربوط به نزدیک‌ترین تصویر موجود در تاریخ {actual_image_date} است.")
        except ee.EEException as e:
             st.error(f"خطای GEE هنگام افزودن لایه نقشه {selected_index}: {e}")
        except Exception as e:
             st.error(f"خطای نامشخص هنگام افزودن لایه نقشه یا کالربار: {e}")

    elif actual_image_date:
         st.warning(f"تصویر معتبری برای تاریخ {actual_image_date} یافت شد، اما محاسبه شاخص {selected_index} ناموفق بود.")
    else:
        st.warning(f"تصویری برای نمایش شاخص {selected_index} در حدود تاریخ {selected_date.strftime(DATE_FORMAT)} یافت نشد.")

    # Add Layer Control
    m.add_layer_control()

    # Display Map
    try:
        m.to_streamlit(height=500)
    except Exception as e:
        st.error(f"خطا در نمایش نقشه: {e}")


    # Map Download Button (Placeholder - geemap download needs refinement for server-side)
    st.caption("قابلیت دانلود نقشه در حال توسعه است.")


with col2_info:
    st.subheader(f"اطلاعات مزرعه: {selected_farm_name}")
    try:
        # Ensure farm_info is fetched correctly
        farm_info_series = farm_data_full[farm_data_full['مزرعه'] == selected_farm_name]
        if not farm_info_series.empty:
            farm_info = farm_info_series.iloc[0]
            # Format coordinates safely
            lat_str = f"{farm_info.get('عرض جغرافیایی', 'N/A'):.5f}" if pd.notna(farm_info.get('عرض جغرافیایی')) else 'N/A'
            lon_str = f"{farm_info.get('طول جغرافیایی', 'N/A'):.5f}" if pd.notna(farm_info.get('طول جغرافیایی')) else 'N/A'
            coords_missing_status = 'گمشده' if farm_info.get('coordinates_missing', True) else 'موجود'

            st.markdown(f"""
            - **کانال:** {farm_info.get('کانال', 'N/A')}
            - **اداره:** {farm_info.get('اداره', 'N/A')}
            - **مساحت داشت:** {farm_info.get('مساحت داشت', 'N/A')} هکتار
            - **واریته:** {farm_info.get('واریته', 'N/A')}
            - **سن:** {farm_info.get('سن', 'N/A')}
            - **مختصات:** ({lat_str}, {lon_str})
            - **وضعیت داده مختصات:** {coords_missing_status}
            - **روز هفته (فیلتر):** {farm_info.get('روزهای هفته', 'N/A')}
            """)
        else:
            st.warning(f"اطلاعات مزرعه {selected_farm_name} در فایل CSV یافت نشد.")

    except Exception as e:
        st.error(f"خطا در نمایش اطلاعات مزرعه: {e}")


    st.markdown("---")
    st.subheader("راهنمای رنگ نقشه")
    palette_name = INDEX_PALETTES.get(selected_index, '')
    if palette_name:
        colors = palette_name.split(', ')
        vis_params = INDEX_RANGES.get(selected_index, {})
        min_val = vis_params.get('min', 'N/A')
        max_val = vis_params.get('max', 'N/A')

        # Improved legend based on palette type
        if len(colors) >= 2:
             # Display first and last color with min/max values
             st.markdown(f"""
             - <span style='color:#{colors[0]};'>■</span> : مقدار کم ({min_val})
             - ...
             - <span style='color:#{colors[-1]};'>■</span> : مقدار زیاد ({max_val})
             """, unsafe_allow_html=True)
             if len(colors) == 3: # Add middle color if 3 colors
                 st.markdown(f"""
                 - <span style='color:#{colors[1]};'>■</span> : مقدار متوسط
                 """, unsafe_allow_html=True)
             # Specific interpretation for common indices
             if selected_index in ['NDVI', 'EVI', 'LAI', 'Biomass', 'Chlorophyll', 'Chlorophyll_Proxy']:
                 st.caption(f"رنگ سبزتر نشان دهنده پوشش گیاهی سالم تر/بیشتر است.")
             elif selected_index == 'NDMI':
                 st.caption("رنگ آبی تر نشان دهنده رطوبت بیشتر است.")
             elif selected_index == 'MSI':
                 st.caption("رنگ آبی تر نشان دهنده رطوبت بیشتر (استرس کمتر) است.")

        else: # Generic legend if palette is unusual
            st.markdown(f"پالت رنگ: {palette_name}")
            st.markdown(f"محدوده مقادیر: {min_val} تا {max_val}")
    else:
        st.markdown("پالت رنگی برای این شاخص تعریف نشده است.")


st.markdown("---")

# --- Time Series Chart ---
st.subheader(f"نمودار سری زمانی شاخص {selected_index} برای مزرعه {selected_farm_name}")
st.markdown(f"بازه زمانی: {ts_start_date.strftime(DATE_FORMAT)} تا {ts_end_date.strftime(DATE_FORMAT)}")

# Add a placeholder while data is loading
ts_chart_placeholder = st.empty()
ts_chart_placeholder.info(f"در حال بارگذاری داده‌های سری زمانی برای {selected_farm_name}...")

# MODIFIED: Pass selected_farm_geometry
ts_df = get_time_series_for_farm(
    selected_farm_name,
    selected_farm_geometry, # Pass the actual geometry object
    selected_index,
    ts_start_date.strftime(DATE_FORMAT),
    ts_end_date.strftime(DATE_FORMAT),
    data_source
)

# Clear placeholder before showing chart or warning
ts_chart_placeholder.empty()

if ts_df is not None and not ts_df.empty:
    # Determine the correct column name (handle proxies)
    index_col_name_ts = selected_index
    if selected_index == 'ET' and data_source == 'Sentinel-2': index_col_name_ts = 'ET_Proxy'
    if selected_index == 'Chlorophyll' and data_source == 'Landsat': index_col_name_ts = 'Chlorophyll_Proxy'

    # Ensure the column exists before plotting
    if index_col_name_ts in ts_df.columns:
        try:
            fig = px.line(ts_df, x='date', y=index_col_name_ts, title=f'روند زمانی {selected_index} برای {selected_farm_name}', markers=True)
            fig.update_layout(xaxis_title='تاریخ', yaxis_title=selected_index)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"خطا در رسم نمودار سری زمانی: {e}")
    else:
         st.warning(f"داده‌ای برای ستون '{index_col_name_ts}' در سری زمانی مزرعه {selected_farm_name} یافت نشد.")

elif ts_df is not None and ts_df.empty:
    st.warning(f"هیچ داده‌ای برای سری زمانی {selected_index} در بازه زمانی مشخص شده برای مزرعه {selected_farm_name} یافت نشد.")
else:
    # Error message is likely already shown by the function call
    st.error(f"خطا در دریافت داده‌های سری زمانی برای مزرعه {selected_farm_name}.")


st.markdown("---")

# --- Farm Ranking and Comparison ---
st.subheader(f"تحلیل و مقایسه مزارع بر اساس شاخص {selected_index}")
st.markdown(f"تاریخ مرجع برای تحلیل هفتگی: {today.strftime(DATE_FORMAT)}")
if selected_day != "همه" and available_days : # Check if filtering is active and possible
    st.markdown(f"فیلتر شده برای مزارع با روز هفته: **{selected_day}** ({len(filtered_farm_names)} مزرعه)")
elif not available_days:
     st.markdown(f"نمایش همه مزارع معتبر ({len(filtered_farm_names)} مزرعه) - فیلتر روز هفته غیرفعال.")
else:
     st.markdown(f"نمایش همه مزارع معتبر ({len(filtered_farm_names)} مزرعه)")


# Check if there are farms to analyze
if not filtered_farm_names:
    st.warning("هیچ مزرعه‌ای برای تحلیل و مقایسه با فیلترهای انتخابی وجود ندارد.")
else:
    # --- Weekly Ranking Table ---
    ranking_col, comparison_col = st.columns(2)

    with ranking_col:
        st.markdown(f"**رتبه‌بندی مزارع (میانگین ۷ روز اخیر)**")
        ranking_placeholder = st.empty()
        ranking_placeholder.info(f"در حال محاسبه میانگین هفتگی {selected_index} برای {len(filtered_farm_names)} مزرعه...")

        # MODIFIED: Pass filtered_farm_geometries
        weekly_avg_today = calculate_weekly_average(
            filtered_farm_names,
            filtered_farm_geometries, # Pass the dict of geometries
            selected_index,
            today,
            data_source
        )

        # Clear placeholder
        ranking_placeholder.empty()

        if weekly_avg_today:
            # Filter out potential NaN values before creating DataFrame
            valid_averages = {farm: avg for farm, avg in weekly_avg_today.items() if avg is not None and not math.isnan(avg)}
            if valid_averages:
                ranking_df = pd.DataFrame(list(valid_averages.items()), columns=['مزرعه', f'میانگین {selected_index}'])
                # Sort descending for beneficial indices (NDVI, EVI, LAI, Biomass, Chlorophyll, ET_Proxy)
                # Sort ascending for stress indices (MSI)
                ascending_sort = selected_index in ['MSI'] # Lower MSI is better (less stress)
                ranking_df = ranking_df.sort_values(by=f'میانگین {selected_index}', ascending=ascending_sort).reset_index(drop=True)
                ranking_df.index += 1 # Start ranking from 1
                st.dataframe(ranking_df.style.format({f'میانگین {selected_index}': "{:.3f}"}), use_container_width=True)
            else:
                 st.warning(f"هیچ مقدار معتبری برای رتبه‌بندی میانگین هفتگی {selected_index} محاسبه نشد.")

        else:
            st.warning(f"محاسبه میانگین هفتگی {selected_index} با خطا مواجه شد یا داده‌ای یافت نشد.")


    # --- Weekly Comparison ---
    with comparison_col:
        st.markdown(f"**مقایسه هفتگی (۷ روز اخیر در مقابل ۷ روز قبل)**")
        comparison_placeholder = st.empty()
        comparison_placeholder.info(f"در حال محاسبه مقایسه هفتگی {selected_index} برای {len(filtered_farm_names)} مزرعه...")

        # Calculate average for the 7 days before the last 7 days
        previous_week_end_date = today - datetime.timedelta(days=7)
        # MODIFIED: Pass filtered_farm_geometries
        weekly_avg_previous = calculate_weekly_average(
            filtered_farm_names,
            filtered_farm_geometries, # Pass the dict of geometries
            selected_index,
            previous_week_end_date,
            data_source
        )

        # Clear placeholder
        comparison_placeholder.empty()

        # Ensure both dictionaries were successfully populated (even if with NaNs)
        if weekly_avg_today is not None and weekly_avg_previous is not None:
            compare_data = []
            report_lines = [f"**گزارش تحلیلی مقایسه هفتگی برای شاخص {selected_index}:**",
                            f"(مقایسه میانگین {today - datetime.timedelta(days=6)} تا {today} با {previous_week_end_date - datetime.timedelta(days=6)} تا {previous_week_end_date})",
                            ""] # Add empty line

            increased_farms = []
            decreased_farms = []
            no_change_farms = []

            for farm_name in filtered_farm_names: # Iterate through the filtered list
                current_avg = weekly_avg_today.get(farm_name) # Use .get() for safety
                previous_avg = weekly_avg_previous.get(farm_name)

                # Check if both values are valid numbers for comparison
                if current_avg is not None and previous_avg is not None and not math.isnan(current_avg) and not math.isnan(previous_avg):
                    change = current_avg - previous_avg
                    # Handle division by zero or near-zero for percentage change
                    if abs(previous_avg) > 1e-6:
                         change_pct = (change / previous_avg) * 100
                    else:
                         change_pct = 0 # Assign 0% change if previous average was effectively zero

                    compare_data.append({
                        'مزرعه': farm_name,
                        'میانگین هفته اخیر': current_avg,
                        'میانگین هفته قبل': previous_avg,
                        'تغییر': change,
                        'درصد تغییر': change_pct
                    })
                    # Add to report lists based on percentage change threshold
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
                        'میانگین هفته اخیر': current_avg if current_avg is not None and not math.isnan(current_avg) else 'N/A',
                        'میانگین هفته قبل': previous_avg if previous_avg is not None and not math.isnan(previous_avg) else 'N/A',
                        'تغییر': 'N/A',
                        'درصد تغییر': 'N/A'
                    })

            if compare_data:
                compare_df = pd.DataFrame(compare_data)
                st.dataframe(compare_df.style.format({
                    'میانگین هفته اخیر': "{:.3f}",
                    'میانگین هفته قبل': "{:.3f}",
                    'تغییر': "{:+.3f}",
                    'درصد تغییر': "{:+.1f}%"
                }, na_rep='N/A'), use_container_width=True) # Use na_rep for display
            else:
                 st.warning("داده‌ای برای جدول مقایسه تولید نشد.")


            # --- Generate Text Report ---
            st.markdown("---")
            st.subheader("گزارش تحلیلی هفتگی")
            report_placeholder = st.empty()
            report_placeholder.info("در حال تولید گزارش...")

            # Interpretation based on index type
            # Higher is better for NDVI, EVI, LAI, Biomass, Chlorophyll, ET_Proxy, NDMI (more moisture)
            # Lower is better for MSI (less stress)
            positive_change_is_good = selected_index not in ['MSI']

            if positive_change_is_good:
                if increased_farms:
                    report_lines.append(f"📈 **بهبود وضعیت ({selected_index}):** مزارع {', '.join(increased_farms)} در هفته اخیر نسبت به هفته قبل بهبود نشان داده‌اند.")
                if decreased_farms:
                    report_lines.append(f"📉 **کاهش وضعیت ({selected_index}):** مزارع {', '.join(decreased_farms)} در هفته اخیر نسبت به هفته قبل کاهش نشان داده‌اند و نیاز به بررسی بیشتر دارند.")
            else: # For stress indices like MSI
                 if increased_farms: # Increase in MSI is bad
                    report_lines.append(f"📈 **افزایش استرس ({selected_index}):** مزارع {', '.join(increased_farms)} در هفته اخیر نسبت به هفته قبل افزایش استرس نشان داده‌اند و نیاز به بررسی فوری دارند.")
                 if decreased_farms: # Decrease in MSI is good
                    report_lines.append(f"📉 **کاهش استرس ({selected_index}):** مزارع {', '.join(decreased_farms)} در هفته اخیر نسبت به هفته قبل کاهش استرس نشان داده‌اند.")

            if no_change_farms:
                 report_lines.append(f"📊 **وضعیت پایدار ({selected_index}):** مزارع {', '.join(no_change_farms)} تغییر قابل توجهی (کمتر از ۱٪) نسبت به هفته قبل نداشته‌اند.")

            # Check if any comparison was actually made
            if not increased_farms and not decreased_farms and not no_change_farms:
                 report_lines.append("داده کافی برای مقایسه هفتگی مزارع فیلتر شده وجود ندارد یا هیچ تغییری ثبت نشد.")

            report_placeholder.markdown("\n\n".join(report_lines)) # Add more spacing between lines


        else:
            st.warning("محاسبه مقایسه هفتگی با خطا مواجه شد یا داده‌ای برای هر دو دوره یافت نشد.")
            st.markdown("---")
            st.subheader("گزارش تحلیلی هفتگی")
            st.warning("امکان تولید گزارش تحلیلی به دلیل عدم وجود داده‌های مقایسه‌ای وجود ندارد.")


# --- Footer ---
st.markdown("---")
st.caption("طراحی و توسعه توسط هوش مصنوعی | داده‌های ماهواره‌ای: Sentinel-2 (ESA), Landsat 8/9 (NASA/USGS) | پردازش: Google Earth Engine")
