# --- START OF FILE app (70)_enhanced.py ---

import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
from folium.plugins import MarkerCluster # For clustering markers on classified maps
import json
import datetime
import plotly.express as px
import plotly.graph_objects as go
import os
import traceback
from streamlit_folium import st_folium
import google.generativeai as genai # Gemini API
import time # برای شبیه سازی تاخیر (اختیاری)
import random # For color generation
from collections import Counter # For counting statuses

# --- Custom CSS ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide"
)

# Modern CSS with enhanced styles
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
        @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');

        /* General Styles */
        html, body, .main, .stApp {
            font-family: 'Vazirmatn', sans-serif !important;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); /* Very light gray gradient */
            color: #212529; /* Bootstrap dark gray */
        }

        /* Header Styles */
        .main-header {
            display: flex;
            align-items: center;
            gap: 20px; /* Increased gap */
            margin-bottom: 1rem;
            padding-bottom: 15px;
            border-bottom: 3px solid #6f42c1; /* Bootstrap Purple */
        }
        .main-header h1 {
            color: #6f42c1; /* Bootstrap Purple */
            margin: 0;
            font-weight: 700;
            font-size: 2.2em; /* Slightly larger title */
        }
         .main-header h4 {
            color: #fd7e14; /* Bootstrap Orange */
            margin-top: 5px; /* Adjust spacing */
            font-weight: 500; /* Medium weight */
            font-size: 1.1em;
        }
        .main-logo {
            width: 60px;
            height: 60px;
            border-radius: 18px; /* Rounded square */
            margin-left: 12px;
            vertical-align: middle;
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
            border: 2px solid #ffffff; /* White border */
        }

        /* Sidebar Styles */
        .stSidebar {
             background: #ffffff; /* Clean white */
             border-right: 1px solid #dee2e6; /* Lighter border */
        }
        .sidebar-logo {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 1.5rem;
            padding-top: 1.5rem;
        }
        .sidebar-logo img {
            width: 110px;
            height: 110px;
            border-radius: 22px;
            box-shadow: 0 5px 18px rgba(111, 66, 193, 0.2); /* Purple shadow */
        }
        .stSidebar .stSelectbox label, .stSidebar .stSlider label, .stSidebar .stExpander label, .stSidebar h3 {
             color: #6f42c1 !important; /* Purple labels */
             font-weight: 700;
             font-size: 1.05em;
        }
        .stSidebar .stExpander { /* Style expanders */
             background-color: #f8f9fa;
             border-radius: 10px;
             border: 1px solid #e9ecef;
             margin-bottom: 10px;
        }

        /* Modern card style - Enhanced */
        .modern-card {
            background: #ffffff;
            color: #212529;
            border-radius: 16px;
            padding: 25px 20px;
            margin: 12px 0;
            box-shadow: 0 6px 20px rgba(111, 66, 193, 0.09); /* Subtle purple shadow */
            text-align: center;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border: 1px solid #f0f0f0;
            position: relative; /* For potential pseudo-elements */
            overflow: hidden; /* Hide overflow for effects */
        }
        /* Optional: Add a subtle top border color */
        .modern-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 5px; /* Height of the color bar */
            background: linear-gradient(90deg, #6f42c1, #fd7e14); /* Purple to Orange gradient */
            opacity: 0.8;
        }
        .modern-card:hover {
            transform: translateY(-6px) scale(1.01); /* Slightly more lift */
            box-shadow: 0 10px 30px rgba(111, 66, 193, 0.15);
        }
        .modern-card h5 { /* Label */
             color: #6c757d; /* Bootstrap gray */
             font-weight: 500;
             font-size: 0.95em;
             margin-bottom: 8px;
        }
         .modern-card h3 { /* Value */
             color: #6f42c1; /* Purple value */
             margin: 0;
             font-weight: 700;
             font-size: 1.8em; /* Larger value */
             line-height: 1.2;
         }
         .modern-card i { /* Icon */
            font-size: 2em; /* Larger icon */
            margin-bottom: 15px;
            color: #fd7e14; /* Orange icon color */
         }

        /* Status Badges - Enhanced */
        .status-badge {
            padding: 6px 15px;
            border-radius: 20px;
            font-weight: 700; /* Bolder */
            font-size: 0.8em; /* Smaller text */
            white-space: nowrap;
            border: none;
            display: inline-block;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1); /* Subtle shadow on badges */
            transition: transform 0.2s ease;
        }
        .status-badge:hover {
            transform: scale(1.05);
        }
        /* Using Bootstrap-like colors */
        .status-positive { background-color: #d1e7dd; color: #0f5132; } /* Light Green / Dark Green */
        .status-negative { background-color: #f8d7da; color: #842029; } /* Light Red / Dark Red */
        .status-neutral { background-color: #fff3cd; color: #664d03; } /* Light Yellow / Dark Yellow */
        .status-nodata { background-color: #e9ecef; color: #495057; } /* Light Gray / Dark Gray */
        .status-unknown { background-color: #f8f9fa; color: #6c757d; }
        .status-new { background-color: #cff4fc; color: #055160; } /* Light Cyan / Dark Cyan */
        .status-removed { background-color: #dee2e6; color: #495057; } /* Gray */

        /* Plotly Chart Background */
        .plotly-chart { background-color: transparent !important; }

        /* Dataframe styling */
        .dataframe { width: 100% !important; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border-radius: 8px; overflow: hidden;}
        th { background-color: #f8f9fa !important; color: #6f42c1 !important; font-weight: bold; text-align: right !important; border-bottom: 2px solid #dee2e6 !important;}
        td { text-align: right !important; vertical-align: middle !important; border-bottom: 1px solid #f1f1f1 !important;}
        tr:hover { background-color: #f1f3ff !important; } /* Light purple hover */

        /* Folium Map Popup Style */
        .folium-popup .leaflet-popup-content-wrapper {
             background-color: #ffffff;
             border-radius: 10px;
             box-shadow: 0 3px 8px rgba(0,0,0,0.15);
             border: 1px solid #e0e0e0;
         }
        .folium-popup .leaflet-popup-content {
             font-family: 'Vazirmatn', sans-serif !important;
             color: #333;
             font-size: 0.95em;
             line-height: 1.6;
         }
         .folium-popup .leaflet-popup-content b {
             color: #6f42c1; /* Purple for bold text */
         }


        /* Dark mode support - Needs careful color matching */
        @media (prefers-color-scheme: dark) {
            html, body, .main, .stApp {
                background: linear-gradient(135deg, #212529 0%, #343a40 100%); /* Darker gradient */
                color: #f8f9fa;
            }
            .stSidebar {
                 background: #212529; /* Dark background */
                 border-right: 1px solid #495057; /* Darker border */
            }
            .stSidebar .stSelectbox label, .stSidebar .stSlider label, .stSidebar .stExpander label, .stSidebar h3 {
                 color: #bf9dfc !important; /* Lighter Purple */
            }
            .stSidebar .stExpander {
                 background-color: #343a40;
                 border: 1px solid #495057;
            }

            .main-header { border-bottom-color: #bf9dfc; }
            .main-header h1 { color: #bf9dfc; }
            .main-header h4 { color: #ffab70; } /* Lighter Orange */
            .main-logo { border-color: #495057; box-shadow: 0 6px 12px rgba(255, 255, 255, 0.1); }


            .modern-card {
                 background: #343a40; /* Dark card background */
                 color: #f1f1f1;
                 border: 1px solid #495057;
                 box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
            }
             .modern-card:hover { box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35); }
             .modern-card::before { background: linear-gradient(90deg, #bf9dfc, #ffab70); } /* Lighter gradient */
             .modern-card h5 { color: #adb5bd; }
             .modern-card h3 { color: #bf9dfc; }
             .modern-card i { color: #ffab70; }

             th { background-color: #495057 !important; color: #bf9dfc !important; border-bottom-color: #6c757d !important;}
             td { border-bottom-color: #495057 !important;}
             tr:hover { background-color: #483d8b !important; } /* Dark Slate Blue hover */


           /* Dark mode badges */
           .status-positive { background-color: #0b2d1e; color: #75b798; box-shadow: 0 2px 5px rgba(255,255,255,0.1); }
           .status-negative { background-color: #3e1116; color: #f1aeb5; box-shadow: 0 2px 5px rgba(255,255,255,0.1); }
           .status-neutral { background-color: #332701; color: #ffda6a; box-shadow: 0 2px 5px rgba(255,255,255,0.1); }
           .status-nodata { background-color: #343a40; color: #adb5bd; box-shadow: 0 2px 5px rgba(255,255,255,0.1); }
           .status-new { background-color: #022a33; color: #6edff6; box-shadow: 0 2px 5px rgba(255,255,255,0.1); }
           .status-removed { background-color: #495057; color: #adb5bd; box-shadow: 0 2px 5px rgba(255,255,255,0.1); }

            /* Dark mode popup */
            .folium-popup .leaflet-popup-content-wrapper {
                 background-color: #343a40;
                 border: 1px solid #495057;
                 box-shadow: 0 3px 8px rgba(0,0,0,0.3);
            }
            .folium-popup .leaflet-popup-content { color: #f8f9fa; }
            .folium-popup .leaflet-popup-content b { color: #bf9dfc; } /* Lighter Purple */

        }
    </style>
""", unsafe_allow_html=True)

# --- Sidebar Logo ---
logo_path = 'MonitoringSugarcane-13/logo (1).png'
if os.path.exists(logo_path):
    st.sidebar.markdown(f"<div class='sidebar-logo'><img src='{logo_path}' alt='لوگو سامانه' /></div>", unsafe_allow_html=True)
else:
    st.sidebar.warning("لوگو یافت نشد.")

# --- Main Header ---
st.markdown("<div class='main-header'>", unsafe_allow_html=True)
if os.path.exists(logo_path):
    st.markdown(f"<img src='{logo_path}' class='main-logo' alt='لوگو' />", unsafe_allow_html=True)
else:
    st.markdown("<span class='main-logo' style='font-size: 40px; line-height: 60px; text-align: center; background: #eee; display: inline-block;'>🌾</span>", unsafe_allow_html=True)
st.markdown(
    f"""
    <div>
        <h1>سامانه پایش هوشمند نیشکر</h1>
        <h4>مطالعات کاربردی شرکت کشت و صنعت دهخدا</h4>
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown("</div>", unsafe_allow_html=True)

# --- Configuration ---
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 11

# --- File Paths ---
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'
FARM_GEOJSON_PATH = 'farm_geodata_fixed.geojson' # Assumed to contain 'اداره' now

# --- GEE Authentication ---
@st.cache_resource
def initialize_gee():
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"خطا: فایل Service Account در مسیر '{SERVICE_ACCOUNT_FILE}' یافت نشد.")
            st.stop()
        credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Initialized Successfully.")
        return True
    except Exception as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.stop()

# --- Load Farm Data ---
@st.cache_data(show_spinner="بارگذاری داده‌های مزارع...")
def load_farm_data_from_geojson(geojson_path):
    if not os.path.exists(geojson_path):
        st.error(f"❌ فایل '{geojson_path}' یافت نشد.")
        st.stop()
    try:
        with open(geojson_path, 'r', encoding='utf-8') as f:
            gj = json.load(f)
        features = gj['features']
        records = []
        required_props = ['مزرعه', 'روز', 'گروه', 'اداره'] # Added 'اداره'
        has_warned_missing_props = False

        for feat in features:
            props = feat.get('properties', {})
            geom = feat.get('geometry')
            centroid_lon, centroid_lat = None, None

            # Check for essential properties
            missing_props = [p for p in required_props if p not in props or props[p] is None]
            if missing_props:
                 if not has_warned_missing_props:
                      st.warning(f"برخی مزارع فاقد ویژگی‌های ضروری ({', '.join(missing_props)}) هستند و نادیده گرفته می‌شوند.", icon="⚠️")
                      has_warned_missing_props = True
                 continue # Skip this feature

            if geom and geom['type'] == 'Polygon' and geom.get('coordinates'):
                coords = geom['coordinates'][0]
                lons = [pt[0] for pt in coords if isinstance(pt, (list, tuple)) and len(pt) >= 1 and isinstance(pt[0], (int, float))]
                lats = [pt[1] for pt in coords if isinstance(pt, (list, tuple)) and len(pt) >= 2 and isinstance(pt[1], (int, float))]
                if lons and lats:
                    centroid_lon = sum(lons) / len(lons)
                    centroid_lat = sum(lats) / len(lats)
            elif geom and geom['type'] == 'Point' and geom.get('coordinates'):
                 coords = geom['coordinates']
                 if isinstance(coords, (list, tuple)) and len(coords) == 2 and all(isinstance(c, (int, float)) for c in coords):
                     centroid_lon, centroid_lat = coords

            # Only add if centroid is valid
            if centroid_lon is not None and centroid_lat is not None:
                record = {
                    **props, # Includes 'مزرعه', 'روز', 'گروه', 'اداره', 'واریته', 'سن', 'مساحت' etc.
                    'geometry_type': geom.get('type'),
                    'coordinates': geom.get('coordinates'),
                    'centroid_lon': centroid_lon,
                    'centroid_lat': centroid_lat
                }
                records.append(record)
            elif not has_warned_missing_props: # Warn only once if geometry/centroid fails
                 st.warning(f"مزرعه '{props.get('مزرعه', 'ناشناس')}' فاقد مختصات معتبر است و نادیده گرفته شد.", icon="🗺️")
                 has_warned_missing_props = True


        df = pd.DataFrame(records)
        if df.empty:
            st.error("⚠️ داده معتبری برای مزارع یافت نشد. برنامه متوقف می‌شود.")
            st.stop()

        # Basic Cleaning
        df['روز'] = df['روز'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
        df['گروه'] = df['گروه'].astype(str).str.strip()
        df['اداره'] = df['اداره'].astype(str).str.strip() # Clean 'اداره'
        if 'مساحت' in df.columns:
            df['مساحت'] = pd.to_numeric(df['مساحت'], errors='coerce')
        if 'سن' in df.columns:
             df['سن'] = pd.to_numeric(df['سن'], errors='coerce').fillna(0).astype(int) # Handle non-numeric age


        st.success(f"✅ داده‌های {len(df)} مزرعه با موفقیت بارگذاری شد.")
        return df
    except json.JSONDecodeError as e:
        st.error(f"❌ خطا در خواندن فایل GeoJSON: {e}")
        st.stop()
    except Exception as e:
        st.error(f"❌ خطا در پردازش GeoJSON: {e}")
        st.error(traceback.format_exc())
        st.stop()


# --- HTML Helper Functions ---
def modern_metric_card(label, value, icon="fa-info-circle", color="#fd7e14"): # Default icon color Orange
    value_display = value if value is not None and value != "" else "N/A"
    # Format numbers with commas if applicable
    if isinstance(value_display, (int, float)) and value_display != "N/A":
         value_display = f"{value_display:,.0f}" if value_display == int(value_display) else f"{value_display:,.2f}"

    return f"""
    <div class="modern-card">
        <i class="fas {icon}" style="color: {color};"></i>
        <h5>{label}</h5>
        <h3>{value_display}</h3>
    </div>
    """

def status_badge(status_text):
    status_text_lower = str(status_text).lower()
    css_class = "status-unknown"
    if pd.isna(status_text) or "بدون داده" in status_text_lower or "n/a" in status_text_lower: css_class = "status-nodata"
    elif "بهبود" in status_text_lower or "مثبت" in status_text_lower: css_class = "status-positive"
    elif "تنش" in status_text_lower or "کاهش" in status_text_lower or "بدتر" in status_text_lower or "خطا" in status_text_lower: css_class = "status-negative"
    elif "ثابت" in status_text_lower: css_class = "status-neutral"
    elif "جدید" in status_text_lower: css_class = "status-new"
    elif "حذف" in status_text_lower: css_class = "status-removed"
    return f'<span class="status-badge {css_class}">{status_text}</span>'

# Function to generate a randomish color based on a string (for variety/age maps)
def generate_color(input_string):
    random.seed(input_string) # Seed random number generator
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

# --- Initialize GEE and Load Data ---
if initialize_gee():
    farm_data_df = load_farm_data_from_geojson(FARM_GEOJSON_PATH)
else:
    st.stop()

if 'farm_data_df' not in locals() or farm_data_df.empty:
    st.stop()

# ==============================================================================
# Sidebar Filters (Enhanced with Expander and الاداره Filter)
# ==============================================================================
st.sidebar.header("🔧 تنظیمات و فیلترها")

with st.sidebar.expander("📅 انتخاب روز و اداره", expanded=True):
    # Day Selection
    available_days = sorted(farm_data_df['روز'].unique())
    selected_day = st.selectbox(
        "روز هفته:", options=available_days, index=0
    )

    # Filter by Day first
    daily_farms_df = farm_data_df[farm_data_df['روز'] == selected_day].copy()
    if daily_farms_df.empty:
        st.warning(f"هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
        st.stop()

    # الاداره Selection (Department/Unit) - Assuming 'اداره' column exists
    if 'اداره' in daily_farms_df.columns:
        available_edareh = sorted(daily_farms_df['اداره'].unique())
        edareh_options = ["همه ادارات"] + available_edareh
        selected_edareh = st.selectbox(
            "اداره:", options=edareh_options, index=0,
            help="فیلتر مزارع بر اساس اداره مربوطه."
        )
    else:
        st.warning("ستون 'اداره' در داده‌های مزارع یافت نشد. فیلتر اداره غیرفعال است.", icon="⚠️")
        selected_edareh = "همه ادارات"

    # Apply الاداره filter
    if selected_edareh == "همه ادارات":
        filtered_farms_df = daily_farms_df
    else:
        filtered_farms_df = daily_farms_df[daily_farms_df['اداره'] == selected_edareh]
        if filtered_farms_df.empty:
            st.warning(f"هیچ مزرعه‌ای برای اداره '{selected_edareh}' در روز '{selected_day}' یافت نشد.")
            st.stop()

with st.sidebar.expander("🌾 انتخاب مزرعه و شاخص", expanded=True):
    # Farm Selection (based on filtered data)
    available_farms = sorted(filtered_farms_df['مزرعه'].unique())
    farm_options = ["همه مزارع"] + available_farms
    # Default to 'همه مزارع' if an اداره is selected, otherwise keep previous logic?
    default_farm_index = 0 # Always default to 'همه مزارع' for simplicity now
    selected_farm_name = st.selectbox(
        "مزرعه:", options=farm_options, index=default_farm_index,
        help="یک مزرعه خاص را انتخاب کنید یا 'همه مزارع' را برای دید کلی نگه دارید."
    )

    # Index Selection
    index_options = {
        "NDVI": "پوشش گیاهی (NDVI)", "NDMI": "رطوبت گیاه (NDMI)", "EVI": "پوشش گیاهی بهبودیافته (EVI)",
        "SAVI": "پوشش گیاهی تعدیل خاک (SAVI)", "MSI": "تنش رطوبتی (MSI)", "LAI": "سطح برگ (LAI)", "CVI": "کلروفیل (CVI)"
    }
    selected_index = st.selectbox(
        "شاخص نقشه اصلی:", options=list(index_options.keys()), format_func=lambda x: f"{index_options[x]}", index=0
    )

# --- Date Range Calculation --- (Remains the same)
today = datetime.date.today()
persian_to_weekday = {"شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1, "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4}
try:
    target_weekday = persian_to_weekday[selected_day]
    days_ago = (today.weekday() - target_weekday + 7) % 7
    end_date_current = today if days_ago == 0 else today - datetime.timedelta(days=days_ago)
    start_date_current = end_date_current - datetime.timedelta(days=6)
    end_date_previous = start_date_current - datetime.timedelta(days=1)
    start_date_previous = end_date_previous - datetime.timedelta(days=6)
    start_date_current_str, end_date_current_str = start_date_current.strftime('%Y-%m-%d'), end_date_current.strftime('%Y-%m-%d')
    start_date_previous_str, end_date_previous_str = start_date_previous.strftime('%Y-%m-%d'), end_date_previous.strftime('%Y-%m-%d')

    st.sidebar.markdown("---")
    st.sidebar.caption(f"بازه فعلی: {start_date_current_str} تا {end_date_current_str}")
    st.sidebar.caption(f"بازه قبلی: {start_date_previous_str} تا {end_date_previous_str}")
    st.sidebar.markdown("---")
except KeyError:
    st.sidebar.error(f"روز هفته '{selected_day}' نامعتبر است.")
    st.stop()
except Exception as e:
    st.sidebar.error(f"خطا در محاسبه بازه زمانی: {e}")
    st.stop()


# ==============================================================================
# Google Earth Engine Functions (Unchanged)
# ==============================================================================
def maskS2clouds(image):
    qa = image.select('QA60')
    cloudBitMask = 1 << 10; cirrusBitMask = 1 << 11
    clear_mask_qa = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
    scl = image.select('SCL'); good_quality_scl = scl.remap([4, 5, 6, 11], [1, 1, 1, 1], 0)
    combined_mask = clear_mask_qa.And(good_quality_scl)
    opticalBands = image.select('B.*').multiply(0.0001)
    return image.addBands(opticalBands, None, True).updateMask(combined_mask)

def add_indices(image):
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    evi = image.expression('2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)', {'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2')}).rename('EVI')
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    savi = image.expression('((NIR - RED) / (NIR + RED + L)) * (1 + L)', {'NIR': image.select('B8'), 'RED': image.select('B4'), 'L': 0.5}).rename('SAVI')
    msi = image.expression('SWIR1 / (NIR + 0.0001)', {'SWIR1': image.select('B11'), 'NIR': image.select('B8')}).rename('MSI')
    lai = ndvi.multiply(3.5).max(0).rename('LAI')
    green_safe = image.select('B3').max(ee.Image(0.0001))
    cvi = image.expression('(NIR / GREEN_SAFE) * (RED / GREEN_SAFE)', {'NIR': image.select('B8'), 'GREEN_SAFE': green_safe, 'RED': image.select('B4')}).rename('CVI')
    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi, savi])

@st.cache_data(show_spinner="پردازش تصویر ماهواره‌ای...", persist=True)
def get_processed_image(_geometry, start_date, end_date, index_name):
    try:
        s2_sr_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(_geometry).filterDate(start_date, end_date).map(maskS2clouds)
        count = s2_sr_col.size().getInfo()
        if count == 0: return None, f"بی‌تصویر ({start_date} تا {end_date})"
        indexed_col = s2_sr_col.map(add_indices)
        median_image = indexed_col.median().select(index_name)
        # Basic check if the band has data near the centroid
        try:
            test_val = median_image.reduceRegion(ee.Reducer.firstNonNull(), _geometry.centroid(maxError=1), 10).get(index_name).getInfo()
            if test_val is None:
                return None, f"داده نامعتبر برای {index_name} در مرکز منطقه"
        except Exception: # Handle potential errors during the test reduction
             return None, f"خطا در بررسی اعتبار داده {index_name}"

        return median_image, None
    except ee.EEException as e: return None, f"خطای GEE: {e.args[0] if e.args else str(e)}"
    except Exception as e: return None, f"خطای ناشناخته GEE: {e}"

@st.cache_data(show_spinner="دریافت سری زمانی...", persist=True)
def get_index_time_series(_point_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    try:
        s2_sr_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(_point_geom).filterDate(start_date, end_date).map(maskS2clouds).map(add_indices).select(index_name)
        def extract_value(image):
            value = image.reduceRegion(reducer=ee.Reducer.firstNonNull(), geometry=_point_geom, scale=10).get(index_name)
            return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value}).set('hasValue', value)
        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.neq('hasValue', None))
        ts_info = ts_features.getInfo()['features']
        if not ts_info: return pd.DataFrame(columns=['date', index_name]), f"داده‌ای برای {index_name} یافت نشد."
        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_info]
        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df = ts_df.groupby('date').mean().reset_index().sort_values('date').set_index('date')
        return ts_df, None
    except ee.EEException as e: return pd.DataFrame(columns=['date', index_name]), f"خطای GEE سری زمانی: {e.args[0] if e.args else str(e)}"
    except Exception as e: return pd.DataFrame(columns=['date', index_name]), f"خطای ناشناخته سری زمانی: {e}"

@st.cache_data(show_spinner="محاسبه شاخص‌های نیازسنجی...", persist=True)
def get_farm_needs_data(_point_geom, start_curr, end_curr, start_prev, end_prev):
    results = {f'{idx}_{p}': None for idx in ['NDVI', 'NDMI', 'EVI', 'SAVI'] for p in ['curr', 'prev']}
    results['error'] = None; indices_to_get = ['NDVI', 'NDMI', 'EVI', 'SAVI']
    def get_mean_values(start, end):
        vals = {index: None for index in indices_to_get}
        try:
            s2_sr_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(_point_geom).filterDate(start, end).map(maskS2clouds).map(add_indices)
            count = s2_sr_col.size().getInfo();
            if count == 0: return vals, f"بی‌تصویر ({start}-{end})"
            median_image = s2_sr_col.median().select(indices_to_get)
            mean_dict = median_image.reduceRegion(reducer=ee.Reducer.mean(), geometry=_point_geom, scale=10, maxPixels=1e9).getInfo()
            if mean_dict:
                for index in indices_to_get: vals[index] = mean_dict.get(index)
            return vals, None
        except ee.EEException as e: return vals, f"خطای GEE ({start}-{end}): {e.args[0] if e.args else str(e)}"
        except Exception as e: return vals, f"خطای ناشناخته ({start}-{end}): {e}"
    curr_vals, err_curr = get_mean_values(start_curr, end_curr)
    if err_curr: results['error'] = err_curr
    for idx in indices_to_get: results[f'{idx}_curr'] = curr_vals.get(idx)
    prev_vals, err_prev = get_mean_values(start_prev, end_prev)
    if err_prev: results['error'] = f"{results.get('error', '')} | {err_prev}" if results.get('error') else err_prev
    for idx in indices_to_get: results[f'{idx}_prev'] = prev_vals.get(idx)
    return results

# ==============================================================================
# Gemini AI Helper Functions (Enhanced)
# ==============================================================================
@st.cache_resource
def configure_gemini():
    try:
        # --- WARNING: Hardcoding API keys is insecure! Use Streamlit secrets instead. ---
        api_key = "AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ" # <-- Use secrets ideally
        if not api_key:
            st.error("❌ کلید API جمینای (AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ) وارد نشده یا خالی است.") # Update error message if using secrets
            return None
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("Gemini Configured Successfully.")
        return model
    except Exception as e:
        st.error(f"❌ خطا در تنظیم Gemini API: {e}")
        return None

@st.cache_data(show_spinner="دریافت تحلیل نیازسنجی...", persist=True)
def get_ai_needs_analysis(_model, farm_name, index_data, recommendations):
    if _model is None: return "سرویس هوش مصنوعی در دسترس نیست."
    def fmt(val): return f"{val:.3f}" if val is not None else "N/A"
    data_str = f"NDVI: {fmt(index_data.get('NDVI_curr'))} (قبل: {fmt(index_data.get('NDVI_prev'))})\n" \
               f"NDMI: {fmt(index_data.get('NDMI_curr'))} (قبل: {fmt(index_data.get('NDMI_prev'))})\n" \
               f"EVI: {fmt(index_data.get('EVI_curr'))} (قبل: {fmt(index_data.get('EVI_prev'))})\n" \
               f"SAVI: {fmt(index_data.get('SAVI_curr'))} (قبل: {fmt(index_data.get('SAVI_prev'))})"
    prompt = f"""به عنوان متخصص نیشکر، وضعیت مزرعه '{farm_name}' را بر اساس داده‌ها و توصیه‌های زیر، در 3-5 جمله فارسی تحلیل کن. تمرکز بر نیاز آبیاری و تغذیه باشد و علت آن را توضیح بده.
داده‌ها (جاری / قبلی): {data_str}
توصیه‌ها: {', '.join(recommendations) if recommendations else 'موردی نیست.'}
تحلیل شما:"""
    try:
        response = _model.generate_content(prompt)
        return response.text if hasattr(response, 'text') else response.parts[0].text
    except Exception as e: return f"خطا در تحلیل نیازسنجی: {str(e)}"

# NEW Gemini function for map summary
@st.cache_data(show_spinner="دریافت خلاصه وضعیت مزارع...", persist=True)
def get_ai_map_summary(_model, status_counts, edareh_filter):
    """Generates AI summary for the classified map."""
    if _model is None: return "سرویس هوش مصنوعی در دسترس نیست."
    if not status_counts: return "داده‌ای برای خلاصه‌سازی وضعیت مزارع وجود ندارد."

    total_farms = sum(status_counts.values())
    status_lines = []
    for status, count in status_counts.items():
        if count > 0:
            percent = (count / total_farms) * 100
            status_lines.append(f"- {status}: {count} مزرعه ({percent:.1f}%)")

    status_summary = "\n".join(status_lines)
    edareh_context = f"برای اداره '{edareh_filter}'" if edareh_filter != "همه ادارات" else "برای همه ادارات انتخاب شده"

    prompt = f"""
    شما یک تحلیلگر کشاورزی هستید. خلاصه‌ای کوتاه و کاربردی (2-4 جمله) به زبان فارسی از وضعیت کلی مزارع بر اساس دسته‌بندی‌های زیر ارائه دهید. به نکات کلیدی مانند درصد مزارع در وضعیت‌های نامطلوب یا بهبود یافته اشاره کنید.
    زمینه: {edareh_context} در روز {selected_day}.

    توزیع وضعیت مزارع:
    {status_summary}
    تعداد کل مزارع: {total_farms}

    خلاصه وضعیت کلی:
    """
    try:
        response = _model.generate_content(prompt)
        return response.text if hasattr(response, 'text') else response.parts[0].text
    except Exception as e:
        st.warning(f"⚠️ خطا در ارتباط با Gemini API برای خلاصه نقشه: {e}")
        return f"خطا در دریافت خلاصه وضعیت: {str(e)}"

# ==============================================================================
# Main Application Layout (Tabs)
# ==============================================================================
gemini_model = configure_gemini()
tab1, tab2 = st.tabs(["📊 پایش مزارع", "💧 نیازسنجی کود و آبیاری"])

with tab1:
    # ==========================================================================
    # Main Panel Display (Monitoring)
    # ==========================================================================
    st.subheader(f"🗓️ وضعیت مزارع در روز: {selected_day}")
    if selected_edareh != "همه ادارات":
        st.markdown(f"##### اداره: {selected_edareh}")

    selected_farm_details = None
    selected_farm_geom = None
    map_center_lat = INITIAL_LAT
    map_center_lon = INITIAL_LON
    map_zoom = INITIAL_ZOOM

    # --- Setup Geometry and Initial Info ---
    if selected_farm_name == "همه مزارع":
        if not filtered_farms_df.empty:
            # Calculate overall stats for the filtered (daily, possibly edareh) farms
            num_farms = len(filtered_farms_df)
            avg_area = filtered_farms_df['مساحت'].mean() if 'مساحت' in filtered_farms_df else None
            avg_age = filtered_farms_df['سن'].mean() if 'سن' in filtered_farms_df else None
            common_variety = filtered_farms_df['واریته'].mode()[0] if 'واریته' in filtered_farms_df and not filtered_farms_df['واریته'].mode().empty else "متنوع"

            summary_cols = st.columns(4)
            with summary_cols[0]:
                 st.markdown(modern_metric_card("تعداد مزارع", num_farms, icon="fa-layer-group"), unsafe_allow_html=True)
            with summary_cols[1]:
                 st.markdown(modern_metric_card("میانگین مساحت", avg_area, icon="fa-chart-area"), unsafe_allow_html=True)
            with summary_cols[2]:
                 st.markdown(modern_metric_card("میانگین سن", avg_age, icon="fa-calendar-days"), unsafe_allow_html=True)
            with summary_cols[3]:
                 st.markdown(modern_metric_card("واریته غالب", common_variety, icon="fa-star"), unsafe_allow_html=True)


            min_lon, min_lat = filtered_farms_df['centroid_lon'].min(), filtered_farms_df['centroid_lat'].min()
            max_lon, max_lat = filtered_farms_df['centroid_lon'].max(), filtered_farms_df['centroid_lat'].max()
            buffer = 0.001
            selected_farm_geom = ee.Geometry.Rectangle([min_lon - buffer, min_lat - buffer, max_lon + buffer, max_lat + buffer])
            map_center_lat = (min_lat + max_lat) / 2
            map_center_lon = (min_lon + max_lon) / 2
            map_zoom = 11 if num_farms > 1 else 13 # Zoom out more for multiple farms
        else:
             st.warning("داده‌ای برای نمایش 'همه مزارع' در این روز/اداره وجود ندارد.")
             selected_farm_geom = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT])
    else:
        selection = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name]
        if not selection.empty:
            selected_farm_details = selection.iloc[0]
            lat = selected_farm_details['centroid_lat']
            lon = selected_farm_details['centroid_lon']
            selected_farm_geom = ee.Geometry.Point([lon, lat])
            map_center_lat, map_center_lon, map_zoom = lat, lon, 14

            st.write(f"**جزئیات مزرعه: {selected_farm_name}** (اداره: {selected_farm_details.get('اداره', 'N/A')})")
            details_cols = st.columns(4)
            details_cols[0].markdown(modern_metric_card("مساحت (ha)", selected_farm_details.get('مساحت'), icon="fa-vector-square"), unsafe_allow_html=True)
            details_cols[1].markdown(modern_metric_card("واریته", selected_farm_details.get('واریته', 'N/A'), icon="fa-seedling"), unsafe_allow_html=True)
            details_cols[2].markdown(modern_metric_card("گروه", selected_farm_details.get('گروه', 'N/A'), icon="fa-users"), unsafe_allow_html=True)
            details_cols[3].markdown(modern_metric_card("سن", selected_farm_details.get('سن'), icon="fa-hourglass-half"), unsafe_allow_html=True)
        else:
             st.error(f"مزرعه '{selected_farm_name}' یافت نشد.")
             selected_farm_geom = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT])


    # --- Map Display (Enhanced with Layers) ---
    st.markdown("---")
    st.subheader(f"🗺️ نقشه پایش مزارع")

    vis_params = { # Keep vis params from previous version
        'NDVI': {'min': 0.0, 'max': 0.9, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']},
        'EVI': {'min': 0.0, 'max': 0.9, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']},
        'NDMI': {'min': -0.5, 'max': 0.8, 'palette': ['#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#f7f7f7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac']},
        'SAVI': {'min': 0.0, 'max': 0.9, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']},
        'LAI': {'min': 0, 'max': 7, 'palette': ['#EFEFEF', '#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']},
        'MSI': {'min': 0, 'max': 3, 'palette': ['#2166ac', '#4393c3', '#92c5de', '#d1e5f0', '#f7f7f7', '#fddbc7', '#f4a582', '#d6604d', '#b2182b'][::-1]},
        'CVI': {'min': 0, 'max': 25, 'palette': ['#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']},
    }
    current_vis = vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']})


    m = geemap.Map(location=[map_center_lat, map_center_lon], zoom=map_zoom, add_google_map=True)
    m.add_basemap("SATELLITE") # Default to Satellite

    # Add GEE Layer (Index)
    gee_image_current, error_msg_current = None, None
    if selected_farm_geom:
        with st.spinner(f"بارگیری تصویر {selected_index}..."):
            gee_image_current, error_msg_current = get_processed_image(
                selected_farm_geom, start_date_current_str, end_date_current_str, selected_index
            )
    map_layer_name = f"{index_options[selected_index]} ({end_date_current_str})"
    if gee_image_current:
        try:
            m.addLayer(gee_image_current, current_vis, map_layer_name)
            m.add_colorbar(current_vis, label=f"{index_options[selected_index]}", layer_name=map_layer_name)
        except Exception as map_err: st.error(f"خطا در افزودن لایه GEE: {map_err}")
    elif error_msg_current: st.warning(f"تصویر {selected_index} یافت نشد: {error_msg_current}")

    # Create Feature Groups for categorized markers (Age, Variety, Status)
    age_groups = {}
    variety_groups = {}
    status_groups = {} # For the new classified status map

    # --- Prepare data for classified layers (using ranking table results) ---
    # Recalculate ranking_df here to ensure it matches current filters
    # This recalculation might happen again later, consider optimizing if slow
    ranking_df_map, map_calc_errors = calculate_weekly_indices(
        filtered_farms_df[['مزرعه', 'گروه', 'اداره', 'سن', 'واریته', 'centroid_lat', 'centroid_lon']], # Include needed cols
        selected_index, start_date_current_str, end_date_current_str,
        start_date_previous_str, end_date_previous_str
    )
    if not ranking_df_map.empty:
         ranking_df_map['وضعیت_متن'] = ranking_df_map.apply(lambda row: determine_status(row, selected_index), axis=1)
         # Merge back other details needed for popups if not already present
         ranking_df_map = pd.merge(ranking_df_map,
                                   filtered_farms_df[['مزرعه', 'سن', 'واریته', 'اداره', 'گروه', 'centroid_lat', 'centroid_lon']],
                                   on='مزرعه', how='left', suffixes=('', '_dup'))
         # Drop duplicate columns resulting from merge if any
         ranking_df_map = ranking_df_map[[c for c in ranking_df_map.columns if not c.endswith('_dup')]]

    else:
         st.warning("داده‌ای برای ایجاد لایه‌های طبقه‌بندی نقشه یافت نشد.")
         # Use base filtered_farms_df for age/variety if ranking fails
         ranking_df_map = filtered_farms_df.copy()
         ranking_df_map['وضعیت_متن'] = 'بدون داده' # Assign default status


    # Define status categories and colors (Map Feature 2)
    status_map_colors = {
        "رشد مثبت / بهبود": ('#198754', 'fa-arrow-up'), # Green, up arrow
        "بهبود / کاهش تنش": ('#198754', 'fa-arrow-down'), # Green, down arrow (less stress)
        "ثابت": ('#ffc107', 'fa-equals'), # Yellow, equals
        "تنش / کاهش": ('#dc3545', 'fa-arrow-down'), # Red, down arrow
        "تنش / بدتر شدن": ('#dc3545', 'fa-arrow-up'), # Red, up arrow (more stress)
        "جدید": ('#0dcaf0', 'fa-star'), # Cyan, star
        "حذف شده?": ('#6c757d', 'fa-question'), # Gray, question
        "بدون داده": ('#adb5bd', 'fa-circle-notch'), # Lighter Gray, spinner
        "خطا در ستون": ('#dc3545', 'fa-exclamation-triangle'), # Red, warning
        "بدون تغییر معتبر": ('#adb5bd', 'fa-minus'), # Lighter Gray, minus
        "Unknown": ('#6c757d', 'fa-question-circle') # Default
    }
    status_legend_map = { # For the legend explanation
        "بهبود": ('#198754', 'وضعیت بهتر نسبت به هفته قبل'),
        "ثابت": ('#ffc107', 'وضعیت مشابه هفته قبل'),
        "تنش/کاهش": ('#dc3545', 'وضعیت بدتر نسبت به هفته قبل'),
        "جدید": ('#0dcaf0', 'مزرعه جدید (داده فقط برای این هفته)'),
        "نامشخص/خطا": ('#6c757d', 'داده ناکافی یا خطا در محاسبه')
    }

    # Define Age colors (Map Feature 3)
    # Define age bins and colors more systematically
    age_bins = [0, 1, 2, 3, 5, 10, 100] # Example bins: 0, 1, 2, 3-4, 5-9, 10+
    age_labels = ['سن 0', 'سن 1', 'سن 2', 'سن 3-4', 'سن 5-9', 'سن +10']
    age_colors = px.colors.qualitative.Pastel # Use a Plotly sequence
    # Assign colors to labels cyclically
    age_color_map = {label: age_colors[i % len(age_colors)] for i, label in enumerate(age_labels)}

    # Populate Feature Groups
    for idx, farm in ranking_df_map.iterrows():
        lat, lon = farm['centroid_lat'], farm['centroid_lon']
        popup_html = f"<b>مزرعه:</b> {farm['مزرعه']}<br>" \
                     f"<b>اداره:</b> {farm.get('اداره', 'N/A')}<br>" \
                     f"<b>گروه:</b> {farm.get('گروه', 'N/A')}<br>" \
                     f"<b>سن:</b> {farm.get('سن', 'N/A'):.0f}<br>" \
                     f"<b>واریته:</b> {farm.get('واریته', 'N/A')}<br>" \
                     f"<b>وضعیت:</b> {farm.get('وضعیت_متن', 'N/A')}"

        # Age Layer (Map Feature 3)
        if 'سن' in farm and pd.notna(farm['سن']):
            age_int = int(farm['سن'])
            # Find the correct bin label
            bin_label = age_labels[-1] # Default to last bin
            for i in range(len(age_bins) - 1):
                if age_bins[i] <= age_int < age_bins[i+1]:
                    bin_label = age_labels[i]
                    break
            age_group_name = bin_label
            if age_group_name not in age_groups:
                 age_groups[age_group_name] = folium.FeatureGroup(name=f"سن: {age_group_name}", show=False)
            color = age_color_map.get(age_group_name, '#CCCCCC') # Get color from map
            folium.CircleMarker(
                location=[lat, lon], radius=5, popup=popup_html, tooltip=f"{farm['مزرعه']} (سن {age_int})",
                color=color, fill=True, fill_color=color, fill_opacity=0.7
            ).add_to(age_groups[age_group_name])

        # Variety Layer (Map Feature 3)
        if 'واریته' in farm and pd.notna(farm['واریته']):
             variety_name = str(farm['واریته']).strip()
             if not variety_name: variety_name = "نامشخص" # Handle empty variety names
             if variety_name not in variety_groups:
                  variety_groups[variety_name] = folium.FeatureGroup(name=f"واریته: {variety_name}", show=False)
             color = generate_color(variety_name) # Generate color based on name
             folium.CircleMarker(
                 location=[lat, lon], radius=5, popup=popup_html, tooltip=f"{farm['مزرعه']} ({variety_name})",
                 color=color, fill=True, fill_color=color, fill_opacity=0.7
             ).add_to(variety_groups[variety_name])

        # Status Layer (Map Feature 2)
        status_text = farm.get('وضعیت_متن', 'Unknown')
        color, icon = status_map_colors.get(status_text, status_map_colors["Unknown"])
        status_group_name = status_text # Group by the exact status text
        if status_group_name not in status_groups:
             # Group similar statuses for layer control simplicity? Or keep separate? Let's keep separate for now.
             status_groups[status_group_name] = folium.FeatureGroup(name=f"وضعیت: {status_group_name}", show=False) # Initially hidden
        folium.Marker(
            location=[lat, lon], popup=popup_html, tooltip=f"{farm['مزرعه']} ({status_text})",
            icon=folium.Icon(color='white', icon_color=color, icon=icon, prefix='fa') # Use FontAwesome icons
        ).add_to(status_groups[status_group_name])


    # Add FeatureGroups to the map
    for group in age_groups.values(): group.add_to(m)
    for group in variety_groups.values(): group.add_to(m)
    for group in status_groups.values(): group.add_to(m)


    # Add the LayerControl
    folium.LayerControl(collapsed=True).add_to(m)

    # Display Map
    try:
        st_folium(m, width=None, height=600, use_container_width=True) # Increased height
        st.caption("از کنترل لایه‌ها (بالا سمت راست) برای نمایش/پنهان کردن لایه‌های شاخص، سن، واریته و وضعیت استفاده کنید.")
    except Exception as display_err:
        st.error(f"خطا در نمایش نقشه: {display_err}")


    # --- Classified Status Map Summary (Feature 2 - Gemini) ---
    st.markdown("---")
    st.subheader("📊 خلاصه وضعیت طبقه‌بندی شده مزارع")
    if not ranking_df_map.empty:
        status_counts_raw = ranking_df_map['وضعیت_متن'].value_counts().to_dict()
        # Map raw statuses to simplified legend categories for reporting
        simplified_status_counts = Counter()
        for status, count in status_counts_raw.items():
             if "بهبود" in status: simplified_status_counts["بهبود"] += count
             elif "ثابت" in status: simplified_status_counts["ثابت"] += count
             elif "تنش" in status or "کاهش" in status or "خطا" in status or "بدتر" in status: simplified_status_counts["تنش/کاهش"] += count
             elif "جدید" in status: simplified_status_counts["جدید"] += count
             else: simplified_status_counts["نامشخص/خطا"] += count

        # Display counts using Plotly Bar Chart
        status_df = pd.DataFrame(simplified_status_counts.items(), columns=['وضعیت', 'تعداد']).sort_values('تعداد', ascending=False)
        status_colors = [status_legend_map.get(s, ('#6c757d',''))[0] for s in status_df['وضعیت']] # Get colors from legend map

        fig_status = px.bar(status_df, x='وضعیت', y='تعداد', color='وضعیت',
                            title=f"توزیع وضعیت مزارع ({selected_edareh if selected_edareh != 'همه ادارات' else 'کل'})",
                            text_auto=True, color_discrete_sequence=status_colors)
        fig_status.update_layout(xaxis_title="وضعیت", yaxis_title="تعداد مزارع", showlegend=False,
                                 height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_status, use_container_width=True)


        # Display AI Summary
        if gemini_model:
             ai_map_summary = get_ai_map_summary(gemini_model, simplified_status_counts, selected_edareh)
             st.markdown("**خلاصه تحلیلی (هوش مصنوعی):**")
             st.markdown(f"> {ai_map_summary}")
        else:
             st.info("سرویس هوش مصنوعی برای خلاصه‌سازی در دسترس نیست.")

        # Display Legend Manually
        st.markdown("**راهنمای نقشه وضعیت:**")
        legend_html = "<div style='display: flex; flex-wrap: wrap; gap: 15px;'>"
        for status_name, (color, desc) in status_legend_map.items():
             # Find the icon used for this status group (use the most representative one)
             icon_class = 'fa-question-circle' # Default
             for raw_status, (icon_color_raw, icon_raw) in status_map_colors.items():
                  match = False
                  if status_name == "بهبود" and "بهبود" in raw_status: match = True
                  elif status_name == "ثابت" and "ثابت" in raw_status: match = True
                  elif status_name == "تنش/کاهش" and ("تنش" in raw_status or "کاهش" in raw_status or "بدتر" in raw_status or "خطا" in raw_status): match = True
                  elif status_name == "جدید" and "جدید" in raw_status: match = True
                  elif status_name == "نامشخص/خطا" and ("داده" in raw_status or "حذف" in raw_status or "تغییر معتبر" in raw_status or "Unknown" in raw_status): match = True

                  if match:
                      icon_class = icon_raw
                      break

             legend_html += f"<div style='display: flex; align-items: center; gap: 5px;'><i class='fas {icon_class}' style='color:{color};'></i> <span>{status_name}: {desc}</span></div>"
        legend_html += "</div>"
        st.markdown(legend_html, unsafe_allow_html=True)

    else:
        st.info("داده‌ای برای نمایش خلاصه وضعیت طبقه‌بندی شده وجود ندارد.")


    # --- Time Series Chart (No change needed here) ---
    st.markdown("---")
    st.subheader(f"📈 نمودار روند زمانی: {index_options[selected_index]}")
    if selected_farm_name == "همه مزارع":
        st.info("یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
    elif selected_farm_geom and selected_farm_details is not None:
        is_point = isinstance(selected_farm_geom, ee.geometry.Point)
        if is_point:
            timeseries_end_date = today.strftime('%Y-%m-%d')
            timeseries_start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
            ts_df, ts_error = get_index_time_series(selected_farm_geom, selected_index, start_date=timeseries_start_date, end_date=timeseries_end_date)
            if ts_error: st.warning(f"خطا در دریافت سری زمانی: {ts_error}")
            elif not ts_df.empty:
                fig_ts = px.line(ts_df, x=ts_df.index, y=selected_index, title=f"روند {selected_index} - {selected_farm_name} (12 ماه اخیر)", labels={'date': 'تاریخ', selected_index: f'مقدار {selected_index}'})
                fig_ts.update_traces(mode='lines+markers', line=dict(color='#6f42c1', width=2), marker=dict(color='#fd7e14', size=5))
                fig_ts.update_layout(hovermode="x unified", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_title=f"{selected_index}", xaxis_title="تاریخ")
                st.plotly_chart(fig_ts, use_container_width=True)
            else: st.info(f"داده‌ای برای سری زمانی {selected_index} در 12 ماه گذشته یافت نشد.")
        else: st.warning("نمودار سری زمانی فقط برای مزارع منفرد در دسترس است.")
    else: st.warning("جزئیات مزرعه برای نمایش نمودار سری زمانی در دسترس نیست.")


    # ==========================================================================
    # Ranking Table (Remains largely the same, but uses recalculated data)
    # ==========================================================================
    st.markdown("---")
    st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {index_options[selected_index]}")
    st.markdown(f"مقایسه هفته جاری ({end_date_current_str}) با هفته قبل ({end_date_previous_str}). اداره: **{selected_edareh}**")


    # Display errors from the map calculation (which is the same calculation)
    if map_calc_errors:
        with st.expander("⚠️ مشاهده خطاهای محاسبه رتبه‌بندی (کلیک کنید)", expanded=False):
             # (Error display logic reused from previous step)
            error_dict = {}
            for error_str in map_calc_errors:
                try: farm_name_err = error_str.split(" (")[0]; error_dict.setdefault(farm_name_err, []).append(error_str)
                except Exception: error_dict.setdefault("Unknown", []).append(error_str)
            for farm_name_err, err_list in error_dict.items():
                 st.error(f"**مزرعه: {farm_name_err}**"); [st.caption(f"- {err}") for err in err_list]


    if not ranking_df_map.empty:
        # Sort, format, and display the table (using ranking_df_map which has status_text)
        ascending_sort = selected_index in ['MSI']
        # Ensure change column is numeric for sorting if needed, handle potential errors
        ranking_df_map['تغییر_numeric'] = pd.to_numeric(ranking_df_map['تغییر'], errors='coerce')
        ranking_df_map_sorted = ranking_df_map.sort_values(
            by=f'{selected_index} (هفته جاری)', ascending=ascending_sort, na_position='last'
        ).reset_index(drop=True)
        ranking_df_map_sorted.index = ranking_df_map_sorted.index + 1
        ranking_df_map_sorted.index.name = 'رتبه'

        ranking_df_map_sorted['وضعیت'] = ranking_df_map_sorted['وضعیت_متن'].apply(status_badge) # Generate HTML badge

        cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
        for col in cols_to_format:
            if col in ranking_df_map_sorted.columns:
                 ranking_df_map_sorted[col] = ranking_df_map_sorted[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) and isinstance(x, (int, float)) else ("N/A" if pd.isna(x) else x))

        display_columns_order = ['مزرعه', 'اداره', 'گروه', f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر', 'وضعیت']
        display_columns = [col for col in display_columns_order if col in ranking_df_map_sorted.columns and col != 'تغییر_numeric'] # Exclude numeric change col

        st.markdown("<style> td, th { text-align: right !important; } </style>", unsafe_allow_html=True)
        st.write(ranking_df_map_sorted[display_columns].to_html(escape=False, index=True, classes='dataframe table table-striped table-hover', justify='right'), unsafe_allow_html=True)

        # Download Button
        csv_df = ranking_df_map_sorted.drop(columns=['وضعیت', 'تغییر_numeric', 'وضعیت_متن']) # Drop helper/HTML columns
        csv_df.rename(columns={'وضعیت_متن': 'Status_Text'}, inplace=True, errors='ignore') # Keep text status if needed
        csv_data = csv_df.to_csv(index=True, encoding='utf-8-sig')
        st.download_button(
            label="📥 دانلود جدول رتبه‌بندی (CSV)", data=csv_data,
            file_name=f'ranking_{selected_edareh}_{selected_index}_{selected_day}_{end_date_current_str}.csv', mime='text/csv'
        )
    else:
        st.info(f"داده‌ای برای جدول رتبه‌بندی ({selected_index}) یافت نشد.")


# --- Tab 2: Needs Analysis ---
with tab2:
    st.header("💧 تحلیل نیاز آبیاری و تغذیه")

    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری در تب 'پایش مزارع' انتخاب کنید تا تحلیل نیازهای آن نمایش داده شود.")
    elif selected_farm_details is not None and selected_farm_geom is not None:
        is_point = isinstance(selected_farm_geom, ee.geometry.Point)
        if not is_point:
            st.warning("تحلیل نیازها فقط برای مزارع منفرد در دسترس است.")
        else:
            st.subheader(f"تحلیل برای مزرعه: {selected_farm_name} (اداره: {selected_farm_details.get('اداره', 'N/A')})")

            # Thresholds
            st.markdown("**تنظیم آستانه‌های هشدار:**")
            thresh_cols = st.columns(2)
            ndmi_threshold = thresh_cols[0].slider("آستانه NDMI (کم آبی):", -0.2, 0.5, 0.25, 0.01, format="%.2f", key="ndmi_thresh_tab2")
            ndvi_drop_threshold = thresh_cols[1].slider("آستانه افت NDVI (تغذیه/تنش):", 0.0, 20.0, 7.0, 0.5, format="%.1f%%", key="ndvi_thresh_tab2")

            # Get Data
            farm_needs_data = get_farm_needs_data(selected_farm_geom, start_date_current_str, end_date_current_str, start_date_previous_str, end_date_previous_str)

            if farm_needs_data['error']:
                st.error(f"خطا در دریافت داده‌های شاخص برای تحلیل: {farm_needs_data['error']}")
            elif farm_needs_data['NDMI_curr'] is None or farm_needs_data['NDVI_curr'] is None:
                st.warning("داده‌های شاخص لازم (NDMI/NDVI) برای تحلیل در دوره فعلی یافت نشد.")
            else:
                # Display Indices
                st.markdown("**مقادیر شاخص‌ها (مقایسه هفتگی):**")
                idx_cols = st.columns(4)
                def calc_delta(curr, prev):
                    return curr - prev if curr is not None and prev is not None and isinstance(curr, (int, float)) and isinstance(prev, (int, float)) else None
                ndvi_d = calc_delta(farm_needs_data.get('NDVI_curr'), farm_needs_data.get('NDVI_prev'))
                ndmi_d = calc_delta(farm_needs_data.get('NDMI_curr'), farm_needs_data.get('NDMI_prev'))
                evi_d = calc_delta(farm_needs_data.get('EVI_curr'), farm_needs_data.get('EVI_prev'))
                savi_d = calc_delta(farm_needs_data.get('SAVI_curr'), farm_needs_data.get('SAVI_prev'))
                idx_cols[0].metric("NDVI", f"{farm_needs_data['NDVI_curr']:.3f}", f"{ndvi_d:+.3f}" if ndvi_d is not None else None)
                idx_cols[1].metric("NDMI", f"{farm_needs_data['NDMI_curr']:.3f}", f"{ndmi_d:+.3f}" if ndmi_d is not None else None)
                idx_cols[2].metric("EVI", f"{farm_needs_data.get('EVI_curr', 0):.3f}", f"{evi_d:+.3f}" if evi_d is not None else None)
                idx_cols[3].metric("SAVI", f"{farm_needs_data.get('SAVI_curr', 0):.3f}", f"{savi_d:+.3f}" if savi_d is not None else None)

                # Recommendations
                recommendations = []
                issues = False
                if farm_needs_data['NDMI_curr'] < ndmi_threshold:
                    recommendations.append(f"💧 **نیاز احتمالی به آبیاری:** NDMI ({farm_needs_data['NDMI_curr']:.3f}) < آستانه ({ndmi_threshold:.2f}).")
                    issues = True
                ndvi_prev = farm_needs_data.get('NDVI_prev')
                if ndvi_prev is not None and farm_needs_data['NDVI_curr'] < ndvi_prev:
                     try:
                         if abs(ndvi_prev) > 1e-6:
                             change_pct = ((farm_needs_data['NDVI_curr'] - ndvi_prev) / abs(ndvi_prev)) * 100
                             if abs(change_pct) > ndvi_drop_threshold:
                                 recommendations.append(f"⚠️ **نیاز به بررسی تغذیه/تنش:** افت NDVI ({change_pct:.1f}%) مشاهده شد.")
                                 issues = True
                     except Exception: pass
                if farm_needs_data['NDVI_curr'] < 0.3 and not any("تغذیه/تنش" in r for r in recommendations):
                    recommendations.append(f"📉 **پوشش گیاهی ضعیف:** NDVI ({farm_needs_data['NDVI_curr']:.3f}) پایین است.")
                    issues = True
                if not issues and not recommendations:
                    recommendations.append("✅ **وضعیت مطلوب:** هشدار خاصی شناسایی نشد.")

                st.markdown("**توصیه‌های اولیه:**")
                for rec in recommendations:
                    if "آبیاری" in rec: st.error(rec)
                    elif "تغذیه/تنش" in rec or "ضعیف" in rec: st.warning(rec)
                    else: st.success(rec)

                # AI Analysis
                st.markdown("---")
                st.markdown("**تحلیل هوش مصنوعی (Gemini):**")
                if gemini_model:
                    concise_recs = [r.split(':')[0].replace('*','').strip() for r in recommendations]
                    ai_needs_summary = get_ai_needs_analysis(gemini_model, selected_farm_name, farm_needs_data, concise_recs)
                    st.markdown(f"> {ai_needs_summary}")
                else: st.info("سرویس تحلیل هوش مصنوعی پیکربندی نشده است.")
    else:
        st.warning("ابتدا یک مزرعه معتبر را از پنل کناری در تب 'پایش مزارع' انتخاب کنید.")


# --- Footer ---
st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با 💚 توسط [اسماعیل کیانی]")
# st.sidebar.markdown("[GitHub](https://your-link-here)")