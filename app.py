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
        # Keep rows with missing coordinates for now, handle in functions needing geometry
        # df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'], inplace=True)
        df['مساحت داشت'] = pd.to_numeric(df['مساحت داشت'], errors='coerce')
        df['مزرعه'] = df['مزرعه'].str.strip()
        for col in ['کانال', 'اداره', 'واریته', 'سن ', 'روزهای هفته']:
             if col in df.columns:
                # Convert to string first to handle mixed types before fillna
                df[col] = df[col].astype(str).fillna('نامشخص')
        # Ensure coordinates_missing is integer
        if 'coordinates_missing' in df.columns:
             df['coordinates_missing'] = pd.to_numeric(df['coordinates_missing'], errors='coerce').fillna(1).astype(int)

        print(f"Data loaded successfully. Shape: {df.shape}")
        return df
    except FileNotFoundError:
        st.error(f"خطا: فایل CSV در مسیر '{csv_path}' یافت نشد.")
        st.stop()
    except Exception as e:
        st.error(f"خطا در بارگذاری یا پردازش فایل CSV: {e}")
        st.stop()

# --- GEE Image Processing Functions ---

# Define common band names (used AFTER processing)
COMMON_BAND_NAMES = ['Blue', 'Green', 'Red', 'RedEdge1', 'NIR', 'SWIR1', 'SWIR2']

# --- Masking Functions ---
def mask_s2_clouds(image):
    img_ee = ee.Image(image) # Cast to image
    qa = img_ee.select('QA60')
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
             qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    data_bands = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12']
    return img_ee.select(data_bands).updateMask(mask).divide(10000.0)\
        .copyProperties(img_ee, ["system:time_start"])

def mask_landsat_clouds(image):
    img_ee = ee.Image(image) # Cast to image
    qa = img_ee.select('QA_PIXEL')
    cloud_shadow_bit = 1 << 3
    snow_bit = 1 << 4
    cloud_bit = 1 << 5
    mask = qa.bitwiseAnd(cloud_shadow_bit).eq(0)\
             .And(qa.bitwiseAnd(snow_bit).eq(0))\
             .And(qa.bitwiseAnd(cloud_bit).eq(0))
    sr_bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']
    scaled_bands = img_ee.select(sr_bands).multiply(0.0000275).add(-0.2)
    return scaled_bands.updateMask(mask)\
        .copyProperties(img_ee, ["system:time_start"])


# --- Index Calculation Functions ---
# (Ensure they return the calculated index band correctly named)
def calculate_ndvi(image):
    img_ee = ee.Image(image)
    ndvi = img_ee.normalizedDifference(['NIR', 'Red'])
    return ndvi.rename('NDVI')

def calculate_evi(image):
    img_ee = ee.Image(image)
    evi = img_ee.expression(
        '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
            'NIR': img_ee.select('NIR'), 'RED': img_ee.select('Red'), 'BLUE': img_ee.select('Blue')
        })
    return evi.rename('EVI')

def calculate_ndmi(image):
    img_ee = ee.Image(image)
    ndmi = img_ee.normalizedDifference(['NIR', 'SWIR1'])
    return ndmi.rename('NDMI')

def calculate_msi(image):
    img_ee = ee.Image(image)
    msi = img_ee.expression('SWIR1 / NIR', { 'SWIR1': img_ee.select('SWIR1'), 'NIR': img_ee.select('NIR') })
    return msi.rename('MSI')

def calculate_lai_simple(image):
    img_ee = ee.Image(image)
    try:
        evi = img_ee.expression('2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
                                {'NIR': img_ee.select('NIR'), 'RED': img_ee.select('Red'), 'BLUE': img_ee.select('Blue')})
        lai = evi.multiply(3.5).add(0.1)
    except Exception:
        # Warning is helpful, but avoid stopping execution if possible
        # st.warning("EVI failed for LAI, using NDVI.", icon="⚠️")
        ndvi = img_ee.normalizedDifference(['NIR', 'Red'])
        lai = ndvi.multiply(5.0).add(0.1)
    return lai.clamp(0, 8).rename('LAI')

def calculate_biomass_simple(image):
    img_ee = ee.Image(image)
    lai_image = calculate_lai_simple(img_ee) # Returns image named 'LAI'
    lai = lai_image.select('LAI')
    a = 1.5; b = 0.2 # Placeholder coefficients
    biomass = lai.multiply(a).add(b)
    return biomass.clamp(0, 50).rename('Biomass')

def calculate_chlorophyll_mcari(image):
    img_ee = ee.Image(image)
    try:
        img_ee.select('RedEdge1') # Check if band exists
        mcari = img_ee.expression('((RE1 - RED) - 0.2 * (RE1 - GREEN)) * (RE1 / RED)',
                                  {'RE1': img_ee.select('RedEdge1'), 'RED': img_ee.select('Red'), 'GREEN': img_ee.select('Green')})
        return mcari.rename('Chlorophyll')
    except ee.EEException:
         # st.warning("MCARI requires S2 Red Edge. Using NDVI as Chlorophyll proxy.", icon="⚠️")
         ndvi = img_ee.normalizedDifference(['NIR', 'Red'])
         return ndvi.rename('Chlorophyll')

def calculate_et_placeholder(image):
    # st.warning("Using NDMI as proxy for ET status.", icon="⚠️")
    img_ee = ee.Image(image)
    ndmi = img_ee.normalizedDifference(['NIR', 'SWIR1'])
    return ndmi.rename('ET_proxy')

# --- Index Definitions Dictionary (with descriptions) ---
INDEX_DEFINITIONS = {
    'NDVI': {
        'func': calculate_ndvi,
        'vis': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
        'name_fa': "شاخص نرمال‌شده تفاوت پوشش گیاهی",
        'desc_fa': """
        **NDVI (Normalized Difference Vegetation Index)** رایج‌ترین شاخص برای سنجش سلامت و تراکم پوشش گیاهی است.
        - **محاسبه:** (NIR - Red) / (NIR + Red)
        - **محدوده:** -۱ تا +۱
        - **تفسیر:**
            - مقادیر نزدیک به +۱: پوشش گیاهی بسیار متراکم و سالم.
            - مقادیر متوسط (۰.۲ تا ۰.۵): پوشش گیاهی پراکنده یا تحت تنش.
            - مقادیر نزدیک به صفر یا منفی: خاک، آب، ابر، یا پوشش گیاهی بسیار کم.
        """,
        'sort_ascending': False # Higher is better
    },
    'EVI': {
        'func': calculate_evi,
        'vis': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
        'name_fa': "شاخص بهبودیافته پوشش گیاهی",
        'desc_fa': """
        **EVI (Enhanced Vegetation Index)** مشابه NDVI است اما حساسیت کمتری به اثرات اتمسفر و پس‌زمینه خاک دارد و در مناطق با تراکم گیاهی بالا بهتر عمل می‌کند.
        - **محاسبه:** 2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)
        - **محدوده:** معمولاً ۰ تا ۱ (می‌تواند کمی بیشتر شود).
        - **تفسیر:** مقادیر بالاتر نشان‌دهنده پوشش گیاهی سالم‌تر و متراکم‌تر است.
        """,
        'sort_ascending': False
    },
    'NDMI': {
        'func': calculate_ndmi,
        'vis': {'min': -0.5, 'max': 0.8, 'palette': ['brown', 'white', 'blue']},
        'name_fa': "شاخص نرمال‌شده تفاوت رطوبت",
        'desc_fa': """
        **NDMI (Normalized Difference Moisture Index)** میزان آب موجود در برگ‌های گیاهان را نشان می‌دهد.
        - **محاسبه:** (NIR - SWIR1) / (NIR + SWIR1)
        - **محدوده:** -۱ تا +۱
        - **تفسیر:**
            - مقادیر بالا: محتوای آب بالا در پوشش گیاهی.
            - مقادیر پایین: پوشش گیاهی خشک یا تحت تنش آبی.
        """,
        'sort_ascending': False
    },
    'MSI': {
        'func': calculate_msi,
        'vis': {'min': 0.4, 'max': 2.5, 'palette': ['darkgreen', 'yellow', 'red']}, # Lower MSI is less stressed
        'name_fa': "شاخص تنش رطوبتی",
        'desc_fa': """
        **MSI (Moisture Stress Index)** نیز به رطوبت گیاه حساس است، اما برخلاف NDMI، مقادیر *بالاتر* آن معمولاً نشان‌دهنده تنش رطوبتی *بیشتر* است.
        - **محاسبه:** SWIR1 / NIR
        - **محدوده:** معمولاً بیشتر از ۰.۴.
        - **تفسیر:**
            - مقادیر پایین‌تر: تنش رطوبتی کمتر.
            - مقادیر بالاتر: تنش رطوبتی بیشتر.
        """,
        'sort_ascending': True # Higher is worse
    },
    'LAI': {
        'func': calculate_lai_simple,
        'vis': {'min': 0, 'max': 8, 'palette': ['white', 'lightgreen', 'darkgreen']},
        'name_fa': "شاخص سطح برگ (تخمینی)",
        'desc_fa': """
        **LAI (Leaf Area Index)** نسبت کل مساحت برگ به واحد سطح زمین است (m²/m²). این یک تخمین بر اساس سایر شاخص‌ها (مانند EVI یا NDVI) است و نیاز به کالیبراسیون محلی دارد.
        - **محاسبه:** تقریبی، مثلاً a * EVI + b
        - **محدوده:** معمولاً ۰ تا ۸ یا بیشتر.
        - **تفسیر:** مقادیر بالاتر نشان‌دهنده پوشش گیاهی متراکم‌تر با سطح برگ بیشتر است.
        """,
        'sort_ascending': False
    },
    'Biomass': {
        'func': calculate_biomass_simple,
        'vis': {'min': 0, 'max': 30, 'palette': ['beige', 'yellow', 'brown']},
        'name_fa': "زیست‌توده (تخمینی)",
        'desc_fa': """
        **Biomass** وزن ماده خشک گیاهی در واحد سطح (مثلاً تن بر هکتار) است. این نیز یک تخمین بر اساس LAI یا سایر شاخص‌هاست و نیاز به کالیبراسیون دقیق دارد.
        - **محاسبه:** تقریبی، مثلاً a * LAI + b
        - **محدوده:** وابسته به نوع گیاه و کالیبراسیون (مثلاً ۰ تا ۵۰+ تن/هکتار).
        - **تفسیر:** مقادیر بالاتر نشان‌دهنده زیست‌توده بیشتر است.
        """,
        'sort_ascending': False
    },
    'Chlorophyll': {
        'func': calculate_chlorophyll_mcari,
        'vis': {'min': 0, 'max': 1, 'palette': ['yellow', 'lightgreen', 'darkgreen']},
        'name_fa': "شاخص کلروفیل (MCARI/NDVI)",
        'desc_fa': """
        **Chlorophyll Index** به غلظت کلروفیل در برگ‌ها حساس است. از شاخص‌هایی مانند MCARI (که به باند RedEdge نیاز دارد) یا تقریبی با NDVI (در صورت عدم دسترسی به RedEdge) استفاده می‌شود.
        - **محاسبه:** MCARI یا NDVI
        - **محدوده:** متغیر، اما معمولاً مقادیر بالاتر بهتر است.
        - **تفسیر:** مقادیر بالاتر معمولاً نشان‌دهنده کلروفیل بیشتر و سلامت بهتر گیاه است.
        """,
        'sort_ascending': False
    },
    'ET_proxy': {
        'func': calculate_et_placeholder,
        'vis': {'min': -0.5, 'max': 0.8, 'palette': ['brown', 'white', 'blue']},
        'name_fa': "پراکسی تبخیر-تعرق (بر اساس NDMI)",
        'desc_fa': """
        **ET Proxy** یک شاخص جایگزین برای نشان دادن وضعیت رطوبتی مرتبط با تبخیر و تعرق (ET) است. در اینجا از NDMI به عنوان پراکسی استفاده می‌شود. محاسبه دقیق ET پیچیده است.
        - **محاسبه:** NDMI
        - **محدوده:** -۱ تا +۱
        - **تفسیر:** مقادیر بالاتر NDMI (رطوبت بیشتر) می‌تواند پتانسیل ET بالاتری را نشان دهد (اگر آب عامل محدودکننده نباشد). مقادیر پایین نشان‌دهنده تنش آبی و احتمالاً ET کمتر است.
        """,
        'sort_ascending': False
    }
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

    # Basic Date Range Check
    if start_date > end_date:
         st.error("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد.")
         return None

    collection = collection.filterDate(start_date_str, end_date_str)
    if geometry:
        # Add a check for valid geometry
        try:
            if geometry.type().getInfo() not in ['Point', 'Polygon', 'Rectangle', 'MultiPolygon']:
                 st.warning(f"نوع هندسی نامعتبر برای فیلتر: {geometry.type().getInfo()}", icon="⚠️")
                 geometry = None # Don't filter by invalid geometry
            else:
                 collection = collection.filterBounds(geometry)
        except Exception as e:
            st.error(f"خطا در فیلتر کردن مرزهای هندسی: {e}")
            return None


    initial_count = collection.size().getInfo()
    if initial_count == 0:
        # Don't show warning if the reason might be the geometry filter failing silently
        if geometry is not None:
             st.warning(f"هیچ تصویری در بازه زمانی و منطقه انتخابی ({sensor}) قبل از ماسک ابر یافت نشد.", icon="⏳")
        return None

    def process_image(image_element):
        image = ee.Image(image_element)
        img_selected_orig = image.select(bands_to_select_orig)
        img_processed = mask_func(img_selected_orig)
        img_processed_safe = ee.Image(img_processed) # Cast for safety
        # Handle potential mismatch in band counts after masking if needed
        expected_band_count = len(bands_to_rename_to)
        actual_bands = img_processed_safe.bandNames()
        # A more robust way might involve checking actual_bands length, but rename handles extra/missing okay
        img_renamed = img_processed_safe.rename(bands_to_rename_to)
        return img_renamed.copyProperties(image, ["system:time_start"])

    processed_collection = collection.map(process_image)

    count = processed_collection.size().getInfo()
    if count == 0:
        st.warning(f"هیچ تصویر بدون ابری در بازه زمانی و منطقه انتخابی ({sensor}) یافت نشد.", icon="☁️")
        return None

    try:
        first_image = processed_collection.first()
        if first_image is None: return None # Empty after processing
        final_bands = ee.Image(first_image).bandNames().getInfo()
        print(f"Final bands in processed collection: {final_bands}")
    except ee.EEException as e:
        st.error(f"خطا در بررسی باندهای پردازش شده: {e}")
        return None

    return processed_collection

# --- Function to calculate a single index for a collection ---
def calculate_single_index(collection, index_name):
    """Calculates a single index for the collection."""
    if collection is None: return None
    index_detail = INDEX_DEFINITIONS.get(index_name)
    if not index_detail:
        st.error(f"تعریف شاخص '{index_name}' یافت نشد.")
        return None

    index_func = index_detail['func']
    try:
        # Map the function - it should return an image with the index band
        indexed_collection = collection.map(index_func)
        # Check if the index band was actually created
        first_img = indexed_collection.first()
        if first_img and index_name in ee.Image(first_img).bandNames().getInfo():
             return indexed_collection.select(index_name) # Return collection with only the index band
        else:
             st.warning(f"باند شاخص '{index_name}' پس از محاسبه ایجاد نشد.", icon="⚠️")
             return None
    except Exception as e:
        st.error(f"خطا در محاسبه شاخص '{index_name}': {e}")
        return None

# --- get_timeseries_for_farm ---
@st.cache_data(ttl=3600)
def get_timeseries_for_farm(_farm_geom_geojson, start_date, end_date, index_name, sensor):
    farm_geom = ee.Geometry(json.loads(_farm_geom_geojson))
    base_collection = get_image_collection(start_date, end_date, farm_geom, sensor)
    if base_collection is None: return pd.DataFrame(columns=['Date', index_name])

    indexed_collection = calculate_single_index(base_collection, index_name)
    if indexed_collection is None: return pd.DataFrame(columns=['Date', index_name])

    def extract_value(image):
        img_ee = ee.Image(image) # Ensure image type
        stats = img_ee.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=farm_geom, scale=30, maxPixels=1e9, tileScale=4
        )
        val = stats.get(index_name)
        time_ms = img_ee.get('system:time_start') # Get time from the image object
        return ee.Feature(None, {'time': time_ms, index_name: ee.Algorithms.If(val, val, -9999)})

    try:
        ts_info = indexed_collection.map(extract_value).getInfo()
    except ee.EEException as e:
        st.error(f"خطا در استخراج سری زمانی (reduceRegion): {e}")
        return pd.DataFrame(columns=['Date', index_name])

    data = []
    if 'features' in ts_info:
        for feature in ts_info['features']:
            props = feature.get('properties', {})
            value = props.get(index_name)
            time_ms = props.get('time')
            if value not in [None, -9999] and time_ms is not None:
                try:
                    dt = datetime.datetime.fromtimestamp(time_ms / 1000.0)
                    data.append([dt, value])
                except (TypeError, ValueError) as time_e:
                     st.warning(f"نادیده گرفتن زمان نامعتبر ({time_ms}): {time_e}", icon="⚠️")
    else:
        st.warning("کلید 'features' در نتایج سری زمانی یافت نشد.")

    if not data: return pd.DataFrame(columns=['Date', index_name])
    ts_df = pd.DataFrame(data, columns=['Date', index_name]).sort_values(by='Date')
    return ts_df

# --- Renamed Function for getting median index over a period for multiple farms ---
@st.cache_data(ttl=3600)
def get_median_index_for_period(_farms_df_json, start_date, end_date, index_name, sensor):
    """Gets the median index value over a period for multiple farms."""
    farms_df = pd.read_json(_farms_df_json)
    # Filter out farms with missing coordinates *before* creating features
    farms_df_valid_coords = farms_df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی']).copy()

    if farms_df_valid_coords.empty:
         st.warning("هیچ مزرعه‌ای با مختصات معتبر برای تحلیل یافت نشد.", icon="📍")
         return pd.DataFrame(columns=['مزرعه', index_name])

    features = []
    for idx, row in farms_df_valid_coords.iterrows():
        try:
             geom = ee.Geometry.Point([row['طول جغرافیایی'], row['عرض جغرافیایی']])
             buffered_geom = geom.buffer(50) # Buffer for reduction
             feature = ee.Feature(buffered_geom, {'farm_id': row['مزرعه']})
             features.append(feature)
        except Exception as e:
             st.warning(f"خطا در ایجاد هندسه برای مزرعه {row.get('مزرعه', 'Unknown')}: {e}", icon="⚠️")

    if not features:
         st.warning("هیچ هندسه معتبری برای مزارع ایجاد نشد.", icon="⚠️")
         return pd.DataFrame(columns=['مزرعه', index_name])

    farm_fc = ee.FeatureCollection(features)

    base_collection = get_image_collection(start_date, end_date, farm_fc.geometry(), sensor)
    if base_collection is None:
        # Warning already shown in get_image_collection
        return pd.DataFrame(columns=['مزرعه', index_name])

    indexed_collection = calculate_single_index(base_collection, index_name)
    if indexed_collection is None:
        return pd.DataFrame(columns=['مزرعه', index_name])

    # Create a median composite over the period
    median_image = indexed_collection.median() # Already selected index band

    # Reduce the composite image over the farm geometries
    try:
        farm_values = median_image.reduceRegions(
            collection=farm_fc, reducer=ee.Reducer.mean(), scale=30, tileScale=8
        ).getInfo()
    except ee.EEException as e:
        st.error(f"خطا در محاسبه مقادیر مزارع (reduceRegions): {e}")
        return pd.DataFrame(columns=['مزرعه', index_name])

    # Extract results
    results_data = []
    if 'features' in farm_values:
        for feature in farm_values['features']:
            props = feature.get('properties', {})
            farm_id = props.get('farm_id')
            value = props.get('mean') # Default output name is 'mean'
            if farm_id is not None and value is not None:
                results_data.append({'مزرعه': farm_id, index_name: value})
    else:
        st.warning("کلید 'features' در نتایج reduceRegions یافت نشد.")


    if not results_data:
         st.warning("هیچ داده‌ای پس از پردازش GEE برای مزارع استخراج نشد.", icon="📊")
         return pd.DataFrame(columns=['مزرعه', index_name])

    results_df = pd.DataFrame(results_data)
    return results_df

# --- Function for Weekly Comparison ---
@st.cache_data(ttl=3600)
def get_weekly_comparison(_filtered_df_json, start_date, end_date, index_name, sensor):
    """Compares the index values from the current week to the previous week."""
    # Define current and previous week date ranges
    current_start = start_date
    current_end = end_date
    prev_end = current_start - timedelta(days=1)
    prev_start = current_start - timedelta(days=7) # Assuming 7-day week

    st.write(f"دوره فعلی: {current_start} تا {current_end}")
    st.write(f"دوره قبلی: {prev_start} تا {prev_end}")


    # Get data for the current period
    df_current = get_median_index_for_period(_filtered_df_json, current_start, current_end, index_name, sensor)
    if df_current.empty:
        st.warning(f"داده‌ای برای دوره فعلی ({current_start} تا {current_end}) جهت مقایسه یافت نشد.", icon="⚠️")
        return pd.DataFrame()

    # Get data for the previous period
    df_previous = get_median_index_for_period(_filtered_df_json, prev_start, prev_end, index_name, sensor)
    if df_previous.empty:
        st.warning(f"داده‌ای برای دوره قبلی ({prev_start} تا {prev_end}) جهت مقایسه یافت نشد.", icon="⚠️")
        # Return current data only if previous is missing? Or empty? Let's return empty for comparison.
        return pd.DataFrame()

    # Merge the dataframes
    df_comparison = pd.merge(
        df_previous.rename(columns={index_name: f'{index_name}_prev'}),
        df_current.rename(columns={index_name: f'{index_name}_curr'}),
        on='مزرعه',
        how='inner' # Only compare farms present in both periods
    )

    if df_comparison.empty:
        st.info("هیچ مزرعه مشترکی بین دو دوره زمانی برای مقایسه یافت نشد.")
        return pd.DataFrame()

    # Calculate difference and percentage change
    df_comparison['تغییر'] = df_comparison[f'{index_name}_curr'] - df_comparison[f'{index_name}_prev']
    # Calculate percentage change carefully, handle division by zero or near-zero
    df_comparison['درصد_تغییر'] = np.where(
        np.abs(df_comparison[f'{index_name}_prev']) > 1e-6, # Avoid division by zero/small numbers
       ((df_comparison['تغییر'] / df_comparison[f'{index_name}_prev']) * 100),
        np.nan # Assign NaN if previous value is too small
    )


    # Filter for farms with decrease
    df_decreased = df_comparison[df_comparison['تغییر'] < 0].copy()

    # Sort by percentage change (most negative first)
    df_decreased = df_decreased.sort_values(by='درصد_تغییر', ascending=True)

    return df_decreased


# --- Streamlit App Layout ---
st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

# Initialize GEE
if initialize_gee():
    # Load data
    farm_data_df = load_data(CSV_FILE_PATH)

    # --- Sidebar ---
    st.sidebar.header("تنظیمات نمایش")
    default_end_date = datetime.date.today()
    default_start_date = default_end_date - timedelta(days=6) # Default to last 7 days (inclusive)
    start_date = st.sidebar.date_input("تاریخ شروع هفته جاری", value=default_start_date, max_value=default_end_date)
    end_date = st.sidebar.date_input("تاریخ پایان هفته جاری", value=default_end_date, min_value=start_date, max_value=default_end_date)

    # --- Display Index Information ---
    st.sidebar.header("راهنمای شاخص‌ها")
    selected_index_info = st.sidebar.selectbox(
        "انتخاب شاخص برای مشاهده توضیحات:",
        options=list(INDEX_DEFINITIONS.keys()),
        format_func=lambda x: INDEX_DEFINITIONS[x]['name_fa'] # Show Persian name in dropdown
    )
    if selected_index_info:
        with st.sidebar.expander(f"توضیحات شاخص {INDEX_DEFINITIONS[selected_index_info]['name_fa']}", expanded=False):
            st.markdown(INDEX_DEFINITIONS[selected_index_info]['desc_fa'], unsafe_allow_html=True)


    # --- Filters for Map/Ranking/Comparison ---
    st.sidebar.header("فیلترهای داده")
    days_list = ["همه روزها"] + sorted(farm_data_df['روزهای هفته'].unique().tolist())
    selected_day = st.sidebar.selectbox("فیلتر بر اساس روز هفته آبیاری", options=days_list)

    # Filter DataFrame based on selected day *before* farm selection
    if selected_day == "همه روزها":
        filtered_df = farm_data_df.copy()
    else:
        filtered_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day].copy()

    # Allow selecting index for analysis
    available_indices = list(INDEX_DEFINITIONS.keys())
    selected_index = st.sidebar.selectbox("انتخاب شاخص برای تحلیل", options=available_indices)

    # Sensor Selection
    selected_sensor = st.sidebar.radio("انتخاب سنسور ماهواره", ('Sentinel-2', 'Landsat'), index=0, key='sensor_select')

    # Farm Selection (applied AFTER day filter)
    farm_list = ["همه مزارع"] + sorted(filtered_df['مزرعه'].unique().tolist())
    selected_farm = st.sidebar.selectbox("انتخاب مزرعه خاص (یا همه)", options=farm_list)


    # --- Main Panel ---
    tab1, tab2, tab3 = st.tabs(["نقشه و جزئیات مزرعه", "رتبه‌بندی مزارع", "مقایسه هفتگی (کاهش)"])

    # --- Tab 1: Map and Farm Details ---
    with tab1:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"نقشه وضعیت شاخص: {INDEX_DEFINITIONS[selected_index]['name_fa']}")
            map_placeholder = st.empty()
            m = geemap.Map(center=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False)
            m.add_basemap('HYBRID')

            vis_params = INDEX_DEFINITIONS.get(selected_index, {}).get('vis')
            if not vis_params: vis_params = {'min': 0, 'max': 1, 'palette': ['white', 'gray']}

            # Determine display geometry
            display_geom = None
            target_object_for_map = None
            farm_info_for_popup = None
            # Use the filtered_df which respects the day filter
            display_df = filtered_df.copy() # Work with the day-filtered data

            if selected_farm == "همه مزارع":
                display_df_valid = display_df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
                if not display_df_valid.empty:
                    min_lon, min_lat = display_df_valid['طول جغرافیایی'].min(), display_df_valid['عرض جغرافیایی'].min()
                    max_lon, max_lat = display_df_valid['طول جغرافیایی'].max(), display_df_valid['عرض جغرافیایی'].max()
                    display_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
                    target_object_for_map = display_geom
                else:
                    st.info("هیچ مزرعه‌ای با مختصات معتبر برای نمایش در این روز هفته یافت نشد.")
            else: # Single farm selected
                farm_info_rows = display_df[display_df['مزرعه'] == selected_farm]
                if not farm_info_rows.empty:
                    farm_info_for_popup = farm_info_rows.iloc[0]
                    farm_lat = farm_info_for_popup['عرض جغرافیایی']
                    farm_lon = farm_info_for_popup['طول جغرافیایی']
                    if pd.notna(farm_lat) and pd.notna(farm_lon):
                        farm_geom = ee.Geometry.Point([farm_lon, farm_lat])
                        display_geom = farm_geom.buffer(150)
                        target_object_for_map = farm_geom
                    else:
                        st.warning(f"مختصات نامعتبر برای مزرعه {selected_farm}.", icon="📍")
                        farm_info_for_popup = None
                else:
                    st.warning(f"اطلاعات مزرعه {selected_farm} برای روز هفته '{selected_day}' یافت نشد.", icon="⚠️")

            # Fetch data and display on map
            if display_geom:
                with st.spinner(f"در حال پردازش نقشه {selected_index}..."):
                    base_collection = get_image_collection(start_date, end_date, display_geom, selected_sensor)
                    if base_collection:
                        indexed_collection = calculate_single_index(base_collection, selected_index)
                        if indexed_collection:
                            median_image = indexed_collection.median()
                            layer_image = median_image.clip(display_geom) if selected_farm != "همه مزارع" else median_image
                            m.addLayer(layer_image, vis_params, f'{selected_index} (Median)')
                            try:
                                m.add_legend(title=f'{selected_index}', builtin_legend=None, palette=vis_params['palette'], min=vis_params['min'], max=vis_params['max'])
                            except Exception as legend_e: pass # Ignore legend errors for now

                            # Add download button for map layer
                            try:
                                thumb_url = median_image.getThumbURL({'region': display_geom.toGeoJson(), 'bands': selected_index, 'palette': vis_params['palette'], 'min': vis_params['min'], 'max': vis_params['max'], 'dimensions': 512})
                                response = requests.get(thumb_url)
                                if response.status_code == 200:
                                    st.sidebar.download_button(label=f"دانلود نقشه ({selected_index})", data=BytesIO(response.content), file_name=f"map_{selected_farm if selected_farm != 'همه مزارع' else 'all'}_{selected_index}.png", mime="image/png", key=f"dl_map_{selected_index}_{selected_farm}")
                            except Exception as thumb_e: pass # Ignore thumb errors silently for now

                        else: st.warning(f"محاسبه شاخص '{selected_index}' برای نقشه ممکن نبود.", icon="⚠️")
                    else: st.warning(f"تصویری برای پردازش نقشه یافت نشد.", icon="⏳")

                # Add markers
                if selected_farm == "همه مزارع":
                    df_to_mark = display_df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
                    for idx, row in df_to_mark.iterrows():
                        popup_html = f"<b>مزرعه:</b> {row['مزرعه']}<br><b>کانال:</b> {row['کانال']}<br><b>مساحت:</b> {row['مساحت داشت']:.2f}"
                        folium.Marker(location=[row['عرض جغرافیایی'], row['طول جغرافیایی']], popup=folium.Popup(popup_html, max_width=200), tooltip=f"{row['مزرعه']}", icon=folium.Icon(color='blue', icon='info-sign')).add_to(m)
                elif farm_info_for_popup is not None:
                    farm_info = farm_info_for_popup
                    popup_html = f"<b>مزرعه:</b> {farm_info['مزرعه']}<br><b>کانال:</b> {farm_info['کانال']}<br><b>اداره:</b> {farm_info['اداره']}<br><b>مساحت:</b> {farm_info['مساحت داشت']:.2f}<br><b>واریته:</b> {farm_info['واریته']}<br><b>سن:</b> {farm_info['سن ']}"
                    folium.Marker(location=[farm_info['عرض جغرافیایی'], farm_info['طول جغرافیایی']], popup=folium.Popup(popup_html, max_width=250), tooltip=f"{farm_info['مزرعه']}", icon=folium.Icon(color='red', icon='star')).add_to(m)

                # Center the map
                if target_object_for_map:
                    zoom_level = INITIAL_ZOOM + 2 if selected_farm != "همه مزارع" else INITIAL_ZOOM
                    try: m.center_object(target_object_for_map, zoom=zoom_level)
                    except: m.set_center(INITIAL_LON, INITIAL_LAT, INITIAL_ZOOM) # Fallback center

            # Render the map
            with map_placeholder: m.to_streamlit(height=500)

        # --- Column 2: Details / Timeseries ---
        with col2:
            if selected_farm != "همه مزارع":
                st.subheader(f"جزئیات مزرعه: {selected_farm}")
                if farm_info_for_popup is not None:
                    farm_info = farm_info_for_popup
                    st.metric("کانال", str(farm_info['کانال']))
                    st.metric("اداره", str(farm_info['اداره']))
                    st.metric("مساحت (هکتار)", f"{farm_info['مساحت داشت']:.2f}" if pd.notna(farm_info['مساحت داشت']) else "N/A")
                    st.metric("واریته", str(farm_info['واریته']))
                    st.metric("سن", str(farm_info['سن ']))
                    st.metric("روز آبیاری", str(farm_info['روزهای هفته']))

                    st.subheader(f"روند شاخص: {INDEX_DEFINITIONS[selected_index]['name_fa']}")
                    if pd.notna(farm_info['عرض جغرافیایی']) and pd.notna(farm_info['طول جغرافیایی']):
                        with st.spinner(f"در حال دریافت سری زمانی {selected_index}..."):
                            farm_geom = ee.Geometry.Point([farm_info['طول جغرافیایی'], farm_info['عرض جغرافیایی']])
                            ts_df = get_timeseries_for_farm(farm_geom.toGeoJsonString(), start_date, end_date, selected_index, selected_sensor)
                        if not ts_df.empty:
                            fig = px.line(ts_df, x='Date', y=selected_index, title=f"روند زمانی {selected_index}", markers=True)
                            fig.update_layout(xaxis_title="تاریخ", yaxis_title=selected_index)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info(f"داده‌ای برای نمایش نمودار روند زمانی {selected_index} یافت نشد.")
                    else:
                        st.warning("مختصات نامعتبر برای دریافت سری زمانی.", icon="📍")
                else:
                    st.info("اطلاعات این مزرعه برای روز هفته یا انتخاب فعلی موجود نیست.")
            else:
                st.info("برای مشاهده جزئیات و روند زمانی، یک مزرعه خاص را از نوار کناری انتخاب کنید.")


    # --- Tab 2: Ranking ---
    with tab2:
        st.subheader(f"رتبه‌بندی مزارع بر اساس شاخص: {INDEX_DEFINITIONS[selected_index]['name_fa']}")
        st.info(f"نمایش میانگین مقدار شاخص '{selected_index}' در بازه زمانی {start_date} تا {end_date} برای مزارع فعال در '{selected_day}'.")

        with st.spinner(f"در حال محاسبه رتبه‌بندی مزارع..."):
            # Use the day-filtered DataFrame for ranking
            ranking_df = get_median_index_for_period(filtered_df.to_json(), start_date, end_date, selected_index, sensor=selected_sensor)

        if not ranking_df.empty:
            # Determine sort order based on index definition
            ascending_sort = INDEX_DEFINITIONS[selected_index].get('sort_ascending', False)
            ranking_df_sorted = ranking_df.sort_values(by=selected_index, ascending=ascending_sort, na_position='last').reset_index(drop=True)

            if selected_index in ranking_df_sorted.columns:
                 st.dataframe(ranking_df_sorted.style.format({selected_index: "{:.3f}"}), use_container_width=True)
            else:
                 st.dataframe(ranking_df_sorted, use_container_width=True)

            csv = ranking_df_sorted.to_csv(index=False).encode('utf-8')
            st.download_button(
               label=f"دانلود جدول رتبه‌بندی ({selected_index})", data=csv,
               file_name=f'ranking_{selected_index}_{selected_day}.csv', mime='text/csv', key='dl_rank'
             )
        else:
            st.warning("اطلاعاتی برای رتبه‌بندی مزارع با فیلترهای انتخابی یافت نشد.", icon="📊")

    # --- Tab 3: Weekly Comparison ---
    with tab3:
        st.subheader(f"مقایسه هفتگی: مزارع با کاهش شاخص ({INDEX_DEFINITIONS[selected_index]['name_fa']})")
        st.markdown(f"مقایسه مقادیر میانگین شاخص **{selected_index}** بین دوره **{start_date} تا {end_date}** (هفته جاری) و دوره **{start_date - timedelta(days=7)} تا {start_date - timedelta(days=1)}** (هفته قبل).")
        st.info("فقط مزارعی نمایش داده می‌شوند که مقدار شاخص آن‌ها در هفته جاری نسبت به هفته قبل کاهش داشته است.")

        with st.spinner("در حال محاسبه و مقایسه داده‌های هفتگی..."):
            # Pass the day-filtered json for comparison relevant to the selected day
            comparison_df = get_weekly_comparison(filtered_df.to_json(), start_date, end_date, selected_index, selected_sensor)

        if not comparison_df.empty:
            st.markdown("##### مزارع با کاهش شاخص:")
            # Display table with relevant columns
            display_cols = ['مزرعه', f'{index_name}_prev', f'{index_name}_curr', 'تغییر', 'درصد_تغییر']
            st.dataframe(
                comparison_df[display_cols].style.format({
                    f'{index_name}_prev': "{:.3f}",
                    f'{index_name}_curr': "{:.3f}",
                    'تغییر': "{:.3f}",
                    'درصد_تغییر': "{:.1f}%"
                }),
                use_container_width=True
            )

            st.markdown("##### نمودار مقایسه‌ای:")
            # Create grouped bar chart
            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(
                x=comparison_df['مزرعه'],
                y=comparison_df[f'{index_name}_prev'],
                name='هفته قبل',
                marker_color='skyblue'
            ))
            fig_comp.add_trace(go.Bar(
                x=comparison_df['مزرعه'],
                y=comparison_df[f'{index_name}_curr'],
                name='هفته جاری',
                marker_color='salmon'
            ))

            fig_comp.update_layout(
                barmode='group',
                title=f'مقایسه شاخص {selected_index} (مزارع با کاهش)',
                xaxis_title='مزرعه',
                yaxis_title=f'مقدار {selected_index}',
                legend_title='دوره زمانی'
            )
            st.plotly_chart(fig_comp, use_container_width=True)

            # Download comparison data
            csv_comp = comparison_df.to_csv(index=False).encode('utf-8')
            st.download_button(
               label=f"دانلود داده‌های مقایسه ({selected_index})", data=csv_comp,
               file_name=f'comparison_decrease_{selected_index}_{selected_day}.csv', mime='text/csv', key='dl_comp'
             )

        else:
            st.success("هیچ مزرعه‌ای کاهش قابل توجهی در این شاخص بین دو هفته اخیر نشان نداد.")

else:
    st.warning("لطفا صبر کنید تا اتصال به Google Earth Engine برقرار شود یا خطاهای نمایش داده شده را بررسی کنید.", icon="⏳")

# Footer
st.sidebar.markdown("---")
st.sidebar.info("راهنما: از منوها برای انتخاب بازه زمانی، روز هفته، مزرعه و شاخص استفاده کنید.")