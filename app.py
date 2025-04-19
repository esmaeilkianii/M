import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
import json
import datetime
from datetime import timedelta # Import timedelta
import plotly.express as px
import plotly.graph_objects as go # For grouped bar chart
import os
from io import BytesIO
import requests # Needed for getThumbUrl download
import numpy as np # For calculations and handling potential NaNs

# --- Configuration ---
APP_TITLE = "داشبورد هوشمند مانیتورینگ مزارع نیشکر دهخدا"
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 12

# --- File Paths (Relative to the script location in Hugging Face) ---
# Ensure these files are in the same directory as your app.py or provide correct path
CSV_FILE_PATH = 'output (1).csv'
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json' # Your service account file

# --- GEE Authentication ---
@st.cache_resource # Cache the GEE initialization for efficiency
def initialize_gee():
    """Initializes Google Earth Engine using the Service Account."""
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"خطا: فایل Service Account در مسیر '{SERVICE_ACCOUNT_FILE}' یافت نشد. لطفاً فایل را کنار اسکریپت قرار دهید.")
            st.stop()
        credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
        # Use high-volume endpoint for potentially better performance
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Initialized Successfully using Service Account.")
        return True # Indicate success
    except ee.EEException as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.error("لطفاً از صحت فایل Service Account، فعال بودن آن در پروژه GEE و اتصال اینترنت اطمینان حاصل کنید.")
        st.stop() # Stop execution if GEE fails
    except Exception as e:
        st.error(f"خطای غیرمنتظره هنگام اتصال به GEE: {e}")
        st.stop()

# --- Data Loading ---
@st.cache_data # Cache the loaded data
def load_data(csv_path):
    """Loads and preprocesses farm data from the CSV file."""
    try:
        df = pd.read_csv(csv_path)
        # **Critical Step**: Clean column names FIRST
        df.columns = df.columns.str.strip() # Remove leading/trailing whitespace from headers
        print(f"Original columns: {df.columns.tolist()}") # Debug: See original columns

        # Rename columns for easier access if needed (optional)
        # df = df.rename(columns={'سن ': 'سن'}) # Example if you prefer no space

        # Convert coordinates to numeric, coercing errors to NaN
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')

        # Convert area to numeric
        df['مساحت داشت'] = pd.to_numeric(df['مساحت داشت'], errors='coerce')

        # Standardize farm IDs
        df['مزرعه'] = df['مزرعه'].str.strip()

        # Fill potential NaN in categorical columns with a placeholder AFTER converting to string
        for col in ['کانال', 'اداره', 'واریته', 'سن', 'روزهای هفته']: # Use cleaned name 'سن'
             if col in df.columns:
                # Convert to string first to handle mixed types (like numbers in 'کانال')
                df[col] = df[col].astype(str).fillna('نامشخص')
             else:
                 print(f"Warning: Column '{col}' not found during data loading.")


        # Ensure coordinates_missing is integer, handle potential NaN after coercion
        if 'coordinates_missing' in df.columns:
             df['coordinates_missing'] = pd.to_numeric(df['coordinates_missing'], errors='coerce').fillna(1).astype(int)
        else:
             print("Warning: Column 'coordinates_missing' not found. Assuming missing (1).")
             df['coordinates_missing'] = 1 # Add column if missing, assuming coordinates are missing


        print(f"Data loaded successfully. Shape: {df.shape}")
        print(f"Cleaned columns: {df.columns.tolist()}") # Debug: See cleaned columns
        return df
    except FileNotFoundError:
        st.error(f"خطا: فایل CSV در مسیر '{csv_path}' یافت نشد.")
        st.stop()
    except Exception as e:
        st.error(f"خطا در بارگذاری یا پردازش فایل CSV: {e}")
        st.exception(e) # Print full traceback for debugging
        st.stop()

# --- GEE Image Processing Functions ---

# Define common band names (used AFTER processing)
COMMON_BAND_NAMES = ['Blue', 'Green', 'Red', 'RedEdge1', 'NIR', 'SWIR1', 'SWIR2']

# --- Masking Functions (Optimized) ---
def mask_s2_clouds(image):
    img_ee = ee.Image(image)
    qa = img_ee.select('QA60')
    cloud_mask = 1 << 10
    cirrus_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_mask).eq(0).And(qa.bitwiseAnd(cirrus_mask).eq(0))
    # Select necessary data bands, scale, and apply mask
    data_bands = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12']
    # Scale factor for Sentinel-2 SR is 10000
    return img_ee.select(data_bands).updateMask(mask).divide(10000.0)\
        .copyProperties(img_ee, ["system:time_start"])

def mask_landsat_clouds(image):
    img_ee = ee.Image(image)
    qa = img_ee.select('QA_PIXEL')
    # Check Collection 2 specification for cloud, shadow, snow bits
    cloud_shadow_mask = 1 << 3
    snow_mask = 1 << 4
    cloud_mask = 1 << 5
    mask = qa.bitwiseAnd(cloud_shadow_mask).eq(0)\
             .And(qa.bitwiseAnd(snow_mask).eq(0))\
             .And(qa.bitwiseAnd(cloud_mask).eq(0))
    # Apply scaling factors for Collection 2 Level 2 SR bands
    sr_bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']
    scale = 0.0000275; offset = -0.2
    scaled_bands = img_ee.select(sr_bands).multiply(scale).add(offset)
    return scaled_bands.updateMask(mask)\
        .copyProperties(img_ee, ["system:time_start"])


# --- Index Calculation Functions ---
# Ensure they return the calculated index band correctly named.
def calculate_ndvi(image):
    img_ee = ee.Image(image)
    return img_ee.normalizedDifference(['NIR', 'Red']).rename('NDVI')

def calculate_evi(image):
    img_ee = ee.Image(image)
    # Ensure necessary bands exist before expression
    try:
        img_ee.select(['NIR', 'Red', 'Blue']) # Check existence
        evi = img_ee.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                'NIR': img_ee.select('NIR'), 'RED': img_ee.select('Red'), 'BLUE': img_ee.select('Blue')
            })
        return evi.rename('EVI')
    except ee.EEException as e:
        # Return a dummy band or handle error if bands are missing
        print(f"Could not calculate EVI, possibly missing bands: {e}")
        return ee.Image().rename('EVI') # Return empty image named EVI

def calculate_ndmi(image):
    img_ee = ee.Image(image)
    return img_ee.normalizedDifference(['NIR', 'SWIR1']).rename('NDMI')

def calculate_msi(image):
    img_ee = ee.Image(image)
    return img_ee.expression('SWIR1 / NIR', { 'SWIR1': img_ee.select('SWIR1'), 'NIR': img_ee.select('NIR') }).rename('MSI')

def calculate_lai_simple(image):
    img_ee = ee.Image(image)
    try:
        # Prefer EVI if available
        evi_img = calculate_evi(img_ee) # Calculate EVI (handles band check internally)
        # Check if EVI calculation was successful (returned a band)
        if 'EVI' in evi_img.bandNames().getInfo():
            lai = evi_img.select('EVI').multiply(3.5).add(0.1) # Placeholder EVI-based LAI
        else:
             raise ee.EEException("EVI calculation failed, using NDVI for LAI.") # Force fallback
    except Exception: # Catch potential EVI failure
        # Fallback to NDVI
        ndvi = img_ee.normalizedDifference(['NIR', 'Red'])
        lai = ndvi.multiply(5.0).add(0.1) # Placeholder NDVI-based LAI
    # Rename the final LAI calculation and clamp
    return lai.clamp(0, 8).rename('LAI')

def calculate_biomass_simple(image):
    img_ee = ee.Image(image)
    lai_image = calculate_lai_simple(img_ee) # This calculates and returns an image named 'LAI'
    # Check if LAI calculation was successful
    if 'LAI' in lai_image.bandNames().getInfo():
        lai = lai_image.select('LAI')
        a = 1.5; b = 0.2 # Placeholder coefficients - NEEDS CALIBRATION
        biomass = lai.multiply(a).add(b)
        return biomass.clamp(0, 50).rename('Biomass') # Placeholder clamp
    else:
        print("LAI calculation failed, cannot calculate Biomass.")
        return ee.Image().rename('Biomass') # Return empty Biomass image

def calculate_chlorophyll_mcari(image):
    img_ee = ee.Image(image)
    try:
        # Check for RedEdge1 band explicitly
        img_ee.select('RedEdge1')
        mcari = img_ee.expression('((RE1 - RED) - 0.2 * (RE1 - GREEN)) * (RE1 / RED)',
                                  {'RE1': img_ee.select('RedEdge1'), 'RED': img_ee.select('Red'), 'GREEN': img_ee.select('Green')})
        return mcari.rename('Chlorophyll')
    except ee.EEException:
         # Fallback to NDVI if RedEdge1 is missing (e.g., Landsat)
         ndvi = img_ee.normalizedDifference(['NIR', 'Red'])
         return ndvi.rename('Chlorophyll')

def calculate_et_placeholder(image):
    img_ee = ee.Image(image)
    # Using NDMI as a proxy for water content, related to ET potential
    ndmi = img_ee.normalizedDifference(['NIR', 'SWIR1'])
    return ndmi.rename('ET_proxy')

# --- Index Definitions Dictionary (with descriptions) ---
INDEX_DEFINITIONS = {
    'NDVI': {
        'func': calculate_ndvi, 'vis': {'min': 0, 'max': 1, 'palette': ['#d73027', '#fee08b', '#1a9850']}, # Red-Yellow-Green
        'name_fa': "شاخص پوشش گیاهی (NDVI)",
        'desc_fa': """**NDVI (شاخص نرمال‌شده تفاوت پوشش گیاهی):** رایج‌ترین شاخص برای سنجش سلامت و تراکم پوشش گیاهی سبز. مقادیر بالاتر نشان‌دهنده پوشش گیاهی سالم‌تر و متراکم‌تر است.
                    - **محدوده:** -۱ تا +۱ (برای پوشش گیاهی معمولاً ۰.۱ تا ۰.۹)
                    - **تفسیر:** < ۰.۲ (خاک، آب)، ۰.۲-۰.۵ (گیاه پراکنده/تنش)، > ۰.۵ (گیاه سالم و متراکم)""",
        'sort_ascending': False # Higher is better
    },
    'EVI': {
        'func': calculate_evi, 'vis': {'min': 0, 'max': 1, 'palette': ['#d73027', '#fee08b', '#1a9850']},
        'name_fa': "شاخص پوشش گیاهی بهبودیافته (EVI)",
        'desc_fa': """**EVI (شاخص بهبودیافته پوشش گیاهی):** مشابه NDVI اما با کاهش اثرات جوی و خاک زمینه، به‌ویژه در مناطق با پوشش گیاهی متراکم.
                    - **محدوده:** معمولاً ۰ تا ۱
                    - **تفسیر:** مقادیر بالاتر نشان‌دهنده پوشش گیاهی سالم‌تر و متراکم‌تر است.""",
        'sort_ascending': False
    },
    'NDMI': {
        'func': calculate_ndmi, 'vis': {'min': -0.5, 'max': 0.8, 'palette': ['#a50026', '#ffffbf', '#313695']}, # Brown-Yellow-Blue
        'name_fa': "شاخص رطوبت (NDMI)",
        'desc_fa': """**NDMI (شاخص نرمال‌شده تفاوت رطوبت):** میزان آب موجود در برگ‌ها را نشان می‌دهد.
                    - **محدوده:** -۱ تا +۱
                    - **تفسیر:** مقادیر بالاتر (آبی) نشان‌دهنده رطوبت بیشتر، مقادیر پایین‌تر (قهوه‌ای) نشان‌دهنده خشکی یا تنش آبی است.""",
        'sort_ascending': False
    },
    'MSI': {
        'func': calculate_msi, 'vis': {'min': 0.4, 'max': 2.5, 'palette': ['#1a9641', '#ffffbf', '#d7191c']}, # Green-Yellow-Red
        'name_fa': "شاخص تنش رطوبتی (MSI)",
        'desc_fa': """**MSI (شاخص تنش رطوبتی):** نیز به رطوبت گیاه حساس است، اما مقادیر **بالاتر** نشان‌دهنده تنش رطوبتی **بیشتر** است (برعکس NDMI).
                    - **محاسبه:** SWIR1 / NIR
                    - **محدوده:** معمولاً > ۰.۴
                    - **تفسیر:** مقادیر پایین‌تر (سبز) بهتر است، مقادیر بالاتر (قرمز) نشان‌دهنده تنش بیشتر است.""",
        'sort_ascending': True # Higher is worse (more stress)
    },
    'LAI': {
        'func': calculate_lai_simple, 'vis': {'min': 0, 'max': 8, 'palette': ['#fff5f0', '#fdcdb9', '#e34a33']}, # Light Orange to Red
        'name_fa': "شاخص سطح برگ (LAI - تخمینی)",
        'desc_fa': """**LAI (شاخص سطح برگ):** نسبت کل مساحت یک طرفه برگ به واحد سطح زمین (m²/m²). این یک **تخمین** بر اساس سایر شاخص‌هاست و نیاز به کالیبراسیون دارد.
                    - **محدوده:** معمولاً ۰ تا ۸+
                    - **تفسیر:** مقادیر بالاتر نشان‌دهنده پوشش گیاهی متراکم‌تر با سطح برگ بیشتر است.""",
        'sort_ascending': False
    },
    'Biomass': {
        'func': calculate_biomass_simple, 'vis': {'min': 0, 'max': 30, 'palette': ['#f7fcb9', '#addd8e', '#31a354']}, # Yellow-LightGreen-DarkGreen
        'name_fa': "زیست‌توده (Biomass - تخمینی)",
        'desc_fa': """**Biomass:** وزن ماده خشک گیاهی در واحد سطح (مثلاً تن بر هکتار). این نیز یک **تخمین** بر اساس LAI یا سایر شاخص‌هاست و نیاز به کالیبراسیون دقیق دارد.
                    - **محدوده:** وابسته به نوع گیاه و کالیبراسیون.
                    - **تفسیر:** مقادیر بالاتر نشان‌دهنده زیست‌توده بیشتر است.""",
        'sort_ascending': False
    },
    'Chlorophyll': {
        'func': calculate_chlorophyll_mcari, 'vis': {'min': 0, 'max': 1, 'palette': ['#ffffcc', '#a1dab4', '#253494']}, # Yellow-Green-Blue
        'name_fa': "شاخص کلروفیل (MCARI/NDVI)",
        'desc_fa': """**Chlorophyll Index:** به غلظت کلروفیل در برگ‌ها حساس است (مرتبط با فتوسنتز و سلامت). از شاخص MCARI (نیاز به باند RedEdge در Sentinel-2) یا NDVI (به عنوان تقریبی) استفاده می‌شود.
                    - **محدوده:** متغیر.
                    - **تفسیر:** مقادیر بالاتر معمولاً نشان‌دهنده کلروفیل بیشتر و سلامت بهتر گیاه است.""",
        'sort_ascending': False
    },
    'ET_proxy': {
        'func': calculate_et_placeholder, 'vis': {'min': -0.5, 'max': 0.8, 'palette': ['#a50026', '#ffffbf', '#313695']}, # Same as NDMI
        'name_fa': "پراکسی تبخیر-تعرق (ET - بر اساس NDMI)",
        'desc_fa': """**ET Proxy:** یک شاخص جایگزین برای نشان دادن وضعیت رطوبتی مرتبط با تبخیر و تعرق (ET). در اینجا از NDMI استفاده می‌شود. محاسبه دقیق ET بسیار پیچیده است.
                    - **تفسیر:** مقادیر بالاتر NDMI (رطوبت بیشتر) می‌تواند پتانسیل ET بالاتری را نشان دهد.""",
        'sort_ascending': False
    }
}


# --- GEE Data Retrieval ---
def get_image_collection(start_date, end_date, geometry=None, sensor='Sentinel-2'):
    """Gets, filters, masks, scales, and renames Sentinel-2 or Landsat images."""
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    collection_id = None
    bands_to_select_orig = []
    bands_to_rename_to = []
    mask_func = None

    if sensor == 'Sentinel-2':
        collection_id = 'COPERNICUS/S2_SR_HARMONIZED'
        mask_func = mask_s2_clouds
        bands_to_select_orig = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12', 'QA60']
        bands_to_rename_to = COMMON_BAND_NAMES # Uses the global list
    elif sensor == 'Landsat':
        # Combine L8 and L9 SR collections
        l9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
        l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        collection_id = l9.merge(l8) # Use merged collection
        mask_func = mask_landsat_clouds
        bands_to_select_orig = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'QA_PIXEL']
        # Landsat doesn't have RedEdge1 equivalent easily available for all indices
        bands_to_rename_to = ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2']
    else:
        st.error(f"سنسور نامعتبر: {sensor}")
        return None

    # Basic Date Range Check
    if start_date > end_date:
         st.error("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد.")
         return None

    # Create base collection object
    collection = ee.ImageCollection(collection_id) if isinstance(collection_id, str) else collection_id

    # Apply filters
    collection = collection.filterDate(start_date_str, end_date_str)
    if geometry:
        try:
            # Simple check if geometry seems valid before filtering
            if geometry.type().getInfo():
                 collection = collection.filterBounds(geometry)
        except Exception as e:
            st.error(f"خطا در فیلتر کردن مرزهای هندسی: {e}")
            return None

    # Check size before processing (can be slow)
    try:
        initial_count = collection.size().getInfo()
        if initial_count == 0:
            # Don't show warning if the date range itself is empty
            if (end_date - start_date).days >= 0:
                 st.warning(f"هیچ تصویری در بازه زمانی و منطقه انتخابی ({sensor}) قبل از ماسک ابر یافت نشد.", icon="⏳")
            return None
    except ee.EEException as e:
        st.error(f"خطا در دریافت تعداد اولیه تصاویر: {e}")
        return None


    # --- Processing Function (Mapped) ---
    def process_image(image_element):
        image = ee.Image(image_element)
        # Select necessary bands FIRST
        img_selected_orig = image.select(bands_to_select_orig)
        # Apply masking and scaling
        img_processed = mask_func(img_selected_orig)
        # Ensure it's an image before renaming
        img_processed_safe = ee.Image(img_processed)
        # Rename to common names
        # Rename might fail if mask_func returned fewer bands than expected
        try:
            # Check band count compatibility if needed
            # actual_bands = img_processed_safe.bandNames().length()
            # expected_bands = ee.Number(len(bands_to_rename_to))
            # ... conditional logic ...
            img_renamed = img_processed_safe.rename(bands_to_rename_to)
        except ee.EEException as rename_e:
            # Handle rename error, maybe return the image without renaming or log warning
            print(f"Warning: Could not rename bands for an image. Error: {rename_e}")
            # Decide how to proceed: return unprocessed, processed without rename, or skip?
            # Returning processed but not renamed might break downstream index calcs
            return None # Skip image if renaming fails
        # Copy essential properties
        return img_renamed.copyProperties(image, ["system:time_start"])

    # Map the processing function, removing nulls (images that failed processing)
    processed_collection = collection.map(process_image).filter(ee.Filter.neq('item', None))


    # Check size AFTER processing
    try:
        count = processed_collection.size().getInfo()
        if count == 0:
            st.warning(f"هیچ تصویر بدون ابری در بازه زمانی و منطقه انتخابی ({sensor}) یافت نشد.", icon="☁️")
            return None
    except ee.EEException as e:
        st.error(f"خطا در دریافت تعداد تصاویر پردازش شده: {e}")
        return None


    # Final check on first image bands (optional)
    try:
        first_image = processed_collection.first()
        if first_image:
            final_bands = ee.Image(first_image).bandNames().getInfo()
            print(f"Bands in first processed image: {final_bands}")
        else:
            # This case should be caught by the size check above, but for safety:
             st.warning("کالکشن پس از پردازش خالی شد.", icon="⚠️")
             return None

    except ee.EEException as e:
        # Non-critical error, proceed but log it
        print(f"Warning: Could not verify bands in first processed image: {e}")

    return processed_collection

# --- Function to calculate a single index for a collection ---
def calculate_single_index(collection, index_name):
    """Calculates a single specified index for the collection."""
    if collection is None: return None
    index_detail = INDEX_DEFINITIONS.get(index_name)
    if not index_detail:
        st.error(f"تعریف شاخص '{index_name}' یافت نشد.")
        return None

    index_func = index_detail['func']
    try:
        # Map the function - it should return an image containing the calculated index band
        indexed_collection = collection.map(index_func)

        # Check if the index band was actually created in the first image
        first_img = indexed_collection.first()
        if first_img and index_name in ee.Image(first_img).bandNames().getInfo():
             # Return the collection containing images with (at least) the calculated index band
             # Select only the index band for consistency downstream?
             return indexed_collection.select(index_name)
        else:
             # Log which bands ARE available if the index is missing
             available_bands = ee.Image(first_img).bandNames().getInfo() if first_img else "None"
             st.warning(f"باند شاخص '{index_name}' پس از محاسبه ایجاد نشد. باندهای موجود: {available_bands}", icon="⚠️")
             return None # Indicate failure
    except ee.EEException as e:
        st.error(f"خطای GEE در محاسبه شاخص '{index_name}': {e}")
        # Attempt to provide more context
        try:
            first_input_img = collection.first()
            if first_input_img:
                st.info(f"Bands input to failed index calculation: {ee.Image(first_input_img).bandNames().getInfo()}")
        except: pass # Ignore errors during error reporting
        return None
    except Exception as e:
        st.error(f"خطای غیر GEE در محاسبه شاخص '{index_name}': {e}")
        st.exception(e) # Show full traceback
        return None


# --- get_timeseries_for_farm ---
@st.cache_data(ttl=1800) # Cache for 30 minutes
def get_timeseries_for_farm(_farm_geom_geojson, start_date, end_date, index_name, sensor):
    """Retrieves and calculates the time series for a specific index and farm geometry."""
    try:
        farm_geom = ee.Geometry(json.loads(_farm_geom_geojson))
    except Exception as e:
        st.error(f"خطا در پردازش هندسه مزرعه: {e}")
        return pd.DataFrame(columns=['Date', index_name])

    # Get the base masked, renamed collection
    base_collection = get_image_collection(start_date, end_date, farm_geom, sensor)
    if base_collection is None: return pd.DataFrame(columns=['Date', index_name])

    # Calculate the specific index
    indexed_collection = calculate_single_index(base_collection, index_name)
    if indexed_collection is None: return pd.DataFrame(columns=['Date', index_name])

    # Define the extraction function
    def extract_value(image):
        img_ee = ee.Image(image) # Ensure image type
        # Use mean reducer over the buffered farm point geometry
        stats = img_ee.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=farm_geom, scale=30, maxPixels=1e9, tileScale=4
        )
        val = stats.get(index_name) # Get the calculated value
        time_ms = img_ee.get('system:time_start') # Get time from the image object
        # Return feature with time and value (or placeholder if null)
        return ee.Feature(None, {'time': time_ms, index_name: ee.Algorithms.If(val, val, -9999)})

    # Execute the extraction
    try:
        # Increase timeout? Not directly possible here. Use tileScale.
        ts_info = indexed_collection.map(extract_value).getInfo()
    except ee.EEException as e:
        st.error(f"خطای GEE در استخراج سری زمانی (reduceRegion): {e}")
        st.info("این خطا ممکن است به دلیل محدودیت حافظه یا زمان GEE باشد. سعی کنید بازه زمانی کوتاه‌تر یا منطقه کوچک‌تری را انتخاب کنید.")
        return pd.DataFrame(columns=['Date', index_name])
    except Exception as e:
        st.error(f"خطای ناشناخته در استخراج سری زمانی: {e}")
        return pd.DataFrame(columns=['Date', index_name])


    # Process results into DataFrame
    data = []
    if 'features' in ts_info:
        for feature in ts_info['features']:
            props = feature.get('properties', {})
            value = props.get(index_name)
            time_ms = props.get('time')
            # Validate data before appending
            if value not in [None, -9999] and time_ms is not None:
                try:
                    # Convert milliseconds timestamp to datetime
                    dt = datetime.datetime.fromtimestamp(time_ms / 1000.0)
                    data.append([dt, value])
                except (TypeError, ValueError) as time_e:
                     st.warning(f"نادیده گرفتن داده با زمان نامعتبر ({time_ms}): {time_e}", icon="⚠️")
    else:
        st.warning("ساختار 'features' در نتایج سری زمانی یافت نشد.")

    if not data: return pd.DataFrame(columns=['Date', index_name]) # Return empty if no valid data
    ts_df = pd.DataFrame(data, columns=['Date', index_name]).sort_values(by='Date').reset_index(drop=True)
    return ts_df

# --- Function for getting median index over a period for multiple farms ---
@st.cache_data(ttl=1800) # Cache for 30 minutes
def get_median_index_for_period(_farms_df_json, start_date, end_date, index_name, sensor):
    """Gets the median index value over a period for multiple farms."""
    farms_df = pd.read_json(_farms_df_json)
    farms_df_valid_coords = farms_df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی']).copy()

    if farms_df_valid_coords.empty:
         # Don't show warning here, let calling function handle empty result
         # st.warning("No farms with valid coordinates for period calculation.", icon="📍")
         return pd.DataFrame(columns=['مزرعه', index_name])

    features = []
    for idx, row in farms_df_valid_coords.iterrows():
        try:
             geom = ee.Geometry.Point([row['طول جغرافیایی'], row['عرض جغرافیایی']])
             buffered_geom = geom.buffer(50) # Buffer for reduction robustness
             # Ensure farm_id is included in properties
             feature = ee.Feature(buffered_geom, {'farm_id': row['مزرعه']})
             features.append(feature)
        except Exception as e:
             print(f"Warning: Skipping farm {row.get('مزرعه', 'Unknown')} due to geometry error: {e}")

    if not features:
         # st.warning("No valid farm geometries created.", icon="⚠️")
         return pd.DataFrame(columns=['مزرعه', index_name])

    farm_fc = ee.FeatureCollection(features)

    # Get base collection for the period
    base_collection = get_image_collection(start_date, end_date, farm_fc.geometry(), sensor)
    if base_collection is None: return pd.DataFrame(columns=['مزرعه', index_name])

    # Calculate the specified index
    indexed_collection = calculate_single_index(base_collection, index_name)
    if indexed_collection is None: return pd.DataFrame(columns=['مزرعه', index_name])

    # Create a median composite image for robustness against outliers
    median_image = indexed_collection.median() # Contains only the index band

    # Reduce the composite image over all farm geometries
    try:
        farm_values = median_image.reduceRegions(
            collection=farm_fc, reducer=ee.Reducer.mean(), scale=30, tileScale=8 # Increased tileScale
        ).getInfo()
    except ee.EEException as e:
        st.error(f"خطای GEE در محاسبه مقادیر مزارع (reduceRegions): {e}")
        return pd.DataFrame(columns=['مزرعه', index_name])
    except Exception as e:
         st.error(f"خطای ناشناخته در محاسبه مقادیر مزارع: {e}")
         return pd.DataFrame(columns=['مزرعه', index_name])

    # Extract results into a DataFrame
    results_data = []
    if 'features' in farm_values:
        for feature in farm_values['features']:
            props = feature.get('properties', {})
            farm_id = props.get('farm_id') # Get farm_id from properties
            value = props.get('mean') # Default output name for mean reducer
            if farm_id is not None and value is not None:
                results_data.append({'مزرعه': farm_id, index_name: value})
            else:
                # Log if reduction failed for a specific farm
                print(f"Warning: Could not get value for farm_id: {farm_id}, Props: {props}")
    else:
        st.warning("ساختار 'features' در نتایج reduceRegions یافت نشد.")

    if not results_data:
         # st.warning("No data extracted after GEE processing for farms.", icon="📊")
         return pd.DataFrame(columns=['مزرعه', index_name])

    results_df = pd.DataFrame(results_data)
    return results_df

# --- Function for Weekly Comparison ---
@st.cache_data(ttl=1800) # Cache for 30 minutes
def get_weekly_comparison(_filtered_df_json, start_date, end_date, index_name, sensor):
    """Compares the index values from the current week to the previous week."""
    if not isinstance(start_date, datetime.date) or not isinstance(end_date, datetime.date):
        st.error("تاریخ‌های شروع و پایان نامعتبر برای مقایسه هفتگی.")
        return pd.DataFrame()

    # Define current and previous week date ranges
    current_start = start_date
    current_end = end_date
    # Ensure previous week doesn't overlap
    prev_end = current_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=(end_date-start_date).days) # Match duration

    st.write(f"دوره فعلی: {current_start.strftime('%Y-%m-%d')} تا {current_end.strftime('%Y-%m-%d')}")
    st.write(f"دوره قبلی: {prev_start.strftime('%Y-%m-%d')} تا {prev_end.strftime('%Y-%m-%d')}")

    # Get data for the current period
    with st.spinner(f"درحال دریافت داده‌های '{index_name}' برای دوره فعلی..."):
        df_current = get_median_index_for_period(_filtered_df_json, current_start, current_end, index_name, sensor)
    if df_current.empty:
        st.warning(f"داده‌ای برای دوره فعلی ({current_start} تا {current_end}) جهت مقایسه یافت نشد.", icon="⚠️")
        return pd.DataFrame()

    # Get data for the previous period
    with st.spinner(f"درحال دریافت داده‌های '{index_name}' برای دوره قبلی..."):
        df_previous = get_median_index_for_period(_filtered_df_json, prev_start, prev_end, index_name, sensor)
    if df_previous.empty:
        st.warning(f"داده‌ای برای دوره قبلی ({prev_start} تا {prev_end}) جهت مقایسه یافت نشد.", icon="⚠️")
        return pd.DataFrame() # Cannot compare without previous week's data

    # Merge the dataframes on 'مزرعه'
    df_comparison = pd.merge(
        df_previous.rename(columns={index_name: f'{index_name}_prev'}),
        df_current.rename(columns={index_name: f'{index_name}_curr'}),
        on='مزرعه',
        how='inner' # Only compare farms present in BOTH periods
    )

    if df_comparison.empty:
        st.info("هیچ مزرعه مشترکی بین دو دوره زمانی برای مقایسه یافت نشد.")
        return pd.DataFrame()

    # Calculate difference and percentage change robustly
    df_comparison['تغییر'] = df_comparison[f'{index_name}_curr'] - df_comparison[f'{index_name}_prev']
    # Use numpy for safe division and handling potential NaNs
    df_comparison['درصد_تغییر'] = np.where(
        np.abs(df_comparison[f'{index_name}_prev']) > 1e-9, # Avoid division by very small numbers
       ((df_comparison['تغییر'] / df_comparison[f'{index_name}_prev']) * 100.0),
        np.nan # Assign NaN if previous value is too small or zero
    )

    # Filter for farms with decrease (change < 0)
    # Consider a small threshold? e.g., df_comparison['تغییر'] < -0.01
    df_decreased = df_comparison[df_comparison['تغییر'] < 0].copy()

    # Sort by percentage change (most negative first)
    df_decreased = df_decreased.sort_values(by='درصد_تغییر', ascending=True, na_position='last')

    return df_decreased


# --- Streamlit App Layout ---
st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")
st.title(f"🌾 {APP_TITLE}")
st.markdown("مانیتورینگ وضعیت مزارع نیشکر با استفاده از تصاویر ماهواره‌ای و Google Earth Engine")
st.divider()

# Initialize GEE (shows error if fails)
if initialize_gee():
    # Load data (shows error if fails)
    farm_data_df = load_data(CSV_FILE_PATH)

    # --- Sidebar Controls ---
    with st.sidebar:
        st.header("⚙️ تنظیمات و فیلترها")
        st.divider()

        # --- Date Range Selection ---
        st.subheader("🗓️ انتخاب بازه زمانی")
        today = datetime.date.today()
        # Default to last 7 days ending today
        default_start = today - timedelta(days=6)
        start_date = st.date_input("تاریخ شروع", value=default_start, max_value=today, help="تاریخ شروع دوره تحلیل اصلی")
        end_date = st.date_input("تاریخ پایان", value=today, min_value=start_date, max_value=today, help="تاریخ پایان دوره تحلیل اصلی")
        st.info(f"مدت دوره: {(end_date - start_date).days + 1} روز", icon="⏳")
        st.divider()

        # --- Data Filters ---
        st.subheader("🔍 فیلتر داده‌ها")
        # Day of Week Filter
        days_list = ["همه روزها"] + sorted(farm_data_df['روزهای هفته'].unique().tolist())
        selected_day = st.selectbox("روز هفته آبیاری", options=days_list, help="فیلتر مزارع بر اساس روز هفته ثبت شده در فایل CSV")

        # Filter DataFrame based on selected day *before* subsequent controls
        if selected_day == "همه روزها":
            filtered_df = farm_data_df.copy()
        else:
            filtered_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day].copy()
        st.caption(f"{len(filtered_df)} مزرعه با فیلتر روز هفته انتخاب شده است.")

        # Index Selection for Analysis
        available_indices = list(INDEX_DEFINITIONS.keys())
        selected_index = st.selectbox(
            "شاخص مورد تحلیل",
            options=available_indices,
            format_func=lambda x: INDEX_DEFINITIONS[x]['name_fa'], # Show Persian name
            help="شاخصی که برای نقشه، رتبه‌بندی و مقایسه استفاده خواهد شد"
            )

        # Sensor Selection
        selected_sensor = st.radio(
            "سنسور ماهواره",
            ('Sentinel-2', 'Landsat'), index=0, horizontal=True,
            help="Sentinel-2 تفکیک مکانی بهتر (10m) و باندهای RedEdge دارد. Landsat توالی زمانی طولانی‌تر دارد."
            )
        st.divider()

        # --- Farm Selection ---
        st.subheader("🚜 انتخاب مزرعه")
        # Populate farm list based on the *day-filtered* data
        farm_list = ["همه مزارع"] + sorted(filtered_df['مزرعه'].unique().tolist())
        selected_farm = st.selectbox(
            "مزرعه خاص (یا همه)", options=farm_list,
             help="یک مزرعه خاص را برای مشاهده جزئیات و روند زمانی انتخاب کنید، یا 'همه مزارع' را برای دید کلی نگه دارید."
             )
        st.divider()


        # --- Display Index Information ---
        st.header("ℹ️ راهنمای شاخص‌ها")
        index_options = list(INDEX_DEFINITIONS.keys())
        index_to_explain = st.selectbox(
            "مشاهده توضیحات شاخص:",
            options=index_options,
            index=index_options.index(selected_index), # Default to selected index for analysis
            format_func=lambda x: INDEX_DEFINITIONS[x]['name_fa']
        )
        if index_to_explain:
            with st.expander(f"جزئیات شاخص {INDEX_DEFINITIONS[index_to_explain]['name_fa']}", expanded=False):
                st.markdown(INDEX_DEFINITIONS[index_to_explain]['desc_fa'], unsafe_allow_html=True)
        st.divider()
        st.caption("ساخته شده با Streamlit و Google Earth Engine")


    # --- Main Panel with Tabs ---
    tab1, tab2, tab3 = st.tabs([
        "🗺️ نقشه و جزئیات",
        "📊 رتبه‌بندی مزارع",
        "📉 مقایسه هفتگی"
        ])

    # --- Tab 1: Map and Farm Details ---
    with tab1:
        col_map, col_detail = st.columns([2, 1]) # Adjust column ratio

        with col_map:
            st.subheader(f"نقشه وضعیت: {INDEX_DEFINITIONS[selected_index]['name_fa']}")
            st.caption(f"دوره: {start_date.strftime('%Y-%m-%d')} تا {end_date.strftime('%Y-%m-%d')} | سنسور: {selected_sensor}")
            map_placeholder = st.empty() # Placeholder for the map
            m = geemap.Map(center=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False)
            m.add_basemap('HYBRID') # Use satellite view

            vis_params = INDEX_DEFINITIONS.get(selected_index, {}).get('vis')
            if not vis_params: vis_params = {'min': 0, 'max': 1, 'palette': ['white', 'gray']} # Fallback vis

            # Determine display geometry and target farm info
            display_geom = None
            target_object_for_map = None
            farm_info_for_display = None # Store info of the selected farm for details pane

            # Use the day-filtered data for display logic
            display_df = filtered_df.copy()

            if selected_farm == "همه مزارع":
                # Use only farms with valid coordinates for bounds calculation
                display_df_valid = display_df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
                if not display_df_valid.empty:
                    try:
                        min_lon, min_lat = display_df_valid['طول جغرافیایی'].min(), display_df_valid['عرض جغرافیایی'].min()
                        max_lon, max_lat = display_df_valid['طول جغرافیایی'].max(), display_df_valid['عرض جغرافیایی'].max()
                        display_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
                        target_object_for_map = display_geom
                    except Exception as bounds_e:
                        st.error(f"خطا در محاسبه مرزها: {bounds_e}")
                else:
                    st.info("هیچ مزرعه‌ای با مختصات معتبر برای نمایش در این روز هفته یافت نشد.", icon="📍")
            else: # Single farm selected
                farm_info_rows = display_df[display_df['مزرعه'] == selected_farm]
                if not farm_info_rows.empty:
                    farm_info_for_display = farm_info_rows.iloc[0] # Save for details pane
                    farm_lat = farm_info_for_display['عرض جغرافیایی']
                    farm_lon = farm_info_for_display['طول جغرافیایی']
                    if pd.notna(farm_lat) and pd.notna(farm_lon):
                        try:
                            farm_geom = ee.Geometry.Point([farm_lon, farm_lat])
                            display_geom = farm_geom.buffer(150) # Area around point for vis
                            target_object_for_map = farm_geom # Center on the actual point
                        except Exception as point_e:
                             st.error(f"خطا در ایجاد هندسه نقطه: {point_e}")
                             farm_info_for_display = None # Invalidate if geom fails
                    else:
                        st.warning(f"مختصات نامعتبر برای مزرعه {selected_farm}.", icon="📍")
                        farm_info_for_display = None
                else:
                    st.warning(f"اطلاعات مزرعه {selected_farm} برای روز هفته '{selected_day}' یافت نشد.", icon="⚠️")

            # --- Fetch data and display layer on map ---
            if display_geom:
                with st.spinner(f"در حال پردازش نقشه '{selected_index}'... لطفاً کمی صبر کنید."):
                    base_collection = get_image_collection(start_date, end_date, display_geom, selected_sensor)
                    layer_added = False # Flag to check if layer was added
                    if base_collection:
                        indexed_collection = calculate_single_index(base_collection, selected_index)
                        if indexed_collection:
                            try:
                                median_image = indexed_collection.median()
                                # Clip layer visually if single farm selected
                                layer_image = median_image.clip(display_geom) if selected_farm != "همه مزارع" else median_image
                                # Add layer to map
                                m.addLayer(layer_image, vis_params, f'{selected_index} (Median)')
                                layer_added = True # Mark as added
                                # Add legend
                                try:
                                    m.add_legend(title=f'{selected_index}', builtin_legend=None, palette=vis_params['palette'], min=vis_params['min'], max=vis_params['max'])
                                except Exception as legend_e:
                                     print(f"Warning: Could not add legend: {legend_e}") # Log warning

                                # Add download button for map layer
                                try:
                                    thumb_url = median_image.getThumbURL({
                                        'region': display_geom.toGeoJson(), 'bands': selected_index,
                                        'palette': vis_params['palette'], 'min': vis_params['min'], 'max': vis_params['max'],
                                        'dimensions': 512 })
                                    response = requests.get(thumb_url)
                                    if response.status_code == 200:
                                        st.sidebar.download_button(
                                            label=f"📥 دانلود نقشه ({selected_index})", data=BytesIO(response.content),
                                            file_name=f"map_{selected_farm if selected_farm != 'همه مزارع' else 'all'}_{selected_index}.png",
                                            mime="image/png", key=f"dl_map_{selected_index}_{selected_farm}" )
                                except Exception as thumb_e:
                                     print(f"Warning: Could not generate map thumbnail: {thumb_e}") # Log warning

                            except ee.EEException as ee_err:
                                st.error(f"خطای GEE هنگام پردازش لایه نقشه: {ee_err}")
                            except Exception as err:
                                st.error(f"خطای ناشناخته هنگام پردازش لایه نقشه: {err}")
                        else:
                             st.warning(f"محاسبه شاخص '{selected_index}' برای نقشه ممکن نبود.", icon="⚠️")
                    else:
                         # Warnings are shown inside get_image_collection if no images found
                         pass # st.info("تصویری برای پردازش نقشه یافت نشد.")

                # --- Add markers ---
                if layer_added: # Only add markers if the layer was processed
                    if selected_farm == "همه مزارع":
                        # Mark all farms from the day-filtered list with valid coords
                        df_to_mark = display_df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
                        for idx, row in df_to_mark.iterrows():
                            # Use cleaned column name 'سن'
                            popup_html = f"<b>مزرعه:</b> {row['مزرعه']}<br><b>کانال:</b> {row['کانال']} | <b>اداره:</b> {row['اداره']}<br><b>مساحت:</b> {row['مساحت داشت']:.2f}<br><b>واریته:</b> {row['واریته']} | <b>سن:</b> {row['سن']}"
                            folium.Marker(location=[row['عرض جغرافیایی'], row['طول جغرافیایی']],
                                          popup=folium.Popup(popup_html, max_width=250),
                                          tooltip=f"{row['مزرعه']}",
                                          icon=folium.Icon(color='blue', icon='info-sign', prefix='fa') # Use FontAwesome icons
                                          ).add_to(m)
                    elif farm_info_for_display is not None: # Single farm selected and info is valid
                        farm_info = farm_info_for_display
                        # Use cleaned column name 'سن'
                        popup_html = f"<b>مزرعه:</b> {farm_info['مزرعه']}<br><b>کانال:</b> {farm_info['کانال']} | <b>اداره:</b> {farm_info['اداره']}<br><b>مساحت:</b> {farm_info['مساحت داشت']:.2f}<br><b>واریته:</b> {farm_info['واریته']} | <b>سن:</b> {farm_info['سن']}"
                        folium.Marker(location=[farm_info['عرض جغرافیایی'], farm_info['طول جغرافیایی']],
                                      popup=folium.Popup(popup_html, max_width=250),
                                      tooltip=f"{farm_info['مزرعه']} (انتخاب شده)",
                                      icon=folium.Icon(color='red', icon='star', prefix='fa') # Red star for selected
                                      ).add_to(m)

                # Center the map view
                if target_object_for_map:
                    zoom_level = INITIAL_ZOOM + 2 if selected_farm != "همه مزارع" else INITIAL_ZOOM
                    try: m.center_object(target_object_for_map, zoom=zoom_level)
                    except Exception as center_e:
                         print(f"Warning: Could not center map object: {center_e}")
                         m.set_center(INITIAL_LON, INITIAL_LAT, INITIAL_ZOOM) # Fallback center

            else:
                # No valid geometry determined earlier
                st.info("لطفاً یک مزرعه معتبر انتخاب کنید یا از وجود مزارع با مختصات صحیح در فایل CSV اطمینان حاصل کنید.")


            # Render the map in the placeholder
            with map_placeholder:
                m.to_streamlit(height=550) # Slightly taller map


        # --- Column 2: Farm Details and Timeseries ---
        with col_detail:
            if selected_farm != "همه مزارع":
                st.subheader(f" جزئیات مزرعه: {selected_farm}")
                st.divider()
                if farm_info_for_display is not None:
                    farm_info = farm_info_for_display # Use the data fetched for map display
                    # Display metrics using cleaned column name 'سن'
                    st.metric("کانال", str(farm_info.get('کانال', 'N/A')), help="شماره کانال آبیاری")
                    st.metric("اداره", str(farm_info.get('اداره', 'N/A')), help="شماره اداره مربوطه")
                    st.metric("مساحت (هکتار)", f"{farm_info['مساحت داشت']:.2f}" if pd.notna(farm_info.get('مساحت داشت')) else "N/A", help="مساحت ثبت شده مزرعه")
                    st.metric("واریته", str(farm_info.get('واریته', 'N/A')), help="نوع واریته کشت شده")
                    st.metric("سن", str(farm_info.get('سن', 'N/A')), help="سن کشت (P: پلانت، R: راتون)") # Access cleaned name
                    st.metric("روز آبیاری", str(farm_info.get('روزهای هفته', 'N/A')), help="روز هفته آبیاری طبق برنامه")
                    st.divider()

                    # --- Timeseries Chart ---
                    st.subheader(f"📈 روند شاخص: {INDEX_DEFINITIONS[selected_index]['name_fa']}")
                    # Check coordinates again before potentially expensive GEE call
                    if pd.notna(farm_info.get('عرض جغرافیایی')) and pd.notna(farm_info.get('طول جغرافیایی')):
                        with st.spinner(f"در حال دریافت سری زمانی '{selected_index}'..."):
                            # Create geometry again safely
                            try:
                                farm_geom_ts = ee.Geometry.Point([farm_info['طول جغرافیایی'], farm_info['عرض جغرافیایی']])
                                # Pass geom as GeoJSON string for caching
                                ts_df = get_timeseries_for_farm(farm_geom_ts.toGeoJsonString(), start_date, end_date, selected_index, selected_sensor)
                            except Exception as ts_geom_e:
                                st.error(f"خطا در ایجاد هندسه برای سری زمانی: {ts_geom_e}")
                                ts_df = pd.DataFrame() # Ensure empty df

                        if not ts_df.empty:
                            fig_ts = px.line(ts_df, x='Date', y=selected_index,
                                            title=f"روند زمانی {selected_index} برای مزرعه {selected_farm}",
                                            markers=True, labels={'Date': 'تاریخ', selected_index: f'مقدار {selected_index}'})
                            fig_ts.update_layout(xaxis_title="تاریخ", yaxis_title=f"مقدار {selected_index}", title_x=0.5)
                            fig_ts.update_traces(line=dict(color='royalblue', width=2), marker=dict(color='salmon', size=6))
                            st.plotly_chart(fig_ts, use_container_width=True)
                        else:
                            st.info(f"داده‌ای برای نمایش نمودار روند زمانی '{selected_index}' در بازه انتخابی یافت نشد.", icon="📉")
                    else:
                        st.warning("مختصات نامعتبر برای دریافت سری زمانی.", icon="📍")
                else:
                    st.info("اطلاعات این مزرعه برای روز هفته یا انتخاب فعلی در دسترس نیست یا مختصات نامعتبر است.")
            else: # "همه مزارع" selected
                 st.subheader("راهنمای جزئیات و روند")
                 st.info("""
                 برای مشاهده جزئیات کامل و نمودار روند زمانی یک مزرعه خاص:
                 1.  از نوار کناری، فیلتر **روز هفته آبیاری** را (در صورت نیاز) تنظیم کنید.
                 2.  از منوی **مزرعه خاص (یا همه)**، نام مزرعه مورد نظر را انتخاب نمایید.
                 3.  جزئیات و نمودار در این بخش نمایش داده خواهد شد.
                 """, icon="👈")


    # --- Tab 2: Ranking ---
    with tab2:
        st.subheader(f"📊 رتبه‌بندی مزارع بر اساس شاخص: {INDEX_DEFINITIONS[selected_index]['name_fa']}")
        st.caption(f"میانگین مقدار شاخص '{selected_index}' در بازه زمانی {start_date.strftime('%Y-%m-%d')} تا {end_date.strftime('%Y-%m-%d')} برای مزارع با روز هفته '{selected_day}'.")
        st.divider()

        # Use the filtered_df which respects the day filter
        if filtered_df.empty:
             st.warning(f"هیچ مزرعه‌ای برای روز هفته '{selected_day}' جهت رتبه‌بندی یافت نشد.", icon="⚠️")
        else:
            with st.spinner(f"در حال محاسبه رتبه‌بندی '{selected_index}'..."):
                # Pass the day-filtered DataFrame JSON for ranking
                ranking_df = get_median_index_for_period(filtered_df.to_json(), start_date, end_date, selected_index, sensor=selected_sensor)

            if not ranking_df.empty:
                # Determine sort order based on index definition
                ascending_sort = INDEX_DEFINITIONS[selected_index].get('sort_ascending', False)
                ranking_df_sorted = ranking_df.sort_values(by=selected_index, ascending=ascending_sort, na_position='last').reset_index(drop=True)

                st.dataframe(
                    ranking_df_sorted.style.format({selected_index: "{:.3f}"}) # Format the index value
                                          .bar(subset=[selected_index], color='lightcoral' if ascending_sort else 'lightgreen', align='mid'), # Add data bars
                    use_container_width=True
                    )

                # Download Button for Ranking
                csv_rank = ranking_df_sorted.to_csv(index=False).encode('utf-8')
                st.download_button(
                   label=f"📥 دانلود جدول رتبه‌بندی ({selected_index})", data=csv_rank,
                   file_name=f'ranking_{selected_index}_{selected_day}.csv', mime='text/csv', key='dl_rank'
                 )
            else:
                st.warning(f"اطلاعاتی برای رتبه‌بندی مزارع با فیلتر '{selected_day}' و شاخص '{selected_index}' یافت نشد.", icon="📊")
        st.divider()


    # --- Tab 3: Weekly Comparison ---
    with tab3:
        st.subheader(f"📉 مقایسه هفتگی: مزارع با کاهش شاخص ({INDEX_DEFINITIONS[selected_index]['name_fa']})")
        st.caption(f"مقایسه مقادیر میانگین شاخص بین دوره جاری و دوره مشابه هفته قبل برای مزارع با روز هفته '{selected_day}'.")
        st.markdown("فقط مزارعی نمایش داده می‌شوند که مقدار شاخص آن‌ها در هفته جاری نسبت به هفته قبل **کاهش** داشته است.")
        st.divider()

        # Use the filtered_df which respects the day filter
        if filtered_df.empty:
             st.warning(f"هیچ مزرعه‌ای برای روز هفته '{selected_day}' جهت مقایسه یافت نشد.", icon="⚠️")
        else:
            with st.spinner(f"در حال محاسبه و مقایسه داده‌های هفتگی '{selected_index}'..."):
                # Pass the day-filtered json for comparison relevant to the selected day
                comparison_df_decreased = get_weekly_comparison(filtered_df.to_json(), start_date, end_date, selected_index, selected_sensor)

            if not comparison_df_decreased.empty:
                st.markdown("##### مزارع با کاهش شاخص:")
                # Display table with relevant columns, formatted nicely
                display_cols = ['مزرعه', f'{index_name}_prev', f'{index_name}_curr', 'تغییر', 'درصد_تغییر']
                st.dataframe(
                    comparison_df_decreased[display_cols].style.format({
                        f'{index_name}_prev': "{:.3f}", f'{index_name}_curr': "{:.3f}",
                        'تغییر': "{:+.3f}", 'درصد_تغییر': "{:+.1f}%" # Add sign to change
                    }).applymap(lambda x: 'color: red' if x < 0 else ('color: black' if x==0 else 'color: green'), subset=['تغییر','درصد_تغییر']), # Color changes
                    use_container_width=True
                )
                st.divider()

                st.markdown("##### نمودار مقایسه‌ای:")
                # Create grouped bar chart for visual comparison
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Bar(
                    x=comparison_df_decreased['مزرعه'], y=comparison_df_decreased[f'{index_name}_prev'],
                    name='هفته قبل', marker_color='dodgerblue', text=comparison_df_decreased[f'{index_name}_prev'].round(3), textposition='auto'
                ))
                fig_comp.add_trace(go.Bar(
                    x=comparison_df_decreased['مزرعه'], y=comparison_df_decreased[f'{index_name}_curr'],
                    name='هفته جاری', marker_color='lightcoral', text=comparison_df_decreased[f'{index_name}_curr'].round(3), textposition='auto'
                ))

                fig_comp.update_layout(
                    barmode='group', title=f'مقایسه شاخص {selected_index} (مزارع با کاهش)',
                    xaxis_title='مزرعه', yaxis_title=f'مقدار {selected_index}', legend_title='دوره زمانی',
                    xaxis={'categoryorder':'total descending'}, # Order bars if needed
                    hovermode="x unified", title_x=0.5
                )
                st.plotly_chart(fig_comp, use_container_width=True)
                st.divider()

                # Download Button for Comparison Data
                csv_comp = comparison_df_decreased.to_csv(index=False).encode('utf-8')
                st.download_button(
                   label=f"📥 دانلود داده‌های مقایسه ({selected_index})", data=csv_comp,
                   file_name=f'comparison_decrease_{selected_index}_{selected_day}.csv', mime='text/csv', key='dl_comp'
                 )

            else:
                st.success(f"✅ هیچ مزرعه‌ای کاهش قابل توجهی در شاخص '{selected_index}' بین دو هفته اخیر نشان نداد.")

else:
    st.error("اتصال به Google Earth Engine برقرار نشد. لطفاً پیش‌نیازها و خطاهای احتمالی را بررسی کنید.", icon="🚨")