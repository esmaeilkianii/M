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
from io import BytesIO
import requests
import traceback
from streamlit_folium import st_folium
import base64
import google.generativeai as genai
from shapely.geometry import Polygon
import pyproj
import numpy as np # Import numpy for np.nan

# Define the source CRS (likely UTM Zone 39N for Khuzestan)
# Assuming WGS 84 / UTM zone 39N based on typical data format and region
SOURCE_CRS = "EPSG:32639"
TARGET_CRS = "EPSG:4326" # WGS 84 geographic 2D

transformer = None
try:
    transformer = pyproj.Transformer.from_crs(SOURCE_CRS, TARGET_CRS, always_xy=True)
    print(f"Coordinate transformer created: {SOURCE_CRS} to {TARGET_CRS}")
except pyproj.exceptions.CRSError as e:
    st.error(f"❌ خطای پیکربندی سیستم مختصات: {e}. لطفاً کدهای EPSG {SOURCE_CRS} و {TARGET_CRS} را بررسی کنید.")
except Exception as e:
     st.error(f"❌ خطای ناشناخته در ایجاد تبدیل کننده مختصات: {e}")


# --- HARDCODED GEMINI API KEY (SECURITY RISK - NOT RECOMMENDED) ---
# As requested, the API key is hardcoded here.
# !!! WARNING: This is a security vulnerability. Anyone with access to this code
# !!! can use your API key and potentially incur costs on your account.
# !!! It is strongly recommended to use Streamlit Secrets for API keys.
# !!! https://docs.streamlit.io/develop/concepts/secrets
GEMINI_API_KEY_HARDCODED = "AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ"
# --- END OF HARDCODED API KEY ---


# --- Custom CSS for an Amazing and User-Friendly UI ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded" # Keep sidebar expanded by default
)

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700;900&display=swap');
        @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');
        @import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');

        html, body, .main, .stApp {
            font-family: 'Vazirmatn', sans-serif !important;
            background: linear-gradient(135deg, #e0f7fa 0%, #f8fafc 100%);
            color: #333;
        }

        /* Header styling with animations */
        header {
            position: sticky;
            top: 0;
            z-index: 999;
            animation: fadeIn 0.8s ease-in-out;
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            background: rgba(255, 255, 255, 0.8);
            border-bottom: 1px solid rgba(0, 0, 0, 0.1);
            padding: 0.5rem 0;
            transition: all 0.3s ease;
        }
        
        header:hover {
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }

        /* Dark Mode Enhancements */
        @media (prefers-color-scheme: dark) {
            html, body, .main, .stApp {
                background: linear-gradient(135deg, #1a1f36 0%, #2d3748 100%);
                color: #f8f8f8;
            }
            header {
                background: rgba(30, 41, 59, 0.8);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
            .stTabs [data-baseweb="tab-list"] button [data-baseweb="tab"] {
                color: #bbb !important;
            }
            .stTabs [data-baseweb="tab-list"] button:hover {
                color: #f8f8f8 !important;
            }
            .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
                color: #43cea2 !important;
                border-bottom-color: #43cea2 !important;
            }
            .modern-card {
                background: linear-gradient(135deg, #1a435a 0%, #2a2a2a 100%);
                color: #f8f8f8;
                box-shadow: 0 4px 16px rgba(0,0,0,0.3);
            }
            .status-positive { background-color: #218838; }
            .status-negative { background-color: #c82333; }
            .status-neutral { background-color: #5a6268; color: #fff; }
            .status-nodata { background-color: #d39e00; color: #f8f8f8;}
        }

        h1, h2, h3, h4, h5, h6 {
            color: #185a9d;
            font-weight: 700;
        }
        .stMarkdown h1 {
            color: #185a9d !important;
            animation: fadeInDown 0.5s ease-in-out;
        }

        /* Modern animated cards */
        .modern-card {
            background: linear-gradient(135deg, #43cea2 0%, #185a9d 100%);
            color: white;
            border-radius: 18px;
            padding: 20px;
            margin: 15px 0;
            box-shadow: 0 6px 20px rgba(30,60,114,0.1);
            text-align: center;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            overflow: hidden;
            position: relative;
            animation: fadeIn 0.6s ease-in-out;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .modern-card:hover {
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 15px 30px rgba(30,60,114,0.2);
        }
        .modern-card::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(45deg, transparent, rgba(255,255,255,0.1), transparent);
            transform: rotate(45deg);
            transition: all 1s ease;
            opacity: 0;
        }
        .modern-card:hover::before {
            opacity: 1;
            animation: shine 1.5s ease-in-out;
        }
        .modern-card div:first-child {
            font-size: 1em;
            opacity: 0.9;
            margin-bottom: 8px;
        }
        .modern-card div:last-child {
            font-size: 2em;
            font-weight: 900;
        }

        /* Sidebar enhancements */
        .sidebar-logo {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 2rem;
            padding-top: 1rem;
            animation: pulse 2s infinite;
        }
        .sidebar-logo img {
            width: 100px;
            height: 100px;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(30,60,114,0.15);
            transition: all 0.3s ease;
        }
        .sidebar-logo img:hover {
            transform: rotate(5deg) scale(1.05);
        }
        
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
            border-right: 1px solid rgba(0,0,0,0.1);
            box-shadow: 5px 0 10px rgba(0,0,0,0.05);
        }
        
        @media (prefers-color-scheme: dark) {
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #1e2937 0%, #111827 100%);
                border-right: 1px solid rgba(255,255,255,0.1);
            }
        }

        /* Main logo animation */
        .main-logo {
            width: 55px;
            height: 55px;
            border-radius: 15px;
            margin-left: 15px;
            vertical-align: middle;
            box-shadow: 0 2px 8px rgba(30,60,114,0.1);
            transition: all 0.3s ease;
            animation: bounceIn 1s;
        }
        .main-logo:hover {
            transform: rotate(10deg) scale(1.1);
        }

        /* Tab styling enhancements */
        .stTabs [data-baseweb="tab-list"] {
            gap: 20px;
            border-bottom: 1px solid rgba(0,0,0,0.1);
            padding-bottom: 0;
            margin-bottom: 20px;
        }
        .stTabs [data-baseweb="tab-list"] button {
            background-color: transparent;
            padding: 12px 20px;
            border-radius: 8px 8px 0 0;
            border-bottom: 3px solid transparent;
            transition: all 0.3s ease;
            font-weight: 700;
            color: #555;
            position: relative;
            overflow: hidden;
        }
        .stTabs [data-baseweb="tab-list"] button:hover {
            background-color: rgba(67, 206, 162, 0.1);
            color: #185a9d;
            border-bottom-color: rgba(67, 206, 162, 0.5);
        }
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
            background-color: rgba(67, 206, 162, 0.15);
            border-bottom-color: #43cea2;
            color: #185a9d;
            box-shadow: 0 -2px 8px rgba(30,60,114,0.05);
        }
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"]::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, #43cea2, #185a9d);
            animation: slideInRight 0.3s ease-out;
        }
        .stTabs [data-baseweb="tab-panel"] {
            padding: 25px 5px;
            animation: fadeIn 0.5s ease-in-out;
        }

        /* Status badges enhancements */
        .status-badge {
            display: inline-block;
            padding: 0.4em 0.8em;
            font-size: 0.85em;
            font-weight: bold;
            line-height: 1.2;
            text-align: center;
            white-space: nowrap;
            vertical-align: middle;
            border-radius: 0.5rem;
            color: #fff;
            margin: 3px;
            transition: all 0.3s ease;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            animation: fadeIn 0.5s ease-in-out;
        }
        .status-badge:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .status-positive { 
            background: linear-gradient(90deg, #28a745, #1e7e34);
        }
        .status-negative { 
            background: linear-gradient(90deg, #dc3545, #bd2130);
        }
        .status-neutral { 
            background: linear-gradient(90deg, #6c757d, #5a6268);
            color: #fff;
        }
        .status-nodata { 
            background: linear-gradient(90deg, #ffc107, #d39e00);
            color: #212529;
        }

        /* Table enhancements */
        table {
            border-collapse: separate;
            border-spacing: 0;
            width: 100%;
            margin: 20px 0;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            border-radius: 10px;
            overflow: hidden;
            animation: fadeIn 0.5s ease-in-out;
        }
        
        table thead tr {
            background: linear-gradient(90deg, #43cea2, #185a9d);
            color: white;
        }
        
        table th {
            padding: 12px 15px;
            text-align: right;
            font-weight: bold;
        }
        
        table td {
            padding: 10px 15px;
            border-bottom: 1px solid rgba(0,0,0,0.05);
        }
        
        table tbody tr {
            transition: all 0.3s ease;
        }
        
        table tbody tr:hover {
            background-color: rgba(67, 206, 162, 0.05);
            transform: scale(1.005);
        }
        
        table tbody tr:last-child td {
            border-bottom: none;
        }
        
        /* Button enhancements */
        .stButton > button {
            border-radius: 8px;
            padding: 0.5rem 1rem;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(50, 50, 93, 0.11), 0 1px 3px rgba(0, 0, 0, 0.08);
            border: none;
            background: linear-gradient(135deg, #43cea2 0%, #185a9d 100%);
            color: white;
            position: relative;
            overflow: hidden;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 7px 14px rgba(50, 50, 93, 0.1), 0 3px 6px rgba(0, 0, 0, 0.08);
        }
        
        .stButton > button:active {
            transform: translateY(1px);
        }
        
        .stButton > button::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 5px;
            height: 5px;
            background: rgba(255, 255, 255, 0.5);
            opacity: 0;
            border-radius: 100%;
            transform: scale(1, 1) translate(-50%, -50%);
            transform-origin: 50% 50%;
        }
        
        .stButton > button:hover::after {
            animation: ripple 1s ease-out;
            opacity: 0;
        }
        
        /* Select box enhancements */
        .stSelectbox {
            border-radius: 8px;
            overflow: hidden;
        }
        
        .stSelectbox > div > div[data-baseweb="select"] {
            transition: all 0.3s ease;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        
        .stSelectbox > div > div[data-baseweb="select"]:hover {
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
            transform: translateY(-1px);
        }
        
        /* Animation keyframes */
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes fadeInDown {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        @keyframes slideInRight {
            from { 
                width: 0;
            }
            to {
                width: 100%;
            }
        }
        
        @keyframes bounceIn {
            0% {
                opacity: 0;
                transform: scale(0.3);
            }
            50% {
                opacity: 1;
                transform: scale(1.05);
            }
            70% { transform: scale(0.9); }
            100% { transform: scale(1); }
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }
        
        @keyframes ripple {
            0% {
                transform: scale(0, 0);
                opacity: 0.5;
            }
            100% {
                transform: scale(100, 100);
                opacity: 0;
            }
        }
        
        @keyframes shine {
            0% {
                left: -100%;
                opacity: 0;
            }
            100% {
                left: 100%;
                opacity: 0.3;
            }
        }
    </style>
""", unsafe_allow_html=True)


def status_badge(status: str) -> str:
    """Returns HTML for a status badge with color."""
    if "بهبود" in status or "رشد مثبت" in status or "افزایش رطوبت" in status: # Added NDMI positive
        badge_class = "status-positive"
    elif "تنش" in status or "کاهش" in status or "بدتر شدن" in status or "نیاز" in status: # Added NDMI negative
        badge_class = "status-negative"
    elif "ثابت" in status or "رطوبت ثابت" in status or "پوشش گیاهی پایین" in status or "قابل توجه" in status: # Added NDMI neutral/warning
        badge_class = "status-neutral"
    elif "بدون داده" in status or "N/A" in status:
         badge_class = "status-nodata"
    else:
        badge_class = "status-neutral"

    return f'<span class="status-badge {badge_class}">{status}</span>'

def modern_metric_card(title: str, value: str, icon: str, color: str) -> str:
    """
    Returns a modern styled HTML card for displaying a metric.
    :param title: Title of the metric
    :param value: Value of the metric
    :param icon: FontAwesome icon class (e.g., 'fa-leaf')
    :param color: Accent color for the card background gradient
    :return: HTML string
    """
    return f'''
    <div class="modern-card" style="background: linear-gradient(135deg, {color} 0%, #185a9d 100%);">
        <div>{title} <i class="fa {icon}"></i></div>
        <div>{value}</div>
    </div>
    '''

def modern_progress_bar(progress: float) -> str:
    """
    Returns a modern styled HTML progress bar for Streamlit.
    :param progress: float between 0 and 1
    :return: HTML string
    """
    percent = max(0, min(100, int(progress * 100)))
    color_start = '#dc3545'
    color_mid = '#ffc107'
    color_end = '#28a745'

    if percent <= 50:
        r = int(0xdc + (0xff - 0xdc) * (percent / 50))
        g = int(0x35 + (0xc1 - 0x35) * (percent / 50))
        b = int(0x45 + (0x07 - 0x45) * (percent / 50))
        current_color = f"#{r:02x}{g:02x}{b:02x}"
        background_gradient = f"linear-gradient(90deg, {color_start} 0%, {current_color} 100%)"
    else:
        r = int(0xff + (0x28 - 0xff) * ((percent - 50) / 50))
        g = int(0xc1 + (0xa7 - 0xc1) * ((percent - 50) / 50))
        b = int(0x07 + (0x45 - 0x07) * ((percent - 50) / 50))
        current_color = f"#{r:02x}{g:02x}{b:02x}"
        background_gradient = f"linear-gradient(90deg, {color_mid} 0%, {current_color} 100%)"

    if percent == 100:
        background_gradient = f"linear-gradient(90deg, {color_end} 0%, #1a9850 100%)"


    return f'''
    <div style="width: 100%; background: #e0f7fa; border-radius: 12px; height: 22px; margin: 8px 0; box-shadow: 0 2px 8px rgba(30,60,114,0.08); overflow: hidden; position: relative;">
      <div style="width: {percent}%; background: {background_gradient}; height: 100%; border-radius: 12px; transition: width 0.3s ease-in-out;"></div>
      <span style="position: absolute; left: 50%; top: 0; transform: translateX(-50%); color: #185a9d; font-weight: bold; line-height: 22px; text-shadow: 0 0 2px rgba(255,255,255,0.5); /* Add subtle text shadow for readability */">
          {percent}%
      </span>
    </div>
    '''

st.sidebar.markdown(
    """
    <div class='sidebar-logo'>
        <img src='https://raw.githubusercontent.com/esmaeilkiani13877/MonitoringSugarcane-13/main/logo%20(1).png' alt='لوگو سامانه' />
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div style='display: flex; align-items: center; gap: 16px; margin-bottom: 0.5rem;'>
        <img src='https://raw.githubusercontent.com/esmaeilkiani13877/MonitoringSugarcane-13/main/logo%20(1).png' class='main-logo' alt='لوگو' />
        <h1 style='font-family: Vazirmatn, sans-serif; color: #185a9d; margin: 0;'>سامانه پایش هوشمند نیشکر</h1>
    </div>
    <h4 style='color: #43cea2; margin-top: 0;'>مطالعات کاربردی شرکت کشت و صنعت دهخدا</h4>
    """,
    unsafe_allow_html=True
)

APP_TITLE = "سامانه پایش هوشمند نیشکر"
APP_SUBTITLE = "مطالعات کاربردی شرکت کشت و صنعت دهخدا"
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 12

FARM_DATA_CSV_PATH = 'merged_farm_data_renamed (1).csv'
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'
ANALYSIS_CSV_PATH = 'محاسبات 2.csv'


@st.cache_resource(show_spinner="در حال اتصال به Google Earth Engine...")
def initialize_gee():
    """Initializes Google Earth Engine using the Service Account."""
    try:
        if os.path.exists(SERVICE_ACCOUNT_FILE):
            credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
            print("GEE Initialized Successfully using Service Account File.")
        else:
            try:
                if "gee_auth_json" in st.secrets:
                    auth_info = json.loads(st.secrets["gee_auth_json"])
                    credentials = ee.ServiceAccountCredentials(auth_info['client_email'], None, private_key_id=auth_info['private_key_id'], private_key=auth_info['private_key'], token_uri=auth_info['token_uri'])
                    print("GEE Initialized Successfully using Streamlit Secrets JSON.")
                else:
                     raise ValueError("GEE credentials not found in secrets ('gee_auth_json').")

            except Exception as e:
                 st.error(f"❌ خطا در دریافت اطلاعات Service Account از Secrets: {e}")
                 st.info("لطفاً از تنظیم صحیح Secrets برای Google Earth Engine اطمینان حاصل کنید. (به خصوص secret 'gee_auth_json').")
                 return None

        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Initialized Successfully.")
        return True
    except ee.EEException as e:
        st.error(f"❌ خطا در اتصال به Google Earth Engine: {e}")
        st.error("لطفاً از صحت فایل Service Account یا تنظیمات Secrets و فعال بودن آن در پروژه GEE اطمینان حاصل کنید.")
        return None
    except Exception as e:
        st.error(f"❌ خطای غیرمنتظره هنگام اتصال به GEE: {e}")
        st.error(traceback.format_exc())
        return None


@st.cache_data(show_spinner="در حال بارگذاری و پردازش داده‌های مزارع...", persist="disk") # Corrected persist option
def load_farm_data_from_csv(csv_path=FARM_DATA_CSV_PATH):
    """Loads farm data from the specified CSV file and processes coordinates."""
    if transformer is None:
         st.error("❌ تبدیل کننده مختصات پیکربندی نشده است. بارگذاری داده‌های مزارع امکان‌پذیر نیست.")
         return pd.DataFrame()

    try:
        df = None
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, encoding='utf-8')
            print(f"Loaded Farm data from local CSV: {csv_path}")
        else:
            github_raw_url = f'https://raw.githubusercontent.com/esmaeilkiani13877/MonitoringSugarcane-13/main/{csv_path}'
            try:
                response = requests.get(github_raw_url)
                response.raise_for_status()
                df = pd.read_csv(BytesIO(response.content), encoding='utf-8')
                print(f"Loaded Farm data from URL: {github_raw_url}")
            except requests.exceptions.RequestException as e:
                 st.error(f"❌ فایل '{csv_path}' در مسیر محلی یا از URL گیت‌هاب '{github_raw_url}' یافت نشد یا قابل دسترسی نیست: {e}")
                 return pd.DataFrame()
            except Exception as e:
                 st.error(f"❌ خطای غیرمنتظره در دریافت فایل CSV از URL: {e}")
                 return pd.DataFrame()


        if df is None or df.empty:
             st.error("❌ فایل داده مزارع خالی است یا خوانده نشد.")
             return pd.DataFrame()


        df.columns = df.columns.str.strip().str.replace('\ufeff', '')

        required_cols = ['مزرعه', 'روز', 'lat1', 'lon1', 'lat2', 'lon2', 'lat3', 'lon3', 'lat4', 'lon4']
        if not all(col in df.columns for col in required_cols):
            missing_cols = [col for col in required_cols if col not in df.columns]
            st.error(f"❌ فایل CSV مزارع باید شامل ستون‌های ضروری باشد. ستون‌های یافت نشد: {', '.join(missing_cols)}")
            return pd.DataFrame()

        df['wgs84_centroid_lon'] = None
        df['wgs84_centroid_lat'] = None
        df['ee_geometry'] = None
        df['wgs84_polygon_coords'] = None

        processed_records = []
        skipped_farms = []

        for index, row in df.iterrows():
            farm_name = row.get('مزرعه', f'مزرعه ناشناس ردیف {index+1}')
            try:
                points_utm = []
                valid_points = True
                for i in range(1, 5):
                    lat_col = f'lat{i}'
                    lon_col = f'lon{i}'
                    if pd.notna(row.get(lat_col)) and pd.notna(row.get(lon_col)):
                        try:
                            easting = float(row[lon_col])
                            northing = float(row[lat_col])
                            points_utm.append((easting, northing))
                        except ValueError:
                            valid_points = False
                            break
                    else:
                        valid_points = False
                        break


                if not valid_points or len(points_utm) < 4:
                    skipped_farms.append(f"مزرعه '{farm_name}': مختصات نامعتبر یا ناقص (نیاز به ۴ نقطه).")
                    continue


                points_wgs84 = []
                try:
                    for easting, northing in points_utm:
                         lon_wgs84, lat_wgs84 = transformer.transform(easting, northing)
                         points_wgs84.append((lon_wgs84, lat_wgs84))
                except pyproj.exceptions.TransformerError as te:
                     skipped_farms.append(f"مزرعه '{farm_name}': خطای تبدیل مختصات UTM به WGS84: {te}")
                     continue
                except Exception as e:
                     skipped_farms.append(f"مزرعه '{farm_name}': خطای ناشناخته در تبدیل مختصات: {e}")
                     continue


                if points_wgs84[-1] != points_wgs84[0]:
                     polygon_coords_wgs84 = points_wgs84 + [points_wgs84[0]]
                else:
                     polygon_coords_wgs84 = points_wgs84

                try:
                    shapely_polygon = Polygon(polygon_coords_wgs84)
                    if not shapely_polygon.is_valid:
                         shapely_polygon = shapely_polygon.buffer(0)
                         if not shapely_polygon.is_valid:
                             skipped_farms.append(f"مزرعه '{farm_name}': پلی‌گون WGS84 نامعتبر باقی ماند پس از buffer(0).")
                             continue

                    ee_polygon = ee.Geometry.Polygon(list(shapely_polygon.exterior.coords))

                    centroid_ee = ee_polygon.centroid(maxError=1)
                    centroid_coords_wgs84 = centroid_ee.getInfo()['coordinates']
                    centroid_lon_wgs84, centroid_lat_wgs84 = centroid_coords_wgs84[0], centroid_coords_wgs84[1]

                    processed_row = row.copy()
                    processed_row['wgs84_centroid_lon'] = centroid_lon_wgs84
                    processed_row['wgs84_centroid_lat'] = centroid_lat_wgs84
                    processed_row['ee_geometry'] = ee_polygon
                    processed_row['wgs84_polygon_coords'] = [list(coord) for coord in shapely_polygon.exterior.coords]

                    processed_records.append(processed_row)

                except ee.EEException as ee_geom_e:
                    skipped_farms.append(f"مزرعه '{farm_name}': خطای ایجاد هندسه GEE یا محاسبه Centroid: {ee_geom_e}")
                    continue
                except Exception as e:
                    skipped_farms.append(f"مزرعه '{farm_name}': خطای ناشناخته در پردازش هندسه: {e}")
                    continue


            except Exception as e:
                skipped_farms.append(f"مزرعه '{farm_name}': خطای عمومی در پردازش ردیف: {e}")
                continue

        processed_df = pd.DataFrame(processed_records)

        if skipped_farms:
            st.warning("⚠️ برخی از مزارع به دلیل خطای پردازش مختصات یا هندسه نادیده گرفته شدند:")
            for msg in skipped_farms[:10]:
                 st.warning(f"- {msg}")
            if len(skipped_farms) > 10:
                 st.warning(f"... و {len(skipped_farms) - 10} خطای دیگر.")


        if processed_df.empty:
            st.error("❌ هیچ داده معتبری پس از پردازش فایل CSV مزارع باقی نماند.")
            return pd.DataFrame()


        for col in ['روز', 'گروه', 'واریته', 'سن']:
            if col in processed_df.columns:
                processed_df[col] = processed_df[col].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
                processed_df[col] = processed_df[col].replace(['nan', ''], 'نامشخص')
            else:
                 processed_df[col] = 'نامشخص'

        if 'مساحت' in processed_df.columns:
             processed_df['مساحت'] = pd.to_numeric(processed_df['مساحت'], errors='coerce')
             processed_df['مساحت'] = processed_df['مساحت'].fillna(0)
        else:
            processed_df['مساحت'] = 0


        st.success(f"✅ داده‌های {len(processed_df)} مزرعه با موفقیت از CSV بارگذاری و پردازش شد.")
        return processed_df
    except FileNotFoundError:
        st.error(f"❌ فایل '{csv_path}' یافت نشد. لطفاً فایل CSV داده‌های مزارع را در مسیر صحیح قرار دهید.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری یا پردازش فایل CSV: {e}")
        st.error(traceback.format_exc())
        return pd.DataFrame()


@st.cache_data(show_spinner="در حال بارگذاری داده‌های محاسبات...", persist="disk") # Corrected persist option
def load_analysis_data(csv_path=ANALYSIS_CSV_PATH):
    """Loads and preprocesses data from the analysis CSV file."""
    try:
        lines = None
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            print(f"Loaded Analysis CSV from local path: {csv_path}")
        else:
             github_raw_url = f'https://raw.githubusercontent.com/esmaeilkiani13877/MonitoringSugarcane-13/main/{csv_path}'
             try:
                 response = requests.get(github_raw_url)
                 response.raise_for_status()
                 lines = response.text.splitlines()
                 print(f"Loaded Analysis CSV from URL: {github_raw_url}")
             except requests.exceptions.RequestException as e:
                 st.error(f"❌ فایل '{csv_path}' در مسیر محلی یا از URL گیت‌هاب '{github_raw_url}' یافت نشد یا قابل دسترسی نیست: {e}")
                 return None, None
             except Exception as e:
                 st.error(f"❌ خطای غیرمنتظره در دریافت فایل CSV از URL: {e}")
                 return None, None


        if lines is None:
             return None, None


        headers_indices = [i for i, line in enumerate(lines) if line.strip().lstrip('\ufeff').startswith('اداره,سن,') or line.strip().lstrip('\ufeff').startswith('تولید,سن,')]

        if len(headers_indices) < 1:
            st.error(f"❌ ساختار فایل '{csv_path}' قابل شناسایی نیست. هدرهای مورد انتظار ('اداره,سن,' یا 'تولید,سن,') یافت نشد.")
            return None, None

        section1_start_line_num = headers_indices[0]
        section2_start_line_num = len(lines)

        if len(headers_indices) > 1:
            section2_start_line_num = headers_indices[1]

        end_row_area_line_num = section2_start_line_num

        try:
            area_section_io = BytesIO("\n".join(lines[section1_start_line_num : end_row_area_line_num]).encode('utf-8'))
            df_area = pd.read_csv(area_section_io, encoding='utf-8')
        except Exception as e:
             st.warning(f"⚠️ خطا در خواندن بخش مساحت از فایل محاسبات: {e}")
             df_area = pd.DataFrame()


        df_prod = pd.DataFrame()
        if len(headers_indices) > 1:
             end_row_prod_line_num = len(lines)
             for i in range(section2_start_line_num + 1, len(lines)):
                 if "Grand Total" in lines[i] or len(lines[i].strip()) < 5:
                     end_row_prod_line_num = i
                     break

             try:
                  prod_section_io = BytesIO("\n".join(lines[section2_start_line_num : end_row_prod_line_num]).encode('utf-8'))
                  df_prod = pd.read_csv(prod_section_io, encoding='utf-8')
             except Exception as e:
                  st.warning(f"⚠️ خطا در خواندن بخش تولید از فایل محاسبات: {e}")
                  df_prod = pd.DataFrame()


        def preprocess_df(df, section_name):
            if df is None or df.empty:
                return None

            df.columns = df.columns.str.strip().str.replace('\ufeff', '')

            if df.columns.tolist() and 'اداره' not in df.columns:
                df.rename(columns={df.columns[0]: 'اداره'}, inplace=True)


            if not all(col in df.columns for col in ['اداره', 'سن']):
                 st.warning(f"⚠️ ستون های ضروری 'اداره' یا 'سن' در بخش '{section_name}' یافت نشد.")
                 return None

            df['اداره'] = df['اداره'].ffill()

            df = df[~df['سن'].astype(str).str.contains('total', case=False, na=False)].copy()
            df = df[~df['اداره'].astype(str).str.contains('total|دهخدا', case=False, na=False)].copy()

            df = df.dropna(subset=['اداره']).copy()

            df['اداره'] = pd.to_numeric(df['اداره'], errors='coerce').astype('Int64')
            df = df.dropna(subset=['اداره']).copy()

            value_cols = [col for col in df.columns if col not in ['اداره', 'سن', 'درصد', 'Grand Total']]
            for col in value_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df = df.dropna(axis=1, how='all').copy()

            df = df.drop(columns=['Grand Total', 'درصد'], errors='ignore')

            if 'اداره' in df.columns and 'سن' in df.columns:
                try:
                    df = df.set_index(['اداره', 'سن']).copy()
                except ValueError as e:
                     st.warning(f"⚠️ خطای تنظیم ایندکس چندگانه در بخش '{section_name}': {e}. ادامه بدون ایندکس.")

            return df

        df_area_processed = preprocess_df(df_area, "مساحت")
        df_prod_processed = preprocess_df(df_prod, "تولید")

        if df_area_processed is not None or df_prod_processed is not None:
             st.success(f"✅ داده‌های محاسبات با موفقیت بارگذاری و پردازش شد.")
        else:
             st.warning("⚠️ هیچ داده معتبری از فایل محاسبات بارگذاری یا پردازش نشد. لطفاً ساختار فایل 'محاسبات 2.csv' را بررسی کنید.")

        return df_area_processed, df_prod_processed

    except FileNotFoundError:
        st.error(f"❌ فایل '{csv_path}' یافت نشد. لطفاً فایل CSV داده‌های محاسبات را در مسیر صحیح قرار دهید.")
        return None, None
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری یا پردازش فایل محاسبات CSV: {e}")
        st.error(traceback.format_exc())
        return None, None


gee_initialized = initialize_gee()

farm_data_df = pd.DataFrame()
if transformer is not None:
    farm_data_df = load_farm_data_from_csv()
else:
     st.error("❌ بارگذاری داده‌های مزارع به دلیل خطای پیکربندی سیستم مختصات امکان‌پذیر نیست.")


analysis_area_df, analysis_prod_df = load_analysis_data()


@st.cache_resource(show_spinner="در حال پیکربندی سرویس هوش مصنوعی...")
def configure_gemini(api_key): # Accept API key as parameter
    """Configures the Gemini API client."""
    try:
        if not api_key:
             st.error("❌ کلید API جمینای در دسترس نیست.")
             st.info("لطفاً کلید API را در کد برنامه یا در Streamlit Secrets تنظیم کنید.")
             return None

        genai.configure(api_key=api_key)

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        model = genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety_settings)
        print("Gemini Configured Successfully.")
        return model
    except Exception as e:
        st.error(f"❌ خطا در تنظیم Gemini API: {e}")
        st.error(traceback.format_exc())
        return None


# Initialize Gemini model AFTER its definition
gemini_model = None
if gee_initialized:
    # Use the hardcoded API key
    gemini_model = configure_gemini(GEMINI_API_KEY_HARDCODED)
    if gemini_model is None:
         st.warning("⚠️ سرویس تحلیل هوش مصنوعی به دلیل خطای پیکربندی در دسترس نیست. قابلیت‌های تحلیل هوش مصنوعی غیرفعال است.")
    # Add a prominent warning about hardcoding the API key
    st.warning("⚠️ **هشدار امنیتی:** کلید API جمینای مستقیماً در کد قرار داده شده است. این روش **ناامن** است و به شدت توصیه می‌شود از Streamlit Secrets برای مدیریت امن کلید استفاده کنید.", icon="🔒")


# --- Sidebar Logo ---
st.sidebar.markdown(
    """
    <div class='sidebar-logo'>
        <img src='https://raw.githubusercontent.com/esmaeilkiani13877/MonitoringSugarcane-13/main/logo%20(1).png' alt='لوگو سامانه' />
    </div>
    """,
    unsafe_allow_html=True
)

# --- Main Header with Logo ---
st.markdown(
    """
    <div style='display: flex; align-items: center; gap: 16px; margin-bottom: 0.5rem;'>
        <img src='https://raw.githubusercontent.com/esmaeilkiani13877/MonitoringSugarcane-13/main/logo%20(1).png' class='main-logo' alt='لوگو' />
        <h1 style='font-family: Vazirmatn, sans-serif; color: #185a9d; margin: 0;'>سامانه پایش هوشمند نیشکر</h1>
    </div>
    <h4 style='color: #43cea2; margin-top: 0;'>مطالعات کاربردی شرکت کشت و صنعت دهخدا</h4>
    """,
    unsafe_allow_html=True
)

# ==============================================================================
# Sidebar Filters (Moved here, after data loading)
# ==============================================================================
st.sidebar.header("تنظیمات نمایش")

selected_day = None
if not farm_data_df.empty and 'روز' in farm_data_df.columns:
    available_days = sorted(farm_data_df['روز'].unique())
    if not available_days or (len(available_days) == 1 and available_days[0] == 'نامشخص'):
         st.sidebar.warning("هیچ روز هفته‌ای معتبری در داده‌های مزارع یافت نشد.")
         selected_day = None
    else:
         valid_days = [d for d in available_days if d != 'نامشخص']
         if not valid_days:
              st.sidebar.warning("هیچ روز هفته‌ای معتبری در داده‌های مزارع یافت نشد.")
              selected_day = None
         else:
            selected_day = st.sidebar.selectbox(
                "📅 روز هفته را انتخاب کنید:",
                options=valid_days,
                index=0,
                help="داده‌های مزارع بر اساس این روز فیلتر می‌شوند."
            )
else:
     st.sidebar.info("ℹ️ داده مزارع برای فیلتر روز هفته در دسترس نیست.")
     selected_day = None


filtered_farms_df = pd.DataFrame()
if selected_day and not farm_data_df.empty:
    filtered_farms_df = farm_data_df[farm_data_df['روز'] == selected_day].copy()

selected_farm_name = "همه مزارع"
available_farms = []
if not filtered_farms_df.empty:
    available_farms = sorted(filtered_farms_df['مزرعه'].unique())
    farm_options = ["همه مزارع"] + available_farms
    selected_farm_name = st.sidebar.selectbox(
        "🌾 مزرعه مورد نظر را انتخاب کنید:",
        options=farm_options,
        index=0,
        help="مزرعه‌ای که می‌خواهید جزئیات آن را ببینید یا 'همه مزارع' برای نمایش کلی."
    )
else:
    st.sidebar.info("ℹ️ مزارعی برای روز انتخابی یافت نشد.")


index_options = {
    "NDVI": "شاخص پوشش گیاهی تفاضلی نرمال شده",
    "EVI": "شاخص پوشش گیاهی بهبود یافته",
    "NDMI": "شاخص رطوبتی تفاضلی نرمال شده",
    "LAI": "شاخص سطح برگ (تخمینی)",
    "MSI": "شاخص تنش رطوبتی",
    "CVI": "شاخص کلروفیل (تخمینی)",
    "SAVI": "شاخص پوشش گیاهی تعدیل شده با خاک",
}
selected_index = st.sidebar.selectbox(
    "📈 شاخص مورد نظر برای نمایش و رتبه‌بندی:",
    options=list(index_options.keys()),
    format_func=lambda x: f"{x} ({index_options[x]})",
    index=0
)

today = datetime.date.today()
start_date_current_str = None
end_date_current_str = None
start_date_previous_str = None
end_date_previous_str = None

if selected_day:
    try:
        persian_to_weekday = {
            "شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1,
            "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4,
        }
        target_weekday = persian_to_weekday[selected_day.strip()]
        today_weekday = today.weekday()

        days_ago = (today_weekday - target_weekday + 7) % 7
        end_date_current = today - datetime.timedelta(days=days_ago)

        start_date_current = end_date_current - datetime.timedelta(days=6)

        end_date_previous = start_date_current - datetime.timedelta(days=1)
        start_date_previous = end_date_previous - datetime.timedelta(days=6)

        # Ensure previous start date is not too far back if needed
        one_year_ago = today - datetime.timedelta(days=365)
        if start_date_previous < one_year_ago:
             start_date_previous = one_year_ago
             st.sidebar.info(f"⚠️ بازه زمانی قبلی به یک سال قبل محدود شد: {start_date_previous.strftime('%Y-%m-%d')}")


        start_date_current_str = start_date_current.strftime('%Y-%m-%d')
        end_date_current_str = end_date_current.strftime('%Y-%m-%d')
        start_date_previous_str = start_date_previous.strftime('%Y-%m-%d')
        end_date_previous_str = end_date_previous.strftime('%Y-%m-%d')

        st.sidebar.info(f"**بازه زمانی فعلی:** {start_date_current_str} تا {end_date_current_str}")
        st.sidebar.info(f"**بازه زمانی قبلی:** {start_date_previous_str} تا {end_date_previous_str}")

    except KeyError:
        st.sidebar.error(f"❌ نام روز هفته '{selected_day}' قابل شناسایی نیست. لطفاً روز معتبری را انتخاب کنید.")
    except Exception as e:
        st.sidebar.error(f"❌ خطا در محاسبه بازه زمانی: {e}")
        st.error(traceback.format_exc())

st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با ❤️ با استفاده از Streamlit, Google Earth Engine, و geemap")


def maskS2clouds(image):
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask_qa = qa.bitwiseAnd(cloudBitMask).eq(0).And(
             qa.bitwiseAnd(cirrusBitMask).eq(0))

    scl = image.select('SCL')
    # Sentinel-2 SCL band values:
    # 0: No Data (Mask)
    # 1: Saturated or defective pixel
    # 2: Dark Area Pixels
    # 3: Cloud Shadows
    # 4: Vegetation
    # 5: Not Vegetated
    # 6: Water
    # 7: Unclassified
    # 8: Cloud Medium Probability
    # 9: Cloud High Probability
    # 10: Thin Cirrus
    # 11: Snow/Ice
    # Masking out: No Data, Saturated, Dark Area, Cloud Shadows, Cloud High Probability, Thin Cirrus, Snow/Ice
    masked_classes_scl = [0, 1, 2, 3, 9, 10, 11]
    mask_scl = scl.remap(masked_classes_scl, [0] * len(masked_classes_scl), 1).eq(1)


    final_mask = mask_qa.And(mask_scl)
    opticalBands = image.select('B.*').multiply(0.0001)

    return image.addBands(opticalBands, None, True)\
                .updateMask(final_mask)

def add_indices(image):
    red = image.select('B4')
    nir = image.select('B8')
    blue = image.select('B2')
    green = image.select('B3')
    swir1 = image.select('B11')

    epsilon = 1e-9

    ndvi_denominator = nir.add(red)
    ndvi = image.expression(
        '(NIR - RED) / (NIR + RED)',
        {'NIR': nir, 'RED': red}
    ).rename('NDVI').updateMask(ndvi_denominator.gt(epsilon))

    evi_denominator = nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1)
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)',
        {'NIR': nir, 'RED': red, 'BLUE': blue}
    ).rename('EVI').updateMask(evi_denominator.abs().gt(epsilon))

    ndmi_denominator = nir.add(swir1)
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI').updateMask(ndmi_denominator.gt(epsilon))

    savi_denominator = nir.add(red).add(0.5)
    savi = image.expression(
        '((NIR - RED) / (NIR + RED + L)) * (1 + L)',
        {'NIR': nir, 'RED': red, 'L': 0.5}
    ).rename('SAVI').updateMask(savi_denominator.gt(epsilon))

    nir_safe = nir.max(ee.Image(epsilon))
    msi = image.expression('SWIR1 / NIR', {'SWIR1': swir1, 'NIR': nir_safe}).rename('MSI')

    lai = evi.multiply(3.618).subtract(0.118).rename('LAI').reproject(crs=image.projection().crs(), scale=10)
    lai = lai.updateMask(lai.gt(0))

    green_safe = green.max(ee.Image(epsilon))
    cvi = image.expression('(NIR / GREEN) * (RED / GREEN)',
                         {'NIR': nir, 'GREEN': green_safe, 'RED': red}
    ).rename('CVI').reproject(crs=image.projection().crs(), scale=10)

    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi, savi])

@st.cache_data(show_spinner=False, persist="disk")
def get_processed_image(_geometry, start_date, end_date, index_name):
    """
    Gets cloud-masked, index-calculated Sentinel-2 median composite for a given geometry and date range.
    Includes fallback date range logic if no images are found initially.
    Ensures a non-None error message is returned if the image is None.
    """
    if not gee_initialized:
        return None, "Google Earth Engine مقداردهی اولیه نشده است."
    if _geometry is None:
        return None, "هندسه معتبر برای پردازش GEE وجود ندارد."

    initial_start_date = start_date
    initial_end_date = end_date
    fallback_days = 30 # Increased fallback period


    def filter_and_process_collection(s_date, e_date):
        try:
            s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                         .filterBounds(_geometry)
                         .filterDate(s_date, e_date)
                         .map(maskS2clouds))

            count = s2_sr_col.size().getInfo()
            if count == 0:
                return None, 0, f"هیچ تصویر Sentinel-2 بدون ابر در بازه {s_date} تا {e_date} یافت نشد."

            indexed_col = s2_sr_col.map(add_indices)
            median_image = indexed_col.median()

            available_bands = median_image.bandNames().getInfo()
            if index_name not in available_bands:
                 # Attempt to select another common band to see if the image is valid otherwise
                 test_band = 'B4' if 'B4' in available_bands else (available_bands[0] if available_bands else None)
                 if test_band:
                     try:
                         # Test reducing a small region with the available band
                          test_region = _geometry.centroid(1).buffer(10) # Small buffer around centroid
                          median_image.select(test_band).reduceRegion(ee.Reducer.first(), test_region, 10).getInfo()
                          # If above works, the issue is band calculation/availability
                          return None, count, f"شاخص '{index_name}' در تصاویر پردازش شده یافت نشد (ممکن است خطایی در محاسبه شاخص رخ داده باشد). باندهای موجود: {', '.join(available_bands)}"
                     except Exception as band_test_e:
                          # If even testing another band fails, likely a broader issue
                          return None, count, f"شاخص '{index_name}' یافت نشد و خطای پردازش تصویر نیز وجود دارد: {band_test_e}. باندهای موجود: {', '.join(available_bands)}"
                 else: # No bands available at all
                     return None, count, f"شاخص '{index_name}' یافت نشد و هیچ باند معتبری در تصویر وجود ندارد."


            # Select the band before returning
            output_image = median_image.select(index_name)

            # Final validity check: Ensure the selected band has data over the geometry
            try:
                test_reduction = output_image.reduceRegion(
                    reducer=ee.Reducer.firstNonNull(), # Check if there's any non-null pixel
                    geometry=_geometry,
                    scale=30, # Use slightly coarser scale for faster check
                    bestEffort=True
                ).get(index_name).getInfo()
                if test_reduction is None:
                     return None, count, f"تصویر برای شاخص '{index_name}' در بازه {s_date}-{e_date} ایجاد شد اما هیچ داده معتبری روی هندسه مورد نظر ندارد (احتمالاً همه پیکسل‌ها Mask شده‌اند)."
            except ee.EEException as reduce_err:
                 # If reduction itself fails, report it
                 return None, count, f"خطا در تأیید داده‌های تصویر برای شاخص '{index_name}' در بازه {s_date}-{e_date}: {reduce_err}"


            return output_image, count, None

        except ee.EEException as e:
            error_message = f"خطای Google Earth Engine در بازه {s_date}-{e_date}: {e}"
            try:
                error_details = e.args[0] if e.args else str(e)
                if isinstance(error_details, str):
                     if 'computation timed out' in error_details.lower():
                         error_message += "\\n(احتمالاً به دلیل حجم بالای پردازش یا بازه زمانی طولانی)"
                     elif 'user memory limit exceeded' in error_details.lower():
                         error_message += "\\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده)"
                     elif 'image.projection' in error_details.lower() and 'different projections' in error_details.lower():
                        error_message += "\\n(خطای پروجکشن داخلی در GEE. ممکن است با تلاش مجدد یا بازه زمانی متفاوت برطرف شود.)"
                     elif 'geometryconstructors' in error_details.lower() or 'invalid polygon' in error_details.lower():
                         error_message += "\\n(احتمالاً مشکلی در هندسه ورودی وجود دارد)"

            except Exception:
                pass # Ignore errors during error message enhancement
            return None, 0, error_message
        except Exception as e:
            error_message = f"خطای ناشناخته در پردازش GEE در بازه {s_date}-{e_date}: {e}\\n{traceback.format_exc()}"
            return None, 0, error_message


    # --- Main Logic with Improved Error Handling ---
    image, count, error_msg = filter_and_process_collection(initial_start_date, initial_end_date)
    initial_error_msg = error_msg # Store the initial error message

    if image is None:
        # Attempt 2: Fallback with extended end date
        try:
            # Ensure dates are valid datetime objects before manipulation
            start_dt_obj = datetime.datetime.strptime(initial_start_date, '%Y-%m-%d')
            end_dt_obj = datetime.datetime.strptime(initial_end_date, '%Y-%m-%d')

            fallback_end_date = (end_dt_obj + datetime.timedelta(days=fallback_days)).strftime('%Y-%m-%d')
            # Use original start date for fallback range
            fallback_start_date = initial_start_date

            print(f"Attempt 1 failed for {initial_start_date}-{initial_end_date}. Error: '{initial_error_msg}'. Trying fallback range: {fallback_start_date} to {fallback_end_date}")

            # Call fallback, store result in separate variables
            fallback_image, fallback_count, fallback_error_msg = filter_and_process_collection(fallback_start_date, fallback_end_date)

            if fallback_image is not None:
                 image = fallback_image # Use fallback image if successful
                 error_msg = None # Clear error message if fallback succeeded
                 print(f"Found {fallback_count} images in fallback range {fallback_start_date}-{fallback_end_date}.")
                 # Optionally add info message: st.info(f"ℹ️ از داده‌های تصویری تا تاریخ {fallback_end_date} برای نمایش نقشه استفاده شد.")
            else:
                 # Fallback also failed. Prioritize the fallback error message if it exists and is informative, otherwise use the initial error message.
                 if fallback_error_msg and "هیچ تصویر" not in fallback_error_msg: # Prioritize specific errors from fallback
                      error_msg = f"تلاش اول ناموفق ({initial_error_msg}). تلاش دوم ({fallback_start_date}-{fallback_end_date}) نیز ناموفق: {fallback_error_msg}"
                 else: # Use initial error if fallback error is generic "no image" or None
                      error_msg = initial_error_msg if initial_error_msg else fallback_error_msg # Fallback error only if initial was None

                 # Ensure error_msg is never None if image is None at this stage
                 if image is None and not error_msg:
                     error_msg = f"پردازش تصویر برای بازه {initial_start_date}-{initial_end_date} و بازه جایگزین {fallback_start_date}-{fallback_end_date} ناموفق بود (خطای نامشخص)."
                 print(f"Attempt 2 also failed for {fallback_start_date}-{fallback_end_date}. Final Error: {error_msg}")

        except ValueError as date_err:
            # Handle potential errors converting date strings
            error_msg = f"خطا در تبدیل تاریخ برای بازه جایگزین: {date_err}. خطای اولیه: {initial_error_msg}"
            image = None # Ensure image remains None
            print(f"Error processing fallback dates: {date_err}")
        except Exception as e:
            # Error during the fallback *attempt* itself
            error_msg = f"خطا در تلاش جایگزین ({fallback_start_date}-{fallback_end_date}): {e}\\n{traceback.format_exc()}. خطای اولیه: {initial_error_msg}"
            image = None # Ensure image remains None
            print(f"Error during fallback attempt: {e}")

    # Final check: if image is None, ensure there's an error message
    if image is None and not error_msg:
        error_msg = f"پردازش تصویر برای بازه {initial_start_date}-{initial_end_date} ناموفق بود (دلیل نامشخص)."


    # --- Return Value ---
    return image, error_msg


@st.cache_data(show_spinner="در حال دریافت سری زمانی شاخص...", persist="disk")
def get_index_time_series(_point_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    if not gee_initialized:
        return pd.DataFrame(columns=['date', index_name]), "Google Earth Engine مقداردهی اولیه نشده است."
    if _point_geom is None:
        return pd.DataFrame(columns=['date', index_name]), "هندسه نقطه‌ای معتبر برای سری زمانی وجود ندارد."
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)
                     .map(add_indices))

        # Select the band explicitly before proceeding
        s2_sr_col = s2_sr_col.select([index_name])

        def extract_value(image):
            try:
                # Select the band again before reducing to be extra safe with projections
                value = image.select(index_name).reduceRegion(
                    reducer=ee.Reducer.first(),
                    geometry=_point_geom,
                    scale=10,
                    bestEffort=True
                ).get(index_name)
                return ee.Feature(None, {
                    'date': image.date().format('YYYY-MM-dd'),
                    index_name: value
                })
            except Exception as e:
                 # Log the error internally or print for debugging
                 print(f"Error extracting value for date {image.date().format('YYYY-MM-dd')} and index {index_name}: {e}")
                 return ee.Feature(None, {
                    'date': image.date().format('YYYY-MM-dd'),
                    index_name: None
                })

        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.notNull([index_name]))

        try:
            # Using aggregate_array might be more robust than getInfo() on features for large collections
            dates_list = ts_features.aggregate_array('date').getInfo()
            values_list = ts_features.aggregate_array(index_name).getInfo()

            if not dates_list or not values_list:
                 return pd.DataFrame(columns=['date', index_name]), "داده‌ای برای سری زمانی در بازه مشخص شده یافت نشد (ممکن است به دلیل پوشش ابری یا خطای پردازش باشد)."


            ts_df = pd.DataFrame({
                'date': dates_list,
                index_name: values_list
            })

        except ee.EEException as e:
            return pd.DataFrame(columns=['date', index_name]), f"خطای GEE در دریافت اطلاعات سری زمانی: {e}"
        except Exception as e:
            return pd.DataFrame(columns=['date', index_name]), f"خطای ناشناخته در دریافت اطلاعات سری زمانی: {e}"


        if ts_df.empty:
             return pd.DataFrame(columns=['date', index_name]), "داده معتبری برای سری زمانی یافت نشد (پس از حذف مقادیر خالی)."

        ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df = ts_df.sort_values('date').set_index('date')

        return ts_df, None
    except ee.EEException as e:
        error_message = f"خطای GEE در دریافت سری زمانی: {e}"
        st.error(error_message)
        return pd.DataFrame(columns=['date', index_name]), error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در دریافت سری زمانی: {e}\n{traceback.format_exc()}"
        st.error(error_message)
        return pd.DataFrame(columns=['date', index_name]), error_message

@st.cache_data(show_spinner=False, persist="disk")
def get_farm_needs_data(_farm_geometry, start_curr, end_curr, start_prev, end_prev):
    if not gee_initialized:
        results = {'error': "Google Earth Engine مقداردهی اولیه نشده است."}
        return results
    if _farm_geometry is None:
        results = {'error': "هندسه معتبر برای محاسبه شاخص‌های نیازسنجی وجود ندارد."}
        return results

    results = {
        'NDVI_curr': None, 'NDMI_curr': None, 'EVI_curr': None, 'SAVI_curr': None,
        'NDVI_prev': None, 'NDMI_prev': None, 'EVI_prev': None, 'SAVI_prev': None,
        'error': None
    }
    indices_to_get = ['NDVI', 'NDMI', 'EVI', 'SAVI']

    def get_mean_values_for_period(start, end):
        period_values = {index: None for index in indices_to_get}
        error_msg = None
        try:
            s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                         .filterBounds(_farm_geometry)
                         .filterDate(start, end)
                         .map(maskS2clouds))

            count = s2_sr_col.size().getInfo()
            if count == 0:
                # Fallback logic (similar to get_processed_image)
                fallback_days_needs = 30 # Fallback for needs data as well
                fallback_end_date = (datetime.datetime.strptime(end, '%Y-%m-%d') + datetime.timedelta(days=fallback_days_needs)).strftime('%Y-%m-%d')
                s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                             .filterBounds(_farm_geometry)
                             .filterDate(start, fallback_end_date)
                             .map(maskS2clouds))
                count = s2_sr_col.size().getInfo()
                if count == 0:
                    return period_values, f"هیچ تصویری در بازه {start}-{end} (و بازه جایگزین تا {fallback_end_date}) یافت نشد"


            indexed_col = s2_sr_col.map(add_indices)
            median_image = indexed_col.median()

            available_bands = median_image.bandNames().getInfo()
            indices_to_reduce = [idx for idx in indices_to_get if idx in available_bands]

            if not indices_to_reduce:
                 return period_values, f"هیچ یک از شاخص‌های مورد نیاز ({', '.join(indices_to_get)}) در تصاویر پردازش شده برای بازه {start}-{end} یافت نشد."

            # Calculate mean for each index separately to avoid projection issues with multi-band image reduction
            mean_dict = {}
            for idx in indices_to_reduce:
                try:
                    mean_value = median_image.select(idx).reduceRegion( # Select band before reduceRegion
                        reducer=ee.Reducer.mean(),
                        geometry=_farm_geometry,
                        scale=10,
                        bestEffort=True,
                        maxPixels=1e8
                    ).get(idx).getInfo()
                    mean_dict[idx] = mean_value
                except Exception as e:
                     print(f"Error calculating mean for index {idx} in period {start}-{end}: {e}") # Log error per index


            if mean_dict:
                for index in indices_to_get:
                    if index in mean_dict and mean_dict[index] is not None:
                         period_values[index] = mean_dict[index]

            return period_values, None
        except ee.EEException as e:
            error_msg = f"خطای GEE در بازه {start}-{end}: {e}"
            return period_values, error_msg
        except Exception as e:
            error_msg = f"خطای ناشناخته در بازه {start}-{end}: {e}\n{traceback.format_exc()}"
            return period_values, error_msg

    curr_values, err_curr = get_mean_values_for_period(start_curr, end_curr)
    if err_curr:
        results['error'] = f"خطا در بازه جاری: {err_curr}"
    results['NDVI_curr'] = curr_values.get('NDVI')
    results['NDMI_curr'] = curr_values.get('NDMI')
    results['EVI_curr'] = curr_values.get('EVI')
    results['SAVI_curr'] = curr_values.get('SAVI')


    prev_values, err_prev = get_mean_values_for_period(start_prev, end_prev)
    if err_prev:
        if results.get('error'):
             results['error'] += f"\nخطا در بازه قبلی: {err_prev}"
        else:
             results['error'] = f"خطا در بازه قبلی: {err_prev}"

    # Consolidate error message if both periods failed
    if results.get('error') and 'خطا در بازه جاری:' in results['error'] and 'خطا در بازه قبلی:' in results['error']:
         results['error'] = "خطا در هر دو بازه زمانی هنگام محاسبه شاخص‌های نیازسنجی."
    elif results.get('error'):
         pass # Keep the specific error if only one period failed
    elif pd.isna(results['NDVI_curr']) and pd.isna(results['NDMI_curr']) and pd.isna(results['EVI_curr']) and pd.isna(results['SAVI_curr']) and \
         pd.isna(results['NDVI_prev']) and pd.isna(results['NDMI_prev']) and pd.isna(results['EVI_prev']) and pd.isna(results['SAVI_prev']):
         results['error'] = "هیچ داده شاخصی برای بازه‌های زمانی مشخص شده یافت نشد."

    results['NDVI_prev'] = prev_values.get('NDVI')
    results['NDMI_prev'] = prev_values.get('NDMI')
    results['EVI_prev'] = prev_values.get('EVI')
    results['SAVI_prev'] = prev_values.get('SAVI')


    return results


@st.cache_data(show_spinner="در حال دریافت تحلیل هوش مصنوعی...", persist="disk")
def get_ai_needs_analysis(_model, farm_name, index_data, recommendations):
    """Generates AI analysis for the farm's condition related to needs."""
    if _model is None:
        return "سرویس هوش مصنوعی در دسترس نیست."

    data_str_parts = []
    indices_to_display = ['NDVI', 'NDMI', 'EVI', 'SAVI']
    for idx in indices_to_display:
         curr_val = index_data.get(f'{idx}_curr')
         prev_val = index_data.get(f'{idx}_prev')

         if pd.notna(curr_val):
              line = f"- {idx} فعلی: {curr_val:.3f}"
              if pd.notna(prev_val):
                  line += f" (قبلی: {prev_val:.3f}"
                  change_percent = None
                  if pd.notna(prev_val) and prev_val != 0:
                      try:
                         change_percent = ((curr_val - prev_val) / prev_val) * 100
                      except Exception:
                         change_percent = None # Handle division by zero

                  if change_percent is not None:
                      line += f", تغییر: {change_percent:.1f}%)"
                      # Provide context for change based on index type
                      change_status_desc = ""
                      if idx in ['NDVI', 'EVI', 'LAI', 'CVI', 'SAVI']: # Higher is better
                           if change_percent > 3: change_status_desc = "رشد مثبت قابل توجه"
                           elif change_percent > 0: change_status_desc = "رشد مثبت"
                           elif change_percent < -5: change_status_desc = "افت قابل توجه"
                           elif change_percent < 0: change_status_desc = "کاهش"
                           else: change_status_desc = "بدون تغییر معنادار" # Added "معنادار"
                      elif idx == 'MSI': # Lower is better
                           if change_percent < -3: change_status_desc = "بهبود (کاهش تنش قابل توجه)"
                           elif change_percent < 0: change_status_desc = "بهبود (کاهش تنش)"
                           elif change_percent > 5: change_status_desc = "افزایش تنش قابل توجه"
                           elif change_percent > 0: change_status_desc = "افزایش تنش"
                           else: change_status_desc = "بدون تغییر معنادار"
                      elif idx == 'NDMI': # Higher is better
                           if change_percent > 3: change_status_desc = "افزایش رطوبت قابل توجه"
                           elif change_percent > 0: change_status_desc = "افزایش رطوبت"
                           elif change_percent < -5: change_status_desc = "کاهش رطوبت قابل توجه"
                           elif change_percent < 0: change_status_desc = "کاهش رطوبت"
                           else: change_status_desc = "رطوبت ثابت"

                      if change_status_desc:
                           line += f" - {change_status_desc}"
                  else:
                      line += ")" # Close parenthesis if percentage change couldn't be calculated
              data_str_parts.append(line)
         elif pd.notna(prev_val):
              data_str_parts.append(f"- {idx} قبلی: {prev_val:.3f} (داده فعلی موجود نیست)")


    data_str = "\n".join(data_str_parts) if data_str_parts else "داده‌های شاخص در دسترس نیست."

    recommendations_str = "\n".join([f"- {rec}" for rec in recommendations]) if recommendations else 'هیچ توصیه‌ای بر اساس قوانین اولیه وجود ندارد.'


    prompt = f"""
    شما یک متخصص کشاورزی باتجربه هستید که در زمینه پایش نیشکر با استفاده از داده‌های ماهواره‌ای تخصص دارید. لطفاً وضعیت مزرعه '{farm_name}' را با جزئیات و دقت بیشتری بر اساس داده‌های شاخص ماهواره‌ای و توصیه‌های اولیه زیر تحلیل کنید. تحلیل شما باید جامع، کاربردی و قابل ارائه به مدیران یا کارشناسان کشاورزی باشد. به ارتباط بین شاخص‌ها (مثلاً NDMI و NDVI) و نیازهای احتمالی مزرعه (آبیاری، کوددهی، یا سایر عوامل تنش‌زا) اشاره کنید. تحلیل شما باید شامل موارد زیر باشد:

    1.  **ارزیابی وضعیت فعلی:** وضعیت سلامت پوشش گیاهی و رطوبت بر اساس مقادیر شاخص‌های فعلی (NDVI, NDMI, EVI, SAVI). مقایسه مقادیر با آستانه‌های معمول برای نیشکر (اگر اطلاعات دارید) می‌تواند مفید باشد.
    2.  **تحلیل روند:** مقایسه شاخص‌های فعلی با هفته قبل و توضیح معانی تغییرات مشاهده شده (رشد مثبت، کاهش، تنش، بهبود رطوبت، افزایش تنش و...). به بزرگی تغییرات (قابل توجه یا جزئی) اشاره کنید.
    3.  **شناسایی نیازها و عوامل تنش‌زا:** با توجه به مقادیر و روند شاخص‌ها، به نیازهای احتمالی (آبیاری اگر NDMI پایین است یا کاهش قابل توجهی داشته، کوددهی اگر NDVI/EVI کاهش یافته با وجود رطوبت کافی، بررسی آفات یا بیماری‌ها اگر شاخص‌های سلامت کاهش یافته و رطوبت مناسب است و...) اشاره کنید. توصیه‌های اولیه (سیستم قوانین ساده) را در تحلیل خود لحاظ کنید و آن‌ها را بسط دهید.
    4.  **توصیه‌های کلی:** ارائه راهنمایی کلی بر اساس تحلیل برای اقدامات بعدی (بازدید میدانی با تمرکز بر نقاط مشکل‌دار، تنظیم برنامه آبیاری/کوددهی، بررسی عوامل محیطی).
    5.  **یادداشت مهم:** اگر داده‌های کافی (مثلاً داده هفته قبل یا جاری) موجود نبود، به این موضوع اشاره کنید و ذکر کنید که تحلیل روند دقیق امکان‌پذیر نیست.

    زبان تحلیل باید فارسی، تخصصی اما قابل فهم باشد.

    داده‌های شاخص:
{data_str}

    توصیه‌های اولیه (سیستم قوانین ساده):
{recommendations_str}

    تحلیل جامع شما:
    """

    try:
        response = _model.generate_content(prompt)
        if response.candidates and response.candidates[0].content.parts:
            return "".join([part.text for part in response.candidates[0].content.parts])
        elif response.prompt_feedback and response.prompt_feedback.block_reason:
             block_reason = response.prompt_feedback.block_reason.name
             st.warning(f"⚠️ پاسخ Gemini به دلیل '{block_reason}' مسدود شد. پرامپت ممکن است نیاز به بازبینی داشته باشد.")
             return "پاسخ هوش مصنوعی مسدود شد."
        else:
             st.warning("⚠️ پاسخ معتبری از Gemini دریافت نشد.")
             return "پاسخ هوش مصنوعی در دسترس نیست."

    except Exception as e:
        st.warning(f"⚠️ خطا در ارتباط با Gemini API هنگام تحلیل نیازها: {e}")
        st.warning(traceback.format_exc())
        return "خطا در دریافت تحلیل هوش مصنوعی."


@st.cache_data(show_spinner="در حال دریافت خلاصه هوش مصنوعی نقشه...", persist="disk")
def get_ai_map_summary(_model, ranking_df_sorted, selected_index, selected_day):
    """Generates AI summary for the overall map/ranking status."""
    if _model is None:
        return "سرویس هوش مصنوعی در دسترس نیست."

    if ranking_df_sorted.empty:
        return "داده‌ای برای خلاصه‌سازی وضعیت مزارع در این روز وجود ندارد."

    # Ensure these temporary copies are made if modifications are planned, though none are here
    negative_status_farms = ranking_df_sorted[ranking_df_sorted['وضعیت'].astype(str).str.contains("تنش|کاهش|بدتر|نیاز", case=False, na=False)]
    positive_status_farms = ranking_df_sorted[ranking_df_sorted['وضعیت'].astype(str).str.contains("بهبود|رشد مثبت", case=False, na=False)]
    nodata_farms = ranking_df_sorted[ranking_df_sorted['وضعیت'].astype(str).str.contains("بدون داده", case=False, na=False)]
    neutral_terms_list = ["ثابت", "رطوبت ثابت", "پوشش گیاهی پایین", "قابل توجه"] # Define list for neutral terms
    neutral_farms = ranking_df_sorted[ranking_df_sorted['وضعیت'].astype(str).str.contains("|".join(neutral_terms_list), case=False, na=False)] # Use list here


    summary_text = f"خلاصه وضعیت کلی مزارع برای روز {selected_day} بر اساس شاخص {selected_index}:\n"
    summary_text += f"تعداد کل مزارع بررسی شده: {len(ranking_df_sorted)}\n"
    summary_text += f"تعداد مزارع با وضعیت 'تنش/کاهش/نیاز': {len(negative_status_farms)}\n"
    summary_text += f"تعداد مزارع با وضعیت 'بهبود/رشد مثبت': {len(positive_status_farms)}\n"
    summary_text += f"تعداد مزارع با وضعیت 'ثابت/خنثی': {len(neutral_farms)}\n"
    summary_text += f"تعداد مزارع 'بدون داده': {len(nodata_farms)}\n\n"

    if not negative_status_farms.empty:
        summary_text += "مزارعی که بیشترین نیاز به توجه فوری دارند (بیشترین تنش یا کاهش، تا ۵ مزرعه اول بر اساس رتبه):\n"
        # Sort negative farms by rank to get the "top" problem farms
        top_problem_farms = negative_status_farms.sort_index().head(5) # Assuming index is rank

        for idx, row in top_problem_farms.iterrows():
            farm_name_ai = row.get('مزرعه', 'نامشخص')
            status_html_ai = row.get('وضعیت_نمایش', 'نامشخص')
            # Clean HTML tags from status for AI prompt
            status_text_ai = status_html_ai.replace('<span class="status-badge status-positive">', '').replace('<span class="status-badge status-negative">', '').replace('<span class="status-badge status-neutral">', '').replace('<span class="status-badge status-nodata">', '').replace('</span>', '')

            current_index_val_ai = row.get(f'{selected_index} (هفته جاری)', 'N/A')
            change_val_ai = row.get('تغییر', 'N/A')

            current_index_display = f"{float(str(current_index_val_ai).replace('N/A', 'nan')):.3f}" if pd.notna(current_index_val_ai) and str(current_index_val_ai) != 'N/A' else 'N/A'
            change_display = f"{float(str(change_val_ai).replace('N/A', 'nan')):.3f}" if pd.notna(change_val_ai) and str(change_val_ai) != 'N/A' else 'N/A'


            summary_text += f"- رتبه {idx}: مزرعه {farm_name_ai}, وضعیت {status_text_ai}, شاخص هفته جاری: {current_index_display}, تغییر: {change_display}\n"


    if not positive_status_farms.empty and len(positive_status_farms) > 0:
         summary_text += "\nمزارعی که وضعیت بهبود یافته یا رشد مثبت نشان می‌دهند (تا ۵ مزرعه اول بر اساس رتبه):\n"
         # Sort positive farms by rank to get the "top" improving farms
         top_improving_farms = positive_status_farms.sort_index().head(5) # Assuming index is rank

         for idx, row in top_improving_farms.iterrows():
             farm_name_ai = row.get('مزرعه', 'نامشخص')
             status_html_ai = row.get('وضعیت_نمایش', 'نامشخص')
             status_text_ai = status_html_ai.replace('<span class="status-badge status-positive">', '').replace('<span class="status-badge status-negative">', '').replace('<span class="status-badge status-neutral">', '').replace('<span class="status-badge status-nodata">', '').replace('</span>', '')

             current_index_val_ai = row.get(f'{selected_index} (هفته جاری)', 'N/A')
             change_val_ai = row.get('تغییر', 'N/A')

             current_index_display = f"{float(str(current_index_val_ai).replace('N/A', 'nan')):.3f}" if pd.notna(current_index_val_ai) and str(current_index_val_ai) != 'N/A' else 'N/A'
             change_display = f"{float(str(change_val_ai).replace('N/A', 'nan')):.3f}" if pd.notna(change_val_ai) and str(change_val_ai) != 'N/A' else 'N/A'

             summary_text += f"- رتبه {idx}: مزرعه {farm_name_ai}, وضعیت {status_text_ai}, شاخص هفته جاری: {current_index_display}, تغییر: {change_display}\n"


    prompt = f"""
    شما یک تحلیلگر داده‌های کشاورزی هستید و وظیفه دارید خلاصه‌ای کاربردی و حرفه‌ای از وضعیت کلی مزارع بر اساس داده‌های رتبه‌بندی ماهواره‌ای ارائه دهید. این خلاصه باید به مدیران یا کارشناسان کمک کند تا به سرعت وضعیت کلی را درک کرده و مزارع نیازمند اقدام را شناسایی کنند.

    خلاصه شما باید شامل موارد زیر باشد:
    1.  **تصویر کلی:** تعداد مزارع در هر دسته وضعیت (تنش/کاهش، بهبود/رشد مثبت، ثابت، بدون داده) و معنی کلی این توزیع چیست؟
    2.  **مزارع بحرانی:** اشاره به مزارعی که بیشترین تنش یا کاهش را نشان داده‌اند (بر اساس لیست ارائه شده). با توجه به شاخص {selected_index}، چه نوع تنشی (مثلاً رطوبتی، پوشش گیاهی) محتمل است و چه اقداماتی برای این مزارع توصیه می‌شود؟ (بازدید میدانی با تمرکز بر نقاط مشکل‌دار، بررسی عوامل تنش‌زا، آزمایش خاک، تنظیم برنامه آبیاری/کوددهی).
    3.  **مزارع با عملکرد خوب:** اشاره به مزارعی که بهبود یا رشد مثبت نشان داده‌اند (بر اساس لیست ارائه شده). آیا می‌توان از دلایل موفقیت این مزارع در سایر نقاط الگوبرداری کرد؟ (بررسی تاریخچه اقدامات زراعی در این مزارع).
    4.  **داده‌های ناموجود:** توضیح کوتاه در مورد مزارع بدون داده و لزوم بررسی دستی یا استفاده از داده‌های دیگر برای آن‌ها.
    5.  **اهمیت شاخص:** یادآوری کوتاه در مورد اینکه شاخص {selected_index} چه اطلاعاتی به ما می‌دهد و چرا برای پایش مهم است.

    زبان تحلیل باید فارسی و حرفه‌ای باشد.

    داده‌های خلاصه رتبه‌بندی:
{summary_text}

    خلاصه تحلیل جامع شما:
    """
    try:
        response = _model.generate_content(prompt)
        if response.candidates and response.candidates[0].content.parts:
            return "".join([part.text for part in response.candidates[0].content.parts])
        elif response.prompt_feedback and response.prompt_feedback.block_reason:
             block_reason = response.prompt_feedback.block_reason.name
             st.warning(f"⚠️ پاسخ Gemini به دلیل '{block_reason}' مسدود شد.")
             return "خلاصه هوش مصنوعی مسدود شد."
        else:
             st.warning("⚠️ پاسخ معتبری از Gemini برای خلاصه نقشه دریافت نشد.")
             return "خلاصه هوش مصنوعی در دسترس نیست."
    except Exception as e:
        st.warning(f"⚠️ خطا در ارتباط با Gemini API هنگام خلاصه‌سازی نقشه: {e}")
        st.warning(traceback.format_exc())
        return "خطا در دریافت خلاصه هوش مصنوعی نقشه."


def determine_status(row, index_name):
    """Determines the status based on change in index value using fixed thresholds."""
    # Fixed Thresholds (Not visible to the user)
    NDMI_IRRIGATION_THRESHOLD = 0.25 # Example threshold for low NDMI
    NDVI_DROP_PERCENT_THRESHOLD = 5.0 # Example threshold for significant NDVI drop
    # General thresholds for change significance
    ABSOLUTE_CHANGE_THRESHOLD = 0.02 # Example absolute change for significance
    PERCENT_CHANGE_THRESHOLD = 3.0 # Example percentage change for positive significance
    NEGATIVE_PERCENT_CHANGE_THRESHOLD = 5.0 # Example percentage change for negative significance (can be different)


    current_val = row.get(f'{index_name} (هفته جاری)')
    previous_val = row.get(f'{index_name} (هفته قبل)')
    change_val = row.get('تغییر')

    # Ensure values are floats, handling possible string representations of None or N/A
    try:
        current_val_float = float(str(current_val).replace('N/A', 'nan').replace('None', 'nan'))
    except ValueError:
        current_val_float = np.nan
    try:
        previous_val_float = float(str(previous_val).replace('N/A', 'nan').replace('None', 'nan'))
    except ValueError:
        previous_val_float = np.nan
    try:
        change_val_float = float(str(change_val).replace('N/A', 'nan').replace('None', 'nan'))
    except ValueError:
         # Recalculate change_val_float if needed, based on raw floats
         if pd.notna(current_val_float) and pd.notna(previous_val_float):
              change_val_float = current_val_float - previous_val_float
         else:
              change_val_float = np.nan


    if pd.notna(current_val_float) and pd.notna(previous_val_float) and pd.notna(change_val_float):
        percentage_change = None
        if pd.notna(previous_val_float) and previous_val_float != 0:
            try:
                 percentage_change = (change_val_float / previous_val_float) * 100
            except Exception: # Handle division by zero or other issues
                 percentage_change = None


        is_significant_positive = change_val_float > ABSOLUTE_CHANGE_THRESHOLD or (percentage_change is not None and percentage_change > PERCENT_CHANGE_THRESHOLD)
        is_significant_negative = change_val_float < -ABSOLUTE_CHANGE_THRESHOLD or (percentage_change is not None and percentage_change < -NEGATIVE_PERCENT_CHANGE_THRESHOLD) # Use negative threshold

        if index_name in ['NDVI', 'EVI', 'LAI', 'CVI', 'SAVI']:
            if is_significant_positive:
                return "رشد مثبت / بهبود"
            elif is_significant_negative:
                return "تنش / کاهش"
            else:
                 return "ثابت"
        elif index_name in ['MSI']: # Lower MSI is better
             is_significant_improvement = change_val_float < -ABSOLUTE_CHANGE_THRESHOLD or (percentage_change is not None and percentage_change < -NEGATIVE_PERCENT_CHANGE_THRESHOLD) # Negative change in MSI is improvement
             is_significant_deterioration = change_val_float > ABSOLUTE_CHANGE_THRESHOLD or (percentage_change is not None and percentage_change > PERCENT_CHANGE_THRESHOLD) # Positive change in MSI is deterioration

             if is_significant_improvement:
                return "بهبود (کاهش تنش)"
             elif is_significant_deterioration:
                return "تنش (افزایش MSI)"
             else:
                return "ثابت"
        elif index_name == 'NDMI': # Higher NDMI is better (more moisture)
             is_low_ndmi = pd.notna(current_val_float) and current_val_float <= NDMI_IRRIGATION_THRESHOLD
             is_significant_decrease = change_val_float < -ABSOLUTE_CHANGE_THRESHOLD or (percentage_change is not None and percentage_change < -NEGATIVE_PERCENT_CHANGE_THRESHOLD)


             if is_low_ndmi and is_significant_decrease:
                  return "تنش رطوبتی شدید / نیاز به آبیاری"
             elif is_low_ndmi:
                  return "تنش رطوبتی / نیاز به آبیاری"
             elif is_significant_decrease:
                  return "کاهش رطوبت قابل توجه"
             elif is_significant_positive: # Significant increase in NDMI
                 return "افزایش رطوبت / بهبود"
             else:
                  return "رطوبت ثابت" # Within thresholds or slight non-significant change


        else:
            return "نامشخص"
    elif pd.notna(current_val_float) and pd.isna(previous_val_float):
         # If current data exists but previous doesn't, check current against a fixed threshold if applicable
         if index_name == 'NDMI' and pd.notna(current_val_float) and current_val_float <= NDMI_IRRIGATION_THRESHOLD:
              return "احتمال تنش رطوبتی (بدون داده قبل)"
         # Add similar checks for low values of other indices if they indicate potential issues
         elif index_name in ['NDVI', 'EVI', 'LAI', 'CVI', 'SAVI'] and pd.notna(current_val_float) and current_val_float <= 0.3: # Example low threshold for these indices
              return "پوشش گیاهی پایین (بدون داده قبل)"
         else:
              return "بدون داده هفته قبل"

    elif pd.isna(current_val_float) and pd.notna(previous_val_float):
         return "بدون داده هفته جاری"
    else:
        return "بدون داده"


# ==============================================================================
# Main Application Layout (Using Tabs)
# ==============================================================================

tab1, tab2, tab3 = st.tabs(["📊 پایش مزارع (نقشه و رتبه‌بندی)", "📈 تحلیل داده‌های محاسبات", "💧 تحلیل نیاز آبیاری و کوددهی"])

with tab1:
    st.header("📊 پایش مزارع (نقشه و رتبه‌بندی)")
    st.markdown("""
    <div style="text-align: justify; margin-bottom: 20px;">
    در این بخش می‌توانید وضعیت سلامت و رطوبت مزارع را بر اساس شاخص‌های ماهواره‌ای مشاهده کنید. نقشه، توزیع مکانی شاخص انتخابی را در هفته جاری نمایش می‌دهد و جدول رتبه‌بندی، مقایسه‌ای با هفته قبل ارائه می‌دهد تا مزارع نیازمند توجه بیشتر را شناسایی کنید.
    </div>
    """, unsafe_allow_html=True)


    if farm_data_df.empty:
        st.error("❌ داده‌های مزارع بارگذاری نشد یا خالی است. لطفاً فایل CSV مزارع را بررسی کنید.")
    elif filtered_farms_df.empty:
        st.warning("⚠️ هیچ مزرعه‌ای برای روز و فیلترهای انتخابی یافت نشد. نمایش نقشه و رتبه‌بندی امکان‌پذیر نیست. لطفاً داده‌های مزارع یا فیلترهای انتخابی را بررسی کنید.")
    elif not gee_initialized:
         st.warning("⚠️ اتصال به Google Earth Engine برقرار نیست. نمایش نقشه و شاخص‌های ماهواره‌ای امکان‌پذیر نمی‌باشد.")
    else:
        selected_farm_details = None
        selected_farm_gee_geom = None
        center_lat = INITIAL_LAT
        center_lon = INITIAL_LON
        zoom_level = INITIAL_ZOOM
        is_single_farm = (selected_farm_name != "همه مزارع")

        if is_single_farm:
            selected_farm_details_list = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name]
            if not selected_farm_details_list.empty:
                 selected_farm_details = selected_farm_details_list.iloc[0]
                 lat = selected_farm_details.get('wgs84_centroid_lat')
                 lon = selected_farm_details.get('wgs84_centroid_lon')
                 selected_farm_gee_geom = selected_farm_details.get('ee_geometry')

                 if pd.notna(lat) and pd.notna(lon) and selected_farm_gee_geom is not None:
                     center_lat = lat
                     center_lon = lon
                     zoom_level = 14
                 else:
                      st.warning(f"⚠️ مختصات WGS84 یا هندسه GEE معتبر برای مزرعه '{selected_farm_name}' یافت نشد. نمایش نقشه محدود خواهد باشد.")
                      selected_farm_gee_geom = None


                 st.subheader(f"جزئیات مزرعه: {selected_farm_name} (روز: {selected_day})")
                 details_cols = st.columns(3)
                 with details_cols[0]:
                     st.markdown(modern_metric_card("مساحت داشت (هکتار)", f"{selected_farm_details.get('مساحت', 'N/A'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "N/A", icon="fa-ruler-combined", color="#43cea2"), unsafe_allow_html=True)
                     st.markdown(modern_metric_card("واریته", f"{selected_farm_details.get('واریته', 'نامشخص')}", icon="fa-seedling", color="#43cea2"), unsafe_allow_html=True)
                 with details_cols[1]:
                     st.markdown(modern_metric_card("گروه", f"{selected_farm_details.get('گروه', 'نامشخص')}", icon="fa-users", color="#43cea2"), unsafe_allow_html=True)
                     st.markdown(modern_metric_card("سن", f"{selected_farm_details.get('سن', 'نامشخص')}", icon="fa-hourglass-half", color="#43cea2"), unsafe_allow_html=True)
                 with details_cols[2]:
                     st.markdown(modern_metric_card("مختصات", f"{lat:.5f}, {lon:.5f}" if pd.notna(lat) and pd.notna(lon) else "N/A", icon="fa-map-marker-alt", color="#43cea2"), unsafe_allow_html=True)
            else:
                 st.error(f"❌ جزئیات مزرعه '{selected_farm_name}' در داده‌های فیلتر شده یافت نشد.")
                 is_single_farm = False


        if not is_single_farm:
            all_farm_geometries = [geom for geom in filtered_farms_df['ee_geometry'] if geom is not None]
            if all_farm_geometries:
                try:
                    selected_farm_gee_geom = ee.Geometry.MultiPolygon(all_farm_geometries)
                    center = selected_farm_gee_geom.centroid(maxError=1).getInfo()['coordinates']
                    center_lon, center_lat = center[0], center[1]
                    bounds = selected_farm_gee_geom.bounds().getInfo()
                    
                    # Fix for bounds coordinates access
                    if 'coordinates' in bounds:
                        # New GEE API format uses 'coordinates'
                        coordinates = bounds['coordinates'][0]  # First polygon's coordinates
                        # Find min/max coordinates
                        lon_vals = [coord[0] for coord in coordinates]
                        lat_vals = [coord[1] for coord in coordinates]
                        lon_min, lon_max = min(lon_vals), max(lon_vals)
                        lat_min, lat_max = min(lat_vals), max(lat_vals)
                        lon_diff = lon_max - lon_min
                        lat_diff = lat_max - lat_min
                    elif 'even' in bounds:
                        # Old format
                        lon_diff = bounds['even'][2] - bounds['even'][0]
                        lat_diff = bounds['even'][3] - bounds['even'][1]
                    else:
                        # If both formats fail, extract coordinates differently
                        bbox = selected_farm_gee_geom.bounds().getInfo()
                        if isinstance(bbox, dict) and 'type' in bbox and bbox['type'] == 'Polygon':
                            coordinates = bbox['coordinates'][0]  # First polygon's coordinates
                            lon_vals = [coord[0] for coord in coordinates]
                            lat_vals = [coord[1] for coord in coordinates]
                            lon_min, lon_max = min(lon_vals), max(lon_vals)
                            lat_min, lat_max = min(lat_vals), max(lat_vals)
                            lon_diff = lon_max - lon_min
                            lat_diff = lat_max - lat_min
                        else:
                            # If we can't determine bounds, use default values
                            lon_diff = 1.0
                            lat_diff = 1.0
                            st.info("ℹ️ استفاده از مقادیر پیش‌فرض برای محاسبه زوم نقشه.")
                    
                    # Set zoom level based on the geographic extent
                    if max(lon_diff, lat_diff) > 10: zoom_level = 6
                    elif max(lon_diff, lat_diff) > 5: zoom_level = 8
                    elif max(lon_diff, lat_diff) > 2: zoom_level = 10
                    elif max(lon_diff, lat_diff) > 0.5: zoom_level = 12
                    else: zoom_level = 13

                except Exception as e:
                     st.warning(f"⚠️ خطا در ایجاد هندسه GEE برای همه مزارع: {e}. نقشه با مرکز پیش‌فرض نمایش داده می‌شود.")
                     selected_farm_gee_geom = None
            else:
                st.warning("⚠️ هیچ هندسه GEE معتبری برای مزارع انتخابی یافت نشد. نمایش نقشه محدود خواهد بود.")
                selected_farm_gee_geom = None


            st.subheader(f"نمایش کلی مزارع برای روز: {selected_day}")
            st.markdown(modern_metric_card("تعداد مزارع در این روز", f"{len(filtered_farms_df):,}", icon="fa-leaf", color="#185a9d"), unsafe_allow_html=True)
            st.caption("تعداد کل مزارع ثبت شده برای روز انتخاب شده.")

            if 'واریته' in filtered_farms_df.columns and not filtered_farms_df['واریته'].isna().all():
                variety_counts = filtered_farms_df[filtered_farms_df['واریته'].astype(str).str.lower() != 'نامشخص']['واریته'].value_counts().sort_values(ascending=False)
                if not variety_counts.empty:
                     pie_df = pd.DataFrame({
                         'واریته': variety_counts.index,
                         'تعداد مزرعه': variety_counts.values
                     })
                     fig_pie = px.pie(pie_df, values='تعداد مزرعه', names='واریته',
                                       title=f'درصد واریته‌ها در مزارع روز {selected_day}',
                                       hole=0.3)
                     fig_pie.update_traces(textposition='inside', textinfo='percent+label', insidetextorientation='radial')
                     fig_pie.update_layout(
                         showlegend=True,
                         height=400,
                         margin=dict(l=20, r=20, t=40, b=20),
                         paper_bgcolor='rgba(0,0,0,0)',
                         plot_bgcolor='rgba(0,0,0,0)'
                     )
                     st.plotly_chart(fig_pie, use_container_width=True)
                     st.caption("درصد هر واریته از کل مزارع ثبت شده در این روز.")
                else:
                    st.info("⚠️ داده واریته معتبری برای نمودار در این روز یافت نشد.")
            else:
                st.info("⚠️ ستون واریته در داده‌های این روز وجود ندارد یا خالی است.")


        st.markdown("---")
        st.subheader("🗺️ نقشه وضعیت مزارع")
        st.markdown("نقشه، مقدار شاخص انتخابی را در هفته جاری نمایش می‌دهد.")

        vis_params = {
            'NDVI': {'min': 0.1, 'max': 0.9, 'palette': ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']},
            'EVI': {'min': 0.1, 'max': 0.8, 'palette': ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']},
            'NDMI': {'min': -0.6, 'max': 0.6, 'palette': ['#b2182b', '#ef8a62', '#fddbc7', '#f7f7f7', '#d1e5f0', '#67a9cf', '#2166ac']},
            'LAI': {'min': 0, 'max': 6, 'palette': ['#f7f7f7', '#dcdcdc', '#babcba', '#8aae8b', '#5a9c5a', '#2a8a2a', '#006400']},
            'MSI': {'min': 0.6, 'max': 2.5, 'palette': ['#2166ac', '#67a9cf', '#d1e5f0', '#f7f7f7', '#fddbc7', '#ef8a62', '#b2182b']},
            'CVI_corrected_palette': {'min': 0, 'max': 20, 'palette': ['#ffffb2', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']},
            'SAVI': {'min': 0.1, 'max': 0.8, 'palette': ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']},
        }

        if selected_index == 'CVI':
            index_vis_params = vis_params['CVI_corrected_palette']
        else:
             index_vis_params = vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']})


        m = geemap.Map(
            location=[center_lat, center_lon],
            zoom=zoom_level,
            add_google_map=False
        )
        m.add_basemap("HYBRID")

        gee_image_current = None
        error_msg_current = None
        if gee_initialized and selected_farm_gee_geom is not None and start_date_current_str and end_date_current_str:
             with st.spinner(f"در حال بارگذاری تصویر ماهواره‌ای شاخص {selected_index}..."):
                 gee_image_current, error_msg_current = get_processed_image(
                     selected_farm_gee_geom, start_date_current_str, end_date_current_str, selected_index
                 )

        if gee_image_current:
            try:
                m.addLayer(
                    gee_image_current,
                    index_vis_params,
                    f"{selected_index} ({start_date_current_str} تا {end_date_current_str})"
                )

                farm_boundary_collection = ee.FeatureCollection([ee.Feature(geom) for geom in filtered_farms_df['ee_geometry'] if geom is not None])
                if not farm_boundary_collection.size().getInfo() == 0:
                     m.addLayer(
                         farm_boundary_collection,
                         {'color': 'yellow', 'fillColor': '00000000'},
                         'محدوده مزارع'
                     )
                else:
                     st.warning("⚠️ هندسه مزارع برای نمایش لایه مرزی یافت نشد.")


                legend_title = f"راهنمای شاخص {selected_index}"
                legend_description = ""

                if selected_index in ['NDVI', 'EVI', 'LAI', 'CVI', 'SAVI']:
                     legend_description = "(نشان‌دهنده وضعیت پوشش گیاهی/سلامت، مقادیر بالاتر بهتر است)"
                     palette_colors = index_vis_params.get('palette', ['red', 'yellow', 'green'])
                     color_low = palette_colors[0] if palette_colors else 'red'
                     color_mid = palette_colors[len(palette_colors)//2] if palette_colors else 'yellow'
                     color_high = palette_colors[-1] if palette_colors else 'green'
                     legend_text = f'''
                     <p style="margin: 0;"><span style="color: {color_low};">مقدار کم</span> / <span style="color: {color_mid};">متوسط</span> / <span style="color: {color_high};">مقدار زیاد</span></p>
                     '''
                elif selected_index in ['NDMI']:
                     legend_description = "(نشان‌دهنده رطوبت خاک، مقادیر بالاتر بهتر است)"
                     palette_colors = index_vis_params.get('palette', ['brown', 'white', 'blue'])
                     color_low = palette_colors[0] if palette_colors else 'brown'
                     color_mid = palette_colors[len(palette_colors)//2] if palette_colors else 'white'
                     color_high = palette_colors[-1] if palette_colors else 'blue'
                     legend_text = f'''
                     <p style="margin: 0;"><span style="color: {color_low};">خشک (کم)</span> / <span style="color: {color_mid};">متوسط</span> / <span style="color: {color_high};">مرطوب (زیاد)</span></p>
                     '''
                elif selected_index in ['MSI']:
                     legend_description = "(نشان‌دهنده تنش رطوبتی، مقادیر پایین‌تر بهتر است)"
                     palette_colors = index_vis_params.get('palette', ['blue', 'white', 'brown'])
                     color_low = palette_colors[0] if palette_colors else 'blue'
                     color_mid = palette_colors[len(palette_colors)//2] if palette_colors else 'white'
                     color_high = palette_colors[-1] if palette_colors else 'brown'
                     legend_text = f'''
                     <p style="margin: 0;"><span style="color: {color_low};">مرطوب (کم)</span> / <span style="color: {color_mid};">متوسط</span> / <span style="color: {color_high};">خشک (زیاد)</span></p>
                     '''
                else:
                    legend_text = '''
                    <p style="margin: 0;">راهنمای مقادیر شاخص</p>
                    '''

                legend_html = f'''
                <div style="position: fixed; bottom: 50px; right: 10px; z-index: 1000; background-color: rgba(255, 255, 255, 0.9); padding: 10px; border: 1px solid grey; border-radius: 8px; font-family: Vazirmatn, sans-serif; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <p style="margin: 0;"><strong>{legend_title}</strong></p>
                    {legend_text}
                    <p style="margin: 0; font-size: 0.8em; opacity: 0.8;">{legend_description}</p>
                </div>
                '''
                m.get_root().html.add_child(folium.Element(legend_html))

                ranking_df_map_popups = pd.DataFrame()
                if not is_single_farm and start_date_current_str and end_date_current_str and start_date_previous_str and end_date_previous_str:
                     with st.spinner("در حال آماده‌سازی اطلاعات مزارع برای نمایش در پاپ‌آپ‌های نقشه..."):
                         # Re-calculate indices for popups only if not single farm, to save computation
                         # This calculation is parallelized within the function if possible
                         ranking_df_map_popups, popup_calculation_errors = calculate_weekly_indices_for_table(
                              filtered_farms_df,
                              selected_index,
                              start_date_current_str,
                              end_date_current_str,
                              start_date_previous_str,
                              end_date_previous_str
                         )
                         if popup_calculation_errors:
                             st.warning("⚠️ برخی خطاها در حین محاسبه شاخص‌ها برای پاپ‌آپ‌های نقشه رخ داد (تا ۵ خطا):")
                             for error in popup_calculation_errors[:5]: st.warning(f"- {error}")


                if not filtered_farms_df.empty:
                     for idx, farm in filtered_farms_df.iterrows():
                          lat = farm.get('wgs84_centroid_lat')
                          lon = farm.get('wgs84_centroid_lon')

                          if pd.notna(lat) and pd.notna(lon):
                               farm_name = farm.get('مزرعه', 'نامشخص')
                               group = farm.get('گروه', 'نامشخص')
                               age = farm.get('سن', 'نامشخص')
                               variety = farm.get('واریته', 'نامشخص')

                               current_index_val = 'N/A'
                               previous_index_val = 'N/A'
                               change_val_display = 'N/A'
                               status_text = "بدون داده"

                               # Get data for popup: use ranking_df if single farm, or ranking_df_map_popups if all farms
                               farm_data_for_popup = None
                               if is_single_farm and 'ranking_df' in locals() and not ranking_df.empty:
                                    farm_data_for_popup_list = ranking_df[ranking_df['مزرعه'] == farm_name]
                                    if not farm_data_for_popup_list.empty:
                                         farm_data_for_popup = farm_data_for_popup_list.iloc[0]
                               elif not is_single_farm and not ranking_df_map_popups.empty:
                                    farm_data_for_popup_list = ranking_df_map_popups[ranking_df_map_popups['مزرعه'] == farm_name]
                                    if not farm_data_for_popup_list.empty:
                                        farm_data_for_popup = farm_data_for_popup_list.iloc[0]


                               if farm_data_for_popup is not None:
                                    current_index_val_raw = farm_data_for_popup.get(f'{selected_index} (هفته جاری)')
                                    previous_index_val_raw = farm_data_for_popup.get(f'{selected_index} (هفته قبل)')
                                    change_val_raw = farm_data_for_popup.get('تغییر')

                                    # Format for display, handling None/N/A/nan
                                    current_index_val = f"{float(str(current_index_val_raw).replace('N/A', 'nan').replace('None', 'nan')):.3f}" if pd.notna(current_index_val_raw) and str(current_index_val_raw) != 'N/A' and str(current_index_val_raw) != 'None' else 'N/A'
                                    previous_index_val = f"{float(str(previous_index_val_raw).replace('N/A', 'nan').replace('None', 'nan')):.3f}" if pd.notna(previous_index_val_raw) and str(previous_index_val_raw) != 'N/A' and str(previous_index_val_raw) != 'None' else 'N/A'
                                    change_val_display = f"{float(str(change_val_raw).replace('N/A', 'nan').replace('None', 'nan')):.3f}" if pd.notna(change_val_raw) and str(change_val_raw) != 'N/A' and str(change_val_raw) != 'None' else 'N/A'

                                    status_text = determine_status(farm_data_for_popup, selected_index)
                               else:
                                   # If no data found for this farm in the ranking/popup df, try getting just the current value
                                   try:
                                       point_geom_single = ee.Geometry.Point([lon, lat])
                                       current_img_single, err_single = get_processed_image(point_geom_single, start_date_current_str, end_date_current_str, selected_index)
                                       if current_img_single:
                                           current_val_single = current_img_single.reduceRegion(
                                               reducer=ee.Reducer.first(),
                                               geometry=point_geom_single,
                                               scale=10,
                                               bestEffort=True
                                           ).get(selected_index).getInfo()
                                           current_index_val = f"{float(str(current_val_single).replace('None', 'nan')):.3f}" if pd.notna(current_val_single) and str(current_val_single) != 'None' else 'N/A'
                                           status_text = "بدون داده هفته قبل" if pd.notna(current_val_single) else "بدون داده"
                                       else:
                                            status_text = "بدون داده"
                                            if err_single: print(f"Error getting single farm current index for popup ({farm_name}): {err_single}")
                                   except Exception as e:
                                       print(f"Error getting single farm current index for popup ({farm_name}): {e}")
                                       status_text = "خطا در داده"


                               popup_html = f"""
                               <strong>مزرعه:</strong> {farm_name}<br>
                               <strong>گروه:</strong> {group}<br>
                               <strong>سن:</strong> {age}<br>
                               <strong>واریته:</strong> {variety}<br>
                               ---<br>
                               <strong>{selected_index} (جاری):</strong> {current_index_val} <br>
                               <strong>{selected_index} (قبلی):</strong> {previous_index_val} <br>
                               <strong>تغییر:</strong> {change_val_display} <br>
                               <strong>وضعیت:</strong> {status_text}
                               """

                               marker_icon = 'info-sign'
                               marker_color = 'blue'
                               if is_single_farm:
                                    marker_icon = 'star'
                                    marker_color = 'red'

                               folium.Marker(
                                   location=[lat, lon],
                                   popup=folium.Popup(popup_html, max_width=300),
                                   tooltip=farm_name,
                                   icon=folium.Icon(color=marker_color, icon=marker_icon, prefix='fa')
                               ).add_to(m)


                m.add_layer_control()

            except Exception as map_err:
                st.error(f"❌ خطا در افزودن لایه GEE به نقشه: {map_err}")
                st.error(traceback.format_exc())
        else:
            st.warning(f"⚠️ تصویری برای نمایش شاخص {selected_index} روی نقشه در بازه فعلی یافت نشد. ({error_msg_current})")


        map_placeholder = st.empty()
        with map_placeholder:
             st_folium(m, width=None, height=500, use_container_width=True)

        st.caption("برای مشاهده جزئیات روی مارکرها کلیک کنید. از کنترل لایه‌ها در سمت راست بالا برای تغییر نقشه پایه و لایه شاخص استفاده کنید.")
        st.info("💡 برای ذخیره نقشه، می‌توانید از ابزار عکس گرفتن از صفحه (Screenshot) مرورگر یا سیستم عامل خود استفاده کنید.")


        st.markdown("---")
        st.subheader(f"📈 نمودار روند زمانی شاخص {selected_index}")
        st.markdown("روند تغییرات شاخص انتخابی برای مزرعه در یک سال گذشته (بر اساس تصاویر ماهواره‌ای بدون ابر).")

        if not is_single_farm:
            st.info("ℹ️ لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
        elif not gee_initialized:
             st.warning("⚠️ اتصال به Google Earth Engine برقرار نیست. نمودار روند زمانی در دسترس نمی‌باشد.")
        elif selected_farm_details is None or pd.isna(selected_farm_details.get('wgs84_centroid_lat')) or pd.isna(selected_farm_details.get('wgs84_centroid_lon')):
             st.warning(f"⚠️ مختصات WGS84 معتبر برای مزرعه '{selected_farm_name}' یافت نشد. نمودار روند زمانی امکان‌پذیر نیست.")
        else:
             point_geom_ts = ee.Geometry.Point([selected_farm_details['wgs84_centroid_lon'], selected_farm_details['wgs84_centroid_lat']])

             timeseries_end_date = today.strftime('%Y-%m-%d')
             timeseries_start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d')

             ts_df, ts_error = get_index_time_series(
                 point_geom_ts,
                 selected_index,
                 start_date=timeseries_start_date,
                 end_date=timeseries_end_date
             )

             if ts_error:
                 st.warning(f"⚠️ خطا در دریافت داده‌های سری زمانی: {ts_error}")
             elif not ts_df.empty:
                 fig_ts = px.line(ts_df, y=selected_index, title=f'روند زمانی شاخص {selected_index} برای مزرعه {selected_farm_name}')
                 fig_ts.update_layout(
                     xaxis_title="تاریخ",
                     yaxis_title=selected_index,
                     hovermode="x unified",
                     margin=dict(l=20, r=20, t=40, b=20),
                     paper_bgcolor='rgba(0,0,0,0)',
                     plot_bgcolor='rgba(0,0,0,0)'
                 )
                 st.plotly_chart(fig_ts, use_container_width=True)
                 st.caption(f"نمودار تغییرات شاخص {selected_index} برای مزرعه {selected_farm_name} در یک سال گذشته (بر اساس تصاویر ماهواره‌ای بدون ابر).")
             else:
                 st.info(f"ℹ️ داده‌ای برای نمایش نمودار سری زمانی شاخص {selected_index} در بازه مشخص شده یافت نشد (احتمالاً به دلیل پوشش ابری مداوم).")


        st.markdown("---")
        st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day})")
        st.markdown("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل و تعیین وضعیت هر مزرعه.")

        @st.cache_data(show_spinner=False, persist="disk")
        def calculate_weekly_indices_for_table(
            _farms_df, index_name, start_curr, end_curr, start_prev, end_prev
        ):
            results = []
            errors = []
            total_farms = len(_farms_df)
            progress_placeholder = st.empty()


            for i, (idx, farm) in enumerate(_farms_df.iterrows()):
                farm_name = farm.get('مزرعه', f'مزرعه ناشناس ردیف {i+1}')
                farm_gee_geom = farm.get('ee_geometry')

                if farm_gee_geom is None:
                    errors.append(f"هندسه GEE نامعتبر برای مزرعه '{farm_name}'. نادیده گرفته شد.")
                    results.append({
                         'مزرعه': farm_name,
                         'گروه': farm.get('گروه', 'نامشخص'),
                         f'{index_name} (هفته جاری)': None,
                         f'{index_name} (هفته قبل)': None,
                         'تغییر': None,
                         'سن': farm.get('سن', 'نامشخص'),
                         'واریته': farm.get('واریته', 'نامشخص'),
                     })
                    progress = (i + 1) / total_farms
                    progress_placeholder.markdown(modern_progress_bar(progress), unsafe_allow_html=True)
                    continue

                def get_mean_value_single_index(start, end, index):
                     try:
                          image, error = get_processed_image(farm_gee_geom, start, end, index)
                          if image:
                              # Select the band explicitly before reducing to avoid projection issues
                              mean_dict = image.select(index).reduceRegion(
                                  reducer=ee.Reducer.mean(),
                                  geometry=farm_gee_geom,
                                  scale=10,
                                  bestEffort=True,
                                  maxPixels=1e8
                              ).get(index).getInfo()
                              return mean_dict, None
                          else:
                              return None, error
                     except ee.EEException as e:
                          # Check for common errors and provide more specific messages
                          error_message = f"GEE Error for {farm_name} ({start}-{end}): {e}"
                          try:
                               error_details = e.args[0] if e.args else str(e)
                               if isinstance(error_details, str) and 'computation timed out' in error_details.lower():
                                   error_message += "\n(احتمالاً به دلیل حجم بالای پردازش یا بازه زمانی طولانی)"
                               elif isinstance(error_details, str) and 'user memory limit exceeded' in error_details.lower():
                                   error_message += "\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده)"
                               elif isinstance(error_details, str) and 'Image.projection: The bands of the specified image contains different projections' in error_details:
                                    error_message += "\n(خطای پروجکشن داخلی در GEE. ممکن است با تلاش مجدد یا بازه زمانی متفاوت برطرف شود.)"
                          except Exception:
                               pass
                          return None, error_message
                     except Exception as e:
                          return None, f"Unknown Error for {farm_name} ({start}-{end}): {e}"


                current_val, err_curr = get_mean_value_single_index(start_curr, end_curr, index_name)
                if err_curr: errors.append(f"مزرعه '{farm_name}' (هفته جاری): {err_curr}")

                previous_val, err_prev = get_mean_value_single_index(start_prev, end_prev, index_name)
                if err_prev: errors.append(f"مزرعه '{farm_name}' (هفته قبل): {err_prev}")

                change = None
                if pd.notna(current_val) and pd.notna(previous_val):
                    try:
                        change = current_val - previous_val
                    except TypeError:
                        change = None


                results.append({
                    'مزرعه': farm_name,
                    'گروه': farm.get('گروه', 'نامشخص'),
                    f'{index_name} (هفته جاری)': current_val, # Store raw numerical value here
                    f'{index_name} (هفته قبل)': previous_val, # Store raw numerical value here
                    'تغییر': change, # Store raw numerical value here
                    'سن': farm.get('سن', 'نامشخص'),
                    'واریته': farm.get('واریته', 'نامشخص'),
                })

                progress = (i + 1) / total_farms
                progress_placeholder.markdown(modern_progress_bar(progress), unsafe_allow_html=True)

            progress_placeholder.empty()
            return pd.DataFrame(results), errors

        ranking_df = pd.DataFrame()
        calculation_errors = []

        if gee_initialized and start_date_current_str and end_date_current_str and start_date_previous_str and end_date_previous_str and not filtered_farms_df.empty:
             ranking_df, calculation_errors = calculate_weekly_indices_for_table(
                 filtered_farms_df,
                 selected_index,
                 start_date_current_str,
                 end_date_current_str,
                 start_date_previous_str,
                 end_date_previous_str
             )
        elif not gee_initialized:
             st.warning("⚠️ اتصال به Google Earth Engine برقرار نیست. جدول رتبه‌بندی در دسترس نمی‌باشد.")
        elif filtered_farms_df.empty:
             st.warning("⚠️ هیچ مزرعه‌ای برای محاسبه رتبه‌بندی یافت نشد.")
        else:
             st.warning("⚠️ بازه‌های زمانی معتبر برای محاسبه رتبه‌بندی در دسترس نیست.")


        if calculation_errors:
            st.warning("⚠️ برخی خطاها در حین محاسبه شاخص‌ها برای رتبه‌بندی رخ داد (تا ۱۰ خطا):")
            for error in calculation_errors[:10]:
                st.warning(f"- {error}")
            if len(calculation_errors) > 10:
                st.warning(f"... و {len(calculation_errors) - 10} خطای دیگر.")


        if not ranking_df.empty:
            ascending_sort = selected_index == 'MSI'

            sort_col_name_raw = f'{selected_index} (هفته جاری)'

            if sort_col_name_raw in ranking_df.columns:
                # Sort directly on the raw numerical column (which might have None/NaN)
                # Use 'na_position' to control where missing values appear
                ranking_df_sorted = ranking_df.sort_values(
                    by=sort_col_name_raw,
                    ascending=ascending_sort,
                    na_position='last' # Place missing values at the end
                ).reset_index(drop=True)
            else:
                 st.warning(f"⚠️ ستون '{sort_col_name_raw}' برای مرتب‌سازی جدول یافت نشد.")
                 ranking_df_sorted = ranking_df.copy()


            if not ranking_df_sorted.empty:
                 ranking_df_sorted.index = ranking_df_sorted.index + 1
                 ranking_df_sorted.index.name = 'رتبه'

                 # Calculate status AFTER sorting, based on the sorted data (which has raw numbers)
                 ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(
                     lambda row: determine_status(row, selected_index), axis=1
                 )

                 ranking_df_sorted['وضعیت_نمایش'] = ranking_df_sorted['وضعیت'].apply(lambda s: status_badge(s))

                 # Format the numerical columns for display AFTER status calculation and sorting
                 cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
                 for col in cols_to_format:
                     if col in ranking_df_sorted.columns:
                          # Convert numerical values to formatted strings, leaving None/NaN as N/A
                          ranking_df_sorted[col] = ranking_df_sorted[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")


                 display_columns = ['مزرعه', 'گروه', 'سن', 'واریته'] + cols_to_format + ['وضعیت_نمایش']
                 final_display_columns = [col for col in display_columns if col in ranking_df_sorted.columns]

                 ranking_df_display = ranking_df_sorted[final_display_columns].rename(columns={'وضعیت_نمایش': 'وضعیت'})

                 st.write("<style>td {vertical-align: middle !important;}</style>", unsafe_allow_html=True)
                 st.write(ranking_df_display.to_html(escape=False, index=True), unsafe_allow_html=True)

                 st.subheader("📊 خلاصه وضعیت مزارع (بر اساس رتبه‌بندی)")

                 status_counts = ranking_df_sorted['وضعیت'].value_counts()

                 # Define groups based on keywords
                 positive_terms = [s for s in status_counts.index if "بهبود" in s or "رشد مثبت" in s or "افزایش رطوبت" in s]
                 negative_terms = [s for s in status_counts.index if any(sub in s for sub in ["تنش", "کاهش", "بدتر", "نیاز"])]
                 neutral_terms = [s for s in status_counts.index if any(sub in s for sub in ["ثابت", "رطوبت ثابت", "پوشش گیاهی پایین", "قابل توجه"])] # Added 'قابل توجه' for NDMI decrease
                 nodata_terms = [s for s in status_counts.index if "بدون داده" in s or "N/A" in s] # Added N/A for completeness

                 col1, col2, col3, col4 = st.columns(4)

                 with col1:
                     pos_count = sum(status_counts.get(term, 0) for term in positive_terms)
                     st.metric("🟢 بهبود", pos_count)

                 with col2:
                     neutral_count = sum(status_counts.get(term, 0) for term in neutral_terms)
                     st.metric("⚪ ثابت", neutral_count)

                 with col3:
                     neg_count = sum(status_counts.get(term, 0) for term in negative_terms)
                     st.metric("🔴 تنش", neg_count)

                 with col4:
                      nodata_count = sum(status_counts.get(term, 0) for term in nodata_terms)
                      st.metric("🟡 بدون داده", nodata_count)

                 st.info(f"""
                 **توضیحات وضعیت:**
                 - **🟢 بهبود/رشد مثبت**: مزارعی که نسبت به هفته قبل بهبود قابل توجهی داشته‌اند (افزایش شاخص‌هایی مانند NDVI یا کاهش شاخص‌هایی مانند MSI) یا افزایش رطوبت نشان می‌دهند.
                 - **⚪ ثابت**: مزارعی که تغییر معناداری در شاخص نداشته‌اند (درون آستانه تغییر) یا وضعیت پایداری دارند (مثل رطوبت ثابت یا پوشش گیاهی پایین بدون تغییر). شامل کاهش‌های رطوبت که به حد تنش نرسیده‌اند.
                 - **🔴 تنش/کاهش/بدتر شدن**: مزارعی که نسبت به هفته قبل وضعیت نامطلوب‌تری داشته‌اند (کاهش شاخص‌هایی مانند NDVI یا افزایش شاخص‌هایی مانند MSI) یا نیاز آبیاری/کودی تشخیص داده شده است. شامل تنش رطوبتی یا کاهش رطوبت قابل توجه.
                 - **🟡 بدون داده**: مزارعی که به دلیل عدم دسترسی به تصاویر ماهواره‌ای بدون ابر در یک یا هر دو بازه زمانی، امکان محاسبه تغییرات وجود نداشته است.
                 """)

                 st.markdown("---")
                 st.subheader("🤖 خلاصه هوش مصنوعی از وضعیت مزارع")
                 if gemini_model:
                      with st.spinner("در حال تولید خلاصه هوش مصنوعی..."):
                          ai_map_summary = get_ai_map_summary(gemini_model, ranking_df_sorted, selected_index, selected_day)
                      st.markdown(ai_map_summary)
                 else:
                      st.info("⚠️ سرویس تحلیل هوش مصنوعی پیکربندی نشده یا در دسترس نیست.")

                 ranking_df_clean = ranking_df_sorted.drop(columns=['وضعیت_نمایش'], errors='ignore')
                 # Format numerical columns back to string for CSV export if desired, or keep as numbers
                 # Let's keep them as numbers for potential further analysis outside the app
                 csv_data = ranking_df_clean.to_csv(index=True).encode('utf-8')
                 st.download_button(
                     label="📥 دانلود جدول رتبه‌بندی (CSV)",
                     data=csv_data,
                     file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv',
                     mime='text/csv',
                 )
            else:
                 st.info("⚠️ داده‌های جدول رتبه‌بندی پس از مرتب‌سازی خالی است. ممکن است مشکلی در داده‌های ورودی یا مرتب‌سازی وجود داشته باشد.")
        else:
            st.info(f"ℹ️ داده‌ای برای جدول رتبه‌بندی بر اساس شاخص {selected_index} در این بازه زمانی یافت نشد (احتمالاً به دلیل عدم دسترسی به تصاویر ماهواره‌ای بدون ابر).")


    st.markdown("---")


with tab2:
    st.header("📈 تحلیل داده‌های فایل محاسبات")
    st.markdown("""
    <div style="text-align: justify; margin-bottom: 20px;">
    در این بخش می‌توانید داده‌های بارگذاری شده از فایل محاسبات مساحت و تولید را به‌صورت نمودارهای تعاملی مشاهده کنید. این نمودارها توزیع مساحت و تولید را بر اساس اداره، سن و واریته نمایش می‌دهند.
    </div>
    """, unsafe_allow_html=True)


    if analysis_area_df is None and analysis_prod_df is None:
        st.error("❌ داده‌های تحلیل از فایل 'محاسبات 2.csv' بارگذاری یا پردازش نشدند. لطفاً فایل را بررسی کنید.")
    else:
        available_edareh = []
        if analysis_area_df is not None and 'اداره' in analysis_area_df.index.names:
            available_edareh.extend(analysis_area_df.index.get_level_values('اداره').unique().tolist())
        if analysis_prod_df is not None and 'اداره' in analysis_prod_df.index.names:
            available_edareh.extend(analysis_prod_df.index.get_level_values('اداره').unique().tolist())

        available_edareh = sorted(list(set(e for e in available_edareh if e is not None)))

        if not available_edareh:
            st.warning("⚠️ هیچ اداره‌ای برای نمایش در داده‌های تحلیلی یافت نشد. لطفاً ساختار فایل 'محاسبات 2.csv' را بررسی کنید.")
        else:
            selected_edareh = st.selectbox(
                "اداره مورد نظر را برای تحلیل انتخاب کنید:",
                options=available_edareh,
                key='analysis_edareh_select'
            )

            st.subheader(f"داده‌های اداره: {selected_edareh}")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### مساحت (هکتار)")
                if analysis_area_df is not None and selected_edareh in analysis_area_df.index.get_level_values('اداره').unique():
                    try:
                        df_area_selected = analysis_area_df.loc[selected_edareh].copy()

                        ages = df_area_selected.index.tolist()
                        varieties = df_area_selected.columns.tolist()
                        z_data = df_area_selected.values

                        if len(ages) > 1 and len(varieties) > 1 and z_data.shape[0] > 1 and z_data.shape[1] > 1:
                             try:
                                 fig_3d_area = go.Figure(data=[go.Surface(z=z_data, x=ages, y=varieties, colorscale='Viridis')])
                                 fig_3d_area.update_layout(
                                     title=f'نمودار سطح مساحت - اداره {selected_edareh}',
                                     scene=dict(
                                         xaxis_title='سن',
                                         yaxis_title='واریته',
                                         zaxis_title='مساحت (هکتار)'),
                                     autosize=True, height=500,
                                     margin=dict(l=0, r=0, t=40, b=0),
                                     paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
                                 )
                                 st.plotly_chart(fig_3d_area, use_container_width=True)
                                 st.caption("نمایش توزیع مساحت بر اساس سن و واریته در یک سطح سه بعدی تعاملی.")
                             except Exception as e:
                                 st.error(f"❌ خطا در ایجاد نمودار Surface Plot مساحت: {e}")
                                 st.dataframe(df_area_selected)
                        else:
                             st.info("ℹ️ داده کافی برای رسم نمودار Surface Plot مساحت وجود ندارد (نیاز به بیش از یک مقدار سن و یک واریته با داده).")
                             st.dataframe(df_area_selected)


                        if 'سن' in df_area_selected.index.names:
                             df_area_melt = df_area_selected.reset_index().melt(id_vars='سن', var_name='واریته', value_name='مساحت')
                        else:
                              st.warning("⚠️ ساختار داده مساحت برای هیستوگرام غیرمنتظره است. نمایش هیستوگرام امکان‌پذیر نیست.")
                              df_area_melt = pd.DataFrame()

                        df_area_melt = df_area_melt.dropna(subset=['مساحت', 'واریته', 'سن'])
                        df_area_melt = df_area_melt[pd.to_numeric(df_area_melt['سن'], errors='coerce').notna()]


                        if not df_area_melt.empty:
                            try:
                                fig_hist_area = px.histogram(df_area_melt, x='واریته', y='مساحت', color='سن',
                                                           title=f'هیستوگرام مساحت بر اساس واریته و سن - اداره {selected_edareh}',
                                                           labels={'مساحت':'مجموع مساحت (هکتار)'},
                                                           barmode='group',
                                                           text_auto=True)
                                fig_hist_area.update_layout(
                                     margin=dict(l=0, r=0, t=40, b=0),
                                     paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
                                )
                                st.plotly_chart(fig_hist_area, use_container_width=True)
                                st.caption("توزیع مساحت هر واریته به تفکیک سن.")
                            except Exception as e:
                                 st.error(f"❌ خطا در ایجاد نمودار هیستوگرام مساحت: {e}")
                                 st.dataframe(df_area_selected)
                        else:
                             st.info(f"ℹ️ داده معتبری برای هیستوگرام مساحت در اداره {selected_edareh} یافت نشد.")

                    except KeyError:
                        st.error(f"❌ خطای دسترسی به داده اداره '{selected_edareh}' در داده مساحت. لطفاً ستون 'اداره' را بررسی کنید.")
                    except Exception as e:
                         st.error(f"❌ خطای غیرمنتظره در پردازش داده مساحت برای اداره '{selected_edareh}': {e}")
                         st.error(traceback.format_exc())

                else:
                    st.info(f"⚠️ داده مساحت برای اداره {selected_edareh} یافت نشد یا بارگذاری نشده است.")

            with col2:
                st.markdown("#### تولید (تن)")
                if analysis_prod_df is not None and selected_edareh in analysis_prod_df.index.get_level_values('اداره').unique():
                    try:
                        df_prod_selected = analysis_prod_df.loc[selected_edareh].copy()

                        ages_prod = df_prod_selected.index.tolist()
                        varieties_prod = df_prod_selected.columns.tolist()
                        z_data_prod = df_prod_selected.values

                        if len(ages_prod) > 1 and len(varieties_prod) > 1 and z_data_prod.shape[0] > 1 and z_data_prod.shape[1] > 1:
                             try:
                                 fig_3d_prod = go.Figure(data=[go.Surface(z=z_data_prod, x=ages_prod, y=varieties_prod, colorscale='Plasma')])
                                 fig_3d_prod.update_layout(
                                     title=f'نمودار سطح تولید - اداره {selected_edareh}',
                                     scene=dict(
                                         xaxis_title='سن',
                                         yaxis_title='واریته',
                                         zaxis_title='تولید (تن)'),
                                     autosize=True, height=500,
                                     margin=dict(l=0, r=0, t=40, b=0),
                                     paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
                                 )
                                 st.plotly_chart(fig_3d_prod, use_container_width=True)
                                 st.caption("نمایش توزیع تولید بر اساس سن و واریته در یک سطح سه بعدی تعاملی.")
                             except Exception as e:
                                  st.error(f"❌ خطا در ایجاد نمودار Surface Plot تولید: {e}")
                                  st.dataframe(df_prod_selected)
                        else:
                             st.info("ℹ️ داده کافی برای رسم نمودار Surface Plot تولید وجود ندارد (نیاز به بیش از یک مقدار سن و یک واریته با داده).")
                             st.dataframe(df_prod_selected)


                        if 'سن' in df_prod_selected.index.names:
                            df_prod_melt = df_prod_selected.reset_index().melt(id_vars='سن', var_name='واریته', value_name='تولید')
                        else:
                             st.warning("⚠️ ساختار داده تولید برای هیستوگرام غیرمنتظره است. نمایش هیستوگرام امکان‌پذیر نیست.")
                             df_prod_melt = pd.DataFrame()

                        df_prod_melt = df_prod_melt.dropna(subset=['تولید', 'واریته', 'سن'])
                        df_prod_melt = df_prod_melt[pd.to_numeric(df_prod_melt['سن'], errors='coerce').notna()]


                        if not df_prod_melt.empty:
                            try:
                                fig_hist_prod = px.histogram(df_prod_melt, x='واریته', y='تولید', color='سن',
                                                           title=f'هیستوگرام تولید بر اساس واریته و سن - اداره {selected_edareh}',
                                                           labels={'تولید':'مجموع تولید (تن)'},
                                                           barmode='group',
                                                           text_auto=True)
                                fig_hist_prod.update_layout(
                                     margin=dict(l=0, r=0, t=40, b=0),
                                     paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
                                )
                                st.plotly_chart(fig_hist_prod, use_container_width=True)
                                st.caption("توزیع تولید هر واریته به تفکیک سن.")
                            except Exception as e:
                                 st.error(f"❌ خطا در ایجاد نمودار هیستوگرام تولید: {e}")
                                 st.dataframe(df_prod_selected)
                        else:
                             st.info(f"ℹ️ داده معتبری برای هیستوگرام تولید در اداره {selected_edareh} یافت نشد.")

                    except KeyError:
                         st.error(f"❌ خطای دسترسی به داده اداره '{selected_edareh}' در داده تولید. لطفاً ستون 'اداره' را بررسی کنید.")
                    except Exception as e:
                         st.error(f"❌ خطای غیرمنتظره در پردازش داده تولید برای اداره '{selected_edareh}': {e}")
                         st.error(traceback.format_exc())
                else:
                    st.info(f"⚠️ داده تولید برای اداره {selected_edareh} یافت نشد یا بارگذاری نشده است.")

    st.markdown("---")


with tab3:
    st.header("💧 تحلیل نیاز آبیاری و کوددهی")
    st.markdown("""
    <div style="text-align: justify; margin-bottom: 20px;">
    این بخش به شما کمک می‌کند تا با استفاده از شاخص‌های ماهواره‌ای مانند NDMI (رطوبت) و NDVI (سلامت پوشش گیاهی)، نیازهای احتمالی آبیاری و کوددهی مزرعه انتخابی را ارزیابی کنید. توصیه‌های اولیه بر اساس آستانه‌های از پیش تعیین شده ارائه می‌شوند و سپس تحلیل هوش مصنوعی دیدگاه جامع‌تری را فراهم می‌کند.
    </div>
    """, unsafe_allow_html=True)


    is_single_farm = (selected_farm_name != "همه مزارع")

    # Need to get farm needs data only if a single farm is selected and GEE is initialized
    farm_needs_data = {'error': "لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید."}
    if is_single_farm and gee_initialized and selected_farm_details is not None and selected_farm_details.get('ee_geometry') is not None and start_date_current_str and end_date_current_str and start_date_previous_str and end_date_previous_str:
         with st.spinner("در حال دریافت داده‌های شاخص برای تحلیل نیازها..."):
             farm_needs_data = get_farm_needs_data(selected_farm_details.get('ee_geometry'), start_date_current_str, end_date_current_str, start_date_previous_str, end_date_previous_str)
    elif is_single_farm and gee_initialized and (selected_farm_details is None or selected_farm_details.get('ee_geometry') is None):
         farm_needs_data = {'error': f"هندسه GEE معتبر برای مزرعه '{selected_farm_name}' یافت نشد."}
    elif is_single_farm and not gee_initialized:
         farm_needs_data = {'error': "Google Earth Engine مقداردهی اولیه نشده است."}
    elif is_single_farm and (not start_date_current_str or not end_date_current_str or not start_date_previous_str or not end_date_previous_str):
         farm_needs_data = {'error': "بازه‌های زمانی معتبر برای تحلیل نیازها در دسترس نیست."}


    if not is_single_farm:
        st.info("⚠️ لطفاً یک مزرعه خاص را از پنل کناری (سمت چپ) انتخاب کنید تا تحلیل نیازهای آن نمایش داده شود.")
    elif farm_needs_data.get('error'):
         st.error(f"❌ خطا در دریافت داده‌های شاخص برای تحلیل نیازها: {farm_needs_data['error']}")
    elif pd.isna(farm_needs_data.get('NDMI_curr')) and pd.isna(farm_needs_data.get('NDVI_curr')):
        st.warning("⚠️ داده‌های شاخص لازم (NDMI و NDVI) برای تحلیل در دوره فعلی یافت نشد. (ممکن است به دلیل پوشش ابری یا خطای پردازش باشد).")
        st.markdown("---")
        st.markdown("#### تحلیل هوش مصنوعی")
        st.info("⚠️ به دلیل عدم دسترسی به داده‌های شاخص، تحلیل هوش مصنوعی امکان‌پذیر نیست.")

    else:
        st.subheader(f"تحلیل برای مزرعه: {selected_farm_name}")

        st.markdown("---")
        st.markdown("#### نتایج شاخص‌ها (هفته جاری و قبل)")

        st.markdown("**مقادیر شاخص‌ها:**")
        idx_cols = st.columns(4)
        with idx_cols[0]:
            display_val = f"{farm_needs_data['NDVI_curr']:.3f}" if pd.notna(farm_needs_data.get('NDVI_curr')) else "N/A"
            st.metric("NDVI (جاری)", display_val)
        with idx_cols[1]:
            display_val = f"{farm_needs_data['NDMI_curr']:.3f}" if pd.notna(farm_needs_data.get('NDMI_curr')) else "N/A"
            st.metric("NDMI (جاری)", display_val)
        with idx_cols[2]:
            display_val = f"{farm_needs_data.get('EVI_curr', 'N/A'):.3f}" if pd.notna(farm_needs_data.get('EVI_curr')) else "N/A"
            st.metric("EVI (جاری)", display_val)
        with idx_cols[3]:
            display_val = f"{farm_needs_data.get('SAVI_curr', 'N/A'):.3f}" if pd.notna(farm_needs_data.get('SAVI_curr')) else "N/A"
            st.metric("SAVI (جاری)", display_val)


        idx_prev_cols = st.columns(4)
        with idx_prev_cols[0]:
             display_val_prev = f"{farm_needs_data['NDVI_prev']:.3f}" if pd.notna(farm_needs_data.get('NDVI_prev')) else "N/A"
             st.metric("NDVI (قبلی)", display_val_prev)
        with idx_prev_cols[1]:
             display_val_prev = f"{farm_needs_data['NDMI_prev']:.3f}" if pd.notna(farm_needs_data.get('NDMI_prev')) else "N/A"
             st.metric("NDMI (قبلی)", display_val_prev)
        with idx_prev_cols[2]:
             display_val_prev = f"{farm_needs_data.get('EVI_prev', 'N/A'):.3f}" if pd.notna(farm_needs_data.get('EVI_prev')) else "N/A"
             st.metric("EVI (قبلی)", display_val_prev)
        with idx_prev_cols[3]:
             display_val_prev = f"{farm_needs_data.get('SAVI_prev', 'N/A'):.3f}" if pd.notna(farm_needs_data.get('SAVI_prev')) else "N/A"
             st.metric("SAVI (قبلی)", display_val_prev)


        st.markdown("---")
        st.markdown("#### توصیه‌های اولیه (بر اساس آستانه‌ها)")
        st.markdown("این توصیه‌ها بر اساس مقادیر شاخص و آستانه‌های داخلی سیستم، به‌صورت خودکار تولید می‌شوند:")
        recommendations = []

        NDMI_IRRIGATION_THRESHOLD = 0.25
        NDVI_DROP_PERCENT_THRESHOLD = 5.0

        # Get status using the determine_status logic for consistency
        # We need the raw numerical values for determine_status
        farm_row_for_status = {
            f'{idx} (هفته جاری)': farm_needs_data.get(f'{idx}_curr') for idx in ['NDVI', 'NDMI', 'EVI', 'SAVI']
        }
        farm_row_for_status.update({
             f'{idx} (هفته قبل)': farm_needs_data.get(f'{idx}_prev') for idx in ['NDVI', 'NDMI', 'EVI', 'SAVI']
        })

        # Calculate change for status determination based on raw numerical values
        current_ndvi_raw = farm_needs_data.get('NDVI_curr')
        previous_ndvi_raw = farm_needs_data.get('NDVI_prev')
        ndvi_change_raw = current_ndvi_raw - previous_ndvi_raw if pd.notna(current_ndvi_raw) and pd.notna(previous_ndvi_raw) else np.nan
        farm_row_for_status['تغییر'] = ndvi_change_raw # Add change for NDVI status check


        # Use determine_status for specific recommendations
        ndmi_status = determine_status(farm_row_for_status, 'NDMI')
        ndvi_status = determine_status(farm_row_for_status, 'NDVI')


        if "نیاز به آبیاری فوری" in ndmi_status or "تنش رطوبتی شدید" in ndmi_status:
             recommendations.append(f"💧 نیاز به آبیاری فوری ({ndmi_status})")
        elif "کاهش رطوبت قابل توجه" in ndmi_status:
             recommendations.append(f"❗ کاهش رطوبت مشاهده شده است. بررسی نیاز به آبیاری ({ndmi_status})")
        elif "احتمال تنش رطوبتی (بدون داده قبل)" in ndmi_status:
             recommendations.append(f"⚠️ احتمال تنش رطوبتی بر اساس شاخص جاری. (بدون داده هفته قبل برای مقایسه)")


        if "تنش / کاهش" in ndvi_status:
             recommendations.append(f"⚠️ کاهش در پوشش گیاهی/سلامت مشاهده شده است. بررسی نیاز به کوددهی یا سایر عوامل تنش‌زا ({ndvi_status})")
        # Check if NDVI is low when previous data is missing
        elif pd.notna(farm_needs_data.get('NDVI_curr')) and pd.isna(farm_needs_data.get('NDVI_prev')):
             LOW_NDVI_THRESHOLD = 0.3 # Example low threshold for NDVI
             if farm_needs_data['NDVI_curr'] <= LOW_NDVI_THRESHOLD:
                 recommendations.append(f"⚠️ پوشش گیاهی پایین بر اساس شاخص جاری ({farm_needs_data['NDVI_curr']:.3f}). (بدون داده هفته قبل برای مقایسه). بررسی عمومی مزرعه.")

        # Handle cases where data is missing for NDMI or NDVI specifically
        if pd.isna(farm_needs_data.get('NDMI_curr')) and pd.notna(farm_needs_data.get('NDMI_prev')):
             recommendations.append("ℹ️ داده رطوبت (NDMI) هفته جاری برای ارزیابی وضعیت فعلی در دسترس نیست.")
        elif pd.notna(farm_needs_data.get('NDMI_curr')) and pd.isna(farm_needs_data.get('NDMI_prev')) and "احتمال تنش رطوبتی (بدون داده قبل)" not in recommendations:
             # If current NDMI exists but previous doesn't, and no other NDMI warning was added
              recommendations.append("ℹ️ داده رطوبت (NDMI) هفته قبل برای ارزیابی تغییرات در دسترس نیست.")


        if pd.isna(farm_needs_data.get('NDVI_curr')) and pd.notna(farm_needs_data.get('NDVI_prev')):
             recommendations.append("ℹ️ داده پوشش گیاهی (NDVI) هفته جاری برای ارزیابی وضعیت فعلی در دسترس نیست.")
        elif pd.notna(farm_needs_data.get('NDVI_curr')) and pd.isna(farm_needs_data.get('NDVI_prev')) and "پوشش گیاهی پایین (بدون داده قبل)" not in recommendations:
             # If current NDVI exists but previous doesn't, and no other NDVI warning was added
              recommendations.append("ℹ️ داده پوشش گیاهی (NDVI) هفته قبل برای ارزیابی تغییرات در دسترس نیست.")


        if not recommendations:
             recommendations.append("✅ بر اساس شاخص‌های فعلی و تغییرات نسبت به هفته قبل، وضعیت مزرعه مطلوب به نظر می‌رسد یا داده کافی برای تشخیص مشکل واضح وجود ندارد.")


        for rec in recommendations:
            if "نیاز به آبیاری فوری" in rec or "تنش رطوبتی شدید" in rec or "کاهش رطوبت قابل توجه" in rec or "احتمال تنش رطوبتی" in rec: st.error(rec)
            elif "نیاز به بررسی کوددهی" in rec or "پوشش گیاهی پایین" in rec: st.warning(rec)
            else: st.success(rec)

        st.markdown("---")
        st.markdown("#### تحلیل هوش مصنوعی")
        if gemini_model:
             with st.spinner("در حال تولید تحلیل هوش مصنوعی..."):
                 ai_explanation = get_ai_needs_analysis(gemini_model, selected_farm_name, farm_needs_data, recommendations)
             st.markdown(ai_explanation)
        else:
             st.info("⚠️ سرویس تحلیل هوش مصنوعی پیکربندی نشده یا در دسترس نیست.")

    st.markdown("---")