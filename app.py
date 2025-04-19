import streamlit as st
import ee
import geemap.foliumap as geemap # Use foliumap for Streamlit integration
import pandas as pd
import plotly.express as px
import json
from datetime import datetime, timedelta
import io
import base64
import os
import folium # Needed for potential marker customizations

# ==============================================================================
# Configuration and Page Setup
# ==============================================================================
st.set_page_config(layout="wide", page_title="داشبورد مانیتورینگ مزارع نیشکر دهخدا")

st.title("📊 داشبورد هوشمند مانیتورینگ هفتگی مزارع نیشکر شرکت دهخدا")
st.markdown("""
این داشبورد به منظور پایش وضعیت مزارع نیشکر با استفاده از تصاویر ماهواره‌ای و شاخص‌های کشاورزی طراحی شده است.
""")

# ==============================================================================
# Authentication and Initialization (Cached)
# ==============================================================================

# Define the path to the service account key file within the Streamlit app's structure
# Assuming it's in the root directory or a specific 'keys' directory
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'
DEFAULT_SERVICE_EMAIL = "dehkhodamap-e9f0da4ce9f6514021@ee-esmaeilkiani13877.iam.gserviceaccount.com" # Provided email

@st.cache_resource(show_spinner="در حال اتصال به Google Earth Engine...")
def authenticate_gee(service_account_file):
    """Authenticates to GEE using service account credentials."""
    try:
        # Check if running in Streamlit Cloud/Sharing where secrets might be used
        if 'GEE_SERVICE_ACCOUNT_CREDENTIALS' in st.secrets:
             print("Authenticating GEE using Streamlit secrets...")
             creds_json = json.loads(st.secrets["GEE_SERVICE_ACCOUNT_CREDENTIALS"])
             credentials = ee.ServiceAccountCredentials(creds_json['client_email'], key_data=json.dumps(creds_json))
             ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
             st.success(f"اتصال موفق به GEE با ایمیل: {creds_json['client_email']}")
             return True # Indicate successful authentication
        # Fallback to local file if secrets not found or not running in Cloud
        elif os.path.exists(service_account_file):
            print(f"Authenticating GEE using file: {service_account_file}...")
            # Use the service account email provided in the prompt if needed for initialization
            # However, ServiceAccountCredentials usually infers email from the key file
            with open(service_account_file) as f:
                 key_data = json.load(f)
            credentials = ee.ServiceAccountCredentials(key_data['client_email'], service_account_file)
            # credentials = ee.ServiceAccountCredentials(DEFAULT_SERVICE_EMAIL, service_account_file) # Alternative if needed
            ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
            st.success(f"اتصال موفق به GEE با ایمیل: {key_data['client_email']}")
            return True
        else:
             st.error(f"فایل Service Account یافت نشد: {service_account_file}. لطفاً فایل را در مسیر صحیح قرار دهید یا از Streamlit Secrets استفاده کنید.")
             st.stop()
             return False # Indicate failure

    except ee.EEException as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.error("ممکن است مشکل از فایل service_account.json یا دسترسی‌های آن باشد.")
        st.stop()
        return False
    except FileNotFoundError:
        st.error(f"فایل Service Account یافت نشد: {service_account_file}. لطفاً فایل را بارگذاری یا در مسیر صحیح قرار دهید.")
        st.stop()
        return False
    except Exception as e:
        st.error(f"خطای پیش‌بینی نشده در زمان اتصال به GEE: {e}")
        st.stop()
        return False

# --- Trigger Authentication ---
# Attempt authentication only if the file exists locally or secrets are available
gee_authenticated = False
if 'GEE_SERVICE_ACCOUNT_CREDENTIALS' in st.secrets or os.path.exists(SERVICE_ACCOUNT_FILE):
    gee_authenticated = authenticate_gee(SERVICE_ACCOUNT_FILE)
else:
    st.warning(f"فایل احراز هویت '{SERVICE_ACCOUNT_FILE}' یافت نشد. لطفاً آن را در کنار اسکریپت قرار دهید یا از طریق Streamlit Secrets تنظیم کنید.")
    # Optionally allow upload if local file isn't found
    uploaded_key = st.sidebar.file_uploader("بارگذاری فایل service_account.json (اختیاری)", type=['json'])
    if uploaded_key:
        # Save the uploaded key temporarily to be used by authentication
        temp_key_path = "temp_service_account.json"
        with open(temp_key_path, "wb") as f:
            f.write(uploaded_key.getvalue())
        gee_authenticated = authenticate_gee(temp_key_path)
        # Clean up the temporary file (optional, Streamlit might handle temp files)
        # if os.path.exists(temp_key_path):
        #     os.remove(temp_key_path)
    else:
        st.stop() # Stop execution if no key is available

# Stop if GEE authentication failed
if not gee_authenticated:
    st.stop()


# ==============================================================================
# Data Loading (Cached)
# ==============================================================================
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data(uploaded_file):
    """Loads farm data from the uploaded CSV file."""
    if uploaded_file is None:
        st.warning("لطفاً فایل CSV مشخصات مزارع را بارگذاری کنید.")
        return None
    try:
        # Specify dtype={'مزرعه': str} if farm names can be interpreted as numbers
        df = pd.read_csv(uploaded_file, dtype={'مزرعه': str})
        # Basic validation
        required_cols = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته', 'coordinates_missing']
        if not all(col in df.columns for col in required_cols):
            st.error(f"فایل CSV باید شامل ستون‌های ضروری باشد: {', '.join(required_cols)}")
            return None

        # Handle potential missing coordinates flag
        df['coordinates_missing'] = df['coordinates_missing'].fillna(False).astype(bool)
        # Convert coordinate columns to numeric, coercing errors
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')

        # Add a unique ID for easier referencing if needed
        df['farm_id'] = df.index

        # Filter out rows with invalid coordinates *unless* explicitly marked as missing
        initial_rows = len(df)
        df_valid = df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
        df_missing_flagged = df[df['coordinates_missing'] == True]
        rows_dropped = initial_rows - len(df_valid) - len(df_missing_flagged)

        if rows_dropped > 0:
             st.warning(f"{rows_dropped} ردیف به دلیل مختصات نامعتبر (و عدم علامت‌گذاری به عنوان گمشده) نادیده گرفته شد.")

        df_final = pd.concat([df_valid, df_missing_flagged])

        st.success(f"فایل CSV با موفقیت بارگذاری شد. {len(df_final)} مزرعه معتبر یافت شد.")
        return df_final

    except pd.errors.EmptyDataError:
        st.error("فایل CSV بارگذاری شده خالی است.")
        return None
    except Exception as e:
        st.error(f"خطا در خواندن فایل CSV: {e}")
        return None

# --- File Uploader in Sidebar ---
uploaded_csv = st.sidebar.file_uploader("📂 بارگذاری فایل CSV مزارع", type=['csv'])
farm_data_df = load_farm_data(uploaded_csv)

# Stop execution if data loading failed
if farm_data_df is None:
    st.stop()

# ==============================================================================
# Sidebar Controls
# ==============================================================================
st.sidebar.header("⚙️ تنظیمات و فیلترها")

# --- Date Selection ---
analysis_end_date = st.sidebar.date_input(
    "📅 انتخاب تاریخ پایان هفته پایش",
    datetime.now().date(), # Default to today
    help="تاریخ پایانی برای دوره 7 روزه پایش انتخاب می‌شود."
)
# Calculate start date (7 days before the end date, inclusive)
analysis_start_date = analysis_end_date - timedelta(days=6)
prev_week_end_date = analysis_start_date - timedelta(days=1)
prev_week_start_date = prev_week_end_date - timedelta(days=6)

st.sidebar.info(f"دوره پایش فعلی: {analysis_start_date.strftime('%Y-%m-%d')} تا {analysis_end_date.strftime('%Y-%m-%d')}")
st.sidebar.info(f"دوره مقایسه (هفته قبل): {prev_week_start_date.strftime('%Y-%m-%d')} تا {prev_week_end_date.strftime('%Y-%m-%d')}")


# --- Day of the Week Filter ---
available_days = sorted(farm_data_df['روزهای هفته'].unique().tolist())
selected_day = st.sidebar.selectbox(
    "☀️ انتخاب روز هفته",
    options=["همه روزها"] + available_days,
    index=0,
    help="مزارع مربوط به این روز نمایش داده خواهند شد."
)

# Filter dataframe based on selected day
if selected_day == "همه روزها":
    filtered_df = farm_data_df.copy()
else:
    filtered_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day].copy()

# Filter out farms explicitly marked with missing coordinates for mapping/analysis
mappable_df = filtered_df[~filtered_df['coordinates_missing']].copy()

if mappable_df.empty and not filtered_df.empty:
     st.warning(f"مزارع برای '{selected_day}' یافت شد، اما هیچکدام مختصات معتبر برای نمایش روی نقشه ندارند.")
elif mappable_df.empty:
     st.warning(f"هیچ مزرعه‌ای برای '{selected_day}' یافت نشد یا هیچکدام مختصات معتبر ندارند.")
     # st.stop() # Don't stop, allow user to change selection

# --- Farm Selection (for detailed analysis) ---
# Use only mappable farms for selection
farm_options = ["-- انتخاب مزرعه برای تحلیل جزئی --"] + sorted(mappable_df['مزرعه'].unique().tolist())
selected_farm_name = st.sidebar.selectbox(
    "🌾 انتخاب مزرعه خاص",
    options=farm_options,
    index=0,
    help="یک مزرعه برای مشاهده جزئیات، نمودار زمانی و مقایسه هفتگی انتخاب کنید."
)

# Get details of the selected farm
selected_farm_details = None
selected_farm_geometry = None
if selected_farm_name != "-- انتخاب مزرعه برای تحلیل جزئی --":
    selected_farm_details = mappable_df[mappable_df['مزرعه'] == selected_farm_name].iloc[0]
    try:
        # Create GEE geometry *inside* the scope where it's used, using _ prefix if needed later for caching functions
        # For now, it's used directly, so prefix isn't strictly needed unless passed to a cached func
        _selected_farm_geometry = ee.Geometry.Point([selected_farm_details['طول جغرافیایی'], selected_farm_details['عرض جغرافیایی']])
        selected_farm_geometry = _selected_farm_geometry # Assign to the variable used later
    except Exception as e:
        st.error(f"خطا در ایجاد هندسه GEE برای مزرعه '{selected_farm_name}': {e}")
        selected_farm_details = None # Reset if geometry creation fails


# ==============================================================================
# GEE Image Processing Functions
# ==============================================================================

# --- Constants ---
S2_SR_HARMONIZED = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
LANDSAT_LC08_C02_T1_L2 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') # Example Landsat 8
LANDSAT_LC09_C02_T1_L2 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2') # Example Landsat 9
ERA5_DAILY = ee.ImageCollection('ECMWF/ERA5/DAILY') # For ET
MODIS_MCD15A3H = ee.ImageCollection('MODIS/061/MCD15A3H') # For LAI (4-day composite)

# Define analysis scale (e.g., 10m for Sentinel-2)
ANALYSIS_SCALE = 10

# --- Cloud Masking (Sentinel-2 Example) ---
def mask_s2_clouds(image):
    """Masks clouds in a Sentinel-2 SR image using the QA60 band."""
    qa = image.select('QA60')
    # Bits 10 and 11 are cloud and cirrus flags, respectively.
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    # Both flags should be set to zero, indicating clear conditions.
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
             qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    # Also mask saturated or defective pixels using SCL band if available
    scl = image.select('SCL')
    # Keep vegetation (4), bare soil (5), water (6), snow (11)
    # Mask out saturated/defective (1), dark area (2), cloud shadow (3), cloud medium prob (8), cloud high prob (9), cirrus (10)
    valid_scl = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(11))

    return image.updateMask(mask).updateMask(valid_scl).divide(10000).copyProperties(image, ["system:time_start"]) # Scale optical bands


# --- Index Calculation Functions ---
# Note: These assume input image bands are already scaled (e.g., 0-1)
# Sentinel-2 SR Harmonized Bands: B2(Blue), B3(Green), B4(Red), B5(VNIR), B6(VNIR), B7(VNIR), B8(NIR), B8A(Narrow NIR), B11(SWIR1), B12(SWIR2)

def calculate_ndvi(image):
    return image.normalizedDifference(['B8', 'B4']).rename('NDVI')

def calculate_ndmi(image):
    # NDMI = (NIR - SWIR1) / (NIR + SWIR1) = (B8 - B11) / (B8 + B11)
    return image.normalizedDifference(['B8', 'B11']).rename('NDMI')

def calculate_evi(image):
    # EVI = 2.5 * ((NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1))
    # EVI = 2.5 * ((B8 - B4) / (B8 + 6 * B4 - 7.5 * B2 + 1))
    evi = image.expression(
        '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
            'NIR': image.select('B8'),
            'RED': image.select('B4'),
            'BLUE': image.select('B2')
        })
    return evi.rename('EVI')

def calculate_lai(image):
    # LAI often derived empirically from NDVI or EVI. Using a simple NDVI-based example.
    # Source: e.g., Myneni et al. or specific crop models. This is illustrative.
    # A common simple form: LAI = a * exp(b * NDVI) or polynomial
    # Or use MODIS LAI product directly (requires reprojection/resampling if combining)
    # For demonstration, let's use a simple linear relationship with EVI (adjust coefficients based on calibration)
    # LAI = 3.618 * EVI - 0.118 (Example from MODIS documentation, may not be suitable for S2/Sugarcane)
    # It's generally better to use MODIS LAI or calibrated models.
    # Here, we'll just return EVI as a proxy placeholder or use MODIS.
    # Let's try linking to MODIS LAI (4-day product)
    # Find the closest MODIS image in time.
    modis_lai = MODIS_MCD15A3H.filterDate(
        image.date().advance(-2, 'day'), image.date().advance(2, 'day')
    ).first()
    # Check if MODIS image exists for the timeframe
    lai = ee.Algorithms.If(
        modis_lai,
        modis_lai.select('Lai').multiply(0.1).rename('LAI'), # Scale factor for MODIS LAI
        # Provide a default or calculated fallback if no MODIS image found (e.g., EVI based)
        calculate_evi(image).multiply(3.0).rename('LAI') # Placeholder fallback
    )
    # Need to cast the result of ee.Algorithms.If back to ee.Image
    return ee.Image(lai).copyProperties(image, ["system:time_start"])


def calculate_msi(image):
    # Moisture Stress Index = SWIR1 / NIR = B11 / B8
    msi = image.expression('SWIR1 / NIR', {
        'SWIR1': image.select('B11'),
        'NIR': image.select('B8')
    })
    return msi.rename('MSI')

def calculate_biomass(image):
    # Biomass estimation is complex, often involves SAR or specific models.
    # Using a simple proxy based on NDVI or LAI. This is highly empirical.
    # Example: Biomass ~ a * NDVI + b or using LAI
    # Let's use a placeholder calculation based on NDVI
    # Biomass_proxy = 10 * NDVI (Illustrative, needs calibration)
    return calculate_ndvi(image).multiply(10).rename('Biomass')

def calculate_et(image):
    # Actual Evapotranspiration (ETa) is complex. Often calculated using models like METRIC, SEBAL, or FAO-56 Penman-Monteith with Kc.
    # Using ERA5 meteorological data and a simplified approach (e.g., reference ET * Kc derived from NDVI).
    # Get reference ET from ERA5 (requires calculation from temp, radiation, etc.) or use existing ET products if available.
    # Example: Simplified ETa ~ K_c * ET_ref
    # K_c can be approximated from NDVI: K_c = 1.25 * NDVI + 0.2 (example relationship)
    # Get daily mean 2m air temperature from ERA5 for the image date
    meteo = ERA5_DAILY.filterDate(image.date(), image.date().advance(1, 'day')).first()
    # Check if meteo data exists
    et_approx = ee.Algorithms.If(
        meteo,
        # Placeholder: Assume ETref is related to temperature (highly simplified)
        # A proper ET calculation is much more involved.
        # Example using temperature as a proxy driver (NOT ACCURATE)
        meteo.select('mean_2m_air_temperature').multiply(0.1).rename('ET'), # Very rough proxy
        # Fallback if no meteo data
        calculate_ndvi(image).multiply(0.5).rename('ET') # Fallback based on NDVI
    )
    return ee.Image(et_approx).copyProperties(image, ["system:time_start"])


def calculate_chlorophyll(image):
    # Chlorophyll content indices often use red-edge bands (B5, B6, B7 on Sentinel-2)
    # Example: Chlorophyll Index Red Edge (CIRE) = (NIR / RedEdge) - 1 = (B8 / B5) - 1
    # Or MTCI: (B6 - B5) / (B5 - B4)
    cire = image.expression('(NIR / RE1) - 1', {
        'NIR': image.select('B8'),
        'RE1': image.select('B5') # B5 is the first Red Edge band
    })
    return cire.rename('Chlorophyll')

# --- Function to add all indices to an image ---
def add_ag_indices(image):
    """Calculates and adds all required agricultural indices as bands to an image."""
    image = mask_s2_clouds(image) # Apply cloud mask and scaling first
    # Calculate indices that depend only on S2 bands
    ndvi = calculate_ndvi(image)
    ndmi = calculate_ndmi(image)
    evi = calculate_evi(image)
    msi = calculate_msi(image)
    chlorophyll = calculate_chlorophyll(image)
    biomass_proxy = calculate_biomass(image) # Uses NDVI internally
    # Indices potentially needing external data (handled within their functions)
    lai = calculate_lai(image) # Uses MODIS or EVI fallback
    et_proxy = calculate_et(image) # Uses ERA5 or NDVI fallback

    return image.addBands([ndvi, ndmi, evi, lai, msi, biomass_proxy, et_proxy, chlorophyll])

# --- Function to get weekly data (median composite) ---
@st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", persist=True)
def get_weekly_composite(_geometry_coords, start_date_str, end_date_str, indices_list):
    """
    Fetches Sentinel-2 imagery for the date range, calculates indices,
    and returns a median composite image for the period.
    Uses coordinates instead of ee.Geometry for caching compatibility.
    """
    try:
        _point_geometry = ee.Geometry.Point(_geometry_coords)
        s2_collection = (
            S2_SR_HARMONIZED
            .filterBounds(_point_geometry)
            .filterDate(start_date_str, end_date_str)
            # Pre-filter based on cloud cover metadata (optional, but can speed up)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 50))
            .map(add_ag_indices) # Add all indices
            .select(indices_list) # Select only the requested indices
        )

        # Check if any images are found
        count = s2_collection.size().getInfo()
        if count == 0:
            # st.warning(f"هیچ تصویر Sentinel-2 بدون ابر مناسبی در بازه {start_date_str} تا {end_date_str} یافت نشد.")
            print(f"Warning: No cloud-free Sentinel-2 images found between {start_date_str} and {end_date_str}.")
            return None # Return None if no images

        # Create a median composite for the week
        weekly_composite = s2_collection.median()
        return weekly_composite.clip(_point_geometry.buffer(500)) # Clip to a buffer around the point

    except ee.EEException as e:
        st.error(f"خطای Earth Engine در زمان پردازش تصاویر: {e}")
        return None
    except Exception as e:
        st.error(f"خطای نامشخص در زمان پردازش تصاویر: {e}")
        return None

# --- Function to extract time series data ---
@st.cache_data(show_spinner="در حال استخراج سری زمانی...", persist=True)
def get_indices_timeseries(_geometry_coords, start_date_str, end_date_str, indices_list, _scale=ANALYSIS_SCALE):
    """
    Extracts mean index values over a geometry for a time period.
    Uses coordinates instead of ee.Geometry for caching compatibility.
    """
    try:
        _point_geometry = ee.Geometry.Point(_geometry_coords)
        s2_collection = (
            S2_SR_HARMONIZED
            .filterBounds(_point_geometry)
            .filterDate(start_date_str, end_date_str)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 50))
            .map(add_ag_indices)
            .select(indices_list)
        )

        # Check image count
        count = s2_collection.size().getInfo()
        if count == 0:
            print(f"Warning: No cloud-free Sentinel-2 images found for time series between {start_date_str} and {end_date_str}.")
            return pd.DataFrame(columns=['date'] + indices_list) # Return empty DataFrame

        def extract_values(image):
            # Reduce region to get the mean value for the point/small area
            stats = image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=_point_geometry.buffer(10), # Buffer point slightly
                scale=_scale,
                maxPixels=1e9,
                tileScale=4 # Increase tileScale for potentially faster computation
            )
            # Add date information
            return ee.Feature(None, stats).set('date', image.date().format('YYYY-MM-dd'))

        # Map over the collection and get values
        feature_collection = ee.FeatureCollection(s2_collection.map(extract_values)).filter(ee.Filter.notNull(indices_list)) # Remove nulls

        # Convert FeatureCollection to list of dictionaries
        data = feature_collection.getInfo()['features']

        if not data:
            print(f"Warning: No valid data points extracted for time series between {start_date_str} and {end_date_str}.")
            return pd.DataFrame(columns=['date'] + indices_list)


        # Process data into a pandas DataFrame
        processed_data = []
        for feature in data:
            row = {'date': feature['properties']['date']}
            # Add index values, handling potential missing keys if reduceRegion failed for some indices
            for index_name in indices_list:
                 row[index_name] = feature['properties'].get(index_name) # Use .get for safety
            processed_data.append(row)

        df = pd.DataFrame(processed_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(by='date')
        # Optional: Forward fill or interpolate short gaps if needed
        # df = df.set_index('date').resample('D').mean().interpolate(method='time').reset_index()

        return df.dropna(subset=indices_list, how='all') # Drop rows where ALL indices are null

    except ee.EEException as e:
        st.error(f"خطای Earth Engine در زمان استخراج سری زمانی: {e}")
        return pd.DataFrame(columns=['date'] + indices_list) # Return empty DataFrame on error
    except Exception as e:
        st.error(f"خطای نامشخص در زمان استخراج سری زمانی: {e}")
        return pd.DataFrame(columns=['date'] + indices_list) # Return empty DataFrame on error


# ==============================================================================
# Map Display
# ==============================================================================
st.header("🗺️ نقشه تعاملی مزارع و شاخص‌ها")

# --- Map Initialization ---
# Initial map center coordinates
initial_lat = 31.534442
initial_lon = 48.724416

m = geemap.Map(
    center=[initial_lat, initial_lon],
    zoom=11,
    # layer_control=True, # Geemap adds this by default
    add_google_map=False # Start with satellite
)
m.add_basemap("SATELLITE")
m.add_basemap("HYBRID")


# --- Define Indices and Palettes ---
# Standard Red-Yellow-Green palettes
palette_ndvi = "FFFFFF, CE7E45, DF923D, F1B555, FCD163, 99B718, 74A901, 66A000, 529400, 3E8601, 207401, 056201, 004C00, 023B01, 012E01, 011D01, 011301" # Standard NDVI
palette_ndmi = "ff0000, ffff00, 00ff00" # Red (dry) to Green (wet)
palette_evi = "FFFFFF, CE7E45, DF923D, F1B555, FCD163, 99B718, 74A901, 66A000, 529400, 3E8601, 207401, 056201, 004C00, 023B01, 012E01, 011D01, 011301" # Similar to NDVI
palette_lai = "ff0000, ffff00, 00ff00" # Red (low LAI) to Green (high LAI)
palette_msi = "00ff00, ffff00, ff0000" # Green (low stress) to Red (high stress) - Inverse logic
palette_biomass = "ffffbe, c7e9b4, 7fcdbb, 41b6c4, 1d91c0, 225ea8, 0c2c84" # Yellow to Blue/Green
palette_et = "eff3ff, c6dbef, 9ecae1, 6baed6, 4292c6, 2171b5, 084594" # Blues for water/ET
palette_chlorophyll = "ffffe5,fff7bc,fee391,fec44f,fe9929,ec7014,cc4c02,8c2d04" # Yellow to Brown/Red

indices_info = {
    "NDVI": {"vis": {'min': 0, 'max': 1, 'palette': palette_ndvi}, "calc_func": calculate_ndvi},
    "NDMI": {"vis": {'min': -1, 'max': 1, 'palette': palette_ndmi}, "calc_func": calculate_ndmi},
    "EVI": {"vis": {'min': 0, 'max': 1, 'palette': palette_evi}, "calc_func": calculate_evi},
    "LAI": {"vis": {'min': 0, 'max': 6, 'palette': palette_lai}, "calc_func": calculate_lai}, # Adjust max based on typical values
    "MSI": {"vis": {'min': 0, 'max': 3, 'palette': palette_msi}, "calc_func": calculate_msi}, # High MSI indicates stress
    "Biomass": {"vis": {'min': 0, 'max': 10, 'palette': palette_biomass}, "calc_func": calculate_biomass}, # Placeholder range
    "ET": {"vis": {'min': 0, 'max': 1, 'palette': palette_et}, "calc_func": calculate_et}, # Placeholder range for proxy
    "Chlorophyll": {"vis": {'min': 0, 'max': 5, 'palette': palette_chlorophyll}, "calc_func": calculate_chlorophyll} # Placeholder range
}
index_names = list(indices_info.keys())


# --- Add Farm Markers ---
if not mappable_df.empty:
    # Use geemap's built-in function for adding points from DataFrame
    m.add_points_from_xy(
        mappable_df,
        x="طول جغرافیایی",
        y="عرض جغرافیایی",
        popup=[ # Specify columns for popup
            "مزرعه", "کانال", "اداره", "مساحت داشت",
            "واریته", "سن", "روزهای هفته"
            ],
        layer_name="مزارع فیلتر شده",
        # marker_cluster=True # Option for clustering if many points
        # color_column='SomeStatusColumn', # Can color markers based on a column
        # marker_colors=['#3388ff', '#ff0000'], # Example colors if using color_column
        # icon_names=['info', 'warning'], # Example icons
        # spin=True # Creates a loading spinner, not blinking
    )
    # Note: Blinking marker is not directly supported by geemap's add_points_from_xy.
    # It would require iterating and adding individual folium.Marker objects with custom JS or CSS,
    # which complicates integration with geemap layers. Using standard markers for now.

    # Center map on the filtered data if available
    map_center_lat = mappable_df['عرض جغرافیایی'].mean()
    map_center_lon = mappable_df['طول جغرافیایی'].mean()
    m.set_center(map_center_lat, map_center_lon, 12) # Zoom in slightly more
else:
    st.info("هیچ مزرعه‌ای با مختصات معتبر برای نمایش روی نقشه در روز انتخاب شده وجود ندارد.")


# --- Add Index Layers (using a composite for the selected week) ---
# Use the first mappable farm's coordinates for fetching the composite image (or map center)
if not mappable_df.empty:
    composite_geom_coords = [mappable_df.iloc[0]['طول جغرافیایی'], mappable_df.iloc[0]['عرض جغرافیایی']]
    start_str = analysis_start_date.strftime('%Y-%m-%d')
    end_str = analysis_end_date.strftime('%Y-%m-%d')

    with st.spinner("در حال محاسبه میانگین شاخص‌های هفتگی برای نقشه..."):
        weekly_composite_image = get_weekly_composite(
            composite_geom_coords,
            start_str,
            end_str,
            index_names
        )

    if weekly_composite_image:
        st.success("لایه شاخص‌های هفتگی محاسبه شد.")
        for index_name in index_names:
            vis_params = indices_info[index_name]["vis"]
            try:
                m.addLayer(
                    weekly_composite_image.select(index_name),
                    vis_params,
                    name=f"{index_name} (هفتگی)",
                    shown=False # Start with layers turned off
                )
                # Add color bar for each layer
                # Note: geemap's add_colorbar might add multiple bars if called in a loop like this.
                # It might be better to add one colorbar based on a selected index later or outside the loop.
                # For now, let's add it, but be aware it might look cluttered.
                m.add_colorbar(vis_params, label=index_name, layer_name=f"{index_name} (هفتگی)")

            except ee.EEException as e:
                st.warning(f"خطای GEE هنگام افزودن لایه {index_name}: {e}. ممکن است داده‌ای در این منطقه/بازه زمانی موجود نباشد.")
            except Exception as e:
                 st.warning(f"خطا هنگام افزودن لایه {index_name}: {e}")
    else:
        st.warning(f"تصویری برای محاسبه شاخص‌های هفتگی در بازه {start_str} تا {end_str} یافت نشد.")

else:
     st.warning("هیچ مزرعه‌ای برای محاسبه لایه‌های شاخص یافت نشد.")


# --- Display Map ---
map_output_container = st.container()
with map_output_container:
    m.to_streamlit(height=600)

# --- Map Download Button ---
# Needs function to convert folium map object to image/html
def get_map_download_link(the_map, filename="map.html"):
    """Generates a link to download the map as HTML."""
    try:
        map_html = the_map._repr_html_() # Get the HTML representation of the map
        b64 = base64.b64encode(map_html.encode()).decode()
        href = f'<a href="data:text/html;base64,{b64}" download="{filename}">دانلود نقشه (HTML)</a>'
        return href
    except Exception as e:
        print(f"Error generating map download link: {e}")
        return "خطا در ایجاد لینک دانلود نقشه"

# Note: Downloading as PNG directly from folium/geemap in Streamlit is complex.
# HTML download is more reliable. Geemap's `to_image` often fails in deployed environments.
st.markdown(get_map_download_link(m), unsafe_allow_html=True)


# ==============================================================================
# Detailed Analysis for Selected Farm
# ==============================================================================
st.divider()
st.header(f"📈 تحلیل جزئی مزرعه: {selected_farm_name if selected_farm_details is not None else 'انتخاب نشده'}")

if selected_farm_details is not None and selected_farm_geometry is not None:
    col1, col2 = st.columns([1, 3])

    with col1:
        st.subheader("📄 مشخصات مزرعه")
        # Display farm details using st.dataframe for better formatting or just st.write
        details_df = pd.DataFrame([selected_farm_details[['مزرعه', 'کانال', 'اداره', 'مساحت داشت', 'واریته', 'سن', 'طول جغرافیایی', 'عرض جغرافیایی']]])
        st.dataframe(details_df.T.rename(columns={0: 'مقدار'}), use_container_width=True)

    with col2:
        st.subheader("📊 نمودار سری زمانی شاخص‌ها (دو ماه اخیر)")
        # Fetch time series data for the last ~60 days for the selected farm
        ts_end_date = analysis_end_date # Use the main analysis end date
        ts_start_date = ts_end_date - timedelta(days=59)
        ts_start_str = ts_start_date.strftime('%Y-%m-%d')
        ts_end_str = ts_end_date.strftime('%Y-%m-%d')
        farm_coords = [selected_farm_details['طول جغرافیایی'], selected_farm_details['عرض جغرافیایی']]

        # Fetch time series data using the cached function
        timeseries_df = get_indices_timeseries(
            farm_coords,
            ts_start_str,
            ts_end_str,
            index_names
        )

        if not timeseries_df.empty:
            # Melt dataframe for Plotly
            timeseries_melted = timeseries_df.melt(
                id_vars=['date'],
                var_name='شاخص',
                value_name='مقدار'
            )
            # Remove rows with NaN values that might remain
            timeseries_melted = timeseries_melted.dropna(subset=['مقدار'])

            if not timeseries_melted.empty:
                # Create Plotly chart
                fig = px.line(
                    timeseries_melted,
                    x='date',
                    y='مقدار',
                    color='شاخص',
                    title=f"روند تغییرات شاخص‌ها برای مزرعه: {selected_farm_name}",
                    labels={'date': 'تاریخ', 'مقدار': 'مقدار شاخص'},
                    markers=True
                )
                fig.update_layout(legend_title_text='شاخص‌ها')
                st.plotly_chart(fig, use_container_width=True)

                # Chart Download Button
                buffer = io.StringIO()
                fig.write_html(buffer, include_plotlyjs='cdn')
                html_bytes = buffer.getvalue().encode()
                b64_html = base64.b64encode(html_bytes).decode()
                href_chart = f'<a href="data:text/html;base64,{b64_html}" download="timeseries_{selected_farm_name}.html">دانلود نمودار (HTML)</a>'
                st.markdown(href_chart, unsafe_allow_html=True)

            else:
                st.warning("داده معتبری برای رسم نمودار سری زمانی یافت نشد (پس از حذف مقادیر نامعتبر).")
        else:
            st.warning(f"داده‌ای برای سری زمانی مزرعه '{selected_farm_name}' در بازه {ts_start_str} تا {ts_end_str} یافت نشد.")

    # --- Weekly Comparison Analysis ---
    st.subheader("⚖️ مقایسه هفتگی")
    # Get average values for the current week and previous week
    current_week_start_str = analysis_start_date.strftime('%Y-%m-%d')
    current_week_end_str = analysis_end_date.strftime('%Y-%m-%d')
    prev_week_start_str = prev_week_start_date.strftime('%Y-%m-%d')
    prev_week_end_str = prev_week_end_date.strftime('%Y-%m-%d')

    # Fetch data for both weeks (can reuse the time series function)
    # Note: This re-runs the time series extraction, could be optimized if needed
    # For simplicity, we call it again for the specific weeks.
    current_week_data = get_indices_timeseries(farm_coords, current_week_start_str, current_week_end_str, index_names)
    prev_week_data = get_indices_timeseries(farm_coords, prev_week_start_str, prev_week_end_str, index_names)

    # Calculate mean for each index in each week
    current_means = current_week_data[index_names].mean()
    prev_means = prev_week_data[index_names].mean()

    comparison_results = []
    valid_comparison = False
    for index in index_names:
        current_val = current_means.get(index)
        prev_val = prev_means.get(index)

        if pd.notna(current_val) and pd.notna(prev_val) and prev_val != 0:
            change_pct = ((current_val - prev_val) / abs(prev_val)) * 100
            comparison_results.append({
                "شاخص": index,
                "هفته اخیر": f"{current_val:.3f}",
                "هفته قبل": f"{prev_val:.3f}",
                "تغییر (%)": f"{change_pct:.1f}%"
            })
            valid_comparison = True # Mark that at least one comparison was possible
        elif pd.notna(current_val) and pd.notna(prev_val): # Handle zero previous value
             comparison_results.append({
                "شاخص": index,
                "هفته اخیر": f"{current_val:.3f}",
                "هفته قبل": f"{prev_val:.3f}",
                "تغییر (%)": "N/A (هفته قبل صفر)"
            })
        else:
             comparison_results.append({
                "شاخص": index,
                "هفته اخیر": f"{current_val:.3f}" if pd.notna(current_val) else "N/A",
                "هفته قبل": f"{prev_val:.3f}" if pd.notna(prev_val) else "N/A",
                "تغییر (%)": "N/A"
            })

    if valid_comparison:
        comparison_df = pd.DataFrame(comparison_results)
        st.dataframe(comparison_df, use_container_width=True)

        # Generate Textual Analysis (Example using NDVI and NDMI)
        st.subheader("📝 تحلیل روند هفتگی")
        analysis_text = f"تحلیل مقایسه‌ای برای **{selected_farm_name}** بین هفته منتهی به {current_week_end_str} و هفته قبل:\n\n"
        try:
            ndvi_comp = comparison_df[comparison_df['شاخص'] == 'NDVI'].iloc[0]
            ndvi_curr = float(ndvi_comp['هفته اخیر']) if ndvi_comp['هفته اخیر'] != 'N/A' else None
            ndvi_prev = float(ndvi_comp['هفته قبل']) if ndvi_comp['هفته قبل'] != 'N/A' else None
            ndvi_change = float(ndvi_comp['تغییر (%)'].replace('%','')) if '%' in ndvi_comp['تغییر (%)'] else None

            if ndvi_curr is not None and ndvi_prev is not None and ndvi_change is not None:
                if ndvi_change > 5:
                    analysis_text += f"- **پوشش گیاهی (NDVI):** بهبود قابل توجه ({ndvi_change:.1f}%) نسبت به هفته قبل مشاهده می‌شود (مقدار فعلی: {ndvi_curr:.3f}). وضعیت رشد مطلوب است.\n"
                elif ndvi_change < -5:
                    analysis_text += f"- **پوشش گیاهی (NDVI):** کاهش قابل توجه ({ndvi_change:.1f}%) نسبت به هفته قبل مشاهده می‌شود (مقدار فعلی: {ndvi_curr:.3f}). نیاز به بررسی عوامل تنش‌زا وجود دارد.\n"
                else:
                    analysis_text += f"- **پوشش گیاهی (NDVI):** تغییرات اندک ({ndvi_change:.1f}%) نسبت به هفته قبل داشته است (مقدار فعلی: {ndvi_curr:.3f}). وضعیت تقریباً پایدار است.\n"
            elif ndvi_curr is not None:
                 analysis_text += f"- **پوشش گیاهی (NDVI):** مقدار در هفته اخیر {ndvi_curr:.3f} بوده است (داده هفته قبل موجود نیست).\n"
            else:
                 analysis_text += f"- **پوشش گیاهی (NDVI):** داده معتبری برای تحلیل یافت نشد.\n"

            ndmi_comp = comparison_df[comparison_df['شاخص'] == 'NDMI'].iloc[0]
            ndmi_curr = float(ndmi_comp['هفته اخیر']) if ndmi_comp['هفته اخیر'] != 'N/A' else None
            ndmi_prev = float(ndmi_comp['هفته قبل']) if ndmi_comp['هفته قبل'] != 'N/A' else None
            ndmi_change = float(ndmi_comp['تغییر (%)'].replace('%','')) if '%' in ndmi_comp['تغییر (%)'] else None

            if ndmi_curr is not None and ndmi_prev is not None and ndmi_change is not None:
                 if ndmi_change > 5: # Higher NDMI is generally better (more moisture)
                     analysis_text += f"- **رطوبت گیاه (NDMI):** بهبود در وضعیت رطوبت ({ndmi_change:.1f}%) نسبت به هفته قبل مشاهده می‌شود (مقدار فعلی: {ndmi_curr:.3f}).\n"
                 elif ndmi_change < -5:
                     analysis_text += f"- **رطوبت گیاه (NDMI):** کاهش در وضعیت رطوبت ({ndmi_change:.1f}%) نسبت به هفته قبل مشاهده می‌شود (مقدار فعلی: {ndmi_curr:.3f}). احتمال وجود تنش خشکی.\n"
                 else:
                     analysis_text += f"- **رطوبت گیاه (NDMI):** تغییرات اندک ({ndmi_change:.1f}%) نسبت به هفته قبل داشته است (مقدار فعلی: {ndmi_curr:.3f}).\n"
            elif ndmi_curr is not None:
                 analysis_text += f"- **رطوبت گیاه (NDMI):** مقدار در هفته اخیر {ndmi_curr:.3f} بوده است (داده هفته قبل موجود نیست).\n"
            else:
                 analysis_text += f"- **رطوبت گیاه (NDMI):** داده معتبری برای تحلیل یافت نشد.\n"

            # Add similar analysis for other key indices like MSI, EVI if desired...

            st.markdown(analysis_text)

        except Exception as e:
             st.warning(f"خطا در تولید تحلیل متنی: {e}")
             st.markdown(analysis_text + "\n *خطا در تکمیل خودکار تحلیل برای برخی شاخص‌ها.*")

    else:
        st.warning("داده کافی برای انجام مقایسه هفتگی (مقادیر معتبر در هر دو هفته) یافت نشد.")

else:
    st.info("برای مشاهده تحلیل جزئی، لطفاً یک مزرعه را از منوی کناری انتخاب کنید.")


# ==============================================================================
# Ranking Table
# ==============================================================================
st.divider()
st.header("🏆 جدول رتبه‌بندی مزارع (بر اساس میانگین هفته اخیر)")

# Calculate average index values for *all mappable farms* in the *filtered day* for the *current week*
# This can be computationally intensive if many farms are selected.
ranking_data = []
if not mappable_df.empty:
    with st.spinner(f"در حال محاسبه میانگین شاخص‌ها برای {len(mappable_df)} مزرعه فیلتر شده..."):
        current_week_start_str = analysis_start_date.strftime('%Y-%m-%d')
        current_week_end_str = analysis_end_date.strftime('%Y-%m-%d')

        for idx, farm_row in mappable_df.iterrows():
            farm_name = farm_row['مزرعه']
            farm_coords = [farm_row['طول جغرافیایی'], farm_row['عرض جغرافیایی']]
            # Use the time series function to get data for the week
            # Note: Caching helps here if the same farm/week is requested multiple times,
            # but iterating through many farms will still trigger many GEE requests.
            week_data = get_indices_timeseries(
                farm_coords,
                current_week_start_str,
                current_week_end_str,
                index_names # Only fetch necessary indices for ranking, e.g., NDVI, NDMI
                # index_names=['NDVI', 'NDMI'] # Optimization: only fetch needed indices
            )
            if not week_data.empty:
                avg_values = week_data[index_names].mean().to_dict()
                avg_values['مزرعه'] = farm_name
                ranking_data.append(avg_values)
            else:
                # Append row with NAs if no data found
                 no_data_row = {index: None for index in index_names}
                 no_data_row['مزرعه'] = farm_name
                 ranking_data.append(no_data_row)


    if ranking_data:
        ranking_df = pd.DataFrame(ranking_data)
        # Select and reorder columns for display
        display_cols = ['مزرعه'] + index_names # Add desired indices here
        ranking_df = ranking_df[display_cols]

        # Define status based on NDVI (example thresholds)
        def get_status(ndvi):
            if pd.isna(ndvi):
                return "نامشخص"
            elif ndvi >= 0.6:
                return "رشد خوب"
            elif ndvi >= 0.3:
                return "متوسط"
            else:
                return "تنش / ضعیف"

        ranking_df['وضعیت رشد (NDVI)'] = ranking_df['NDVI'].apply(get_status)

        # Sort by a key index, e.g., NDVI descending
        ranking_df = ranking_df.sort_values(by='NDVI', ascending=False, na_position='last')

        # Function to apply color styling
        def style_status(row):
            status = row['وضعیت رشد (NDVI)']
            if status == "رشد خوب":
                return ['background-color: lightgreen'] * len(row)
            elif status == "تنش / ضعیف":
                return ['background-color: lightcoral'] * len(row)
            elif status == "متوسط":
                return ['background-color: lightyellow'] * len(row)
            else:
                return [''] * len(row) # Default style

        st.dataframe(
             ranking_df.style.apply(style_status, axis=1).format({idx: "{:.3f}" for idx in index_names if idx in ranking_df.columns}), # Format numeric columns
             use_container_width=True
        )


        # Download Button for Ranking Table
        csv = ranking_df.to_csv(index=False).encode('utf-8')
        st.download_button(
           label="📥 دانلود جدول رتبه‌بندی (CSV)",
           data=csv,
           file_name=f'farm_ranking_{selected_day}_{current_week_end_str}.csv',
           mime='text/csv',
        )
    else:
        st.warning("داده‌ای برای ایجاد جدول رتبه‌بندی یافت نشد.")
else:
     st.info("هیچ مزرعه‌ای برای رتبه‌بندی در روز انتخابی وجود ندارد.")


st.sidebar.markdown("---")
st.sidebar.info("طراحی و پیاده‌سازی: [نام شما/تیم شما]") # Replace with your name/team