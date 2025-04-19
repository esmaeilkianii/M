# -*- coding: utf-8 -*-
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

# --- File Paths (Relative to the script location) ---
CSV_FILE_PATH = 'output (1).csv'
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'

# --- GEE Authentication ---
@st.cache_resource
def initialize_gee():
    """Initializes Google Earth Engine using the Service Account."""
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"خطا: فایل Service Account '{SERVICE_ACCOUNT_FILE}' یافت نشد.")
            st.stop()
        credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Initialized Successfully.")
        return True
    except ee.EEException as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.stop()
    except Exception as e:
        st.error(f"خطای غیرمنتظره هنگام اتصال به GEE: {e}")
        st.stop()

# --- Data Loading ---
@st.cache_data
def load_data(csv_path):
    """Loads and preprocesses farm data from the CSV file."""
    try:
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()
        print(f"Original columns: {df.columns.tolist()}")

        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        df['مساحت داشت'] = pd.to_numeric(df['مساحت داشت'], errors='coerce')
        df['مزرعه'] = df['مزرعه'].str.strip()

        # Ensure 'سن' column exists before accessing (handle potential CSV variations)
        if 'سن' not in df.columns:
            if 'سن ' in df.columns: # Check for the version with space
                 df.rename(columns={'سن ': 'سن'}, inplace=True) # Rename it
            else:
                 print("Warning: 'سن' column not found. Adding default.")
                 df['سن'] = 'نامشخص' # Add default if completely missing

        for col in ['کانال', 'اداره', 'واریته', 'سن', 'روزهای هفته']:
             if col in df.columns:
                df[col] = df[col].astype(str).fillna('نامشخص')
             else:
                 print(f"Warning: Column '{col}' not found.")

        if 'coordinates_missing' in df.columns:
             df['coordinates_missing'] = pd.to_numeric(df['coordinates_missing'], errors='coerce').fillna(1).astype(int)
        else:
             print("Warning: Column 'coordinates_missing' not found.")
             df['coordinates_missing'] = df.apply(lambda row: 1 if pd.isna(row['طول جغرافیایی']) or pd.isna(row['عرض جغرافیایی']) else 0, axis=1)


        print(f"Data loaded. Shape: {df.shape}. Cleaned columns: {df.columns.tolist()}")
        return df
    except FileNotFoundError:
        st.error(f"خطا: فایل CSV '{csv_path}' یافت نشد.")
        st.stop()
    except Exception as e:
        st.error(f"خطا در بارگذاری CSV: {e}")
        st.exception(e)
        st.stop()

# --- GEE Image Processing Functions ---
COMMON_BAND_NAMES = ['Blue', 'Green', 'Red', 'RedEdge1', 'NIR', 'SWIR1', 'SWIR2']

def mask_s2_clouds(image):
    img_ee = ee.Image(image)
    qa = img_ee.select('QA60')
    cloud_mask = 1 << 10
    cirrus_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_mask).eq(0).And(qa.bitwiseAnd(cirrus_mask).eq(0))
    data_bands = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12']
    return img_ee.select(data_bands).updateMask(mask).divide(10000.0)\
        .copyProperties(img_ee, ["system:time_start"])

def mask_landsat_clouds(image):
    img_ee = ee.Image(image)
    qa = img_ee.select('QA_PIXEL')
    cloud_shadow_mask = 1 << 3; snow_mask = 1 << 4; cloud_mask = 1 << 5
    mask = qa.bitwiseAnd(cloud_shadow_mask).eq(0).And(qa.bitwiseAnd(snow_mask).eq(0)).And(qa.bitwiseAnd(cloud_mask).eq(0))
    sr_bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']
    scale = 0.0000275; offset = -0.2
    scaled_bands = img_ee.select(sr_bands).multiply(scale).add(offset)
    return scaled_bands.updateMask(mask).copyProperties(img_ee, ["system:time_start"])

# --- Index Calculation Functions ---
# (Defined as before - calculate_ndvi, calculate_evi, etc.)
def calculate_ndvi(image):
    img_ee = ee.Image(image)
    return img_ee.normalizedDifference(['NIR', 'Red']).rename('NDVI')

def calculate_evi(image):
    img_ee = ee.Image(image)
    try:
        img_ee.select(['NIR', 'Red', 'Blue'])
        evi = img_ee.expression('2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
                                {'NIR': img_ee.select('NIR'), 'RED': img_ee.select('Red'), 'BLUE': img_ee.select('Blue')})
        return evi.rename('EVI')
    except: return ee.Image().rename('EVI')

def calculate_ndmi(image):
    img_ee = ee.Image(image)
    return img_ee.normalizedDifference(['NIR', 'SWIR1']).rename('NDMI')

def calculate_msi(image):
    img_ee = ee.Image(image)
    return img_ee.expression('SWIR1 / NIR', {'SWIR1': img_ee.select('SWIR1'), 'NIR': img_ee.select('NIR')}).rename('MSI')

def calculate_lai_simple(image):
    img_ee = ee.Image(image)
    lai = None
    try:
        evi_img = calculate_evi(img_ee)
        if 'EVI' in evi_img.bandNames().getInfo(): lai = evi_img.select('EVI').multiply(3.5).add(0.1)
        else: raise ee.EEException("EVI failed")
    except:
        try:
            ndvi = img_ee.normalizedDifference(['NIR', 'Red'])
            lai = ndvi.multiply(5.0).add(0.1)
        except: return ee.Image().rename('LAI') # Failed both
    return lai.clamp(0, 8).rename('LAI') if lai else ee.Image().rename('LAI')

def calculate_biomass_simple(image):
    img_ee = ee.Image(image)
    lai_image = calculate_lai_simple(img_ee)
    if 'LAI' in lai_image.bandNames().getInfo():
        lai = lai_image.select('LAI')
        a = 1.5; b = 0.2
        biomass = lai.multiply(a).add(b)
        return biomass.clamp(0, 50).rename('Biomass')
    else: return ee.Image().rename('Biomass')

def calculate_chlorophyll_mcari(image):
    img_ee = ee.Image(image)
    try:
        img_ee.select('RedEdge1')
        mcari = img_ee.expression('((RE1 - RED) - 0.2 * (RE1 - GREEN)) * (RE1 / RED)',
                                  {'RE1': img_ee.select('RedEdge1'), 'RED': img_ee.select('Red'), 'GREEN': img_ee.select('Green')})
        return mcari.rename('Chlorophyll')
    except:
        ndvi = img_ee.normalizedDifference(['NIR', 'Red'])
        return ndvi.rename('Chlorophyll')

def calculate_et_placeholder(image):
    img_ee = ee.Image(image)
    ndmi = img_ee.normalizedDifference(['NIR', 'SWIR1'])
    return ndmi.rename('ET_proxy')

# --- Index Definitions Dictionary ---
# (Defined as before, with 'func', 'vis', 'name_fa', 'desc_fa', 'sort_ascending')
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
# **MODIFIED:** Returns the processed collection, even if empty after masking.
def get_image_collection(start_date, end_date, geometry=None, sensor='Sentinel-2'):
    """Gets, filters, masks, scales, and renames image collection. Returns collection."""
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    collection_id = None; bands_to_select_orig = []; bands_to_rename_to = []; mask_func = None

    if sensor == 'Sentinel-2':
        collection_id = 'COPERNICUS/S2_SR_HARMONIZED'
        mask_func = mask_s2_clouds
        bands_to_select_orig = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12', 'QA60']
        bands_to_rename_to = COMMON_BAND_NAMES
    elif sensor == 'Landsat':
        l9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2'); l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        collection_id = l9.merge(l8)
        mask_func = mask_landsat_clouds
        bands_to_select_orig = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'QA_PIXEL']
        bands_to_rename_to = ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2']
    else: st.error(f"سنسور نامعتبر: {sensor}"); return None

    if start_date > end_date: st.error("تاریخ شروع نمی‌تواند بعد از پایان باشد."); return None

    collection = ee.ImageCollection(collection_id) if isinstance(collection_id, str) else collection_id
    collection = collection.filterDate(start_date_str, end_date_str)
    if geometry:
        try: collection = collection.filterBounds(geometry)
        except Exception as e: st.error(f"خطا در فیلتر هندسی: {e}"); return None

    try:
        initial_count = collection.size().getInfo()
        if initial_count == 0:
            print(f"No initial images found for {sensor} in period/region.")
            # Return the empty collection, let caller handle it
            return collection
    except ee.EEException as e: st.error(f"خطا در دریافت تعداد اولیه تصاویر: {e}"); return None

    def process_image(image_element):
        image = ee.Image(image_element)
        try:
            img_selected_orig = image.select(bands_to_select_orig)
            img_processed = mask_func(img_selected_orig)
            img_processed_safe = ee.Image(img_processed)
            # Check if bands_to_rename_to length matches actual bands in processed image
            actual_band_names = img_processed_safe.bandNames()
            if actual_band_names.size().getInfo() == len(bands_to_rename_to):
                img_renamed = img_processed_safe.rename(bands_to_rename_to)
                return img_renamed.copyProperties(image, ["system:time_start"])
            else:
                 print(f"Warning: Band count mismatch after processing. Expected {len(bands_to_rename_to)}, got {actual_band_names.size().getInfo()}. Skipping image.")
                 return None # Skip if band count doesn't match expected common names
        except Exception as proc_e:
            print(f"Error processing single image: {proc_e}. Skipping.")
            return None # Skip image if processing fails

    processed_collection = collection.map(process_image).filter(ee.Filter.neq('item', None))

    # **CHANGE:** Do not return None here if count is 0. Just provide info.
    try:
        count = processed_collection.size().getInfo()
        print(f"Processed collection size: {count}")
        if count == 0:
            st.info(f"هشدار: پس از حذف ابرها، تصویری در بازه زمانی و منطقه انتخابی ({sensor}) باقی نماند. ممکن است نیاز به افزایش بازه زمانی باشد.", icon="☁️")
    except ee.EEException as e:
        st.error(f"خطا در دریافت تعداد تصاویر پردازش شده: {e}")
        # Return the collection anyway, maybe subsequent steps can handle it
        # return None

    return processed_collection # Return the collection, even if empty

# --- Function to calculate a single index ---
# **MODIFIED:** Handles empty input collection more gracefully.
def calculate_single_index(collection, index_name):
    """Calculates a single specified index for the collection."""
    if collection is None: return None
    # Check if collection is empty *before* trying to calculate
    try:
        collection_size = collection.size().getInfo()
        if collection_size == 0:
            print(f"Input collection for '{index_name}' calculation is empty.")
            return None # Return None if input is empty
    except ee.EEException as e:
         st.error(f"خطای GEE در بررسی اندازه کالکشن برای '{index_name}': {e}")
         return None


    index_detail = INDEX_DEFINITIONS.get(index_name)
    if not index_detail: st.error(f"تعریف شاخص '{index_name}' یافت نشد."); return None

    index_func = index_detail['func']
    try:
        indexed_collection = collection.map(index_func)
        # Verify the index band exists in the *first* image of the result
        first_img = indexed_collection.first()
        # Check if first_img is None (if map failed on all images) OR if band is missing
        if first_img is None or index_name not in ee.Image(first_img).bandNames().getInfo():
             available_bands = ee.Image(first_img).bandNames().getInfo() if first_img else "None"
             st.warning(f"باند شاخص '{index_name}' پس از محاسبه ایجاد نشد. باندهای موجود: {available_bands}", icon="⚠️")
             return None
        # Select only the calculated index band for consistency
        return indexed_collection.select(index_name)
    except ee.EEException as e:
        st.error(f"خطای GEE در محاسبه شاخص '{index_name}': {e}")
        return None
    except Exception as e:
        st.error(f"خطای غیر GEE در محاسبه شاخص '{index_name}': {e}")
        return None

# --- get_timeseries_for_farm ---
@st.cache_data(ttl=1800)
def get_timeseries_for_farm(_farm_geom_geojson, start_date, end_date, index_name, sensor):
    """Retrieves and calculates the time series for a specific index and farm geometry."""
    try: farm_geom = ee.Geometry(json.loads(_farm_geom_geojson))
    except Exception as e: st.error(f"خطا در پردازش هندسه مزرعه: {e}"); return pd.DataFrame()

    base_collection = get_image_collection(start_date, end_date, farm_geom, sensor)
    # Base collection might be empty but not None
    if base_collection is None: return pd.DataFrame() # Error occurred in get_image_collection
    if base_collection.size().getInfo() == 0:
         st.info(f"داده‌ای برای سری زمانی '{index_name}' یافت نشد (عدم وجود تصویر بدون ابر). بازه زمانی را افزایش دهید.", icon="📈")
         return pd.DataFrame() # Empty df if no images after masking


    indexed_collection = calculate_single_index(base_collection, index_name)
    if indexed_collection is None: return pd.DataFrame() # Index calculation failed

    def extract_value(image):
        img_ee = ee.Image(image)
        try:
            stats = img_ee.reduceRegion(reducer=ee.Reducer.mean(), geometry=farm_geom, scale=30, maxPixels=1e9, tileScale=4)
            val = stats.get(index_name)
            time_ms = img_ee.get('system:time_start')
            return ee.Feature(None, {'time': time_ms, index_name: ee.Algorithms.If(val, val, -9999)})
        except ee.EEException as reduce_e:
            print(f"Warning: reduceRegion failed for one image in timeseries: {reduce_e}")
            return None # Return None if reduction fails for this image

    try:
        # Map extraction and filter out nulls from failed reductions
        ts_info = indexed_collection.map(extract_value).filter(ee.Filter.neq('item', None)).getInfo()
    except ee.EEException as e:
        st.error(f"خطای GEE در استخراج سری زمانی: {e}"); return pd.DataFrame()
    except Exception as e: st.error(f"خطای ناشناخته در استخراج سری زمانی: {e}"); return pd.DataFrame()

    data = []
    # ... (rest of the data processing remains the same)
    if 'features' in ts_info:
        for feature in ts_info['features']:
            props = feature.get('properties', {})
            value = props.get(index_name)
            time_ms = props.get('time')
            if value not in [None, -9999] and time_ms is not None:
                try:
                    dt = datetime.datetime.fromtimestamp(time_ms / 1000.0)
                    data.append([dt, value])
                except (TypeError, ValueError) as time_e: pass # Ignore invalid time silently
    if not data: return pd.DataFrame(columns=['Date', index_name])
    return pd.DataFrame(data, columns=['Date', index_name]).sort_values(by='Date').reset_index(drop=True)


# --- Function for getting median index over a period for multiple farms ---
@st.cache_data(ttl=1800)
def get_median_index_for_period(_farms_df_json, start_date, end_date, index_name, sensor):
    """Gets the median index value over a period for multiple farms."""
    farms_df = pd.read_json(_farms_df_json)
    farms_df_valid = farms_df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
    if farms_df_valid.empty: return pd.DataFrame(columns=['مزرعه', index_name])

    features = []
    for idx, row in farms_df_valid.iterrows():
        try:
             geom = ee.Geometry.Point([row['طول جغرافیایی'], row['عرض جغرافیایی']]).buffer(50)
             features.append(ee.Feature(geom, {'farm_id': row['مزرعه']}))
        except Exception as e: print(f"Skipping farm {row.get('مزرعه')} due to geom error: {e}")
    if not features: return pd.DataFrame(columns=['مزرعه', index_name])
    farm_fc = ee.FeatureCollection(features)

    base_collection = get_image_collection(start_date, end_date, farm_fc.geometry(), sensor)
    if base_collection is None or base_collection.size().getInfo() == 0:
         print(f"No base images for period median calculation ({index_name}).")
         return pd.DataFrame(columns=['مزرعه', index_name]) # Return empty if no images

    indexed_collection = calculate_single_index(base_collection, index_name)
    if indexed_collection is None: return pd.DataFrame(columns=['مزرعه', index_name])

    try:
        # Calculate median *after* calculating index for the collection
        median_image = indexed_collection.median()
        # Check if median calculation resulted in a valid image with bands
        if not median_image.bandNames().getInfo():
             st.warning(f"محاسبه Median برای شاخص '{index_name}' تصویری بدون باند ایجاد کرد (احتمالاً داده کافی وجود ندارد).", icon="⚠️")
             return pd.DataFrame(columns=['مزرعه', index_name])
    except ee.EEException as median_e:
        st.error(f"خطای GEE در محاسبه Median برای شاخص '{index_name}': {median_e}")
        return pd.DataFrame(columns=['مزرعه', index_name])


    try:
        farm_values = median_image.reduceRegions(collection=farm_fc, reducer=ee.Reducer.mean(), scale=30, tileScale=8).getInfo()
    except ee.EEException as e: st.error(f"خطای GEE در reduceRegions: {e}"); return pd.DataFrame(columns=['مزرعه', index_name])
    except Exception as e: st.error(f"خطای ناشناخته در reduceRegions: {e}"); return pd.DataFrame(columns=['مزرعه', index_name])

    results_data = []
    # ... (rest of data extraction remains the same)
    if 'features' in farm_values:
        for feature in farm_values['features']:
            props = feature.get('properties', {})
            farm_id = props.get('farm_id'); value = props.get('mean')
            if farm_id is not None and value is not None: results_data.append({'مزرعه': farm_id, index_name: value})
    if not results_data: return pd.DataFrame(columns=['مزرعه', index_name])
    return pd.DataFrame(results_data)


# --- Function for Weekly Comparison ---
@st.cache_data(ttl=1800)
def get_weekly_comparison(_filtered_df_json, start_date, end_date, index_name, sensor):
    """Compares the index values from the current week to the previous week."""
    if not isinstance(start_date, datetime.date) or not isinstance(end_date, datetime.date):
        st.error("تاریخ‌های نامعتبر برای مقایسه."); return pd.DataFrame()

    current_start = start_date; current_end = end_date
    prev_end = current_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=(end_date-start_date).days)

    print(f"Comparing Period: {current_start} to {current_end}")
    print(f"Previous Period: {prev_start} to {prev_end}")

    # Get data for the current period
    df_current = get_median_index_for_period(_filtered_df_json, current_start, current_end, index_name, sensor)
    if df_current.empty: st.warning(f"داده‌ای برای دوره فعلی جهت مقایسه یافت نشد.", icon="⚠️"); return pd.DataFrame()

    # Get data for the previous period
    df_previous = get_median_index_for_period(_filtered_df_json, prev_start, prev_end, index_name, sensor)
    if df_previous.empty: st.warning(f"داده‌ای برای دوره قبلی جهت مقایسه یافت نشد.", icon="⚠️"); return pd.DataFrame() # Cannot compare

    df_comparison = pd.merge(df_previous.rename(columns={index_name: f'{index_name}_prev'}),
                           df_current.rename(columns={index_name: f'{index_name}_curr'}),
                           on='مزرعه', how='inner')
    if df_comparison.empty: st.info("مزرعه مشترکی بین دو دوره یافت نشد."); return pd.DataFrame()

    df_comparison['تغییر'] = df_comparison[f'{index_name}_curr'] - df_comparison[f'{index_name}_prev']
    df_comparison['درصد_تغییر'] = np.where(np.abs(df_comparison[f'{index_name}_prev']) > 1e-9,
                                       ((df_comparison['تغییر'] / df_comparison[f'{index_name}_prev']) * 100.0), np.nan)
    df_decreased = df_comparison[df_comparison['تغییر'] < 0].copy()
    df_decreased = df_decreased.sort_values(by='درصد_تغییر', ascending=True, na_position='last')
    return df_decreased


# --- Streamlit App Layout ---
st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")
st.title(f"🌾 {APP_TITLE}")
st.markdown("مانیتورینگ وضعیت مزارع نیشکر با استفاده از تصاویر ماهواره‌ای و Google Earth Engine")
st.divider()

# Initialize GEE
if initialize_gee():
    # Load data
    farm_data_df = load_data(CSV_FILE_PATH)

    # --- Sidebar Controls ---
    with st.sidebar:
        st.header("⚙️ تنظیمات و فیلترها")
        st.divider()
        st.subheader("🗓️ انتخاب بازه زمانی")
        today = datetime.date.today()
        default_start = today - timedelta(days=6)
        start_date = st.date_input("تاریخ شروع", value=default_start, max_value=today, help="تاریخ شروع دوره تحلیل اصلی")
        end_date = st.date_input("تاریخ پایان", value=today, min_value=start_date, max_value=today, help="تاریخ پایان دوره تحلیل اصلی")
        st.info(f"مدت دوره: {(end_date - start_date).days + 1} روز", icon="⏳")
        st.divider()

        st.subheader("🔍 فیلتر داده‌ها")
        days_list = ["همه روزها"] + sorted(farm_data_df['روزهای هفته'].unique().tolist())
        selected_day = st.selectbox("روز هفته آبیاری", options=days_list, help="فیلتر مزارع بر اساس روز هفته")
        if selected_day == "همه روزها": filtered_df = farm_data_df.copy()
        else: filtered_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day].copy()
        st.caption(f"{len(filtered_df)} مزرعه انتخاب شد.")

        available_indices = list(INDEX_DEFINITIONS.keys())
        selected_index = st.selectbox("شاخص مورد تحلیل", options=available_indices, format_func=lambda x: INDEX_DEFINITIONS[x]['name_fa'], help="شاخص برای نقشه، رتبه‌بندی و مقایسه")
        selected_sensor = st.radio("سنسور ماهواره", ('Sentinel-2', 'Landsat'), index=0, horizontal=True, help="Sentinel-2 (10m, RedEdge), Landsat (30m)")
        st.divider()

        st.subheader("🚜 انتخاب مزرعه")
        farm_list = ["همه مزارع"] + sorted(filtered_df['مزرعه'].unique().tolist())
        selected_farm = st.selectbox("مزرعه خاص (یا همه)", options=farm_list, help="انتخاب مزرعه برای جزئیات و روند زمانی")
        st.divider()

        st.header("ℹ️ راهنمای شاخص‌ها")
        index_to_explain = st.selectbox("مشاهده توضیحات شاخص:", options=list(INDEX_DEFINITIONS.keys()), index=available_indices.index(selected_index), format_func=lambda x: INDEX_DEFINITIONS[x]['name_fa'])
        if index_to_explain:
            with st.expander(f"جزئیات شاخص {INDEX_DEFINITIONS[index_to_explain]['name_fa']}", expanded=False):
                st.markdown(INDEX_DEFINITIONS[index_to_explain]['desc_fa'], unsafe_allow_html=True)
        st.divider()
        st.caption("v1.1 - Dehkhoda Sugarcane Monitoring")

    # --- Main Panel with Tabs ---
    tab1, tab2, tab3 = st.tabs(["🗺️ نقشه و جزئیات", "📊 رتبه‌بندی مزارع", "📉 مقایسه هفتگی"])

    with tab1:
        col_map, col_detail = st.columns([2, 1])
        with col_map:
            st.subheader(f"نقشه وضعیت: {INDEX_DEFINITIONS[selected_index]['name_fa']}")
            st.caption(f"دوره: {start_date.strftime('%Y-%m-%d')} تا {end_date.strftime('%Y-%m-%d')} | سنسور: {selected_sensor}")
            map_placeholder = st.empty()
            m = geemap.Map(center=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False)
            m.add_basemap('HYBRID')
            vis_params = INDEX_DEFINITIONS.get(selected_index, {}).get('vis', {'min': 0, 'max': 1, 'palette': ['white', 'gray']})

            display_geom = None; target_object_for_map = None; farm_info_for_display = None
            display_df = filtered_df.copy() # Use day-filtered data

            if selected_farm == "همه مزارع":
                display_df_valid = display_df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
                if not display_df_valid.empty:
                    try:
                        min_lon, min_lat = display_df_valid['طول جغرافیایی'].min(), display_df_valid['عرض جغرافیایی'].min()
                        max_lon, max_lat = display_df_valid['طول جغرافیایی'].max(), display_df_valid['عرض جغرافیایی'].max()
                        display_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
                        target_object_for_map = display_geom
                    except Exception as bounds_e: st.error(f"خطا در محاسبه مرزها: {bounds_e}")
                else: st.info("مزرعه‌ای با مختصات معتبر برای نمایش در این روز یافت نشد.", icon="📍")
            else: # Single farm
                farm_info_rows = display_df[display_df['مزرعه'] == selected_farm]
                if not farm_info_rows.empty:
                    farm_info_for_display = farm_info_rows.iloc[0]
                    farm_lat = farm_info_for_display['عرض جغرافیایی']; farm_lon = farm_info_for_display['طول جغرافیایی']
                    if pd.notna(farm_lat) and pd.notna(farm_lon):
                        try:
                            farm_geom = ee.Geometry.Point([farm_lon, farm_lat])
                            display_geom = farm_geom.buffer(150); target_object_for_map = farm_geom
                        except Exception as point_e: st.error(f"خطا در ایجاد هندسه نقطه: {point_e}"); farm_info_for_display = None
                    else: st.warning(f"مختصات نامعتبر: {selected_farm}.", icon="📍"); farm_info_for_display = None
                else: st.warning(f"اطلاعات مزرعه {selected_farm} برای روز '{selected_day}' یافت نشد.", icon="⚠️")

            # --- Display Map Layer ---
            layer_added = False
            if display_geom:
                with st.spinner(f"در حال پردازش نقشه '{selected_index}'... (ممکن است کمی طول بکشد)"):
                    base_collection = get_image_collection(start_date, end_date, display_geom, selected_sensor)
                    # Base collection might be empty but not None
                    if base_collection is not None:
                        indexed_collection = calculate_single_index(base_collection, selected_index)
                        if indexed_collection is not None:
                            try:
                                # **CRUCIAL CHANGE:** Use median composite for map display
                                median_image = indexed_collection.median()
                                # Check if median calculation resulted in a valid image
                                if median_image.bandNames().getInfo():
                                    layer_image = median_image.clip(display_geom) if selected_farm != "همه مزارع" else median_image
                                    m.addLayer(layer_image, vis_params, f'{selected_index} (Median)')
                                    layer_added = True
                                    try: m.add_legend(title=f'{selected_index}', builtin_legend=None, palette=vis_params['palette'], min=vis_params['min'], max=vis_params['max'])
                                    except Exception as legend_e: print(f"Legend error: {legend_e}")

                                    # Add download button
                                    # ... (download button logic remains same)

                                else:
                                     st.warning(f"محاسبه Median برای '{selected_index}' تصویری بدون باند ایجاد کرد. داده کافی در بازه زمانی وجود ندارد.", icon="⚠️")

                            except ee.EEException as ee_err: st.error(f"خطای GEE در پردازش لایه نقشه: {ee_err}")
                            except Exception as err: st.error(f"خطای ناشناخته در پردازش لایه نقشه: {err}")
                        # else: Warning shown in calculate_single_index
                    # else: Warning shown in get_image_collection

                # --- Add markers ---
                if layer_added: # Only add markers if layer exists
                    # ... (marker adding logic remains same, uses cleaned 'سن')
                    if selected_farm == "همه مزارع":
                        df_to_mark = display_df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
                        for idx, row in df_to_mark.iterrows():
                            popup_html = f"<b>مزرعه:</b> {row['مزرعه']}<br><b>کانال:</b> {row['کانال']} | <b>اداره:</b> {row['اداره']}<br><b>مساحت:</b> {row['مساحت داشت']:.2f}<br><b>واریته:</b> {row['واریته']} | <b>سن:</b> {row['سن']}" # Use 'سن'
                            folium.Marker(location=[row['عرض جغرافیایی'], row['طول جغرافیایی']], popup=folium.Popup(popup_html, max_width=250), tooltip=f"{row['مزرعه']}", icon=folium.Icon(color='blue', icon='info-sign', prefix='fa')).add_to(m)
                    elif farm_info_for_display is not None:
                        farm_info = farm_info_for_display
                        popup_html = f"<b>مزرعه:</b> {farm_info['مزرعه']}<br><b>کانال:</b> {farm_info['کانال']} | <b>اداره:</b> {farm_info['اداره']}<br><b>مساحت:</b> {farm_info['مساحت داشت']:.2f}<br><b>واریته:</b> {farm_info['واریته']} | <b>سن:</b> {farm_info['سن']}" # Use 'سن'
                        folium.Marker(location=[farm_info['عرض جغرافیایی'], farm_info['طول جغرافیایی']], popup=folium.Popup(popup_html, max_width=250), tooltip=f"{farm_info['مزرعه']} (انتخاب شده)", icon=folium.Icon(color='red', icon='star', prefix='fa')).add_to(m)

                # Center map
                if target_object_for_map:
                    zoom = INITIAL_ZOOM + 2 if selected_farm != "همه مزارع" else INITIAL_ZOOM
                    try: m.center_object(target_object_for_map, zoom=zoom)
                    except: m.set_center(INITIAL_LON, INITIAL_LAT, INITIAL_ZOOM)

            else: st.info("هندسه معتبری برای نمایش نقشه تعیین نشد.", icon="🗺️")

            with map_placeholder: m.to_streamlit(height=550)

        # --- Column 2: Details / Timeseries ---
        with col_detail:
            if selected_farm != "همه مزارع":
                st.subheader(f" جزئیات مزرعه: {selected_farm}")
                st.divider()
                if farm_info_for_display is not None:
                    farm_info = farm_info_for_display
                    st.metric("کانال", str(farm_info.get('کانال', 'N/A')), help="شماره کانال")
                    st.metric("اداره", str(farm_info.get('اداره', 'N/A')), help="شماره اداره")
                    st.metric("مساحت (هکتار)", f"{farm_info['مساحت داشت']:.2f}" if pd.notna(farm_info.get('مساحت داشت')) else "N/A", help="مساحت ثبت شده")
                    st.metric("واریته", str(farm_info.get('واریته', 'N/A')))
                    st.metric("سن", str(farm_info.get('سن', 'N/A'))) # Use cleaned name
                    st.metric("روز آبیاری", str(farm_info.get('روزهای هفته', 'N/A')))
                    st.divider()

                    st.subheader(f"📈 روند شاخص: {INDEX_DEFINITIONS[selected_index]['name_fa']}")
                    if pd.notna(farm_info.get('عرض جغرافیایی')) and pd.notna(farm_info.get('طول جغرافیایی')):
                        with st.spinner(f"دریافت سری زمانی '{selected_index}'..."):
                            try:
                                farm_geom_ts = ee.Geometry.Point([farm_info['طول جغرافیایی'], farm_info['عرض جغرافیایی']])
                                ts_df = get_timeseries_for_farm(farm_geom_ts.toGeoJsonString(), start_date, end_date, selected_index, selected_sensor)
                            except Exception as ts_geom_e: st.error(f"خطا در هندسه سری زمانی: {ts_geom_e}"); ts_df = pd.DataFrame()

                        if not ts_df.empty:
                            fig_ts = px.line(ts_df, x='Date', y=selected_index, title=f"روند زمانی {selected_index}", markers=True, labels={'Date': 'تاریخ', selected_index: f'مقدار {selected_index}'})
                            fig_ts.update_layout(xaxis_title="تاریخ", yaxis_title=f"مقدار {selected_index}", title_x=0.5)
                            fig_ts.update_traces(line=dict(color='royalblue', width=2), marker=dict(color='salmon', size=6))
                            st.plotly_chart(fig_ts, use_container_width=True)
                        # else: Warning/Info shown in get_timeseries_for_farm if empty
                    else: st.warning("مختصات نامعتبر برای سری زمانی.", icon="📍")
                else: st.info("اطلاعات این مزرعه برای نمایش موجود نیست.")
            else:
                 st.subheader("راهنمای جزئیات و روند")
                 st.info("برای مشاهده جزئیات و نمودار روند، یک مزرعه خاص را از نوار کناری انتخاب کنید.", icon="👈")


    with tab2:
        st.subheader(f"📊 رتبه‌بندی مزارع بر اساس: {INDEX_DEFINITIONS[selected_index]['name_fa']}")
        st.caption(f"دوره: {start_date.strftime('%Y-%m-%d')} تا {end_date.strftime('%Y-%m-%d')} | روز هفته: '{selected_day}' | سنسور: {selected_sensor}")
        st.divider()
        if filtered_df.empty: st.warning(f"مزرعه‌ای برای روز هفته '{selected_day}' یافت نشد.", icon="⚠️")
        else:
            with st.spinner(f"محاسبه رتبه‌بندی '{selected_index}'..."):
                ranking_df = get_median_index_for_period(filtered_df.to_json(), start_date, end_date, selected_index, sensor=selected_sensor)

            if not ranking_df.empty:
                ascending_sort = INDEX_DEFINITIONS[selected_index].get('sort_ascending', False)
                ranking_df_sorted = ranking_df.sort_values(by=selected_index, ascending=ascending_sort, na_position='last').reset_index(drop=True)
                st.dataframe(ranking_df_sorted.style.format({selected_index: "{:.3f}"})
                                     .bar(subset=[selected_index], color='lightcoral' if ascending_sort else 'lightgreen', align='zero'), # Align bars at zero
                                     use_container_width=True)
                csv_rank = ranking_df_sorted.to_csv(index=False).encode('utf-8')
                st.download_button(label=f"📥 دانلود جدول رتبه‌بندی", data=csv_rank, file_name=f'ranking_{selected_index}_{selected_day}.csv', mime='text/csv', key='dl_rank')
            else: st.warning(f"اطلاعاتی برای رتبه‌بندی یافت نشد. ممکن است تصویری در بازه زمانی موجود نباشد.", icon="📊")
        st.divider()


    with tab3:
        st.subheader(f"📉 مقایسه هفتگی: مزارع با کاهش شاخص ({INDEX_DEFINITIONS[selected_index]['name_fa']})")
        st.caption(f"مقایسه دوره جاری با هفته قبل | روز هفته: '{selected_day}' | سنسور: {selected_sensor}")
        st.divider()
        if filtered_df.empty: st.warning(f"مزرعه‌ای برای روز هفته '{selected_day}' جهت مقایسه یافت نشد.", icon="⚠️")
        else:
            with st.spinner(f"مقایسه داده‌های هفتگی '{selected_index}'..."):
                comparison_df_decreased = get_weekly_comparison(filtered_df.to_json(), start_date, end_date, selected_index, selected_sensor)

            if not comparison_df_decreased.empty:
                st.markdown("##### مزارع با کاهش شاخص:")
                display_cols = ['مزرعه', f'{index_name}_prev', f'{index_name}_curr', 'تغییر', 'درصد_تغییر']
                st.dataframe(comparison_df_decreased[display_cols].style.format({
                                f'{index_name}_prev': "{:.3f}", f'{index_name}_curr': "{:.3f}",
                                'تغییر': "{:+.3f}", 'درصد_تغییر': "{:+.1f}%"
                            }).applymap(lambda x: 'color: red' if isinstance(x, (int, float)) and x < 0 else ('color: green' if isinstance(x, (int, float)) and x > 0 else 'color: black'), subset=['تغییر','درصد_تغییر']),
                            use_container_width=True)
                st.divider()
                st.markdown("##### نمودار مقایسه‌ای:")
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Bar(x=comparison_df_decreased['مزرعه'], y=comparison_df_decreased[f'{index_name}_prev'], name='هفته قبل', marker_color='dodgerblue', text=comparison_df_decreased[f'{index_name}_prev'].round(3), textposition='auto'))
                fig_comp.add_trace(go.Bar(x=comparison_df_decreased['مزرعه'], y=comparison_df_decreased[f'{index_name}_curr'], name='هفته جاری', marker_color='lightcoral', text=comparison_df_decreased[f'{index_name}_curr'].round(3), textposition='auto'))
                fig_comp.update_layout(barmode='group', title=f'مقایسه شاخص {selected_index} (مزارع با کاهش)', xaxis_title='مزرعه', yaxis_title=f'مقدار {selected_index}', legend_title='دوره', hovermode="x unified", title_x=0.5)
                st.plotly_chart(fig_comp, use_container_width=True)
                st.divider()
                csv_comp = comparison_df_decreased.to_csv(index=False).encode('utf-8')
                st.download_button(label=f"📥 دانلود داده‌های مقایسه", data=csv_comp, file_name=f'comparison_decrease_{selected_index}_{selected_day}.csv', mime='text/csv', key='dl_comp')
            else:
                 # Check if comparison failed due to lack of data in *either* period (based on warnings from get_median_index_for_period)
                 # This requires passing status back or checking df validity more carefully.
                 # For now, assume if comparison_df is empty, either no decrease or no data.
                 st.success(f"✅ عدم کاهش: هیچ مزرعه‌ای کاهش شاخص '{selected_index}' را بین دو هفته اخیر نشان نداد یا داده کافی برای مقایسه وجود نداشت.")

else:
    st.error("اتصال به Google Earth Engine برقرار نشد. لطفاً پیش‌نیازها و اتصال اینترنت را بررسی کنید.", icon="🚨")