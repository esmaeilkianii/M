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
import io
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
# Using standard palettes, customize if needed
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
# Google Earth Engine Functions
# ==============================================================================

@st.cache_resource(show_spinner="در حال اتصال به Google Earth Engine...")
def get_ee_credentials(_service_account_file):
    """Authenticates to Earth Engine using service account credentials."""
    try:
        # Check if the file path exists
        if not os.path.exists(_service_account_file):
            st.error(f"فایل Service Account در مسیر مشخص شده یافت نشد: {_service_account_file}")
            st.error("لطفاً فایل `service_account.json` را در دایرکتوری صحیح قرار دهید یا مسیر آن را در کد اصلاح کنید.")
            return None

        # Load credentials from the file
        with open(_service_account_file) as f:
            credentials_dict = json.load(f)
        credentials = ee.ServiceAccountCredentials(credentials_dict['client_email'], _service_account_file)
        ee.Initialize(credentials)
        st.success("اتصال به Google Earth Engine با موفقیت انجام شد.")
        return ee # Return the authenticated ee object
    except ee.EEException as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.error("جزئیات خطا: ممکن است مشکل از فایل Credential یا دسترسی‌های آن باشد.")
        return None
    except FileNotFoundError:
        st.error(f"فایل Service Account یافت نشد: {_service_account_file}")
        st.error("لطفاً فایل `service_account.json` را در کنار اسکریپت قرار دهید یا مسیر آن را بررسی کنید.")
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
    # Landsat 8/9: NIR = B5, Red = B4
    # Sentinel-2: NIR = B8, Red = B4
    nir = image.select(['SR_B5', 'B8'], ['NIR']).max() # Select available NIR band
    red = image.select(['SR_B4', 'B4'], ['Red']).max() # Select available Red band
    ndvi = image.expression(
        '(NIR - Red) / (NIR + Red)', {
            'NIR': nir,
            'Red': red
        }).rename('NDVI')
    return image.addBands(ndvi)

def add_ndmi(image):
    """Calculates NDMI (Normalized Difference Moisture Index)."""
    # Landsat 8/9: NIR = B5, SWIR1 = B6
    # Sentinel-2: NIR = B8, SWIR1 = B11
    nir = image.select(['SR_B5', 'B8'], ['NIR']).max()
    swir1 = image.select(['SR_B6', 'B11'], ['SWIR1']).max()
    ndmi = image.expression(
        '(NIR - SWIR1) / (NIR + SWIR1)', {
            'NIR': nir,
            'SWIR1': swir1
        }).rename('NDMI')
    return image.addBands(ndmi)

def add_evi(image):
    """Calculates EVI (Enhanced Vegetation Index)."""
    # Landsat 8/9: NIR = B5, Red = B4, Blue = B2
    # Sentinel-2: NIR = B8, Red = B4, Blue = B2
    nir = image.select(['SR_B5', 'B8'], ['NIR']).max()
    red = image.select(['SR_B4', 'B4'], ['Red']).max()
    blue = image.select(['SR_B2', 'B2'], ['Blue']).max()
    evi = image.expression(
        '2.5 * ((NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1))', {
            'NIR': nir,
            'Red': red,
            'Blue': blue
        }).rename('EVI')
    return image.addBands(evi)

def add_lai_simple(image):
    """Estimates LAI from NDVI (Simple empirical formula - needs calibration)."""
    # Example formula: LAI = a * exp(b * NDVI) - Adjust a, b based on crop/region
    # This is a very rough estimate. Proper LAI requires specific models.
    # Using a generic formula for demonstration.
    a = 0.57 # Example coefficient
    b = 2.23 # Example coefficient
    ndvi = image.select('NDVI') # Assumes NDVI is already calculated
    lai = ndvi.expression(
        'a * exp(b * NDVI)', {'a': a, 'b': b, 'NDVI': ndvi}
    ).rename('LAI')
    # Clip LAI to reasonable bounds
    lai = lai.where(lai.lt(0), 0).where(lai.gt(8), 8)
    return image.addBands(lai)

def add_msi(image):
    """Calculates MSI (Moisture Stress Index)."""
    # Landsat 8/9: SWIR1 = B6, NIR = B5
    # Sentinel-2: SWIR1 = B11, NIR = B8
    swir1 = image.select(['SR_B6', 'B11'], ['SWIR1']).max()
    nir = image.select(['SR_B5', 'B8'], ['NIR']).max()
    msi = image.expression(
        'SWIR1 / NIR', {
            'SWIR1': swir1,
            'NIR': nir
        }).rename('MSI')
    return image.addBands(msi)

# --- Main Data Fetching and Processing ---
@st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", ttl=3600) # Cache for 1 hour
def get_satellite_data(_start_date_str, _end_date_str, _aoi, _indices_to_calculate):
    """
    Fetches, processes satellite data (Sentinel-2 & Landsat 8/9) for the AOI and date range,
    calculates specified indices, and creates weekly median composites.
    """
    try:
        start_date = ee.Date(_start_date_str)
        end_date = ee.Date(_end_date_str)
        aoi_ee = geemap.geojson_to_ee(_aoi) # Convert GeoJSON AOI to ee.Geometry

        # --- Sentinel-2 Collection ---
        s2_sr = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(aoi_ee) \
            .filterDate(start_date, end_date) \
            .map(mask_s2_clouds)

        # --- Landsat 8 Collection ---
        l8_sr = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
            .filterBounds(aoi_ee) \
            .filterDate(start_date, end_date) \
            .map(mask_landsat_clouds)

        # --- Landsat 9 Collection ---
        l9_sr = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2') \
            .filterBounds(aoi_ee) \
            .filterDate(start_date, end_date) \
            .map(mask_landsat_clouds)

        # --- Merge Collections ---
        # Select common bands with consistent names for merging if needed,
        # but index functions handle selection. Merging might be complex due to band differences.
        # It's often better to process separately or prioritize one sensor if possible.
        # For simplicity here, we'll prioritize Sentinel-2 if available, then Landsat 9, then 8.
        # A more robust approach would involve harmonization or separate processing paths.

        # We will calculate indices on each collection and then merge the results,
        # taking the median over time.

        def calculate_indices(image):
            img_with_indices = image
            if 'NDVI' in _indices_to_calculate:
                img_with_indices = add_ndvi(img_with_indices)
            if 'NDMI' in _indices_to_calculate:
                img_with_indices = add_ndmi(img_with_indices)
            if 'EVI' in _indices_to_calculate:
                img_with_indices = add_evi(img_with_indices)
            # Calculate LAI only if NDVI is calculated
            if 'LAI' in _indices_to_calculate and 'NDVI' in _indices_to_calculate:
                 # Ensure NDVI exists before calculating LAI
                 if 'NDVI' not in img_with_indices.bandNames().getInfo():
                     img_with_indices = add_ndvi(img_with_indices)
                 img_with_indices = add_lai_simple(img_with_indices)
            if 'MSI' in _indices_to_calculate:
                img_with_indices = add_msi(img_with_indices)
            # Add system:time_start for later filtering/compositing
            return img_with_indices.addBands(ee.Image.constant(image.date().millis()).long().rename('timestamp'))


        s2_processed = s2_sr.map(calculate_indices).select(_indices_to_calculate + ['timestamp'])
        l8_processed = l8_sr.map(calculate_indices).select(_indices_to_calculate + ['timestamp'])
        l9_processed = l9_sr.map(calculate_indices).select(_indices_to_calculate + ['timestamp'])

        # Merge the processed collections
        merged_collection = ee.ImageCollection(s2_processed.merge(l9_processed).merge(l8_processed)) \
                               .sort('system:time_start')

        # --- Create Weekly Median Composite ---
        # Generate a list of dates separated by a week
        date_diff = end_date.difference(start_date, 'day')
        num_weeks = date_diff.divide(7).ceil().getInfo()
        if num_weeks == 0: num_weeks = 1 # Ensure at least one period

        weekly_composites = []
        composite_dates = []

        for i in range(num_weeks):
            week_start = start_date.advance(i * 7, 'day')
            week_end = week_start.advance(7, 'day')
            # Ensure the last week doesn't exceed the overall end_date
            if week_end.millis().getInfo() > end_date.millis().getInfo():
                week_end = end_date

            # Filter collection for the current week
            weekly_data = merged_collection.filterDate(week_start, week_end)

            if weekly_data.size().getInfo() > 0:
                # Calculate median composite for the week
                median_composite = weekly_data.median() # Use median to reduce outlier effects
                # Set the date property to the start of the week for tracking
                median_composite = median_composite.set('system:time_start', week_start.millis())
                weekly_composites.append(median_composite)
                composite_dates.append(week_start.format('YYYY-MM-dd').getInfo())
            # else: # Handle weeks with no data if necessary
                # st.warning(f"داده‌ای برای هفته شروع‌شده در {week_start.format('YYYY-MM-dd').getInfo()} یافت نشد.")


        if not weekly_composites:
            st.warning("هیچ داده ماهواره‌ای معتبری در بازه زمانی و منطقه انتخابی یافت نشد.")
            return None, None

        # Convert the list of images to an ImageCollection
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
        return None

    farm_polygons_ee = geemap.geojson_to_ee({
        "type": "FeatureCollection",
        "features": _farm_features
    })

    all_stats = []

    def extract_stats(image):
        # Get the date of the image (start of the week)
        image_date = ee.Date(image.get('system:time_start')).format('YYYY-MM-dd')
        # Calculate mean for selected indices for all features
        stats = image.select(_indices).reduceRegions(
            collection=farm_polygons_ee,
            reducer=ee.Reducer.mean(),
            scale=30 # Adjust scale based on sensor resolution (e.g., 10 for Sentinel-2)
        )
        # Add date to each feature's properties
        def add_date(feature):
            return feature.set('date', image_date)
        return stats.map(add_date)

    # Map over the collection and flatten the results
    try:
        results = _composite_collection.map(extract_stats).flatten()
        # Retrieve the results from GEE
        stats_list = results.getInfo()['features']

        # Convert to Pandas DataFrame
        data = []
        for feature in stats_list:
            props = feature['properties']
            row = {
                _farm_id_col: props.get(_farm_id_col),
                'date': props.get('date')
            }
            for index in _indices:
                row[index] = props.get(index)
            data.append(row)

        if not data:
            st.warning("داده آماری برای مزارع محاسبه نشد.")
            return None

        stats_df = pd.DataFrame(data)
        stats_df['date'] = pd.to_datetime(stats_df['date'])
        # Pivot table for easier analysis (optional, depends on usage)
        # stats_pivot = stats_df.pivot(index='date', columns=_farm_id_col, values=_indices)
        return stats_df.dropna(subset=[_farm_id_col]) # Drop rows where farm ID is missing

    except ee.EEException as e:
        st.error(f"خطا در محاسبه آمار منطقه‌ای (Zonal Statistics): {e}")
        return None
    except Exception as e:
        st.error(f"خطای غیرمنتظره در محاسبه آمار منطقه‌ای: {e}")
        return None

# ==============================================================================
# Helper Functions
# ==============================================================================

def load_data(uploaded_file):
    """Loads farm data from the uploaded CSV file."""
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            # Basic validation
            required_cols = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته']
            if not all(col in df.columns for col in required_cols):
                st.error(f"فایل CSV باید شامل ستون‌های ضروری باشد: {', '.join(required_cols)}")
                return None
            # Convert coordinate columns to numeric, coercing errors
            df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
            df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
            # Drop rows with invalid coordinates
            df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'], inplace=True)
            # Ensure 'روزهای هفته' is string
            df['روزهای هفته'] = df['روزهای هفته'].astype(str)
            return df
        except Exception as e:
            st.error(f"خطا در بارگذاری یا پردازش فایل CSV: {e}")
            return None
    return None

def df_to_geojson(df, lat_col='عرض جغرافیایی', lon_col='طول جغرافیایی'):
    """Converts a DataFrame to GeoJSON FeatureCollection (Points)."""
    features = []
    for _, row in df.iterrows():
        try:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(row[lon_col]), float(row[lat_col])]
                },
                "properties": row.to_dict() # Include all other columns as properties
            }
            # Convert non-serializable types like Timestamp to string if necessary
            for key, value in feature["properties"].items():
                if isinstance(value, pd.Timestamp):
                    feature["properties"][key] = str(value)
                # Add more type checks if needed
            features.append(feature)
        except (ValueError, TypeError) as e:
            st.warning(f"خطا در تبدیل ردیف به GeoJSON (مزرعه: {row.get('مزرعه', 'N/A')}): {e}. این ردیف نادیده گرفته شد.")
            continue # Skip rows with conversion errors

    return {"type": "FeatureCollection", "features": features}


def get_week_dates(n_weeks=1):
    """Gets the start and end dates for the last n weeks."""
    today = date.today()
    # Go back to the beginning of the current week (e.g., Monday) if needed
    # start_of_current_week = today - timedelta(days=today.weekday())
    end_date = today
    start_date = today - timedelta(days=(n_weeks * 7) -1) # -1 because it includes today
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def get_previous_week_dates(current_start_str, current_end_str):
    """Gets the start and end dates for the week prior to the given range."""
    current_end = datetime.strptime(current_end_str, '%Y-%m-%d').date()
    # Assuming the current range is typically 7 days
    prev_end_date = current_end - timedelta(days=7)
    prev_start_date = prev_end_date - timedelta(days=6) # 7 days total
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
    return "خارج از محدوده" # Or "نامشخص" if value is outside defined ranges


def style_rank_table(df):
    """Applies styling to the ranking table based on weekly change."""
    def highlight_change(row):
        color = ''
        if pd.notna(row['تغییر هفتگی']):
            if row['تغییر هفتگی'] > 0.01: # Threshold for improvement
                color = 'background-color: lightgreen'
            elif row['تغییر هفتگی'] < -0.01: # Threshold for decline
                color = 'background-color: lightcoral'
        # Apply to the whole row
        return [color] * len(row)

    # Apply styling - check if 'تغییر هفتگی' column exists
    if 'تغییر هفتگی' in df.columns:
         # Reset index if 'مزرعه' is the index to make it a column for styling access
        df_reset = df.reset_index()
        styled_df = df_reset.style.apply(highlight_change, axis=1)
        # Set the index back if needed, or just return the styled object
        return styled_df # .set_index('مزرعه') # Optional: set index back
    else:
        return df # Return original if no change column


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
st.sidebar.header("تنظیمات ورودی و نمایش")

# 1. GEE Authentication File Path (Consider security implications)
# It's better practice to use environment variables or Streamlit secrets
# For now, hardcoding the path as requested, assuming it's in the same directory
SERVICE_ACCOUNT_FILE = 'service_account.json' # Or provide the full path if elsewhere

# Attempt GEE authentication
ee_authenticated = get_ee_credentials(SERVICE_ACCOUNT_FILE)

if not ee_authenticated:
    st.sidebar.error("اتصال به Google Earth Engine برقرار نشد. لطفاً خطاها را بررسی کنید.")
    st.stop() # Stop execution if GEE connection fails

# 2. CSV File Uploader
uploaded_file = st.sidebar.file_uploader("۱. فایل CSV اطلاعات مزارع را بارگذاری کنید", type=["csv"])

# Load and process farm data
farm_data_df = None
farm_geojson = None
if uploaded_file:
    farm_data_df = load_data(uploaded_file)
    if farm_data_df is not None:
        farm_geojson = df_to_geojson(farm_data_df)
        st.sidebar.success(f"{len(farm_data_df)} مزرعه با موفقیت بارگذاری شد.")
    else:
        st.sidebar.error("خطا در پردازش فایل CSV.")
else:
    st.sidebar.info("لطفاً فایل CSV مزارع را بارگذاری کنید.")
    st.stop() # Stop if no farm data

# 3. Date Range Selection
st.sidebar.subheader("۲. بازه زمانی تحلیل")
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
st.sidebar.subheader("۳. انتخاب شاخص برای نمایش")
available_indices = list(INDEX_VIS_PARAMS.keys())
selected_index = st.sidebar.selectbox("شاخص مورد نظر را انتخاب کنید:", available_indices, index=0) # Default to NDVI

# 5. Day of the Week Filter
st.sidebar.subheader("۴. فیلتر بر اساس روز هفته")
unique_days = sorted(farm_data_df['روزهای هفته'].unique())
# Add an option for 'All Days'
day_options = ['همه روزها'] + unique_days
selected_day = st.sidebar.selectbox("روز هفته را انتخاب کنید:", day_options, index=0) # Default to 'All Days'

# --- Filter farm data based on selected day ---
if selected_day == 'همه روزها':
    filtered_farm_df = farm_data_df
else:
    filtered_farm_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day]

if filtered_farm_df.empty:
    st.warning(f"هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
    filtered_farm_geojson = {"type": "FeatureCollection", "features": []}
    aoi_geojson = farm_geojson # Use all farms for AOI calculation
else:
    filtered_farm_geojson = df_to_geojson(filtered_farm_df)
    # Define Area of Interest (AOI) based on filtered farms or all farms
    # Using bounding box of all farms for data fetching is safer
    aoi_geojson = farm_geojson # Use all farms for satellite data query bounds


# --- Main Panel ---
if farm_data_df is not None and farm_geojson and aoi_geojson:

    st.header("نقشه تعاملی مزارع و شاخص‌ها")
    map_col, download_col = st.columns([4, 1])

    # --- Fetch and Process Satellite Data ---
    # Use the full date range selected by the user
    # The AOI should cover all farms to ensure data availability
    composite_collection, composite_dates = get_satellite_data(
        start_date_str,
        end_date_str,
        aoi_geojson, # Use AOI covering all farms
        available_indices # Calculate all available indices
    )

    # --- Calculate Zonal Statistics ---
    # Calculate stats for the current period
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
        add_google_map=False # Start with a clean slate
    )
    # Add base maps
    m.add_basemap("SATELLITE")
    m.add_basemap("ROADMAP")


    # --- Add Data Layers to Map ---
    if composite_collection and selected_index in available_indices:
        try:
            # Get the latest composite image (usually the last one in the collection)
            latest_composite = composite_collection.sort('system:time_start', False).first()
            latest_composite_date = "نامشخص"
            if latest_composite.get('system:time_start').getInfo():
                 latest_composite_date = ee.Date(latest_composite.get('system:time_start')).format('YYYY-MM-dd').getInfo()


            vis_params = INDEX_VIS_PARAMS[selected_index]
            layer_name = f"{selected_index} ({latest_composite_date})"

            # Add the raster layer for the selected index
            m.add_ee_layer(
                latest_composite.select(selected_index),
                vis_params,
                layer_name
            )
            m.add_colorbar(vis_params, label=f"{selected_index} (مقادیر)", layer_name=layer_name)

        except ee.EEException as e:
            st.error(f"خطا در اضافه کردن لایه GEE به نقشه: {e}")
        except Exception as e:
            st.error(f"خطای غیرمنتظره در نمایش لایه نقشه: {e}")
    else:
        st.warning(f"داده‌ای برای نمایش شاخص '{selected_index}' در بازه زمانی انتخابی وجود ندارد.")


    # --- Add Farm Markers ---
    # Add markers for the filtered farms (selected day)
    if filtered_farm_geojson and filtered_farm_geojson['features']:
        style = {
            "color": "#FF0000", # Red color for highlight
            "weight": 2,
            "fillColor": "#FF0000",
            "fillOpacity": 0.5,
            "radius": 8 # Larger radius for highlight
        }
        hover_style = {"fillOpacity": 0.7}

        # Create tooltip content dynamically
        tooltip_cols = ['مزرعه', 'کانال', 'اداره', 'مساحت داشت', 'واریته', 'سن']
        tooltip = folium.features.GeoJsonTooltip(
            fields=tooltip_cols,
            aliases=[f"{col}:" for col in tooltip_cols], # Add colon for clarity
            localize=True,
            sticky=False,
            style="""
                background-color: #F0EFEF;
                border: 2px solid black;
                border-radius: 3px;
                box-shadow: 3px;
            """
        )

        # Add GeoJson layer for filtered farms
        folium.GeoJson(
            filtered_farm_geojson,
            name=f"مزارع روز: {selected_day}",
            marker=folium.CircleMarker(radius=style['radius'], weight=style['weight'], color=style['color'], fill_color=style['fillColor'], fill_opacity=style['fillOpacity']),
            tooltip=tooltip,
            style_function=lambda x: style,
            highlight_function=lambda x: {"fillOpacity": hover_style["fillOpacity"]},
            show=True # Ensure it's visible by default
        ).add_to(m)


    # --- Add Map Controls ---
    m.add_layer_control()
    Fullscreen().add_to(m)
    MeasureControl(position='topleft', primary_length_unit='meters', secondary_length_unit='kilometers', primary_area_unit='hectares', secondary_area_unit='sqmeters').add_to(m)
    MiniMap().add_to(m)

    # --- Display Map ---
    with map_col:
        map_output = m.to_streamlit(height=500)

    # --- Map Download Button ---
    with download_col:
        st.write(" ") # Spacer
        st.write(" ") # Spacer
        # The direct PNG download from geemap/folium in Streamlit can be tricky.
        # Using the internal _to_png method is experimental.
        # Provide instructions if direct download fails.
        st.info("برای دانلود نقشه، از ابزار اسکرین‌شات سیستم خود استفاده کنید یا منتظر بمانید تا دکمه دانلود فعال شود (ممکن است کمی طول بکشد).")
        if st.button("آماده‌سازی دانلود نقشه PNG"):
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
        if farm_stats_df is not None and not farm_stats_df.empty:
             # Filter stats for the selected day's farms if a specific day is chosen
            if selected_day != 'همه روزها':
                farms_on_selected_day = filtered_farm_df['مزرعه'].tolist()
                plot_df = farm_stats_df[farm_stats_df['مزرعه'].isin(farms_on_selected_day)]
            else:
                plot_df = farm_stats_df

            if not plot_df.empty:
                fig = px.line(
                    plot_df,
                    x='date',
                    y=selected_index,
                    color='مزرعه', # Color lines by farm name
                    title=f"روند هفتگی شاخص {selected_index}",
                    markers=True,
                    labels={'date': 'تاریخ (شروع هفته)', selected_index: f'میانگین {selected_index}'}
                )
                fig.update_layout(legend_title_text='مزرعه')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"داده‌ای برای رسم نمودار روند برای مزارع روز '{selected_day}' یافت نشد.")

        else:
            st.warning("داده‌های آماری برای نمایش روند زمانی در دسترس نیست.")

    with analysis_col2:
        st.subheader("رتبه‌بندی و مقایسه هفتگی مزارع")
        st.write(f"بر اساس میانگین شاخص **{selected_index}** در هفته منتهی به **{end_date_str}**")

        if farm_stats_df is not None and not farm_stats_df.empty:
            # Calculate average for the most recent week available in the stats
            latest_week_df = farm_stats_df[farm_stats_df['date'] == farm_stats_df['date'].max()]
            latest_avg = latest_week_df.groupby('مزرعه')[selected_index].mean().reset_index()
            latest_avg.rename(columns={selected_index: 'میانگین هفته اخیر'}, inplace=True)

            # Calculate average for the previous week if data exists
            prev_avg = pd.DataFrame(columns=['مزرعه', 'میانگین هفته قبل']) # Empty df default
            if prev_farm_stats_df is not None and not prev_farm_stats_df.empty:
                 prev_week_df = prev_farm_stats_df[prev_farm_stats_df['date'] == prev_farm_stats_df['date'].max()]
                 prev_avg = prev_week_df.groupby('مزرعه')[selected_index].mean().reset_index()
                 prev_avg.rename(columns={selected_index: 'میانگین هفته قبل'}, inplace=True)

            # Merge current and previous week averages
            rank_df = pd.merge(latest_avg, prev_avg, on='مزرعه', how='left')

            # Calculate weekly change
            rank_df['تغییر هفتگی'] = rank_df['میانگین هفته اخیر'] - rank_df['میانگین هفته قبل']

            # Add interpretation
            rank_df['وضعیت'] = rank_df['میانگین هفته اخیر'].apply(lambda x: get_index_interpretation(selected_index, x))

            # Sort by the average index value (descending for NDVI/EVI/NDMI/LAI, ascending for MSI)
            ascending_sort = selected_index == 'MSI'
            rank_df = rank_df.sort_values(by='میانگین هفته اخیر', ascending=ascending_sort).reset_index(drop=True)

            # Select columns to display and rename
            rank_display_df = rank_df[['مزرعه', 'میانگین هفته اخیر', 'میانگین هفته قبل', 'تغییر هفتگی', 'وضعیت']]
            rank_display_df.columns = ['مزرعه', 'میانگین اخیر', 'میانگین قبل', 'تغییر هفتگی', 'وضعیت']

            # Apply styling
            styled_rank_df = style_rank_table(rank_display_df)

            st.dataframe(styled_rank_df, use_container_width=True)

            # --- Persian Analysis Text ---
            st.subheader("تحلیل وضعیت")
            if not rank_df.empty:
                avg_current = rank_df['میانگین هفته اخیر'].mean()
                avg_prev = rank_df['میانگین هفته قبل'].mean() # Note: mean of means might not be perfect stat
                overall_change = avg_current - avg_prev if pd.notna(avg_current) and pd.notna(avg_prev) else None

                st.write(f"**شاخص انتخابی:** {selected_index}")
                st.write(f"**دوره تحلیل:** {start_date_str} تا {end_date_str}")

                # General Interpretation of the selected index
                interp_ranges = INDEX_INTERPRETATION.get(selected_index, {})
                interp_text = f" - **خوب:** {interp_ranges.get('خوب', 'N/A')}" \
                              f" - **متوسط:** {interp_ranges.get('متوسط', 'N/A')}" \
                              f" - **بحرانی:** {interp_ranges.get('بحرانی', 'N/A')}"
                st.write(f"**راهنمای کلی مقادیر {selected_index}:** {interp_text}")

                # Overall Trend
                if overall_change is not None:
                    trend_desc = "بهبود یافته" if overall_change > 0 else "کاهش یافته" if overall_change < 0 else "تقریباً ثابت مانده"
                    if selected_index == 'MSI': # Lower MSI is better
                       trend_desc = "بهبود یافته (تنش کمتر)" if overall_change < 0 else "بدتر شده (تنش بیشتر)" if overall_change > 0 else "تقریباً ثابت مانده"

                    st.write(f"**روند کلی مزارع:** در مقایسه با هفته قبل، میانگین شاخص {selected_index} به طور کلی **{trend_desc}** است (تغییر میانگین: {overall_change:.3f}).")
                else:
                    st.write("**روند کلی مزارع:** داده‌های هفته قبل برای مقایسه کلی در دسترس نیست.")

                # Highlight specific farms if a day is selected
                if selected_day != 'همه روزها':
                    st.write(f"**تحلیل برای مزارع روز {selected_day}:**")
                    day_rank_df = rank_df[rank_df['مزرعه'].isin(filtered_farm_df['مزرعه'].tolist())]
                    if not day_rank_df.empty:
                         improving_farms = day_rank_df[day_rank_df['تغییر هفتگی'] > 0.01]['مزرعه'].tolist()
                         declining_farms = day_rank_df[day_rank_df['تغییر هفتگی'] < -0.01]['مزرعه'].tolist()

                         if selected_index == 'MSI': # Swap logic for MSI
                             improving_farms = day_rank_df[day_rank_df['تغییر هفتگی'] < -0.01]['مزرعه'].tolist() # Improvement = decrease
                             declining_farms = day_rank_df[day_rank_df['تغییر هفتگی'] > 0.01]['مزرعه'].tolist() # Decline = increase

                         if improving_farms:
                              st.success(f"مزارع با بهبود قابل توجه ({'کاهش تنش' if selected_index == 'MSI' else 'رشد'}): {', '.join(improving_farms)}")
                         if declining_farms:
                              st.error(f"مزارع با کاهش قابل توجه ({'افزایش تنش' if selected_index == 'MSI' else 'تنش/کاهش رشد'}): {', '.join(declining_farms)}")
                         if not improving_farms and not declining_farms:
                              st.info("تغییرات قابل توجهی در مزارع این روز نسبت به هفته قبل مشاهده نشد.")
                    else:
                         st.info(f"داده رتبه‌بندی برای مزارع روز '{selected_day}' جهت تحلیل هفتگی موجود نیست.")


            else:
                 st.warning("داده‌ای برای تحلیل رتبه‌بندی در دسترس نیست.")

        else:
            st.warning("داده‌های آماری برای نمایش رتبه‌بندی در دسترس نیست.")


    # --- Farm Details Section (Optional - Add if needed) ---
    st.divider()
    st.header("جزئیات مزرعه")
    if filtered_farm_df is not None and not filtered_farm_df.empty:
        farm_names = filtered_farm_df['مزرعه'].tolist()
        selected_farm_name = st.selectbox("یک مزرعه از لیست روز انتخاب شده را برای مشاهده جزئیات انتخاب کنید:", farm_names)

        if selected_farm_name:
            farm_details = filtered_farm_df[filtered_farm_df['مزرعه'] == selected_farm_name].iloc[0]
            st.subheader(f"اطلاعات مزرعه: {selected_farm_name}")
            details_cols_to_show = ['کانال', 'اداره', 'مساحت داشت', 'واریته', 'سن', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته']
            for col in details_cols_to_show:
                if col in farm_details:
                     st.text(f"**{col}:** {farm_details[col]}")

            # Show latest index values for this farm
            st.subheader(f"آخرین مقادیر شاخص‌ها (هفته منتهی به {end_date_str})")
            if farm_stats_df is not None:
                 latest_farm_stats = farm_stats_df[
                     (farm_stats_df['مزرعه'] == selected_farm_name) &
                     (farm_stats_df['date'] == farm_stats_df['date'].max())
                 ]
                 if not latest_farm_stats.empty:
                     for index in available_indices:
                         if index in latest_farm_stats.columns:
                             value = latest_farm_stats[index].iloc[0]
                             interp = get_index_interpretation(index, value)
                             st.text(f"**{index}:** {value:.3f} ({interp})")
                         else:
                             st.text(f"**{index}:** داده موجود نیست")
                 else:
                     st.warning(f"داده‌های شاخص اخیر برای مزرعه {selected_farm_name} یافت نشد.")
            else:
                 st.warning("داده‌های آماری برای نمایش جزئیات شاخص در دسترس نیست.")

    else:
        st.info("مزرعه‌ای برای نمایش جزئیات انتخاب نشده یا در دسترس نیست.")


else:
    st.info("منتظر بارگذاری فایل CSV و انتخاب تنظیمات...")

st.sidebar.markdown("---")
st.sidebar.info("ساخته شده با Streamlit و Google Earth Engine")
