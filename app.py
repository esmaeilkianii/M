import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
import json
import datetime
import plotly.express as px
import os
from io import BytesIO
import requests # Needed for getThumbUrl download
import traceback
from streamlit_folium import st_folium
import base64

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
        .css-1d391kg { /* This selector might change with Streamlit versions for sidebar */
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
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 11 # Adjusted default zoom

# --- File Paths (Relative to the script location in Hugging Face) ---
# CSV_FILE_PATH = 'cleaned_output.csv' # No longer used
GEE_ASSET_PATH = 'projects/ee-esmaeilkiani13877/assets/Croplogging-Farm'
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json' # Ensure this file is present

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


# --- Load Farm Data from GEE Asset ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع از Google Earth Engine...")
def load_farm_data(asset_path=GEE_ASSET_PATH):
    """Loads farm data from the specified GEE FeatureCollection asset."""
    try:
        ee_fc = ee.FeatureCollection(asset_path)

        # Function to extract properties and add centroid coordinates and GeoJSON geometry
        def process_feature(feature):
            geom = feature.geometry()
            # Calculate centroid, ensure it's robust (maxError for complex geometries)
            centroid = geom.centroid(maxError=1).coordinates()
            props = feature.toDictionary() # Get all properties from the feature
            
            # Set new properties: centroid coordinates and GeoJSON string of the geometry
            props = props.set('longitude_centroid', centroid.get(0))
            props = props.set('latitude_centroid', centroid.get(1))
            props = props.set('geojson_geometry', geom.toGeoJSONString()) # Store full geometry
            
            # Return a new feature with no geometry (to avoid issues with ee_to_df) 
            # but with all properties including new ones.
            return ee.Feature(None, props)

        # Apply the processing function to each feature
        processed_fc = ee_fc.map(process_feature)
        
        # Convert the processed FeatureCollection to a Pandas DataFrame
        df = geemap.ee_to_df(processed_fc)

        if df.empty:
            st.error(f"❌ داده‌ای از GEE Asset '{asset_path}' بارگذاری نشد یا Asset خالی است.")
            return None

        # Rename columns to match the application's expected Persian names
        # Original GEE columns: Age, Area, Day, Field, Variety, edare, farm, group, system:index, Feature Index
        # Derived columns: longitude_centroid, latitude_centroid, geojson_geometry
        column_mapping = {
            'farm': 'مزرعه',
            'longitude_centroid': 'طول جغرافیایی',
            'latitude_centroid': 'عرض جغرافیایی',
            'Day': 'روزهای هفته',
            'Area': 'مساحت', # Area (Float)
            'Variety': 'واریته', # Variety (String)
            'Field': 'کانال',   # Field (Long) - mapping to 'کانال'
            'Age': 'سن',       # Age (String)
            'edare': 'اداره',    # edare (String)
            'geojson_geometry': 'geojson_geometry' # Keep this for actual geometry
            # 'group' is not currently used by the app
            # 'Feature Index' and 'system:index' are GEE identifiers, not directly used in UI display names
        }
        
        # Select and rename relevant columns
        # Ensure all keys in column_mapping exist in df.columns before trying to rename
        rename_map_filtered = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=rename_map_filtered)
        
        # Keep only the columns that are in the values of rename_map_filtered
        required_df_cols = list(rename_map_filtered.values())
        # Check if essential columns like 'مزرعه' are present after renaming
        if 'مزرعه' not in df.columns or 'طول جغرافیایی' not in df.columns or 'عرض جغرافیایی' not in df.columns:
            st.error(f"❌ ستون های ضروری ('farm', 'Day', centroid coordinates) در GEE Asset یافت نشد یا نامگذاری آنها صحیح نیست.")
            st.error(f"ستون های موجود در DataFrame پس از پردازش: {', '.join(df.columns.tolist())}")
            return None

        df = df[required_df_cols]


        # Basic validation for essential columns (already implicitly done by selection)
        # Convert coordinate columns to numeric
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        
        # Convert 'مساحت' to numeric if it exists
        if 'مساحت' in df.columns:
            df['مساحت'] = pd.to_numeric(df['مساحت'], errors='coerce')

        # Drop rows where essential coordinates are missing after coercion
        df = df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی', 'مزرعه'])

        if df.empty:
            st.warning("⚠️ داده معتبری برای مزارع یافت نشد (پس از حذف رکوردهای بدون مختصات معتبر).")
            return None

        # Ensure 'روزهای هفته' is string type for consistent filtering
        if 'روزهای هفته' in df.columns:
            df['روزهای هفته'] = df['روزهای هفته'].astype(str).str.strip()
        else:
            st.warning("⚠️ ستون 'روزهای هفته' (Day) در داده‌ها یافت نشد. فیلتر روز هفته ممکن است کار نکند.")
            # Add a dummy column if it's critical for downstream logic, or handle absence
            df['روزهای هفته'] = "نامشخص"


        st.success(f"✅ داده‌های {len(df)} مزرعه با موفقیت از GEE بارگذاری شد.")
        return df
    except ee.EEException as e:
        st.error(f"❌ خطا در بارگذاری داده‌ها از Google Earth Engine Asset: {e}")
        st.error(f"لطفاً از صحت مسیر Asset ('{asset_path}') و دسترسی‌های لازم اطمینان حاصل کنید.")
        st.error(traceback.format_exc())
        return None
    except Exception as e:
        st.error(f"❌ خطا در پردازش داده‌های مزارع از GEE: {e}")
        st.error(traceback.format_exc())
        return None

# Initialize GEE and Load Data
if initialize_gee():
    farm_data_df = load_farm_data()
else:
    st.error("❌ امکان ادامه کار بدون اتصال به Google Earth Engine وجود ندارد.")
    st.stop()

if farm_data_df is None or farm_data_df.empty:
    st.error("❌ امکان ادامه کار بدون داده‌های مزارع وجود ندارد.")
    st.stop()


# ==============================================================================
# Sidebar Filters
# ==============================================================================
st.sidebar.header("تنظیمات نمایش")

# --- Day of the Week Selection ---
if 'روزهای هفته' in farm_data_df.columns:
    available_days = sorted(farm_data_df['روزهای هفته'].unique())
    if not available_days: # Handle case where 'روزهای هفته' column exists but has no valid unique values
        st.sidebar.warning("هیچ روزی برای انتخاب یافت نشد. لطفاً داده‌های مزارع را بررسی کنید.")
        st.stop()
    selected_day = st.sidebar.selectbox(
        "📅 روز هفته را انتخاب کنید:",
        options=available_days,
        index=0, # Default to the first day
        help="داده‌های مزارع بر اساس این روز فیلتر می‌شوند."
    )
    # --- Filter Data Based on Selected Day ---
    filtered_farms_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day].copy()
else:
    st.sidebar.warning("ستون 'روزهای هفته' برای فیلتر کردن موجود نیست. همه مزارع نمایش داده می‌شوند.")
    filtered_farms_df = farm_data_df.copy() # Use all farms if day filtering is not possible
    selected_day = "همه روزها" # Placeholder

if filtered_farms_df.empty:
    st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
    st.stop()

# --- Farm Selection ---
available_farms = sorted(filtered_farms_df['مزرعه'].unique())
farm_options = ["همه مزارع"] + available_farms
selected_farm_name = st.sidebar.selectbox(
    "🌾 مزرعه مورد نظر را انتخاب کنید:",
    options=farm_options,
    index=0, # Default to "All Farms"
    help="مزرعه‌ای که می‌خواهید جزئیات آن را ببینید یا 'همه مزارع' برای نمایش کلی."
)

# --- Index Selection ---
index_options = {
    "NDVI": "شاخص پوشش گیاهی تفاضلی نرمال شده",
    "EVI": "شاخص پوشش گیاهی بهبود یافته",
    "NDMI": "شاخص رطوبت تفاضلی نرمال شده",
    "LAI": "شاخص سطح برگ (تخمینی)",
    "MSI": "شاخص تنش رطوبتی",
    "CVI": "شاخص کلروفیل (تخمینی)",
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
    "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4, "نامشخص": -1 # Handle "نامشخص"
}
try:
    if selected_day != "همه روزها" and selected_day != "نامشخص" and selected_day in persian_to_weekday:
        target_weekday = persian_to_weekday[selected_day]
        days_ago = (today.weekday() - target_weekday + 7) % 7
        end_date_current = today - datetime.timedelta(days=days_ago if days_ago != 0 else 0)
    else: # Default to today if day is not specific or mapping fails
        end_date_current = today
        st.sidebar.warning(f"روز هفته '{selected_day}' برای محاسبه دقیق بازه زمانی شناسایی نشد. از تاریخ امروز استفاده می‌شود.")

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
    st.sidebar.error(f"نام روز هفته '{selected_day}' قابل شناسایی نیست. لطفاً داده‌ها را بررسی کنید.")
    st.stop()
except Exception as e:
    st.sidebar.error(f"خطا در محاسبه بازه زمانی: {e}")
    st.stop()


# ==============================================================================
# Google Earth Engine Functions
# ==============================================================================

def maskS2clouds(image):
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
    
    scl = image.select('SCL')
    good_quality_scl = scl.remap([4, 5, 6, 7, 11], [1, 1, 1, 1, 1], 0) # Vegetation, Not Vegetated, Water, Snow/Ice, Bare Soil

    opticalBands = image.select('B.*').multiply(0.0001)
    
    return image.addBands(opticalBands, None, True)\
                .updateMask(mask).updateMask(good_quality_scl)

def add_indices(image):
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)', {
            'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2')
        }).rename('EVI')
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    msi = image.expression('SWIR1 / NIR', {
        'SWIR1': image.select('B11'), 'NIR': image.select('B8')
    }).rename('MSI')
    lai = ndvi.multiply(3.5).rename('LAI') # Placeholder
    green_safe = image.select('B3').max(ee.Image(0.0001))
    cvi = image.expression('(NIR / GREEN) * (RED / GREEN)', {
        'NIR': image.select('B8'), 'GREEN': green_safe, 'RED': image.select('B4')
    }).rename('CVI')
    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi])

@st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", persist=True)
def get_processed_image(_geometry, start_date, end_date, index_name):
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds))
        count = s2_sr_col.size().getInfo()
        if count == 0:
            return None, f"No cloud-free Sentinel-2 images found for {start_date} to {end_date} for the given geometry."
        indexed_col = s2_sr_col.map(add_indices)
        median_image = indexed_col.median()
        output_image = median_image.select(index_name)
        return output_image, None
    except ee.EEException as e:
        error_message = f"خطای Google Earth Engine در get_processed_image: {e}"
        try:
            error_details = e.args[0] if e.args else str(e)
            if isinstance(error_details, str) and 'computation timed out' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل حجم بالای پردازش یا بازه زمانی طولانی)"
            elif isinstance(error_details, str) and 'user memory limit exceeded' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده)"
        except Exception: pass
        return None, error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در پردازش GEE (get_processed_image): {e}\n{traceback.format_exc()}"
        return None, error_message

@st.cache_data(show_spinner="در حال دریافت سری زمانی شاخص...", persist=True)
def get_index_time_series(_point_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)
                     .map(add_indices))
        def extract_value(image):
            value = image.reduceRegion(
                reducer=ee.Reducer.first(), geometry=_point_geom, scale=10
            ).get(index_name)
            return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value})
        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.notNull([index_name]))
        ts_info = ts_features.getInfo()['features']
        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), "داده‌ای برای سری زمانی یافت نشد."
        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_info]
        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df = ts_df.sort_values('date').set_index('date')
        return ts_df, None
    except ee.EEException as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای GEE در دریافت سری زمانی: {e}"
    except Exception as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای ناشناخته در دریافت سری زمانی: {e}\n{traceback.format_exc()}"

# ==============================================================================
# Main Panel Display
# ==============================================================================

selected_farm_details = None
selected_farm_aoi_geom = None # Area of Interest Geometry (can be Point or Polygon)
selected_farm_point_geom_for_timeseries = None # Always a Point (centroid) for time series

if selected_farm_name == "همه مزارع":
    if not filtered_farms_df.empty and 'طول جغرافیایی' in filtered_farms_df.columns:
        min_lon = filtered_farms_df['طول جغرافیایی'].min()
        min_lat = filtered_farms_df['عرض جغرافیایی'].min()
        max_lon = filtered_farms_df['طول جغرافیایی'].max()
        max_lat = filtered_farms_df['عرض جغرافیایی'].max()
        selected_farm_aoi_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
    else: # Fallback if no farms or no coordinates
        selected_farm_aoi_geom = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT]).buffer(10000).bounds() # Default region
    st.subheader(f"نمایش کلی مزارع برای روز: {selected_day}")
    st.info(f"تعداد مزارع در این روز: {len(filtered_farms_df)}")
else:
    selected_farm_details_series = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name]
    if not selected_farm_details_series.empty:
        selected_farm_details = selected_farm_details_series.iloc[0]
        
        # Centroid coordinates (already in DataFrame)
        lat_centroid = selected_farm_details['عرض جغرافیایی']
        lon_centroid = selected_farm_details['طول جغرافیایی']
        selected_farm_point_geom_for_timeseries = ee.Geometry.Point([lon_centroid, lat_centroid])

        # Actual farm geometry (from GeoJSON string)
        if 'geojson_geometry' in selected_farm_details and pd.notna(selected_farm_details['geojson_geometry']):
            try:
                geojson_str = selected_farm_details['geojson_geometry']
                selected_farm_aoi_geom = ee.Geometry(json.loads(geojson_str))
            except Exception as e:
                st.warning(f"خطا در بارگذاری هندسه مزرعه {selected_farm_name}: {e}. از نقطه مرکزی استفاده می‌شود.")
                selected_farm_aoi_geom = selected_farm_point_geom_for_timeseries # Fallback to centroid point
        else:
            st.warning(f"هندسه دقیق (geojson_geometry) برای مزرعه {selected_farm_name} یافت نشد. از نقطه مرکزی استفاده می‌شود.")
            selected_farm_aoi_geom = selected_farm_point_geom_for_timeseries # Fallback

        st.subheader(f"جزئیات مزرعه: {selected_farm_name} (روز: {selected_day})")
        details_cols = st.columns(3)
        with details_cols[0]:
            area_val = selected_farm_details.get('مساحت', 'N/A')
            st.metric("مساحت (هکتار)", f"{area_val:,.2f}" if pd.notna(area_val) and isinstance(area_val, (int, float)) else "N/A")
            st.metric("واریته", f"{selected_farm_details.get('واریته', 'N/A')}")
        with details_cols[1]:
            st.metric("کانال", f"{selected_farm_details.get('کانال', 'N/A')}")
            st.metric("سن", f"{selected_farm_details.get('سن', 'N/A')}")
        with details_cols[2]:
            st.metric("اداره", f"{selected_farm_details.get('اداره', 'N/A')}")
            st.metric("مختصات مرکز", f"{lat_centroid:.5f}, {lon_centroid:.5f}")
    else:
        st.error(f"اطلاعات مزرعه '{selected_farm_name}' یافت نشد.")
        st.stop()

# --- Map Display ---
st.markdown("---")
st.subheader(" نقشه وضعیت مزارع")

vis_params = {
    'NDVI': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
    'EVI': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
    'NDMI': {'min': -1, 'max': 1, 'palette': ['brown', 'white', 'blue']},
    'LAI': {'min': 0, 'max': 6, 'palette': ['white', 'lightgreen', 'darkgreen']},
    'MSI': {'min': 0, 'max': 3, 'palette': ['blue', 'white', 'brown']},
    'CVI': {'min': 0, 'max': 20, 'palette': ['yellow', 'lightgreen', 'darkgreen']},
}

map_center_lat = INITIAL_LAT
map_center_lon = INITIAL_LON
map_initial_zoom = INITIAL_ZOOM

if selected_farm_name != "همه مزارع" and selected_farm_point_geom_for_timeseries:
    map_center_lat = selected_farm_details['عرض جغرافیایی']
    map_center_lon = selected_farm_details['طول جغرافیایی']
    map_initial_zoom = 14 # Zoom closer for single farm

m = geemap.Map(location=[map_center_lat, map_center_lon], zoom=map_initial_zoom, add_google_map=False)
m.add_basemap("HYBRID")

if selected_farm_aoi_geom:
    gee_image_current, error_msg_current = get_processed_image(
        selected_farm_aoi_geom, start_date_current_str, end_date_current_str, selected_index
    )

    if gee_image_current:
        try:
            m.addLayer(
                gee_image_current,
                vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}),
                f"{selected_index} ({start_date_current_str} to {end_date_current_str})"
            )
            # Custom Legend
            legend_html_template = '''
            <div style="position: fixed; bottom: 50px; right: 50px; z-index: 1000; background-color: white; padding: 10px; border: 2px solid grey; border-radius: 5px;">
                <p style="margin: 0;"><strong>{index_name} Legend</strong></p> {items}
            </div>'''
            legend_items_html = ""
            if selected_index in ['NDVI', 'EVI', 'LAI', 'CVI']:
                legend_items_html = """<p style="margin: 0; color: red;">بحرانی/پایین</p>
                                     <p style="margin: 0; color: yellow;">متوسط</p>
                                     <p style="margin: 0; color: green;">سالم/بالا</p>"""
            elif selected_index in ['NDMI', 'MSI']:
                legend_items_html = """<p style="margin: 0; color: blue;">مرطوب/بالا</p>
                                     <p style="margin: 0; color: white; background-color: grey;">متوسط</p>
                                     <p style="margin: 0; color: brown;">خشک/پایین</p>"""
            else:
                legend_items_html = "<p style='margin: 0;'>Low</p><p style='margin: 0;'>Medium</p><p style='margin: 0;'>High</p>"
            
            m.get_root().html.add_child(folium.Element(legend_html_template.format(index_name=selected_index, items=legend_items_html)))

            # Add markers
            if selected_farm_name == "همه مزارع":
                 for idx, farm_row in filtered_farms_df.iterrows():
                     folium.Marker(
                         location=[farm_row['عرض جغرافیایی'], farm_row['طول جغرافیایی']], # Centroid
                         popup=f"مزرعه: {farm_row['مزرعه']}<br>کانال: {farm_row.get('کانال', 'N/A')}<br>اداره: {farm_row.get('اداره', 'N/A')}",
                         tooltip=farm_row['مزرعه'],
                         icon=folium.Icon(color='blue', icon='info-sign')
                     ).add_to(m)
                 if selected_farm_aoi_geom: m.center_object(selected_farm_aoi_geom, zoom=map_initial_zoom)
            elif selected_farm_details is not None: # Single farm
                 folium.Marker(
                     location=[selected_farm_details['عرض جغرافیایی'], selected_farm_details['طول جغرافیایی']], # Centroid
                     popup=f"مزرعه: {selected_farm_name}",
                     tooltip=selected_farm_name,
                     icon=folium.Icon(color='red', icon='star')
                 ).add_to(m)
                 if selected_farm_aoi_geom: m.center_object(selected_farm_aoi_geom, zoom=map_initial_zoom)
            
            m.add_layer_control()
        except Exception as map_err:
            st.error(f"خطا در افزودن لایه به نقشه: {map_err}")
            st.error(traceback.format_exc())
    else:
        st.warning(f"تصویری برای نمایش روی نقشه یافت نشد. {error_msg_current}")
else:
    st.warning("هندسه مزرعه برای نمایش نقشه انتخاب نشده یا نامعتبر است.")

st_folium(m, width=None, height=500, use_container_width=True)
st.caption("برای مشاهده جزئیات روی مارکرها کلیک کنید. از کنترل لایه‌ها برای تغییر نقشه پایه استفاده کنید.")
st.info("💡 برای ذخیره نقشه، می‌توانید از ابزار عکس گرفتن از صفحه (Screenshot) مرورگر یا سیستم عامل خود استفاده کنید.")

# --- Time Series Chart ---
st.markdown("---")
st.subheader(f"📈 نمودار روند زمانی شاخص {selected_index}")

if selected_farm_name == "همه مزارع":
    st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
elif selected_farm_point_geom_for_timeseries: # Use the centroid point geometry
    timeseries_end_date = today.strftime('%Y-%m-%d')
    timeseries_start_date = (today - datetime.timedelta(days=365*2)).strftime('%Y-%m-%d') # 2 years of data

    ts_df, ts_error = get_index_time_series(
        selected_farm_point_geom_for_timeseries,
        selected_index,
        start_date=timeseries_start_date,
        end_date=timeseries_end_date
    )

    if ts_error:
        st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
    elif not ts_df.empty:
        fig = px.line(ts_df, x=ts_df.index, y=selected_index, labels={'index':'تاریخ', selected_index:f'مقدار {selected_index}'})
        fig.update_layout(title_text=f"روند زمانی {selected_index} برای مزرعه {selected_farm_name}", title_x=0.5, xaxis_title="تاریخ", yaxis_title=f"مقدار {selected_index}")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"نمودار تغییرات شاخص {selected_index} برای مزرعه {selected_farm_name} در 2 سال گذشته.")
    else:
        st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} در بازه مشخص شده یافت نشد.")
else:
    st.warning("هندسه مزرعه برای نمودار سری زمانی در دسترس نیست (نقطه مرکزی مزرعه یافت نشد).")

# --- Ranking Table ---
st.markdown("---")
st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day})")
st.markdown("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل.")

@st.cache_data(show_spinner=f"در حال محاسبه {selected_index} برای مزارع...", persist=True)
def calculate_weekly_indices(_farms_df_input, index_name_calc, start_curr, end_curr, start_prev, end_prev):
    results = []
    errors = []
    
    # Ensure we don't modify the original DataFrame passed to the cached function
    _farms_df = _farms_df_input.copy()

    if 'geojson_geometry' not in _farms_df.columns:
        errors.append("ستون 'geojson_geometry' برای محاسبه دقیق شاخص مزارع مورد نیاز است و یافت نشد.")
        return pd.DataFrame(results), errors

    total_farms = len(_farms_df)
    if total_farms == 0:
        return pd.DataFrame(results), errors
        
    progress_bar = st.progress(0)

    for i, (idx_row, farm_row) in enumerate(_farms_df.iterrows()):
        farm_name = farm_row['مزرعه']
        current_farm_ee_geometry = None

        try:
            geojson_str = farm_row['geojson_geometry']
            if pd.isna(geojson_str):
                raise ValueError("GeoJSON string is missing.")
            current_farm_ee_geometry = ee.Geometry(json.loads(geojson_str))
        except Exception as e:
            errors.append(f"خطا در پردازش هندسه برای {farm_name}: {e}. از نقطه مرکزی (در صورت وجود) استفاده می‌شود یا این مزرعه رد می‌شود.")
            # Try to use centroid if full geometry fails
            if 'طول جغرافیایی' in farm_row and 'عرض جغرافیایی' in farm_row and \
               pd.notna(farm_row['طول جغرافیایی']) and pd.notna(farm_row['عرض جغرافیایی']):
                current_farm_ee_geometry = ee.Geometry.Point([farm_row['طول جغرافیایی'], farm_row['عرض جغرافیایی']])
            else: # Skip this farm if no geometry at all
                results.append({'مزرعه': farm_name, f'{index_name_calc} (هفته جاری)': None, f'{index_name_calc} (هفته قبل)': None, 'تغییر': None,
                                'کانال': farm_row.get('کانال', 'N/A'), 'اداره': farm_row.get('اداره', 'N/A')})
                progress_bar.progress((i + 1) / total_farms)
                continue
        
        # Inner function to get mean value for a specific geometry and period
        def get_mean_value_for_geom(geometry_to_process, start_date_str, end_date_str):
            try:
                image, error_img = get_processed_image(geometry_to_process, start_date_str, end_date_str, index_name_calc)
                if image:
                    mean_dict = image.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=geometry_to_process,
                        scale=10, # 10m for Sentinel-2
                        maxPixels=1e9
                    ).getInfo()
                    return mean_dict.get(index_name_calc) if mean_dict else None, None
                else:
                    return None, error_img or f"No image for {farm_name} ({start_date_str}-{end_date_str})"
            except Exception as e_reduce:
                 return None, f"Error reducing region for {farm_name} ({start_date_str}-{end_date_str}): {e_reduce}"

        current_val, err_curr = get_mean_value_for_geom(current_farm_ee_geometry, start_curr, end_curr)
        if err_curr: errors.append(f"{farm_name} (هفته جاری): {err_curr}")

        previous_val, err_prev = get_mean_value_for_geom(current_farm_ee_geometry, start_prev, end_prev)
        if err_prev: errors.append(f"{farm_name} (هفته قبل): {err_prev}")

        change = None
        if current_val is not None and previous_val is not None:
            try: change = current_val - previous_val
            except TypeError: change = None

        results.append({
            'مزرعه': farm_name,
            'کانال': farm_row.get('کانال', 'N/A'),
            'اداره': farm_row.get('اداره', 'N/A'),
            f'{index_name_calc} (هفته جاری)': current_val,
            f'{index_name_calc} (هفته قبل)': previous_val,
            'تغییر': change
        })
        progress_bar.progress((i + 1) / total_farms)
    progress_bar.empty()
    return pd.DataFrame(results), errors

# Calculate and display the ranking table
ranking_df, calculation_errors = calculate_weekly_indices(
    filtered_farms_df, # Pass a copy to avoid modifying the original if calculate_weekly_indices did so
    selected_index,
    start_date_current_str,
    end_date_current_str,
    start_date_previous_str,
    end_date_previous_str
)

if calculation_errors:
    st.warning("⚠️ برخی خطاها در حین محاسبه شاخص‌ها برای جدول رتبه‌بندی رخ داد:")
    for error_idx, error_msg in enumerate(calculation_errors[:10]):
        st.caption(f" - {error_msg}")
    if len(calculation_errors) > 10:
        st.caption(f"... و {len(calculation_errors) - 10} خطای دیگر (برای جزئیات به کنسول مراجعه کنید).")


if not ranking_df.empty:
    ascending_sort = selected_index in ['MSI']
    ranking_df_sorted = ranking_df.sort_values(
        by=f'{selected_index} (هفته جاری)',
        ascending=ascending_sort,
        na_position='last'
    ).reset_index(drop=True)
    ranking_df_sorted.index = ranking_df_sorted.index + 1
    ranking_df_sorted.index.name = 'رتبه'

    def determine_status(row, index_name_status):
        change_val = row['تغییر']
        if pd.isna(change_val) or pd.isna(row[f'{index_name_status} (هفته جاری)']) or pd.isna(row[f'{index_name_status} (هفته قبل)']):
            return "بدون داده"
        threshold = 0.05 # General threshold, might need adjustment per index
        if index_name_status in ['NDVI', 'EVI', 'LAI', 'CVI']: # Higher is better
            if change_val > threshold: return "رشد مثبت"
            elif change_val < -threshold: return "تنش/کاهش"
            else: return "ثابت"
        elif index_name_status in ['MSI', 'NDMI']: # Lower is better (for MSI higher means more stress; NDMI higher means more moisture)
                                                   # For NDMI, higher change means more moisture = improvement.
                                                   # For MSI, higher change means more stress = deterioration.
            if index_name_status == 'NDMI': # Higher change is better
                 if change_val > threshold: return "بهبود رطوبت"
                 elif change_val < -threshold: return "کاهش رطوبت"
                 else: return "ثابت"
            elif index_name_status == 'MSI': # Lower change is better (less stress)
                 if change_val < -threshold: return "کاهش تنش (بهبود)" # e.g. MSI from 1.5 to 1.0 -> change = -0.5
                 elif change_val > threshold: return "افزایش تنش (بدتر شدن)"
                 else: return "ثابت"
        return "نامشخص"

    ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(lambda row: determine_status(row, selected_index), axis=1)
    
    cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
    for col_format in cols_to_format:
        if col_format in ranking_df_sorted.columns:
             ranking_df_sorted[col_format] = ranking_df_sorted[col_format].map(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")
    
    st.dataframe(ranking_df_sorted, use_container_width=True)
    
    # Summary metrics
    st.subheader("📊 خلاصه وضعیت مزارع")
    status_counts = ranking_df_sorted['وضعیت'].value_counts()
    col1, col2, col3, col4 = st.columns(4) # Added one more for flexibility

    positive_statuses = ["رشد مثبت", "بهبود رطوبت", "کاهش تنش (بهبود)"]
    negative_statuses = ["تنش/کाहش", "کاهش رطوبت", "افزایش تنش (بدتر شدن)"]
    
    positive_count = sum(status_counts.get(s, 0) for s in positive_statuses)
    negative_count = sum(status_counts.get(s, 0) for s in negative_statuses)
    neutral_count = status_counts.get("ثابت", 0)
    nodata_count = status_counts.get("بدون داده", 0)

    with col1: st.metric("🟢 بهبود یافته", positive_count)
    with col2: st.metric("⚪ ثابت", neutral_count)
    with col3: st.metric("🔴 بدتر شده", negative_count)
    with col4: st.metric("❓ بدون داده", nodata_count)
    
    st.info("""
    **توضیحات وضعیت:**
    - **بهبود یافته**: مزارعی که وضعیت آنها نسبت به هفته قبل بهتر شده (مثلاً NDVI بیشتر، MSI کمتر).
    - **ثابت**: مزارعی که تغییر قابل توجهی نداشته‌اند.
    - **بدتر شده**: مزارعی که وضعیت آنها نسبت به هفته قبل نامطلوب‌تر شده است.
    - **بدون داده**: مزارعی که امکان محاسبه تغییرات برای آنها وجود نداشته است.
    """)

    csv_data = ranking_df_sorted.to_csv(index=True).encode('utf-8-sig') # utf-8-sig for Excel compatibility with Persian
    st.download_button(
        label="📥 دانلود جدول رتبه‌بندی (CSV)",
        data=csv_data,
        file_name=f'ranking_{selected_index}_{selected_day.replace(" ", "_")}_{end_date_current_str}.csv',
        mime='text/csv',
    )
else:
    st.info(f"داده‌ای برای جدول رتبه‌بندی بر اساس {selected_index} در این بازه زمانی یافت نشد یا خطایی در محاسبه رخ داده است.")

st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با استفاده از Streamlit, Google Earth Engine, و geemap")
st.sidebar.markdown(f"<p style='text-align: right;'>نسخه 1.1.0</p>", unsafe_allow_html=True)