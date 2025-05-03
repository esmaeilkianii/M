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
import numpy as np # For NaN handling

# --- Custom CSS ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide"
)

# Modern CSS with enhanced styles (Unchanged from your original code)
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
# --- NOTE: Ensure this path is correct relative to where you run the script ---
logo_path = 'logo (1).png'
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, use_column_width=True)
    # st.sidebar.markdown(f"<div class='sidebar-logo'><img src='{logo_path}' alt='لوگو سامانه' /></div>", unsafe_allow_html=True) # Use st.image for better handling
else:
    st.sidebar.warning(f"لوگو در مسیر '{logo_path}' یافت نشد.")

# --- Main Header ---
st.markdown("<div class='main-header'>", unsafe_allow_html=True)
# Using st.image is generally safer and handles path/display better
if os.path.exists(logo_path):
     # Create columns to control logo size and alignment better
     h_cols = st.columns([1, 10]) # Adjust ratio as needed
     with h_cols[0]:
          st.image(logo_path, width=60) # Adjust width as needed
     with h_cols[1]:
         st.markdown(
             """
             <div>
                 <h1>سامانه پایش هوشمند نیشکر</h1>
                 <h4>مطالعات کاربردی شرکت کشت و صنعت دهخدا</h4>
             </div>
             """,
             unsafe_allow_html=True
         )
else:
     st.markdown(
         f"""
         <span class='main-logo' style='font-size: 40px; line-height: 60px; text-align: center; background: #eee; display: inline-block;'>🌾</span>
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
# --- WARNING: Hardcoding paths like this might not be portable. Consider relative paths or config files. ---
# --- Make sure this file exists in the *same directory* as your script, or provide the full path ---
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'
FARM_GEOJSON_PATH = 'farm_geodata_fixed.geojson' # Assumed to contain 'اداره' now (or handle its absence)

# --- GEE Authentication ---
@st.cache_resource
def initialize_gee():
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"خطا: فایل Service Account در مسیر '{SERVICE_ACCOUNT_FILE}' یافت نشد. لطفاً فایل را در کنار اسکریپت قرار دهید یا مسیر کامل را وارد کنید.")
            st.stop()
        # --- WARNING: Using Service Account Credentials directly ---
        credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Initialized Successfully.")
        return True
    except Exception as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.error(traceback.format_exc()) # Print full traceback for debugging
        st.stop()

# --- Load Farm Data ---
@st.cache_data(show_spinner="بارگذاری داده‌های مزارع...")
def load_farm_data_from_geojson(geojson_path):
    if not os.path.exists(geojson_path):
        st.error(f"❌ فایل '{geojson_path}' یافت نشد. لطفاً فایل را در کنار اسکریپت قرار دهید یا مسیر صحیح را وارد کنید.")
        st.stop()
    try:
        with open(geojson_path, 'r', encoding='utf-8') as f:
            gj = json.load(f)
        features = gj.get('features', []) # Use .get() for safety
        if not features:
            st.error("❌ فایل GeoJSON معتبر است اما هیچ 'feature' ای در آن یافت نشد.")
            st.stop()

        records = []
        # --- MODIFIED: Removed 'اداره' from strictly required properties for loading ---
        # 'اداره' is useful but not essential to load the basic farm data.
        # The rest of the code will handle its potential absence.
        required_props = ['مزرعه', 'روز', 'گروه']
        optional_props = ['اداره', 'واریته', 'سن', 'مساحت'] # Properties we want but might be missing
        has_warned_missing_req_props = False
        has_warned_invalid_coords = False

        for i, feat in enumerate(features):
            props = feat.get('properties', {})
            geom = feat.get('geometry')
            centroid_lon, centroid_lat = None, None

            # Check for essential properties needed for identification and grouping
            missing_req = [p for p in required_props if p not in props or props[p] is None or str(props[p]).strip() == ""]
            if missing_req:
                 if not has_warned_missing_req_props:
                      st.warning(f"برخی مزارع (اولین مورد در ردیف {i+1} فایل GeoJSON) فاقد ویژگی‌های ضروری ({', '.join(missing_req)}) هستند و نادیده گرفته می‌شوند.", icon="⚠️")
                      has_warned_missing_req_props = True
                 continue # Skip this feature

            # Calculate Centroid
            try:
                if geom and geom['type'] == 'Polygon' and geom.get('coordinates'):
                    # Handling potential nesting [[]] vs []
                    coords = geom['coordinates'][0] if isinstance(geom['coordinates'][0], list) else geom['coordinates']
                    # Ensure coordinates are valid points
                    valid_coords = [pt for pt in coords if isinstance(pt, (list, tuple)) and len(pt) >= 2 and all(isinstance(c, (int, float)) for c in pt[:2])]
                    if valid_coords:
                        lons = [pt[0] for pt in valid_coords]
                        lats = [pt[1] for pt in valid_coords]
                        if lons and lats:
                            centroid_lon = sum(lons) / len(lons)
                            centroid_lat = sum(lats) / len(lats)
                elif geom and geom['type'] == 'Point' and geom.get('coordinates'):
                     coords = geom['coordinates']
                     if isinstance(coords, (list, tuple)) and len(coords) == 2 and all(isinstance(c, (int, float)) for c in coords):
                         centroid_lon, centroid_lat = coords
            except Exception as e:
                 # Catch potential errors during coordinate processing
                 if not has_warned_invalid_coords:
                     st.warning(f"خطا در پردازش مختصات برای مزرعه '{props.get('مزرعه', 'ناشناس')}' (ردیف {i+1}): {e}. این مزرعه نادیده گرفته شد.", icon="🗺️")
                     has_warned_invalid_coords = True
                 continue # Skip if coordinates cause error

            # Only add if centroid is valid
            if centroid_lon is not None and centroid_lat is not None:
                record = {prop: props.get(prop) for prop in required_props} # Add required props
                record.update({prop: props.get(prop) for prop in optional_props}) # Add optional props if they exist
                record['geometry_type'] = geom.get('type')
                # Storing coordinates can make the dataframe huge, maybe skip if not needed later?
                # record['coordinates'] = geom.get('coordinates')
                record['centroid_lon'] = centroid_lon
                record['centroid_lat'] = centroid_lat
                records.append(record)
            elif not has_warned_invalid_coords: # Warn only once if geometry/centroid calculation fails silently
                 st.warning(f"مزرعه '{props.get('مزرعه', 'ناشناس')}' (ردیف {i+1}) فاقد مختصات معتبر یا قابل محاسبه است و نادیده گرفته شد.", icon="🗺️")
                 has_warned_invalid_coords = True

        if not records:
            st.error("⚠️ هیچ مزرعه‌ای با ویژگی‌های ضروری و مختصات معتبر در فایل GeoJSON یافت نشد. برنامه متوقف می‌شود.")
            st.stop()

        df = pd.DataFrame(records)

        # --- Basic Cleaning ---
        # Apply cleaning only if column exists
        if 'روز' in df.columns:
             df['روز'] = df['روز'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
        if 'گروه' in df.columns:
             df['گروه'] = df['گروه'].astype(str).str.strip()
        if 'اداره' in df.columns: # Clean 'اداره' only if it exists
             df['اداره'] = df['اداره'].astype(str).str.strip().replace('None', pd.NA).replace('', pd.NA)
             if df['اداره'].isna().all(): # Drop if all values became NA (was likely useless)
                 del df['اداره']
                 st.info("ستون 'اداره' فقط شامل مقادیر نامعتبر بود و حذف شد.", icon="ℹ️")
        if 'مساحت' in df.columns:
            df['مساحت'] = pd.to_numeric(df['مساحت'], errors='coerce')
        if 'سن' in df.columns:
             # Handle non-numeric age like 'R2' -> NaN -> 0
             df['سن'] = pd.to_numeric(df['سن'], errors='coerce').fillna(0).astype(int)

        # Final check for essential columns after loading
        if 'مزرعه' not in df.columns or 'روز' not in df.columns or 'centroid_lon' not in df.columns or 'centroid_lat' not in df.columns:
             st.error("خطای داخلی: ستون‌های ضروری ('مزرعه', 'روز', 'centroid_lon', 'centroid_lat') پس از پردازش ایجاد نشدند.")
             st.stop()

        st.success(f"✅ داده‌های {len(df)} مزرعه با موفقیت بارگذاری شد.")
        return df
    except json.JSONDecodeError as e:
        st.error(f"❌ خطا در خواندن فایل GeoJSON در خط {e.lineno} ستون {e.colno}: {e.msg}")
        st.stop()
    except Exception as e:
        st.error(f"❌ خطا در پردازش GeoJSON: {e}")
        st.error(traceback.format_exc())
        st.stop()


# --- HTML Helper Functions (Unchanged) ---
def modern_metric_card(label, value, icon="fa-info-circle", color="#fd7e14"): # Default icon color Orange
    value_display = value if pd.notna(value) and value != "" else "N/A"
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
    status_text_str = str(status_text) # Convert to string first
    status_text_lower = status_text_str.lower()
    css_class = "status-unknown"
    if pd.isna(status_text) or "بدون داده" in status_text_lower or "n/a" in status_text_lower or status_text_str == "nan": css_class = "status-nodata"
    elif "بهبود" in status_text_lower or "مثبت" in status_text_lower: css_class = "status-positive"
    elif "تنش" in status_text_lower or "کاهش" in status_text_lower or "بدتر" in status_text_lower or "خطا" in status_text_lower or "منفی" in status_text_lower : css_class = "status-negative"
    elif "ثابت" in status_text_lower: css_class = "status-neutral"
    elif "جدید" in status_text_lower: css_class = "status-new"
    elif "حذف" in status_text_lower: css_class = "status-removed"
    return f'<span class="status-badge {css_class}">{status_text_str}</span>'

# Function to generate a randomish color based on a string (for variety/age maps)
def generate_color(input_string):
    random.seed(input_string) # Seed random number generator
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

# --- Initialize GEE and Load Data ---
if initialize_gee():
    farm_data_df = load_farm_data_from_geojson(FARM_GEOJSON_PATH)
else:
    st.error("اتصال به GEE ناموفق بود. برنامه متوقف می‌شود.")
    st.stop()

# Add a check here AFTER loading to ensure farm_data_df is valid
if 'farm_data_df' not in locals() or not isinstance(farm_data_df, pd.DataFrame) or farm_data_df.empty:
    st.error("بارگذاری داده‌های مزارع ناموفق بود یا داده‌ای یافت نشد. برنامه متوقف می‌شود.")
    st.stop()

# ==============================================================================
# Sidebar Filters (Enhanced with Expander and الاداره Filter)
# ==============================================================================
st.sidebar.header("🔧 تنظیمات و فیلترها")

with st.sidebar.expander("📅 انتخاب روز و اداره", expanded=True):
    # Day Selection
    if 'روز' not in farm_data_df.columns:
        st.sidebar.error("ستون 'روز' در داده‌های بارگذاری شده وجود ندارد. فیلتر روز غیرفعال است.")
        st.stop()
    available_days = sorted(farm_data_df['روز'].dropna().unique())
    if not available_days:
        st.sidebar.error("هیچ مقدار معتبری در ستون 'روز' یافت نشد.")
        st.stop()
    selected_day = st.selectbox(
        "روز هفته:", options=available_days, index=0
    )

    # Filter by Day first
    daily_farms_df = farm_data_df[farm_data_df['روز'] == selected_day].copy()
    if daily_farms_df.empty:
        st.warning(f"هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
        st.stop() # Stop if no farms for the selected day

    # الاداره Selection (Department/Unit) - Check if 'اداره' column exists
    if 'اداره' in daily_farms_df.columns and daily_farms_df['اداره'].notna().any():
        available_edareh = sorted(daily_farms_df['اداره'].dropna().unique())
        edareh_options = ["همه ادارات"] + available_edareh
        selected_edareh = st.selectbox(
            "اداره:", options=edareh_options, index=0,
            help="فیلتر مزارع بر اساس اداره مربوطه (در صورت وجود داده)."
        )
    else:
        # st.sidebar.info("ستون 'اداره' در داده‌ها موجود نیست یا خالی است. فیلتر اداره غیرفعال است.", icon="ℹ️")
        selected_edareh = "همه ادارات" # Default if column is missing or empty

    # Apply الاداره filter
    if selected_edareh == "همه ادارات":
        filtered_farms_df = daily_farms_df
    elif 'اداره' in daily_farms_df.columns: # Ensure column exists before filtering
        filtered_farms_df = daily_farms_df[daily_farms_df['اداره'] == selected_edareh]
        if filtered_farms_df.empty:
            st.warning(f"هیچ مزرعه‌ای برای اداره '{selected_edareh}' در روز '{selected_day}' یافت نشد.")
            # Don't stop here, maybe user wants to see the empty state
            # st.stop()
    else:
        # Should not happen if selected_edareh != "همه ادارات" but added as safety
        filtered_farms_df = daily_farms_df

    # --- Add a final check ---
    if filtered_farms_df.empty and selected_edareh != "همه ادارات":
         st.warning(f"هیچ مزرعه‌ای با فیلترهای انتخاب شده (روز: {selected_day}, اداره: {selected_edareh}) یافت نشد.")
         # Consider stopping or allowing continuation with empty data
         # st.stop()
    elif filtered_farms_df.empty:
         st.warning(f"هیچ مزرعه‌ای با فیلتر روز: {selected_day} یافت نشد.")
         # st.stop()


with st.sidebar.expander("🌾 انتخاب مزرعه و شاخص", expanded=True):
    # Farm Selection (based on filtered data)
    if filtered_farms_df.empty:
        st.markdown("`مزرعه‌ای برای انتخاب وجود ندارد.`")
        selected_farm_name = "همه مزارع" # Default needed even if empty
    else:
        available_farms = sorted(filtered_farms_df['مزرعه'].unique())
        farm_options = ["همه مزارع"] + available_farms
        default_farm_index = 0 # Always default to 'همه مزارع'
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

# --- Date Range Calculation ---
today = datetime.date.today()
# Map Persian day names to Python's weekday() (Monday=0, Sunday=6)
persian_to_weekday = {"شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1, "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4}
try:
    target_weekday = persian_to_weekday[selected_day] # Get target weekday (0-6)
    today_weekday = today.weekday() # Get today's weekday (0-6)

    # Calculate days ago for the *most recent* occurrence of target_weekday
    days_ago = (today_weekday - target_weekday + 7) % 7
    if days_ago == 0: # If today is the target day
         end_date_current = today
    else:
         end_date_current = today - datetime.timedelta(days=days_ago)

    # Define the 7-day window ending on end_date_current
    start_date_current = end_date_current - datetime.timedelta(days=6)

    # Define the previous 7-day window
    end_date_previous = start_date_current - datetime.timedelta(days=1)
    start_date_previous = end_date_previous - datetime.timedelta(days=6)

    # Format dates as strings
    start_date_current_str, end_date_current_str = start_date_current.strftime('%Y-%m-%d'), end_date_current.strftime('%Y-%m-%d')
    start_date_previous_str, end_date_previous_str = start_date_previous.strftime('%Y-%m-%d'), end_date_previous.strftime('%Y-%m-%d')

    st.sidebar.markdown("---")
    st.sidebar.caption(f"بازه فعلی: {start_date_current_str} تا {end_date_current_str}")
    st.sidebar.caption(f"بازه قبلی: {start_date_previous_str} تا {end_date_previous_str}")
    st.sidebar.markdown("---")
except KeyError:
    st.sidebar.error(f"روز هفته '{selected_day}' در مپینگ روزهای هفته یافت نشد.")
    st.stop()
except Exception as e:
    st.sidebar.error(f"خطا در محاسبه بازه زمانی: {e}")
    st.stop()


# ==============================================================================
# Google Earth Engine Functions (Mostly Unchanged)
# ==============================================================================
def maskS2clouds(image):
    """Masks clouds and shadows in Sentinel-2 SR images using QA60 and SCL bands."""
    qa = image.select('QA60')
    # Bits 10 and 11 are clouds and cirrus, respectively.
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    # Get Scene Classification Layer (SCL)
    scl = image.select('SCL')

    # Both flags should be zero (clear) based on QA60
    clear_mask_qa = qa.bitwiseAnd(cloudBitMask).eq(0).And(
        qa.bitwiseAnd(cirrusBitMask).eq(0))

    # SCL values for good data (vegetation, bare soils, water, snow/ice)
    # Values: 4 (Vegetation), 5 (Bare Soils), 6 (Water), 11 (Snow/Ice), 7 (Unclassified - sometimes ok)
    # Excluding: 1 (Saturated/Defective), 2 (Dark Area Pixels), 3 (Cloud Shadows),
    #            8 (Cloud Medium Probability), 9 (Cloud High Probability), 10 (Cirrus)
    good_quality_scl = scl.remap([4, 5, 6, 7, 11], [1, 1, 1, 1, 1], 0) # Remap good values to 1, others to 0

    # Combine masks - both QA and SCL should indicate clear conditions
    combined_mask = clear_mask_qa.And(good_quality_scl)

    # Scale optical bands to reflectance values (0-1) and apply mask
    opticalBands = image.select('B.*').multiply(0.0001)

    return image.addBands(opticalBands, None, True).updateMask(combined_mask)


def add_indices(image):
    """Calculates and adds common spectral indices to an image."""
    # Ensure bands exist before calculating indices to avoid errors
    # Add dummy bands with value 0 if they don't exist (or handle differently)
    image = image.addBands(ee.Image(0).rename('B8'), overwrite=False) # NIR
    image = image.addBands(ee.Image(0).rename('B4'), overwrite=False) # Red
    image = image.addBands(ee.Image(0).rename('B2'), overwrite=False) # Blue
    image = image.addBands(ee.Image(0).rename('B11'),overwrite=False) # SWIR1
    image = image.addBands(ee.Image(0.0001).rename('B3'),overwrite=False) # Green (add small constant to avoid division by zero)


    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    # EVI calculation requires Blue band (B2)
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)', {
            'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2')
        }).rename('EVI')
    # NDMI calculation requires SWIR1 band (B11)
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    # SAVI calculation
    savi = image.expression(
        '((NIR - RED) / (NIR + RED + L)) * (1 + L)', {
            'NIR': image.select('B8'), 'RED': image.select('B4'), 'L': 0.5 # L is the soil adjustment factor
        }).rename('SAVI')
    # MSI calculation requires SWIR1 (B11) and NIR (B8)
    msi = image.expression(
        'SWIR1 / NIR', { # Avoid division by zero? GEE might handle it. Add small constant if needed.
            'SWIR1': image.select('B11'), 'NIR': image.select('B8').max(ee.Image(0.0001)) # Add small constant to NIR
        }).rename('MSI')
    # LAI - Simple estimation based on NDVI, can be improved with more complex models
    # Clamp LAI to be non-negative
    lai = ndvi.multiply(3.5).max(0).rename('LAI')
     # CVI - Chlorophyll Vegetation Index requires Green (B3), Red (B4), NIR (B8)
    # Ensure Green band has a minimum value > 0 to avoid division by zero
    green_safe = image.select('B3').max(ee.Image(0.0001))
    cvi = image.expression(
        '(NIR / GREEN_SAFE) * (RED / GREEN_SAFE)', {
            'NIR': image.select('B8'), 'GREEN_SAFE': green_safe, 'RED': image.select('B4')
        }).rename('CVI')

    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi, savi])

# Function to get a single processed image (median) for a given geometry and date range
@st.cache_data(show_spinner="پردازش تصویر ماهواره‌ای...", persist=True)
def get_processed_image(_geometry, start_date, end_date, index_name):
    """Gets the median GEE image for a given index, dates, and geometry."""
    try:
        if _geometry is None:
            return None, "منطقه جغرافیایی (Geometry) نامعتبر است."

        s2_sr_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(_geometry) \
            .filterDate(start_date, end_date) \
            .map(maskS2clouds) # Apply cloud masking first

        # Check image count after masking
        count = s2_sr_col.size().getInfo()
        if count == 0:
            return None, f"تصویری بدون ابر در بازه ({start_date} تا {end_date}) یافت نشد."

        # Add indices to the cloud-masked collection
        indexed_col = s2_sr_col.map(add_indices)

        # Select the desired index and compute the median
        median_image = indexed_col.median().select(index_name) # Select the specific index

        # --- Optional: Check if the resulting image has valid data in the region ---
        # This adds an extra GEE call but can prevent adding empty layers
        try:
            # Reduce the region to get a sample value (using firstNonNull)
            test_val = median_image.reduceRegion(
                reducer=ee.Reducer.firstNonNull(),
                geometry=_geometry.centroid(maxError=1) if _geometry else ee.Geometry.Point([INITIAL_LON, INITIAL_LAT]), # Use centroid or default point
                scale=30, # Use a slightly coarser scale for check
                maxPixels=1e6
            ).get(index_name).getInfo()

            if test_val is None:
                return None, f"داده معتبر برای شاخص '{index_name}' در مرکز منطقه یافت نشد (مقدار Null)."
        except ee.EEException as ee_err:
             # Handle cases where reduceRegion might fail (e.g., complex geometry)
             # Don't stop the process, just warn
             st.warning(f"اخطار در بررسی اعتبار داده '{index_name}': {ee_err.args[0] if ee_err.args else str(ee_err)}. ممکن است لایه خالی باشد.")
        except Exception as e:
             st.warning(f"خطای ناشناخته در بررسی اعتبار داده '{index_name}': {e}")

        # If the checks pass (or warnings occurred), return the image
        return median_image, None

    except ee.EEException as e:
        # Detailed GEE error
        error_message = f"خطای GEE در پردازش تصویر: {e.args[0] if e.args else str(e)}"
        print(error_message) # Log for debugging
        return None, error_message
    except Exception as e:
        # Other errors
        error_message = f"خطای ناشناخته در get_processed_image: {e}"
        print(error_message)
        print(traceback.format_exc()) # Log traceback
        return None, error_message


@st.cache_data(show_spinner="دریافت سری زمانی...", persist=True)
def get_index_time_series(_point_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    """Gets GEE time series for an index at a specific point."""
    try:
        if not isinstance(_point_geom, ee.Geometry):
             return pd.DataFrame(columns=['date', index_name]), "ورودی _point_geom باید از نوع ee.Geometry باشد."

        s2_sr_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(_point_geom) \
            .filterDate(start_date, end_date) \
            .map(maskS2clouds) \
            .map(add_indices) \
            .select(index_name) # Select the index

        def extract_value(image):
            # Use reduceRegion with firstNonNull for potentially masked pixels
            value = image.reduceRegion(
                reducer=ee.Reducer.firstNonNull(), # More robust than .mean() for single point if masked
                geometry=_point_geom,
                scale=10 # Scale of Sentinel-2 bands used
            ).get(index_name)

            # Return a feature with date and value, only if value is not null
            return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value}) \
                     .set('hasValue', value) # Set a property to filter nulls server-side

        # Filter out images where the value couldn't be extracted (null)
        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.neq('hasValue', None))

        # Get the results as a list of features
        ts_info = ts_features.getInfo()['features']

        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), f"داده‌ای برای سری زمانی {index_name} در بازه ({start_date} تا {end_date}) یافت نشد."

        # Convert to Pandas DataFrame
        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_info]
        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])

        # Handle potential duplicate dates (e.g., multiple orbits same day) by averaging
        ts_df = ts_df.groupby('date').mean().reset_index()

        ts_df = ts_df.sort_values('date').set_index('date')
        return ts_df, None

    except ee.EEException as e:
        error_msg = f"خطای GEE در دریافت سری زمانی: {e.args[0] if e.args else str(e)}"
        print(error_msg)
        return pd.DataFrame(columns=['date', index_name]), error_msg
    except Exception as e:
        error_msg = f"خطای ناشناخته در get_index_time_series: {e}"
        print(error_msg)
        print(traceback.format_exc())
        return pd.DataFrame(columns=['date', index_name]), error_msg

# --- NEW Helper Function: Calculate Weekly Indices (Needed for Ranking Table/Map) ---
@st.cache_data(show_spinner="محاسبه شاخص‌های هفتگی برای مزارع...", persist=True)
def calculate_weekly_indices(farms_df_subset, index_name, start_curr, end_curr, start_prev, end_prev):
    """Calculates current and previous week's mean index value for multiple farms."""
    results = []
    errors = []

    def get_mean_value_for_farm(geometry, start_date, end_date):
        """Helper to get mean index value for one farm and period."""
        try:
            s2_sr_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterBounds(geometry) \
                .filterDate(start_date, end_date) \
                .map(maskS2clouds)

            count = s2_sr_col.size().getInfo()
            if count == 0:
                return None, f"بی‌تصویر ({start_date}-{end_date})"

            indexed_col = s2_sr_col.map(add_indices)
            median_image = indexed_col.median().select(index_name)

            mean_val = median_image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=10, # Use appropriate scale
                maxPixels=1e9
            ).get(index_name).getInfo()

            return mean_val, None # Return value can be None if region has no valid data
        except ee.EEException as e:
            return None, f"خطای GEE ({start_date}-{end_date}): {e.args[0] if e.args else str(e)}"
        except Exception as e:
            return None, f"خطای ناشناخته ({start_date}-{end_date}): {e}"

    # Iterate through the farms in the provided subset DataFrame
    required_cols = ['مزرعه', 'centroid_lon', 'centroid_lat']
    if not all(col in farms_df_subset.columns for col in required_cols):
         missing = [col for col in required_cols if col not in farms_df_subset.columns]
         st.error(f"خطای داخلی: ستون‌های مورد نیاز ({', '.join(missing)}) در DataFrame ورودی calculate_weekly_indices وجود ندارد.")
         return pd.DataFrame(), [f"ستون‌های مورد نیاز ({', '.join(missing)}) یافت نشد."]


    progress_bar = st.progress(0)
    total_farms = len(farms_df_subset)

    for i, farm in farms_df_subset.iterrows():
        farm_name = farm['مزرعه']
        lon, lat = farm['centroid_lon'], farm['centroid_lat']
        point_geom = ee.Geometry.Point([lon, lat]) # Use centroid point

        # Get current period value
        current_val, err_curr = get_mean_value_for_farm(point_geom, start_curr, end_curr)
        if err_curr:
            errors.append(f"{farm_name} (جاری): {err_curr}")

        # Get previous period value
        previous_val, err_prev = get_mean_value_for_farm(point_geom, start_prev, end_prev)
        if err_prev:
            errors.append(f"{farm_name} (قبلی): {err_prev}")

        # Calculate change
        change = None
        if isinstance(current_val, (int, float)) and isinstance(previous_val, (int, float)):
             # Avoid division by zero if previous_val is very small or zero
             if abs(previous_val) > 1e-9:
                  change = ((current_val - previous_val) / abs(previous_val)) * 100
             elif current_val == previous_val: # Both zero or very small
                  change = 0.0
             # else: change remains None (cannot calculate percentage change from zero)

        farm_result = {
            'مزرعه': farm_name,
            f'{index_name} (هفته جاری)': current_val,
            f'{index_name} (هفته قبل)': previous_val,
            'تغییر': change # Percentage change or None
        }
        # Add other identifying columns from the input df if needed
        for col in ['گروه', 'اداره', 'سن', 'واریته', 'centroid_lat', 'centroid_lon']:
            if col in farm.index:
                farm_result[col] = farm[col]

        results.append(farm_result)
        progress_bar.progress((i + 1) / total_farms)

    progress_bar.empty() # Remove progress bar
    return pd.DataFrame(results), errors


# --- NEW Helper Function: Determine Status (Needed for Ranking Table/Map) ---
def determine_status(row, index_name, change_threshold=5.0):
    """Determines a descriptive status based on current, previous index values and change."""
    current_col = f'{index_name} (هفته جاری)'
    prev_col = f'{index_name} (هفته قبل)'
    change_col = 'تغییر' # Assumes 'تغییر' is percentage change

    if current_col not in row or prev_col not in row or change_col not in row:
        return "خطا در ستون" # Missing necessary columns

    current_val = row[current_col]
    prev_val = row[prev_col]
    change_pct = row[change_col]

    is_stress_index = index_name in ['MSI'] # Indices where higher value means more stress

    # Handle cases with missing data
    if pd.isna(current_val) and pd.isna(prev_val): return "بدون داده"
    if pd.isna(current_val) and pd.notna(prev_val): return "حذف شده؟" # Data loss
    if pd.notna(current_val) and pd.isna(prev_val): return "جدید"     # New data

    # Handle cases where change couldn't be calculated (e.g., division by zero)
    if pd.isna(change_pct):
         if current_val == prev_val: change_pct = 0.0 # Treat as no change if values are equal
         else: return "بدون تغییر معتبر" # Cannot determine status reliably

    # Determine status based on change percentage
    if abs(change_pct) < change_threshold:
        return "ثابت"
    elif change_pct > 0: # Positive change
        if is_stress_index: return "تنش / بدتر شدن" # Increase in stress index is bad
        else: return "رشد مثبت / بهبود" # Increase in vegetation index is good
    elif change_pct < 0: # Negative change
        if is_stress_index: return "بهبود / کاهش تنش" # Decrease in stress index is good
        else: return "تنش / کاهش"       # Decrease in vegetation index is bad
    else:
        return "Unknown" # Should not happen if logic above is correct

# ==============================================================================
# Needs Analysis Function (using GEE) - Modified to reuse index calculation logic
# ==============================================================================
@st.cache_data(show_spinner="محاسبه شاخص‌های نیازسنجی...", persist=True)
def get_farm_needs_data(_point_geom, start_curr, end_curr, start_prev, end_prev):
    """Gets key indices (NDVI, NDMI, EVI, SAVI) for current and previous periods for needs analysis."""
    results = {f'{idx}_{p}': None for idx in ['NDVI', 'NDMI', 'EVI', 'SAVI'] for p in ['curr', 'prev']}
    results['error'] = None
    indices_to_get = ['NDVI', 'NDMI', 'EVI', 'SAVI']

    def get_mean_values(start, end):
        """Helper to get mean index values for a specific period."""
        vals = {index: None for index in indices_to_get}
        error_msg = None
        try:
            s2_sr_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterBounds(_point_geom) \
                .filterDate(start, end) \
                .map(maskS2clouds)

            count = s2_sr_col.size().getInfo()
            if count == 0:
                return vals, f"بی‌تصویر ({start}-{end})"

            # Add all indices needed
            indexed_col = s2_sr_col.map(add_indices)

            # Compute median image containing all needed indices
            median_image = indexed_col.median().select(indices_to_get)

            # Reduce region to get mean values for all indices at once
            mean_dict = median_image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=_point_geom,
                scale=10,
                maxPixels=1e9
            ).getInfo() # Get the dictionary of results

            if mean_dict:
                for index in indices_to_get:
                    vals[index] = mean_dict.get(index) # Returns None if index not found or null
            return vals, None
        except ee.EEException as e:
            error_msg = f"خطای GEE ({start}-{end}): {e.args[0] if e.args else str(e)}"
            print(error_msg)
            return vals, error_msg
        except Exception as e:
            error_msg = f"خطای ناشناخته ({start}-{end}): {e}"
            print(error_msg)
            print(traceback.format_exc())
            return vals, error_msg

    # Get current period values
    curr_vals, err_curr = get_mean_values(start_curr, end_curr)
    if err_curr:
        results['error'] = err_curr
    for idx in indices_to_get:
        results[f'{idx}_curr'] = curr_vals.get(idx)

    # Get previous period values
    prev_vals, err_prev = get_mean_values(start_prev, end_prev)
    if err_prev:
        # Append previous error to current error if exists
        results['error'] = f"{results.get('error', '')} | {err_prev}" if results.get('error') else err_prev
    for idx in indices_to_get:
        results[f'{idx}_prev'] = prev_vals.get(idx)

    return results


# ==============================================================================
# Gemini AI Helper Functions (Enhanced)
# ==============================================================================
@st.cache_resource
def configure_gemini():
    try:
        # --- WARNING: Hardcoding API keys is insecure! Use Streamlit secrets in production. ---
        # --- Replace with your actual Gemini API Key ---
        api_key = "YOUR_GEMINI_API_KEY" # <-- PASTE YOUR KEY HERE
        # --- End of Warning ---

        # Basic check if the key looks like a placeholder
        if not api_key or api_key == "YOUR_GEMINI_API_KEY":
            st.warning("⚠️ کلید API جمینای وارد نشده یا هنوز مقدار پیش‌فرض است. تحلیل هوش مصنوعی غیرفعال خواهد بود.", icon="🤖")
            return None

        genai.configure(api_key=api_key)
        # Choose a model - 'gemini-1.5-flash' is often fast and capable
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("Gemini Configured Successfully.")
        # Perform a simple test call (optional, but good for verification)
        try:
            _ = model.generate_content("Test")
            print("Gemini test call successful.")
        except Exception as test_e:
            st.error(f"❌ خطا در تست Gemini API پس از تنظیم: {test_e}. لطفاً کلید API و دسترسی شبکه را بررسی کنید.")
            return None
        return model
    except Exception as e:
        st.error(f"❌ خطا در تنظیم Gemini API: {e}")
        st.error(traceback.format_exc())
        return None

@st.cache_data(show_spinner="دریافت تحلیل نیازسنجی...", persist=True)
def get_ai_needs_analysis(_model, farm_name, index_data, recommendations):
    if _model is None:
        return "سرویس هوش مصنوعی پیکربندی نشده یا در دسترس نیست."
    # Helper to format numbers, handling None
    def fmt(val):
        return f"{val:.3f}" if isinstance(val, (int, float)) and pd.notna(val) else "N/A"

    # Prepare data string, explicitly handling potential None values
    data_lines = []
    for idx in ['NDVI', 'NDMI', 'EVI', 'SAVI']:
        curr_val = index_data.get(f'{idx}_curr')
        prev_val = index_data.get(f'{idx}_prev')
        data_lines.append(f"{idx}: {fmt(curr_val)} (هفته قبل: {fmt(prev_val)})")
    data_str = "\n".join(data_lines)

    # Prepare recommendations string
    rec_str = ', '.join(recommendations) if recommendations else 'نیاز خاصی شناسایی نشد.'

    prompt = f"""
شما یک متخصص کشاورزی نیشکر هستید. لطفاً وضعیت مزرعه با نام '{farm_name}' را بر اساس داده‌های شاخص‌های ماهواره‌ای و توصیه‌های اولیه زیر، در 3 تا 5 جمله کوتاه و کاربردی به زبان فارسی تحلیل کنید.

تمرکز اصلی تحلیل باید بر **نیازهای احتمالی آبیاری و تغذیه** باشد. لطفاً دلایل پیشنهادی خود را بر اساس تغییرات شاخص‌ها (مانند کاهش NDMI برای نیاز آبیاری یا افت قابل توجه NDVI برای مشکلات تغذیه/تنش) به طور خلاصه توضیح دهید.

**داده‌های شاخص (مقدار فعلی / مقدار هفته قبل):**
{data_str}

**توصیه‌های اولیه سیستم:**
{rec_str}

**تحلیل شما (3-5 جمله):**
"""
    try:
        # Adding safety configurations (optional but recommended)
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        response = _model.generate_content(prompt, safety_settings=safety_settings)

        # Accessing response text safely
        if hasattr(response, 'text'):
            return response.text
        elif hasattr(response, 'parts') and response.parts:
            return response.parts[0].text
        else:
            # Handle unexpected response structure or blocked content
            try:
                 # Attempt to access prompt feedback if available
                 feedback = response.prompt_feedback
                 block_reason = feedback.block_reason if feedback else 'نامشخص'
                 return f"پاسخی دریافت نشد. ممکن است محتوا مسدود شده باشد (دلیل: {block_reason})."
            except Exception:
                 return "ساختار پاسخ دریافتی از Gemini نامعتبر است."

    except Exception as e:
        st.error(f"خطا در ارتباط با Gemini API برای تحلیل نیازسنجی: {e}")
        return f"خطا در تحلیل نیازسنجی: {str(e)}"


# NEW Gemini function for map summary
@st.cache_data(show_spinner="دریافت خلاصه وضعیت مزارع...", persist=True)
def get_ai_map_summary(_model, status_counts, edareh_filter, day_filter):
    """Generates AI summary for the classified map."""
    if _model is None:
        return "سرویس هوش مصنوعی پیکربندی نشده یا در دسترس نیست."

    if not status_counts or sum(status_counts.values()) == 0:
        return "داده‌ای برای خلاصه‌سازی وضعیت مزارع وجود ندارد."

    total_farms = sum(status_counts.values())
    status_lines = []
    # Sort status counts for consistent output (optional)
    sorted_statuses = sorted(status_counts.items(), key=lambda item: item[1], reverse=True)

    for status, count in sorted_statuses:
        if count > 0:
            percent = (count / total_farms) * 100
            status_lines.append(f"- {status}: {count} مزرعه ({percent:.1f}٪)")

    status_summary = "\n".join(status_lines)
    edareh_context = f"برای اداره '{edareh_filter}'" if edareh_filter != "همه ادارات" else "برای همه ادارات"

    prompt = f"""
شما یک تحلیلگر داده‌های کشاورزی هستید. لطفاً یک خلاصه کوتاه و کاربردی (2 تا 4 جمله) به زبان فارسی از وضعیت کلی مزارع نیشکر ارائه دهید. این خلاصه بر اساس دسته‌بندی وضعیت مزارع در مقایسه با هفته گذشته تهیه شده است.

**زمینه تحلیل:**
- **روز:** {day_filter}
- **فیلتر اداره:** {edareh_context}
- **تعداد کل مزارع تحلیل شده:** {total_farms}

**توزیع وضعیت مزارع:**
{status_summary}

**وظیفه:**
خلاصه‌ای مدیریتی ارائه دهید که نکات کلیدی را برجسته کند. به موارد مهم مانند:
- درصد قابل توجه مزارع در وضعیت "تنش/کاهش" یا وضعیت‌های نامطلوب دیگر.
- درصد مزارع با وضعیت "بهبود".
- هرگونه روند یا الگوی قابل توجه دیگر در توزیع وضعیت‌ها.

**خلاصه وضعیت کلی (2-4 جمله):**
"""
    try:
        # Adding safety configurations
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        response = _model.generate_content(prompt, safety_settings=safety_settings)

        # Safe access to response text
        if hasattr(response, 'text'):
            return response.text
        elif hasattr(response, 'parts') and response.parts:
            return response.parts[0].text
        else:
            try:
                 feedback = response.prompt_feedback
                 block_reason = feedback.block_reason if feedback else 'نامشخص'
                 return f"پاسخی برای خلاصه نقشه دریافت نشد. ممکن است محتوا مسدود شده باشد (دلیل: {block_reason})."
            except Exception:
                 return "ساختار پاسخ دریافتی از Gemini برای خلاصه نقشه نامعتبر است."

    except Exception as e:
        st.warning(f"⚠️ خطا در ارتباط با Gemini API برای خلاصه نقشه: {e}")
        return f"خطا در دریافت خلاصه وضعیت: {str(e)}"


# ==============================================================================
# Main Application Layout (Tabs)
# ==============================================================================
gemini_model = configure_gemini() # Configure Gemini once
tab1, tab2 = st.tabs(["📊 پایش مزارع", "💧 نیازسنجی کود و آبیاری"])

with tab1:
    # ==========================================================================
    # Main Panel Display (Monitoring)
    # ==========================================================================
    st.subheader(f"🗓️ وضعیت مزارع در روز: {selected_day}")
    if selected_edareh != "همه ادارات":
        st.markdown(f"##### اداره: {selected_edareh}")
    elif 'اداره' not in filtered_farms_df.columns and len(farm_data_df['اداره'].unique()) > 1:
        st.info("فیلتر 'اداره' به دلیل عدم وجود داده در دسترس نیست.", icon="ℹ️")


    selected_farm_details = None
    selected_farm_geom = None # Will be ee.Geometry.Point or ee.Geometry.Rectangle
    map_center_lat = INITIAL_LAT
    map_center_lon = INITIAL_LON
    map_zoom = INITIAL_ZOOM

    # --- Handle case where filtered_farms_df might be empty after filtering ---
    if filtered_farms_df.empty:
         st.warning("هیچ مزرعه‌ای برای نمایش با فیلترهای انتخابی یافت نشد.")
         # Set a default geometry to avoid errors later
         selected_farm_geom = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT])
         # Stop execution in this tab might be desired, or show empty map
         # st.stop() # Uncomment if you want to stop if no farms
    else:
        # --- Setup Geometry and Initial Info ---
        if selected_farm_name == "همه مزارع":
            num_farms = len(filtered_farms_df)
            avg_area = filtered_farms_df['مساحت'].mean() if 'مساحت' in filtered_farms_df.columns and filtered_farms_df['مساحت'].notna().any() else None
            avg_age = filtered_farms_df['سن'].mean() if 'سن' in filtered_farms_df.columns and filtered_farms_df['سن'].notna().any() else None
            # Calculate common variety carefully, handling potential NAs
            common_variety = "متنوع"
            if 'واریته' in filtered_farms_df.columns and filtered_farms_df['واریته'].notna().any():
                mode_result = filtered_farms_df['واریته'].dropna().mode()
                if not mode_result.empty:
                    common_variety = mode_result[0]

            # Display Summary Cards
            summary_cols = st.columns(4)
            with summary_cols[0]:
                 st.markdown(modern_metric_card("تعداد مزارع", num_farms, icon="fa-layer-group"), unsafe_allow_html=True)
            with summary_cols[1]:
                 st.markdown(modern_metric_card("میانگین مساحت (ha)", avg_area, icon="fa-chart-area"), unsafe_allow_html=True) # Added unit
            with summary_cols[2]:
                 st.markdown(modern_metric_card("میانگین سن", avg_age, icon="fa-calendar-days"), unsafe_allow_html=True)
            with summary_cols[3]:
                 st.markdown(modern_metric_card("واریته غالب", common_variety, icon="fa-star"), unsafe_allow_html=True)

            # Define the bounding box for "همه مزارع" view
            min_lon, min_lat = filtered_farms_df['centroid_lon'].min(), filtered_farms_df['centroid_lat'].min()
            max_lon, max_lat = filtered_farms_df['centroid_lon'].max(), filtered_farms_df['centroid_lat'].max()
            # Add a small buffer to the bounds
            buffer = 0.005 # Adjust buffer as needed
            try:
                selected_farm_geom = ee.Geometry.Rectangle(
                    [min_lon - buffer, min_lat - buffer, max_lon + buffer, max_lat + buffer]
                )
                map_center_lat = (min_lat + max_lat) / 2
                map_center_lon = (min_lon + max_lon) / 2
                # Adjust zoom based on number of farms or extent
                map_zoom = 11 if num_farms > 5 else 12 # Zoom out more for many farms
            except Exception as e_geom:
                 st.error(f"خطا در ایجاد геометрии برای 'همه مزارع': {e_geom}")
                 selected_farm_geom = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT]) # Fallback


        else: # A specific farm is selected
            selection = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name]
            if not selection.empty:
                selected_farm_details = selection.iloc[0]
                lat = selected_farm_details['centroid_lat']
                lon = selected_farm_details['centroid_lon']
                # Use the Point geometry for single farm analysis
                try:
                    selected_farm_geom = ee.Geometry.Point([lon, lat])
                    map_center_lat, map_center_lon, map_zoom = lat, lon, 14 # Zoom in for single farm

                    # Display Farm Details
                    edareh_val = selected_farm_details.get('اداره', 'N/A') if 'اداره' in selected_farm_details else 'N/A'
                    st.write(f"**جزئیات مزرعه: {selected_farm_name}** (اداره: {edareh_val})")
                    details_cols = st.columns(4)
                    details_cols[0].markdown(modern_metric_card("مساحت (ha)", selected_farm_details.get('مساحت'), icon="fa-vector-square"), unsafe_allow_html=True)
                    details_cols[1].markdown(modern_metric_card("واریته", selected_farm_details.get('واریته', 'N/A'), icon="fa-seedling"), unsafe_allow_html=True)
                    details_cols[2].markdown(modern_metric_card("گروه", selected_farm_details.get('گروه', 'N/A'), icon="fa-users"), unsafe_allow_html=True)
                    details_cols[3].markdown(modern_metric_card("سن", selected_farm_details.get('سن'), icon="fa-hourglass-half"), unsafe_allow_html=True)
                except Exception as e_geom:
                    st.error(f"خطا در ایجاد геометрии برای مزرعه '{selected_farm_name}': {e_geom}")
                    selected_farm_geom = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT]) # Fallback

            else:
                 st.error(f"مزرعه '{selected_farm_name}' در داده‌های فیلتر شده یافت نشد.")
                 selected_farm_geom = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT]) # Fallback


    # --- Map Display (Enhanced with Layers) ---
    st.markdown("---")
    st.subheader(f"🗺️ نقشه پایش مزارع - شاخص: {index_options[selected_index]}")

    # Define Visualization Parameters (Consistent palettes)
    vis_params = {
        'NDVI': {'min': 0.0, 'max': 0.9, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']},
        'EVI': {'min': 0.0, 'max': 0.9, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']}, # Same as NDVI
        'NDMI': {'min': -0.5, 'max': 0.8, 'palette': ['#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#f7f7f7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac']}, # Blue is wetter
        'SAVI': {'min': 0.0, 'max': 0.9, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']}, # Same as NDVI
        'LAI': {'min': 0, 'max': 7, 'palette': ['#EFEFEF', '#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']}, # Yellow to brown
        'MSI': {'min': 0, 'max': 3, 'palette': ['#2166ac', '#67a9cf', '#d1e5f0', '#fddbc7', '#ef8a62', '#b2182b'][::-1]}, # Reversed: Blue (low stress) to Red (high stress)
        'CVI': {'min': 0, 'max': 25, 'palette': ['#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']}, # Similar to LAI
    }
    current_vis = vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}) # Default vis


    # Initialize the map
    m = geemap.Map(location=[map_center_lat, map_center_lon], zoom=map_zoom, add_google_map=True)
    m.add_basemap("SATELLITE") # Default to Satellite view

    # Add GEE Layer (Selected Index)
    gee_image_current, error_msg_current = None, None
    if selected_farm_geom: # Check if geometry is valid
        with st.spinner(f"بارگیری تصویر ماهواره‌ای برای {selected_index}..."):
            gee_image_current, error_msg_current = get_processed_image(
                selected_farm_geom, start_date_current_str, end_date_current_str, selected_index
            )
        map_layer_name = f"{index_options[selected_index]} ({end_date_current_str})"
        if gee_image_current:
            try:
                # Clip the layer to the selected geometry for better visualization
                # clipped_image = gee_image_current.clip(selected_farm_geom)
                # m.addLayer(clipped_image, current_vis, map_layer_name)
                # Clipping might hide context, add full layer instead
                m.addLayer(gee_image_current, current_vis, map_layer_name)
                m.add_colorbar(current_vis, label=f"{index_options[selected_index]}", layer_name=map_layer_name)
            except Exception as map_err:
                st.error(f"خطا در افزودن لایه GEE به نقشه: {map_err}")
        elif error_msg_current:
            st.warning(f"عدم نمایش لایه {selected_index}: {error_msg_current}", icon="🛰️")
    else:
         st.warning("محدوده جغرافیایی برای نمایش لایه GEE تعریف نشده است.")


    # --- Calculate Ranking Data for Map Layers ---
    # Use the currently filtered DataFrame (daily, possibly edareh)
    # Select only necessary columns for the calculation function
    cols_for_ranking = ['مزرعه', 'centroid_lon', 'centroid_lat']
    # Add optional columns if they exist, for inclusion in the result
    for col in ['گروه', 'اداره', 'سن', 'واریته']:
         if col in filtered_farms_df.columns:
              cols_for_ranking.append(col)

    # Check if the filtered DataFrame is empty before calculating
    ranking_df_map = pd.DataFrame() # Initialize empty DataFrame
    map_calc_errors = []
    if not filtered_farms_df.empty:
        ranking_df_map, map_calc_errors = calculate_weekly_indices(
            filtered_farms_df[cols_for_ranking], # Pass only needed columns
            selected_index, start_date_current_str, end_date_current_str,
            start_date_previous_str, end_date_previous_str
        )
        if map_calc_errors:
             st.warning(f"خطاهایی در محاسبه شاخص‌های هفتگی برای {len(map_calc_errors)} مورد رخ داد. (جزئیات در جدول رتبه‌بندی)")

        if not ranking_df_map.empty:
            # --- Determine Status ---
            # Define a sensible threshold for significant change (e.g., 5%)
            change_threshold_for_status = 5.0
            ranking_df_map['وضعیت_متن'] = ranking_df_map.apply(
                lambda row: determine_status(row, selected_index, change_threshold_for_status),
                axis=1
            )
            # Merge back details ONLY IF they weren't included by calculate_weekly_indices
            # (The modified calculate_weekly_indices should already include them if present)
            # ranking_df_map = pd.merge(ranking_df_map,
            #                           filtered_farms_df[['مزرعه', 'سن', 'واریته', 'اداره', 'گروه', 'centroid_lat', 'centroid_lon']],
            #                           on='مزرعه', how='left', suffixes=('', '_dup'))
            # ranking_df_map = ranking_df_map.loc[:, ~ranking_df_map.columns.str.endswith('_dup')]
        else:
             st.warning("محاسبه شاخص‌های هفتگی نتیجه‌ای نداشت. لایه‌های طبقه‌بندی نقشه نمایش داده نمی‌شوند.")
             # Use base filtered_farms_df for age/variety if ranking fails, assign default status
             ranking_df_map = filtered_farms_df.copy()
             ranking_df_map['وضعیت_متن'] = 'بدون داده'
    else:
         st.info("داده‌ای برای محاسبه رتبه‌بندی و ایجاد لایه‌های طبقه‌بندی نقشه وجود ندارد.")


    # --- Define Layer Styles ---
    # Status Layer Styles
    status_map_colors = {
        "رشد مثبت / بهبود": ('green', 'fa-arrow-up'),
        "بهبود / کاهش تنش": ('blue', 'fa-arrow-down'), # Blue for less stress/more water
        "ثابت": ('orange', 'fa-equals'),
        "تنش / کاهش": ('red', 'fa-arrow-down'),
        "تنش / بدتر شدن": ('darkred', 'fa-arrow-up'),
        "جدید": ('lightblue', 'fa-star'),
        "حذف شده?": ('gray', 'fa-question'),
        "بدون داده": ('lightgray', 'fa-circle-notch'),
        "خطا در ستون": ('black', 'fa-exclamation-triangle'),
        "بدون تغییر معتبر": ('lightgray', 'fa-minus'),
        "Unknown": ('purple', 'fa-question-circle') # Default/fallback
    }
    # Simplified Legend for Status Map
    status_legend_map = {
        "بهبود": ('#28a745', 'وضعیت بهتر (رشد بیشتر / تنش کمتر)'), # Green
        "ثابت": ('#ffc107', 'وضعیت تقریباً مشابه هفته قبل'),     # Yellow/Orange
        "تنش/کاهش": ('#dc3545', 'وضعیت بدتر (رشد کمتر / تنش بیشتر)'), # Red
        "جدید": ('#17a2b8', 'مزرعه جدید (داده فقط برای این هفته)'), # Cyan
        "نامشخص/خطا": ('#6c757d', 'داده ناکافی، خطا یا تغییر نامعتبر') # Gray
    }
    # Age Layer Styles
    age_bins = [-1, 0, 1, 2, 3, 5, 10, 1000] # Bins: 0, 1, 2, 3, 4-5, 6-10, 10+ (Use -1 for edge)
    age_labels = ['سن 0', 'سن 1', 'سن 2', 'سن 3', 'سن 4-5', 'سن 6-10', 'سن +10']
    age_colors_palette = px.colors.qualitative.Pastel # Color palette
    age_color_map = {label: age_colors_palette[i % len(age_colors_palette)] for i, label in enumerate(age_labels)}
    # Variety Layer: Colors generated dynamically


    # --- Create Feature Groups for Layers ---
    age_groups = {}
    variety_groups = {}
    status_groups = {} # Group by simplified status for cleaner LayerControl

    # Check if ranking_df_map has data and required columns
    if not ranking_df_map.empty and all(c in ranking_df_map.columns for c in ['centroid_lat', 'centroid_lon', 'مزرعه']):
        for idx, farm in ranking_df_map.iterrows():
            lat, lon = farm['centroid_lat'], farm['centroid_lon']
            if pd.isna(lat) or pd.isna(lon): continue # Skip if coords are missing

            # Base Popup HTML (Common for all layers)
            popup_html = f"<div class='folium-popup'>" \
                         f"<b>مزرعه:</b> {farm.get('مزرعه', 'N/A')}<br>"
            if 'اداره' in farm and pd.notna(farm['اداره']): popup_html += f"<b>اداره:</b> {farm['اداره']}<br>"
            if 'گروه' in farm and pd.notna(farm['گروه']): popup_html += f"<b>گروه:</b> {farm['گروه']}<br>"
            if 'سن' in farm and pd.notna(farm['سن']): popup_html += f"<b>سن:</b> {farm['سن']:.0f}<br>"
            if 'واریته' in farm and pd.notna(farm['واریته']): popup_html += f"<b>واریته:</b> {farm['واریته']}<br>"
            popup_html += f"<b>وضعیت:</b> {farm.get('وضعیت_متن', 'N/A')}<br>"
            # Add current/previous index values to popup
            curr_val_pop = farm.get(f'{selected_index} (هفته جاری)')
            prev_val_pop = farm.get(f'{selected_index} (هفته قبل)')
            popup_html += f"<b>{selected_index} فعلی:</b> {curr_val_pop:.3f}" if pd.notna(curr_val_pop) else f"<b>{selected_index} فعلی:</b> N/A"
            popup_html += "<br>"
            popup_html += f"<b>{selected_index} قبلی:</b> {prev_val_pop:.3f}" if pd.notna(prev_val_pop) else f"<b>{selected_index} قبلی:</b> N/A"
            popup_html += "</div>"


            # 1. Age Layer (Optional)
            if 'سن' in farm and pd.notna(farm['سن']):
                try:
                    age_int = int(farm['سن'])
                    bin_label = pd.cut([age_int], bins=age_bins, labels=age_labels, right=False)[0]
                    age_group_name = bin_label
                    if age_group_name not in age_groups:
                         age_groups[age_group_name] = folium.FeatureGroup(name=f"{age_group_name}", show=False) # Initially hidden
                    color = age_color_map.get(age_group_name, '#CCCCCC') # Fallback color
                    folium.CircleMarker(
                        location=[lat, lon], radius=5, popup=folium.Popup(popup_html, max_width=300),
                        tooltip=f"{farm['مزرعه']} (سن {age_int})",
                        color=color, fill=True, fill_color=color, fill_opacity=0.7
                    ).add_to(age_groups[age_group_name])
                except ValueError: pass # Ignore if age cannot be converted to int


            # 2. Variety Layer (Optional)
            if 'واریته' in farm and pd.notna(farm['واریته']):
                 variety_name = str(farm['واریته']).strip()
                 if not variety_name: variety_name = "نامشخص"
                 if variety_name not in variety_groups:
                      variety_groups[variety_name] = folium.FeatureGroup(name=f"واریته: {variety_name}", show=False) # Initially hidden
                 color = generate_color(variety_name) # Generate color based on name
                 folium.CircleMarker(
                     location=[lat, lon], radius=5, popup=folium.Popup(popup_html, max_width=300),
                     tooltip=f"{farm['مزرعه']} ({variety_name})",
                     color=color, fill=True, fill_color=color, fill_opacity=0.7
                 ).add_to(variety_groups[variety_name])


            # 3. Status Layer (Core classified layer)
            status_text_raw = farm.get('وضعیت_متن', 'Unknown')
            # Map raw status to simplified legend category for grouping
            simplified_status = "نامشخص/خطا" # Default
            if "بهبود" in status_text_raw: simplified_status = "بهبود"
            elif "ثابت" in status_text_raw: simplified_status = "ثابت"
            elif any(s in status_text_raw for s in ["تنش", "کاهش", "بدتر"]): simplified_status = "تنش/کاهش"
            elif "جدید" in status_text_raw: simplified_status = "جدید"
            # Keep "نامشخص/خطا" for "بدون داده", "حذف شده?", "خطا", "Unknown", etc.

            if simplified_status not in status_groups:
                 status_groups[simplified_status] = folium.FeatureGroup(name=f"وضعیت: {simplified_status}", show=True) # Show status layer by default

            # Get marker style from raw status text for visual detail
            color_name, icon = status_map_colors.get(status_text_raw, status_map_colors["Unknown"])

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{farm.get('مزرعه', 'N/A')}: {status_text_raw}",
                # Use folium AwesomeIcon for FontAwesome icons
                icon=folium.Icon(color=color_name, icon=icon, prefix='fa')
            ).add_to(status_groups[simplified_status])

        # Add FeatureGroups to the map (add Status groups last so they are on top)
        for group in age_groups.values(): group.add_to(m)
        for group in variety_groups.values(): group.add_to(m)
        for group in status_groups.values(): group.add_to(m)

        # Add Layer Control
        folium.LayerControl(collapsed=False).add_to(m) # Keep it open initially

    else:
        st.info("لایه‌های طبقه‌بندی (سن، واریته، وضعیت) به دلیل عدم وجود داده‌های رتبه‌بندی نمایش داده نمی‌شوند.")


    # Display Map
    try:
        st_folium_output = st_folium(m, width=None, height=600, use_container_width=True, returned_objects=[]) # Increased height
        st.caption("از کنترل لایه‌ها (بالا سمت راست نقشه) برای نمایش/پنهان کردن لایه‌های شاخص، وضعیت، سن و واریته استفاده کنید.")
    except Exception as display_err:
        st.error(f"خطا در نمایش نقشه: {display_err}")
        st.error(traceback.format_exc())


    # --- Classified Status Map Summary ---
    st.markdown("---")
    st.subheader("📊 خلاصه وضعیت طبقه‌بندی شده مزارع")
    if not ranking_df_map.empty and 'وضعیت_متن' in ranking_df_map.columns:
        status_counts_raw = ranking_df_map['وضعیت_متن'].value_counts().to_dict()
        # Map raw statuses to simplified legend categories for reporting
        simplified_status_counts = Counter()
        for status, count in status_counts_raw.items():
             status_key = "نامشخص/خطا" # Default
             if "بهبود" in status: status_key = "بهبود"
             elif "ثابت" in status: status_key = "ثابت"
             elif any(s in status for s in ["تنش", "کاهش", "بدتر"]): status_key = "تنش/کاهش"
             elif "جدید" in status: status_key = "جدید"
             simplified_status_counts[status_key] += count

        if sum(simplified_status_counts.values()) > 0:
            # Display counts using Plotly Bar Chart
            status_df = pd.DataFrame(simplified_status_counts.items(), columns=['وضعیت', 'تعداد']).sort_values('تعداد', ascending=False)
            # Get colors from the legend map
            status_colors = [status_legend_map.get(s, status_legend_map["نامشخص/خطا"])[0] for s in status_df['وضعیت']]

            fig_status = px.bar(status_df, x='وضعیت', y='تعداد', color='وضعیت',
                                title=f"توزیع وضعیت مزارع ({selected_edareh if selected_edareh != 'همه ادارات' else 'کل'}) - روز: {selected_day}",
                                text_auto=True, color_discrete_map={k: v[0] for k, v in status_legend_map.items()}) # Use legend colors
            fig_status.update_layout(xaxis_title="وضعیت", yaxis_title="تعداد مزارع", showlegend=False,
                                     height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_status, use_container_width=True)

            # Display AI Summary
            if gemini_model:
                 ai_map_summary = get_ai_map_summary(gemini_model, simplified_status_counts, selected_edareh, selected_day)
                 st.markdown("**خلاصه تحلیلی (هوش مصنوعی):**")
                 with st.spinner("در حال تولید خلاصه هوشمند..."):
                      st.markdown(f"> {ai_map_summary}") # Display the summary inside a blockquote
            else:
                 st.info("سرویس هوش مصنوعی برای خلاصه‌سازی در دسترس نیست. (کلید API تنظیم نشده؟)")

            # Display Legend Manually using simplified categories
            st.markdown("**راهنمای نقشه وضعیت:**")
            legend_html = "<div style='display: flex; flex-wrap: wrap; gap: 20px; align-items: center;'>"
            # Use simplified legend map
            for status_name, (color, desc) in status_legend_map.items():
                 # Find the *most representative* icon for this simplified status group
                 icon_class = 'fa-question-circle' # Default
                 if status_name == "بهبود": icon_class = 'fa-arrow-up' # Or down based on index? Use generic up for now
                 elif status_name == "ثابت": icon_class = 'fa-equals'
                 elif status_name == "تنش/کاهش": icon_class = 'fa-arrow-down' # Generic down for decrease/stress
                 elif status_name == "جدید": icon_class = 'fa-star'
                 elif status_name == "نامشخص/خطا": icon_class = 'fa-circle-notch' # Spinner for no data

                 # Use the color defined in status_map_colors matching the icon if possible, else use legend color
                 marker_color = next((mc[0] for r_stat, mc in status_map_colors.items() if mc[1] == icon_class), color) # Find color by icon

                 legend_html += f"<div style='display: flex; align-items: center; gap: 5px;'>" \
                                f"<i class='fas {icon_class}' style='color:{marker_color}; font-size: 1.2em;'></i>" \
                                f"<span style='background-color:{color}; color: {'white' if color in ['#dc3545', '#6c757d'] else 'black'}; padding: 2px 6px; border-radius: 4px;'>{status_name}</span>: " \
                                f"<span>{desc}</span>" \
                                f"</div>"
            legend_html += "</div>"
            st.markdown(legend_html, unsafe_allow_html=True)
            st.caption("رنگ آیکون‌ها در نقشه ممکن است بر اساس وضعیت دقیق‌تر متفاوت باشد (مثلاً فلش سبز برای رشد مثبت).")

        else:
             st.info("داده‌ای برای نمایش خلاصه وضعیت طبقه‌بندی شده وجود ندارد.")
    else:
        st.info("داده‌ای برای نمایش خلاصه وضعیت طبقه‌بندی شده وجود ندارد (رتبه‌بندی محاسبه نشد؟).")


    # --- Time Series Chart ---
    st.markdown("---")
    st.subheader(f"📈 نمودار روند زمانی: {index_options[selected_index]}")
    if selected_farm_name == "همه مزارع":
        st.info("یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
    elif selected_farm_geom and selected_farm_details is not None:
        # Check if selected_farm_geom is a Point (required for time series)
        is_point = isinstance(selected_farm_geom, ee.geometry.Geometry) and selected_farm_geom.type().getInfo() == 'Point'

        if is_point:
            with st.spinner(f"در حال دریافت سری زمانی {selected_index} برای {selected_farm_name}..."):
                # Define time range (e.g., last 12 months)
                timeseries_end_date = today.strftime('%Y-%m-%d')
                timeseries_start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d') # Last year

                ts_df, ts_error = get_index_time_series(
                    selected_farm_geom, selected_index,
                    start_date=timeseries_start_date, end_date=timeseries_end_date
                )

            if ts_error:
                st.warning(f"خطا در دریافت سری زمانی: {ts_error}", icon="📉")
            elif not ts_df.empty:
                # Resample to weekly or bi-weekly means for smoother plot? (Optional)
                # ts_df_resampled = ts_df.resample('W').mean() # Weekly mean
                ts_df_resampled = ts_df # Or plot raw data

                fig_ts = px.line(ts_df_resampled, x=ts_df_resampled.index, y=selected_index,
                                 title=f"روند {index_options[selected_index]} - مزرعه: {selected_farm_name} (12 ماه اخیر)",
                                 labels={'date': 'تاریخ', selected_index: f'مقدار {selected_index}'}, markers=True)
                fig_ts.update_traces(line=dict(color='#6f42c1', width=2), marker=dict(color='#fd7e14', size=6))
                fig_ts.update_layout(hovermode="x unified", height=400,
                                     paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                     yaxis_title=f"{selected_index}", xaxis_title="تاریخ")
                st.plotly_chart(fig_ts, use_container_width=True)
            else:
                st.info(f"داده‌ای برای سری زمانی {selected_index} در 12 ماه گذشته برای این مزرعه یافت نشد.")
        else:
            st.warning("نمودار سری زمانی فقط برای مزارع منفرد (با انتخاب از پنل کناری) در دسترس است.")
    else:
        st.warning("جزئیات یا موقعیت مزرعه برای نمایش نمودار سری زمانی در دسترس نیست.")


    # ==========================================================================
    # Ranking Table
    # ==========================================================================
    st.markdown("---")
    st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {index_options[selected_index]}")
    st.markdown(f"مقایسه هفته جاری ({end_date_current_str}) با هفته قبل ({end_date_previous_str}). اداره: **{selected_edareh}**")

    # Display errors from the ranking calculation
    if map_calc_errors: # Reuse errors from map calculation
        with st.expander("⚠️ مشاهده خطاهای محاسبه رتبه‌بندی (کلیک کنید)", expanded=False):
            error_dict = {}
            for error_str in map_calc_errors:
                try:
                    # Try to extract farm name (assuming format "FarmName (period): Error")
                    farm_name_err = error_str.split(" (")[0]
                except Exception:
                    farm_name_err = "مزرعه ناشناس"
                error_dict.setdefault(farm_name_err, []).append(error_str)

            # Display errors grouped by farm name
            for farm_name_err, err_list in error_dict.items():
                 st.error(f"**مزرعه: {farm_name_err}**")
                 unique_errors = list(set(err_list)) # Show only unique errors per farm
                 for err in unique_errors:
                     st.caption(f"- {err}")


    # Display the ranking table if data exists
    if not ranking_df_map.empty and f'{selected_index} (هفته جاری)' in ranking_df_map.columns:
        # Sort the table
        # Lower MSI is better, higher for others (usually)
        ascending_sort = selected_index in ['MSI']
        ranking_df_map_sorted = ranking_df_map.sort_values(
            by=f'{selected_index} (هفته جاری)',
            ascending=ascending_sort,
            na_position='last' # Put farms with no data at the bottom
        ).reset_index(drop=True)

        # Add Rank column (starting from 1)
        ranking_df_map_sorted.index = ranking_df_map_sorted.index + 1
        ranking_df_map_sorted.index.name = 'رتبه'

        # Apply status badge HTML formatting
        if 'وضعیت_متن' in ranking_df_map_sorted.columns:
             ranking_df_map_sorted['وضعیت'] = ranking_df_map_sorted['وضعیت_متن'].apply(status_badge)
        else:
             ranking_df_map_sorted['وضعیت'] = status_badge("N/A") # Fallback

        # Format numeric columns for display
        cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
        for col in cols_to_format:
            if col in ranking_df_map_sorted.columns:
                 # Format numbers, keep strings/NAs as they are
                 if col == 'تغییر': # Format percentage change
                      ranking_df_map_sorted[col] = ranking_df_map_sorted[col].apply(
                           lambda x: f"{x:+.1f}%" if pd.notna(x) and isinstance(x, (int, float)) else ("-" if pd.isna(x) else x)
                      )
                 else: # Format index values
                      ranking_df_map_sorted[col] = ranking_df_map_sorted[col].apply(
                           lambda x: f"{x:.3f}" if pd.notna(x) and isinstance(x, (int, float)) else ("N/A" if pd.isna(x) else x)
                      )

        # Select and order columns for display
        display_columns_order = ['مزرعه', 'اداره', 'گروه', 'سن', 'واریته',
                                 f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)',
                                 'تغییر', 'وضعیت']
        # Filter list to only include columns that actually exist in the dataframe
        display_columns = [col for col in display_columns_order if col in ranking_df_map_sorted.columns]

        # Display the HTML table
        st.markdown("<style> td, th { text-align: right !important; vertical-align: middle; } </style>", unsafe_allow_html=True)
        # Use st.dataframe for better interactivity or st.write for HTML rendering
        # st.dataframe(ranking_df_map_sorted[display_columns]) # Interactive
        st.write(ranking_df_map_sorted[display_columns].to_html(escape=False, index=True, classes='dataframe table table-striped table-hover', justify='right', border=0), unsafe_allow_html=True) # Render HTML

        # Download Button
        try:
            # Prepare DataFrame for CSV export (use raw data, remove HTML badge)
            csv_df = ranking_df_map_sorted.copy()
            # Keep the text status, drop the HTML badge column if it exists
            if 'وضعیت' in csv_df.columns:
                csv_df = csv_df.drop(columns=['وضعیت'])
            # Rename text status column for clarity in CSV
            if 'وضعیت_متن' in csv_df.columns:
                 csv_df.rename(columns={'وضعیت_متن': 'Status_Description'}, inplace=True)

            # Convert float columns back to numeric if they were formatted as strings
            for col in [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']:
                 if col in csv_df.columns:
                      csv_df[col] = pd.to_numeric(csv_df[col].astype(str).str.replace('%', '').str.replace('+', ''), errors='coerce')


            csv_data = csv_df.to_csv(index=True, encoding='utf-8-sig') # Use utf-8-sig for Excel compatibility
            st.download_button(
                label="📥 دانلود جدول رتبه‌بندی (CSV)",
                data=csv_data,
                file_name=f'ranking_{selected_edareh.replace(" ","_")}_{selected_index}_{selected_day}_{end_date_current_str}.csv',
                mime='text/csv'
            )
        except Exception as e_csv:
            st.error(f"خطا در ایجاد فایل CSV برای دانلود: {e_csv}")

    elif filtered_farms_df.empty:
         st.info(f"هیچ مزرعه‌ای برای رتبه‌بندی با فیلترهای انتخابی وجود ندارد.")
    else:
        st.info(f"داده‌ای برای جدول رتبه‌بندی ({selected_index}) محاسبه نشد یا یافت نشد.")


# --- Tab 2: Needs Analysis ---
with tab2:
    st.header("💧 تحلیل نیاز آبیاری و تغذیه")

    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری (در تب 'پایش مزارع') انتخاب کنید تا تحلیل نیازهای آن نمایش داده شود.")
    elif selected_farm_details is not None and selected_farm_geom is not None:
        # Ensure geometry is a point for needs analysis
        is_point = isinstance(selected_farm_geom, ee.geometry.Geometry) and selected_farm_geom.type().getInfo() == 'Point'

        if not is_point:
            st.warning("تحلیل نیازها فقط برای مزارع منفرد (که به صورت نقطه تعریف شده‌اند) در دسترس است. لطفاً یک مزرعه از لیست انتخاب کنید.")
        else:
            edareh_val_tab2 = selected_farm_details.get('اداره', 'N/A') if 'اداره' in selected_farm_details else 'N/A'
            st.subheader(f"تحلیل برای مزرعه: {selected_farm_name} (اداره: {edareh_val_tab2})")

            # --- User-defined Thresholds ---
            st.markdown("**تنظیم آستانه‌های هشدار:**")
            thresh_cols = st.columns(2)
            # Define reasonable defaults and ranges
            ndmi_threshold = thresh_cols[0].slider(
                label="آستانه NDMI (کم آبی):",
                min_value=-0.2, max_value=0.5, value=0.25, step=0.01,
                format="%.2f", key="ndmi_thresh_tab2",
                help="مقادیر NDMI کمتر از این آستانه ممکن است نشان‌دهنده تنش آبی باشد."
            )
            ndvi_drop_threshold = thresh_cols[1].slider(
                label="آستانه افت NDVI (تغذیه/تنش):",
                min_value=0.0, max_value=20.0, value=7.0, step=0.5,
                format="%.1f%%", key="ndvi_thresh_tab2",
                help="افت NDVI بیشتر از این درصد نسبت به هفته قبل، ممکن است نیاز به بررسی تغذیه یا سایر تنش‌ها داشته باشد."
            )

            # --- Get Data for Needs Analysis ---
            with st.spinner("در حال دریافت داده‌های شاخص برای تحلیل نیازسنجی..."):
                farm_needs_data = get_farm_needs_data(
                    selected_farm_geom,
                    start_date_current_str, end_date_current_str,
                    start_date_previous_str, end_date_previous_str
                )

            # --- Display Results and Analysis ---
            if farm_needs_data.get('error'):
                st.error(f"خطا در دریافت داده‌های شاخص برای تحلیل: {farm_needs_data['error']}")
            # Check if essential current data is missing
            elif pd.isna(farm_needs_data.get('NDMI_curr')) or pd.isna(farm_needs_data.get('NDVI_curr')):
                st.warning("داده‌های شاخص کلیدی (NDMI/NDVI) برای دوره فعلی جهت تحلیل یافت نشد.", icon="⚠️")
            else:
                # Display Indices Metrics
                st.markdown("**مقادیر شاخص‌ها (مقایسه هفتگی):**")
                idx_cols = st.columns(4)

                # Helper function to calculate delta safely
                def calc_delta(curr, prev):
                    if pd.notna(curr) and pd.notna(prev) and isinstance(curr, (int, float)) and isinstance(prev, (int, float)):
                        return curr - prev
                    return None # Return None if any value is missing or not numeric

                # Calculate deltas
                ndvi_d = calc_delta(farm_needs_data.get('NDVI_curr'), farm_needs_data.get('NDVI_prev'))
                ndmi_d = calc_delta(farm_needs_data.get('NDMI_curr'), farm_needs_data.get('NDMI_prev'))
                evi_d = calc_delta(farm_needs_data.get('EVI_curr'), farm_needs_data.get('EVI_prev'))
                savi_d = calc_delta(farm_needs_data.get('SAVI_curr'), farm_needs_data.get('SAVI_prev'))

                # Display metrics
                idx_cols[0].metric("NDVI", f"{farm_needs_data['NDVI_curr']:.3f}" if pd.notna(farm_needs_data.get('NDVI_curr')) else "N/A",
                                   f"{ndvi_d:+.3f}" if ndvi_d is not None else None, delta_color="normal")
                idx_cols[1].metric("NDMI", f"{farm_needs_data['NDMI_curr']:.3f}" if pd.notna(farm_needs_data.get('NDMI_curr')) else "N/A",
                                   f"{ndmi_d:+.3f}" if ndmi_d is not None else None, delta_color="normal")
                idx_cols[2].metric("EVI", f"{farm_needs_data.get('EVI_curr'):.3f}" if pd.notna(farm_needs_data.get('EVI_curr')) else "N/A",
                                   f"{evi_d:+.3f}" if evi_d is not None else None, delta_color="normal")
                idx_cols[3].metric("SAVI", f"{farm_needs_data.get('SAVI_curr'):.3f}" if pd.notna(farm_needs_data.get('SAVI_curr')) else "N/A",
                                   f"{savi_d:+.3f}" if savi_d is not None else None, delta_color="normal")

                # --- Rule-Based Recommendations ---
                recommendations = []
                issues_found = False

                # 1. Check NDMI for water stress
                ndmi_curr = farm_needs_data.get('NDMI_curr')
                if pd.notna(ndmi_curr) and ndmi_curr < ndmi_threshold:
                    recommendations.append(f"💧 **نیاز احتمالی به آبیاری:** مقدار NDMI ({ndmi_curr:.3f}) کمتر از آستانه تعیین شده ({ndmi_threshold:.2f}) است.")
                    issues_found = True

                # 2. Check NDVI drop for nutrition/stress issues
                ndvi_curr = farm_needs_data.get('NDVI_curr')
                ndvi_prev = farm_needs_data.get('NDVI_prev')
                if pd.notna(ndvi_curr) and pd.notna(ndvi_prev):
                     try:
                         # Calculate percentage change only if prev value is not close to zero
                         if abs(ndvi_prev) > 1e-6:
                             change_pct = ((ndvi_curr - ndvi_prev) / abs(ndvi_prev)) * 100
                             # Check if the drop exceeds the threshold (negative change)
                             if change_pct < -ndvi_drop_threshold: # Note the negative sign
                                 recommendations.append(f"⚠️ **نیاز به بررسی تغذیه/تنش:** افت قابل توجه NDVI ({change_pct:.1f}%) نسبت به هفته قبل مشاهده شد.")
                                 issues_found = True
                         elif ndvi_curr < ndvi_prev: # Handle case where previous was zero/small
                             # Check if the absolute drop is significant (e.g. > 0.05)
                             if (ndvi_prev - ndvi_curr) > 0.05:
                                   recommendations.append(f"⚠️ **نیاز به بررسی تغذیه/تنش:** افت NDVI مشاهده شد (مقدار قبلی: {ndvi_prev:.3f}).")
                                   issues_found = True

                     except Exception as e_ndvi:
                          print(f"Error calculating NDVI change: {e_ndvi}") # Log error
                          pass # Ignore calculation errors

                # 3. Check absolute low NDVI value
                if pd.notna(ndvi_curr) and ndvi_curr < 0.35: # Example threshold for low vegetation
                    # Avoid duplicating warning if already flagged by drop %
                    if not any("تغذیه/تنش" in r for r in recommendations):
                        recommendations.append(f"📉 **پوشش گیاهی ضعیف:** مقدار NDVI ({ndvi_curr:.3f}) پایین است و نیاز به بررسی دارد.")
                        issues_found = True

                # 4. If no issues found
                if not issues_found:
                    recommendations.append("✅ **وضعیت مطلوب:** بر اساس آستانه‌های تنظیم شده، هشدار خاصی شناسایی نشد.")

                # Display Recommendations with appropriate styling
                st.markdown("**توصیه‌های اولیه:**")
                for rec in recommendations:
                    if "آبیاری" in rec: st.error(rec)
                    elif "تغذیه/تنش" in rec or "ضعیف" in rec: st.warning(rec)
                    else: st.success(rec) # For "وضعیت مطلوب"

                # --- AI Analysis (Gemini) ---
                st.markdown("---")
                st.markdown("**تحلیل هوش مصنوعی (Gemini):**")
                if gemini_model:
                    # Prepare concise recommendations for the AI prompt
                    concise_recs = []
                    for r in recommendations:
                         if r.startswith("💧"): concise_recs.append("نیاز به آبیاری")
                         elif r.startswith("⚠️"): concise_recs.append("نیاز به بررسی تغذیه/تنش")
                         elif r.startswith("📉"): concise_recs.append("پوشش گیاهی ضعیف")
                         elif r.startswith("✅"): concise_recs.append("وضعیت مطلوب")

                    with st.spinner("در حال تولید تحلیل هوشمند..."):
                         ai_needs_summary = get_ai_needs_analysis(gemini_model, selected_farm_name, farm_needs_data, concise_recs)
                    st.markdown(f"> {ai_needs_summary}") # Display inside blockquote
                else:
                     st.info("سرویس تحلیل هوش مصنوعی پیکربندی نشده یا در دسترس نیست. (کلید API تنظیم نشده؟)")

    elif not selected_farm_details and selected_farm_name != "همه مزارع":
        st.error(f"جزئیات مزرعه '{selected_farm_name}' یافت نشد. لطفاً از لیست معتبر انتخاب کنید.")
    else: # Should cover initial state or error states
        st.warning("ابتدا یک مزرعه معتبر را از پنل کناری در تب 'پایش مزارع' انتخاب کنید.")


# --- Footer ---
st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.info("ساخته شده با 💚 توسط اسماعیل کیانی")
# st.sidebar.markdown("[GitHub](https://your-link-here)") # Add link if available