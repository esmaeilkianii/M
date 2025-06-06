import streamlit as st
import pyproj # Added for coordinate transformation
# import base64 # For encoding logo image - Will be removed if not used elsewhere
import os # For path joining - Will be removed if not used elsewhere


# --- Page Config ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide"
)

# --- Apply Custom Styles from styles.py ---
st.markdown("""
    <link href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css" rel="stylesheet" type="text/css" />
    <style>
    /* Test comment for indentation */
    /* Modern Color Scheme */
    :root {
        --primary-color: #2C3E50;
        --secondary-color: #3498DB;
        --accent-color: #E74C3C;
        --success-color: #2ECC71;
        --warning-color: #F1C40F;
        --background-color: #ECF0F1;
        --card-bg-color: rgba(255, 255, 255, 0.95);
        --text-color: #2C3E50;
        /* Added based on reintegration needs */
        --info-bg: #e6f7ff;
        --info-border: #007bff;
        --success-bg: #f0fff0; /* Consider: color-mix(in srgb, var(--success-color) 15%, transparent); */
        --success-border: var(--success-color);
        --warning-bg: #fff3cd; /* Consider: color-mix(in srgb, var(--warning-color) 15%, transparent); */
        --warning-border: var(--warning-color);
        --header-text-color: var(--primary-color); /* Default header text color */
    }

    /* Glass Morphism Effect */
    .glass-card {
        background: rgba(255, 255, 255, 0.7);
        backdrop-filter: blur(10px);
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.3);
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
    }

    /* Modern Dashboard Layout */
    .stApp {
        background: linear-gradient(135deg, #ECF0F1 0%, #D5DBDB 100%);
        font-family: 'Vazirmatn', sans-serif;
    }

    /* Enhanced Cards */
    div.element-container {
        background: var(--card-bg-color);
        border-radius: 15px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease;
    }

    div.element-container:hover {
        transform: translateY(-5px);
    }

    /* Animated Metrics */
    [data-testid="stMetric"] {
        background: var(--card-bg-color);
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid var(--accent-color);
        animation: slideIn 0.5s ease-out;
    }

    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateX(-20px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    /* Modern Buttons */
    .stButton > button {
        background: linear-gradient(45deg, var(--primary-color), var(--secondary-color));
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.5rem 2rem;
        font-weight: 500;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
    }

    /* Enhanced Charts */
    .js-plotly-plot {
        background: var(--card-bg-color);
        border-radius: 15px;
        padding: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }

    /* Modern Tables */
    .dataframe {
        border: none !important;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }

    .dataframe thead th {
        background-color: var(--primary-color) !important;
        color: white !important;
    }

    .dataframe tbody tr:nth-child(even) {
        background-color: rgba(236, 240, 241, 0.5);
    }

    /* Animated Loading Spinner */
    .stSpinner {
        border: 4px solid var(--background-color);
        border-top: 4px solid var(--accent-color);
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    /* RTL Support */
    .rtl-content {
        direction: rtl;
        text-align: right;
    }

    /* Responsive Design */
    @media screen and (max-width: 768px) {
        .stButton > button {
            width: 100%;
        }

        div.element-container {
            margin: 0.25rem 0;
        }
    }

    /* --- START REINTEGRATED STYLES --- */

    /* Headers */
    h1, h2, h3 {
        font-family: 'Vazirmatn', sans-serif;
        text-align: right;
        font-weight: 600;
    }
    h1 {
        color: var(--header-text-color, var(--primary-color)); /* Fallback to primary-color */
        border-bottom: 2px solid var(--secondary-color);
        padding-bottom: 0.3em;
        margin-bottom: 0.7em;
    }
    h2 {
        color: var(--primary-color);
    }
    h3 {
        color: var(--accent-color);
        font-weight: 500;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 5px;
        direction: rtl;
        border-bottom: 2px solid #e0e0e0; /* Consider var(--background-color) or a lighter gray */
    }
    .stTabs [data-baseweb="tab"] {
        height: 55px;
        padding: 12px 25px;
        background-color: #f8f9fa; /* Neutral non-active tab, consider var(--card-bg-color) or lighter var(--background-color) */
        border-radius: 8px 8px 0 0;
        font-family: 'Vazirmatn', sans-serif;
        font-weight: 600;
        color: var(--text-color);
        border: 1px solid #e0e0e0; /* Consider var(--background-color) or a lighter gray */
        border-bottom: none;
        transition: background-color 0.2s, color 0.2s;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: var(--secondary-color); /* Use theme's secondary color for active tab */
        color: white; /* Ensure contrast with secondary color */
        border-color: var(--secondary-color);
    }

    /* Custom status badges */
    .status-badge {
        padding: 5px 10px;
        border-radius: 15px;
        font-size: 0.85em;
        font-weight: 500;
        display: inline-block;
    }
    .status-positive {
        background-color: var(--success-bg); /* #d1fae5; */
        color: var(--success-color); /* #065f46; */
        border: 1px solid var(--success-border); /* #6ee7b7; */
    }
    .status-neutral {
        background-color: var(--warning-bg); /* #feF3c7; */
        color: var(--warning-color); /* #92400e; */
        border: 1px solid var(--warning-border); /* #fcd34d; */
    }
    .status-negative {
        background-color: color-mix(in srgb, var(--accent-color) 15%, transparent); /* #fee2e2; */
        color: var(--accent-color); /* #991b1b; */
        border: 1px solid var(--accent-color); /* #fca5a5; */
    }

    /* Custom containers for better visual grouping */
    .section-container {
        background-color: var(--card-bg-color);
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.07);
        margin-bottom: 2rem;
    }

    /* Markdown links */
    a {
        color: var(--accent-color);
        text-decoration: none;
    }
    a:hover {
        text-decoration: underline;
    }

    /* Custom Gemini response box styles */
    .gemini-response-default {
        background-color: var(--info-bg);
        border-left: 5px solid var(--info-border);
        padding: 20px;
        border-radius: 10px;
        margin-top:20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    .gemini-response-default:before {
        content: '💡';
        font-size: 1.2em;
        position: absolute;
        top: 10px;
        right: 15px;
        opacity: 0.5;
    }
    .gemini-response-default:hover {
        box-shadow: 0 6px 16px rgba(0,0,0,0.12);
        transform: translateY(-3px);
    }

    .gemini-response-report {
        background-color: var(--success-bg);
        border-left: 5px solid var(--success-border);
        padding: 20px;
        border-radius: 10px;
        margin-top:20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transition: all 0.3s ease;
        position: relative;
    }
    .gemini-response-report:before {
        content: '📊';
        font-size: 1.2em;
        position: absolute;
        top: 10px;
        right: 15px;
        opacity: 0.5;
    }
    .gemini-response-report:hover {
        box-shadow: 0 6px 16px rgba(0,0,0,0.12);
        transform: translateY(-3px);
    }

    .gemini-response-analysis {
        background-color: var(--warning-bg);
        border-left: 5px solid var(--warning-border);
        padding: 20px;
        border-radius: 10px;
        margin-top:20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transition: all 0.3s ease;
        position: relative;
    }
    .gemini-response-analysis:before {
        content: '🔍';
        font-size: 1.2em;
        position: absolute;
        top: 10px;
        right: 15px;
        opacity: 0.5;
    }
    .gemini-response-analysis:hover {
        box-shadow: 0 6px 16px rgba(0,0,0,0.12);
        transform: translateY(-3px);
    }

    /* Animated Gemini AI Tab specific styles */
    .gemini-header {
        background: linear-gradient(-45deg, var(--primary-color), var(--secondary-color), var(--accent-color));
        background-size: 400% 400%;
        animation: gradient 15s ease infinite;
        color: white;
        padding: 15px 25px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    @keyframes gradient {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    .pulse-animation {
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }

    .fade-in {
        opacity: 0;
        animation: fadeIn 1s forwards;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Animated AI Icon for Gemini Sections */
    .ai-icon { /* This is for Gemini sections, distinct from tab intro icons */
        display: flex;
        justify-content: center;
        margin-bottom: 15px;
    }
    .ai-icon-pulse { /* Specific animated icon for Gemini */
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background-color: var(--accent-color);
        display: flex;
        justify-content: center;
        align-items: center;
        color: white;
        font-size: 30px;
        box-shadow: 0 0 0 0 rgba(var(--accent-color), 0.5); /* Use accent color for pulse */
        animation: ai-pulse 2s infinite;
    }
    @keyframes ai-pulse { /* Keyframes for the Gemini AI icon pulse */
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent-color) 70%, transparent); }
        70% { transform: scale(1); box-shadow: 0 0 0 10px color-mix(in srgb, var(--accent-color) 0%, transparent); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent-color) 0%, transparent); }
    }

    /* Advanced Card Design for Gemini Sections */
    .gemini-card {
        background-color: var(--card-bg-color);
        border-radius: 12px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        padding: 20px;
        margin-bottom: 25px;
        transition: all 0.3s ease;
        border-top: 5px solid var(--accent-color);
        position: relative;
        overflow: hidden;
    }
    .gemini-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 30px rgba(0,0,0,0.15);
    }
    .gemini-card::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(135deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0) 50%);
        pointer-events: none;
    }
    .gemini-card-header {
        display: flex;
        align-items: center;
        margin-bottom: 15px;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(0,0,0,0.1);
    }
    .gemini-card-icon { /* Icon within Gemini cards */
        width: 40px;
        height: 40px;
        border-radius: 8px;
        background-color: var(--accent-color);
        display: flex;
        justify-content: center;
        align-items: center;
        margin-left: 15px; /* RTL: should be margin-right if text is LTR */
        color: white;
        font-weight: bold;
        font-size: 20px;
    }
    .gemini-card-title {
        margin: 0;
        font-size: 18px;
        color: var(--primary-color);
        font-weight: 600;
    }

    /* Loading Animation for Gemini responses */
    .loading-animation {
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 20px;
    }
    .loading-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background-color: var(--accent-color);
        margin: 0 5px;
        animation: loading-dots-animation 1.4s infinite ease-in-out both;
    }
    .loading-dot:nth-child(1) { animation-delay: -0.32s; }
    .loading-dot:nth-child(2) { animation-delay: -0.16s; }
    @keyframes loading-dots-animation { /* Renamed to avoid conflict with .stSpinner's 'spin' */
        0%, 80%, 100% { transform: scale(0); }
        40% { transform: scale(1); }
    }
    /* --- END REINTEGRATED STYLES --- */
    </style>
    """, unsafe_allow_html=True)

# --- REMOVED Custom Modern Cards CSS ---
# --- REMOVED Animated Logo Display ---

# --- Imports ---
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
import json
import datetime
import plotly.express as px
import os
from io import BytesIO
import requests
import traceback
from streamlit_folium import st_folium
import google.generativeai as genai
import time # For potential (not recommended) auto-rerun

# --- Configuration ---
APP_TITLE = "سامانه پایش هوشمند نیشکر"
APP_SUBTITLE = "مطالعات کاربردی شرکت کشت و صنعت دهخدا"
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 12

# --- File Paths (Relative to the script location in Hugging Face) ---
# CSV_FILE_PATH = 'cleaned_output.csv' # OLD
CSV_FILE_PATH = 'merged_farm_data_renamed (1).csv' # NEW
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'


# --- GEE Authentication ---
@st.cache_resource
def initialize_gee():
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"خطا: فایل Service Account در مسیر '{SERVICE_ACCOUNT_FILE}' یافت نشد.")
            st.stop()
        credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        return True
    except Exception as e:
        st.error(f"خطا در اتصال به GEE: {e}")
        st.stop()

# --- Load Farm Data from GEE FeatureCollection ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع از GEE...")
def load_farm_data_from_gee():
    try:
        farms_fc = ee.FeatureCollection("projects/ee-esmaeilkiani13877/assets/Croplogging-Farm")
        features = farms_fc.getInfo()['features']
        farm_records = []
        for f in features:
            props = f['properties']
            geom = f['geometry']
            
            # Create EE geometry to calculate accurate area
            ee_geom = None
            if geom['type'] == 'Polygon':
                ee_geom = ee.Geometry.Polygon(geom['coordinates'])
                
            # محاسبه centroid
            if geom['type'] == 'Polygon':
                coords = geom['coordinates'][0]
                centroid_lon = sum([pt[0] for pt in coords]) / len(coords)
                centroid_lat = sum([pt[1] for pt in coords]) / len(coords)
            else:
                centroid_lon, centroid_lat = None, None
            
            # محاسبه مساحت دقیق بر اساس هندسه
            area_ha = None
            if ee_geom:
                try:
                    area_m2 = ee_geom.area(maxError=1).getInfo()
                    if area_m2 is not None:
                        area_ha = area_m2 / 10000.0  # تبدیل به هکتار
                except Exception:
                    area_ha = None
                
            farm_records.append({
                'مزرعه': props.get('farm', ''),
                'گروه': props.get('group', ''),
                'واریته': props.get('Variety', ''),
                'سن': props.get('Age', ''),
                'مساحت': area_ha if area_ha is not None else props.get('Area', ''),  # استفاده از مساحت محاسبه شده دقیق
                'روز ': props.get('Day', ''),
                'Field': props.get('Field', ''),
                'geometry': geom,
                'centroid_lon': centroid_lon,
                'centroid_lat': centroid_lat,
                'calculated_area_ha': area_ha,  # ذخیره مساحت محاسبه شده به عنوان ستون جداگانه
            })
        df = pd.DataFrame(farm_records)
        st.success(f"✅ داده‌های {len(df)} مزرعه از GEE بارگذاری شد.")
        return df
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری داده از GEE: {e}")
        return None

# --- Use GEE farm data instead of CSV ---
if initialize_gee():
    farm_data_df = load_farm_data_from_gee()
else:
    st.error("❌ اتصال به GEE ناموفق بود.")
    st.stop()

if farm_data_df is None:
    st.error("❌ بارگذاری داده مزارع از GEE ناموفق بود.")
    st.stop()

# ==============================================================================
# Gemini API Configuration
# ==============================================================================
# !!! هشدار امنیتی: قرار دادن مستقیم API Key در کد ریسک بالایی دارد !!!
GEMINI_API_KEY = "AIzaSyDzirWUubBVyjF10_JZUVSd6c6nnTKpLw" # <<<<<<< جایگزین کنید >>>>>>>>

gemini_model = None
if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        # st.sidebar.success("✅ اتصال به Gemini برقرار شد.") # Sidebar not yet rendered
    except Exception as e:
        # st.sidebar.error(f"خطا در اتصال به Gemini: {e}") # Sidebar not yet rendered
        print(f"خطا در اتصال به Gemini: {e}") # Log to console instead
        gemini_model = None
# else handled in sidebar display logic

def ask_gemini(prompt_text, temperature=0.7, top_p=1.0, top_k=40):
    if not gemini_model:
        return "خطا: مدل Gemini مقداردهی اولیه نشده است. کلید API را بررسی کنید."
    try:
        generation_config = genai.types.GenerationConfig(
            temperature=temperature, top_p=top_p, top_k=top_k, max_output_tokens=3072
        )
        response = gemini_model.generate_content(prompt_text, generation_config=generation_config)
        return response.text
    except Exception as e:
        return f"خطا در ارتباط با Gemini API: {e}\n{traceback.format_exc()}"

# ==============================================================================
# Sidebar
# ==============================================================================
with st.sidebar:
    # st.markdown("## 🎨 انتخاب تم") # Removed theme selection
    # selected_theme_name_sidebar = st.selectbox(
    #     "تم رنگی برنامه را انتخاب کنید:",
    #     options=list(THEMES.keys()),
    #     index=list(THEMES.keys()).index(st.session_state.selected_theme_name),
    #     key="theme_selector_widget"
    # )
    # if selected_theme_name_sidebar != st.session_state.selected_theme_name:
    #     st.session_state.selected_theme_name = selected_theme_name_sidebar
    #     st.rerun() # Rerun to apply new theme CSS

    # st.markdown("---") # Removed separator if theme selection was the only thing above it
    st.header("⚙️ تنظیمات نمایش")

    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        st.warning("⚠️ کلید API جمینای خود را مستقیماً در کد برنامه (متغیر GEMINI_API_KEY) وارد کنید تا قابلیت‌های هوشمند فعال شوند.")
    elif not gemini_model:
         st.error("اتصال به Gemini ناموفق بود. کلید API را بررسی کنید.")
    else:
        st.success("✅ اتصال به Gemini برقرار است.")


    # available_days = sorted(farm_data_df['روزهای هفته'].unique()) # OLD
    available_days = sorted(farm_data_df['روز '].unique()) # NEW: Using 'روز ' (with space)
    selected_day = st.selectbox(
        "📅 روز هفته:", options=available_days, index=0,
        help="داده‌های مزارع بر اساس این روز فیلتر می‌شوند."
    )

    # filtered_farms_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day].copy() # OLD
    filtered_farms_df = farm_data_df[farm_data_df['روز '] == selected_day].copy() # NEW

    if filtered_farms_df.empty:
        st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
        st.stop()

    available_farms = sorted(filtered_farms_df['مزرعه'].unique())
    farm_options = ["همه مزارع"] + available_farms
    selected_farm_name = st.selectbox(
        "🌾 انتخاب مزرعه:", options=farm_options, index=0,
        help="مزرعه‌ای که می‌خواهید جزئیات آن را ببینید یا 'همه مزارع' برای نمایش کلی."
    )

    index_options = {
        "NDVI": "پوشش گیاهی (NDVI)", "EVI": "پوشش گیاهی بهبودیافته (EVI)",
        "NDMI": "رطوبت گیاه (NDMI)", "LAI": "سطح برگ (LAI)",
        "MSI": "تنش رطوبتی (MSI)", "CVI": "کلروفیل (CVI)",
    }
    selected_index = st.selectbox(
        "📈 انتخاب شاخص:", options=list(index_options.keys()),
        format_func=lambda x: f"{x} - {index_options[x]}", index=0
    )

    today = datetime.date.today()
    persian_to_weekday = {"شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1, "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4}
    try:
        target_weekday = persian_to_weekday[selected_day]
        days_to_subtract = (today.weekday() - target_weekday + 7) % 7
        end_date_current = today - datetime.timedelta(days=days_to_subtract if days_to_subtract != 0 else 0)
        if today.weekday() == target_weekday and days_to_subtract == 0: end_date_current = today
        elif days_to_subtract == 0 and today.weekday() != target_weekday: end_date_current = today - datetime.timedelta(days=7)

        start_date_current = end_date_current - datetime.timedelta(days=6)
        end_date_previous = start_date_current - datetime.timedelta(days=1)
        start_date_previous = end_date_previous - datetime.timedelta(days=6)
        start_date_current_str, end_date_current_str = start_date_current.strftime('%Y-%m-%d'), end_date_current.strftime('%Y-%m-%d')
        start_date_previous_str, end_date_previous_str = start_date_previous.strftime('%Y-%m-%d'), end_date_previous.strftime('%Y-%m-%d')
        
        st.markdown(f"<p style='font-size:0.9em;'>🗓️ <b>بازه فعلی:</b> {start_date_current_str} تا {end_date_current_str}</p>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:0.9em;'>🗓️ <b>بازه قبلی:</b> {start_date_previous_str} تا {end_date_previous_str}</p>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"خطا در محاسبه بازه زمانی: {e}")
        st.stop()
    
    st.markdown("---")
    st.markdown("<div style='text-align:center; font-size:0.9em;'>Developed by Esmaeil Kiani<strong>اسماعیل کیانی</strong></div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center; font-size:0.95em;'>🌾 شرکت کشت و صنعت دهخدا</div>", unsafe_allow_html=True)


# ==============================================================================
# GEE Functions (Copied from previous version - no changes needed for this request)
# ==============================================================================
def maskS2clouds(image):
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
    scl = image.select('SCL')
    good_quality_scl = scl.remap([4, 5, 6], [1, 1, 1], 0)
    opticalBands = image.select('B.*').multiply(0.0001)
    return image.addBands(opticalBands, None, True).updateMask(mask).updateMask(good_quality_scl)

def add_indices(image):
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)',
        {'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2')}
    ).rename('EVI')
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    msi = image.expression('SWIR1 / NIR', {'SWIR1': image.select('B11'), 'NIR': image.select('B8')}).rename('MSI')
    lai_expr = ndvi.multiply(3.5).clamp(0,8)
    lai = lai_expr.rename('LAI')
    green_safe = image.select('B3').max(ee.Image(0.0001))
    red_safe = image.select('B4').max(ee.Image(0.0001))
    cvi = image.expression('(NIR / GREEN) * (RED / GREEN)',
        {'NIR': image.select('B8'), 'GREEN': green_safe, 'RED': red_safe}
    ).rename('CVI')
    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi])

@st.cache_data(show_spinner="⏳ در حال پردازش تصاویر ماهواره‌ای...", persist=True)
def get_processed_image(_geometry, start_date, end_date, index_name):
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds))
        count = s2_sr_col.size().getInfo()
        if count == 0:
            return None, f"تصویر بدون ابری در بازه {start_date} تا {end_date} یافت نشد."
        indexed_col = s2_sr_col.map(add_indices)
        median_image = indexed_col.median()
        if index_name not in median_image.bandNames().getInfo():
             return None, f"شاخص '{index_name}' پس از پردازش در تصویر میانه یافت نشد."
        output_image = median_image.select(index_name)
        return output_image, None
    except ee.EEException as e:
        error_message = f"خطای Google Earth Engine: {e}"
        error_details = e.args[0] if e.args else str(e)
        if isinstance(error_details, str):
            if 'computation timed out' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل حجم بالای پردازش یا بازه زمانی طولانی)"
            elif 'user memory limit exceeded' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده)"
        return None, error_message
    except Exception as e:
        return None, f"خطای ناشناخته در پردازش GEE: {e}\n{traceback.format_exc()}"

@st.cache_data(show_spinner="⏳ در حال دریافت سری زمانی شاخص...", persist=True)
def get_index_time_series(_geometry, index_name, start_date_str, end_date_str):
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date_str, end_date_str)
                     .map(maskS2clouds)
                     .map(add_indices))
        
        def extract_value(image):
            value = ee.Algorithms.If(
                image.bandNames().contains(index_name),
                image.reduceRegion(
                    reducer=ee.Reducer.mean(), 
                    geometry=_geometry, 
                    scale=10,
                    maxPixels=1e9
                ).get(index_name),
                None
            )
            return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value})

        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.notNull([index_name]))
        ts_info = ts_features.getInfo()['features']
        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), "داده‌ای برای سری زمانی یافت نشد."
        
        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_info if f['properties'] and f['properties'][index_name] is not None]
        if not ts_data:
            return pd.DataFrame(columns=['date', index_name]), "داده معتبری برای سری زمانی یافت نشد."

        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df = ts_df.sort_values('date').set_index('date')
        return ts_df, None
    except ee.EEException as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای GEE در دریافت سری زمانی: {e}"
    except Exception as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای ناشناخته در دریافت سری زمانی: {e}\n{traceback.format_exc()}"

# ==============================================================================
# Determine active farm geometry
# ==============================================================================
active_farm_geom = None
active_farm_centroid_for_point_ops = None # For operations needing a point (e.g., time series)
active_farm_name_display = selected_farm_name
active_farm_area_ha_display = "N/A" # Default, as 'مساحت' might not be in CSV or calculated yet

def get_farm_polygon_ee(farm_row):
    try:
        geom = farm_row['geometry']
        if geom['type'] == 'Polygon':
            coords = geom['coordinates']
            return ee.Geometry.Polygon(coords)
        return None
    except Exception as e:
        return None

if selected_farm_name == "همه مزارع":
    if not filtered_farms_df.empty:
        # For "همه مزارع", use a bounding box of the centroids of all farms in the filtered list
        # These centroids ('centroid_lon', 'centroid_lat') were calculated in load_farm_data using WGS84
        min_lon_df = filtered_farms_df['centroid_lon'].min()
        min_lat_df = filtered_farms_df['centroid_lat'].min()
        max_lon_df = filtered_farms_df['centroid_lon'].max()
        max_lat_df = filtered_farms_df['centroid_lat'].max()
        
        if pd.notna(min_lon_df) and pd.notna(min_lat_df) and pd.notna(max_lon_df) and pd.notna(max_lat_df):
            try:
                active_farm_geom = ee.Geometry.Rectangle([min_lon_df, min_lat_df, max_lon_df, max_lat_df])
                active_farm_centroid_for_point_ops = active_farm_geom.centroid(maxError=1)
            except Exception as e_bbox:
                st.error(f"خطا در ایجاد محدوده کلی مزارع: {e_bbox}")
                active_farm_geom = None
                active_farm_centroid_for_point_ops = None
else: # A single farm is selected
    selected_farm_details_active_df = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name]
    if not selected_farm_details_active_df.empty:
        farm_row_active = selected_farm_details_active_df.iloc[0]
        active_farm_geom = get_farm_polygon_ee(farm_row_active) # This is now an ee.Geometry.Polygon
        
        if active_farm_geom:
            active_farm_centroid_for_point_ops = active_farm_geom.centroid(maxError=1)
            try:
                # Try to calculate area using GEE for the selected polygon
                area_m2 = active_farm_geom.area(maxError=1).getInfo()
                if area_m2 is not None:
                    active_farm_area_ha_display = area_m2 / 10000.0
                else:
                    active_farm_area_ha_display = "محاسبه نشد" # GEE returned None for area
            except Exception as e_area:
                active_farm_area_ha_display = "خطا در محاسبه" # Error during GEE call
        else:
            active_farm_area_ha_display = "هندسه نامعتبر"
            
    else: # Should not happen if farm name is from dropdown
        st.warning(f"جزئیات مزرعه '{selected_farm_name}' در لیست فیلتر شده یافت نشد.")

# ==============================================================================
# Main Panel Display
# ==============================================================================
tab_titles = ["📊 داشبورد اصلی", "🗺️ نقشه و نمودارها", "💡 تحلیل هوشمند"]
# Add icons to tab titles (experimental, might not work perfectly on all browsers/versions)
# tab_icons = ["📊", "🗺️", "💡"]
# tab_titles_with_icons = [f"{icon} {title}" for icon, title in zip(tab_icons, tab_titles)]
# tab1, tab2, tab3 = st.tabs(tab_titles_with_icons)

tab1, tab2, tab3 = st.tabs(tab_titles)


with tab1:
    st.subheader("🌱 وضعیت کلی مزارع")
    st.markdown(f"تعداد کل مزارع: **{len(filtered_farms_df)}**")
    st.markdown(f"روز انتخابی: **{selected_day}**")
    # The modern-gradient-card div was removed. Content is now directly in tab1.
    # Additional styling for this section can be applied via .section-container or specific classes if needed.

    with st.container():
        # Applying section-container styling for consistent layout
        st.markdown("<div class='section-container'>", unsafe_allow_html=True)
        if selected_farm_name == "همه مزارع":
            st.subheader(f"📋 نمایش کلی مزارع برای روز: {selected_day}")
            st.info(f"تعداد مزارع در این روز: {len(filtered_farms_df)}")
        else:
            selected_farm_details_tab1 = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
            st.subheader(f"📋 جزئیات مزرعه: {selected_farm_name} (روز: {selected_day})")
            cols_details = st.columns([1,1,1])
            with cols_details[0]:
                # استفاده از مساحت دقیق محاسبه شده در GEE
                farm_area_display = selected_farm_details_tab1.get('مساحت')
                if pd.notna(farm_area_display) and isinstance(farm_area_display, (int, float)):
                    st.metric("مساحت (هکتار)", f"{farm_area_display:,.2f}")
                else:
                    st.metric("مساحت (هکتار)", "N/A")
            with cols_details[1]:
                st.metric("واریته", f"{selected_farm_details_tab1.get('واریته', 'N/A')}")
            with cols_details[2]:
                # 'کانال' is not in new CSV. Using 'اداره' or 'گروه' if available.
                admin_val = selected_farm_details_tab1.get('اداره', 'N/A')
                group_val = selected_farm_details_tab1.get('گروه', 'N/A')
                st.metric("اداره/گروه", f"{admin_val} / {group_val}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.subheader(f"📈 جدول رتبه‌بندی مزارع بر اساس {index_options[selected_index]} (روز: {selected_day})")
    st.caption("مقایسه مقادیر متوسط شاخص (نقاط مرکزی CSV) در هفته جاری با هفته قبل.")

    @st.cache_data(show_spinner=f"⏳ در حال محاسبه {selected_index}...", persist=True)
    def calculate_weekly_indices_for_ranking_table(_farms_df, index_name_calc, start_curr, end_curr, start_prev, end_prev):
        results = []
        errors = []
        total_farms = len(_farms_df)
        prog_bar = st.progress(0, text="شروع پردازش مزارع...")

        for i, (idx, farm) in enumerate(_farms_df.iterrows()):
            prog_bar.progress((i + 1) / total_farms, text=f"پردازش مزرعه {i+1}/{total_farms}: {farm['مزرعه']}")
            farm_name_calc = farm['مزرعه']
            
            # Create polygon and then get centroid for point-based GEE analysis
            farm_polygon_for_calc = get_farm_polygon_ee(farm)
            if not farm_polygon_for_calc:
                errors.append(f"خطا در ایجاد هندسه برای {farm_name_calc} در جدول رتبه‌بندی.")
                results.append({
                    'مزرعه': farm_name_calc, 
                    'اداره': farm.get('اداره', 'N/A'), 
                    'گروه': farm.get('گروه', 'N/A'),
                    'مساحت (هکتار)': farm.get('مساحت', 'N/A'),
                    f'{index_name_calc} (هفته جاری)': None, 
                    f'{index_name_calc} (هفته قبل)': None, 
                    'تغییر': None
                })
                continue
            
            # استفاده از هندسه کامل مزرعه برای محاسبه شاخص دقیق بجای نقطه مرکزی
            farm_area_ha = farm.get('مساحت')
            
            def get_mean_value(start_dt, end_dt):
                try:
                    image_calc, error_calc = get_processed_image(farm_polygon_for_calc, start_dt, end_dt, index_name_calc)
                    if image_calc:
                        # استفاده از کل پلیگون برای محاسبه میانگین بجای نقطه مرکزی
                        mean_dict = image_calc.reduceRegion(
                            reducer=ee.Reducer.mean(), 
                            geometry=farm_polygon_for_calc, 
                            scale=10, 
                            maxPixels=1e9
                        ).getInfo()
                        return mean_dict.get(index_name_calc), None
                    return None, error_calc
                except Exception as e_reduce: return None, f"خطا در {farm_name_calc} ({start_dt}-{end_dt}): {e_reduce}"

            current_val, err_curr = get_mean_value(start_curr, end_curr)
            if err_curr: errors.append(f"{farm_name_calc} (جاری): {err_curr}")
            previous_val, err_prev = get_mean_value(start_prev, end_prev)
            if err_prev: errors.append(f"{farm_name_calc} (قبلی): {err_prev}")
            change = float(current_val) - float(previous_val) if current_val is not None and previous_val is not None else None
            results.append({
                'مزرعه': farm_name_calc, 
                'اداره': farm.get('اداره', 'N/A'), # 'اداره' is in new CSV
                'گروه': farm.get('گروه', 'N/A'),   # 'گروه' is in new CSV
                'مساحت (هکتار)': farm_area_ha,
                f'{index_name_calc} (هفته جاری)': current_val, 
                f'{index_name_calc} (هفته قبل)': previous_val, 
                'تغییر': change
            })
        prog_bar.empty()
        return pd.DataFrame(results), errors

    ranking_df, calculation_errors = calculate_weekly_indices_for_ranking_table(
        filtered_farms_df, selected_index,
        start_date_current_str, end_date_current_str,
        start_date_previous_str, end_date_previous_str
    )

    if calculation_errors:
        with st.expander("⚠️ مشاهده خطاهای محاسبه شاخص‌ها", expanded=False):
            for error_item in calculation_errors: st.caption(f"- {error_item}")

    ranking_df_sorted = pd.DataFrame()
    if not ranking_df.empty:
        ascending_sort = selected_index in ['MSI']
        ranking_df_sorted = ranking_df.sort_values(
            by=f'{selected_index} (هفته جاری)', ascending=ascending_sort, na_position='last'
        ).reset_index(drop=True)
        ranking_df_sorted.index = ranking_df_sorted.index + 1
        ranking_df_sorted.index.name = 'رتبه'

        def determine_status_html(row, index_name_col_status):
            change_val_status = row['تغییر']
            current_val_status = row[f'{index_name_col_status} (هفته جاری)']
            prev_val_status = row[f'{index_name_col_status} (هفته قبل)']

            if pd.isna(change_val_status) or pd.isna(current_val_status) or pd.isna(prev_val_status):
                return "<span class='status-badge status-neutral'>بدون داده</span>"
            
            try: change_val_status = float(change_val_status)
            except (ValueError, TypeError): return "<span class='status-badge status-neutral'>خطا در داده</span>"

            threshold_status = 0.05
            if index_name_col_status in ['NDVI', 'EVI', 'LAI', 'CVI', 'NDMI']:
                if change_val_status > threshold_status: return "<span class='status-badge status-positive'>رشد/بهبود</span>"
                elif change_val_status < -threshold_status: return "<span class='status-badge status-negative'>تنش/کاهش</span>"
                else: return "<span class='status-badge status-neutral'>ثابت</span>"
            elif index_name_col_status in ['MSI']:
                if change_val_status < -threshold_status: return "<span class='status-badge status-positive'>بهبود (تنش کمتر)</span>"
                elif change_val_status > threshold_status: return "<span class='status-badge status-negative'>تنش بیشتر</span>"
                else: return "<span class='status-badge status-neutral'>ثابت</span>"
            return "<span class='status-badge status-neutral'>نامشخص</span>"


        ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(lambda row: determine_status_html(row, selected_index), axis=1)
        df_display = ranking_df_sorted.copy()
        cols_to_format_display = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر', 'مساحت (هکتار)']
        for col_fmt_dsp in cols_to_format_display:
            if col_fmt_dsp in df_display.columns:
                 df_display[col_fmt_dsp] = df_display[col_fmt_dsp].apply(lambda x: f"{float(x):.3f}" if pd.notna(x) and isinstance(x, (int, float)) else ("N/A" if pd.isna(x) else str(x)))
        st.markdown(f"<div class='dataframe-container'>{df_display.to_html(escape=False, index=True, classes='styled-table')}</div>", unsafe_allow_html=True)

        st.subheader("📊 خلاصه وضعیت مزارع")
        count_positive_summary = sum(1 for s in ranking_df_sorted['وضعیت'] if 'status-positive' in s)
        count_neutral_summary = sum(1 for s in ranking_df_sorted['وضعیت'] if 'status-neutral' in s and 'بدون داده' not in s and 'خطا' not in s)
        count_negative_summary = sum(1 for s in ranking_df_sorted['وضعیت'] if 'status-negative' in s)
        count_nodata_summary = sum(1 for s in ranking_df_sorted['وضعیت'] if 'بدون داده' in s or 'خطا' in s or 'نامشخص' in s)

        col1_sum, col2_sum, col3_sum, col4_sum = st.columns(4)
        with col1_sum: st.metric("🟢 بهبود/رشد", count_positive_summary)
        with col2_sum: st.metric("⚪ ثابت", count_neutral_summary)
        with col3_sum: st.metric("🔴 تنش/کاهش", count_negative_summary)
        with col4_sum: st.metric("❔ بدون داده/خطا", count_nodata_summary)

        st.info("""**توضیحات وضعیت:** 🟢 بهبود/رشد  ⚪ ثابت  🔴 تنش/کاهش  ❔ بدون داده/خطا""")
        
        def extract_status_text(html_badge):
            if 'رشد/بهبود' in html_badge: return 'رشد/بهبود'
            if 'تنش کمتر' in html_badge: return 'بهبود (تنش کمتر)'
            if 'ثابت' in html_badge: return 'ثابت'
            if 'تنش/کاهش' in html_badge: return 'تنش/کاهش'
            if 'تنش شدید' in html_badge: return 'تنش شدید'
            if 'بدون داده' in html_badge: return 'بدون داده'
            if 'خطا در داده' in html_badge: return 'خطا در داده'
            return 'نامشخص'

        csv_data_dl = ranking_df_sorted.copy()
        csv_data_dl['وضعیت'] = csv_data_dl['وضعیت'].apply(extract_status_text)
        csv_output = csv_data_dl.to_csv(index=True).encode('utf-8-sig')
        st.download_button(
            label="📥 دانلود جدول رتبه‌بندی (CSV)", data=csv_output,
            file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv', mime='text/csv',
        )
    else:
        st.info(f"داده‌ای برای جدول رتبه‌بندی بر اساس {selected_index} در این بازه زمانی یافت نشد.")
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    # Glassmorphism Card (Tab2) - FAB removed
    st.markdown(f"""
    <div class='glass-card'>
        <span class='glass-icon'>🗺️</span>
        <div>
            <div style='font-size:1.18em; font-weight:600;'>نمایش نقشه و نمودارها</div>
            <div style='font-size:1em;'>شاخص انتخابی: <b>{index_options[selected_index]}</b></div>
            <div style='font-size:0.95em;'>مزرعه: <b>{active_farm_name_display}</b></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    vis_params_map = {
        'NDVI': {'min': 0.0, 'max': 0.9, 'palette': ['#a50026', '#d73027', '#f46d43', '#fdae61', '#fee08b', '#ffffbf', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837']},
        'EVI': {'min': 0.0, 'max': 0.9, 'palette': ['#a50026', '#d73027', '#f46d43', '#fdae61', '#fee08b', '#ffffbf', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837']},
        'NDMI': {'min': -0.5, 'max': 0.8, 'palette': ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#f5f5f5', '#c7eae5', '#80cdc1', '#35978f', '#01665e']},
        'LAI': {'min': 0, 'max': 7, 'palette': ['#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']},
        'MSI': {'min': 0.2, 'max': 3.0, 'palette': ['#01665e', '#35978f', '#80cdc1', '#c7eae5', '#f5f5f5', '#f6e8c3', '#dfc27d', '#bf812d', '#8c510a']},
        'CVI': {'min': 0, 'max': 25, 'palette': ['#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']},
    }
    
    map_center_lat_folium, map_center_lon_folium, initial_zoom_map_val_folium = INITIAL_LAT, INITIAL_LON, INITIAL_ZOOM
    if active_farm_geom: # This is now a polygon for single farm, or bounding box for all
        try:
            # Center map on the centroid of the active geometry (polygon or bounding box)
            if active_farm_geom.coordinates(): # Check if coordinates exist (it might be an empty geometry if creation failed)
                 centroid_coords = active_farm_geom.centroid(maxError=1).coordinates().getInfo()
                 map_center_lon_folium, map_center_lat_folium = centroid_coords[0], centroid_coords[1]
            
            if selected_farm_name != "همه مزارع": # Single farm selected (polygon)
                 initial_zoom_map_val_folium = 15 # Zoom closer for a single farm polygon
            # else: "همه مزارع" (bounding box), use default INITIAL_ZOOM or adjust based on bounds

        except Exception: pass # Keep initial map center on error (e.g. if getInfo fails)

    m = geemap.Map(location=[map_center_lat_folium, map_center_lon_folium], zoom=initial_zoom_map_val_folium, add_google_map=True)
    m.add_basemap("HYBRID")
    m.add_basemap("SATELLITE")

    if active_farm_geom:
        gee_image_current_map, error_msg_current_map = get_processed_image(
            active_farm_geom, start_date_current_str, end_date_current_str, selected_index
        )
        if gee_image_current_map:
            try:
                m.addLayer(
                    gee_image_current_map, vis_params_map.get(selected_index, {}),
                    f"{selected_index} ({start_date_current_str} to {end_date_current_str})"
                )
                palette_map_lgd = vis_params_map.get(selected_index, {}).get('palette', []) # Legend logic same as before
                legend_html_content = ""
                if palette_map_lgd:
                    if selected_index in ['NDVI', 'EVI', 'LAI', 'CVI']:
                        legend_html_content = f'<p style="margin:0; background-color:{palette_map_lgd[-1]}; color:white; padding: 2px 5px; border-radius:3px;">بالا (مطلوب)</p>' \
                                              f'<p style="margin:0; background-color:{palette_map_lgd[len(palette_map_lgd)//2]}; color:black; padding: 2px 5px; border-radius:3px;">متوسط</p>' \
                                              f'<p style="margin:0; background-color:{palette_map_lgd[0]}; color:white; padding: 2px 5px; border-radius:3px;">پایین (نامطلوب)</p>'
                    elif selected_index == 'NDMI':
                         legend_html_content = f'<p style="margin:0; background-color:{palette_map_lgd[-1]}; color:white; padding: 2px 5px; border-radius:3px;">مرطوب</p>' \
                                               f'<p style="margin:0; background-color:{palette_map_lgd[0]}; color:black; padding: 2px 5px; border-radius:3px;">خشک</p>'
                    elif selected_index == 'MSI':
                         legend_html_content = f'<p style="margin:0; background-color:{palette_map_lgd[0]}; color:white; padding: 2px 5px; border-radius:3px;">تنش کم (مرطوب)</p>' \
                                               f'<p style="margin:0; background-color:{palette_map_lgd[-1]}; color:black; padding: 2px 5px; border-radius:3px;">تنش زیاد (خشک)</p>'

                if legend_html_content:
                    legend_title_map = index_options[selected_index].split('(')[0].strip()
                    legend_html = f'''
                     <div style="position: fixed; bottom: 50px; left: 10px; width: auto; 
                                background-color: var(--container-background-color); opacity: 0.85; z-index:1000; padding: 10px; border-radius:8px;
                                font-family: 'Vazirmatn', sans-serif; font-size: 0.9em; box-shadow: 0 2px 5px rgba(0,0,0,0.2); color: var(--text-color);">
                       <p style="margin:0 0 8px 0; font-weight:bold; color:var(--primary-color);">راهنمای {legend_title_map}</p>
                       {legend_html_content}
                     </div>'''
                    m.get_root().html.add_child(folium.Element(legend_html))

                if active_farm_name_display == "همه مزارع":
                     for _, farm_row_map in filtered_farms_df.iterrows():
                         # Display marker at centroid for "همه مزارع" view
                         # Centroids were pre-calculated in load_farm_data for pandas df (now WGS84)
                         centroid_lon_map = farm_row_map.get('centroid_lon')
                         centroid_lat_map = farm_row_map.get('centroid_lat')
                         if pd.notna(centroid_lon_map) and pd.notna(centroid_lat_map):
                             folium.Marker(
                                 location=[centroid_lat_map, centroid_lon_map],
                                 popup=f"<b>{farm_row_map['مزرعه']}</b><br>اداره: {farm_row_map.get('اداره', 'N/A')}<br>گروه: {farm_row_map.get('گروه', 'N/A')}",
                                 tooltip=farm_row_map['مزرعه'], icon=folium.Icon(color='royalblue', icon='leaf', prefix='fa')
                             ).add_to(m)
                # For a single selected farm, its boundary is drawn. A marker at centroid can also be added if desired.
                elif selected_farm_name != "همه مزارع" and active_farm_centroid_for_point_ops:
                     try:
                         point_coords_map = active_farm_centroid_for_point_ops.coordinates().getInfo()
                         folium.Marker(
                             location=[point_coords_map[1], point_coords_map[0]], tooltip=f"مرکز مزرعه: {active_farm_name_display}",
                             icon=folium.Icon(color='crimson', icon='map-marker', prefix='fa')
                         ).add_to(m)
                     except Exception as e_marker:
                         st.caption(f"نکته: نتوانست نشانگر مرکز مزرعه را اضافه کند: {e_marker}")
                m.add_layer_control()
            except Exception as map_err: st.error(f"خطا در افزودن لایه به نقشه: {map_err}\n{traceback.format_exc()}")
        else: st.warning(f"تصویری برای نمایش روی نقشه یافت نشد. {error_msg_current_map}")
        st_folium(m, width=None, height=500, use_container_width=True, returned_objects=[])
    else: st.warning("هندسه مزرعه برای نمایش نقشه انتخاب نشده است.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.subheader(f"📊 نمودار روند زمانی شاخص {index_options[selected_index]} برای '{active_farm_name_display}'")
    if active_farm_name_display == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را برای نمایش نمودار سری زمانی انتخاب کنید.")
    # Check if a single farm is selected AND its geometry is available for GEE operations
    elif selected_farm_name != "همه مزارع" and active_farm_geom:
        ts_end_date_chart = today.strftime('%Y-%m-%d')
        ts_start_date_chart_user = st.date_input("تاریخ شروع برای سری زمانی:", 
            value=today - datetime.timedelta(days=365),
            min_value=datetime.date(2017,1,1), max_value=today - datetime.timedelta(days=30),
            key="ts_start_date_chart", help="بازه زمانی حداقل ۳۰ روز و حداکثر ۲ سال توصیه می‌شود."
        )
        if st.button("📈 نمایش/به‌روزرسانی نمودار سری زمانی", key="btn_ts_chart_show"):
            max_days_chart = 365 * 2
            if (today - ts_start_date_chart_user).days > max_days_chart:
                st.warning(f"بازه زمانی به ۲ سال محدود شد.")
                ts_start_date_chart_user = today - datetime.timedelta(days=max_days_chart)

            with st.spinner(f"⏳ در حال دریافت و ترسیم سری زمانی..."):
                ts_df_chart, ts_error_chart = get_index_time_series(
                    active_farm_geom, selected_index, # استفاده از کل پلیگون برای محاسبه دقیق
                    start_date_str=ts_start_date_chart_user.strftime('%Y-%m-%d'),
                    end_date_str=ts_end_date_chart
                )
                if ts_error_chart: st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error_chart}")
                elif not ts_df_chart.empty:
                    fig_chart = px.line(ts_df_chart, y=selected_index, markers=True,
                                  title=f"روند زمانی {index_options[selected_index]} برای '{active_farm_name_display}'",
                                  labels={'date': 'تاریخ', selected_index: index_options[selected_index]})
                    fig_chart.update_layout(
                        font=dict(family="Vazirmatn", color="var(--text-color)"),
                        xaxis_title="تاریخ", yaxis_title=index_options[selected_index],
                        plot_bgcolor="var(--container-background-color)", 
                        paper_bgcolor="var(--container-background-color)",
                        hovermode="x unified"
                    )
                    fig_chart.update_traces(line=dict(color="var(--accent-color)", width=2.5), marker=dict(color="var(--primary-color)", size=6))
                    st.plotly_chart(fig_chart, use_container_width=True)
                else: st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} یافت نشد.")
    else: # Handles "همه مزارع" or if single farm's geometry could not be determined
        st.warning("نمودار سری زمانی فقط برای مزارع منفرد (با هندسه معتبر) قابل نمایش است.")
    st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.subheader("🤖 تحلیل هوشمند با Gemini")
    st.markdown("پاسخ‌های هوشمند و گزارش‌های تحلیلی با هوش مصنوعی")
    # The ai-fadein-card div was removed. Content is now directly in tab3.

    if not gemini_model:
        st.warning("⚠️ قابلیت‌های هوشمند Gemini با وارد کردن صحیح کلید API در کد فعال می‌شوند.")
    else:
        # --- Data Preparation for Tab 3 ---
        # Ensure ranking_df and its summaries are available for Gemini analyses in tab3
        # It will use cache if already computed in tab1
        # Active variables from sidebar: filtered_farms_df, selected_index,
        # start_date_current_str, end_date_current_str, start_date_previous_str, end_date_previous_str
        
        # Make sure all variables needed by calculate_weekly_indices_for_ranking_table are defined
        # These should be available from the sidebar scope
        # Example: filtered_farms_df, selected_index, start_date_current_str, etc.

        ranking_df_tab3, calculation_errors_tab3 = calculate_weekly_indices_for_ranking_table(
            filtered_farms_df, selected_index,
            start_date_current_str, end_date_current_str,
            start_date_previous_str, end_date_previous_str
        )

        ranking_df_sorted_tab3 = pd.DataFrame()
        count_positive_summary_tab3 = 0
        count_neutral_summary_tab3 = 0
        count_negative_summary_tab3 = 0
        count_nodata_summary_tab3 = 0

        if not ranking_df_tab3.empty:
            ascending_sort_tab3 = selected_index in ['MSI'] # True for MSI (lower is better for change, but higher value is worse)
            # For ranking, we sort by current value. For 'critical', we might look at 'change'.
            
            # Create a temporary column for sorting by 'change' if it's a positive-is-good index, to get worst changes first
            # Or for negative-is-good index, to get worst (largest positive) changes first.
            # This is complex. Let's stick to sorting by current value for now, Gemini prompt will handle selection.
            ranking_df_sorted_tab3 = ranking_df_tab3.sort_values(
                by=f'{selected_index} (هفته جاری)', ascending=ascending_sort_tab3, na_position='last'
            ).reset_index(drop=True)
            ranking_df_sorted_tab3.index = ranking_df_sorted_tab3.index + 1 # Start ranking from 1
            ranking_df_sorted_tab3.index.name = 'رتبه'
            
            # Add HTML status for display and text status for prompts
            ranking_df_sorted_tab3['وضعیت_html'] = ranking_df_sorted_tab3.apply(lambda row: determine_status_html(row, selected_index), axis=1)
            ranking_df_sorted_tab3['وضعیت'] = ranking_df_sorted_tab3['وضعیت_html'].apply(extract_status_text)

            # Recalculate summary counts for tab3 context
            count_positive_summary_tab3 = sum(1 for s in ranking_df_sorted_tab3['وضعیت_html'] if 'status-positive' in s)
            count_neutral_summary_tab3 = sum(1 for s in ranking_df_sorted_tab3['وضعیت_html'] if 'status-neutral' in s and 'بدون داده' not in s and 'خطا' not in s)
            count_negative_summary_tab3 = sum(1 for s in ranking_df_sorted_tab3['وضعیت_html'] if 'status-negative' in s)
            count_nodata_summary_tab3 = sum(1 for s in ranking_df_sorted_tab3['وضعیت_html'] if 'بدون داده' in s or 'خطا' in s or 'نامشخص' in s)
        else:
            # Ensure essential columns exist even if empty for downstream code
            essential_cols = ['مزرعه', 'وضعیت_html', 'وضعیت', f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
            ranking_df_sorted_tab3 = pd.DataFrame(columns=essential_cols)
            count_nodata_summary_tab3 = len(filtered_farms_df) if filtered_farms_df is not None else 0


        # --- Shared Context Strings for Gemini in Tab 3 ---
        farm_details_for_gemini_tab3 = ""
        analysis_basis_str_gemini_tab3 = "تحلیل شاخص‌ها بر اساس کل مساحت مزارع انجام می‌شود و از مرز دقیق هندسی هر مزرعه (چندضلعی) برای محاسبه استفاده می‌شود. این روش نسبت به استفاده از نقطه مرکزی، دقت بیشتری دارد." # Updated basis
        if active_farm_name_display != "همه مزارع":
            farm_details_for_gemini_tab3 = f"مزرعه مورد نظر: '{active_farm_name_display}'.\n"
            # active_farm_area_ha_display is now "N/A" or GEE calculated.
            if isinstance(active_farm_area_ha_display, (int, float)):
                farm_details_for_gemini_tab3 += f"مساحت محاسبه‌شده (تخمینی با GEE): {active_farm_area_ha_display:,.2f} هکتار.\n"
            else: # Could be "N/A", "خطا در محاسبه", etc.
                farm_details_for_gemini_tab3 += f"مساحت: {active_farm_area_ha_display}.\n"
            
            # Get other details like 'واریته', 'اداره', 'گروه', 'سن' if available from filtered_farms_df
            if filtered_farms_df is not None and not filtered_farms_df.empty:
                 csv_farm_details_tab3_series_df = filtered_farms_df[filtered_farms_df['مزرعه'] == active_farm_name_display]
                 if not csv_farm_details_tab3_series_df.empty:
                     csv_farm_detail_row = csv_farm_details_tab3_series_df.iloc[0]
                     farm_details_for_gemini_tab3 += f"واریته (از CSV): {csv_farm_detail_row.get('واریته', 'N/A')}.\n"
                     farm_details_for_gemini_tab3 += f"اداره (از CSV): {csv_farm_detail_row.get('اداره', 'N/A')}.\n"
                     farm_details_for_gemini_tab3 += f"گروه (از CSV): {csv_farm_detail_row.get('گروه', 'N/A')}.\n"
                     farm_details_for_gemini_tab3 += f"سن (از CSV): {csv_farm_detail_row.get('سن', 'N/A')}.\n"


        # --- 1. Intelligent Q&A ---
        # Wrap this section in gemini-card and add a header
        st.markdown("<div class='gemini-card'>", unsafe_allow_html=True) # Start gemini-card
        with st.expander("💬 پرسش و پاسخ هوشمند", expanded=True):
            st.markdown("""
            <div class='gemini-card-header'>
                <div class='gemini-card-icon'>💬</div>
                <h3 class='gemini-card-title'>پرسش و پاسخ هوشمند</h3>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("##### سوال خود را در مورد وضعیت عمومی مزارع یا یک مزرعه خاص بپرسید.") # Keep descriptive text
            user_farm_q_gemini = st.text_area(
                f"سوال شما درباره '{active_farm_name_display}' یا مزارع روز '{selected_day}' (شاخص: {index_options[selected_index]}):", 
                key="gemini_farm_q_text_tab3", 
                height=100
            )
            if st.button("✉️ ارسال سوال به Gemini", key="btn_gemini_farm_q_send_tab3"):
                if not user_farm_q_gemini:
                    st.info("لطفاً سوال خود را وارد کنید.")
                else:
                    with st.container(): # Use a container for the spinner and response
                        st.markdown("<div class='loading-animation'><div class='loading-dot'></div><div class='loading-dot'></div><div class='loading-dot'></div></div>", unsafe_allow_html=True)
                        st.info("⏳ در حال پردازش پاسخ با Gemini...")
                        
                        prompt_gemini_q = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. {analysis_basis_str_gemini_tab3}\n"
                        context_data_gemini_q = ""
                        if active_farm_name_display != "همه مزارع":
                            context_data_gemini_q += farm_details_for_gemini_tab3
                            farm_data_for_prompt_q = pd.DataFrame()
                            if not ranking_df_sorted_tab3.empty:
                                farm_data_for_prompt_q = ranking_df_sorted_tab3[ranking_df_sorted_tab3['مزرعه'] == active_farm_name_display]
                            
                            if not farm_data_for_prompt_q.empty:
                                current_farm_data = farm_data_for_prompt_q.iloc[0]
                                status_text_gemini_q = current_farm_data['وضعیت']
                                current_val_str_gemini_q = f"{current_farm_data[f'{selected_index} (هفته جاری)']:.3f}" if pd.notna(current_farm_data[f'{selected_index} (هفته جاری)']) else "N/A"
                                prev_val_str_gemini_q = f"{current_farm_data[f'{selected_index} (هفته قبل)']:.3f}" if pd.notna(current_farm_data[f'{selected_index} (هفته قبل)']) else "N/A"
                                change_str_gemini_q = f"{current_farm_data['تغییر']:.3f}" if pd.notna(current_farm_data['تغییر']) else "N/A"
                                
                                context_data_gemini_q += (
                                    f"داده‌های مزرعه '{active_farm_name_display}' برای شاخص {index_options[selected_index]} (هفته منتهی به {end_date_current_str}):\n"
                                    f"- مقدار هفته جاری: {current_val_str_gemini_q}\n"
                                    f"- مقدار هفته قبل: {prev_val_str_gemini_q}\n"
                                    f"- تغییر: {change_str_gemini_q}\n"
                                    f"- وضعیت کلی: {status_text_gemini_q}\n"
                                )
                            else:
                                context_data_gemini_q += f"داده‌های عددی هفتگی برای شاخص '{selected_index}' جهت مزرعه '{active_farm_name_display}' در جدول رتبه‌بندی یافت نشد.\n"
                            prompt_gemini_q += f"کاربر در مورد '{active_farm_name_display}' پرسیده: '{user_farm_q_gemini}'.\n{context_data_gemini_q}پاسخ جامع و مفید به فارسی ارائه دهید."
                        else: # "همه مزارع"
                            context_data_gemini_q = f"وضعیت کلی مزارع برای روز '{selected_day}' و شاخص '{index_options[selected_index]}'. تعداد {len(filtered_farms_df) if filtered_farms_df is not None else 0} مزرعه فیلتر شده‌اند."
                            if not ranking_df_sorted_tab3.empty:
                                context_data_gemini_q += (
                                    f"\nخلاصه وضعیت مزارع (نقاط مرکزی CSV) برای شاخص {selected_index}:\n"
                                    f"- بهبود/رشد: {count_positive_summary_tab3}\n"
                                    f"- ثابت: {count_neutral_summary_tab3}\n"
                                    f"- تنش/کاهش: {count_negative_summary_tab3}\n"
                                    f"- بدون داده/خطا: {count_nodata_summary_tab3}\n"
                                )
                            prompt_gemini_q += f"کاربر در مورد وضعیت کلی مزارع پرسیده: '{user_farm_q_gemini}'.\n{context_data_gemini_q}پاسخ جامع و مفید به فارسی ارائه دهید."
                        
                        response_gemini_q = ask_gemini(prompt_gemini_q)
                        st.markdown(f"<div class='gemini-response-default'>{response_gemini_q}</div>", unsafe_allow_html=True)
                        st.empty() # Clear spinner and info

        st.markdown("</div>", unsafe_allow_html=True) # End gemini-card

        # --- 2. Automatic Weekly Report ---
        # Wrap this section in gemini-card and add a header
        st.markdown("<div class='gemini-card'>", unsafe_allow_html=True) # Start gemini-card
        with st.expander("📄 تولید گزارش خودکار هفتگی", expanded=False):
            st.markdown("""
            <div class='gemini-card-header'>
                <div class='gemini-card-icon'>📄</div>
                <h3 class='gemini-card-title'>تولید گزارش خودکار هفتگی</h3>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"##### تولید گزارش هفتگی برای مزرعه '{active_farm_name_display}' بر اساس شاخص '{index_options[selected_index]}'.") # Keep descriptive text
            if active_farm_name_display == "همه مزارع":
                st.info("لطفاً یک مزرعه خاص را از سایدبار برای تولید گزارش انتخاب کنید.")
            else:
                farm_data_for_report_gemini = pd.DataFrame()
                if not ranking_df_sorted_tab3.empty:
                    farm_data_for_report_gemini = ranking_df_sorted_tab3[ranking_df_sorted_tab3['مزرعه'] == active_farm_name_display]

                if farm_data_for_report_gemini.empty:
                    st.info(f"داده‌های رتبه‌بندی برای '{active_farm_name_display}' (شاخص: {selected_index}) جهت تولید گزارش موجود نیست.")
                elif st.button(f"📝 تولید گزارش برای '{active_farm_name_display}'", key="btn_gemini_report_gen_tab3"):
                    with st.container(): # Use a container for the spinner and response
                        st.markdown("<div class='loading-animation'><div class='loading-dot'></div><div class='loading-dot'></div><div class='loading-dot'></div></div>", unsafe_allow_html=True)
                        st.info(f"⏳ در حال تولید گزارش برای '{active_farm_name_display}'...")

                        report_context_gemini = farm_details_for_gemini_tab3
                        current_farm_report_data = farm_data_for_report_gemini.iloc[0]
                        current_val_str_rep = f"{current_farm_report_data[f'{selected_index} (هفته جاری)']:.3f}" if pd.notna(current_farm_report_data[f'{selected_index} (هفته جاری)']) else "N/A"
                        prev_val_str_rep = f"{current_farm_report_data[f'{selected_index} (هفته قبل)']:.3f}" if pd.notna(current_farm_report_data[f'{selected_index} (هفته قبل)']) else "N/A"
                        change_str_rep = f"{current_farm_report_data['تغییر']:.3f}" if pd.notna(current_farm_report_data['تغییر']) else "N/A"
                        status_text_rep = current_farm_report_data['وضعیت']
                        
                        report_context_gemini += (
                            f"داده‌های شاخص {index_options[selected_index]} برای '{active_farm_name_display}' (هفته منتهی به {end_date_current_str}):\n"
                            f"- جاری: {current_val_str_rep}\n"
                            f"- قبلی: {prev_val_str_rep}\n"
                            f"- تغییر: {change_str_rep}\n"
                            f"- وضعیت: {status_text_rep}\n"
                        )
                        prompt_rep = (
                            f"شما یک دستیار هوشمند برای تهیه گزارش‌های کشاورزی هستید. لطفاً یک گزارش توصیفی و ساختاریافته به زبان فارسی در مورد وضعیت '{active_farm_name_display}' برای هفته منتهی به {end_date_current_str} تهیه کنید.\n"
                            f"اطلاعات موجود:\n{report_context_gemini}{analysis_basis_str_gemini_tab3}\n"
                            f"در گزارش به موارد فوق اشاره کنید، تحلیل مختصری از وضعیت (با توجه به شاخص {selected_index}) ارائه دهید و در صورت امکان، پیشنهادهای کلی (نه تخصصی و قطعی) برای بهبود یا حفظ وضعیت مطلوب بیان کنید. گزارش باید رسمی، دارای عنوان، تاریخ، و بخش‌های مشخص (مقدمه، وضعیت فعلی، تحلیل، پیشنهادات) و قابل فهم برای مدیران کشاورزی باشد."
                        )
                        response_rep = ask_gemini(prompt_rep, temperature=0.6, top_p=0.9)
                        st.markdown(f"### گزارش هفتگی '{active_farm_name_display}' (شاخص {index_options[selected_index]})")
                        st.markdown(f"**تاریخ گزارش:** {datetime.date.today().strftime('%Y-%m-%d')}")
                        st.markdown(f"**بازه زمانی:** {start_date_current_str} الی {end_date_current_str}")
                        st.markdown(f"<div class='gemini-response-report'>{response_rep}</div>", unsafe_allow_html=True)
                        st.empty() # Clear spinner and info
        
        st.markdown("</div>", unsafe_allow_html=True) # End gemini-card

        # --- 3. Prioritization Assistant (NEW) ---
        # Wrap this section in gemini-card and add a header
        st.markdown("<div class='gemini-card'>", unsafe_allow_html=True) # Start gemini-card
        with st.expander("⚠️ دستیار اولویت‌بندی مزارع بحرانی", expanded=False):
            st.markdown("""
            <div class='gemini-card-header'>
                <div class='gemini-card-icon'>🚨</div>
                <h3 class='gemini-card-title'>دستیار اولویت‌بندی مزارع بحرانی</h3>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"##### شناسایی مزارع نیازمند توجه فوری بر اساس شاخص '{index_options[selected_index]}'.") # Keep descriptive text
            if count_negative_summary_tab3 == 0 and (not ranking_df_sorted_tab3.empty):
                st.info(f"بر اساس شاخص '{index_options[selected_index]}'، هیچ مزرعه‌ای در وضعیت 'تنش/کاهش' برای روز '{selected_day}' شناسایی نشد.")
            elif ranking_df_sorted_tab3.empty :
                 st.info(f"داده‌ای برای رتبه‌بندی و اولویت‌بندی مزارع بر اساس شاخص '{index_options[selected_index]}' یافت نشد.")
            elif st.button(f"🔍 تحلیل و اولویت‌بندی مزارع بحرانی", key="btn_gemini_priority_assist_tab3"):
                with st.container(): # Use a container for the spinner and response
                    st.markdown("<div class='loading-animation'><div class='loading-dot'></div><div class='loading-dot'></div><div class='loading-dot'></div></div>", unsafe_allow_html=True)
                    st.info("⏳ در حال تحلیل اولویت‌بندی با Gemini...")

                    problematic_farms_df = ranking_df_sorted_tab3[
                        ranking_df_sorted_tab3['وضعیت'].str.contains('تنش|کاهش', case=False, na=False)
                    ]
                    # Sort by 'تغییر' column to highlight most significant changes for the prompt context
                    # If index is like NDVI (higher better), sort 'تغییر' ascending (most negative first)
                    # If index is like MSI (higher worse), sort 'تغییر' descending (most positive first)
                    sort_asc_for_change = selected_index not in ['MSI'] 
                    
                    problematic_farms_for_prompt = problematic_farms_df.sort_values(by='تغییر', ascending=sort_asc_for_change)
                                    
                    prompt_priority = f"""شما یک دستیار هوشمند برای اولویت‌بندی در مدیریت مزارع نیشکر هستید.
روز مشاهده: {selected_day}
شاخص مورد بررسی: {index_options[selected_index]} (ماهیت شاخص: {'مقدار بالاتر بهتر است' if selected_index not in ['MSI'] else 'مقدار بالاتر بدتر است (تنش بیشتر)'})
هفته منتهی به: {end_date_current_str}

بر اساس جدول رتبه‌بندی هفتگی، {count_negative_summary_tab3} مزرعه وضعیت 'تنش/کاهش' یا تغییر منفی قابل توجهی را نشان می‌دهند.
اطلاعات حداکثر ۵ مزرعه از این مزارع بحرانی (مرتب شده بر اساس شدت تغییر نامطلوب):
{problematic_farms_for_prompt[['مزرعه', f'{selected_index} (هفته جاری)', 'تغییر', 'وضعیت']].head().to_string(index=False)}

وظیفه شما:
1.  از بین مزارع فوق، حداکثر ۳ مورد از بحرانی‌ترین‌ها را بر اساس شدت وضعیت نامطلوب (مقدار 'تغییر' و مقدار فعلی شاخص) انتخاب کنید.
2.  برای هر مزرعه منتخب:
    الف. نام مزرعه و داده‌های کلیدی آن (مقدار شاخص جاری، تغییر، وضعیت) را ذکر کنید.
    ب. دو یا سه دلیل احتمالی اولیه برای این وضعیت نامطلوب (با توجه به ماهیت شاخص {selected_index}) ارائه دهید. (مثال: برای NDVI پایین: تنش آبی، آفات، بیماری، برداشت اخیر. برای MSI بالا: خشکی، تنش آبی شدید).
    ج. یک یا دو اقدام اولیه پیشنهادی برای بررسی میدانی یا مدیریتی ارائه دهید. (مثال: بررسی سیستم آبیاری، پایش آفات، نمونه برداری خاک/گیاه).
3.  اگر هیچ مزرعه‌ای وضعیت بحرانی ندارد (که در اینجا قاعدتا نباید اینطور باشد چون دکمه فعال شده)، این موضوع را اعلام کنید.

پاسخ باید به فارسی، ساختاریافته (مثلاً با استفاده از لیست‌ها یا بخش‌بندی برای هر مزرعه)، و کاربردی باشد.
{analysis_basis_str_gemini_tab3}
"""
                    response_priority = ask_gemini(prompt_priority, temperature=0.5)
                    st.markdown(f"<div class='gemini-response-analysis'>{response_priority}</div>", unsafe_allow_html=True)
                    st.empty() # Clear spinner and info
        
        st.markdown("</div>", unsafe_allow_html=True) # End gemini-card

        # --- 4. Intelligent Timeseries Analysis ---
        # Wrap this section in gemini-card and add a header
        st.markdown("<div class='gemini-card'>", unsafe_allow_html=True) # Start gemini-card
        with st.expander(f"📉 تحلیل هوشمند روند زمانی شاخص {index_options[selected_index]}", expanded=False):
            st.markdown("""
            <div class='gemini-card-header'>
                <div class='gemini-card-icon'>📉</div>
                <h3 class='gemini-card-title'>تحلیل هوشمند روند زمانی</h3>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"##### تحلیل روند زمانی شاخص '{index_options[selected_index]}' برای مزرعه '{active_farm_name_display}'.") # Keep descriptive text
            if active_farm_name_display == "همه مزارع":
                st.info("لطفاً یک مزرعه خاص را از سایدبار برای تحلیل سری زمانی انتخاب کنید.")
            elif active_farm_geom:
                if st.button(f"🔍 تحلیل روند زمانی {selected_index} برای '{active_farm_name_display}' با Gemini", key="btn_gemini_timeseries_an_tab3"):
                    ts_end_date_gemini_ts = today.strftime('%Y-%m-%d')
                    ts_start_date_gemini_ts = (today - datetime.timedelta(days=180)).strftime('%Y-%m-%d') # 6 months
                    
                    with st.container(): # Use a container for the spinner and response
                        st.markdown("<div class='loading-animation'><div class='loading-dot'></div><div class='loading-dot'></div><div class='loading-dot'></div></div>", unsafe_allow_html=True)
                        st.info(f"⏳ در حال دریافت داده‌های سری زمانی برای Gemini...")
                        
                        # get_index_time_series is cached
                        ts_df_gemini_ts, ts_error_gemini_ts = get_index_time_series(
                            active_farm_geom, selected_index, # Use entire farm polygon
                            start_date_str=ts_start_date_gemini_ts, end_date_str=ts_end_date_gemini_ts
                        )
                    
                    if ts_error_gemini_ts:
                        st.error(f"خطا در دریافت داده‌های سری زمانی برای Gemini: {ts_error_gemini_ts}")
                        st.empty() # Clear spinner and info
                    elif not ts_df_gemini_ts.empty:
                        ts_summary_gemini = f"داده‌های سری زمانی شاخص {index_options[selected_index]} برای '{active_farm_name_display}' در 6 ماه گذشته ({ts_start_date_gemini_ts} تا {ts_end_date_gemini_ts}):\n"
                        # Sample data for conciseness in prompt, but provide key stats
                        sample_freq_gemini = max(1, len(ts_df_gemini_ts) // 10) # Max 10 samples + ends
                        ts_sampled_data_str = ts_df_gemini_ts.iloc[::sample_freq_gemini][selected_index].to_string(header=True, index=True)
                        if len(ts_df_gemini_ts) > 1:
                             ts_sampled_data_str += f"\n...\n{ts_df_gemini_ts[[selected_index]].iloc[-1].to_string(header=False)}" # Ensure last point is included

                        ts_summary_gemini += ts_sampled_data_str
                        ts_summary_gemini += f"\nمقدار اولیه حدود {ts_df_gemini_ts[selected_index].iloc[0]:.3f} و نهایی حدود {ts_df_gemini_ts[selected_index].iloc[-1]:.3f}."
                        ts_summary_gemini += f"\n میانگین: {ts_df_gemini_ts[selected_index].mean():.3f}, کمترین: {ts_df_gemini_ts[selected_index].min():.3f}, بیشترین: {ts_df_gemini_ts[selected_index].max():.3f}."
                        
                        prompt_ts_an = (
                            f"شما یک تحلیلگر داده‌های کشاورزی خبره هستید. {analysis_basis_str_gemini_tab3}\n"
                            f" بر اساس داده‌های سری زمانی زیر برای شاخص {index_options[selected_index]} مزرعه '{active_farm_name_display}' طی 6 ماه گذشته:\n{ts_summary_gemini}\n"
                            f"وظایف تحلیلگر:\n"
                            f"۱. روند کلی تغییرات شاخص را توصیف کنید (مثلاً صعودی، نزولی، نوسانی، ثابت).\n"
                            f"۲. آیا دوره‌های خاصی از رشد قابل توجه، کاهش شدید یا ثبات طولانی مدت مشاهده می‌شود؟ اگر بله، به تاریخ‌های تقریبی اشاره کنید.\n"
                            f"۳. با توجه به ماهیت شاخص '{selected_index}' ({'مقدار بالاتر بهتر است' if selected_index not in ['MSI'] else 'مقدار بالاتر بدتر است (تنش بیشتر)'}) و روند مشاهده شده، چه تفسیرهای اولیه‌ای در مورد سلامت و وضعیت گیاه می‌توان داشت؟\n"
                            f"۴. چه نوع مشاهدات میدانی یا اطلاعات تکمیلی می‌تواند به درک بهتر این روند و تأیید تحلیل شما کمک کند?\n"
                            f"پاسخ به فارسی، ساختاریافته، تحلیلی و کاربردی باشد."
                        )
                        response_ts_an = ask_gemini(prompt_ts_an, temperature=0.5)
                        st.markdown(f"<div class='gemini-response-analysis'>{response_ts_an}</div>", unsafe_allow_html=True)
                        st.empty() # Clear spinner and info
                    else:
                        st.info(f"داده‌ای برای تحلیل سری زمانی {selected_index} برای '{active_farm_name_display}' در 6 ماه گذشته یافت نشد.")
            else: # Not a single farm or no geometry
                 st.info("تحلیل روند زمانی فقط برای یک مزرعه منفرد با مختصات مشخص قابل انجام است.")

        # --- 5. General Q&A ---
        # Wrap this section in gemini-card and add a header
        st.markdown("<div class='gemini-card'>", unsafe_allow_html=True) # Start gemini-card
        with st.expander("🗣️ پرسش و پاسخ عمومی", expanded=False):
            st.markdown("""
            <div class='gemini-card-header'>
                <div class='gemini-card-icon'>❓</div>
                <h3 class='gemini-card-title'>پرسش و پاسخ عمومی</h3>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("##### سوالات عمومی خود را در مورد مفاهیم کشاورزی، شاخص‌های سنجش از دور، نیشکر یا عملکرد این سامانه بپرسید.") # Keep descriptive text
            user_general_q_gemini = st.text_area(
                "سوال عمومی شما:", 
                key="gemini_general_q_text_tab3", 
                height=100
            )
            if st.button("❓ پرسیدن سوال عمومی از Gemini", key="btn_gemini_general_q_send_tab3"):
                if not user_general_q_gemini:
                    st.info("لطفاً سوال خود را وارد کنید.")
                else:
                    with st.container(): # Use a container for the spinner and response
                        st.markdown("<div class='loading-animation'><div class='loading-dot'></div><div class='loading-dot'></div><div class='loading-dot'></div></div>", unsafe_allow_html=True)
                        st.info("⏳ در حال جستجو برای پاسخ با Gemini...")

                        prompt_gen_q = (
                            f"شما یک دانشنامه هوشمند در زمینه کشاورزی (با تمرکز بر نیشکر) و سنجش از دور هستید. "
                            f"لطفاً به سوال زیر که توسط یک کاربر سامانه پایش نیشکر پرسیده شده است، به زبان فارسی پاسخ دهید. "
                            f"سعی کنید پاسخ شما ساده، قابل فهم، دقیق و در حد امکان جامع باشد.\n"
                            f"سوال کاربر: '{user_general_q_gemini}'"
                        )
                        response_gen_q = ask_gemini(prompt_gen_q, temperature=0.4)
                        st.markdown(f"<div class='gemini-response-default'>{response_gen_q}</div>", unsafe_allow_html=True)
                        st.empty() # Clear spinner and info
    
        st.markdown("</div>", unsafe_allow_html=True) # End gemini-card