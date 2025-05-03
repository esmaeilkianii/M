# --- START OF FILE app (70)_fixed.py ---

import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
import json
import datetime
import plotly.express as px
import plotly.graph_objects as go
import os
import traceback
from streamlit_folium import st_folium
import google.generativeai as genai # Gemini API
import time # برای شبیه سازی تاخیر و نمایش بهتر اسپینر (اختیاری)

# --- Custom CSS ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide"
)

# Modern CSS with dark mode and color palette
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
        @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');
        
        /* General Styles */
        html, body, .main, .stApp {
            font-family: 'Vazirmatn', sans-serif !important;
            background: linear-gradient(135deg, #f5f7fa 0%, #e0f2f7 100%); /* Lighter gradient */
            color: #333; /* Darker text for better contrast */
        }

        /* Header Styles */
        .main-header {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 0.5rem;
            padding-bottom: 10px;
            border-bottom: 2px solid #43cea2;
        }
        .main-header h1 {
            font-family: 'Vazirmatn', sans-serif;
            color: #185a9d; /* Dark Blue */
            margin: 0;
            font-weight: 700;
        }
         .main-header h4 {
            color: #43cea2; /* Teal */
            margin-top: 0;
            font-weight: 400;
        }
        .main-logo {
            width: 55px; /* Slightly larger logo */
            height: 55px;
            border-radius: 15px;
            margin-left: 12px;
            vertical-align: middle;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }

        /* Sidebar Styles */
        .stSidebar {
             background: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%);
             border-right: 1px solid #e0e0e0;
        }
        .sidebar-logo {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 1.5rem;
            padding-top: 1rem; /* Add padding */
        }
        .sidebar-logo img {
            width: 100px; /* Larger sidebar logo */
            height: 100px;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(30,60,114,0.15);
        }
        .stSidebar .stSelectbox label, .stSidebar .stSlider label, .stSidebar h3 {
             color: #185a9d !important; /* Consistent label color */
             font-weight: 700;
        }

        /* Modern card style */
        .modern-card {
            /* background: linear-gradient(135deg, #43cea2 0%, #185a9d 100%); */
            background: #ffffff; /* White background */
            color: #333; /* Dark text */
            border-radius: 15px; /* Softer edges */
            padding: 20px 15px; /* Adjust padding */
            margin: 10px 0;
            box-shadow: 0 5px 15px rgba(0, 83, 156, 0.08); /* Softer shadow */
            text-align: center;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border: 1px solid #e8e8e8;
        }
        .modern-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0, 83, 156, 0.12);
        }
        .modern-card h5 { /* Label */
             color: #555;
             font-weight: 400;
             font-size: 1em;
             margin-bottom: 8px;
        }
         .modern-card h3 { /* Value */
             color: #185a9d;
             margin: 0;
             font-weight: 700;
             font-size: 1.6em;
        }
         .modern-card i { /* Icon */
            font-size: 1.8em;
            margin-bottom: 12px;
            color: #43cea2; /* Teal icon color */
         }


        /* Status Badges */
        .status-badge {
            padding: 5px 12px; /* Slightly larger padding */
            border-radius: 15px; /* Pill shape */
            font-weight: bold;
            font-size: 0.85em;
            white-space: nowrap;
            border: none; /* Remove border */
            display: inline-block; /* Ensure proper spacing */
            text-align: center;
        }
        .status-positive { background-color: #e0f2f7; color: #0d6efd; } /* Light Blue / Blue */
        .status-negative { background-color: #fdeaea; color: #dc3545; } /* Light Red / Red */
        .status-neutral { background-color: #fff8e1; color: #ffc107; } /* Light Yellow / Yellow */
        .status-nodata { background-color: #f8f9fa; color: #6c757d; } /* Light Gray / Gray */
        .status-unknown { background-color: #f0f0f0; color: #555; }
        .status-new { background-color: #e6f7ff; color: #17a2b8; } /* Light Cyan / Cyan */
        .status-removed { background-color: #f2f2f2; color: #6c757d; } /* Lighter Gray */

        /* Plotly Chart Background */
        .plotly-chart {
             background-color: transparent !important;
        }

        /* Dataframe styling */
        .dataframe { width: 100% !important; }
        th { background-color: #e0f2f7 !important; color: #185a9d !important; font-weight: bold; text-align: right !important; }
        td { text-align: right !important; vertical-align: middle !important; }


        /* Dark mode support */
        @media (prefers-color-scheme: dark) {
            html, body, .main, .stApp {
                background: linear-gradient(135deg, #232526 0%, #414345 100%);
                color: #f8fafc;
            }
            .stSidebar {
                 background: linear-gradient(180deg, #2a2d2f 0%, #232526 100%);
                 border-right: 1px solid #3a3d40;
            }
            .stSidebar .stSelectbox label, .stSidebar .stSlider label, .stSidebar h3 {
                 color: #a0d8ef !important; /* Lighter blue for dark mode */
            }
            .main-header h1 { color: #a0d8ef; }
            .main-header h4 { color: #66d9b8; } /* Lighter teal */
            .main-header { border-bottom-color: #66d9b8; }

            .modern-card {
                 background: #2a2d2f; /* Dark card background */
                 color: #f1f1f1;
                 border: 1px solid #3a3d40;
                 box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            }
             .modern-card:hover { box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3); }
             .modern-card h5 { color: #bbb; }
             .modern-card h3 { color: #a0d8ef; }
             .modern-card i { color: #66d9b8; }

             th { background-color: #3a3d40 !important; color: #a0d8ef !important; }

           .status-positive { background-color: #1a3a5c; color: #a0d8ef; }
           .status-negative { background-color: #5c1a2e; color: #f5c6cb; }
           .status-neutral { background-color: #664d03; color: #ffeeba; }
           .status-nodata { background-color: #383d41; color: #d6d8db; }
           .status-unknown { background-color: #444; color: #ccc; }
           .status-new { background-color: #1a505e; color: #adecf9; }
           .status-removed { background-color: #454545; color: #b0b0b0; }
        }
    </style>
""", unsafe_allow_html=True)

# --- Sidebar Logo ---
logo_path = 'MonitoringSugarcane-13/logo (1).png'
if os.path.exists(logo_path):
    st.sidebar.markdown(
        f"""
        <div class='sidebar-logo'>
            <img src='{logo_path}' alt='لوگو سامانه' />
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.sidebar.warning("لوگو یافت نشد (مسیر مورد انتظار: MonitoringSugarcane-13/logo (1).png)")

# --- Main Header ---
st.markdown("<div class='main-header'>", unsafe_allow_html=True) # Start header div
if os.path.exists(logo_path):
    st.markdown(f"<img src='{logo_path}' class='main-logo' alt='لوگو' />", unsafe_allow_html=True)
else:
    st.markdown("<span class='main-logo' style='font-size: 40px; line-height: 55px;'>🌾</span>", unsafe_allow_html=True) # Fallback icon

st.markdown(
    f"""
    <div>
        <h1>سامانه پایش هوشمند نیشکر</h1>
        <h4>مطالعات کاربردی شرکت کشت و صنعت دهخدا</h4>
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown("</div>", unsafe_allow_html=True) # End header div

# --- Configuration ---
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 11 # Start slightly more zoomed out

# --- File Paths (Relative to the script location in Hugging Face) ---
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'
FARM_GEOJSON_PATH = 'farm_geodata_fixed.geojson'

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

# --- Load Farm Data from GeoJSON ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data_from_geojson(geojson_path):
    """Loads farm data from the specified GeoJSON file."""
    if not os.path.exists(geojson_path):
        st.error(f"❌ فایل '{geojson_path}' یافت نشد. لطفاً فایل GeoJSON داده‌های مزارع را در مسیر صحیح قرار دهید.")
        st.stop()
    try:
        with open(geojson_path, 'r', encoding='utf-8') as f:
            gj = json.load(f)
        features = gj['features']
        records = []
        for feat in features:
            props = feat['properties']
            geom = feat.get('geometry') # Use .get for safer access
            centroid_lon, centroid_lat = None, None

            if geom and geom['type'] == 'Polygon' and geom.get('coordinates'):
                coords = geom['coordinates'][0]  # Outer ring
                lons = [pt[0] for pt in coords if isinstance(pt, (list, tuple)) and len(pt) >= 1 and isinstance(pt[0], (int, float))]
                lats = [pt[1] for pt in coords if isinstance(pt, (list, tuple)) and len(pt) >= 2 and isinstance(pt[1], (int, float))]
                if lons and lats:
                    centroid_lon = sum(lons) / len(lons)
                    centroid_lat = sum(lats) / len(lats)
            elif geom and geom['type'] == 'Point' and geom.get('coordinates'):
                 coords = geom['coordinates']
                 if isinstance(coords, (list, tuple)) and len(coords) == 2 and all(isinstance(c, (int, float)) for c in coords):
                     centroid_lon, centroid_lat = coords

            record = {
                **props,
                'geometry_type': geom.get('type') if geom else None,
                'coordinates': geom.get('coordinates') if geom else None,
                'centroid_lon': centroid_lon,
                'centroid_lat': centroid_lat
            }
            records.append(record)

        df = pd.DataFrame(records)
        required_cols = ['مزرعه', 'centroid_lon', 'centroid_lat', 'روز', 'گروه']
        if not all(col in df.columns for col in required_cols):
            missing = [col for col in required_cols if col not in df.columns]
            st.error(f"❌ فایل GeoJSON باید شامل ستون‌های ضروری باشد. ستون‌های یافت‌نشده: {', '.join(missing)}")
            st.stop()

        initial_count = len(df)
        df = df.dropna(subset=['centroid_lon', 'centroid_lat', 'روز', 'مزرعه']) # Add مزرعه to dropna
        dropped_count = initial_count - len(df)
        if dropped_count > 0:
            st.warning(f"⚠️ {dropped_count} رکورد به دلیل مقادیر نامعتبر یا خالی در مختصات، روز یا نام مزرعه حذف شدند.")
        if df.empty:
            st.error("⚠️ داده معتبری برای مزارع یافت نشد (پس از حذف رکوردهای نامعتبر). برنامه متوقف می‌شود.")
            st.stop()

        df['روز'] = df['روز'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
        df['گروه'] = df['گروه'].astype(str).str.strip()
        if 'مساحت' in df.columns:
            df['مساحت'] = pd.to_numeric(df['مساحت'], errors='coerce')
        # Ensure unique farm names per day - handle potential duplicates if needed
        # df = df.drop_duplicates(subset=['روز', 'مزرعه'], keep='first')

        st.success(f"✅ داده‌های {len(df)} مزرعه با موفقیت از GeoJSON بارگذاری شد.")
        return df
    except json.JSONDecodeError as e:
        st.error(f"❌ خطا در خواندن فایل GeoJSON (احتمالاً فرمت نامعتبر): {e}")
        st.stop()
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری یا پردازش فایل GeoJSON: {e}")
        st.error(traceback.format_exc())
        st.stop()


# --- HTML Helper Functions ---
def modern_metric_card(label, value, icon="fa-info-circle", color="#43cea2"):
    """Generates HTML for a modern metric card."""
    # Use the primary color for the icon if no specific color is given
    icon_color = color if color != "#43cea2" else "#43cea2" # Default to teal
    value_display = value if value is not None else "N/A"
    return f"""
    <div class="modern-card">
        <i class="fas {icon}" style="color: {icon_color};"></i>
        <h5>{label}</h5>
        <h3>{value_display}</h3>
    </div>
    """

def status_badge(status_text):
    """Generates an HTML badge based on status text."""
    status_text_lower = str(status_text).lower() # Ensure string conversion
    css_class = "status-unknown" # Default
    if pd.isna(status_text) or "بدون داده" in status_text_lower or "n/a" in status_text_lower:
         css_class = "status-nodata"
    elif "بهبود" in status_text_lower or "مثبت" in status_text_lower:
        css_class = "status-positive"
    elif "تنش" in status_text_lower or "کاهش" in status_text_lower or "بدتر" in status_text_lower:
        css_class = "status-negative"
    elif "ثابت" in status_text_lower:
        css_class = "status-neutral"
    elif "جدید" in status_text_lower:
        css_class = "status-new"
    elif "حذف" in status_text_lower: # Catch "حذف شده؟"
        css_class = "status-removed"
    elif "خطا" in status_text_lower:
        css_class = "status-negative" # Treat error as negative

    return f'<span class="status-badge {css_class}">{status_text}</span>'


# --- Initialize GEE and Load Data ---
if initialize_gee():
    farm_data_df = load_farm_data_from_geojson(FARM_GEOJSON_PATH)
else:
    # Stop execution if GEE fails
    st.error("اتصال به Google Earth Engine ناموفق بود. برنامه نمی‌تواند ادامه دهد.")
    st.stop()

# Check if farm data loaded successfully before proceeding
if 'farm_data_df' not in locals() or farm_data_df.empty:
    st.error("بارگذاری داده‌های مزارع ناموفق بود یا داده‌ای یافت نشد. برنامه متوقف می‌شود.")
    st.stop()


# ==============================================================================
# Sidebar Filters
# ==============================================================================
st.sidebar.header("تنظیمات نمایش")

# --- Day of the Week Selection ---
available_days = sorted(farm_data_df['روز'].unique())
selected_day = st.sidebar.selectbox(
    "📅 روز هفته:",
    options=available_days,
    index=0,
    help="داده‌های مزارع بر اساس این روز فیلتر می‌شوند."
)

# --- Filter Data Based on Selected Day ---
filtered_farms_df = farm_data_df[farm_data_df['روز'] == selected_day].copy()

if filtered_farms_df.empty:
    st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
    st.stop() # Stop if no farms for the selected day

# --- Farm Selection ---
available_farms = sorted(filtered_farms_df['مزرعه'].unique())
farm_options = ["همه مزارع"] + available_farms
selected_farm_name = st.sidebar.selectbox(
    "🌾 مزرعه:",
    options=farm_options,
    index=0,
    help="مزرعه‌ای که می‌خواهید جزئیات آن را ببینید یا 'همه مزارع' برای نمایش کلی."
)

# --- Index Selection ---
index_options = {
    "NDVI": "پوشش گیاهی (NDVI)",
    "NDMI": "رطوبت گیاه (NDMI)",
    "EVI": "پوشش گیاهی بهبودیافته (EVI)",
    "SAVI": "پوشش گیاهی با تعدیل خاک (SAVI)",
    "MSI": "تنش رطوبتی (MSI)",
    "LAI": "سطح برگ (LAI - تخمینی)",
    "CVI": "کلروفیل (CVI - تخمینی)",
}
selected_index = st.sidebar.selectbox(
    "📈 شاخص نقشه:",
    options=list(index_options.keys()),
    format_func=lambda x: f"{index_options[x]}", # Show descriptive name
    index=0 # Default to NDVI
)

# --- Date Range Calculation ---
# (Keep this logic as it determines the analysis periods)
today = datetime.date.today()
persian_to_weekday = {
    "شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1,
    "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4,
}
try:
    target_weekday = persian_to_weekday[selected_day]
    days_ago = (today.weekday() - target_weekday + 7) % 7
    end_date_current = today if days_ago == 0 else today - datetime.timedelta(days=days_ago)
    start_date_current = end_date_current - datetime.timedelta(days=6)
    end_date_previous = start_date_current - datetime.timedelta(days=1)
    start_date_previous = end_date_previous - datetime.timedelta(days=6)

    start_date_current_str = start_date_current.strftime('%Y-%m-%d')
    end_date_current_str = end_date_current.strftime('%Y-%m-%d')
    start_date_previous_str = start_date_previous.strftime('%Y-%m-%d')
    end_date_previous_str = end_date_previous.strftime('%Y-%m-%d')

    st.sidebar.markdown("---")
    st.sidebar.write(f"**بازه فعلی:**")
    st.sidebar.caption(f"{start_date_current_str} تا {end_date_current_str}")
    st.sidebar.write(f"**بازه قبلی:**")
    st.sidebar.caption(f"{start_date_previous_str} تا {end_date_previous_str}")
    st.sidebar.markdown("---")


except KeyError:
    st.sidebar.error(f"نام روز هفته '{selected_day}' قابل شناسایی نیست.")
    st.stop()
except Exception as e:
    st.sidebar.error(f"خطا در محاسبه بازه زمانی: {e}")
    st.stop()

# ==============================================================================
# Google Earth Engine Functions
# (Cloud Masking, Index Calculation - Keep as before)
# ==============================================================================

def maskS2clouds(image):
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    clear_mask_qa = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
    scl = image.select('SCL')
    good_quality_scl = scl.remap([4, 5, 6, 11], [1, 1, 1, 1], 0)
    combined_mask = clear_mask_qa.And(good_quality_scl)
    opticalBands = image.select('B.*').multiply(0.0001)
    return image.addBands(opticalBands, None, True).updateMask(combined_mask)

def add_indices(image):
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    evi = image.expression('2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)',
                           {'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2')}).rename('EVI')
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    savi = image.expression('((NIR - RED) / (NIR + RED + L)) * (1 + L)',
                            {'NIR': image.select('B8'), 'RED': image.select('B4'), 'L': 0.5}).rename('SAVI')
    msi = image.expression('SWIR1 / (NIR + 0.0001)', {'SWIR1': image.select('B11'), 'NIR': image.select('B8')}).rename('MSI')
    lai = ndvi.multiply(3.5).max(0).rename('LAI')
    green_safe = image.select('B3').max(ee.Image(0.0001))
    cvi = image.expression('(NIR / GREEN_SAFE) * (RED / GREEN_SAFE)',
                           {'NIR': image.select('B8'), 'GREEN_SAFE': green_safe, 'RED': image.select('B4')}).rename('CVI')
    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi, savi])

@st.cache_data(show_spinner="در حال پردازش تصویر ماهواره‌ای...", persist=True)
def get_processed_image(_geometry, start_date, end_date, index_name):
    """Gets median composite image for the period and selects the index."""
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds))
        count = s2_sr_col.size().getInfo()
        if count == 0:
            return None, f"هیچ تصویر بدون ابر در بازه {start_date} تا {end_date} یافت نشد."
        indexed_col = s2_sr_col.map(add_indices)
        median_image = indexed_col.median()
        output_image = median_image.select(index_name)
        # Check if the selected band exists and has valid data after median calculation
        band_info = output_image.bandNames().getInfo()
        if not band_info or index_name not in band_info:
             return None, f"باند '{index_name}' پس از پردازش یافت نشد (احتمالا داده کافی وجود نداشت)."
        # Optional: Add a check for image validity here if needed
        # test_reduction = output_image.reduceRegion(ee.Reducer.mean(), _geometry.centroid(1), 10).getInfo()
        # if not test_reduction or test_reduction.get(index_name) is None:
        #      return None, f"تصویر محاسبه شده برای '{index_name}' فاقد داده معتبر در منطقه است."

        return output_image, None
    except ee.EEException as e:
        error_details = e.args[0] if e.args else str(e)
        error_message = f"خطای GEE ({start_date}-{end_date}): {error_details}"
        return None, error_message
    except Exception as e:
        return None, f"خطای ناشناخته GEE ({start_date}-{end_date}): {e}\n{traceback.format_exc()}"

@st.cache_data(show_spinner="در حال دریافت سری زمانی...", persist=True)
def get_index_time_series(_point_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    """Gets time series data for a point."""
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)
                     .map(add_indices)
                     .select(index_name))

        def extract_value(image):
            value = image.reduceRegion(
                reducer=ee.Reducer.firstNonNull(), geometry=_point_geom, scale=10
            ).get(index_name)
            return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value}).set('hasValue', value)

        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.neq('hasValue', None))
        ts_info = ts_features.getInfo()['features']

        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), f"داده‌ای برای سری زمانی {index_name} در بازه {start_date}-{end_date} یافت نشد."

        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_info]
        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df = ts_df.groupby('date').mean().reset_index().sort_values('date').set_index('date')
        return ts_df, None
    except ee.EEException as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای GEE سری زمانی: {e.args[0] if e.args else str(e)}"
    except Exception as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای ناشناخته سری زمانی: {e}\n{traceback.format_exc()}"

@st.cache_data(show_spinner="در حال محاسبه شاخص‌های نیازسنجی...", persist=True)
def get_farm_needs_data(_point_geom, start_curr, end_curr, start_prev, end_prev):
    """Calculates mean indices (NDVI, NDMI, EVI, SAVI) for two periods."""
    results = {f'{idx}_{p}': None for idx in ['NDVI', 'NDMI', 'EVI', 'SAVI'] for p in ['curr', 'prev']}
    results['error'] = None
    indices_to_get = ['NDVI', 'NDMI', 'EVI', 'SAVI']

    def get_mean_values_for_period(start, end):
        period_values = {index: None for index in indices_to_get}
        try:
            s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                         .filterBounds(_point_geom).filterDate(start, end)
                         .map(maskS2clouds).map(add_indices))
            count = s2_sr_col.size().getInfo()
            if count == 0: return period_values, f"No images found ({start}-{end})"

            median_image = s2_sr_col.median().select(indices_to_get)
            mean_dict = median_image.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=_point_geom, scale=10, maxPixels=1e9
            ).getInfo()

            if mean_dict:
                for index in indices_to_get:
                    period_values[index] = mean_dict.get(index)
            return period_values, None
        except ee.EEException as e:
            return period_values, f"GEE Error ({start}-{end}): {e.args[0] if e.args else str(e)}"
        except Exception as e:
            return period_values, f"Unknown Error ({start}-{end}): {e}"

    curr_values, err_curr = get_mean_values_for_period(start_curr, end_curr)
    if err_curr: results['error'] = err_curr
    for idx in indices_to_get: results[f'{idx}_curr'] = curr_values.get(idx)

    prev_values, err_prev = get_mean_values_for_period(start_prev, end_prev)
    if err_prev:
        current_error = results.get('error')
        results['error'] = f"{current_error} | {err_prev}" if current_error else err_prev
    for idx in indices_to_get: results[f'{idx}_prev'] = prev_values.get(idx)

    return results

# ==============================================================================
# Gemini AI Helper Functions
# ==============================================================================
@st.cache_resource
def configure_gemini():
    """Configures the Gemini API client."""
    try:
        # --- Strongly recommend using Streamlit secrets ---
        # api_key = st.secrets.get("GEMINI_API_KEY")
        # if not api_key:
        #      st.error("❌ کلید API جمینای (GEMINI_API_KEY) در secrets.toml یافت نشد یا خالی است.")
        #      return None

        # --- Using Hardcoded Key (Less Secure - For Demo Only) ---
        api_key = "AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ" # <-- جایگزین شود یا از secrets استفاده کنید
        if not api_key:
            st.error("❌ کلید API جمینای به صورت مستقیم در کد وارد نشده یا خالی است.")
            return None
        # ---------------------------------------------------------

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
    if _model is None: return "سرویس هوش مصنوعی در دسترس نیست."

    def format_value(val): return f"{val:.3f}" if val is not None else "N/A"

    data_str = f"NDVI: {format_value(index_data.get('NDVI_curr'))} (قبل: {format_value(index_data.get('NDVI_prev'))})\n"
    data_str += f"NDMI: {format_value(index_data.get('NDMI_curr'))} (قبل: {format_value(index_data.get('NDMI_prev'))})\n"
    data_str += f"EVI: {format_value(index_data.get('EVI_curr'))} (قبل: {format_value(index_data.get('EVI_prev'))})\n"
    data_str += f"SAVI: {format_value(index_data.get('SAVI_curr'))} (قبل: {format_value(index_data.get('SAVI_prev'))})"

    prompt = f"""
    به عنوان یک متخصص کشاورزی نیشکر، وضعیت مزرعه '{farm_name}' را بر اساس داده‌های زیر و توصیه‌های اولیه، به طور خلاصه (3-5 جمله) و کاربردی به فارسی تحلیل کن. تمرکز اصلی بر نیاز احتمالی آبیاری و تغذیه باشد و توضیح دهید چرا این نیازها مطرح شده‌اند.

    داده‌های شاخص (مقدار فعلی و مقدار قبلی در پرانتز):
    {data_str}

    توصیه‌های اولیه:
    {', '.join(recommendations) if recommendations else 'موردی نیست.'}

    تحلیل شما:
    """
    try:
        response = _model.generate_content(prompt)
        return response.text if hasattr(response, 'text') else response.parts[0].text
    except Exception as e:
        st.warning(f"⚠️ خطا در ارتباط با Gemini API: {e}")
        return f"خطا در دریافت تحلیل: {str(e)}"

# ==============================================================================
# Main Application Layout (Tabs)
# ==============================================================================

# Configure Gemini Model at the start
gemini_model = configure_gemini()

# Define Tabs - Removed the analysis tab
tab1, tab2 = st.tabs(["📊 پایش مزارع", "💧 نیازسنجی کود و آبیاری"]) # Renamed second tab

with tab1:
    # ==============================================================================
    # Main Panel Display (Monitoring)
    # ==============================================================================
    st.subheader(f"🗓️ وضعیت مزارع در روز: {selected_day}")

    selected_farm_details = None
    selected_farm_geom = None
    map_center_lat = INITIAL_LAT
    map_center_lon = INITIAL_LON
    map_zoom = INITIAL_ZOOM

    # --- Setup Geometry and Initial Info ---
    if selected_farm_name == "همه مزارع":
        if not filtered_farms_df.empty:
            min_lon, min_lat = filtered_farms_df['centroid_lon'].min(), filtered_farms_df['centroid_lat'].min()
            max_lon, max_lat = filtered_farms_df['centroid_lon'].max(), filtered_farms_df['centroid_lat'].max()
            buffer = 0.001
            selected_farm_geom = ee.Geometry.Rectangle([min_lon - buffer, min_lat - buffer, max_lon + buffer, max_lat + buffer])
            map_center_lat = (min_lat + max_lat) / 2
            map_center_lon = (min_lon + max_lon) / 2
            map_zoom = 11
            st.info(f"نمایش کلی {len(filtered_farms_df)} مزرعه.")
        else:
             st.warning("داده‌ای برای نمایش 'همه مزارع' در این روز وجود ندارد.")
             selected_farm_geom = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT]) # Default point
    else:
        # Find the selected farm's details
        selection = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name]
        if not selection.empty:
            selected_farm_details = selection.iloc[0]
            lat = selected_farm_details['centroid_lat']
            lon = selected_farm_details['centroid_lon']
            selected_farm_geom = ee.Geometry.Point([lon, lat])
            map_center_lat = lat
            map_center_lon = lon
            map_zoom = 14 # Zoom closer for single farm

            st.write(f"**جزئیات مزرعه: {selected_farm_name}**")
            details_cols = st.columns([1, 1, 1, 1]) # 4 columns for details
            with details_cols[0]:
                area_val = selected_farm_details.get('مساحت')
                area_display = f"{area_val:,.1f}" if pd.notna(area_val) and isinstance(area_val, (int, float)) else "N/A"
                st.markdown(modern_metric_card("مساحت (ha)", area_display, icon="fa-vector-square"), unsafe_allow_html=True)
            with details_cols[1]:
                st.markdown(modern_metric_card("واریته", f"{selected_farm_details.get('واریته', 'N/A')}", icon="fa-seedling"), unsafe_allow_html=True)
            with details_cols[2]:
                st.markdown(modern_metric_card("گروه", f"{selected_farm_details.get('گروه', 'N/A')}", icon="fa-users"), unsafe_allow_html=True)
            with details_cols[3]:
                st.markdown(modern_metric_card("سن", f"{selected_farm_details.get('سن', 'N/A')}", icon="fa-hourglass-half"), unsafe_allow_html=True)
            # st.caption(f"مختصات: {lat:.5f}, {lon:.5f}") # Display coordinates subtly
        else:
             st.error(f"مزرعه '{selected_farm_name}' یافت نشد. لطفاً دوباره انتخاب کنید.")
             selected_farm_geom = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT]) # Default point

    # --- Variety Distribution Chart (only when 'All Farms' selected) ---
    if selected_farm_name == "همه مزارع" and not filtered_farms_df.empty:
        with st.expander("📊 مشاهده توزیع واریته‌ها", expanded=False):
            if 'واریته' in filtered_farms_df.columns:
                variety_counts = filtered_farms_df['واریته'].value_counts().sort_values(ascending=False)
                if not variety_counts.empty:
                    pie_df = pd.DataFrame({'واریته': variety_counts.index, 'تعداد': variety_counts.values})
                    fig_pie = px.pie(pie_df, names='واریته', values='تعداد',
                                     title="توزیع واریته در مزارع این روز", hole=0.4,
                                     color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_pie.update_traces(textposition='outside', textinfo='percent+label')
                    fig_pie.update_layout(showlegend=False, height=350, margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_pie, use_container_width=True)
                else: st.info("داده واریته برای مزارع این روز موجود نیست.")
            else: st.info("ستون 'واریته' در داده‌ها وجود ندارد.")

    # --- Map Display ---
    st.markdown("---")
    st.subheader(f"🗺️ نقشه وضعیت: {index_options[selected_index]}")

    vis_params = { # Using more standard color palettes
        'NDVI': {'min': 0.0, 'max': 0.9, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']},
        'EVI': {'min': 0.0, 'max': 0.9, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']},
        'NDMI': {'min': -0.5, 'max': 0.8, 'palette': ['#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#f7f7f7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac']},
        'SAVI': {'min': 0.0, 'max': 0.9, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']},
        'LAI': {'min': 0, 'max': 7, 'palette': ['#EFEFEF', '#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']},
        'MSI': {'min': 0, 'max': 3, 'palette': ['#2166ac', '#4393c3', '#92c5de', '#d1e5f0', '#f7f7f7', '#fddbc7', '#f4a582', '#d6604d', '#b2182b'][::-1]}, # Reversed: High MSI (dry) = red
        'CVI': {'min': 0, 'max': 25, 'palette': ['#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']},
    }

    m = geemap.Map(location=[map_center_lat, map_center_lon], zoom=map_zoom, add_google_map=True)
    m.add_basemap("HYBRID")

    gee_image_current, error_msg_current = None, None
    if selected_farm_geom:
        with st.spinner(f"در حال بارگیری تصویر {selected_index}..."):
            gee_image_current, error_msg_current = get_processed_image(
                selected_farm_geom, start_date_current_str, end_date_current_str, selected_index
            )

    map_layer_name = f"{selected_index} ({end_date_current_str})"
    if gee_image_current:
        current_vis = vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']})
        try:
            m.addLayer(gee_image_current, current_vis, map_layer_name)
            m.add_colorbar(current_vis, label=f"{index_options[selected_index]}", layer_name=map_layer_name)
        except Exception as map_err:
             st.error(f"خطا در افزودن لایه به نقشه: {map_err}")
    elif error_msg_current:
        st.warning(f"تصویر {selected_index} برای بازه فعلی یافت نشد: {error_msg_current}")
    else: # Geom might be invalid or other issue
        st.warning(f"امکان پردازش تصویر {selected_index} برای منطقه انتخابی وجود ندارد.")


    # Add Markers regardless of image layer
    marker_color = 'gray' if gee_image_current is None else 'blue' # Gray if no image data
    if selected_farm_name == "همه مزارع" and not filtered_farms_df.empty:
         for idx, farm in filtered_farms_df.iterrows():
             folium.Marker(
                 location=[farm['centroid_lat'], farm['centroid_lon']],
                 popup=(f"<b>مزرعه:</b> {farm['مزرعه']}<br>"
                        f"<b>گروه:</b> {farm.get('گروه', 'N/A')}<br>"
                        f"<b>واریته:</b> {farm.get('واریته', 'N/A')}"),
                 tooltip=f"مزرعه {farm['مزرعه']}",
                 icon=folium.Icon(color=marker_color, icon='info-sign')
             ).add_to(m)
         if selected_farm_geom: m.center_object(selected_farm_geom, zoom=map_zoom)
    elif selected_farm_details is not None:
         folium.Marker(
             location=[map_center_lat, map_center_lon],
             popup=(f"<b>مزرعه:</b> {selected_farm_name}<br>"
                    f"<b>گروه:</b> {selected_farm_details.get('گروه', 'N/A')}<br>"
                    f"<b>واریته:</b> {selected_farm_details.get('واریته', 'N/A')}<br>"
                    f"<b>سن:</b> {selected_farm_details.get('سن', 'N/A')}"),
             tooltip=f"مزرعه {selected_farm_name}",
             icon=folium.Icon(color='red', icon='star') # Highlight selected farm
         ).add_to(m)
         m.set_center(map_center_lon, map_center_lat, zoom=map_zoom)


    m.add_layer_control()
    try:
        st_folium(m, width=None, height=500, use_container_width=True)
        st.caption("از کنترل لایه‌ها (بالا سمت راست) برای تغییر نقشه پایه یا نمایش/عدم نمایش لایه شاخص استفاده کنید.")
    except Exception as display_err:
        st.error(f"خطا در نمایش نقشه: {display_err}")

    st.info("💡 برای ذخیره نقشه، از ابزار عکس گرفتن از صفحه (Screenshot) استفاده کنید.")

    # --- Time Series Chart ---
    st.markdown("---")
    st.subheader(f"📈 نمودار روند زمانی: {index_options[selected_index]}")

    if selected_farm_name == "همه مزارع":
        st.info("یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
    elif selected_farm_geom and selected_farm_details is not None:
        is_point = isinstance(selected_farm_geom, ee.geometry.Point)
        if is_point:
            timeseries_end_date = today.strftime('%Y-%m-%d')
            timeseries_start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d') # Last year

            ts_df, ts_error = get_index_time_series(
                selected_farm_geom, selected_index, start_date=timeseries_start_date, end_date=timeseries_end_date
            )

            if ts_error:
                st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
            elif not ts_df.empty:
                fig_ts = px.line(ts_df, x=ts_df.index, y=selected_index,
                                 title=f"روند {selected_index} - {selected_farm_name} (12 ماه اخیر)",
                                 labels={'date': 'تاریخ', selected_index: f'مقدار {selected_index}'})
                fig_ts.update_traces(mode='lines+markers', line=dict(color='#185a9d', width=2), marker=dict(color='#43cea2', size=5))
                fig_ts.update_layout(hovermode="x unified", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_title=f"{selected_index}", xaxis_title="تاریخ")
                st.plotly_chart(fig_ts, use_container_width=True)
            else:
                st.info(f"داده‌ای برای سری زمانی {selected_index} در 12 ماه گذشته یافت نشد.")
        else:
            st.warning("نمودار سری زمانی فقط برای مزارع منفرد (با هندسه نقطه‌ای) در دسترس است.")
    else:
        st.warning("جزئیات مزرعه برای نمایش نمودار سری زمانی در دسترس نیست.")

    # ==============================================================================
    # Helper Function for Status Determination
    # ==============================================================================
    def determine_status(row, index_name):
        current_col = f'{index_name} (هفته جاری)'
        prev_col = f'{index_name} (هفته قبل)'
        change_col = 'تغییر'

        if not all(col in row.index for col in [current_col, prev_col, change_col]): return "خطا در ستون"
        current_val = row[current_col]
        prev_val = row[prev_col]
        change_val = row[change_col]

        has_current = pd.notna(current_val) and isinstance(current_val, (int, float))
        has_prev = pd.notna(prev_val) and isinstance(prev_val, (int, float))
        has_change = pd.notna(change_val) and isinstance(change_val, (int, float))

        if not has_current and not has_prev: return "بدون داده"
        if has_current and not has_prev: return "جدید"
        if not has_current and has_prev: return "حذف شده؟"
        if not has_change: return "بدون تغییر معتبر" # Both values exist but change is NaN (unlikely here)

        # Use relative threshold for vegetation indices, absolute for others? Let's simplify: absolute
        absolute_threshold = 0.04 # Adjusted threshold

        higher_is_better = index_name in ['NDVI', 'EVI', 'LAI', 'CVI', 'NDMI', 'SAVI']
        lower_is_better = index_name in ['MSI']

        if higher_is_better:
            if change_val > absolute_threshold: return "رشد مثبت / بهبود"
            elif change_val < -absolute_threshold: return "تنش / کاهش"
            else: return "ثابت"
        elif lower_is_better:
            if change_val < -absolute_threshold: return "بهبود / کاهش تنش"
            elif change_val > absolute_threshold: return "تنش / بدتر شدن"
            else: return "ثابت"
        else: # Default (shouldn't happen with defined indices)
             if abs(change_val) > absolute_threshold: return f"تغییر یافته ({change_val:+.2f})"
             else: return "ثابت"


    # ==============================================================================
    # Ranking Table (Modified to use Spinner)
    # ==============================================================================
    st.markdown("---")
    st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {index_options[selected_index]}")
    st.markdown(f"مقایسه هفته جاری ({end_date_current_str}) با هفته قبل ({end_date_previous_str}).")

    # Note: Live progress bar removed from inside the function due to CacheReplayClosureError
    # Spinner will be shown automatically by Streamlit via show_spinner=True
    @st.cache_data(show_spinner=True, persist="disk") # Use Disk persistence if results are large/slow
    def calculate_weekly_indices(_farms_df_filtered, idx_name, s_curr, e_curr, s_prev, e_prev):
        """Calculates weekly indices for farms. No UI updates inside."""
        results = []
        errors = []
        total_farms = len(_farms_df_filtered)

        for i, (idx_row, farm) in enumerate(_farms_df_filtered.iterrows()):
            farm_name = farm['مزرعه']
            lat = farm['centroid_lat']
            lon = farm['centroid_lon']
            point_geom = ee.Geometry.Point([lon, lat])

            current_val, previous_val = None, None
            err_curr, err_prev = None, None

            def get_mean_value_robust(start, end):
                """Wrapper to get mean value robustly."""
                try:
                    image_period, error_img = get_processed_image(point_geom, start, end, idx_name)
                    if image_period:
                        mean_dict = image_period.reduceRegion(
                            reducer=ee.Reducer.mean(), geometry=point_geom, scale=10, maxPixels=1e9
                        ).getInfo()
                        val = mean_dict.get(idx_name) if mean_dict else None
                        return (val, None) if val is not None else (None, f"مقدار {idx_name} یافت نشد ({start}-{end})")
                    else:
                        return None, error_img
                except ee.EEException as e:
                     return None, f"خطای GEE reduceRegion ({start}-{end}): {e.args[0] if e.args else str(e)}"
                except Exception as e:
                     return None, f"خطای ناشناخته محاسبه مقدار ({start}-{end}): {e}"

            current_val, err_curr = get_mean_value_robust(s_curr, e_curr)
            if err_curr: errors.append(f"{farm_name} (جاری): {err_curr}")

            previous_val, err_prev = get_mean_value_robust(s_prev, e_prev)
            if err_prev: errors.append(f"{farm_name} (قبل): {err_prev}")

            change = None
            if current_val is not None and previous_val is not None:
                try:
                    if isinstance(current_val, (int, float)) and isinstance(previous_val, (int, float)):
                        change = current_val - previous_val
                except TypeError: pass # Ignore if types mismatch

            results.append({
                'مزرعه': farm_name,
                'گروه': farm.get('گروه', 'N/A'),
                f'{idx_name} (هفته جاری)': current_val,
                f'{idx_name} (هفته قبل)': previous_val,
                'تغییر': change
            })
            # No st.markdown or progress bar updates here!

        return pd.DataFrame(results), errors

    # Calculate and display the ranking table
    # Pass only necessary data to the cached function
    ranking_df, calculation_errors = calculate_weekly_indices(
        filtered_farms_df[['مزرعه', 'گروه', 'centroid_lat', 'centroid_lon']], # Pass only needed columns
        selected_index,
        start_date_current_str,
        end_date_current_str,
        start_date_previous_str,
        end_date_previous_str
    )

    # Display errors outside the cached function
    if calculation_errors:
        with st.expander("⚠️ مشاهده خطاهای محاسبه (کلیک کنید)", expanded=False):
            error_dict = {}
            for error_str in calculation_errors:
                try:
                    farm_name_err = error_str.split(" (")[0]
                    if farm_name_err not in error_dict: error_dict[farm_name_err] = []
                    error_dict[farm_name_err].append(error_str)
                except Exception:
                     if "Unknown" not in error_dict: error_dict["Unknown"] = []
                     error_dict["Unknown"].append(error_str)

            for farm_name_err, err_list in error_dict.items():
                 st.error(f"**مزرعه: {farm_name_err}**")
                 for err in err_list: st.caption(f"- {err}")

    if not ranking_df.empty:
        ascending_sort = selected_index in ['MSI'] # True if lower value is better
        ranking_df_sorted = ranking_df.sort_values(
            by=f'{selected_index} (هفته جاری)', ascending=ascending_sort, na_position='last'
        ).reset_index(drop=True)
        ranking_df_sorted.index = ranking_df_sorted.index + 1
        ranking_df_sorted.index.name = 'رتبه'

        # Determine status and format
        ranking_df_sorted['وضعیت_متن'] = ranking_df_sorted.apply(lambda row: determine_status(row, selected_index), axis=1)
        ranking_df_sorted['وضعیت'] = ranking_df_sorted['وضعیت_متن'].apply(status_badge)

        cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
        for col in cols_to_format:
            if col in ranking_df_sorted.columns:
                 ranking_df_sorted[col] = ranking_df_sorted[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) and isinstance(x, (int, float)) else ("N/A" if pd.isna(x) else x))

        display_columns_order = ['مزرعه', 'گروه', f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر', 'وضعیت']
        display_columns = [col for col in display_columns_order if col in ranking_df_sorted.columns]

        st.markdown("<style> td, th { text-align: right !important; } </style>", unsafe_allow_html=True)
        st.write(ranking_df_sorted[display_columns].to_html(escape=False, index=True, classes='dataframe table table-striped table-hover', justify='right'), unsafe_allow_html=True)

        # --- Summary Metrics ---
        st.subheader("📊 خلاصه وضعیت")
        status_counts_text = ranking_df_sorted['وضعیت_متن'].value_counts()
        positive_terms = ["رشد مثبت / بهبود", "بهبود / کاهش تنش", "جدید"]
        negative_terms = ["تنش / کاهش", "تنش / بدتر شدن", "حذف شده?", "خطا در ستون", "بدون تغییر معتبر"]
        neutral_terms = ["ثابت"]
        nodata_terms = ["بدون داده"]

        positive_count = sum(status_counts_text.get(term, 0) for term in positive_terms)
        negative_count = sum(status_counts_text.get(term, 0) for term in negative_terms)
        neutral_count = sum(status_counts_text.get(term, 0) for term in neutral_terms)
        nodata_count = sum(status_counts_text.get(term, 0) for term in nodata_terms)
        # unknown_count = len(ranking_df_sorted) - (positive_count + negative_count + neutral_count + nodata_count) # Include others in negative/error

        summary_cols = st.columns(4)
        summary_cols[0].metric("🟢 بهبود/جدید", positive_count)
        summary_cols[1].metric("🔴 تنش/خطا", negative_count)
        summary_cols[2].metric("⚪ ثابت", neutral_count)
        summary_cols[3].metric("⚫ بدون داده", nodata_count)

        with st.expander("راهنمای وضعیت‌ها", expanded=False):
             st.info("""
             - **🟢 بهبود/جدید**: بهبود قابل توجه نسبت به هفته قبل یا داده فقط برای هفته جاری موجود است.
             - **⚪ ثابت**: تغییر معناداری نسبت به هفته قبل نداشته‌ است.
             - **🔴 تنش/خطا**: وضعیت نامطلوب‌تر نسبت به هفته قبل، یا داده فقط برای هفته قبل موجود است، یا خطا در محاسبه.
             - **⚫ بدون داده**: داده کافی برای مقایسه در هر دو هفته وجود ندارد.
             """)

        # Download Button
        csv_df = ranking_df_sorted.drop(columns=['وضعیت']) # Drop HTML badge column
        csv_data = csv_df.to_csv(index=True, encoding='utf-8-sig')
        st.download_button(
            label="📥 دانلود جدول رتبه‌بندی (CSV)",
            data=csv_data,
            file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv',
            mime='text/csv',
        )
    else:
        st.info(f"داده‌ای برای جدول رتبه‌بندی ({selected_index}) یافت نشد یا محاسبه ناموفق بود.")


# --- Tab 2: Needs Analysis ---
with tab2:
    st.header("💧 تحلیل نیاز آبیاری و تغذیه")

    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری در تب 'پایش مزارع' انتخاب کنید تا تحلیل نیازهای آن نمایش داده شود.")
    # Need selected_farm_details to check if a valid single farm is selected
    elif selected_farm_details is not None and selected_farm_geom is not None:
        is_point = isinstance(selected_farm_geom, ee.geometry.Point)
        if not is_point:
            st.warning("تحلیل نیازها فقط برای مزارع منفرد (با هندسه نقطه‌ای) در دسترس است.")
        else:
            st.subheader(f"تحلیل برای مزرعه: {selected_farm_name}")

            # --- Thresholds ---
            st.markdown("**تنظیم آستانه‌های هشدار:**")
            thresh_cols = st.columns(2)
            with thresh_cols[0]:
                ndmi_threshold = st.slider("آستانه NDMI (کم آبی):", -0.2, 0.5, 0.25, 0.01, format="%.2f", key="ndmi_thresh",
                                         help="NDMI کمتر از این مقدار، نشان‌دهنده رطوبت پایین است.")
            with thresh_cols[1]:
                ndvi_drop_threshold = st.slider("آستانه افت NDVI (تغذیه/تنش):", 0.0, 20.0, 7.0, 0.5, format="%.1f%%", key="ndvi_thresh",
                                            help="افت NDVI بیش از این درصد نسبت به هفته قبل، نیاز به بررسی دارد.")

            # --- Get Data ---
            farm_needs_data = get_farm_needs_data(
                selected_farm_geom,
                start_date_current_str, end_date_current_str,
                start_date_previous_str, end_date_previous_str
            )

            if farm_needs_data['error']:
                st.error(f"خطا در دریافت داده‌های شاخص برای تحلیل نیازها:")
                st.error(farm_needs_data['error'])
            elif farm_needs_data['NDMI_curr'] is None or farm_needs_data['NDVI_curr'] is None:
                st.warning("داده‌های شاخص لازم (NDMI/NDVI) برای تحلیل در دوره فعلی یافت نشد (پوشش ابر؟).")
                # Display available data
                st.markdown("**مقادیر شاخص‌ها (در صورت وجود):**")
                idx_cols_partial = st.columns(4)
                def format_val(v): return f"{v:.3f}" if v is not None else "N/A"
                idx_cols_partial[0].metric("NDVI (جاری)", format_val(farm_needs_data.get('NDVI_curr')))
                idx_cols_partial[1].metric("NDMI (جاری)", format_val(farm_needs_data.get('NDMI_curr')))
                idx_cols_partial[2].metric("EVI (جاری)", format_val(farm_needs_data.get('EVI_curr')))
                idx_cols_partial[3].metric("SAVI (جاری)", format_val(farm_needs_data.get('SAVI_curr')))
            else:
                # --- Display Indices with Deltas ---
                st.markdown("**مقادیر شاخص‌ها (مقایسه هفتگی):**")
                idx_cols = st.columns(4)
                def calc_delta(curr, prev):
                    if curr is not None and prev is not None and isinstance(curr, (int, float)) and isinstance(prev, (int, float)):
                        return curr - prev
                    return None

                ndvi_delta = calc_delta(farm_needs_data.get('NDVI_curr'), farm_needs_data.get('NDVI_prev'))
                ndmi_delta = calc_delta(farm_needs_data.get('NDMI_curr'), farm_needs_data.get('NDMI_prev'))
                evi_delta = calc_delta(farm_needs_data.get('EVI_curr'), farm_needs_data.get('EVI_prev'))
                savi_delta = calc_delta(farm_needs_data.get('SAVI_curr'), farm_needs_data.get('SAVI_prev'))

                idx_cols[0].metric("NDVI", f"{farm_needs_data['NDVI_curr']:.3f}", f"{ndvi_delta:+.3f}" if ndvi_delta is not None else None)
                idx_cols[1].metric("NDMI", f"{farm_needs_data['NDMI_curr']:.3f}", f"{ndmi_delta:+.3f}" if ndmi_delta is not None else None)
                idx_cols[2].metric("EVI", f"{farm_needs_data.get('EVI_curr', 0):.3f}", f"{evi_delta:+.3f}" if evi_delta is not None else None) # Use 0 if None for display
                idx_cols[3].metric("SAVI", f"{farm_needs_data.get('SAVI_curr', 0):.3f}", f"{savi_delta:+.3f}" if savi_delta is not None else None)
                st.caption("مقدار جاری و تغییر نسبت به هفته قبل (دلتا).")

                # --- Generate Recommendations ---
                recommendations = []
                issues_found = False

                # 1. Irrigation Check
                if farm_needs_data['NDMI_curr'] < ndmi_threshold:
                    recommendations.append(f"💧 **نیاز احتمالی به آبیاری:** NDMI ({farm_needs_data['NDMI_curr']:.3f}) < آستانه ({ndmi_threshold:.2f}).")
                    issues_found = True

                # 2. Fertilization/Stress Check
                ndvi_prev = farm_needs_data.get('NDVI_prev')
                if ndvi_prev is not None and farm_needs_data['NDVI_curr'] < ndvi_prev:
                     try:
                         if abs(ndvi_prev) > 1e-6:
                             ndvi_change_percent = ((farm_needs_data['NDVI_curr'] - ndvi_prev) / abs(ndvi_prev)) * 100
                             if abs(ndvi_change_percent) > ndvi_drop_threshold:
                                 recommendations.append(f"⚠️ **نیاز به بررسی تغذیه/تنش:** افت NDVI ({ndvi_change_percent:.1f}%) مشاهده شد. بررسی میدانی توصیه می‌شود.")
                                 issues_found = True
                         elif farm_needs_data['NDVI_curr'] > 0.1:
                             recommendations.append(f"📈 **رشد NDVI:** NDVI از نزدیک صفر افزایش یافته.")
                     except Exception: pass # Ignore calculation errors

                # 3. Low Vegetation Check
                if farm_needs_data['NDVI_curr'] < 0.3 and not any("تغذیه/تنش" in rec for rec in recommendations):
                    recommendations.append(f"📉 **پوشش گیاهی ضعیف:** NDVI ({farm_needs_data['NDVI_curr']:.3f}) پایین است. بررسی وضعیت کلی مزرعه.")
                    issues_found = True

                # 4. Default Message
                if not issues_found and not recommendations:
                    recommendations.append("✅ **وضعیت مطلوب:** هشدار خاصی بر اساس شاخص‌های NDMI و روند NDVI شناسایی نشد.")

                st.markdown("**توصیه‌های اولیه:**")
                if recommendations:
                    for rec in recommendations:
                        if "آبیاری" in rec: st.error(rec)
                        elif "تغذیه/تنش" in rec or "ضعیف" in rec: st.warning(rec)
                        else: st.success(rec)
                else:
                    st.info("هیچ توصیه خاصی ایجاد نشد.")

                # --- AI Analysis ---
                st.markdown("---")
                st.markdown("**تحلیل هوش مصنوعی (Gemini):**")
                if gemini_model:
                    # Extract concise recommendations for the AI prompt
                    concise_recs = [r.split(':')[0].replace('*','').strip() for r in recommendations]
                    ai_explanation = get_ai_analysis(gemini_model, selected_farm_name, farm_needs_data, concise_recs)
                    st.markdown(f"> {ai_explanation}") # Use markdown blockquote
                else:
                    st.info("سرویس تحلیل هوش مصنوعی پیکربندی نشده است.")
    else:
        # This case handles when a specific farm name is selected but its details weren't found earlier
        st.warning("ابتدا یک مزرعه معتبر را از پنل کناری در تب 'پایش مزارع' انتخاب کنید.")


# --- Footer ---
st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با 💚 توسط [اسماعیل کیانی]")
# st.sidebar.markdown("[GitHub Repository](https://github.com/your_username/your_repo)") # Add your link