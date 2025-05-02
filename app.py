import streamlit as st
import pandas as pd
import geopandas as gpd # <-- Import GeoPandas
import ee
import geemap.foliumap as geemap
import folium
# import json # Not strictly needed if geopandas handles GeoJSON reading
import datetime
import plotly.express as px
import plotly.graph_objects as go
import os
from io import BytesIO
import requests
import traceback
from streamlit_folium import st_folium
import base64
import google.generativeai as genai # Gemini API
from shapely.geometry import Point, Polygon # For type checking if needed

# --- Custom CSS ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide"
)

# Custom CSS for Persian text alignment and professional styling
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');

        /* Main container */
        .main {
            font-family: 'Vazirmatn', sans-serif;
        }

        /* Headers */
        h1, h2, h3 {
            font-family: 'Vazirmatn', sans-serif;
            color: #2c3e50;
            text-align: right;
        }

        /* Metrics */
        .css-1xarl3l { /* This selector might change with Streamlit versions */
            font-family: 'Vazirmatn', sans-serif;
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
            direction: rtl;
        }

        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding: 10px 20px;
            background-color: #f8f9fa;
            border-radius: 5px 5px 0 0;
            font-family: 'Vazirmatn', sans-serif;
            font-weight: 600;
        }

        /* Tables */
        .dataframe {
            font-family: 'Vazirmatn', sans-serif;
            text-align: right;
        }

        /* Sidebar */
        .css-1d391kg { /* This selector might change */
            font-family: 'Vazirmatn', sans-serif;
            direction: rtl;
        }

        /* Custom status badges */
        .status-badge {
            padding: 4px 8px;
            border-radius: 15px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .status-positive {
            background-color: #d4edda;
            color: #155724;
        }
        .status-neutral {
            background-color: #fff3cd;
            color: #856404;
        }
        .status-negative {
            background-color: #f8d7da;
            color: #721c24;
        }
    </style>
""", unsafe_allow_html=True)

# --- Configuration ---
APP_TITLE = "سامانه پایش هوشمند نیشکر"
APP_SUBTITLE = "مطالعات کاربردی شرکت کشت و صنعت دهخدا"
# Initial map center might be adjusted later based on data bounds
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 11 # Adjusted zoom for potentially wider area

# --- File Paths ---
# CSV_FILE_PATH = 'برنامه_ریزی_با_مختصات (1).csv' # <-- Old CSV path
GEOJSON_FILE_PATH = 'farm_geodata_fixed.geojson' # <-- New GeoJSON path
ANALYSIS_CSV_PATH = 'محاسبات 2.csv'
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

# --- Helper Function to Convert Shapely Geometry to EE Geometry ---
def shapely_to_ee_geometry(geometry):
    """Converts a Shapely geometry object to an ee.Geometry object."""
    if geometry is None or not hasattr(geometry, '__geo_interface__'):
        return None
    geo_interface = geometry.__geo_interface__
    geom_type = geo_interface.get('type')
    coordinates = geo_interface.get('coordinates')

    if not geom_type or coordinates is None:
        # Handle potential empty geometries gracefully if needed
        return None # Or raise an error

    try:
        if geom_type == 'Point':
            return ee.Geometry.Point(coordinates)
        elif geom_type == 'Polygon':
            # EE Polygons expect a list of rings, where each ring is a list of [lon, lat] pairs.
            # The first ring is the exterior, subsequent rings are interiors (holes).
            return ee.Geometry.Polygon(coordinates)
        elif geom_type == 'LineString':
             return ee.Geometry.LineString(coordinates)
        elif geom_type == 'MultiPoint':
             return ee.Geometry.MultiPoint(coordinates)
        elif geom_type == 'MultiPolygon':
             return ee.Geometry.MultiPolygon(coordinates)
        elif geom_type == 'MultiLineString':
             return ee.Geometry.MultiLineString(coordinates)
        # Add other types if necessary (GeometryCollection, etc.)
        else:
            st.warning(f"Unsupported geometry type for EE conversion: {geom_type}")
            return None
    except Exception as e:
        st.error(f"Error converting Shapely {geom_type} to ee.Geometry: {e}")
        st.error(f"Coordinates causing error: {coordinates}") # Log coordinates for debugging
        return None

# --- Load Farm Data from GeoJSON ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع (GeoJSON)...")
def load_farm_data(geojson_path=GEOJSON_FILE_PATH):
    """Loads farm data from the specified GeoJSON file."""
    try:
        if not os.path.exists(geojson_path):
             st.error(f"❌ فایل '{geojson_path}' یافت نشد. لطفاً فایل GeoJSON داده‌های مزارع را در مسیر صحیح قرار دهید.")
             st.stop()

        gdf = gpd.read_file(geojson_path)
        st.success(f"✅ فایل GeoJSON '{geojson_path}' با موفقیت خوانده شد ({len(gdf)} features).")

        # Basic validation of properties
        required_props = ['مزرعه', 'روز', 'گروه'] # Removed 'سن', 'واریته' as maybe not always needed for filtering? Add back if essential for filtering.
        if not all(prop in gdf.columns for prop in required_props):
            missing_cols = [p for p in required_props if p not in gdf.columns]
            st.error(f"❌ فایل GeoJSON باید شامل Propertyهای ضروری باشد: {', '.join(missing_cols)} وجود ندارد.")
            st.stop()

        # --- CRS Handling ---
        if gdf.crs is None:
            st.warning("⚠️ سیستم مختصات (CRS) در فایل GeoJSON مشخص نشده است. فرض بر WGS84 (EPSG:4326) گذاشته می‌شود.")
            gdf.set_crs("EPSG:4326", inplace=True)
        elif gdf.crs.to_epsg() != 4326:
            st.warning(f"⚠️ سیستم مختصات فایل {gdf.crs.to_string()} است. در حال تبدیل به WGS84 (EPSG:4326)...")
            try:
                gdf = gdf.to_crs("EPSG:4326")
                st.success("✅ تبدیل سیستم مختصات به WGS84 با موفقیت انجام شد.")
            except Exception as e:
                st.error(f"❌ خطا در تبدیل سیستم مختصات: {e}")
                st.error("لطفاً از صحت سیستم مختصات مبدأ در فایل GeoJSON اطمینان حاصل کنید.")
                st.stop()

        # Drop rows with invalid or empty geometries
        initial_count = len(gdf)
        gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty]
        dropped_count = initial_count - len(gdf)
        if dropped_count > 0:
            st.warning(f"⚠️ {dropped_count} رکورد به دلیل هندسه نامعتبر یا خالی حذف شدند.")

        if gdf.empty:
            st.warning("⚠️ داده معتبری برای مزارع یافت نشد (پس از بررسی هندسه).")
            st.stop()

        # Ensure 'روز' is string type and normalize spaces
        gdf['روز'] = gdf['روز'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
        # Ensure 'گروه' is treated appropriately
        gdf['گروه'] = gdf['گروه'].astype(str).str.strip()
        # Ensure 'مزرعه' is string
        gdf['مزرعه'] = gdf['مزرعه'].astype(str)

        # --- Calculate Centroids (used for point-based analysis like time series) ---
        try:
             gdf['centroid'] = gdf.geometry.centroid
             # Extract lat/lon from centroid for potential fallback display or point needs
             gdf['centroid_lon'] = gdf.centroid.x
             gdf['centroid_lat'] = gdf.centroid.y
        except Exception as e:
             st.error(f"خطا در محاسبه سنتروید هندسه‌ها: {e}")
             # Decide how to handle - stop or continue without centroids?
             st.warning("ادامه بدون اطلاعات سنتروید...")
             gdf['centroid'] = None
             gdf['centroid_lon'] = None
             gdf['centroid_lat'] = None


        st.success(f"✅ داده‌های {len(gdf)} مزرعه با موفقیت بارگذاری و پردازش شد.")
        return gdf

    except FileNotFoundError: # Should be caught by os.path.exists, but just in case
        st.error(f"❌ فایل '{geojson_path}' یافت نشد.")
        st.stop()
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری یا پردازش فایل GeoJSON: {e}")
        st.error(traceback.format_exc())
        st.stop()


# --- Load Analysis Data (No Changes Needed Here) ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های محاسبات...")
def load_analysis_data(csv_path=ANALYSIS_CSV_PATH):
    """Loads and preprocesses data from the analysis CSV file."""
    try:
        # Read the raw lines to identify sections
        with open(csv_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Find the headers and split points
        headers_indices = [i for i, line in enumerate(lines) if 'اداره,سن,' in line or 'تولید,سن,' in line]
        if len(headers_indices) < 2:
            # Fallback if only one section header is found (less robust)
            headers_indices = [i for i, line in enumerate(lines) if ',سن,' in line]
            if len(headers_indices) < 1:
                st.error(f"❌ ساختار فایل '{csv_path}' قابل شناسایی نیست. هدرهای مورد انتظار یافت نشد.")
                return None, None # Return None instead of st.stop()
            st.warning("⚠️ فقط یک بخش داده در فایل محاسبات شناسایی شد.")
            section1_start = headers_indices[0] + 1
            section2_start = None
            # Try to find a likely separator (e.g., a mostly blank line)
            blank_lines = [i for i, line in enumerate(lines[section1_start:]) if len(line.strip()) < 5]
            if blank_lines:
                section2_start = section1_start + blank_lines[0] + 1 # Heuristic guess
        else:
            section1_start = headers_indices[0] + 1
            section2_start = headers_indices[1] + 1 # Line after the second header

        # Read the first section (Area)
        df_area = pd.read_csv(csv_path, skiprows=headers_indices[0], nrows=(section2_start - section1_start - 2) if section2_start else None, encoding='utf-8')
        df_area.rename(columns={'اداره': 'مساحت_اداره'}, inplace=True) # Rename first col for clarity
        # Check if the first column is unnamed and likely 'اداره'
        if df_area.columns[0].startswith('Unnamed'):
             df_area.rename(columns={df_area.columns[0]: 'اداره'}, inplace=True)


        # Read the second section (Production) if found
        df_prod = None
        if section2_start:
            # Skip rows until the second header, read until end or grand total
            end_row_prod = None
            for i in range(section2_start, len(lines)):
                if "Grand Total" in lines[i]:
                    end_row_prod = i
                    break
            nrows_prod = (end_row_prod - section2_start) if end_row_prod else None
            df_prod = pd.read_csv(csv_path, skiprows=section2_start-1, nrows=nrows_prod, encoding='utf-8') # Read including header
            # The first column name in the second section might be 'تولید' or unnamed
            if df_prod.columns[0].startswith('Unnamed') or df_prod.columns[0] == 'تولید':
                 df_prod.rename(columns={df_prod.columns[0]: 'اداره'}, inplace=True)


        # --- Preprocessing Function ---
        def preprocess_df(df, section_name):
            if df is None:
                return None
            # Ensure 'اداره' is the first column if it got misplaced
            if 'اداره' not in df.columns and len(df.columns) > 0 and not df.columns[0].startswith('Unnamed'):
                 # This case might indicate a parsing issue earlier
                 st.warning(f"⚠️ ستون 'اداره' در موقعیت مورد انتظار در بخش '{section_name}' یافت نشد.")
                 # Attempt to find it, otherwise return None
                 if 'اداره' in df.columns:
                      pass # Already exists
                 else:
                     # Try to intelligently find it - heuristic: find column before 'سن'
                     try:
                         sen_index = df.columns.get_loc('سن')
                         if sen_index > 0:
                             df.rename(columns={df.columns[sen_index-1]: 'اداره'}, inplace=True)
                         else:
                              st.error(f"Не удалось автоматически найти столбец 'اداره' в разделе '{section_name}'.")
                              return None
                     except KeyError:
                         st.error(f"Столбец 'سن' не найден, не удалось найти 'اداره' в разделе '{section_name}'.")
                         return None


            # Check for required columns
            if not all(col in df.columns for col in ['اداره', 'سن']):
                 st.warning(f"⚠️ ستون های ضروری 'اداره' یا 'سن' در بخش '{section_name}' یافت نشد.")
                 return None

            # Forward fill 'اداره'
            df['اداره'] = df['اداره'].ffill()

            # Filter out 'total' and 'Grand Total' rows in 'سن' and 'اداره'
            df = df[~df['سن'].astype(str).str.contains('total', case=False, na=False)]
            df = df[~df['اداره'].astype(str).str.contains('total|دهخدا', case=False, na=False)] # Filter Grand Total/summary rows in اداره

            # Remove rows where 'اداره' is NaN after ffill (first rows before a number)
            df = df.dropna(subset=['اداره'])

            # Convert 'اداره' to integer where possible
            df['اداره_str'] = df['اداره'].astype(str) # Keep original string if needed
            df['اداره'] = pd.to_numeric(df['اداره'], errors='coerce')
            df = df.dropna(subset=['اداره']) # Drop if conversion failed
            df['اداره'] = df['اداره'].astype(int)


            # Convert numeric columns, coerce errors to NaN
            value_cols = [col for col in df.columns if col not in ['اداره', 'اداره_str', 'سن', 'درصد', 'Grand Total']]
            for col in value_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # Drop Grand Total and درصد columns if they exist
            df = df.drop(columns=['Grand Total', 'درصد'], errors='ignore')

            # Set multi-index for easier access
            if 'اداره' in df.columns and 'سن' in df.columns:
                try:
                    df = df.set_index(['اداره', 'سن'])
                except KeyError as e:
                     st.error(f"خطا در تنظیم ایندکس چندگانه ({e}). ستون‌های موجود: {df.columns}")
                     return None # Stop processing this df
            else:
                 st.warning(f"⚠️ امکان تنظیم ایندکس چندگانه در بخش '{section_name}' وجود ندارد.")


            return df

        df_area_processed = preprocess_df(df_area, "مساحت")
        df_prod_processed = preprocess_df(df_prod, "تولید")

        if df_area_processed is not None or df_prod_processed is not None:
            st.success(f"✅ داده‌های محاسبات با موفقیت بارگذاری و پردازش شد.")
        else:
             st.warning("⚠️ پردازش داده های محاسبات به طور کامل موفقیت آمیز نبود.")

        return df_area_processed, df_prod_processed

    except FileNotFoundError:
        st.error(f"❌ فایل '{csv_path}' یافت نشد. لطفاً فایل CSV داده‌های محاسبات را در مسیر صحیح قرار دهید.")
        return None, None
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری یا پردازش فایل محاسبات CSV: {e}")
        st.error(traceback.format_exc()) # Print detailed error
        return None, None


# Initialize GEE and Load Data
if initialize_gee():
    farm_data_gdf = load_farm_data() # Now loads GeoDataFrame

# Load Analysis Data
analysis_area_df, analysis_prod_df = load_analysis_data()

# ==============================================================================
# Sidebar Filters
# ==============================================================================
st.sidebar.header("تنظیمات نمایش")

# --- Day of the Week Selection ---
if farm_data_gdf is not None:
    available_days = sorted(farm_data_gdf['روز'].unique())
    if not available_days:
        st.sidebar.warning("هیچ روزی در داده‌های مزارع یافت نشد.")
        st.stop()

    selected_day = st.sidebar.selectbox(
        "📅 روز هفته را انتخاب کنید:",
        options=available_days,
        index=0, # Default to the first day
        help="داده‌های مزارع بر اساس این روز فیلتر می‌شوند."
    )

    # --- Filter Data Based on Selected Day ---
    filtered_farms_gdf = farm_data_gdf[farm_data_gdf['روز'] == selected_day].copy()

    if filtered_farms_gdf.empty:
        st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
        st.stop() # Stop if no farms for the selected day

    # --- Farm Selection ---
    available_farms = sorted(filtered_farms_gdf['مزرعه'].unique())
    farm_options = ["همه مزارع"] + available_farms
    selected_farm_name = st.sidebar.selectbox(
        "🌾 مزرعه مورد نظر را انتخاب کنید:",
        options=farm_options,
        index=0, # Default to "All Farms"
        help="مزرعه‌ای که می‌خواهید جزئیات آن را ببینید یا 'همه مزارع' برای نمایش کلی."
    )

else:
    st.error("بارگذاری داده‌های مزارع با شکست مواجه شد. برنامه متوقف می‌شود.")
    st.stop()


# --- Index Selection ---
index_options = {
    "NDVI": "شاخص پوشش گیاهی تفاضلی نرمال شده",
    "EVI": "شاخص پوشش گیاهی بهبود یافته",
    "NDMI": "شاخص رطوبت تفاضلی نرمال شده (وضعیت آبی)",
    "LAI": "شاخص سطح برگ (تخمینی)",
    "MSI": "شاخص تنش رطوبتی",
    "CVI": "شاخص کلروفیل (تخمینی)",
    "SAVI": "شاخص پوشش گیاهی تنظیم شده با خاک" # Added SAVI here too
}
selected_index = st.sidebar.selectbox(
    "📈 شاخص مورد نظر برای نمایش روی نقشه:",
    options=list(index_options.keys()),
    format_func=lambda x: f"{x} ({index_options[x]})",
    index=0 # Default to NDVI
)

# --- Date Range Calculation ---
today = datetime.date.today()
persian_to_weekday = {
    "شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1,
    "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4,
}
try:
    target_weekday = persian_to_weekday[selected_day]
    days_ago = (today.weekday() - target_weekday + 7) % 7
    if days_ago == 0:
         end_date_current = today
    else:
         end_date_current = today - datetime.timedelta(days=days_ago)

    start_date_current = end_date_current - datetime.timedelta(days=6)
    end_date_previous = start_date_current - datetime.timedelta(days=1)
    start_date_previous = end_date_previous - datetime.timedelta(days=6)

    start_date_current_str = start_date_current.strftime('%Y-%m-%d')
    end_date_current_str = end_date_current.strftime('%Y-%m-%d')
    start_date_previous_str = start_date_previous.strftime('%Y-%m-%d')
    end_date_previous_str = end_date_previous.strftime('%Y-%m-%d')

    st.sidebar.info(f"بازه زمانی فعلی: {start_date_current_str} تا {end_date_current_str}")
    st.sidebar.info(f"بازه زمانی قبلی: {start_date_previous_str} تا {end_date_previous_str}")

except KeyError:
    st.sidebar.error(f"نام روز هفته '{selected_day}' قابل شناسایی نیست.")
    st.stop()
except Exception as e:
    st.sidebar.error(f"خطا در محاسبه بازه زمانی: {e}")
    st.stop()


# ==============================================================================
# Google Earth Engine Functions
# ==============================================================================

# --- Cloud Masking Function for Sentinel-2 ---
def maskS2clouds(image):
    """Masks clouds in a Sentinel-2 SR image using the QA band."""
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(
             qa.bitwiseAnd(cirrusBitMask).eq(0))
    try:
        # Use SCL band for more robust masking if available
        scl = image.select('SCL')
        # Define good quality pixel values based on SCL documentation
        # 4: Vegetation, 5: Bare Soils, 6: Water, 7: Unclassified -> treat as good? Maybe not. 11: Snow/Ice
        # Keep 4, 5, 6, 11. Mask out others (Clouds, Shadows, etc.)
        good_quality = scl.remap([4, 5, 6, 11], [1, 1, 1, 1], 0) # Map good classes to 1, others to 0
        combined_mask = mask.And(good_quality)
    except ee.EEException as e:
        # Handle cases where SCL might be missing (though unlikely for S2_SR_HARMONIZED)
        # st.warning(f"Could not apply SCL mask: {e}. Using QA60 mask only.")
        combined_mask = mask # Fallback to QA60 mask


    opticalBands = image.select('B.*').multiply(0.0001)

    return image.addBands(opticalBands, None, True)\
                .updateMask(combined_mask) # Apply combined mask


# --- Index Calculation Functions ---
def add_indices(image):
    """Calculates and adds various indices as bands to an image."""
    # Ensure required bands exist before calculating indices
    required_bands = ['B2', 'B3', 'B4', 'B8', 'B11'] # Blue, Green, Red, NIR, SWIR1
    # Create a default image with 0s for missing bands to avoid errors downstream
    # This might slightly affect results if bands are genuinely missing, but prevents crashes
    band_names = image.bandNames()
    default_values = ee.Image(0).rename(required_bands).cast(image.select(band_names.get(0)).dataType())
    image = image.addBands(default_values, None, True) # Add defaults, overwrite=False (keep original if exists)


    # NDVI
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    # EVI
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)', {
            'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2')
        }).rename('EVI')
    # NDMI
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    # SAVI
    savi = image.expression(
        '((NIR - RED) / (NIR + RED + L)) * (1 + L)',
        {'NIR': image.select('B8'), 'RED': image.select('B4'), 'L': 0.5}
    ).rename('SAVI')
    # MSI
    msi = image.expression('SWIR1 / NIR', {
        'SWIR1': image.select('B11').max(ee.Image(0.0001)), # Avoid division by zero/very small NIR
        'NIR': image.select('B8').max(ee.Image(0.0001))
    }).rename('MSI')
    # LAI (Placeholder)
    lai = ndvi.multiply(3.5).rename('LAI') # Placeholder - Needs proper calibration
    # CVI (Handle potential division by zero)
    green_safe = image.select('B3').max(ee.Image(0.0001))
    cvi = image.expression('(NIR / GREEN) * (RED / GREEN)', {
        'NIR': image.select('B8'), 'GREEN': green_safe, 'RED': image.select('B4')
    }).rename('CVI')

    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi, savi])


# --- Function to get processed image for a date range and geometry ---
@st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", persist=True)
def get_processed_image(_ee_geometry, start_date, end_date, index_name):
    """
    Gets cloud-masked, index-calculated Sentinel-2 median composite for a given ee.Geometry and date range.
    _ee_geometry: ee.Geometry object (Point, Polygon, etc.)
    start_date, end_date: YYYY-MM-DD strings
    index_name: Name of the primary index band to return (e.g., 'NDVI')
    """
    if not isinstance(_ee_geometry, ee.geometry.Geometry):
         st.error(f"خطا: ورودی هندسه نامعتبر برای get_processed_image. نوع دریافتی: {type(_ee_geometry)}")
         return None, "Invalid geometry input."
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_ee_geometry)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)) # Apply cloud masking

        count = s2_sr_col.size().getInfo()
        if count == 0:
            return None, f"No cloud-free Sentinel-2 images found for {start_date} to {end_date} in the area."

        indexed_col = s2_sr_col.map(add_indices)
        median_image = indexed_col.median().setDefaultProjection(s2_sr_col.first().projection()) # Keep projection info

        output_image = median_image.select(index_name)

        return output_image, None # Return the image and no error message
    except ee.EEException as e:
        error_message = f"خطای Google Earth Engine در get_processed_image: {e}"
        # st.error(error_message) # Show error in main app area if needed
        try:
            error_details = e.args[0] if e.args else str(e)
            if isinstance(error_details, str):
                if 'computation timed out' in error_details.lower():
                     error_message += "\n(احتمالاً به دلیل حجم بالای پردازش یا بازه زمانی طولانی)"
                elif 'user memory limit exceeded' in error_details.lower():
                     error_message += "\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده)"
                elif 'geometryconstructors polygon':
                     error_message += "\n(احتمالاً خطایی در مختصات هندسه ورودی وجود دارد)"

        except Exception: pass
        return None, error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در پردازش GEE (get_processed_image): {e}\n{traceback.format_exc()}"
        # st.error(error_message)
        return None, error_message


# --- Function to get time series data for a point ---
@st.cache_data(show_spinner="در حال دریافت سری زمانی شاخص...", persist=True)
def get_index_time_series(_ee_point_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    """Gets a time series of a specified index for a POINT geometry."""
    if not isinstance(_ee_point_geom, ee.geometry.Point):
        st.warning("تابع سری زمانی فقط برای هندسه نقطه‌ای (Point) کار می‌کند.")
        return pd.DataFrame(columns=['date', index_name]), "ورودی باید ee.Geometry.Point باشد."

    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_ee_point_geom)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)
                     .map(add_indices))

        def extract_value(image):
            # Extract value at the point, scale=10m for Sentinel-2
            try:
                value = image.reduceRegion(
                    reducer=ee.Reducer.firstNonNull(), # Get first non-null pixel touching the point
                    geometry=_ee_point_geom,
                    scale=10
                ).get(index_name)
                # Return feature only if value is not null
                return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value}).set('dummy', 1) # Add dummy prop for filter
            except Exception:
                # If reduceRegion fails for an image, return null feature
                 return ee.Feature(None).set('dummy', None)


        # Map and filter null features more robustly
        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.notNull(['dummy', index_name])) # Filter based on dummy and index value

        ts_info = ts_features.getInfo()['features']

        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), f"داده‌ای برای سری زمانی {index_name} یافت نشد."

        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_info if index_name in f.get('properties', {})]
        if not ts_data:
             return pd.DataFrame(columns=['date', index_name]), f"داده معتبر {index_name} در سری زمانی یافت نشد."

        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        # Handle potential duplicate dates (e.g., multiple orbits same day) by taking the mean
        ts_df = ts_df.groupby('date')[index_name].mean().reset_index()
        ts_df = ts_df.sort_values('date').set_index('date')


        return ts_df, None # Return DataFrame and no error
    except ee.EEException as e:
        error_message = f"خطای GEE در دریافت سری زمانی: {e}"
        # st.error(error_message)
        return pd.DataFrame(columns=['date', index_name]), error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در دریافت سری زمانی: {e}\n{traceback.format_exc()}"
        # st.error(error_message)
        return pd.DataFrame(columns=['date', index_name]), error_message


# ==============================================================================
# Function to get all relevant indices for a farm POINT for two periods
# (Used for Needs Analysis)
# ==============================================================================
@st.cache_data(show_spinner="در حال محاسبه شاخص‌های نیازسنجی...", persist=True)
def get_farm_needs_data(_ee_point_geom, start_curr, end_curr, start_prev, end_prev):
    """Calculates mean NDVI, NDMI, EVI, SAVI for current and previous periods using a POINT geometry."""
    results = {
        'NDVI_curr': None, 'NDMI_curr': None, 'EVI_curr': None, 'SAVI_curr': None,
        'NDVI_prev': None, 'NDMI_prev': None, 'EVI_prev': None, 'SAVI_prev': None,
        'error': None
    }
    indices_to_get = ['NDVI', 'NDMI', 'EVI', 'SAVI']

    if not isinstance(_ee_point_geom, ee.geometry.Point):
        results['error'] = "get_farm_needs_data requires an ee.Geometry.Point."
        return results

    def get_mean_values_for_period(start, end):
        period_values = {index: None for index in indices_to_get}
        error_msg = None
        try:
            s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                         .filterBounds(_ee_point_geom)
                         .filterDate(start, end)
                         .map(maskS2clouds)
                         .map(add_indices))

            count = s2_sr_col.size().getInfo()
            if count == 0:
                return period_values, f"هیچ تصویری در بازه {start}-{end} یافت نشد"

            median_image = s2_sr_col.median()

            # Reduce region using the point geometry
            mean_dict = median_image.select(indices_to_get).reduceRegion(
                reducer=ee.Reducer.firstNonNull(), # Use firstNonNull for point geometry
                geometry=_ee_point_geom,
                scale=10  # Scale in meters
            ).getInfo()

            if mean_dict:
                for index in indices_to_get:
                    period_values[index] = mean_dict.get(index) # Returns None if key missing
            else:
                 error_msg = f"reduceRegion did not return results for {start}-{end}."

            return period_values, error_msg # Return error if reduceRegion failed

        except ee.EEException as e:
            error_msg = f"خطای GEE در بازه {start}-{end}: {e}"
            return period_values, error_msg
        except Exception as e:
            error_msg = f"خطای ناشناخته در بازه {start}-{end}: {e}"
            return period_values, error_msg

    # Get data for current period
    curr_values, err_curr = get_mean_values_for_period(start_curr, end_curr)
    if err_curr:
        results['error'] = err_curr
    else:
        results['NDVI_curr'] = curr_values.get('NDVI')
        results['NDMI_curr'] = curr_values.get('NDMI')
        results['EVI_curr'] = curr_values.get('EVI')
        results['SAVI_curr'] = curr_values.get('SAVI')

    # Get data for previous period
    prev_values, err_prev = get_mean_values_for_period(start_prev, end_prev)
    if err_prev:
        results['error'] = f"{results.get('error', '')} | {err_prev}" if results.get('error') else err_prev # Append errors
    else:
        results['NDVI_prev'] = prev_values.get('NDVI')
        results['NDMI_prev'] = prev_values.get('NDMI')
        results['EVI_prev'] = prev_values.get('EVI')
        results['SAVI_prev'] = prev_values.get('SAVI')


    # Check if essential current data is missing even if no specific error was raised
    if results['NDVI_curr'] is None or results['NDMI_curr'] is None:
         if not results['error']: # Add a generic error if no specific one exists
              results['error'] = f"Essential index data (NDVI/NDMI) could not be retrieved for the current period ({start_curr}-{end_curr})."
         elif "هیچ تصویری در بازه" not in results['error']: # Don't overwrite the 'no image' error
              results['error'] += f" | Essential index data (NDVI/NDMI) missing for current period."


    return results

# ==============================================================================
# Gemini AI Helper Functions (No changes needed here)
# ==============================================================================
@st.cache_resource
def configure_gemini():
    """Configures the Gemini API client using a hardcoded API key (NOT RECOMMENDED)."""
    try:
        # --- WARNING: Hardcoding API keys is insecure! Use Streamlit secrets instead. ---
        # Replace with your actual key or load from secrets
        api_key = os.environ.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE") # Example: Load from env var or hardcode
        # api_key = "AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ" # Direct hardcoding (Bad practice)

        if not api_key or api_key == "YOUR_API_KEY_HERE":
             st.warning(" کلید API جمینای یافت نشد یا تنظیم نشده است. تحلیل هوش مصنوعی غیرفعال خواهد بود.")
             st.info("برای فعال‌سازی، کلید خود را در متغیر محیطی GEMINI_API_KEY قرار دهید یا مستقیماً در کد جایگزین کنید (توصیه نمی‌شود).")
             return None

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash') # Use the latest flash model
        print("Gemini Configured Successfully.")
        return model
    except Exception as e:
        st.error(f"❌ خطا در تنظیم Gemini API: {e}")
        return None

@st.cache_data(show_spinner="در حال دریافت تحلیل هوش مصنوعی...", persist=True)
def get_ai_analysis(_model, farm_name, index_data, recommendations):
    """Generates AI analysis for the farm's condition."""
    if _model is None:
        return "سرویس هوش مصنوعی در دسترس نیست."

    # Format current and previous values safely
    def format_val(val):
        return f"{val:.3f}" if isinstance(val, (int, float)) else "N/A"

    data_str = ""
    if 'NDVI_curr' in index_data: data_str += f"NDVI فعلی: {format_val(index_data['NDVI_curr'])} (قبلی: {format_val(index_data.get('NDVI_prev'))})\n"
    if 'NDMI_curr' in index_data: data_str += f"NDMI فعلی: {format_val(index_data['NDMI_curr'])} (قبلی: {format_val(index_data.get('NDMI_prev'))})\n"
    if 'EVI_curr' in index_data: data_str += f"EVI فعلی: {format_val(index_data['EVI_curr'])} (قبلی: {format_val(index_data.get('EVI_prev'))})\n"
    if 'SAVI_curr' in index_data: data_str += f"SAVI فعلی: {format_val(index_data['SAVI_curr'])} (قبلی: {format_val(index_data.get('SAVI_prev'))})\n"
    if not data_str: data_str = "داده شاخصی در دسترس نیست."

    prompt = f"""
    شما یک متخصص کشاورزی نیشکر هستید. لطفاً وضعیت مزرعه '{farm_name}' را بر اساس داده‌های شاخص و توصیه‌های اولیه زیر تحلیل کنید و یک توضیح کوتاه و کاربردی به زبان فارسی ارائه دهید. تمرکز تحلیل بر نیاز آبیاری و کودی باشد.

    داده‌های شاخص:
    {data_str}
    توصیه‌های اولیه:
    {', '.join(recommendations) if recommendations else 'هیچ توصیه‌ای وجود ندارد.'}

    تحلیل شما (کوتاه و مختصر):
    """

    try:
        response = _model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.warning(f"⚠️ خطا در ارتباط با Gemini API: {e}")
        # Provide more specific feedback if possible (e.g., quota exceeded, API key issue)
        if "API key not valid" in str(e):
            return "خطا: کلید API جمینای نامعتبر است."
        return "خطا در دریافت تحلیل هوش مصنوعی."


# ==============================================================================
# Main Application Layout (Using Tabs)
# ==============================================================================

# Configure Gemini Model at the start
gemini_model = configure_gemini()

tab1, tab2, tab3 = st.tabs(["📊 پایش مزارع", "📈 تحلیل محاسبات", "💧کود و آبیاری"])

with tab1:
    # ==============================================================================
    # Main Panel Display
    # ==============================================================================

    # --- Get Selected Farm Geometry and Details ---
    selected_farm_details = None
    selected_farm_shapely_geom = None # Shapely geometry from GeoDataFrame
    selected_farm_ee_geom = None # Converted ee.Geometry
    map_bounds = None # To store bounds for map centering

    if selected_farm_name == "همه مزارع":
        # Use the total bounds of all filtered farms for the map view and GEE image extent
        if not filtered_farms_gdf.empty:
             # Get bounds [minx, miny, maxx, maxy]
             map_bounds = filtered_farms_gdf.total_bounds
             selected_farm_ee_geom = ee.Geometry.Rectangle(map_bounds.tolist())
             # Calculate approx center for map view
             map_center_lon = (map_bounds[0] + map_bounds[2]) / 2
             map_center_lat = (map_bounds[1] + map_bounds[3]) / 2
        else:
             # Fallback if somehow the filtered df is empty here
             map_center_lat = INITIAL_LAT
             map_center_lon = INITIAL_LON
             selected_farm_ee_geom = None # No geometry to process
             st.warning("هیچ مزرعه ای برای نمایش در حالت 'همه مزارع' یافت نشد.")

        st.subheader(f"نمایش کلی مزارع برای روز: {selected_day}")
        st.info(f"تعداد مزارع در این روز: {len(filtered_farms_gdf)}")

    else:
        # Get details for the single selected farm
        try:
            selected_farm_details = filtered_farms_gdf[filtered_farms_gdf['مزرعه'] == selected_farm_name].iloc[0]
            selected_farm_shapely_geom = selected_farm_details.geometry
            map_bounds = selected_farm_shapely_geom.bounds # Get bounds of the single polygon
            # Calculate center from polygon bounds
            map_center_lon = (map_bounds[0] + map_bounds[2]) / 2
            map_center_lat = (map_bounds[1] + map_bounds[3]) / 2
            # Convert the polygon to ee.Geometry for GEE processing
            selected_farm_ee_geom = shapely_to_ee_geometry(selected_farm_shapely_geom)

            if selected_farm_ee_geom is None:
                 st.error(f"خطا در تبدیل هندسه مزرعه '{selected_farm_name}' به فرمت Earth Engine.")
                 # Optionally try using centroid as fallback?
                 if selected_farm_details['centroid'] is not None:
                      st.warning("استفاده از سنتروید به عنوان جایگزین...")
                      selected_farm_ee_geom = shapely_to_ee_geometry(selected_farm_details['centroid'])
                      if selected_farm_ee_geom is None:
                           st.error("تبدیل سنتروید نیز با شکست مواجه شد.")
                           selected_farm_details = None # Prevent further processing


            st.subheader(f"جزئیات مزرعه: {selected_farm_name} (روز: {selected_day})")
            # Display farm details
            details_cols = st.columns(3)
            with details_cols[0]:
                # Area: Calculate from geometry if not in properties
                try:
                    # Calculate area in hectares (assuming CRS is geographic - EPSG:4326)
                    # For accurate area, reproject to a suitable projected CRS first (e.g., UTM)
                    # This is a rough estimate using geographic coordinates
                    # area_m2 = selected_farm_details.geometry.to_crs(epsg=32639).area # Example: UTM 39N
                    # area_ha = area_m2 / 10000
                    # st.metric("مساحت تخمینی (هکتار)", f"{area_ha:,.2f}")
                    # Or just show centroid if area calc is complex/slow
                    st.metric("سنتروید", f"{selected_farm_details['centroid_lat']:.5f}, {selected_farm_details['centroid_lon']:.5f}" if selected_farm_details['centroid_lat'] else "N/A")

                except Exception as e:
                    # st.metric("مساحت", "خطا در محاسبه")
                    st.metric("سنتروید", f"{selected_farm_details['centroid_lat']:.5f}, {selected_farm_details['centroid_lon']:.5f}" if selected_farm_details['centroid_lat'] else "N/A")

                st.metric("واریته", f"{selected_farm_details.get('واریته', 'N/A')}")
            with details_cols[1]:
                st.metric("گروه", f"{selected_farm_details.get('گروه', 'N/A')}")
                st.metric("سن", f"{selected_farm_details.get('سن', 'N/A')}")
            with details_cols[2]:
                 # Display polygon bounds or centroid
                 if map_bounds:
                      st.metric("محدوده (تقریبی)", f"Lon: {map_bounds[0]:.4f}-{map_bounds[2]:.4f}, Lat: {map_bounds[1]:.4f}-{map_bounds[3]:.4f}")
                 else:
                      st.metric("مختصات", "N/A")

        except IndexError:
             st.error(f"مزرعه با نام '{selected_farm_name}' در داده های فیلتر شده یافت نشد.")
             selected_farm_details = None
             selected_farm_ee_geom = None
        except Exception as e:
             st.error(f"خطا در بازیابی جزئیات مزرعه '{selected_farm_name}': {e}")
             selected_farm_details = None
             selected_farm_ee_geom = None


    # --- Map Display ---
    st.markdown("---")
    st.subheader(" نقشه وضعیت مزارع")

    vis_params = {
        'NDVI': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
        'EVI': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
        'NDMI': {'min': -1, 'max': 1, 'palette': ['brown', 'white', 'blue']},
        'LAI': {'min': 0, 'max': 6, 'palette': ['white', 'lightgreen', 'darkgreen']},
        'MSI': {'min': 0, 'max': 3, 'palette': ['blue', 'white', 'brown']}, # Lower MSI = more moisture
        'CVI': {'min': 0, 'max': 20, 'palette': ['yellow', 'lightgreen', 'darkgreen']},
        'SAVI': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
    }

    # Use calculated center if available, otherwise default
    map_disp_center_lat = map_center_lat if 'map_center_lat' in locals() else INITIAL_LAT
    map_disp_center_lon = map_center_lon if 'map_center_lon' in locals() else INITIAL_LON
    map_zoom = INITIAL_ZOOM if selected_farm_name == "همه مزارع" else 14 # Zoom closer for single farm


    m = geemap.Map(
        location=[map_disp_center_lat, map_disp_center_lon],
        zoom=map_zoom,
        add_google_map=False
    )
    m.add_basemap("HYBRID")

    # Get the processed GEE image layer for the current week
    gee_image_current = None
    error_msg_current = None
    if selected_farm_ee_geom:
        with st.spinner(f"در حال دریافت تصویر ماهواره‌ای ({selected_index})..."):
            gee_image_current, error_msg_current = get_processed_image(
                selected_farm_ee_geom, start_date_current_str, end_date_current_str, selected_index
            )
        if error_msg_current:
            st.warning(f"خطا در دریافت لایه GEE: {error_msg_current}")
        elif gee_image_current is None:
             st.warning(f"لایه GEE برای دوره فعلی ({selected_index}) بازگردانده نشد.")


    # Add GEE layer to map if available
    if gee_image_current:
        try:
            m.addLayer(
                gee_image_current,
                vis_params.get(selected_index, {'palette': 'viridis'}), # Default palette
                f"{selected_index} ({start_date_current_str} to {end_date_current_str})"
            )
        except Exception as map_err:
            st.error(f"خطا در افزودن لایه GEE به نقشه: {map_err}")
            st.error(traceback.format_exc())
    elif selected_farm_ee_geom : # Only show warning if we expected an image
        st.warning(f"تصویر ماهواره‌ای ({selected_index}) برای نمایش در این بازه زمانی یافت نشد یا خطایی رخ داد.")


    # Add Farm Geometries (Polygons) to the map
    try:
        if selected_farm_name == "همه مزارع":
            if not filtered_farms_gdf.empty:
                 # Add all filtered farms as GeoJSON layer
                 geojson_data = filtered_farms_gdf.__geo_interface__ # Convert GDF to GeoJSON dict
                 # Define a style function for coloring polygons (optional)
                 # def style_function(feature):
                 #      return {'fillColor': '#ffaf00', 'color': 'black', 'weight': 1, 'fillOpacity': 0.5}
                 geemap.add_geojson(m, geojson_data, layer_name="مزارع")
                 # Add tooltips/popups
                 for idx, farm in filtered_farms_gdf.iterrows():
                      if farm.geometry: # Check if geometry exists
                           # Use centroid for marker popup if polygons are too dense
                            popup_text = f"مزرعه: {farm['مزرعه']}<br>گروه: {farm.get('گروه', 'N/A')}<br>سن: {farm.get('سن', 'N/A')}"
                            folium.Marker(
                                location=[farm['centroid_lat'], farm['centroid_lon']],
                                popup=popup_text,
                                tooltip=farm['مزرعه'],
                                icon=folium.Icon(color='blue', icon='info-sign')
                            ).add_to(m)

        elif selected_farm_details is not None and selected_farm_shapely_geom is not None:
             # Add the single selected farm polygon
             geojson_data = selected_farm_details.to_frame().T.__geo_interface__ # Create GeoJSON from the single row Series
             geemap.add_geojson(m, geojson_data, layer_name=selected_farm_name,
                                style_callback=lambda x: {'color': 'red', 'fillColor': 'red', 'fillOpacity': 0.1, 'weight': 2})
             # Add a marker at the centroid for popup
             if selected_farm_details['centroid']:
                    popup_text = f"مزرعه: {selected_farm_name}<br>گروه: {selected_farm_details.get('گروه', 'N/A')}<br>سن: {selected_farm_details.get('سن', 'N/A')}<br>واریته: {selected_farm_details.get('واریته', 'N/A')}"
                    folium.Marker(
                       location=[selected_farm_details['centroid_lat'], selected_farm_details['centroid_lon']],
                       popup=popup_text,
                       tooltip=selected_farm_name,
                       icon=folium.Icon(color='red', icon='star')
                    ).add_to(m)
             # Center map on the selected farm's bounds
             if map_bounds:
                  m.fit_bounds([[map_bounds[1], map_bounds[0]], [map_bounds[3], map_bounds[2]]]) # [[min_lat, min_lon], [max_lat, max_lon]]


    except Exception as e:
        st.error(f"خطا در افزودن هندسه مزارع به نقشه: {e}")
        st.error(traceback.format_exc())


    # Add Legend (Using custom HTML as before)
    legend_html = None
    # Define legend based on index
    if selected_index in ['NDVI', 'EVI', 'LAI', 'CVI', 'SAVI']:
        legend_html = '''
        <div style="position: fixed; bottom: 50px; right: 50px; z-index: 1000; background-color: white; padding: 10px; border: 2px solid grey; border-radius: 5px;">
            <p style="margin: 0;"><strong>{} Legend</strong></p>
            <p style="margin: 0;"><span style="background-color: red; display: inline-block; width: 12px; height: 12px; margin-right: 5px;"></span>بحرانی/پایین</p>
            <p style="margin: 0;"><span style="background-color: yellow; display: inline-block; width: 12px; height: 12px; margin-right: 5px;"></span>متوسط</p>
            <p style="margin: 0;"><span style="background-color: green; display: inline-block; width: 12px; height: 12px; margin-right: 5px;"></span>سالم/بالا</p>
        </div>
        '''.format(selected_index)
    elif selected_index == 'NDMI':
        legend_html = '''
        <div style="position: fixed; bottom: 50px; right: 50px; z-index: 1000; background-color: white; padding: 10px; border: 2px solid grey; border-radius: 5px;">
            <p style="margin: 0;"><strong>{} Legend</strong></p>
            <p style="margin: 0;"><span style="background-color: brown; display: inline-block; width: 12px; height: 12px; margin-right: 5px;"></span>خشک/پایین</p>
            <p style="margin: 0;"><span style="background-color: white; border: 1px solid #ccc; display: inline-block; width: 12px; height: 12px; margin-right: 5px;"></span>متوسط</p>
            <p style="margin: 0;"><span style="background-color: blue; display: inline-block; width: 12px; height: 12px; margin-right: 5px;"></span>مرطوب/بالا</p>
        </div>
        '''.format(selected_index)
    elif selected_index == 'MSI':
         legend_html = '''
         <div style="position: fixed; bottom: 50px; right: 50px; z-index: 1000; background-color: white; padding: 10px; border: 2px solid grey; border-radius: 5px;">
             <p style="margin: 0;"><strong>{} Legend (تنش رطوبتی)</strong></p>
             <p style="margin: 0;"><span style="background-color: blue; display: inline-block; width: 12px; height: 12px; margin-right: 5px;"></span>رطوبت بالا (تنش کم)</p>
             <p style="margin: 0;"><span style="background-color: white; border: 1px solid #ccc; display: inline-block; width: 12px; height: 12px; margin-right: 5px;"></span>متوسط</p>
             <p style="margin: 0;"><span style="background-color: brown; display: inline-block; width: 12px; height: 12px; margin-right: 5px;"></span>رطوبت پایین (تنش زیاد)</p>
         </div>
         '''.format(selected_index)

    if legend_html:
        m.get_root().html.add_child(folium.Element(legend_html))


    m.add_layer_control()
    st_folium(m, width=None, height=500, use_container_width=True)
    st.caption("نقشه شامل لایه ماهواره‌ای (در صورت وجود) و مرز مزارع است. روی مارکرها/مزارع کلیک کنید.")
    st.info("💡 برای ذخیره نقشه، می‌توانید از ابزار عکس گرفتن از صفحه (Screenshot) مرورگر یا سیستم عامل خود استفاده کنید.")


    # --- Time Series Chart ---
    st.markdown("---")
    st.subheader(f"📈 نمودار روند زمانی شاخص {selected_index}")

    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
    elif selected_farm_details is not None:
        # Use the CENTROID for the time series plot
        farm_centroid_shapely = selected_farm_details.get('centroid')
        if farm_centroid_shapely and isinstance(farm_centroid_shapely, Point):
            farm_centroid_ee = shapely_to_ee_geometry(farm_centroid_shapely)

            if farm_centroid_ee:
                # Define a longer period for the time series chart (e.g., last 6 months)
                timeseries_end_date = today.strftime('%Y-%m-%d')
                timeseries_start_date = (today - datetime.timedelta(days=180)).strftime('%Y-%m-%d')

                ts_df, ts_error = get_index_time_series(
                    farm_centroid_ee,
                    selected_index,
                    start_date=timeseries_start_date,
                    end_date=timeseries_end_date
                )

                if ts_error:
                    st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
                elif not ts_df.empty:
                    fig_ts = px.line(ts_df, x=ts_df.index, y=selected_index,
                                    title=f'روند زمانی {selected_index} برای مزرعه {selected_farm_name} (6 ماه اخیر)',
                                    markers=True, labels={'index':'تاریخ'})
                    fig_ts.update_layout(xaxis_title='تاریخ', yaxis_title=selected_index)
                    st.plotly_chart(fig_ts, use_container_width=True)
                    # st.line_chart(ts_df[selected_index]) # Simpler chart
                else:
                    st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} در بازه مشخص شده یافت نشد.")
            else:
                st.error("خطا در تبدیل سنتروید مزرعه به فرمت GEE برای سری زمانی.")
        else:
            st.warning("سنتروید معتبر برای این مزرعه جهت نمایش سری زمانی یافت نشد.")
    else:
         # Handle case where selected_farm_details might be None after an error
         st.warning("جزئیات مزرعه انتخاب شده در دسترس نیست.")


    # ==============================================================================
    # Helper Function for Status Determination (No change needed)
    # ==============================================================================
    def determine_status(row, index_name):
        """Determines the status based on change in index value."""
        change_col = f'{index_name}_تغییر' # Use specific change column name
        curr_col = f'{index_name}_هفته_جاری'
        prev_col = f'{index_name}_هفته_قبل'

        if pd.isna(row.get(change_col)) or pd.isna(row.get(curr_col)) or pd.isna(row.get(prev_col)):
            return "بدون داده"

        change_val = row[change_col]
        threshold = 0.05 # Threshold for significant change

        # Indices where higher is better
        if index_name in ['NDVI', 'EVI', 'LAI', 'CVI', 'NDMI', 'SAVI']:
            if change_val > threshold: return "رشد مثبت / بهبود"
            elif change_val < -threshold: return "تنش / کاهش"
            else: return "ثابت"
        # Indices where lower is better (MSI)
        elif index_name in ['MSI']:
            if change_val < -threshold: return "بهبود" # Negative change means improvement
            elif change_val > threshold: return "تنش / بدتر شدن"
            else: return "ثابت"
        else: return "نامشخص" # Default case


    # ==============================================================================
    # Ranking Table
    # ==============================================================================
    st.markdown("---")
    st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day})")
    st.markdown("مقایسه مقادیر متوسط شاخص (در سنتروید مزرعه) در هفته جاری با هفته قبل.")

    # NOTE: This function now uses the CENTROID of each farm for calculations.
    @st.cache_data(show_spinner=f"در حال محاسبه {selected_index} برای مزارع...", persist=True)
    def calculate_weekly_indices_at_centroid(_farms_gdf, index_name, start_curr, end_curr, start_prev, end_prev):
        """Calculates the average index value AT THE CENTROID for current/previous week."""
        results = []
        errors = []
        total_farms = len(_farms_gdf)
        progress_bar = st.progress(0)
        status_placeholder = st.empty() # Placeholder for status updates

        for i, (idx, farm) in enumerate(_farms_gdf.iterrows()):
            farm_name = farm['مزرعه']
            status_placeholder.text(f"پردازش مزرعه {i+1}/{total_farms}: {farm_name}")

            centroid_shapely = farm.get('centroid')
            if not centroid_shapely or not isinstance(centroid_shapely, Point):
                errors.append(f"{farm_name}: سنتروید نامعتبر یا ناموجود.")
                results.append({
                    'مزرعه': farm_name, 'گروه': farm.get('گروه', 'N/A'),
                    f'{index_name}_هفته_جاری': None, f'{index_name}_هفته_قبل': None,
                    f'{index_name}_تغییر': None
                })
                progress_bar.progress((i + 1) / total_farms)
                continue # Skip to next farm

            point_ee_geom = shapely_to_ee_geometry(centroid_shapely)
            if not point_ee_geom:
                errors.append(f"{farm_name}: خطا در تبدیل سنتروید به ee.Geometry.")
                results.append({
                    'مزرعه': farm_name, 'گروه': farm.get('گروه', 'N/A'),
                    f'{index_name}_هفته_جاری': None, f'{index_name}_هفته_قبل': None,
                    f'{index_name}_تغییر': None
                })
                progress_bar.progress((i + 1) / total_farms)
                continue

            # --- Sub-function to get value for a period ---
            def get_mean_value_at_point(point_geom, start, end):
                try:
                    image, error = get_processed_image(point_geom, start, end, index_name)
                    if image:
                        mean_dict = image.reduceRegion(
                            reducer=ee.Reducer.firstNonNull(), # Use firstNonNull for point
                            geometry=point_geom,
                            scale=10
                        ).getInfo()
                        val = mean_dict.get(index_name) if mean_dict else None
                        if val is None and not error: # Check if reduceRegion failed silently
                             error = f"مقدار {index_name} در نقطه یافت نشد ({start}-{end})."
                        return val, error
                    else:
                        # If get_processed_image returned None, use its error message
                        return None, error if error else f"تصویری برای بازه {start}-{end} یافت نشد."
                except Exception as e:
                     error_msg = f"خطا در محاسبه مقدار برای {farm_name} ({start}-{end}): {e}"
                     return None, error_msg
            # --- End sub-function ---


            # Calculate for current week
            current_val, err_curr = get_mean_value_at_point(point_ee_geom, start_curr, end_curr)
            if err_curr: errors.append(f"{farm_name} (جاری): {err_curr}")

            # Calculate for previous week
            previous_val, err_prev = get_mean_value_at_point(point_ee_geom, start_prev, end_prev)
            if err_prev: errors.append(f"{farm_name} (قبل): {err_prev}")


            # Calculate change
            change = None
            if isinstance(current_val, (int, float)) and isinstance(previous_val, (int, float)):
                change = current_val - previous_val
            elif current_val is not None or previous_val is not None:
                 # If one value exists but not the other, change is undefined but not strictly None
                 pass # Keep change=None


            results.append({
                'مزرعه': farm_name,
                'گروه': farm.get('گروه', 'N/A'),
                f'{index_name}_هفته_جاری': current_val,
                f'{index_name}_هفته_قبل': previous_val,
                f'{index_name}_تغییر': change
            })

            progress_bar.progress((i + 1) / total_farms)
            # time.sleep(0.01) # Optional small delay

        progress_bar.empty() # Remove progress bar
        status_placeholder.empty() # Remove status text
        return pd.DataFrame(results), errors

    # Calculate and display the ranking table
    ranking_df, calculation_errors = calculate_weekly_indices_at_centroid(
        filtered_farms_gdf,
        selected_index,
        start_date_current_str,
        end_date_current_str,
        start_date_previous_str,
        end_date_previous_str
    )

    # Display any errors that occurred during calculation
    if calculation_errors:
        st.warning("⚠️ برخی خطاها در حین محاسبه شاخص‌ها رخ داد:")
        with st.expander("مشاهده جزئیات خطاها"):
            for error in calculation_errors:
                st.warning(f"- {error}")


    if not ranking_df.empty:
        # Define column names based on selected index
        curr_col = f'{selected_index}_هفته_جاری'
        prev_col = f'{selected_index}_هفته_قبل'
        change_col = f'{selected_index}_تغییر'

        # Sort by the current week's index value
        ascending_sort = selected_index in ['MSI'] # Lower MSI is better (less stress)
        ranking_df_sorted = ranking_df.sort_values(
            by=curr_col,
            ascending=ascending_sort,
            na_position='last' # Put farms with no data at the bottom
        ).reset_index(drop=True)

        # Add rank number
        ranking_df_sorted.index = ranking_df_sorted.index + 1
        ranking_df_sorted.index.name = 'رتبه'

        # Apply the determine_status function
        ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(
            lambda row: determine_status(row, selected_index), axis=1
        )

        # Format numbers for better readability
        cols_to_format = [curr_col, prev_col, change_col]
        for col in cols_to_format:
            if col in ranking_df_sorted.columns:
                 ranking_df_sorted[col] = ranking_df_sorted[col].apply(lambda x: f"{x:.3f}" if isinstance(x, (int, float)) else ("N/A" if pd.isna(x) else x))

        # Select and rename columns for display
        display_df = ranking_df_sorted[['مزرعه', 'گروه', curr_col, prev_col, change_col, 'وضعیت']].copy()
        display_df.rename(columns={
             curr_col: f'{selected_index} (هفته جاری)',
             prev_col: f'{selected_index} (هفته قبل)',
             change_col: 'تغییر',
        }, inplace=True)


        # Display the table
        st.dataframe(display_df, use_container_width=True)

        # --- Summary Stats ---
        st.subheader("📊 خلاصه وضعیت مزارع")
        col1, col2, col3, col4 = st.columns(4)

        status_counts = ranking_df_sorted['وضعیت'].value_counts()
        positive_terms = [s for s in status_counts.index if "بهبود" in s]
        negative_terms = [s for s in status_counts.index if any(sub in s for sub in ["تنش", "کاهش", "بدتر"])]
        neutral_term = "ثابت"
        nodata_term = "بدون داده"

        pos_count = sum(status_counts.get(term, 0) for term in positive_terms)
        neg_count = sum(status_counts.get(term, 0) for term in negative_terms)
        neutral_count = status_counts.get(neutral_term, 0)
        nodata_count = status_counts.get(nodata_term, 0)

        with col1:
            pos_label = positive_terms[0].split('/')[1].strip() if positive_terms else "بهبود" # Get the second part like 'بهبود'
            st.metric(f"🟢 {pos_label}", pos_count)
        with col2:
            st.metric(f"⚪ {neutral_term}", neutral_count)
        with col3:
            neg_label = negative_terms[0].split('/')[0].strip() if negative_terms else "تنش" # Get the first part like 'تنش'
            st.metric(f"🔴 {neg_label}", neg_count)
        with col4:
            st.metric(f"⚫️ {nodata_term}", nodata_count)


        st.info(f"""
        **توضیحات:**
        - **🟢 بهبود**: مزارعی که نسبت به هفته قبل بهبود قابل توجهی داشته‌اند ({selected_index} {"افزایش" if not ascending_sort else "کاهش"} یافته).
        - **⚪ ثابت**: مزارعی که تغییر معناداری نداشته‌اند.
        - **🔴 تنش/کاهش**: مزارعی که نسبت به هفته قبل وضعیت نامطلوب‌تری داشته‌اند ({selected_index} {"کاهش" if not ascending_sort else "افزایش"} یافته).
        - **⚫️ بدون داده**: مزارعی که محاسبه شاخص برای آن‌ها در یک یا هر دو دوره امکان‌پذیر نبوده است.
        """)

        # --- Download Button ---
        # Use the original dataframe with specific index names for download
        csv_data = ranking_df_sorted.to_csv(index=True).encode('utf-8')
        st.download_button(
            label="📥 دانلود جدول رتبه‌بندی (CSV)",
            data=csv_data,
            file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv',
            mime='text/csv',
        )
    elif not calculation_errors: # Only show if no data AND no errors were reported
        st.info(f"داده‌ای برای جدول رتبه‌بندی بر اساس {selected_index} در این بازه زمانی یافت نشد.")


    st.markdown("---")



# --- Tab for Analysis Data (No changes needed in logic) ---
with tab2:
    st.header("تحلیل داده‌های فایل محاسبات")
    st.markdown("نمایش گرافیکی داده‌های مساحت و تولید به تفکیک اداره و سن.")

    if analysis_area_df is None and analysis_prod_df is None:
         st.warning("داده‌های تحلیل (مساحت/تولید) بارگذاری نشده یا در پردازش با خطا مواجه شده است.")
    else:
        # Get unique 'اداره' values
        available_edareh = []
        if analysis_area_df is not None and 'اداره' in analysis_area_df.index.names:
            available_edareh.extend(analysis_area_df.index.get_level_values('اداره').unique().tolist())
        if analysis_prod_df is not None and 'اداره' in analysis_prod_df.index.names:
            available_edareh.extend(analysis_prod_df.index.get_level_values('اداره').unique().tolist())
        available_edareh = sorted(list(set(available_edareh)))

        if not available_edareh:
            st.warning("هیچ 'اداره' معتبری برای نمایش در داده‌های تحلیلی یافت نشد.")
        else:
            selected_edareh = st.selectbox(
                "اداره مورد نظر را انتخاب کنید:",
                options=available_edareh,
                key='analysis_edareh_select'
            )

            st.subheader(f"داده‌های اداره: {selected_edareh}")
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### مساحت (هکتار)")
                if analysis_area_df is not None and selected_edareh in analysis_area_df.index.get_level_values('اداره'):
                    try:
                        df_area_selected = analysis_area_df.loc[selected_edareh].copy()
                        df_area_selected = df_area_selected.dropna(how='all', axis=1).dropna(how='all', axis=0) # Drop empty rows/cols

                        if not df_area_selected.empty:
                            # Prepare data for plots
                            varieties = df_area_selected.columns.tolist()
                            ages = df_area_selected.index.tolist()
                            z_data = df_area_selected.fillna(0).values # Fill NA with 0 for plotting

                            # 3D Surface Plot (if enough data)
                            if len(ages) > 1 and len(varieties) > 1 :
                                try:
                                    fig_3d_area = go.Figure(data=[go.Surface(z=z_data, x=ages, y=varieties, colorscale='Viridis')])
                                    fig_3d_area.update_layout(title=f'Surface Plot مساحت - اداره {selected_edareh}',
                                                              scene=dict(xaxis_title='سن', yaxis_title='واریته', zaxis_title='مساحت (هکتار)'),
                                                              autosize=True, height=500)
                                    st.plotly_chart(fig_3d_area, use_container_width=True)
                                except Exception as e:
                                    st.error(f"خطا در ایجاد نمودار Surface Plot مساحت: {e}")
                                    st.dataframe(df_area_selected) # Fallback table

                            # Histogram of Area per Variety
                            df_area_melt = df_area_selected.reset_index().melt(id_vars='سن', var_name='واریته', value_name='مساحت')
                            df_area_melt = df_area_melt.dropna(subset=['مساحت'])
                            if not df_area_melt.empty:
                                fig_hist_area = px.histogram(df_area_melt, x='واریته', y='مساحت', color='سن',
                                                           title=f'هیستوگرام مساحت بر اساس واریته - اداره {selected_edareh}',
                                                           labels={'مساحت':'مجموع مساحت (هکتار)', 'واریته':'واریته', 'سن':'سن'})
                                st.plotly_chart(fig_hist_area, use_container_width=True)
                            elif not (len(ages) > 1 and len(varieties) > 1): # Show table if only histogram fails
                                 st.info("داده کافی برای هیستوگرام مساحت وجود ندارد.")
                                 st.dataframe(df_area_selected)


                        else:
                             st.info(f"داده معتبر مساحت برای اداره {selected_edareh} پس از حذف مقادیر خالی یافت نشد.")

                    except KeyError:
                         st.info(f"داده مساحت برای اداره {selected_edareh} یافت نشد یا فرمت آن نامعتبر است.")
                    except Exception as e:
                         st.error(f"خطا در پردازش داده مساحت برای اداره {selected_edareh}: {e}")

                else:
                    st.info(f"داده مساحت برای اداره {selected_edareh} در فایل بارگذاری شده یافت نشد.")

            with col2:
                st.markdown("#### تولید (تن)")
                if analysis_prod_df is not None and selected_edareh in analysis_prod_df.index.get_level_values('اداره'):
                    try:
                        df_prod_selected = analysis_prod_df.loc[selected_edareh].copy()
                        df_prod_selected = df_prod_selected.dropna(how='all', axis=1).dropna(how='all', axis=0)

                        if not df_prod_selected.empty:
                            # Prepare data
                            varieties_prod = df_prod_selected.columns.tolist()
                            ages_prod = df_prod_selected.index.tolist()
                            z_data_prod = df_prod_selected.fillna(0).values

                            # 3D Surface Plot
                            if len(ages_prod) > 1 and len(varieties_prod) > 1:
                                try:
                                    fig_3d_prod = go.Figure(data=[go.Surface(z=z_data_prod, x=ages_prod, y=varieties_prod, colorscale='Plasma')])
                                    fig_3d_prod.update_layout(title=f'Surface Plot تولید - اداره {selected_edareh}',
                                                              scene=dict(xaxis_title='سن', yaxis_title='واریته', zaxis_title='تولید (تن)'),
                                                              autosize=True, height=500)
                                    st.plotly_chart(fig_3d_prod, use_container_width=True)
                                except Exception as e:
                                    st.error(f"خطا در ایجاد نمودار Surface Plot تولید: {e}")
                                    st.dataframe(df_prod_selected) # Fallback

                            # Histogram of Production
                            df_prod_melt = df_prod_selected.reset_index().melt(id_vars='سن', var_name='واریته', value_name='تولید')
                            df_prod_melt = df_prod_melt.dropna(subset=['تولید'])
                            if not df_prod_melt.empty:
                                fig_hist_prod = px.histogram(df_prod_melt, x='واریته', y='تولید', color='سن',
                                                           title=f'هیستوگرام تولید بر اساس واریته - اداره {selected_edareh}',
                                                           labels={'تولید':'مجموع تولید (تن)', 'واریته':'واریته', 'سن':'سن'})
                                st.plotly_chart(fig_hist_prod, use_container_width=True)
                            elif not (len(ages_prod) > 1 and len(varieties_prod) > 1):
                                 st.info("داده کافی برای هیستوگرام تولید وجود ندارد.")
                                 st.dataframe(df_prod_selected)

                        else:
                             st.info(f"داده معتبر تولید برای اداره {selected_edareh} پس از حذف مقادیر خالی یافت نشد.")

                    except KeyError:
                        st.info(f"داده تولید برای اداره {selected_edareh} یافت نشد یا فرمت آن نامعتبر است.")
                    except Exception as e:
                        st.error(f"خطا در پردازش داده تولید برای اداره {selected_edareh}: {e}")

                else:
                    st.info(f"داده تولید برای اداره {selected_edareh} در فایل بارگذاری شده یافت نشد.")


# --- Tab for Needs Analysis (Uses Centroid) ---
with tab3:
    st.header("تحلیل نیاز آبیاری و کوددهی (بر اساس سنتروید مزرعه)")

    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا تحلیل نیازهای آن نمایش داده شود.")
    elif selected_farm_details is not None :
        st.subheader(f"تحلیل برای مزرعه: {selected_farm_name}")

        # Get the CENTROID geometry for needs analysis
        farm_centroid_shapely = selected_farm_details.get('centroid')
        if not farm_centroid_shapely or not isinstance(farm_centroid_shapely, Point):
             st.error("سنتروید معتبر برای این مزرعه جهت تحلیل نیازها یافت نشد.")
        else:
            farm_centroid_ee = shapely_to_ee_geometry(farm_centroid_shapely)
            if not farm_centroid_ee:
                st.error("خطا در تبدیل سنتروید مزرعه به فرمت GEE برای تحلیل نیازها.")
            else:
                # --- Thresholds ---
                st.markdown("**تنظیم آستانه‌ها:**")
                ndmi_threshold = st.slider("آستانه NDMI برای هشدار آبیاری:", 0.0, 0.5, 0.25, 0.01, key="ndmi_thresh",
                                         help="اگر NDMI کمتر از این مقدار باشد، نیاز به آبیاری اعلام می‌شود.")
                ndvi_drop_threshold = st.slider("آستانه افت NDVI برای بررسی کوددهی (%):", 0.0, 20.0, 5.0, 0.5, key="ndvi_thresh",
                                            help="اگر NDVI نسبت به هفته قبل بیش از این درصد افت کند، نیاز به بررسی کوددهی اعلام می‌شود.")

                # Get needs data using the centroid
                farm_needs_data = get_farm_needs_data(
                    farm_centroid_ee,
                    start_date_current_str, end_date_current_str,
                    start_date_previous_str, end_date_previous_str
                )

                if farm_needs_data.get('error'):
                    st.error(f"خطا در دریافت داده‌های شاخص برای تحلیل نیازها: {farm_needs_data['error']}")
                elif farm_needs_data.get('NDMI_curr') is None or farm_needs_data.get('NDVI_curr') is None:
                     # This case should ideally be covered by the error check above, but double-check
                    st.warning("داده‌های شاخص لازم (NDMI/NDVI) برای تحلیل در دوره فعلی یافت نشد.")
                    st.caption(f"آخرین خطای گزارش شده (در صورت وجود): {farm_needs_data.get('error', 'هیچ خطای مشخصی ثبت نشده')}")
                else:
                    # Display Current Indices
                    st.markdown("**مقادیر شاخص‌ها (هفته جاری - در سنتروید):**")
                    idx_cols = st.columns(4)
                    def format_metric(val):
                        return f"{val:.3f}" if isinstance(val, (int, float)) else "N/A"

                    with idx_cols[0]: st.metric("NDVI", format_metric(farm_needs_data.get('NDVI_curr')))
                    with idx_cols[1]: st.metric("NDMI", format_metric(farm_needs_data.get('NDMI_curr')))
                    with idx_cols[2]: st.metric("EVI", format_metric(farm_needs_data.get('EVI_curr')))
                    with idx_cols[3]: st.metric("SAVI", format_metric(farm_needs_data.get('SAVI_curr')))

                    # Generate Recommendations
                    recommendations = []
                    ndmi_curr = farm_needs_data.get('NDMI_curr')
                    ndvi_curr = farm_needs_data.get('NDVI_curr')
                    ndvi_prev = farm_needs_data.get('NDVI_prev')

                    # 1. Irrigation Check
                    if isinstance(ndmi_curr, (int, float)) and ndmi_curr < ndmi_threshold:
                        recommendations.append(f"💧 نیاز احتمالی به آبیاری (NDMI: {ndmi_curr:.3f} < {ndmi_threshold:.3f})")
                    elif ndmi_curr is None:
                        recommendations.append("⚠️ وضعیت آبیاری نامشخص (NDMI در دسترس نیست)")


                    # 2. Fertilization Check (NDVI drop)
                    if isinstance(ndvi_curr, (int, float)) and isinstance(ndvi_prev, (int, float)) and ndvi_prev > 0: # Avoid division by zero
                        if ndvi_curr < ndvi_prev:
                            ndvi_change_percent = ((ndvi_prev - ndvi_curr) / ndvi_prev) * 100
                            if ndvi_change_percent > ndvi_drop_threshold:
                                recommendations.append(f"⚠️ نیاز احتمالی به بررسی کوددهی (افت {ndvi_change_percent:.1f}% در NDVI)")
                    elif ndvi_curr is not None and ndvi_prev is None:
                         st.caption("داده NDVI هفته قبل برای بررسی افت در دسترس نیست.")
                    elif ndvi_curr is None:
                         recommendations.append("⚠️ وضعیت کوددهی نامشخص (NDVI فعلی در دسترس نیست)")


                    # 3. Overall Health (based on current NDVI/EVI) - Example thresholds
                    if isinstance(ndvi_curr, (int, float)):
                         if ndvi_curr < 0.4: recommendations.append("📉 پوشش گیاهی ضعیف (NDVI پایین)")
                         # Add EVI check if available
                         evi_curr = farm_needs_data.get('EVI_curr')
                         if isinstance(evi_curr, (int, float)) and evi_curr < 0.3:
                              recommendations.append("📉 پوشش گیاهی ضعیف (EVI پایین)")


                    # 4. Default if no specific issues flagged
                    if not recommendations and ndvi_curr is not None and ndmi_curr is not None:
                         recommendations.append("✅ وضعیت فعلی بر اساس شاخص‌های اصلی مطلوب به نظر می‌رسد.")
                    elif not recommendations:
                         recommendations.append("ℹ️ تحلیل کامل به دلیل نبود برخی داده‌ها امکان‌پذیر نیست.")


                    # Display Recommendations
                    st.markdown("**توصیه‌های اولیه:**")
                    rec_container = st.container()
                    has_warning = False
                    has_error = False
                    if not recommendations:
                         rec_container.info("هیچ توصیه مشخصی ایجاد نشد (احتمالاً به دلیل داده‌های ناکافی).")
                    else:
                        for rec in recommendations:
                            if "آبیاری" in rec or "تنش" in rec or "ضعیف" in rec or "افت" in rec :
                                rec_container.error(rec)
                                has_error = True
                            elif "نامشخص" in rec or "بررسی" in rec:
                                rec_container.warning(rec)
                                has_warning = True
                            else:
                                rec_container.success(rec)

                    # --- Get and Display AI Analysis ---
                    if gemini_model:
                        st.markdown("**تحلیل هوش مصنوعی:**")
                        with st.spinner("در حال تولید تحلیل هوش مصنوعی..."):
                            ai_explanation = get_ai_analysis(gemini_model, selected_farm_name, farm_needs_data, recommendations)
                        st.markdown(ai_explanation)
                    else:
                        st.info("سرویس تحلیل هوش مصنوعی پیکربندی نشده یا در دسترس نیست.")

    else:
        # Handle case where selected_farm_details is None
        st.info("ابتدا یک مزرعه معتبر را از پنل کناری انتخاب کنید.")


# --- Footer ---
st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با استفاده از Streamlit, Google Earth Engine, GeoPandas, و geemap")