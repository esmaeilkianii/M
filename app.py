# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
from folium.plugins import Draw, MiniMap, Fullscreen, MeasureControl
import plotly.express as px
import json
from datetime import date, timedelta, datetime
import os
import io # Required for StringIO
import base64 # For map download

# ==============================================================================
# Configuration and Constants
# ==============================================================================
APP_TITLE = "داشبورد مانیتورینگ مزارع نیشکر - شرکت دهخدا"
INITIAL_LATITUDE = 31.534442
INITIAL_LONGITUDE = 48.724416
INITIAL_ZOOM = 11
DEFAULT_DAYS = 7 # Default analysis period

# Define standard color palettes for indices (adjust min/max as needed)
INDEX_VIS_PARAMS = {
    'NDVI': {'min': 0, 'max': 1, 'palette': '006400, FFFF00, FF0000'}, # Green, Yellow, Red
    'NDMI': {'min': -1, 'max': 1, 'palette': 'FF0000, FFFF00, 0000FF'}, # Red, Yellow, Blue (Dry to Wet)
    'EVI': {'min': 0, 'max': 1, 'palette': '006400, FFFF00, FF0000'}, # Green, Yellow, Red
    'LAI': {'min': 0, 'max': 8, 'palette': 'FFFFFF, CE7E45, DF923D, F1B555, FCD163, 99B718, 74A901, 66A000, 529400, 3E8601, 207401, 056201, 004C00, 023B01, 012E01, 011D01, 011301'}, # Standard LAI palette
    'MSI': {'min': 0, 'max': 3, 'palette': 'FF0000, FFFF00, 0000FF'}  # Example palette for Moisture Stress Index
}

# Interpretation ranges (Example - adjust based on expert knowledge)
INDEX_INTERPRETATION = {
    'NDVI': {'بحرانی': (0, 0.3), 'متوسط': (0.3, 0.6), 'خوب': (0.6, 1)},
    'NDMI': {'بحرانی': (-1, 0), 'متوسط': (0, 0.4), 'خوب': (0.4, 1)}, # Higher is wetter
    'EVI': {'بحرانی': (0, 0.2), 'متوسط': (0.2, 0.5), 'خوب': (0.5, 1)},
    'LAI': {'بحرانی': (0, 1), 'متوسط': (1, 3), 'خوب': (3, 8)},
    'MSI': {'بحرانی': (1, 3), 'متوسط': (0.5, 1), 'خوب': (0, 0.5)} # Lower is better (less stress)
}

# ==============================================================================
# Embedded CSV Data
# ==============================================================================
# !!! مهم: محتوای کامل فایل output (1).csv خود را در اینجا کپی و جایگزین کنید !!!
# مطمئن شوید که خط اول (هدر) و تمام ردیف‌های داده را شامل می‌شود.
# مثال (این را با داده واقعی خود جایگزین کنید):
EMBEDDED_CSV_DATA = """مزرعه,طول جغرافیایی,عرض جغرافیایی,کانال,اداره,مساحت داشت,واریته,سن,روزهای هفته,coordinates_missing
Farm1,48.724416,31.534442,C1,Admin1,100,V1,2,شنبه,FALSE
Farm2,48.730000,31.540000,C2,Admin1,150,V2,1,یکشنبه,FALSE
Farm3,48.715000,31.530000,C1,Admin2,120,V1,3,دوشنبه,FALSE
Farm4,48.740000,31.550000,C3,Admin2,200,V3,1,شنبه,FALSE
"""
# !!! پایان بخش داده‌های CSV !!!

# ==============================================================================
# Google Earth Engine Functions
# ==============================================================================

@st.cache_resource(show_spinner="در حال اتصال به Google Earth Engine...")
def get_ee_credentials(_service_account_file):
    """Authenticates to Earth Engine using service account credentials."""
    try:
        # Check if the file path exists
        if not os.path.exists(_service_account_file):
            st.error(f"فایل Service Account در مسیر مشخص شده یافت نشد: {_service_account_file}")
            st.error(f"لطفاً فایل `{os.path.basename(_service_account_file)}` را در دایرکتوری صحیح (کنار فایل پایتون) قرار دهید یا مسیر آن را در کد اصلاح کنید.")
            return None

        # Load credentials from the file
        with open(_service_account_file) as f:
            credentials_dict = json.load(f)
        # Use the client_email from the file itself for credentials
        credentials = ee.ServiceAccountCredentials(credentials_dict['client_email'], _service_account_file)
        ee.Initialize(credentials)
        st.success("اتصال به Google Earth Engine با موفقیت انجام شد.")
        return ee # Return the authenticated ee object
    except ee.EEException as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.error("جزئیات خطا: ممکن است مشکل از فایل Credential، محتوای آن یا دسترسی‌های حساب سرویس باشد.")
        return None
    except FileNotFoundError:
        st.error(f"فایل Service Account یافت نشد: {_service_account_file}")
        st.error(f"لطفاً فایل `{os.path.basename(_service_account_file)}` را در کنار اسکریپت پایتون قرار دهید.")
        return None
    except json.JSONDecodeError:
        st.error(f"خطا در خواندن فایل JSON ({_service_account_file}). لطفاً محتوای فایل را بررسی کنید.")
        return None
    except Exception as e:
        st.error(f"یک خطای غیرمنتظره در زمان اتصال به GEE رخ داد: {e}")
        return None

# --- Cloud Masking ---
def mask_s2_clouds(image):
    """Masks clouds in Sentinel-2 imagery."""
    qa = image.select('QA60')
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0) \
             .And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000) # Scale factor for S2

def mask_landsat_clouds(image):
    """Masks clouds in Landsat 8/9 imagery using the QA_PIXEL band."""
    qa_pixel = image.select('QA_PIXEL')
    # Bits 3 (Cloud Shadow), 4 (Snow), and 5 (Cloud) should be clear.
    cloud_shadow_bit = 1 << 3
    snow_bit = 1 << 4
    cloud_bit = 1 << 5
    mask = qa_pixel.bitwiseAnd(cloud_shadow_bit).eq(0) \
                   .And(qa_pixel.bitwiseAnd(snow_bit).eq(0)) \
                   .And(qa_pixel.bitwiseAnd(cloud_bit).eq(0))
    # Apply scaling factors for Landsat 8/9 Collection 2 Surface Reflectance
    optical_bands = image.select('SR_B.').multiply(0.0000275).add(-0.2)
    thermal_bands = image.select('ST_B.*').multiply(0.00341802).add(149.0) # If needed
    return image.addBands(optical_bands, None, True).addBands(thermal_bands, None, True).updateMask(mask)


# --- Index Calculation Functions ---
def add_ndvi(image):
    """Calculates NDVI."""
    nir = image.select(['SR_B5', 'B8'], ['NIR']).max() # Select available NIR band
    red = image.select(['SR_B4', 'B4'], ['Red']).max() # Select available Red band
    ndvi = image.expression(
        '(NIR - Red) / (NIR + Red)', {
            'NIR': nir,
            'Red': red
        }).rename('NDVI').unmask(0) # Use unmask(0) to avoid issues with fully masked pixels if needed
    return image.addBands(ndvi)

def add_ndmi(image):
    """Calculates NDMI."""
    nir = image.select(['SR_B5', 'B8'], ['NIR']).max()
    swir1 = image.select(['SR_B6', 'B11'], ['SWIR1']).max()
    ndmi = image.expression(
        '(NIR - SWIR1) / (NIR + SWIR1)', {
            'NIR': nir,
            'SWIR1': swir1
        }).rename('NDMI').unmask(0)
    return image.addBands(ndmi)

def add_evi(image):
    """Calculates EVI."""
    nir = image.select(['SR_B5', 'B8'], ['NIR']).max()
    red = image.select(['SR_B4', 'B4'], ['Red']).max()
    blue = image.select(['SR_B2', 'B2'], ['Blue']).max()
    # Add small epsilon to denominator to avoid division by zero
    evi = image.expression(
        '2.5 * ((NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1.0001))', {
            'NIR': nir,
            'Red': red,
            'Blue': blue
        }).rename('EVI').unmask(0)
    return image.addBands(evi)

def add_lai_simple(image):
    """Estimates LAI from NDVI (Simple empirical formula - needs calibration)."""
    a = 0.57 # Example coefficient
    b = 2.23 # Example coefficient
    ndvi = image.select('NDVI') # Assumes NDVI is already calculated
    lai = ndvi.expression(
        'a * exp(b * NDVI)', {'a': a, 'b': b, 'NDVI': ndvi}
    ).rename('LAI').unmask(0)
    # Clip LAI to reasonable bounds
    lai = lai.where(lai.lt(0), 0).where(lai.gt(8), 8)
    return image.addBands(lai)

def add_msi(image):
    """Calculates MSI."""
    swir1 = image.select(['SR_B6', 'B11'], ['SWIR1']).max()
    nir = image.select(['SR_B5', 'B8'], ['NIR']).max()
    # Add small epsilon to avoid division by zero
    msi = image.expression(
        'SWIR1 / (NIR + 0.0001)', {
            'SWIR1': swir1,
            'NIR': nir
        }).rename('MSI').unmask(0)
    return image.addBands(msi)

# --- Main Data Fetching and Processing ---
@st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", ttl=3600) # Cache for 1 hour
def get_satellite_data(_start_date_str, _end_date_str, _aoi, _indices_to_calculate):
    """
    Fetches, processes satellite data, calculates indices, and creates weekly composites.
    Uses caching based on inputs. GEE objects passed as arguments should have '_' prefix.
    """
    try:
        start_date = ee.Date(_start_date_str)
        end_date = ee.Date(_end_date_str)
        # Ensure _aoi is a GeoJSON-like dictionary before converting
        if not isinstance(_aoi, dict) or 'type' not in _aoi or 'features' not in _aoi:
             st.error(" ساختار AOI نامعتبر است. باید GeoJSON FeatureCollection باشد.")
             return None, None
        aoi_ee = geemap.geojson_to_ee(_aoi)

        # --- Collections ---
        s2_sr = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(aoi_ee).filterDate(start_date, end_date).map(mask_s2_clouds)
        l8_sr = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').filterBounds(aoi_ee).filterDate(start_date, end_date).map(mask_landsat_clouds)
        l9_sr = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2').filterBounds(aoi_ee).filterDate(start_date, end_date).map(mask_landsat_clouds)

        # --- Index Calculation ---
        def calculate_indices(image):
            img_with_indices = image
            # Calculate NDVI first if needed by others
            if 'NDVI' in _indices_to_calculate or 'LAI' in _indices_to_calculate:
                img_with_indices = add_ndvi(img_with_indices)
            if 'NDMI' in _indices_to_calculate:
                img_with_indices = add_ndmi(img_with_indices)
            if 'EVI' in _indices_to_calculate:
                img_with_indices = add_evi(img_with_indices)
            if 'LAI' in _indices_to_calculate:
                 img_with_indices = add_lai_simple(img_with_indices) # Assumes NDVI is present
            if 'MSI' in _indices_to_calculate:
                img_with_indices = add_msi(img_with_indices)
            return img_with_indices.addBands(ee.Image.constant(image.date().millis()).long().rename('timestamp'))

        s2_processed = s2_sr.map(calculate_indices)
        l8_processed = l8_sr.map(calculate_indices)
        l9_processed = l9_sr.map(calculate_indices)

        # Merge collections (consider potential band name conflicts if not handled in index functions)
        merged_collection = ee.ImageCollection(s2_processed.merge(l9_processed).merge(l8_processed)) \
                               .select(_indices_to_calculate + ['timestamp']) \
                               .sort('system:time_start')

        # --- Weekly Median Composite ---
        date_diff = end_date.difference(start_date, 'day')
        num_weeks = date_diff.divide(7).ceil().getInfo()
        if num_weeks == 0: num_weeks = 1

        weekly_composites = []
        composite_dates = []

        for i in range(num_weeks):
            week_start = start_date.advance(i * 7, 'day')
            week_end = week_start.advance(7, 'day')
            if week_end.millis().getInfo() > end_date.millis().getInfo():
                week_end = end_date

            weekly_data = merged_collection.filterDate(week_start, week_end)
            if weekly_data.size().getInfo() > 0:
                median_composite = weekly_data.median().set('system:time_start', week_start.millis())
                weekly_composites.append(median_composite)
                composite_dates.append(week_start.format('YYYY-MM-dd').getInfo())

        if not weekly_composites:
            st.warning("هیچ داده ماهواره‌ای معتبری در بازه زمانی و منطقه انتخابی یافت نشد.")
            return None, None

        composite_collection = ee.ImageCollection.fromImages(weekly_composites)
        return composite_collection, composite_dates

    except ee.EEException as e:
        st.error(f"خطای Google Earth Engine در زمان پردازش داده: {e}")
        return None, None
    except Exception as e:
        st.error(f"خطای غیرمنتظره در زمان پردازش داده‌های ماهواره‌ای: {e}")
        return None, None


@st.cache_data(show_spinner="در حال محاسبه آمار مزارع...", ttl=3600)
def get_zonal_statistics(_composite_collection, _farm_features, _indices, _farm_id_col='مزرعه'):
    """Calculates zonal statistics (mean) for each farm feature over the composite collection."""
    if _composite_collection is None or not _farm_features:
        st.warning("داده‌های ترکیبی یا ویژگی‌های مزرعه برای محاسبه آمار در دسترس نیست.")
        return None

    # Ensure _farm_features is a list of GeoJSON features
    if not isinstance(_farm_features, list):
         st.error("ساختار ویژگی‌های مزرعه نامعتبر است. باید لیستی از GeoJSON Features باشد.")
         return None

    farm_polygons_ee = geemap.geojson_to_ee({
        "type": "FeatureCollection",
        "features": _farm_features # Expects a list of features here
    })

    def extract_stats(image):
        image_date = ee.Date(image.get('system:time_start')).format('YYYY-MM-dd')
        # Ensure image has bands before reducing
        img_bands = image.bandNames()
        indices_present = ee.List(_indices).filter(ee.Filter.inList('item', img_bands))

        # Reduce only if there are indices present in the image
        def reduce_image():
            stats = image.select(indices_present).reduceRegions(
                collection=farm_polygons_ee,
                reducer=ee.Reducer.mean(),
                scale=30
            )
            def add_date(feature):
                return feature.set('date', image_date)
            return stats.map(add_date)

        # Return empty FeatureCollection if no indices to reduce
        def empty_fc():
             return ee.FeatureCollection([])

        return ee.Algorithms.If(indices_present.size().gt(0), reduce_image(), empty_fc())


    try:
        # Map over the collection and flatten the results
        results = _composite_collection.map(extract_stats).flatten()

        # Check size before getting info
        if results.size().getInfo() == 0:
             st.warning("هیچ نتیجه آماری پس از پردازش به دست نیامد.")
             return None

        stats_list = results.getInfo()['features']

        # Convert to Pandas DataFrame
        data = []
        for feature in stats_list:
            props = feature['properties']
            # Ensure the farm ID column exists in the properties
            if _farm_id_col not in props:
                # st.warning(f"ویژگی بدون ستون شناسایی '{_farm_id_col}' یافت شد، نادیده گرفته می‌شود.")
                continue
            row = {
                _farm_id_col: props.get(_farm_id_col),
                'date': props.get('date')
            }
            for index in _indices:
                row[index] = props.get(index) # Will be None if index not calculated/present
            data.append(row)

        if not data:
            st.warning("داده آماری برای مزارع محاسبه نشد (ممکن است به دلیل عدم وجود شاخص‌ها در تصاویر باشد).")
            return None

        stats_df = pd.DataFrame(data)
        stats_df['date'] = pd.to_datetime(stats_df['date'])
        return stats_df.dropna(subset=[_farm_id_col]) # Drop rows where farm ID is missing

    except ee.EEException as e:
        st.error(f"خطا در محاسبه آمار منطقه‌ای (Zonal Statistics): {e}")
        # Try to provide more context if possible
        if "Parameter 'collection' is required" in str(e):
             st.error("خطای احتمالی: ممکن است ویژگی‌های مزرعه (farm_features) به درستی به GEE ارسال نشده باشند.")
        elif "computation timed out" in str(e).lower():
             st.error("خطای احتمالی: محاسبه برای منطقه یا دوره زمانی بزرگ زمان‌بر بوده است. سعی کنید بازه زمانی را کوتاه‌تر کنید.")
        return None
    except Exception as e:
        st.error(f"خطای غیرمنتظره در محاسبه آمار منطقه‌ای: {e}")
        return None

# ==============================================================================
# Helper Functions
# ==============================================================================

# Modified to load data from the embedded string
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_data_from_string(csv_data_string):
    """Loads farm data from an embedded CSV string."""
    if not csv_data_string or len(csv_data_string.strip()) == 0:
        st.error("داده‌های CSV جاسازی شده خالی است.")
        return None
    try:
        # Use io.StringIO to treat the string as a file
        data_io = io.StringIO(csv_data_string)
        df = pd.read_csv(data_io)

        # Basic validation (using the provided column names)
        # Handle potential BOM in the first column name
        if df.columns[0].startswith('\ufeff'):
            df.rename(columns={df.columns[0]: df.columns[0].lstrip('\ufeff')}, inplace=True)

        required_cols = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته']
        if not all(col in df.columns for col in required_cols):
            st.error(f"داده‌های CSV جاسازی شده باید شامل ستون‌های ضروری باشد: {', '.join(required_cols)}")
            missing_cols = [col for col in required_cols if col not in df.columns]
            st.error(f"ستون‌های یافت نشده: {', '.join(missing_cols)}")
            return None

        # Convert coordinate columns to numeric, coercing errors
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')

        # Handle potential errors and drop rows with invalid coordinates
        initial_rows = len(df)
        df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'], inplace=True)
        dropped_rows = initial_rows - len(df)
        if dropped_rows > 0:
            st.warning(f"{dropped_rows} ردیف به دلیل مختصات نامعتبر یا خالی حذف شد.")

        if df.empty:
            st.error("هیچ ردیف معتبری با مختصات صحیح در داده‌های CSV یافت نشد.")
            return None

        # Ensure 'روزهای هفته' is string
        df['روزهای هفته'] = df['روزهای هفته'].astype(str).fillna('نامشخص') # Fill NaNs

        # Convert other columns to appropriate types (example)
        if 'مساحت داشت' in df.columns:
            df['مساحت داشت'] = pd.to_numeric(df['مساحت داشت'], errors='coerce')
        if 'سن' in df.columns:
            df['سن'] = pd.to_numeric(df['سن'], errors='coerce') # Keep as numeric if possible

        return df
    except pd.errors.EmptyDataError:
        st.error("خطا: داده‌های CSV جاسازی شده خالی یا نامعتبر است.")
        return None
    except Exception as e:
        st.error(f"خطا در بارگذاری یا پردازش داده‌های CSV جاسازی شده: {e}")
        return None

def df_to_geojson(df, lat_col='عرض جغرافیایی', lon_col='طول جغرافیایی'):
    """Converts a DataFrame to GeoJSON FeatureCollection (Points)."""
    features = []
    # Ensure input is a DataFrame
    if not isinstance(df, pd.DataFrame):
        st.error("ورودی به df_to_geojson باید DataFrame باشد.")
        return {"type": "FeatureCollection", "features": []}

    for _, row in df.iterrows():
        try:
            # Check for valid coordinates
            lon = float(row[lon_col])
            lat = float(row[lat_col])
            if pd.isna(lon) or pd.isna(lat):
                # st.warning(f"مختصات نامعتبر برای مزرعه {row.get('مزرعه', 'N/A')}، نادیده گرفته شد.")
                continue

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "properties": row.to_dict() # Include all other columns as properties
            }
            # Convert non-serializable types like Timestamp to string if necessary
            for key, value in feature["properties"].items():
                if isinstance(value, pd.Timestamp):
                    feature["properties"][key] = str(value)
                elif pd.isna(value): # Convert NaN to None for JSON compatibility
                     feature["properties"][key] = None
                # Add more type checks if needed (e.g., numpy types)

            features.append(feature)
        except (ValueError, TypeError, KeyError) as e:
            st.warning(f"خطا در تبدیل ردیف به GeoJSON (مزرعه: {row.get('مزرعه', 'N/A')}): {e}. این ردیف نادیده گرفته شد.")
            continue # Skip rows with conversion errors

    return {"type": "FeatureCollection", "features": features}


def get_week_dates(n_weeks=1):
    """Gets the start and end dates for the last n weeks."""
    today = date.today()
    end_date = today
    start_date = today - timedelta(days=(n_weeks * 7) -1)
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def get_previous_week_dates(current_start_str, current_end_str):
    """Gets the start and end dates for the week prior to the given range."""
    current_end = datetime.strptime(current_end_str, '%Y-%m-%d').date()
    prev_end_date = current_end - timedelta(days=7)
    prev_start_date = prev_end_date - timedelta(days=6)
    return prev_start_date.strftime('%Y-%m-%d'), prev_end_date.strftime('%Y-%m-%d')


def get_index_interpretation(index_name, value):
    """Returns the interpretation (Good, Medium, Critical) for an index value."""
    if pd.isna(value):
        return "نامشخص"
    ranges = INDEX_INTERPRETATION.get(index_name)
    if not ranges:
        return "نامشخص"
    for level, (low, high) in ranges.items():
        if low <= value <= high:
            return level
    return "خارج از محدوده"


def style_rank_table(df_to_style):
    """Applies styling to the ranking table based on weekly change."""
    # Ensure 'تغییر هفتگی' column exists
    if 'تغییر هفتگی' not in df_to_style.columns:
        return df_to_style # Return original if no change column

    def highlight_change(row):
        color = ''
        change_val = row['تغییر هفتگی']
        # Define thresholds for significant change
        threshold_pos = 0.015 # Adjust as needed
        threshold_neg = -0.015 # Adjust as needed

        if pd.notna(change_val):
            if change_val > threshold_pos:
                color = 'background-color: lightgreen' # Improvement
            elif change_val < threshold_neg:
                color = 'background-color: lightcoral' # Decline
        # Apply to the whole row
        return [color] * len(row)

    try:
        # Apply styling
        # Use format to control decimal places for numeric columns
        format_dict = {
            'میانگین اخیر': '{:.3f}',
            'میانگین قبل': '{:.3f}',
            'تغییر هفتگی': '{:+.3f}' # Add sign to change
        }
        # Check which columns actually exist before formatting
        valid_format_dict = {k: v for k, v in format_dict.items() if k in df_to_style.columns}

        styled = df_to_style.style.apply(highlight_change, axis=1).format(valid_format_dict, na_rep="-")
        return styled
    except Exception as e:
        st.warning(f"خطا در استایل‌دهی جدول رتبه‌بندی: {e}")
        return df_to_style # Return unstyled on error


def map_to_png_bytes(m):
    """Saves a folium map to PNG bytes for download."""
    try:
        img_data = m._to_png(5) # Use internal method with delay
        img_bytes = io.BytesIO(img_data)
        return img_bytes.getvalue()
    except Exception as e:
        st.error(f"خطا در تبدیل نقشه به PNG: {e}")
        return None

def get_image_download_link(img_bytes, filename="map.png", text="دانلود نقشه (PNG)"):
    """Generates a download link for image bytes."""
    if img_bytes is None:
        return ""
    b64 = base64.b64encode(img_bytes).decode()
    href = f'<a href="data:image/png;base64,{b64}" download="{filename}">{text}</a>'
    return href

# ==============================================================================
# Streamlit App UI
# ==============================================================================

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

# --- Sidebar Controls ---
st.sidebar.header("تنظیمات نمایش")

# 1. GEE Authentication File Path (Updated)
# Ensure this file is in the same directory as the script
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'

# Attempt GEE authentication
ee_authenticated = get_ee_credentials(SERVICE_ACCOUNT_FILE)

if not ee_authenticated:
    st.sidebar.error("اتصال به Google Earth Engine برقرار نشد. لطفاً خطاها را بررسی کنید و مطمئن شوید فایل JSON معتبر و در مسیر صحیح قرار دارد.")
    st.stop() # Stop execution if GEE connection fails

# 2. Load Embedded CSV Data (No Uploader)
farm_data_df = load_data_from_string(EMBEDDED_CSV_DATA)
farm_geojson = None

if farm_data_df is None:
    st.error("بارگذاری داده‌های مزارع از کد ناموفق بود. لطفاً محتوای متغیر EMBEDDED_CSV_DATA را در کد بررسی کنید.")
    st.stop() # Stop if farm data loading fails
else:
    farm_geojson = df_to_geojson(farm_data_df)
    if not farm_geojson or not farm_geojson['features']:
         st.error("تبدیل داده‌های مزرعه به GeoJSON ناموفق بود یا هیچ ویژگی معتبری یافت نشد.")
         st.stop()
    st.sidebar.success(f"{len(farm_data_df)} مزرعه با موفقیت از کد بارگذاری شد.")


# 3. Date Range Selection
st.sidebar.subheader("۱. بازه زمانی تحلیل") # Renumbered
default_start, default_end = get_week_dates(n_weeks=1) # Default to last 7 days

start_date_input = st.sidebar.date_input("تاریخ شروع", value=datetime.strptime(default_start, '%Y-%m-%d').date(), key="start_date")
end_date_input = st.sidebar.date_input("تاریخ پایان", value=datetime.strptime(default_end, '%Y-%m-%d').date(), key="end_date")

start_date_str = start_date_input.strftime('%Y-%m-%d')
end_date_str = end_date_input.strftime('%Y-%m-%d')

# Validate date range
if start_date_input > end_date_input:
    st.sidebar.error("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد.")
    st.stop()

# Calculate previous week dates for comparison
prev_start_str, prev_end_str = get_previous_week_dates(start_date_str, end_date_str)

# 4. Index Selection
st.sidebar.subheader("۲. انتخاب شاخص برای نمایش") # Renumbered
available_indices = list(INDEX_VIS_PARAMS.keys())
selected_index = st.sidebar.selectbox("شاخص مورد نظر را انتخاب کنید:", available_indices, index=0) # Default to NDVI

# 5. Day of the Week Filter
st.sidebar.subheader("۳. فیلتر بر اساس روز هفته") # Renumbered
if 'روزهای هفته' in farm_data_df.columns:
    unique_days = sorted(farm_data_df['روزهای هفته'].unique())
    day_options = ['همه روزها'] + unique_days
    selected_day = st.sidebar.selectbox("روز هفته را انتخاب کنید:", day_options, index=0) # Default to 'All Days'
else:
    st.sidebar.warning("ستون 'روزهای هفته' در داده‌های CSV یافت نشد. فیلتر روز غیرفعال است.")
    selected_day = 'همه روزها' # Default to all if column missing
    filtered_farm_df = farm_data_df # No filtering possible

# --- Filter farm data based on selected day ---
if selected_day == 'همه روزها' or 'روزهای هفته' not in farm_data_df.columns:
    filtered_farm_df = farm_data_df
else:
    filtered_farm_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day]

if filtered_farm_df.empty:
    st.warning(f"هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
    filtered_farm_geojson = {"type": "FeatureCollection", "features": []}
else:
    # Convert only the filtered DataFrame to GeoJSON for map display
    filtered_farm_geojson = df_to_geojson(filtered_farm_df)

# Define Area of Interest (AOI) based on ALL farms for fetching satellite data
aoi_geojson = farm_geojson # Use all farms for satellite data query bounds


# --- Main Panel ---
# Check if essential data is available before proceeding
if farm_data_df is not None and farm_geojson and aoi_geojson and farm_geojson['features']:

    st.header("نقشه تعاملی مزارع و شاخص‌ها")
    map_col, download_col = st.columns([4, 1])

    # --- Fetch and Process Satellite Data ---
    composite_collection, composite_dates = get_satellite_data(
        start_date_str,
        end_date_str,
        aoi_geojson, # Use AOI covering all farms
        available_indices # Calculate all available indices
    )

    # --- Calculate Zonal Statistics ---
    # Calculate stats for the current period using ALL farm features
    farm_stats_df = get_zonal_statistics(
        composite_collection,
        farm_geojson['features'], # Use all farms for stats calculation
        available_indices,
        _farm_id_col='مزرعه'
    )

    # Calculate stats for the previous week for comparison
    prev_composite_collection, _ = get_satellite_data(
        prev_start_str,
        prev_end_str,
        aoi_geojson,
        [selected_index] # Only need the selected index for comparison
    )
    prev_farm_stats_df = get_zonal_statistics(
        prev_composite_collection,
        farm_geojson['features'],
        [selected_index],
        _farm_id_col='مزرعه'
    )


    # --- Initialize Map ---
    m = geemap.Map(
        location=[INITIAL_LATITUDE, INITIAL_LONGITUDE],
        zoom=INITIAL_ZOOM,
        add_google_map=False
    )
    m.add_basemap("SATELLITE")
    m.add_basemap("ROADMAP")


    # --- Add Data Layers to Map ---
    latest_composite_date_str = "نامشخص" # Default value
    if composite_collection and selected_index in available_indices:
        try:
            # Check if the collection is not empty before proceeding
            collection_size = composite_collection.size().getInfo()
            if collection_size > 0:
                latest_composite = composite_collection.sort('system:time_start', False).first()
                # Safely get the date
                time_start_info = latest_composite.get('system:time_start')
                if time_start_info.getInfo(): # Check if date info exists
                    latest_composite_date = ee.Date(time_start_info)
                    latest_composite_date_str = latest_composite_date.format('YYYY-MM-dd').getInfo()

                    vis_params = INDEX_VIS_PARAMS[selected_index]
                    layer_name = f"{selected_index} ({latest_composite_date_str})"

                    # Add the raster layer for the selected index
                    m.add_ee_layer(
                        latest_composite.select(selected_index),
                        vis_params,
                        layer_name,
                        shown=True, # Make sure it's visible by default
                        opacity=0.8 # Adjust opacity
                    )
                    m.add_colorbar(vis_params, label=f"{selected_index} (مقادیر)", layer_name=layer_name)
                else:
                    st.warning(f"تاریخ برای آخرین تصویر ترکیبی شاخص '{selected_index}' یافت نشد.")
            else:
                 st.warning(f"مجموعه تصاویر ترکیبی برای شاخص '{selected_index}' خالی است.")

        except ee.EEException as e:
            st.error(f"خطا در اضافه کردن لایه GEE به نقشه: {e}")
        except Exception as e:
            st.error(f"خطای غیرمنتظره در نمایش لایه نقشه: {e}")
    else:
        if not composite_collection:
             st.warning("داده‌های ترکیبی ماهواره‌ای برای نمایش در دسترس نیست.")
        else:
             st.warning(f"شاخص '{selected_index}' در داده‌های محاسبه شده یافت نشد.")


    # --- Add Farm Markers ---
    # Add markers for the FILTERED farms (selected day)
    if filtered_farm_geojson and filtered_farm_geojson['features']:
        style = {
            "color": "#FF4500", # OrangeRed color for highlight
            "weight": 2,
            "fillColor": "#FF8C00", # DarkOrange fill
            "fillOpacity": 0.6,
            "radius": 7 # Slightly larger radius for highlight
        }
        hover_style = {"fillOpacity": 0.8, "color": "#FF0000"} # Highlight more on hover

        # Create tooltip content dynamically (use columns present in the DataFrame)
        tooltip_cols_present = [col for col in ['مزرعه', 'کانال', 'اداره', 'مساحت داشت', 'واریته', 'سن'] if col in filtered_farm_df.columns]
        tooltip = folium.features.GeoJsonTooltip(
            fields=tooltip_cols_present,
            aliases=[f"{col}:" for col in tooltip_cols_present],
            localize=True,
            sticky=False,
            style="""
                background-color: #F0EFEF;
                border: 1px solid black;
                border-radius: 3px;
                box-shadow: 3px;
                font-family: sans-serif;
                font-size: 12px;
                padding: 5px;
            """
        )

        # Add GeoJson layer for filtered farms
        folium.GeoJson(
            filtered_farm_geojson, # Use the filtered GeoJSON here
            name=f"مزارع روز: {selected_day}",
            marker=folium.CircleMarker(), # Use CircleMarker for styling options
            tooltip=tooltip,
            style_function=lambda x: style,
            highlight_function=lambda x: hover_style,
            show=True # Ensure it's visible by default
        ).add_to(m)
    elif selected_day != 'همه روزها':
         st.info(f"هیچ مزرعه‌ای برای نمایش در روز '{selected_day}' یافت نشد.")


    # --- Add Map Controls ---
    m.add_layer_control(position='topright')
    Fullscreen().add_to(m)
    MeasureControl(position='bottomleft', primary_length_unit='meters', secondary_length_unit='kilometers', primary_area_unit='hectares', secondary_area_unit='sqmeters').add_to(m)
    MiniMap(toggle_display=True, position='bottomright').add_to(m)

    # --- Display Map ---
    with map_col:
        map_output = m.to_streamlit(height=550) # Increased height slightly

    # --- Map Download Button ---
    with download_col:
        st.write(" ")
        st.write(" ")
        st.info("برای دانلود نقشه، از ابزار اسکرین‌شات سیستم استفاده کنید یا روی دکمه زیر کلیک کنید (ممکن است کمی طول بکشد).")
        if st.button("آماده‌سازی دانلود نقشه PNG"):
            with st.spinner("در حال ایجاد فایل PNG نقشه..."):
                png_bytes = map_to_png_bytes(m)
            if png_bytes:
                 st.markdown(
                     get_image_download_link(png_bytes, filename=f"map_{selected_index}_{selected_day}_{end_date_str}.png"),
                     unsafe_allow_html=True
                 )
            else:
                 st.error("خطا در ایجاد فایل PNG نقشه.")


    # --- Analysis Section ---
    st.divider()
    st.header("تحلیل زمانی و رتبه‌بندی مزارع")

    analysis_col1, analysis_col2 = st.columns(2)

    with analysis_col1:
        st.subheader(f"روند تغییرات شاخص: {selected_index}")
        if farm_stats_df is not None and not farm_stats_df.empty and selected_index in farm_stats_df.columns:
             # Filter stats for the selected day's farms if a specific day is chosen
            plot_df = farm_stats_df # Start with all stats
            if selected_day != 'همه روزها' and not filtered_farm_df.empty:
                farms_on_selected_day = filtered_farm_df['مزرعه'].tolist()
                plot_df = farm_stats_df[farm_stats_df['مزرعه'].isin(farms_on_selected_day)]

            # Ensure the selected index column exists and has data for plotting
            if not plot_df.empty and selected_index in plot_df.columns and plot_df[selected_index].notna().any():
                # Sort by date for correct line plotting
                plot_df = plot_df.sort_values(by='date')

                fig = px.line(
                    plot_df,
                    x='date',
                    y=selected_index,
                    color='مزرعه', # Color lines by farm name
                    title=f"روند هفتگی شاخص {selected_index} (مزارع روز: {selected_day})",
                    markers=True,
                    labels={'date': 'تاریخ (شروع هفته)', selected_index: f'میانگین {selected_index}'}
                )
                fig.update_layout(legend_title_text='مزرعه', xaxis_title="تاریخ", yaxis_title=f"میانگین {selected_index}")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"داده معتبری برای رسم نمودار روند شاخص '{selected_index}' برای مزارع روز '{selected_day}' یافت نشد.")

        elif farm_stats_df is None:
             st.warning("داده‌های آماری مزارع برای نمایش روند زمانی محاسبه نشده است.")
        elif selected_index not in farm_stats_df.columns:
             st.warning(f"شاخص '{selected_index}' در داده‌های آماری محاسبه شده یافت نشد.")
        else: # farm_stats_df is empty
             st.warning("داده‌های آماری مزارع خالی است.")


    with analysis_col2:
        st.subheader("رتبه‌بندی و مقایسه هفتگی مزارع")
        st.write(f"بر اساس میانگین شاخص **{selected_index}** در هفته منتهی به **{latest_composite_date_str}**") # Use latest composite date

        # Check if farm_stats_df is valid and contains the selected index
        if farm_stats_df is not None and not farm_stats_df.empty and selected_index in farm_stats_df.columns and farm_stats_df[selected_index].notna().any():
            # Calculate average for the most recent week available in the stats
            latest_date = farm_stats_df['date'].max()
            latest_week_df = farm_stats_df[farm_stats_df['date'] == latest_date]
            latest_avg = latest_week_df.groupby('مزرعه')[selected_index].mean().reset_index()
            latest_avg.rename(columns={selected_index: 'میانگین اخیر'}, inplace=True)

            # Calculate average for the previous week if data exists
            prev_avg = pd.DataFrame(columns=['مزرعه', 'میانگین قبل']) # Empty df default
            if prev_farm_stats_df is not None and not prev_farm_stats_df.empty and selected_index in prev_farm_stats_df.columns and prev_farm_stats_df[selected_index].notna().any():
                 prev_date = prev_farm_stats_df['date'].max()
                 prev_week_df = prev_farm_stats_df[prev_farm_stats_df['date'] == prev_date]
                 prev_avg = prev_week_df.groupby('مزرعه')[selected_index].mean().reset_index()
                 prev_avg.rename(columns={selected_index: 'میانگین قبل'}, inplace=True)

            # Merge current and previous week averages
            rank_df = pd.merge(latest_avg, prev_avg, on='مزرعه', how='left')

            # Calculate weekly change only if both columns exist and are numeric
            if 'میانگین اخیر' in rank_df.columns and 'میانگین قبل' in rank_df.columns:
                 # Ensure columns are numeric before subtraction
                 rank_df['میانگین اخیر'] = pd.to_numeric(rank_df['میانگین اخیر'], errors='coerce')
                 rank_df['میانگین قبل'] = pd.to_numeric(rank_df['میانگین قبل'], errors='coerce')
                 rank_df['تغییر هفتگی'] = rank_df['میانگین اخیر'] - rank_df['میانگین قبل']
            else:
                 rank_df['تغییر هفتگی'] = pd.NA # Assign NA if columns are missing

            # Add interpretation
            rank_df['وضعیت'] = rank_df['میانگین اخیر'].apply(lambda x: get_index_interpretation(selected_index, x))

            # Sort by the average index value (descending for NDVI/EVI/NDMI/LAI, ascending for MSI)
            ascending_sort = selected_index == 'MSI'
            rank_df = rank_df.sort_values(by='میانگین اخیر', ascending=ascending_sort, na_position='last').reset_index(drop=True)

            # Select columns to display and rename
            cols_to_display = ['مزرعه', 'میانگین اخیر', 'میانگین قبل', 'تغییر هفتگی', 'وضعیت']
            rank_display_df = rank_df[[col for col in cols_to_display if col in rank_df.columns]] # Only select existing columns


            # Apply styling and display
            styled_rank_df = style_rank_table(rank_display_df)
            st.dataframe(styled_rank_df, use_container_width=True, hide_index=True) # Hide default index

            # --- Persian Analysis Text ---
            st.subheader("تحلیل وضعیت")
            if not rank_df.empty:
                # Calculate overall averages safely
                avg_current = pd.to_numeric(rank_df['میانگین اخیر'], errors='coerce').mean()
                avg_prev = pd.to_numeric(rank_df['میانگین قبل'], errors='coerce').mean()
                overall_change = avg_current - avg_prev if pd.notna(avg_current) and pd.notna(avg_prev) else None

                st.write(f"**شاخص انتخابی:** {selected_index}")
                st.write(f"**دوره تحلیل (آخرین هفته):** هفته منتهی به {latest_composite_date_str}")

                # General Interpretation
                interp_ranges = INDEX_INTERPRETATION.get(selected_index, {})
                interp_text = f"خوب: {interp_ranges.get('خوب', 'N/A')} | متوسط: {interp_ranges.get('متوسط', 'N/A')} | بحرانی: {interp_ranges.get('بحرانی', 'N/A')}"
                st.markdown(f"**راهنمای کلی مقادیر:** {interp_text}")

                # Overall Trend
                if overall_change is not None:
                    trend_desc = "بهبود یافته" if overall_change > 0 else "کاهش یافته" if overall_change < 0 else "تقریباً ثابت مانده"
                    change_sign = "+" if overall_change > 0 else ""
                    if selected_index == 'MSI': # Lower MSI is better
                       trend_desc = "بهبود یافته (تنش کمتر)" if overall_change < 0 else "بدتر شده (تنش بیشتر)" if overall_change > 0 else "تقریباً ثابت مانده"
                       change_sign = "+" if overall_change > 0 else "" # Sign is reversed for interpretation

                    st.markdown(f"**روند کلی:** میانگین شاخص در مقایسه با هفته قبل **{trend_desc}** است (تغییر: {change_sign}{overall_change:.3f}).")
                else:
                    st.markdown("**روند کلی:** داده‌های هفته قبل برای مقایسه کلی در دسترس نیست.")

                # Highlight specific farms if a day is selected
                if selected_day != 'همه روزها' and 'تغییر هفتگی' in rank_df.columns:
                    st.markdown(f"**تحلیل برای مزارع روز {selected_day}:**")
                    day_rank_df = rank_df[rank_df['مزرعه'].isin(filtered_farm_df['مزرعه'].tolist())].dropna(subset=['تغییر هفتگی'])

                    if not day_rank_df.empty:
                         # Use thresholds defined in styling function
                         threshold_pos = 0.015
                         threshold_neg = -0.015

                         improving_farms = day_rank_df[day_rank_df['تغییر هفتگی'] > threshold_pos]['مزرعه'].tolist()
                         declining_farms = day_rank_df[day_rank_df['تغییر هفتگی'] < threshold_neg]['مزرعه'].tolist()

                         if selected_index == 'MSI': # Swap logic for MSI
                             improving_farms = day_rank_df[day_rank_df['تغییر هفتگی'] < threshold_neg]['مزرعه'].tolist() # Improvement = decrease
                             declining_farms = day_rank_df[day_rank_df['تغییر هفتگی'] > threshold_pos]['مزرعه'].tolist() # Decline = increase

                         if improving_farms:
                              st.success(f"مزارع با بهبود قابل توجه ({'کاهش تنش' if selected_index == 'MSI' else 'رشد'}): {', '.join(improving_farms)}")
                         if declining_farms:
                              st.error(f"مزارع با کاهش قابل توجه ({'افزایش تنش' if selected_index == 'MSI' else 'تنش/کاهش رشد'}): {', '.join(declining_farms)}")
                         if not improving_farms and not declining_farms:
                              st.info("تغییرات قابل توجهی (بیش از حد آستانه) در مزارع این روز نسبت به هفته قبل مشاهده نشد.")
                    else:
                         st.info(f"داده رتبه‌بندی با تغییرات هفتگی برای مزارع روز '{selected_day}' جهت تحلیل موجود نیست.")
            else:
                 st.warning("داده‌ای برای تحلیل رتبه‌بندی در دسترس نیست.")
        else:
             st.warning(f"داده‌های آماری معتبر برای شاخص '{selected_index}' جهت نمایش رتبه‌بندی در دسترس نیست.")


    # --- Farm Details Section ---
    st.divider()
    st.header("جزئیات مزرعه")
    # Use the filtered DataFrame (based on selected day) for the selection box
    if filtered_farm_df is not None and not filtered_farm_df.empty:
        farm_names = sorted(filtered_farm_df['مزرعه'].unique())
        if farm_names:
            selected_farm_name = st.selectbox("یک مزرعه از لیست روز انتخاب شده را برای مشاهده جزئیات انتخاب کنید:", farm_names)

            if selected_farm_name:
                # Get details from the original filtered DataFrame
                farm_details = filtered_farm_df[filtered_farm_df['مزرعه'] == selected_farm_name].iloc[0]
                st.subheader(f"اطلاعات مزرعه: {selected_farm_name}")
                # Display details dynamically based on available columns
                details_cols_to_show = ['کانال', 'اداره', 'مساحت داشت', 'واریته', 'سن', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته']
                for col in details_cols_to_show:
                    if col in farm_details and pd.notna(farm_details[col]):
                         # Format numeric values for better readability
                         value_to_display = farm_details[col]
                         if isinstance(value_to_display, (int, float)):
                              value_to_display = f"{value_to_display:.2f}" if col in ['طول جغرافیایی', 'عرض جغرافیایی', 'مساحت داشت'] else int(value_to_display)
                         st.text(f"{col}: {value_to_display}")

                # Show latest index values for this farm from the stats DataFrame
                st.subheader(f"آخرین مقادیر شاخص‌ها (هفته منتهی به {latest_composite_date_str})")
                if farm_stats_df is not None and not farm_stats_df.empty:
                     latest_farm_stats = farm_stats_df[
                         (farm_stats_df['مزرعه'] == selected_farm_name) &
                         (farm_stats_df['date'] == latest_date) # Use latest_date calculated earlier
                     ]
                     if not latest_farm_stats.empty:
                         for index in available_indices:
                             if index in latest_farm_stats.columns and pd.notna(latest_farm_stats[index].iloc[0]):
                                 value = latest_farm_stats[index].iloc[0]
                                 interp = get_index_interpretation(index, value)
                                 st.text(f"{index}: {value:.3f} ({interp})")
                             else:
                                 st.text(f"{index}: داده موجود نیست")
                     else:
                         st.warning(f"داده‌های شاخص اخیر برای مزرعه {selected_farm_name} در تاریخ {latest_composite_date_str} یافت نشد.")
                else:
                     st.warning("داده‌های آماری کلی برای نمایش جزئیات شاخص در دسترس نیست.")
        else:
            st.info(f"هیچ مزرعه‌ای در لیست روز '{selected_day}' برای انتخاب وجود ندارد.")
    else:
        st.info("مزرعه‌ای برای نمایش جزئیات انتخاب نشده یا در دسترس نیست (ممکن است هیچ مزرعه‌ای برای روز انتخابی وجود نداشته باشد).")

else:
    # This part should ideally not be reached if data loading is handled correctly
    st.error("خطای بارگذاری داده‌های اولیه. لطفاً کد و داده‌های CSV جاسازی شده را بررسی کنید.")

st.sidebar.markdown("---")
st.sidebar.info("ساخته شده با Streamlit و Google Earth Engine")

