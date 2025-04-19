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
        original_columns = df.columns.tolist() # Keep original names for reference
        df.columns = df.columns.str.strip() # Clean names
        cleaned_columns = df.columns.tolist()
        print(f"Original columns: {original_columns}")
        print(f"Cleaned columns: {cleaned_columns}")

        # Handle 'سن' column rename explicitly if needed
        if 'سن ' in original_columns and 'سن' not in cleaned_columns:
             df.rename(columns={'سن ': 'سن'}, inplace=True)
             print("Renamed 'سن ' to 'سن'")
             cleaned_columns = df.columns.tolist() # Update cleaned list

        # Type conversions and cleaning
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        df['مساحت داشت'] = pd.to_numeric(df['مساحت داشت'], errors='coerce')
        df['مزرعه'] = df['مزرعه'].str.strip()

        for col in ['کانال', 'اداره', 'واریته', 'سن', 'روزهای هفته']:
             if col in df.columns:
                df[col] = df[col].astype(str).fillna('نامشخص')
             else:
                 print(f"Warning: Column '{col}' not found during loading. Adding default.")
                 df[col] = 'نامشخص'

        if 'coordinates_missing' in df.columns:
             df['coordinates_missing'] = pd.to_numeric(df['coordinates_missing'], errors='coerce').fillna(1).astype(int)
        else:
             print("Inferring 'coordinates_missing' column.")
             df['coordinates_missing'] = df.apply(lambda row: 1 if pd.isna(row['طول جغرافیایی']) or pd.isna(row['عرض جغرافیایی']) else 0, axis=1)

        print(f"Data loaded. Shape: {df.shape}.")
        return df
    except FileNotFoundError: st.error(f"خطا: فایل CSV '{csv_path}' یافت نشد."); st.stop()
    except Exception as e: st.error(f"خطا در بارگذاری CSV: {e}"); st.exception(e); st.stop()

# --- GEE Image Processing Functions ---
COMMON_BAND_NAMES = ['Blue', 'Green', 'Red', 'RedEdge1', 'NIR', 'SWIR1', 'SWIR2']

def mask_s2_clouds(image):
    img_ee = ee.Image(image)
    qa = img_ee.select('QA60')
    cloud_mask = 1 << 10; cirrus_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_mask).eq(0).And(qa.bitwiseAnd(cirrus_mask).eq(0))
    data_bands = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12']
    return img_ee.select(data_bands).updateMask(mask).divide(10000.0).copyProperties(img_ee, ["system:time_start"])

def mask_landsat_clouds(image):
    img_ee = ee.Image(image)
    qa = img_ee.select('QA_PIXEL')
    cloud_shadow_mask = 1 << 3; snow_mask = 1 << 4; cloud_mask = 1 << 5
    mask = qa.bitwiseAnd(cloud_shadow_mask).eq(0).And(qa.bitwiseAnd(snow_mask).eq(0)).And(qa.bitwiseAnd(cloud_mask).eq(0))
    sr_bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']
    scale = 0.0000275; offset = -0.2
    scaled_bands = img_ee.select(sr_bands).multiply(scale).add(offset)
    return scaled_bands.updateMask(mask).copyProperties(img_ee, ["system:time_start"])

# --- Index Calculation Functions (Corrected Syntax) ---
def calculate_ndvi(image):
    img_ee = ee.Image(image)
    try:
        ndvi = img_ee.normalizedDifference(['NIR', 'Red'])
        return ndvi.rename('NDVI')
    except Exception as e:
        print(f"Error calculating NDVI: {e}")
        return ee.Image().rename('NDVI') # Return empty image named NDVI

def calculate_evi(image):
    img_ee = ee.Image(image)
    try:
        # Ensure necessary bands exist
        img_ee.select(['NIR', 'Red', 'Blue'])
        evi = img_ee.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                'NIR': img_ee.select('NIR'),
                'RED': img_ee.select('Red'),
                'BLUE': img_ee.select('Blue')
            })
        return evi.rename('EVI')
    except Exception as e:
        print(f"Error calculating EVI: {e}")
        return ee.Image().rename('EVI')

def calculate_ndmi(image):
    img_ee = ee.Image(image)
    try:
        ndmi = img_ee.normalizedDifference(['NIR', 'SWIR1'])
        return ndmi.rename('NDMI')
    except Exception as e:
        print(f"Error calculating NDMI: {e}")
        return ee.Image().rename('NDMI')

def calculate_msi(image):
    img_ee = ee.Image(image)
    try:
        msi = img_ee.expression('SWIR1 / NIR', {
            'SWIR1': img_ee.select('SWIR1'),
            'NIR': img_ee.select('NIR')
            })
        return msi.rename('MSI')
    except Exception as e:
        print(f"Error calculating MSI: {e}")
        return ee.Image().rename('MSI')

def calculate_lai_simple(image):
    img_ee = ee.Image(image)
    lai = None
    try:
        # Try EVI first
        evi_img = calculate_evi(img_ee) # Will return empty EVI image if fails
        # Check if EVI calculation was successful by checking bands
        if 'EVI' in evi_img.bandNames().getInfo():
             lai = evi_img.select('EVI').multiply(3.5).add(0.1)
        else:
             # Fallback to NDVI
             ndvi = img_ee.normalizedDifference(['NIR', 'Red'])
             lai = ndvi.multiply(5.0).add(0.1)
    except Exception as e:
        print(f"Error in LAI calculation logic: {e}")
        return ee.Image().rename('LAI') # Failed both or other error

    # Ensure lai is calculated before clamping/renaming
    if lai is not None:
         return lai.clamp(0, 8).rename('LAI')
    else:
         return ee.Image().rename('LAI')


def calculate_biomass_simple(image):
    img_ee = ee.Image(image)
    try:
        lai_image = calculate_lai_simple(img_ee)
        # Check if LAI was calculated successfully
        if 'LAI' in lai_image.bandNames().getInfo():
            lai = lai_image.select('LAI')
            a=1.5; b=0.2 # Placeholder coefficients
            biomass = lai.multiply(a).add(b)
            return biomass.clamp(0, 50).rename('Biomass')
        else:
             return ee.Image().rename('Biomass') # LAI failed
    except Exception as e:
        print(f"Error calculating Biomass: {e}")
        return ee.Image().rename('Biomass')

def calculate_chlorophyll_mcari(image):
    img_ee = ee.Image(image)
    try:
        # Try MCARI (requires RedEdge)
        img_ee.select('RedEdge1') # Check for RedEdge1
        mcari = img_ee.expression(
            '((RE1 - RED) - 0.2 * (RE1 - GREEN)) * (RE1 / RED)', {
                'RE1': img_ee.select('RedEdge1'),
                'RED': img_ee.select('Red'),
                'GREEN': img_ee.select('Green')
            })
        return mcari.rename('Chlorophyll')
    except: # If RedEdge fails or other error, fallback to NDVI
        try:
            ndvi = img_ee.normalizedDifference(['NIR', 'Red'])
            return ndvi.rename('Chlorophyll')
        except Exception as e_ndvi: # If even NDVI fails
             print(f"Error calculating Chlorophyll (MCARI/NDVI): {e_ndvi}")
             return ee.Image().rename('Chlorophyll')

def calculate_et_placeholder(image):
    img_ee = ee.Image(image)
    try:
        # Use NDMI as proxy
        ndmi = img_ee.normalizedDifference(['NIR', 'SWIR1'])
        return ndmi.rename('ET_proxy')
    except Exception as e:
        print(f"Error calculating ET Proxy (NDMI): {e}")
        return ee.Image().rename('ET_proxy')


# --- Index Definitions Dictionary ---
# (Defined as before)
INDEX_DEFINITIONS = {
    'NDVI': { 'func': calculate_ndvi, 'vis': {'min': 0, 'max': 1, 'palette': ['#d73027', '#fee08b', '#1a9850']}, 'name_fa': "شاخص پوشش گیاهی (NDVI)", 'desc_fa': """**NDVI:** رایج‌ترین شاخص سلامت و تراکم پوشش گیاهی. مقادیر بالاتر بهتر است.<br>- **محدوده:** -۱ تا +۱ (معمولاً ۰.۱ تا ۰.۹ برای گیاه)<br>- **تفسیر:** < ۰.۲ (خاک/آب), ۰.۲-۰.۵ (پراکنده/تنش), > ۰.۵ (سالم/متراکم)""", 'sort_ascending': False},
    'EVI': { 'func': calculate_evi, 'vis': {'min': 0, 'max': 1, 'palette': ['#d73027', '#fee08b', '#1a9850']}, 'name_fa': "شاخص پوشش گیاهی بهبودیافته (EVI)", 'desc_fa': """**EVI:** مشابه NDVI با حساسیت کمتر به اثرات جو و خاک، بهتر در تراکم بالا.<br>- **محدوده:** ۰ تا ۱<br>- **تفسیر:** مقادیر بالاتر بهتر است.""", 'sort_ascending': False},
    'NDMI': { 'func': calculate_ndmi, 'vis': {'min': -0.5, 'max': 0.8, 'palette': ['#a50026', '#ffffbf', '#313695']}, 'name_fa': "شاخص رطوبت (NDMI)", 'desc_fa': """**NDMI:** میزان آب در برگ‌ها.<br>- **محدوده:** -۱ تا +۱<br>- **تفسیر:** مقادیر بالاتر (آبی) رطوبت بیشتر، پایین‌تر (قهوه‌ای) خشکی/تنش آبی.""", 'sort_ascending': False},
    'MSI': { 'func': calculate_msi, 'vis': {'min': 0.4, 'max': 2.5, 'palette': ['#1a9641', '#ffffbf', '#d7191c']}, 'name_fa': "شاخص تنش رطوبتی (MSI)", 'desc_fa': """**MSI:** حساس به رطوبت، اما مقادیر **بالاتر** نشانه تنش **بیشتر** است (برعکس NDMI).<br>- **محاسبه:** SWIR1 / NIR<br>- **محدوده:** > ۰.۴<br>- **تفسیر:** پایین‌تر (سبز) بهتر، بالاتر (قرمز) تنش بیشتر.""", 'sort_ascending': True},
    'LAI': { 'func': calculate_lai_simple, 'vis': {'min': 0, 'max': 8, 'palette': ['#fff5f0', '#fdcdb9', '#e34a33']}, 'name_fa': "شاخص سطح برگ (LAI - تخمینی)", 'desc_fa': """**LAI:** نسبت سطح برگ به سطح زمین (m²/m²). **تخمینی** و نیاز به کالیبراسیون دارد.<br>- **محدوده:** ۰ تا ۸+<br>- **تفسیر:** بالاتر یعنی تراکم برگ بیشتر.""", 'sort_ascending': False},
    'Biomass': { 'func': calculate_biomass_simple, 'vis': {'min': 0, 'max': 30, 'palette': ['#f7fcb9', '#addd8e', '#31a354']}, 'name_fa': "زیست‌توده (Biomass - تخمینی)", 'desc_fa': """**Biomass:** وزن ماده خشک گیاهی (تن/هکتار). **تخمینی** و نیاز به کالیبراسیون دارد.<br>- **محدوده:** وابسته به کالیبراسیون.<br>- **تفسیر:** بالاتر یعنی زیست‌توده بیشتر.""", 'sort_ascending': False},
    'Chlorophyll': { 'func': calculate_chlorophyll_mcari, 'vis': {'min': 0, 'max': 1, 'palette': ['#ffffcc', '#a1dab4', '#253494']}, 'name_fa': "شاخص کلروفیل (MCARI/NDVI)", 'desc_fa': """**Chlorophyll:** مرتبط با غلظت کلروفیل (سلامت). از MCARI (نیاز به RedEdge) یا NDVI استفاده می‌شود.<br>- **محدوده:** متغیر.<br>- **تفسیر:** بالاتر معمولاً بهتر است.""", 'sort_ascending': False},
    'ET_proxy': { 'func': calculate_et_placeholder, 'vis': {'min': -0.5, 'max': 0.8, 'palette': ['#a50026', '#ffffbf', '#313695']}, 'name_fa': "پراکسی تبخیر-تعرق (ET)", 'desc_fa': """**ET Proxy:** جایگزین برای وضعیت رطوبتی مرتبط با تبخیر-تعرق (ET). از NDMI استفاده می‌شود.<br>- **تفسیر:** بالاتر یعنی پتانسیل رطوبتی بیشتر.""", 'sort_ascending': False}
}

# --- GEE Data Retrieval ---
def get_image_collection(start_date, end_date, geometry=None, sensor='Sentinel-2'):
    start_date_str = start_date.strftime('%Y-%m-%d'); end_date_str = end_date.strftime('%Y-%m-%d')
    collection_id = None; bands_to_select_orig = []; bands_to_rename_to = []; mask_func = None

    if sensor == 'Sentinel-2':
        collection_id = 'COPERNICUS/S2_SR_HARMONIZED'; mask_func = mask_s2_clouds
        bands_to_select_orig = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12', 'QA60']
        bands_to_rename_to = COMMON_BAND_NAMES
    elif sensor == 'Landsat':
        l9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2'); l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        collection_id = l9.merge(l8); mask_func = mask_landsat_clouds
        bands_to_select_orig = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'QA_PIXEL']
        bands_to_rename_to = ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2']
    else: st.error(f"سنسور نامعتبر: {sensor}"); return None

    if start_date > end_date: st.error("تاریخ شروع بعد از پایان است."); return None

    collection = ee.ImageCollection(collection_id) if isinstance(collection_id, str) else collection_id
    collection = collection.filterDate(start_date_str, end_date_str)
    if geometry:
        try: collection = collection.filterBounds(geometry)
        except Exception as e: st.error(f"خطا در فیلتر هندسی: {e}"); return None

    try:
        initial_count = collection.size().getInfo()
        if initial_count == 0: print(f"No initial images for {sensor}."); return collection
    except ee.EEException as e: st.error(f"خطا در دریافت تعداد اولیه: {e}"); return None

    # --- Processing Function (Mapped) ---
    def process_image(image_element):
        image = ee.Image(image_element)
        try:
            img_selected_orig = image.select(bands_to_select_orig)
            img_processed = mask_func(img_selected_orig)
            img_processed_safe = ee.Image(img_processed)
            actual_band_names = img_processed_safe.bandNames()
            if actual_band_names.size().getInfo() != len(bands_to_rename_to):
                print(f"Band count mismatch. Skipping.")
                return ee.Image().set('process_error', 1) # Return empty, mark error

            img_renamed = img_processed_safe.rename(bands_to_rename_to)
            return img_renamed.copyProperties(image, ["system:time_start"])
        except Exception as proc_e:
            print(f"Error processing image: {proc_e}. Skipping.")
            return ee.Image().set('process_error', 1) # Return empty, mark error

    processed_collection = collection.map(process_image).filter(ee.Filter.eq('process_error', None))

    try:
        count = processed_collection.size().getInfo()
        print(f"Processed collection size: {count}")
        if count == 0: st.info(f"هشدار: تصویری پس از حذف ابرها باقی نماند ({sensor}).", icon="☁️")
    except ee.EEException as e: st.error(f"خطا در دریافت تعداد پردازش شده: {e}")

    return processed_collection

# --- Function to calculate a single index ---
def calculate_single_index(collection, index_name):
    if collection is None: return None
    try:
        if collection.size().getInfo() == 0: print(f"Input collection for '{index_name}' empty."); return None
    except ee.EEException as e: st.error(f"GEE Error checking size for '{index_name}': {e}"); return None

    index_detail = INDEX_DEFINITIONS.get(index_name);
    if not index_detail: st.error(f"تعریف شاخص '{index_name}' نیست."); return None
    index_func = index_detail['func']

    # --- Safe Mapping for Index Calculation ---
    def calculate_and_check(image):
        img = ee.Image(image)
        # Calculate the index. Index func should return empty image on failure.
        calculated_index_image = index_func(img)
        # Return the result (could be empty or contain the index band)
        # Preserve time property
        return calculated_index_image.copyProperties(img, ['system:time_start'])

    try:
        indexed_collection = collection.map(calculate_and_check)

        # Filter out images where the index calculation failed (resulted in no bands)
        indexed_collection_valid = indexed_collection.filter(ee.Filter.listContains('system:band_names', index_name))

        # Check if any valid images remain
        valid_count = indexed_collection_valid.size().getInfo()
        if valid_count == 0:
             st.warning(f"محاسبه شاخص '{index_name}' برای تمام تصاویر ناموفق بود.", icon="⚠️")
             return None

        print(f"Valid images after calculating '{index_name}': {valid_count}")
        # Select only the index band from the valid images
        return indexed_collection_valid.select(index_name)

    except ee.EEException as e: st.error(f"خطای GEE در محاسبه شاخص '{index_name}': {e}"); return None
    except Exception as e: st.error(f"خطای غیر GEE در محاسبه شاخص '{index_name}': {e}"); return None


# --- get_timeseries_for_farm ---
@st.cache_data(ttl=1800)
def get_timeseries_for_farm(_farm_geom_geojson, start_date, end_date, index_name, sensor):
    try: farm_geom = ee.Geometry(json.loads(_farm_geom_geojson))
    except Exception as e: st.error(f"خطای هندسه مزرعه: {e}"); return pd.DataFrame()

    base_collection = get_image_collection(start_date, end_date, farm_geom, sensor)
    if base_collection is None: return pd.DataFrame()
    try:
        if base_collection.size().getInfo() == 0: st.info(f"داده‌ای برای سری زمانی '{index_name}' نیست.", icon="📈"); return pd.DataFrame()
    except ee.EEException as e: st.error(f"خطا در بررسی کالکشن پایه سری زمانی: {e}"); return pd.DataFrame()

    indexed_collection = calculate_single_index(base_collection, index_name)
    if indexed_collection is None: return pd.DataFrame() # Error/Warning shown inside function
    try:
         if indexed_collection.size().getInfo() == 0: st.info(f"داده‌ای برای سری زمانی '{index_name}' پس از محاسبه شاخص نیست.", icon="📈"); return pd.DataFrame()
    except ee.EEException as e: st.error(f"خطا در بررسی کالکشن شاخص سری زمانی: {e}"); return pd.DataFrame()


    # --- Safe Extraction Function ---
    def extract_value(image):
        img_ee = ee.Image(image)
        time_ms = img_ee.get('system:time_start')
        try:
            stats = img_ee.reduceRegion(reducer=ee.Reducer.mean(), geometry=farm_geom, scale=30, maxPixels=1e9, tileScale=4)
            val = stats.get(index_name)
            return ee.Feature(None, {'time': time_ms, index_name: ee.Algorithms.If(val, val, -9999)})
        except ee.EEException as reduce_e:
            print(f"Warning: reduceRegion failed: {reduce_e}")
            return ee.Feature(None, {'time': time_ms, index_name: -9999, 'reduce_error': 1}) # Return Feature marking error

    try:
        ts_info = indexed_collection.map(extract_value).getInfo() # Map safe extraction
    except ee.EEException as e: st.error(f"خطای GEE در استخراج سری زمانی: {e}"); return pd.DataFrame()
    except Exception as e: st.error(f"خطای ناشناخته در استخراج سری زمانی: {e}"); return pd.DataFrame()

    # Process results, filtering out reduce_error
    data = []
    if 'features' in ts_info:
        for feature in ts_info['features']:
            props = feature.get('properties', {})
            if props.get('reduce_error') == 1: continue # Skip if reduction failed
            value = props.get(index_name)
            time_ms = props.get('time')
            if value not in [None, -9999] and time_ms is not None:
                try: dt = datetime.datetime.fromtimestamp(time_ms / 1000.0); data.append([dt, value])
                except: pass
    if not data: return pd.DataFrame(columns=['Date', index_name])
    return pd.DataFrame(data, columns=['Date', index_name]).sort_values(by='Date').reset_index(drop=True)


# --- get_median_index_for_period ---
@st.cache_data(ttl=1800)
def get_median_index_for_period(_farms_df_json, start_date, end_date, index_name, sensor):
    farms_df = pd.read_json(_farms_df_json); farms_df_valid = farms_df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
    if farms_df_valid.empty: return pd.DataFrame(columns=['مزرعه', index_name])

    features = []
    for idx, row in farms_df_valid.iterrows():
        try: geom = ee.Geometry.Point([row['طول جغرافیایی'], row['عرض جغرافیایی']]).buffer(50); features.append(ee.Feature(geom, {'farm_id': row['مزرعه']}))
        except Exception as e: print(f"Skipping farm {row.get('مزرعه')} geom error: {e}")
    if not features: return pd.DataFrame(columns=['مزرعه', index_name])
    farm_fc = ee.FeatureCollection(features)

    base_collection = get_image_collection(start_date, end_date, farm_fc.geometry(), sensor)
    if base_collection is None: return pd.DataFrame(columns=['مزرعه', index_name])
    try:
        if base_collection.size().getInfo() == 0: print(f"No base images for median ({index_name})."); return pd.DataFrame(columns=['مزرعه', index_name])
    except ee.EEException as e: st.error(f"Error checking base size median: {e}"); return pd.DataFrame(columns=['مزرعه', index_name])


    indexed_collection = calculate_single_index(base_collection, index_name)
    if indexed_collection is None: return pd.DataFrame(columns=['مزرعه', index_name])
    try:
         if indexed_collection.size().getInfo() == 0: print(f"No indexed images for median ({index_name})."); return pd.DataFrame(columns=['مزرعه', index_name])
    except ee.EEException as e: st.error(f"Error checking indexed size median: {e}"); return pd.DataFrame(columns=['مزرعه', index_name])


    try:
        median_image = indexed_collection.median()
        if not median_image.bandNames().getInfo(): st.warning(f"Median calc failed for '{index_name}'.", icon="⚠️"); return pd.DataFrame(columns=['مزرعه', index_name])
    except ee.EEException as median_e: st.error(f"GEE Median error '{index_name}': {median_e}"); return pd.DataFrame(columns=['مزرعه', index_name])
    except Exception as e: st.error(f"Median error '{index_name}': {e}"); return pd.DataFrame(columns=['مزرعه', index_name])

    try:
        farm_values = median_image.reduceRegions(collection=farm_fc, reducer=ee.Reducer.mean(), scale=30, tileScale=8).getInfo()
    except ee.EEException as e: st.error(f"GEE reduceRegions error: {e}"); return pd.DataFrame(columns=['مزرعه', index_name])
    except Exception as e: st.error(f"reduceRegions error: {e}"); return pd.DataFrame(columns=['مزرعه', index_name])

    results_data = []
    if 'features' in farm_values:
        for feature in farm_values['features']:
            props = feature.get('properties', {}); farm_id = props.get('farm_id'); value = props.get('mean')
            if farm_id is not None and value is not None: results_data.append({'مزرعه': farm_id, index_name: value})
    if not results_data: return pd.DataFrame(columns=['مزرعه', index_name])
    return pd.DataFrame(results_data)


# --- get_weekly_comparison ---
@st.cache_data(ttl=1800)
def get_weekly_comparison(_filtered_df_json, start_date, end_date, index_name, sensor):
    if not isinstance(start_date, datetime.date) or not isinstance(end_date, datetime.date): st.error("تاریخ نامعتبر."); return pd.DataFrame()
    current_start = start_date; current_end = end_date
    prev_end = current_start - timedelta(days=1); prev_start = prev_end - timedelta(days=(end_date-start_date).days)
    print(f"Comparing: {current_start} to {current_end} vs {prev_start} to {prev_end}")

    df_current = get_median_index_for_period(_filtered_df_json, current_start, current_end, index_name, sensor)
    if df_current.empty: st.warning(f"داده دوره فعلی مقایسه نیست.", icon="⚠️"); return pd.DataFrame()
    df_previous = get_median_index_for_period(_filtered_df_json, prev_start, prev_end, index_name, sensor)
    if df_previous.empty: st.warning(f"داده دوره قبلی مقایسه نیست.", icon="⚠️"); return pd.DataFrame()

    df_comparison = pd.merge(df_previous.rename(columns={index_name: f'{index_name}_prev'}),
                           df_current.rename(columns={index_name: f'{index_name}_curr'}), on='مزرعه', how='inner')
    if df_comparison.empty: st.info("مزرعه مشترکی بین دو دوره نیست."); return pd.DataFrame()

    df_comparison['تغییر'] = df_comparison[f'{index_name}_curr'] - df_comparison[f'{index_name}_prev']
    df_comparison['درصد_تغییر'] = np.where(np.abs(df_comparison[f'{index_name}_prev']) > 1e-9, ((df_comparison['تغییر']/df_comparison[f'{index_name}_prev'])*100.0), np.nan)
    df_decreased = df_comparison[df_comparison['تغییر'] < 0].copy()
    df_decreased = df_decreased.sort_values(by='درصد_تغییر', ascending=True, na_position='last')
    return df_decreased


# --- Streamlit App Layout ---
st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")
st.title(f"🌾 {APP_TITLE}")
st.markdown("مانیتورینگ وضعیت مزارع نیشکر با استفاده از تصاویر ماهواره‌ای و Google Earth Engine")
st.divider()

if initialize_gee():
    farm_data_df = load_data(CSV_FILE_PATH)
    with st.sidebar:
        # --- Sidebar Controls ---
        st.header("⚙️ تنظیمات و فیلترها"); st.divider()
        st.subheader("🗓️ انتخاب بازه زمانی"); today = datetime.date.today(); default_start = today - timedelta(days=6)
        start_date = st.date_input("تاریخ شروع", value=default_start, max_value=today); end_date = st.date_input("تاریخ پایان", value=today, min_value=start_date, max_value=today)
        st.info(f"مدت دوره: {(end_date - start_date).days + 1} روز", icon="⏳"); st.divider()

        st.subheader("🔍 فیلتر داده‌ها")
        days_list = ["همه روزها"] + sorted(farm_data_df['روزهای هفته'].unique().tolist())
        selected_day = st.selectbox("روز هفته آبیاری", options=days_list)
        if selected_day == "همه روزها": filtered_df = farm_data_df.copy()
        else: filtered_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day].copy()
        st.caption(f"{len(filtered_df)} مزرعه انتخاب شد.")
        available_indices = list(INDEX_DEFINITIONS.keys())
        selected_index = st.selectbox("شاخص مورد تحلیل", options=available_indices, format_func=lambda x: INDEX_DEFINITIONS[x]['name_fa'])
        selected_sensor = st.radio("سنسور ماهواره", ('Sentinel-2', 'Landsat'), index=0, horizontal=True); st.divider()

        st.subheader("🚜 انتخاب مزرعه")
        farm_list = ["همه مزارع"] + sorted(filtered_df['مزرعه'].unique().tolist())
        selected_farm = st.selectbox("مزرعه خاص (یا همه)", options=farm_list); st.divider()

        st.header("ℹ️ راهنمای شاخص‌ها")
        index_to_explain = st.selectbox("مشاهده توضیحات شاخص:", options=list(INDEX_DEFINITIONS.keys()), index=available_indices.index(selected_index), format_func=lambda x: INDEX_DEFINITIONS[x]['name_fa'])
        if index_to_explain:
            with st.expander(f"جزئیات: {INDEX_DEFINITIONS[index_to_explain]['name_fa']}", expanded=False): st.markdown(INDEX_DEFINITIONS[index_to_explain]['desc_fa'], unsafe_allow_html=True)
        st.divider(); st.caption("v1.3 - GEE Dashboard")


    # --- Main Panel Tabs ---
    tab1, tab2, tab3 = st.tabs(["🗺️ نقشه و جزئیات", "📊 رتبه‌بندی مزارع", "📉 مقایسه هفتگی"])

    with tab1: # Map and Details
        col_map, col_detail = st.columns([2, 1])
        with col_map:
            st.subheader(f"نقشه: {INDEX_DEFINITIONS[selected_index]['name_fa']}")
            st.caption(f"{start_date.strftime('%Y-%m-%d')} تا {end_date.strftime('%Y-%m-%d')} | {selected_sensor}")
            map_placeholder = st.empty(); m = geemap.Map(center=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM); m.add_basemap('HYBRID')
            vis_params = INDEX_DEFINITIONS[selected_index]['vis']

            display_geom = None; target_object_for_map = None; farm_info_for_display = None
            display_df = filtered_df.copy()

            # Determine geometry (same logic as before)
            if selected_farm == "همه مزارع":
                display_df_valid = display_df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
                if not display_df_valid.empty:
                    try: min_lon, min_lat, max_lon, max_lat = display_df_valid['طول جغرافیایی'].min(), display_df_valid['عرض جغرافیایی'].min(), display_df_valid['طول جغرافیایی'].max(), display_df_valid['عرض جغرافیایی'].max(); display_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat]); target_object_for_map = display_geom
                    except Exception as e: st.error(f"خطای مرز: {e}")
                else: st.info("مزرعه‌ای با مختصات نیست.", icon="📍")
            else: # Single farm
                farm_info_rows = display_df[display_df['مزرعه'] == selected_farm]
                if not farm_info_rows.empty:
                    farm_info_for_display = farm_info_rows.iloc[0]; farm_lat = farm_info_for_display['عرض جغرافیایی']; farm_lon = farm_info_for_display['طول جغرافیایی']
                    if pd.notna(farm_lat) and pd.notna(farm_lon):
                        try: farm_geom = ee.Geometry.Point([farm_lon, farm_lat]); display_geom = farm_geom.buffer(150); target_object_for_map = farm_geom
                        except Exception as e: st.error(f"خطای نقطه: {e}"); farm_info_for_display = None
                    else: st.warning(f"مختصات نامعتبر: {selected_farm}.", icon="📍"); farm_info_for_display = None
                else: st.warning(f"اطلاعات مزرعه {selected_farm} نیست.", icon="⚠️")

            # Display Map Layer using Median Composite
            layer_added = False
            if display_geom:
                with st.spinner(f"پردازش نقشه '{selected_index}'..."):
                    base_collection = get_image_collection(start_date, end_date, display_geom, selected_sensor)
                    if base_collection is not None:
                        indexed_collection = calculate_single_index(base_collection, selected_index)
                        if indexed_collection is not None:
                            try:
                                median_image = indexed_collection.median()
                                if median_image.bandNames().getInfo():
                                    layer_image = median_image.clip(display_geom) if selected_farm != "همه مزارع" else median_image
                                    m.addLayer(layer_image, vis_params, f'{selected_index} (Median)')
                                    layer_added = True
                                    try: m.add_legend(title=f'{selected_index}', builtin_legend=None, **vis_params)
                                    except: pass
                                    # Add download button
                                    try:
                                        thumb_url = median_image.getThumbURL({'region': display_geom.toGeoJson(),'bands': selected_index,**vis_params,'dimensions': 512})
                                        response = requests.get(thumb_url)
                                        if response.status_code == 200:
                                            st.sidebar.download_button(label=f"📥 دانلود نقشه", data=BytesIO(response.content), file_name=f"map_{selected_farm if selected_farm!='همه مزارع' else 'all'}_{selected_index}.png", mime="image/png", key=f"dl_map_{selected_index}_{selected_farm}")
                                    except Exception as e: print(f"Thumbnail error: {e}")

                                else: st.warning(f"Median calc failed for '{selected_index}'.", icon="⚠️")
                            except ee.EEException as ee_err: st.error(f"GEE Map Layer Error: {ee_err}")
                            except Exception as err: st.error(f"Map Layer Error: {err}")

            # Add markers (logic remains same, uses cleaned 'سن')
            if layer_added:
                if selected_farm == "همه مزارع":
                    df_to_mark = display_df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
                    for idx, row in df_to_mark.iterrows():
                        area_str = f"{row.get('مساحت داشت', 'N/A'):.2f}" if pd.notna(row.get('مساحت داشت')) else "N/A"
                        popup_html = f"<b>{row['مزرعه']}</b><br>کانال:{row['کانال']}|اداره:{row['اداره']}<br>مساحت:{area_str}<br>واریته:{row['واریته']}|سن:{row['سن']}"
                        folium.Marker([row['عرض جغرافیایی'],row['طول جغرافیایی']], popup=popup_html, tooltip=f"{row['مزرعه']}", icon=folium.Icon(color='blue', icon='info-sign', prefix='fa')).add_to(m)
                elif farm_info_for_display is not None:
                    info = farm_info_for_display; area_str = f"{info.get('مساحت داشت', 'N/A'):.2f}" if pd.notna(info.get('مساحت داشت')) else "N/A"
                    popup_html = f"<b>{info['مزرعه']}</b><br>کانال:{info['کانال']}|اداره:{info['اداره']}<br>مساحت:{area_str}<br>واریته:{info['واریته']}|سن:{info['سن']}"
                    folium.Marker([info['عرض جغرافیایی'],info['طول جغرافیایی']], popup=popup_html, tooltip=f"{info['مزرعه']}", icon=folium.Icon(color='red', icon='star', prefix='fa')).add_to(m)

            if target_object_for_map:
                zoom = INITIAL_ZOOM + 2 if selected_farm != "همه مزارع" else INITIAL_ZOOM
                try: m.center_object(target_object_for_map, zoom=zoom)
                except: m.set_center(INITIAL_LON, INITIAL_LAT, INITIAL_ZOOM)
            else: st.info("هندسه معتبری برای نمایش نقشه نیست.", icon="🗺️")

            with map_placeholder: m.to_streamlit(height=550)

        with col_detail: # Farm Details & Timeseries
            if selected_farm != "همه مزارع":
                st.subheader(f" جزئیات: {selected_farm}"); st.divider()
                if farm_info_for_display is not None:
                    info = farm_info_for_display
                    st.metric("کانال", str(info.get('کانال','N/A'))); st.metric("اداره", str(info.get('اداره','N/A')))
                    st.metric("مساحت (هکتار)", f"{info['مساحت داشت']:.2f}" if pd.notna(info.get('مساحت داشت')) else "N/A")
                    st.metric("واریته", str(info.get('واریته','N/A'))); st.metric("سن", str(info.get('سن','N/A'))) # Use cleaned 'سن'
                    st.metric("روز آبیاری", str(info.get('روزهای هفته','N/A'))); st.divider()
                    st.subheader(f"📈 روند: {INDEX_DEFINITIONS[selected_index]['name_fa']}")
                    if pd.notna(info.get('عرض جغرافیایی')) and pd.notna(info.get('طول جغرافیایی')):
                        with st.spinner(f"دریافت سری زمانی..."):
                            try: farm_geom_ts = ee.Geometry.Point([info['طول جغرافیایی'], info['عرض جغرافیایی']]); ts_df = get_timeseries_for_farm(farm_geom_ts.toGeoJsonString(), start_date, end_date, selected_index, selected_sensor)
                            except: ts_df = pd.DataFrame()
                        if not ts_df.empty:
                            fig_ts = px.line(ts_df, x='Date', y=selected_index, title=f"روند زمانی {selected_index}", markers=True, labels={'Date':'تاریخ', selected_index:f'مقدار'})
                            fig_ts.update_layout(title_x=0.5); fig_ts.update_traces(line={'color':'royalblue'}, marker={'color':'salmon'})
                            st.plotly_chart(fig_ts, use_container_width=True)
                    else: st.warning("مختصات نامعتبر.", icon="📍")
                else: st.info("اطلاعات مزرعه نیست.")
            else: st.subheader("راهنمای جزئیات"); st.info("یک مزرعه خاص را انتخاب کنید.", icon="👈")

    with tab2: # Ranking
        st.subheader(f"📊 رتبه‌بندی: {INDEX_DEFINITIONS[selected_index]['name_fa']}")
        st.caption(f"{start_date.strftime('%Y-%m-%d')} تا {end_date.strftime('%Y-%m-%d')} | روز: '{selected_day}' | {selected_sensor}"); st.divider()
        if filtered_df.empty: st.warning(f"مزرعه‌ای برای روز '{selected_day}' نیست.", icon="⚠️")
        else:
            with st.spinner(f"محاسبه رتبه‌بندی..."):
                ranking_df = get_median_index_for_period(filtered_df.to_json(), start_date, end_date, selected_index, sensor=selected_sensor)
            if not ranking_df.empty:
                ascending_sort = INDEX_DEFINITIONS[selected_index].get('sort_ascending', False)
                ranking_df_sorted = ranking_df.sort_values(by=selected_index, ascending=ascending_sort, na_position='last').reset_index(drop=True)
                st.dataframe(ranking_df_sorted.style.format({selected_index: "{:.3f}"}).bar(subset=[selected_index], color='lightcoral' if ascending_sort else 'lightgreen', align='zero'), use_container_width=True)
                csv_rank = ranking_df_sorted.to_csv(index=False).encode('utf-8'); st.download_button(label=f"📥 دانلود رتبه‌بندی", data=csv_rank, file_name=f'ranking_{selected_index}_{selected_day}.csv', mime='text/csv', key='dl_rank')
            else: st.warning(f"اطلاعاتی برای رتبه‌بندی یافت نشد.", icon="📊")
        st.divider()

    with tab3: # Weekly Comparison
        st.subheader(f"📉 مقایسه هفتگی (کاهش): {INDEX_DEFINITIONS[selected_index]['name_fa']}")
        st.caption(f"مقایسه دوره جاری با هفته قبل | روز: '{selected_day}' | {selected_sensor}"); st.divider()
        if filtered_df.empty: st.warning(f"مزرعه‌ای برای روز '{selected_day}' نیست.", icon="⚠️")
        else:
            with st.spinner(f"مقایسه داده‌های هفتگی..."):
                comparison_df_decreased = get_weekly_comparison(filtered_df.to_json(), start_date, end_date, selected_index, selected_sensor)
            if not comparison_df_decreased.empty:
                st.markdown("##### مزارع با کاهش شاخص:"); display_cols = ['مزرعه', f'{index_name}_prev', f'{index_name}_curr', 'تغییر', 'درصد_تغییر']
                st.dataframe(comparison_df_decreased[display_cols].style.format({f'{index_name}_prev': "{:.3f}", f'{index_name}_curr': "{:.3f}", 'تغییر': "{:+.3f}", 'درصد_تغییر': "{:+.1f}%"})
                                     .applymap(lambda x: 'color: red' if isinstance(x,(int,float)) and x<0 else ('color: green' if isinstance(x,(int,float)) and x>0 else 'color: black'), subset=['تغییر','درصد_تغییر']), use_container_width=True)
                st.divider(); st.markdown("##### نمودار مقایسه‌ای:")
                fig_comp = go.Figure(); fig_comp.add_trace(go.Bar(x=comparison_df_decreased['مزرعه'], y=comparison_df_decreased[f'{index_name}_prev'], name='هفته قبل', marker_color='dodgerblue', text=comparison_df_decreased[f'{index_name}_prev'].round(3), textposition='auto'))
                fig_comp.add_trace(go.Bar(x=comparison_df_decreased['مزرعه'], y=comparison_df_decreased[f'{index_name}_curr'], name='هفته جاری', marker_color='lightcoral', text=comparison_df_decreased[f'{index_name}_curr'].round(3), textposition='auto'))
                fig_comp.update_layout(barmode='group', title=f'مقایسه شاخص {selected_index} (کاهش)', xaxis_title='مزرعه', yaxis_title=f'مقدار {selected_index}', legend_title='دوره', hovermode="x unified", title_x=0.5)
                st.plotly_chart(fig_comp, use_container_width=True); st.divider()
                csv_comp = comparison_df_decreased.to_csv(index=False).encode('utf-8'); st.download_button(label=f"📥 دانلود مقایسه", data=csv_comp, file_name=f'comparison_decrease_{selected_index}_{selected_day}.csv', mime='text/csv', key='dl_comp')
            else: st.success(f"✅ عدم کاهش: موردی یافت نشد یا داده کافی برای مقایسه نبود.")

else:
    st.error("اتصال به Google Earth Engine ناموفق بود.", icon="🚨")