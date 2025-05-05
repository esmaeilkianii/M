# -*- coding: utf-8 -*-
# --- START OF FILE app.py ---

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
# import base64 # No longer explicitly needed
import google.generativeai as genai
from shapely.geometry import Polygon
import pyproj
import numpy as np # Import numpy for np.nan

# Define the source CRS (likely UTM Zone 39N for Khuzestan)
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
GEMINI_API_KEY_HARDCODED = "AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ" # --- YOUR HARDCODED KEY ---
# --- END OF HARDCODED API KEY ---


# --- Custom CSS ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700;900&display=swap');
        @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');

        html, body, .main, .stApp {
            font-family: 'Vazirmatn', sans-serif !important;
            background: linear-gradient(180deg, #e0f7fa 0%, #f8fafc 100%);
            color: #333;
        }

        @media (prefers-color-scheme: dark) {
            html, body, .main, .stApp {
                background: linear-gradient(180deg, #2b2b2b 0%, #3f3f3f 100%);
                color: #f8f8f8;
            }
            .stTabs [data-baseweb="tab-list"] button [data-baseweb="tab"] { color: #bbb !important; }
             .stTabs [data-baseweb="tab-list"] button:hover { color: #f8f8f8 !important; }
            .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] { color: #43cea2 !important; border-bottom-color: #43cea2 !important; }
             .modern-card { background: linear-gradient(135deg, #1a435a 0%, #2a2a2a 100%); color: #f8f8f8; box-shadow: 0 4px 16px rgba(0,0,0,0.3); }
             .status-positive { background-color: #218838; }
             .status-negative { background-color: #c82333; }
             .status-neutral { background-color: #5a6268; color: #fff; }
             .status-nodata { background-color: #d39e00; color: #f8f8f8; }
             table { box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
              th { background-color: #0e3a5d; color: #f8f8f8; }
             tr:nth-child(even) { background-color: #3a3a3a; }
             tr:nth-child(odd) { background-color: #2b2b2b; }
             td { border-bottom-color: #555; }
             .stAlert a { color: #43cea2; }
             .js-plotly-plot { box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
             .stSidebar { background: linear-gradient(180deg, #1a435a 0%, #2b2b2b 100%); color: #f8f8f8; }
              .stSidebar label { color: #f8f8f8; }
              .stSidebar .stTextInput > div > div > input,
              .stSidebar .stSelectbox > div > div > div > input[type="text"],
              .stSidebar .stNumberInput > div > div > input { background-color: #3a3a3a; color: #f8f8f8; border-color: #555; }
              .stSidebar .stTextInput > div > div > input:focus,
              .stSidebar .stSelectbox > div > div > div > input[type="text"]:focus,
              .stSidebar .stNumberInput > div > div > input:focus { border-color: #43cea2; box-shadow: 0 0 5px rgba(67, 206, 162, 0.5); }
              .stSidebar .stRadio > label > div:first-child { color: #f8f8f8; }
              .stExpander { border-color: #555; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
               .stExpander div[data-baseweb="accordion-header"] { background-color: #3a3a3a; border-bottom-color: #555; color: #f8f8f8; }
               hr { border-top: 2px dashed #555; }
        }

        h1, h2, h3, h4, h5, h6 { color: #185a9d; font-weight: 700; }
         .stMarkdown h1 { color: #185a9d !important; }

        .modern-card { background: linear-gradient(135deg, #43cea2 0%, #185a9d 100%); color: white; border-radius: 18px; padding: 20px; margin: 15px 0; box-shadow: 0 6px 20px rgba(30,60,114,0.1); text-align: center; transition: transform 0.3s ease-in-out, box-shadow 0.3s ease-in-out; overflow: hidden; }
        .modern-card:hover { transform: translateY(-5px) scale(1.02); box-shadow: 0 10px 30px rgba(30,60,114,0.15); }
        .modern-card div:first-child { font-size: 1em; opacity: 0.9; margin-bottom: 8px; }
         .modern-card div:last-child { font-size: 2em; font-weight: 900; }

        .sidebar-logo { display: flex; align-items: center; justify-content: center; margin-bottom: 2rem; padding-top: 1rem; }
        .sidebar-logo img { width: 100px; height: 100px; border-radius: 20px; box-shadow: 0 4px 12px rgba(30,60,114,0.15); }

        .main-logo { width: 55px; height: 55px; border-radius: 15px; margin-left: 15px; vertical-align: middle; box-shadow: 0 2px 8px rgba(30,60,114,0.1); }

        .stTabs [data-baseweb="tab-list"] { gap: 20px; }
        .stTabs [data-baseweb="tab-list"] button { background-color: #f0f2f6; padding: 10px 15px; border-radius: 8px 8px 0 0; border-bottom: 2px solid transparent; transition: all 0.3s ease; font-weight: 700; color: #555; }
         .stTabs [data-baseweb="tab-list"] button:hover { background-color: #e2e6eb; color: #185a9d; border-bottom-color: #185a9d; }
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] { background-color: #ffffff; border-bottom-color: #43cea2; color: #185a9d; box-shadow: 0 -2px 8px rgba(30,60,114,0.05); }
         .stTabs [data-baseweb="tab-panel"] { padding: 20px 5px; }

        .status-badge { display: inline-block; padding: 0.3em 0.6em; font-size: 0.8em; font-weight: bold; line-height: 1.2; text-align: center; white-space: nowrap; vertical-align: middle; border-radius: 0.35rem; color: #fff; margin: 2px; }
        .status-positive { background-color: #28a745; }
        .status-negative { background-color: #dc3545; }
        .status-neutral { background-color: #6c757d; color: #fff; }
        .status-nodata { background-color: #ffc107; color: #212529; }

        table { border-collapse: collapse; width: 100%; margin: 20px 0; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-radius: 8px; overflow: hidden; }
        th, td { text-align: center; padding: 10px; border-bottom: 1px solid #ddd; vertical-align: middle !important; }
        th { background-color: #185a9d; color: white; font-weight: 700; }
        tr:nth-child(even) { background-color: #f2f2f2; }

        .stAlert { border-radius: 8px; margin: 15px 0; padding: 15px; display: flex; align-items: flex-start; }
        .stAlert > div:first-child { font-size: 1.5em; margin-right: 15px; flex-shrink: 0; }
         .stAlert > div:last-child { font-size: 1em; line-height: 1.5; flex-grow: 1; }
          .stAlert a { color: #185a9d; }

         .js-plotly-plot { border-radius: 8px; overflow: hidden; margin: 20px 0; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }

         .stSidebar { background: linear-gradient(180deg, #cce7ff 0%, #e0f7fa 100%); color: #333; padding: 20px; }

          .stSidebar h2 { color: #185a9d; }
          .stSidebar .stRadio > label > div:first-child { padding-right: 10px; }
           .stSidebar .stSelectbox > label { font-weight: 700; }
           .stSidebar .stSlider > label { font-weight: 700; }

         .stTextInput > div > div > input,
         .stSelectbox > div > div > div > input[type="text"],
         .stNumberInput > div > div > input { border-radius: 8px; border: 1px solid #ccc; padding: 8px 12px; transition: border-color 0.3s; }
          .stTextInput > div > div > input:focus,
          .stSelectbox > div > div > div > input[type="text"]:focus,
          .stNumberInput > div > div > input:focus { border-color: #43cea2; outline: none; box-shadow: 0 0 5px rgba(67, 206, 162, 0.5); }

         .stButton > button { background-color: #185a9d; color: white; border-radius: 8px; padding: 10px 20px; font-size: 1em; transition: background-color 0.3s, transform 0.1s; border: none; cursor: pointer; }
          .stButton > button:hover { background-color: #0f3c66; transform: translateY(-1px); }
           .stButton > button:active { transform: translateY(0); background-color: #0a2840; }

          .stDownloadButton > button { background-color: #43cea2; }
           .stDownloadButton > button:hover { background-color: #31a380; }
            .stDownloadButton > button:active { background-color: #247a60; }

         .stExpander { border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 2px 8px rgba(0,0,0,0.03); margin: 15px 0; }
           .stExpander div[data-baseweb="accordion-header"] { background-color: #f8f8f8; border-bottom: 1px solid #ddd; border-top-left-radius: 8px; border-top-right-radius: 8px; padding: 10px 15px; font-weight: 700; color: #333; }
            .stExpander div[data-baseweb="accordion-panel"] { padding: 15px; }

           hr { border-top: 2px dashed #ccc; margin: 30px 0; }

            [data-testid="stMetricValue"] { text-align: center; width: 100%; display: block; }
             [data-testid="stMetricLabel"] { text-align: center; width: 100%; display: block; }
    </style>
""", unsafe_allow_html=True)


def status_badge(status: str) -> str:
    """Returns HTML for a status badge with color."""
    if status is None or pd.isna(status):
        return f'<span class="status-badge status-nodata">N/A</span>'

    status_lower = str(status).lower()
    if "بهبود" in status_lower or "رشد مثبت" in status_lower or "افزایش رطوبت" in status_lower:
        badge_class = "status-positive"
    elif any(term in status_lower for term in ["تنش", "کاهش", "بدتر", "نیاز"]):
        badge_class = "status-negative"
    elif any(term in status_lower for term in ["ثابت", "رطوبت ثابت", "پوشش گیاهی پایین", "قابل توجه", "نامشخص"]):
        badge_class = "status-neutral"
    elif "بدون داده" in status_lower:
        badge_class = "status-nodata"
    else:
        badge_class = "status-neutral"

    return f'<span class="status-badge {badge_class}">{status}</span>'

def modern_metric_card(title: str, value: str, icon: str, color: str) -> str:
    """Returns a modern styled HTML card for displaying a metric."""
    return f'''
    <div class="modern-card" style="background: linear-gradient(135deg, {color} 0%, #185a9d 100%);">
        <div>{title} <i class="fa {icon}"></i></div>
        <div>{value}</div>
    </div>
    '''

# Sidebar Logo
st.sidebar.markdown(
    """
    <div class='sidebar-logo'>
        <img src='https://raw.githubusercontent.com/esmaeilkiani13877/MonitoringSugarcane-13/main/logo%20(1).png' alt='لوگو سامانه' />
    </div>
    """,
    unsafe_allow_html=True
)

# Main Header with Logo
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
        credentials = None
        auth_info = None
        if "gee_auth_json" in st.secrets:
             try:
                auth_info = json.loads(st.secrets["gee_auth_json"])
                credentials = ee.ServiceAccountCredentials(auth_info['client_email'], None, private_key_id=auth_info['private_key_id'], private_key=auth_info['private_key'], token_uri=auth_info['token_uri'])
                print("GEE Initialized Successfully using Streamlit Secrets JSON.")
             except Exception as e:
                 st.warning(f"⚠️ خطا در استفاده از Secrets برای GEE: {e}. تلاش برای استفاده از فایل محلی...")
                 credentials = None

        if credentials is None and os.path.exists(SERVICE_ACCOUNT_FILE):
             try:
                credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
                print("GEE Initialized Successfully using Service Account File.")
             except Exception as e:
                 st.error(f"❌ خطا در استفاده از فایل Service Account محلی '{SERVICE_ACCOUNT_FILE}': {e}")
                 return None
        elif credentials is None:
             st.error("❌ هیچ اعتبارنامه معتبری برای Google Earth Engine یافت نشد (نه در Secrets و نه به صورت فایل محلی).")
             st.info("لطفاً Streamlit Secret 'gee_auth_json' یا فایل Service Account را تنظیم کنید.")
             return None

        project_id = None
        if hasattr(credentials, 'project_id'):
            project_id = credentials.project_id
        elif isinstance(auth_info, dict) and 'project_id' in auth_info:
             project_id = auth_info['project_id']

        ee.Initialize(credentials=credentials, project=project_id, opt_url='https://earthengine-highvolume.googleapis.com')
        print(f"GEE Initialized Successfully. Project: {project_id or 'Default'}")
        return True

    except ee.EEException as e:
        st.error(f"❌ خطا در اتصال به Google Earth Engine: {e}")
        return None
    except Exception as e:
        st.error(f"❌ خطای غیرمنتظره هنگام اتصال به GEE: {e}")
        st.error(traceback.format_exc())
        return None


@st.cache_data(show_spinner="در حال بارگذاری و پردازش داده‌های مزارع...", persist="disk")
def load_farm_data_from_csv(_transformer, csv_path=FARM_DATA_CSV_PATH):
    """Loads farm data from the specified CSV file and processes coordinates."""
    if _transformer is None:
         st.error("❌ تبدیل کننده مختصات پیکربندی نشده است.")
         return pd.DataFrame()

    try:
        df = None
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, encoding='utf-8')
            print(f"Loaded Farm data from local CSV: {csv_path}")
        else:
            github_raw_url = f'https://raw.githubusercontent.com/esmaeilkiani13877/MonitoringSugarcane-13/main/{os.path.basename(csv_path)}'
            try:
                response = requests.get(github_raw_url)
                response.raise_for_status()
                df = pd.read_csv(BytesIO(response.content), encoding='utf-8')
                print(f"Loaded Farm data from URL: {github_raw_url}")
            except requests.exceptions.RequestException as e:
                 st.error(f"❌ فایل '{os.path.basename(csv_path)}' در مسیر محلی یا از URL گیت‌هاب '{github_raw_url}' یافت نشد: {e}")
                 return pd.DataFrame()
            except Exception as e:
                 st.error(f"❌ خطای غیرمنتظره در دریافت فایل CSV مزارع از URL: {e}")
                 return pd.DataFrame()

        if df is None or df.empty:
             st.error("❌ فایل داده مزارع خالی است یا خوانده نشد.")
             return pd.DataFrame()

        df.columns = df.columns.str.strip().str.replace('\ufeff', '')

        required_cols = ['مزرعه', 'روز', 'lat1', 'lon1', 'lat2', 'lon2', 'lat3', 'lon3', 'lat4', 'lon4']
        if not all(col in df.columns for col in required_cols):
            missing_cols = [col for col in required_cols if col not in df.columns]
            st.error(f"❌ فایل CSV مزارع فاقد ستون‌های ضروری است: {', '.join(missing_cols)}")
            return pd.DataFrame()

        df['wgs84_centroid_lon'] = np.nan
        df['wgs84_centroid_lat'] = np.nan
        df['ee_geometry'] = None
        df['wgs84_polygon_coords'] = None

        processed_records = []
        skipped_farms = []

        for index, row in df.iterrows():
            farm_name = row.get('مزرعه', f'مزرعه ناشناس {index+1}')
            try:
                points_utm = []
                valid_points = True
                for i in range(1, 5):
                    lat_col, lon_col = f'lat{i}', f'lon{i}'
                    if pd.notna(row.get(lat_col)) and pd.notna(row.get(lon_col)):
                        try:
                            points_utm.append((float(row[lon_col]), float(row[lat_col])))
                        except (ValueError, TypeError): valid_points = False; break
                    else: valid_points = False; break

                if not valid_points or len(points_utm) < 4:
                    skipped_farms.append(f"'{farm_name}': مختصات نامعتبر/ناقص.")
                    continue

                points_wgs84 = []
                try:
                    for easting, northing in points_utm:
                         points_wgs84.append(_transformer.transform(easting, northing))
                except pyproj.exceptions.ProjError as te:
                     skipped_farms.append(f"'{farm_name}': خطای تبدیل مختصات {te}")
                     continue
                except Exception as e:
                     skipped_farms.append(f"'{farm_name}': خطای ناشناخته تبدیل مختصات: {e}")
                     continue

                if not points_wgs84: continue

                polygon_coords_wgs84 = points_wgs84 + [points_wgs84[0]] if points_wgs84[-1] != points_wgs84[0] else points_wgs84
                if len(polygon_coords_wgs84) < 4:
                    skipped_farms.append(f"'{farm_name}': نقاط WGS84 ناکافی.")
                    continue

                try:
                    shapely_polygon = Polygon(polygon_coords_wgs84)
                    if not shapely_polygon.is_valid:
                        fixed_polygon = shapely_polygon.buffer(0)
                        if not fixed_polygon.is_valid or fixed_polygon.is_empty or not isinstance(fixed_polygon, Polygon):
                             skipped_farms.append(f"'{farm_name}': پلی‌گون WGS84 نامعتبر و غیرقابل اصلاح.")
                             continue
                        shapely_polygon = fixed_polygon

                    gee_coords_list = [list(coord) for coord in shapely_polygon.exterior.coords]
                    if not gee_coords_list: continue

                    ee_polygon = ee.Geometry.Polygon(gee_coords_list, proj=TARGET_CRS, evenOdd=False)
                    centroid_ee = ee_polygon.centroid(maxError=1)
                    centroid_coords_wgs84 = centroid_ee.getInfo()['coordinates']

                    processed_row = row.to_dict()
                    processed_row['wgs84_centroid_lon'] = centroid_coords_wgs84[0]
                    processed_row['wgs84_centroid_lat'] = centroid_coords_wgs84[1]
                    processed_row['ee_geometry'] = ee_polygon
                    processed_row['wgs84_polygon_coords'] = gee_coords_list
                    processed_records.append(processed_row)

                except ee.EEException as ee_geom_e: skipped_farms.append(f"'{farm_name}': خطای هندسه GEE: {ee_geom_e}")
                except Exception as e: skipped_farms.append(f"'{farm_name}': خطای پردازش هندسه: {e}")

            except Exception as e: skipped_farms.append(f"'{farm_name}': خطای عمومی ردیف: {e}")

        processed_df = pd.DataFrame(processed_records)

        if skipped_farms:
            st.warning("⚠️ برخی مزارع نادیده گرفته شدند (تا ۱۰ خطا):")
            unique_skipped = list(set(skipped_farms))
            for msg in unique_skipped[:10]: st.warning(f"- {msg}")
            if len(unique_skipped) > 10: st.warning(f"... و {len(unique_skipped) - 10} مورد دیگر.")

        if processed_df.empty:
            st.error("❌ هیچ داده معتبری پس از پردازش CSV مزارع یافت نشد.")
            return pd.DataFrame()

        for col in ['روز', 'گروه', 'واریته', 'سن']:
            if col in processed_df.columns:
                processed_df[col] = processed_df[col].fillna('نامشخص').astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
                processed_df[col] = processed_df[col].replace(['nan', '', 'NaN'], 'نامشخص')
            else: processed_df[col] = 'نامشخص'

        if 'مساحت' in processed_df.columns:
             processed_df['مساحت'] = pd.to_numeric(processed_df['مساحت'], errors='coerce').fillna(0.0)
        else: processed_df['مساحت'] = 0.0

        return processed_df
    except FileNotFoundError:
        st.error(f"❌ فایل '{os.path.basename(csv_path)}' یافت نشد.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری/پردازش CSV مزارع: {e}")
        st.error(traceback.format_exc())
        return pd.DataFrame()


@st.cache_data(show_spinner="در حال بارگذاری داده‌های محاسبات...", persist="disk")
def load_analysis_data(csv_path=ANALYSIS_CSV_PATH):
    """Loads and preprocesses data from the analysis CSV file."""
    try:
        lines = None
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f: lines = f.readlines()
            print(f"Loaded Analysis CSV from: {csv_path}")
        else:
             github_raw_url = f'https://raw.githubusercontent.com/esmaeilkiani13877/MonitoringSugarcane-13/main/{os.path.basename(csv_path)}'
             try:
                 response = requests.get(github_raw_url); response.raise_for_status()
                 lines = response.text.splitlines()
                 print(f"Loaded Analysis CSV from URL: {github_raw_url}")
             except Exception as e:
                 st.error(f"❌ فایل محاسبات '{os.path.basename(csv_path)}' یافت نشد یا دریافت نشد: {e}")
                 return None, None

        if lines is None: return None, None

        header_patterns = ['اداره,سن,', 'تولید,سن,']
        headers_indices = [i for i, line in enumerate(lines)
                           if any(pat in line.strip().lstrip('\ufeff').replace(" ","") for pat in header_patterns)]

        if not headers_indices:
            st.error(f"❌ هدرهای مورد انتظار در '{os.path.basename(csv_path)}' یافت نشد.")
            return None, None

        s1_start, s1_end = headers_indices[0], len(lines)
        s2_start, s2_end = -1, len(lines)
        if len(headers_indices) > 1: s1_end, s2_start = headers_indices[1], headers_indices[1]
        for i in range(s1_start + 1, s1_end):
            if "Grand Total" in lines[i] or len(lines[i].strip()) < 5: s1_end = i; break
        if s2_start != -1:
            for i in range(s2_start + 1, s2_end):
                 if "Grand Total" in lines[i] or len(lines[i].strip()) < 5: s2_end = i; break

        df_area, df_prod = pd.DataFrame(), pd.DataFrame()
        try:
            if lines[s1_start:s1_end]: df_area = pd.read_csv(BytesIO("\n".join(lines[s1_start:s1_end]).encode('utf-8')))
        except Exception as e: st.warning(f"⚠️ خطا خواندن بخش مساحت: {e}")
        if s2_start != -1:
             try:
                  if lines[s2_start:s2_end]: df_prod = pd.read_csv(BytesIO("\n".join(lines[s2_start:s2_end]).encode('utf-8')))
             except Exception as e: st.warning(f"⚠️ خطا خواندن بخش تولید: {e}")

        def preprocess_df(df, section_name):
            if df is None or df.empty: return None
            df.columns = df.columns.str.strip().str.replace('\ufeff', '')
            if df.columns.tolist() and df.columns[0] not in ['اداره', 'تولید'] and 'اداره' not in df.columns:
                 df.rename(columns={df.columns[0]: 'اداره'}, inplace=True)
            if not all(col in df.columns for col in ['اداره', 'سن']):
                 st.warning(f"⚠️ ستون ضروری 'اداره' یا 'سن' در بخش '{section_name}' نیست."); return None
            df['اداره'] = df['اداره'].ffill()
            df = df[~df['سن'].astype(str).str.contains('total', case=False, na=False)].copy()
            df['اداره_num'] = pd.to_numeric(df['اداره'], errors='coerce')
            df = df.dropna(subset=['اداره_num']).copy()
            df['اداره'] = df['اداره_num'].astype('Int64')
            df = df.drop(columns=['اداره_num'])
            df = df[~df['اداره'].isin([99, 999, 0])] # Filter totals
            if df.empty: return None
            value_cols = [col for col in df.columns if col not in ['اداره', 'سن', 'درصد', 'Grand Total']]
            for col in value_cols: df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.dropna(axis=1, how='all').drop(columns=['Grand Total', 'درصد'], errors='ignore')
            if 'اداره' in df.columns and 'سن' in df.columns:
                try:
                    df['سن'] = df['سن'].astype(str).str.strip()
                    df = df.set_index(['اداره', 'سن']).copy()
                except ValueError as e: st.warning(f"⚠️ خطای ایندکس در '{section_name}': {e}")
            return df

        df_area_processed = preprocess_df(df_area, "مساحت")
        df_prod_processed = preprocess_df(df_prod, "تولید")
        if df_area_processed is None and df_prod_processed is None:
             st.warning("⚠️ هیچ داده معتبری از فایل محاسبات بارگذاری نشد.")
        return df_area_processed, df_prod_processed

    except FileNotFoundError: st.error(f"❌ فایل '{os.path.basename(csv_path)}' یافت نشد."); return None, None
    except Exception as e: st.error(f"❌ خطا در بارگذاری/پردازش CSV محاسبات: {e}"); st.error(traceback.format_exc()); return None, None


# --- Initialization ---
gee_initialized = initialize_gee()
farm_data_df = pd.DataFrame()
if transformer is not None and gee_initialized:
    farm_data_df = load_farm_data_from_csv(transformer, FARM_DATA_CSV_PATH)
elif transformer is None:
     st.error("❌ بارگذاری داده مزارع ممکن نیست (خطای تبدیل کننده مختصات).")
analysis_area_df, analysis_prod_df = load_analysis_data(ANALYSIS_CSV_PATH)


@st.cache_resource(show_spinner="در حال پیکربندی سرویس هوش مصنوعی...")
def configure_gemini(api_key):
    """Configures the Gemini API client."""
    if not api_key: st.error("❌ کلید API جمینای در دسترس نیست."); return None
    try:
        genai.configure(api_key=api_key)
        safety_settings = [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
        model = genai.GenerativeModel('gemini-1.5-flash-latest', safety_settings=safety_settings)
        print("Using Gemini Model: gemini-1.5-flash-latest")
        return model
    except Exception as e1:
        print(f"Failed loading latest flash model: {e1}. Falling back.")
        try:
            model = genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety_settings)
            print("Using Gemini Model: gemini-1.5-flash")
            return model
        except Exception as e2:
            st.error(f"❌ خطا در تنظیم مدل Gemini: {e2}")
            return None

gemini_model = None
if gee_initialized:
    gemini_model = configure_gemini(GEMINI_API_KEY_HARDCODED)
    if gemini_model is None: st.warning("⚠️ سرویس تحلیل هوش مصنوعی در دسترس نیست.")

# ==============================================================================
# Sidebar Filters
# ==============================================================================
st.sidebar.header("⚙️ تنظیمات نمایش")

selected_day = None
if farm_data_df is not None and not farm_data_df.empty and 'روز' in farm_data_df.columns:
    valid_days = sorted([d for d in farm_data_df['روز'].dropna().unique() if d != 'نامشخص'])
    if valid_days:
        selected_day = st.sidebar.selectbox("📅 روز هفته:", options=valid_days, index=0)
    else: st.sidebar.warning("⚠️ 'روز هفته' معتبری یافت نشد.")
elif farm_data_df is None or farm_data_df.empty: st.sidebar.info("ℹ️ داده مزارع بارگذاری نشده.")
else: st.sidebar.warning("⚠️ ستون 'روز' در داده مزارع نیست.")

filtered_farms_df = pd.DataFrame()
if selected_day and farm_data_df is not None and not farm_data_df.empty:
    filtered_farms_df = farm_data_df[farm_data_df['روز'] == selected_day].reset_index(drop=True)

selected_farm_name = "همه مزارع"
if not filtered_farms_df.empty:
    if 'مزرعه' in filtered_farms_df.columns:
        available_farms = sorted(filtered_farms_df['مزرعه'].dropna().unique())
        farm_options = ["همه مزارع"] + available_farms
        selected_farm_name = st.sidebar.selectbox("🌾 مزرعه:", options=farm_options, index=0)
    else: st.sidebar.warning("⚠️ ستون 'مزرعه' یافت نشد.")
elif selected_day: st.sidebar.info(f"ℹ️ مزرعه‌ای برای روز '{selected_day}' نیست.")

index_options = {
    "NDVI": "پوشش گیاهی", "EVI": "پوشش گیاهی بهبودیافته", "NDMI": "رطوبت",
    "LAI": "سطح برگ", "MSI": "تنش رطوبتی", "CVI": "کلروفیل", "SAVI": "پوشش (خاک)"}
selected_index = st.sidebar.selectbox(
    "📈 شاخص:", options=list(index_options.keys()),
    format_func=lambda x: f"{x} ({index_options[x]})", index=0)

today = datetime.date.today()
start_date_current_str, end_date_current_str = None, None
start_date_previous_str, end_date_previous_str = None, None
if selected_day:
    try:
        persian_to_weekday = {"شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1, "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4}
        target_weekday = persian_to_weekday[selected_day.strip()]
        days_ago = (today.weekday() - target_weekday + 7) % 7
        end_date_current = today - datetime.timedelta(days=days_ago)
        start_date_current = end_date_current - datetime.timedelta(days=6)
        end_date_previous = start_date_current - datetime.timedelta(days=1)
        start_date_previous = end_date_previous - datetime.timedelta(days=6)
        start_date_current_str = start_date_current.strftime('%Y-%m-%d')
        end_date_current_str = end_date_current.strftime('%Y-%m-%d')
        start_date_previous_str = start_date_previous.strftime('%Y-%m-%d')
        end_date_previous_str = end_date_previous.strftime('%Y-%m-%d')
        st.sidebar.caption(f"جاری: {start_date_current_str} تا {end_date_current_str}")
        st.sidebar.caption(f"قبلی: {start_date_previous_str} تا {end_date_previous_str}")
    except Exception as e: st.sidebar.error(f"خطا محاسبه بازه: {e}")

st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با ❤️")

# ==============================================================================
# GEE Processing Functions
# ==============================================================================

def maskS2clouds(image):
    """Masks clouds and shadows in Sentinel-2 SR images."""
    qa = image.select('QA60'); cloudBitMask = 1 << 10; cirrusBitMask = 1 << 11
    mask_qa = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
    scl = image.select('SCL'); masked_classes_scl = [1, 3, 8, 9, 10, 11]
    mask_scl = scl.remap(masked_classes_scl, [0]*len(masked_classes_scl), 1).eq(1)
    final_mask = mask_qa.And(mask_scl)
    return image.addBands(image.select('B.*').multiply(0.0001), None, True).updateMask(final_mask)

def add_indices(image):
    """Calculates various vegetation indices using ee.Image.expression."""
    epsilon = 1e-9
    common_params = {
        'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2'),
        'GREEN': image.select('B3'), 'SWIR1': image.select('B11'), 'epsilon': epsilon}
    ndvi = image.expression('(NIR - RED) / (NIR + RED + epsilon)', common_params).rename('NDVI')
    evi = image.expression('2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1 + epsilon)', common_params).rename('EVI')
    ndmi = image.expression('(NIR - SWIR1) / (NIR + SWIR1 + epsilon)', common_params).rename('NDMI')
    savi = image.expression('((NIR - RED) / (NIR + RED + 0.5 + epsilon)) * (1.5)', common_params).rename('SAVI')
    msi = image.expression('SWIR1 / (NIR + epsilon)', common_params).rename('MSI')
    lai = evi.multiply(3.618).subtract(0.118).rename('LAI'); lai = lai.updateMask(lai.gte(0))
    cvi = image.expression('(NIR / (GREEN + epsilon)) * (RED / (GREEN + epsilon))', common_params).rename('CVI')
    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi, savi])


@st.cache_data(show_spinner=False, persist="disk")#, ttl=3600)
def get_processed_image(_geometry, start_date, end_date, index_name):
    """Gets cloud-masked, index-calculated Sentinel-2 median composite."""
    if not gee_initialized: return None, "GEE مقداردهی اولیه نشده."
    if _geometry is None: return None, "هندسه نامعتبر."

    fallback_days, error_msg, image = 15, None, None # Shortened fallback

    def filter_and_process(s_date, e_date):
        try:
            s2_sr_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterBounds(_geometry).filterDate(s_date, e_date).map(maskS2clouds)
            count = s2_sr_col.size().getInfo()
            if count == 0: return None, f"هیچ تصویر S2 در {s_date}-{e_date} یافت نشد."

            median_image = s2_sr_col.map(add_indices).median()
            if index_name not in median_image.bandNames().getInfo():
                return None, f"شاخص '{index_name}' محاسبه نشد (باندهای موجود: {', '.join(median_image.bandNames().getInfo())})."

            output_image = median_image.select(index_name)
            data_check = output_image.reduceRegion(ee.Reducer.count(), _geometry, 30, bestEffort=True).get(index_name).getInfo()
            if data_check is None or data_check == 0:
                return None, f"تصویر '{index_name}' داده معتبری روی هندسه ندارد."
            return output_image, None
        except ee.EEException as e: return None, f"خطای GEE ({s_date}-{e_date}): {e}"
        except Exception as e: return None, f"خطای Python ({s_date}-{e_date}): {e}"

    image, error_msg = filter_and_process(start_date, end_date)
    if image is None and ("هیچ تصویر" in error_msg or "not found" in error_msg.lower()):
        try:
            fb_end = (datetime.datetime.strptime(end_date, '%Y-%m-%d') + datetime.timedelta(days=fallback_days)).strftime('%Y-%m-%d')
            fb_start = start_date
            st.info(f"⏳ تصویر اولیه یافت نشد، تلاش با بازه گسترده‌تر تا {fb_end}...")
            image, fb_error_msg = filter_and_process(fb_start, fb_end)
            if image: error_msg = None; st.info(f"ℹ️ از داده تا {fb_end} استفاده شد.")
            else: error_msg = f"اولیه ناموفق ({error_msg}). بازه گسترده نیز ناموفق: {fb_error_msg}"
        except Exception as fb_e: error_msg = f"خطا در بازه جایگزین: {fb_e}. خطای اولیه: {error_msg}"

    if image is None and not error_msg: error_msg = f"پردازش {start_date}-{end_date} ناموفق (نامشخص)."
    return image, error_msg


@st.cache_data(show_spinner="در حال دریافت سری زمانی...", persist="disk", ttl=7200)
def get_index_time_series(_point_geom, index_name, start_date, end_date):
    """Gets time series data for a point geometry."""
    if not gee_initialized: return pd.DataFrame(), "GEE مقداردهی اولیه نشده."
    if _point_geom is None: return pd.DataFrame(), "هندسه نقطه نامعتبر."

    try:
        s2_sr_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(_point_geom).filterDate(start_date, end_date) \
            .map(maskS2clouds).map(add_indices).select(index_name)

        def extract_value(image):
            value = image.reduceRegion(ee.Reducer.first(), _point_geom, 10).get(index_name)
            return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value}) \
                   .set('system:time_start', image.get('system:time_start'))

        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.notNull([index_name]))
        dates_list = ts_features.aggregate_array('date').getInfo()

        if not dates_list:
            orig_count = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(_point_geom).filterDate(start_date, end_date).size().getInfo()
            msg = f"هیچ تصویر S2 یافت نشد." if orig_count == 0 else f"داده‌ای برای '{index_name}' یافت نشد (احتمالا ابری)."
            return pd.DataFrame(), msg

        values_list = ts_features.aggregate_array(index_name).getInfo()
        ts_df = pd.DataFrame({'date': pd.to_datetime(dates_list), index_name: pd.to_numeric(values_list, errors='coerce')})
        return ts_df.sort_values('date').set_index('date').dropna(subset=[index_name]), None

    except ee.EEException as e: return pd.DataFrame(), f"خطای GEE سری زمانی '{index_name}': {e}"
    except Exception as e: return pd.DataFrame(), f"خطای Python سری زمانی '{index_name}': {e}"


@st.cache_data(show_spinner=False, persist="disk", ttl=7200)
def get_farm_needs_data(_farm_geometry, start_curr, end_curr, start_prev, end_prev):
    """Gets mean NDVI, NDMI, EVI, SAVI for current and previous periods."""
    if not gee_initialized: return {'error': "GEE مقداردهی اولیه نشده."}
    if _farm_geometry is None: return {'error': "هندسه نامعتبر."}

    results = {f'{idx}_{p}': np.nan for idx in ['NDVI', 'NDMI', 'EVI', 'SAVI'] for p in ['curr', 'prev']}
    results['error'] = None
    indices_to_get = ['NDVI', 'NDMI', 'EVI', 'SAVI']

    def get_means(start, end):
        period_vals, err_msg = {idx: np.nan for idx in indices_to_get}, None
        img_found = False
        try:
            s2_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterBounds(_farm_geometry).filterDate(start, end).map(maskS2clouds)
            count = s2_col.size().getInfo()
            if count == 0: # Try fallback
                fb_days = 20; fb_end = (datetime.datetime.strptime(end,'%Y-%m-%d') + datetime.timedelta(days=fb_days)).strftime('%Y-%m-%d')
                s2_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(_farm_geometry).filterDate(start, fb_end).map(maskS2clouds)
                count = s2_col.size().getInfo()
                if count == 0: return period_vals, f"تصویری در {start}-{end} (یا بازه گسترده) یافت نشد", False

            img_found = True
            median_image = s2_col.map(add_indices).median().select(indices_to_get)
            mean_stats = median_image.reduceRegion(ee.Reducer.mean(), _farm_geometry, 10, bestEffort=True, maxPixels=1e8).getInfo()
            for index in indices_to_get:
                val = mean_stats.get(index)
                if val is not None: period_vals[index] = float(val)
            return period_vals, None, img_found
        except ee.EEException as e: err_msg = f"خطای GEE ({start}-{end}): {e}"; return period_vals, err_msg, img_found
        except Exception as e: err_msg = f"خطای Python ({start}-{end}): {e}"; return period_vals, err_msg, img_found

    curr_values, err_curr, img_curr = get_means(start_curr, end_curr)
    results.update({f'{idx}_curr': curr_values.get(idx, np.nan) for idx in indices_to_get})
    if err_curr: results['error'] = f"جاری: {err_curr}"

    prev_values, err_prev, img_prev = get_means(start_prev, end_prev)
    results.update({f'{idx}_prev': prev_values.get(idx, np.nan) for idx in indices_to_get})
    if err_prev: results['error'] = (results['error'] + f"\nقبلی: {err_prev}") if results['error'] else f"قبلی: {err_prev}"

    if not img_curr and not img_prev and not results['error']: results['error'] = "تصویری در هیچ بازه‌ای یافت نشد."
    elif pd.isna(results['NDVI_curr']) and pd.isna(results['NDMI_curr']) and pd.isna(results['NDVI_prev']) and pd.isna(results['NDMI_prev']) and not results['error']:
          results['error'] = " مقادیر NDVI/NDMI برای هر دو بازه ناموجود."

    return results


@st.cache_data(show_spinner="در حال دریافت تحلیل AI...", persist="disk", ttl=3600)
def get_ai_needs_analysis(_model, farm_name, index_data, recommendations):
    """Generates AI analysis for the farm's condition related to needs."""
    if _model is None: return "سرویس هوش مصنوعی در دسترس نیست."

    data_str_parts = []
    for idx in ['NDVI', 'NDMI', 'EVI', 'SAVI']:
         curr_val, prev_val = index_data.get(f'{idx}_curr'), index_data.get(f'{idx}_prev')
         curr_s, prev_s = f"{curr_val:.3f}" if pd.notna(curr_val) else "N/A", f"{prev_val:.3f}" if pd.notna(prev_val) else "N/A"
         line = f"- {idx}: "
         if curr_s != "N/A":
             line += f"جاری: {curr_s}"
             if prev_s != "N/A":
                 line += f" (قبلی: {prev_s}"
                 if pd.notna(curr_val) and pd.notna(prev_val):
                     change, pct_change = curr_val - prev_val, np.nan
                     if prev_val != 0: pct_change = (change / abs(prev_val)) * 100
                     line += f", تغییر: {change:.3f}" + (f" [{pct_change:+.1f}%])" if pd.notna(pct_change) else ")")
                     status = determine_status({f'{idx} (هفته جاری)': curr_val, f'{idx} (هفته قبل)': prev_val}, idx)
                     line += f" - وضعیت: {status}"
                 else: line += ")"
             else: line += " (داده قبلی نیست)"
             data_str_parts.append(line)
         elif prev_s != "N/A": data_str_parts.append(f"- {idx}: قبلی: {prev_s} (داده جاری نیست)")

    data_str = "\n".join(data_str_parts) if data_str_parts else "داده شاخص عددی نیست."
    recommendations_str = "\n".join([f"- {rec}" for rec in recommendations]) if recommendations else 'توصیه‌ای نیست.'

    prompt = f"""
    شما متخصص کشاورزی نیشکر با داده‌های ماهواره‌ای هستید. وضعیت مزرعه '{farm_name}' را تحلیل کنید.
    شامل: 1. وضعیت فعلی (سلامت/رطوبت). 2. روند (مقایسه با قبل). 3. نیازها (آبیاری/کود/آفات؟) بر اساس شاخص‌ها و توصیه‌های اولیه. 4. توصیه کلی (بازدید/برنامه). 5. محدودیت داده (اگر هست).
    زبان: فارسی، تخصصی و قابل فهم.

    داده‌های شاخص:
{data_str}

    توصیه‌های اولیه:
{recommendations_str}

    تحلیل جامع شما:
    """
    try:
        response = _model.generate_content(prompt)
        if response and response.parts: return "".join([part.text for part in response.parts if hasattr(part, 'text')])
        elif response.prompt_feedback and response.prompt_feedback.block_reason: return f"پاسخ AI مسدود شد ({response.prompt_feedback.block_reason.name})."
        else: print("AI Needs Resp:", response); return "پاسخ AI نامعتبر."
    except Exception as e: st.warning(f"⚠️ خطای AI نیازها: {e}"); return "خطای دریافت تحلیل AI."


@st.cache_data(show_spinner="در حال دریافت خلاصه AI نقشه...", persist="disk", ttl=3600)
def get_ai_map_summary(_model, ranking_df_sorted, selected_index, selected_day):
    """Generates AI summary for the overall map/ranking status."""
    if _model is None: return "سرویس هوش مصنوعی در دسترس نیست."
    if ranking_df_sorted is None or ranking_df_sorted.empty: return "داده‌ای برای خلاصه‌سازی نیست."
    if 'وضعیت' not in ranking_df_sorted.columns: return "ستون 'وضعیت' نیست."

    ranking_df_sorted['وضعیت'] = ranking_df_sorted['وضعیت'].fillna("بدون داده")
    status_counts = ranking_df_sorted['وضعیت'].value_counts()
    neg = sum(c for s, c in status_counts.items() if any(t in str(s).lower() for t in ["تنش", "کاهش","نیاز"]))
    pos = sum(c for s, c in status_counts.items() if any(t in str(s).lower() for t in ["بهبود", "رشد","افزایش"]))
    nod = sum(c for s, c in status_counts.items() if "بدون داده" in str(s).lower() or "n/a" in str(s).lower())
    neu = len(ranking_df_sorted) - neg - pos - nod

    summary = f"خلاصه وضعیت {len(ranking_df_sorted)} مزرعه ({selected_day}, شاخص: {selected_index}):\n"
    summary += f"- بهبود/رشد: {pos}\n- ثابت/خنثی: {neu}\n- تنش/کاهش: {neg}\n- بدون داده: {nod}\n\n"

    sort_prob = selected_index != 'MSI'
    prob_farms = ranking_df_sorted.sort_index(ascending=sort_prob)[ranking_df_sorted['وضعیت'].astype(str).str.contains("تنش|کاهش|نیاز", case=False, na=False)].head(5)
    if not prob_farms.empty:
        summary += "مزارع با بیشترین نیاز به توجه:\n"
        curr_col, chg_col = f'{selected_index} (هفته جاری)', 'تغییر'
        for idx, row in prob_farms.iterrows():
            curr, chg = pd.to_numeric(row.get(curr_col), errors='coerce'), pd.to_numeric(row.get(chg_col), errors='coerce')
            summary += f"- رتبه {idx}: {row.get('مزرعه', '?')}, وضعیت: {row.get('وضعیت', '?')}, شاخص: {curr:.3f" if pd.notna(curr) else "N/A"}, تغییر: {chg:.3f" if pd.notna(chg) else "N/A"}\n"

    sort_good = selected_index == 'MSI'
    good_farms = ranking_df_sorted.sort_index(ascending=sort_good)[ranking_df_sorted['وضعیت'].astype(str).str.contains("بهبود|رشد", case=False, na=False)].head(5)
    if not good_farms.empty:
         summary += "\nمزارع با بهترین وضعیت/بهبود:\n"
         curr_col, chg_col = f'{selected_index} (هفته جاری)', 'تغییر'
         for idx, row in good_farms.iterrows():
            curr, chg = pd.to_numeric(row.get(curr_col), errors='coerce'), pd.to_numeric(row.get(chg_col), errors='coerce')
            summary += f"- رتبه {idx}: {row.get('مزرعه', '?')}, وضعیت: {row.get('وضعیت', '?')}, شاخص: {curr:.3f" if pd.notna(curr) else "N/A"}, تغییر: {chg:.3f" if pd.notna(chg) else "N/A"}\n"

    prompt = f"""
    شما تحلیلگر داده کشاورزی هستید. خلاصه‌ای کاربردی از وضعیت کلی مزارع بر اساس داده رتبه‌بندی زیر ارائه دهید.
    شامل: 1. تصویر کلی (توزیع وضعیت). 2. مزارع بحرانی (طبق لیست) و اقدام پیشنهادی بر اساس شاخص {selected_index}. 3. مزارع خوب (طبق لیست) و امکان الگوبرداری. 4. داده ناموجود. 5. اهمیت شاخص {selected_index}.
    زبان: فارسی و حرفه‌ای.

    داده‌های خلاصه رتبه‌بندی:
{summary}

    خلاصه تحلیل جامع شما:
    """
    try:
        response = _model.generate_content(prompt)
        if response and response.parts: return "".join([part.text for part in response.parts if hasattr(part, 'text')])
        elif response.prompt_feedback: return f"خلاصه AI مسدود شد ({response.prompt_feedback.block_reason.name})."
        else: print("AI Map Resp:", response); return "پاسخ AI نامعتبر."
    except Exception as e: st.warning(f"⚠️ خطای AI خلاصه نقشه: {e}"); return "خطای دریافت خلاصه AI."


def determine_status(row_data, index_name):
    """Determines status based on index change. Expects dict/Series."""
    NDMI_IRR_TH, NDVI_LOW_TH = 0.25, 0.3
    ABS_CHG_TH, PCT_POS_TH, PCT_NEG_TH = 0.02, 3.0, -5.0

    curr_val = pd.to_numeric(row_data.get(f'{index_name} (هفته جاری)'), errors='coerce')
    prev_val = pd.to_numeric(row_data.get(f'{index_name} (هفته قبل)'), errors='coerce')
    change = curr_val - prev_val if pd.notna(curr_val) and pd.notna(prev_val) else np.nan
    pct_change = (change / abs(prev_val)) * 100 if pd.notna(change) and pd.notna(prev_val) and prev_val != 0 else np.nan

    status = "نامشخص"
    if pd.notna(curr_val) and pd.notna(prev_val):
        is_pos = (pd.notna(change) and change > ABS_CHG_TH) or (pd.notna(pct_change) and pct_change > PCT_POS_TH)
        is_neg = (pd.notna(change) and change < -ABS_CHG_TH) or (pd.notna(pct_change) and pct_change < PCT_NEG_TH)
        if index_name in ['NDVI', 'EVI', 'LAI', 'CVI', 'SAVI']: status = "رشد مثبت / بهبود" if is_pos else ("تنش / کاهش" if is_neg else "ثابت")
        elif index_name == 'MSI': status = "بهبود (کاهش تنش)" if is_neg else ("تنش (افزایش MSI)" if is_pos else "ثابت") # Inverted logic
        elif index_name == 'NDMI':
            low = pd.notna(curr_val) and curr_val <= NDMI_IRR_TH
            if is_neg: status = "تنش رطوبتی شدید / نیاز آبیاری" if low else "کاهش رطوبت قابل توجه"
            elif is_pos: status = "افزایش رطوبت / بهبود"
            else: status = "تنش رطوبتی / نیاز آبیاری" if low else "رطوبت ثابت"
    elif pd.notna(curr_val):
        status = "بدون داده هفته قبل"
        if index_name == 'NDMI' and curr_val <= NDMI_IRR_TH: status += " (تنش رطوبتی احتمالی)"
        elif index_name == 'NDVI' and curr_val <= NDVI_LOW_TH: status += " (پوشش گیاهی پایین)"
    elif pd.notna(prev_val): status = "بدون داده هفته جاری"
    else: status = "بدون داده"
    return status


@st.cache_data(show_spinner=False, persist="disk", ttl=3600)
def calculate_weekly_indices_for_table(_farms_df_filtered, index_name, start_curr, end_curr, start_prev, end_prev):
    """ Calculates mean index values using GEE reduceRegions. Returns DataFrame and errors."""
    errors = []
    if not gee_initialized: return pd.DataFrame(), ["GEE مقداردهی اولیه نشده."]
    if _farms_df_filtered is None or _farms_df_filtered.empty: return pd.DataFrame(), ["DataFrame ورودی خالی."]
    if not all([start_curr, end_curr, start_prev, end_prev]): return pd.DataFrame(), ["تاریخ نامعتبر."]
    print(f"Calculating {index_name} for {len(_farms_df_filtered)} farms...")

    required_cols = ['مزرعه', 'ee_geometry', 'گروه', 'سن', 'واریته']
    if not all(c in _farms_df_filtered.columns for c in required_cols if c != 'ee_geometry'): # Check essentials
        missing = [c for c in required_cols if c not in _farms_df_filtered.columns and c != 'ee_geometry']
        return pd.DataFrame(), [f"ستون ضروری نیست: {', '.join(missing)}"]

    features, farm_props_dict, geoms = [], {}, []
    for idx, farm in _farms_df_filtered.iterrows():
        name, geom = farm.get('مزرعه'), farm.get('ee_geometry')
        props = {'مزرعه': name, 'گروه': farm.get('گروه','?'), 'سن': farm.get('سن','?'), 'واریته': farm.get('واریته','?')}
        farm_props_dict[name] = props # Store props regardless of geometry
        if name and geom and isinstance(geom, ee.Geometry):
            try: features.append(ee.Feature(geom, props).set('farm_id', name)); geoms.append(geom)
            except Exception as e: errors.append(f"خطای Feature '{name}': {e}")
        else: errors.append(f"هندسه نامعتبر/نبود برای '{name}'.") # Will add back with NaN later

    if not features:
        errors.append("هندسه معتبری برای پردازش GEE نیست.")
        return pd.DataFrame(list(farm_props_dict.values())), errors # Return original props

    farm_fc = ee.FeatureCollection(features)
    bounds = ee.Geometry.MultiPolygon(geoms).bounds(maxError=1)

    @st.cache_data(show_spinner=False)
    def get_images(bounds_info, s_c, e_c, s_p, e_p, idx_n):
        img_err = []
        img_c, err_c = get_processed_image(bounds, s_c, e_c, idx_n); img_err.append(f"جاری: {err_c}" if err_c else "")
        img_p, err_p = get_processed_image(bounds, s_p, e_p, idx_n); img_err.append(f"قبلی: {err_p}" if err_p else "")
        return img_c, img_p, [e for e in img_err if e]

    image_curr, image_prev, img_errors = get_images(bounds.getInfo(), start_curr, end_curr, start_prev, end_prev, index_name)
    errors.extend(img_errors)

    image_to_reduce, reducers, band_map = None, [], {}
    if image_curr:
        band_c = f"{index_name}_curr"; image_curr = image_curr.select(index_name).rename(band_c)
        reducers.append(ee.Reducer.mean().setOutputs([f'{band_c}_mean'])); band_map[f'{band_c}_mean'] = band_c
        image_to_reduce = image_curr
    if image_prev:
        band_p = f"{index_name}_prev"; image_prev = image_prev.select(index_name).rename(band_p)
        reducers.append(ee.Reducer.mean().setOutputs([f'{band_p}_mean'])); band_map[f'{band_p}_mean'] = band_p
        image_to_reduce = image_to_reduce.addBands(image_prev) if image_to_reduce else image_prev

    gee_results = {}
    if image_to_reduce and reducers:
        try:
            print(f"Running reduceRegions for {index_name}...")
            reduced_fc = image_to_reduce.reduceRegions(farm_fc, ee.Reducer.combine(reducers, True), 10, tileScale=4)
            results_dict_agg = reduced_fc.aggregate_dictionary('farm_id').getInfo()
            print(f"Fetched GEE results for {len(results_dict_agg)} farms.")
            for farm_id, props in results_dict_agg.items():
                res = {b_map: float(props[g_b]) if g_b in props and props[g_b] is not None else np.nan
                       for g_b, b_map in band_map.items()}
                gee_results[farm_id] = res # farm_id is farm_name
        except ee.EEException as e: errors.append(f"خطای GEE reduceRegions: {e}")
        except Exception as e: errors.append(f"خطای Python reduceRegions: {e}")

    final_list = []
    processed_names = set(gee_results.keys())
    for name, props in farm_props_dict.items():
        combined = props.copy()
        if name in gee_results: combined.update(gee_results[name])
        else: combined.update({f'{index_name}_curr': np.nan, f'{index_name}_prev': np.nan}) # Ensure keys exist if GEE failed
        final_list.append(combined)

    if not final_list: errors.append("پردازش ناموفق، نتیجه‌ای نیست."); return pd.DataFrame(), errors

    final_df = pd.DataFrame(final_list)
    curr_c, prev_c = f'{index_name}_curr', f'{index_name}_prev'
    if curr_c in final_df.columns and prev_c in final_df.columns:
        final_df[curr_c] = pd.to_numeric(final_df[curr_c], errors='coerce')
        final_df[prev_c] = pd.to_numeric(final_df[prev_c], errors='coerce')
        final_df['تغییر'] = final_df[curr_c] - final_df[prev_c]
    else: final_df['تغییر'] = np.nan

    final_df = final_df.rename(columns={curr_c: f'{index_name} (هفته جاری)', prev_c: f'{index_name} (هفته قبل)'})
    cols_order = ['مزرعه', 'گروه', 'سن', 'واریته', f'{index_name} (هفته جاری)', f'{index_name} (هفته قبل)', 'تغییر']
    final_df = final_df[[c for c in cols_order if c in final_df.columns]]

    print(f"Finished calculating weekly indices. Output shape: {final_df.shape}")
    return final_df, list(set(errors))


# ==============================================================================
# Main Application Layout (Tabs)
# ==============================================================================

tab1, tab2, tab3 = st.tabs(["📊 پایش مزارع", "📈 تحلیل محاسبات", "💧 تحلیل نیازها"])

with tab1:
    st.header("📊 پایش مزارع (نقشه و رتبه‌بندی)")
    st.markdown("وضعیت سلامت و رطوبت مزارع با شاخص‌های ماهواره‌ای. نقشه: توزیع شاخص جاری. جدول: مقایسه با قبل.")

    # --- Workflow Check ---
    if farm_data_df is None or farm_data_df.empty: st.error("❌ داده مزارع بارگذاری نشده/خالی است.")
    elif filtered_farms_df.empty: st.warning(f"⚠️ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
    elif not gee_initialized: st.warning("⚠️ اتصال GEE برقرار نیست.")
    elif not all([start_date_current_str, end_date_current_str, start_date_previous_str, end_date_previous_str]):
         st.warning("⚠️ بازه زمانی نامعتبر (لطفاً 'روز هفته' معتبر انتخاب کنید).")
    else:
        # --- Calculate Ranking Data ONCE ---
        ranking_data, calculation_errors = None, []
        with st.spinner(f"در حال محاسبه شاخص '{selected_index}' برای مزارع '{selected_day}'..."):
            try:
                 ranking_data, calculation_errors = calculate_weekly_indices_for_table(
                     filtered_farms_df, selected_index, start_date_current_str,
                     end_date_current_str, start_date_previous_str, end_date_previous_str)
            except Exception as e:
                 st.error(f"❌ خطای محاسبه شاخص‌ها: {e}"); st.error(traceback.format_exc())
                 ranking_data = pd.DataFrame() # Ensure empty DF on error

        if calculation_errors:
            st.warning("⚠️ خطا حین محاسبه شاخص‌ها (تا ۵ مورد):")
            unique_errors = list(set(calculation_errors))
            for err in unique_errors[:5]: st.warning(f"- {err}")
            if len(unique_errors) > 5: st.warning(f"... و {len(unique_errors) - 5} خطای دیگر.")

        if ranking_data is None: st.error("❌ محاسبه شاخص‌ها ناموفق.")
        else:
             # --- Map Display Logic ---
            selected_farm_details, map_bounds_geom = None, None
            center_lat, center_lon, zoom_level = INITIAL_LAT, INITIAL_LON, INITIAL_ZOOM
            is_single_farm = (selected_farm_name != "همه مزارع")

            if is_single_farm:
                details_list = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name]
                if not details_list.empty:
                    selected_farm_details = details_list.iloc[0]
                    lat, lon = selected_farm_details.get('wgs84_centroid_lat'), selected_farm_details.get('wgs84_centroid_lon')
                    geom = selected_farm_details.get('ee_geometry')
                    if pd.notna(lat) and pd.notna(lon) and geom:
                        center_lat, center_lon, zoom_level = lat, lon, 14
                        map_bounds_geom = geom
                    else: st.warning(f"مختصات/هندسه '{selected_farm_name}' نامعتبر.")
                else: st.error(f"جزئیات '{selected_farm_name}' نیست."); is_single_farm = False

            if not is_single_farm or map_bounds_geom is None:
                 all_geoms = [g for g in filtered_farms_df['ee_geometry'] if g]
                 if all_geoms:
                     try:
                         map_bounds_geom = ee.Geometry.MultiPolygon(all_geoms).bounds(maxError=1)
                         center = map_bounds_geom.centroid(maxError=1).getInfo()['coordinates']
                         center_lon, center_lat = center[0], center[1]
                         coords = map_bounds_geom.getInfo()['coordinates'][0]
                         lons, lats = [c[0] for c in coords], [c[1] for c in coords]
                         lon_diff, lat_diff = max(lons)-min(lons), max(lats)-min(lats)
                         if max(lon_diff, lat_diff)>0.5: zoom_level=10
                         elif max(lon_diff, lat_diff)>0.1: zoom_level=11
                         else: zoom_level = 12
                     except Exception as e: st.warning(f"خطای محاسبه مرز کلی: {e}")
                 else: st.warning("هندسه معتبری برای نمایش کلی نیست.")

            if is_single_farm and selected_farm_details is not None:
                 st.subheader(f"جزئیات مزرعه: {selected_farm_name} ({selected_day})")
                 # Display metric cards... (omitted for brevity)
            elif not is_single_farm:
                 st.subheader(f"نمایش کلی مزارع ({selected_day})")
                 st.markdown(modern_metric_card("تعداد مزارع", f"{len(filtered_farms_df):,}", "fa-leaf", "#185a9d"), unsafe_allow_html=True)
                 # Optional Pie chart... (omitted)

            st.markdown("---")
            st.subheader("🗺️ نقشه وضعیت مزارع")
            st.markdown(f"شاخص: '{selected_index}', هفته جاری: {start_date_current_str} تا {end_date_current_str}")

            vis_params = { # Define palettes etc.
                'NDVI': {'min': 0.1, 'max': 0.9, 'palette': ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']},
                 'EVI': {'min': 0.1, 'max': 0.8, 'palette': ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']},
                'NDMI': {'min': -0.5, 'max': 0.6, 'palette': ['#b2182b', '#ef8a62', '#fddbc7', '#f7f7f7', '#d1e5f0', '#67a9cf', '#2166ac']},
                 'LAI': {'min': 0, 'max': 6, 'palette': ['#f7f7f7', '#dcdcdc', '#babcba', '#8aae8b', '#5a9c5a', '#2a8a2a', '#006400']},
                 'MSI': {'min': 0.6, 'max': 2.5, 'palette': ['#2166ac', '#67a9cf', '#d1e5f0', '#f7f7f7', '#fddbc7', '#ef8a62', '#b2182b']},
                 'CVI': {'min': 0, 'max': 20, 'palette': ['#ffffb2', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']},
                 'SAVI': {'min': 0.1, 'max': 0.8, 'palette': ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']},
            }
            index_vis_params = vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']})

            m = geemap.Map(location=[center_lat, center_lon], zoom=zoom_level, add_google_map=False)
            m.add_basemap("HYBRID")

            gee_image_current, error_msg_current = None, None
            if map_bounds_geom:
                 with st.spinner("در حال بارگذاری تصویر ماهواره‌ای..."):
                     gee_image_current, error_msg_current = get_processed_image(map_bounds_geom, start_date_current_str, end_date_current_str, selected_index)
            else: error_msg_current = "مرز معتبر برای دریافت تصویر نیست."

            if gee_image_current:
                try:
                    m.addLayer(gee_image_current.clip(map_bounds_geom), index_vis_params, f"{selected_index} (جاری)")
                    # Add Legend... (omitted)
                    # Add Boundaries... (optional, potentially slow)
                    bound_style = {'color': 'yellow', 'fillColor': '00000000', 'width': 1}
                    if is_single_farm and selected_farm_details and selected_farm_details.get('ee_geometry'):
                         m.addLayer(selected_farm_details['ee_geometry'], bound_style, f'مرز {selected_farm_name}')
                    # elif not is_single_farm and map_bounds_geom: # Show all bounds?
                    #      all_feat = [ee.Feature(g) for g in filtered_farms_df['ee_geometry'] if g]
                    #      if all_feat: m.addLayer(ee.FeatureCollection(all_feat), bound_style, 'مرزها')
                except Exception as e: st.error(f"خطای افزودن لایه GEE: {e}")
            else: st.warning(f"تصویر نقشه یافت نشد. {error_msg_current or ''}")

            # Add Markers using PRE-CALCULATED data
            if ranking_data is not None and not ranking_data.empty:
                 popup_dict = ranking_data.set_index('مزرعه').to_dict('index')
                 for idx, farm_row in filtered_farms_df.iterrows():
                      lat, lon, name = farm_row.get('wgs84_centroid_lat'), farm_row.get('wgs84_centroid_lon'), farm_row.get('مزرعه')
                      if pd.notna(lat) and pd.notna(lon) and name:
                           info = popup_dict.get(name)
                           curr, prev, chg, status = ("N/A",)*3 + ["داده ناموجود"]
                           if info:
                               curr_r = info.get(f'{selected_index} (هفته جاری)')
                               prev_r = info.get(f'{selected_index} (هفته قبل)')
                               chg_r = info.get('تغییر')
                               curr = f"{curr_r:.3f}" if pd.notna(curr_r) else "N/A"
                               prev = f"{prev_r:.3f}" if pd.notna(prev_r) else "N/A"
                               chg = f"{chg_r:.3f}" if pd.notna(chg_r) else "N/A"
                               status = determine_status(info, selected_index)

                           html = f"<strong>{name}</strong><br>گروه: {farm_row.get('گروه','?')}<br>سن: {farm_row.get('سن','?')}<br>واریته: {farm_row.get('واریته','?')}<hr style='margin:2px 0;'>{selected_index}: {curr} (قبل: {prev})<br>تغییر: {chg}<br>وضعیت: {status}"
                           color = 'cadetblue'
                           if any(t in status.lower() for t in ["تنش", "کاهش", "نیاز"]): color='red'
                           elif any(t in status.lower() for t in ["بهبود", "رشد", "افزایش"]): color='green'
                           elif "بدون داده" in status.lower(): color='orange'
                           icon = 'star' if is_single_farm and name == selected_farm_name else 'info-circle'
                           if is_single_farm and name == selected_farm_name: color = 'purple'

                           folium.Marker([lat, lon], popup=folium.Popup(html, max_width=300), tooltip=f"{name} ({status})", icon=folium.Icon(color=color, icon=icon, prefix='fa')).add_to(m)
            else: st.info("داده پاپ‌آپ نیست.")

            m.add_layer_control()
            with st.container(): # Use container to manage layout
                st_folium(m, width=None, height=500, use_container_width=True, returned_objects=[])
            st.caption("برای جزئیات روی مارکر کلیک کنید.")

            # Time Series Plot
            st.markdown("---")
            st.subheader(f"📈 نمودار روند زمانی {selected_index}")
            if not is_single_farm: st.info("یک مزرعه خاص انتخاب کنید.")
            elif not gee_initialized: st.warning("اتصال GEE نیست.")
            elif selected_farm_details is None or pd.isna(selected_farm_details.get('wgs84_centroid_lon')): st.warning("مختصات نامعتبر.")
            else:
                 point = ee.Geometry.Point([selected_farm_details['wgs84_centroid_lon'], selected_farm_details['wgs84_centroid_lat']])
                 ts_df, ts_err = get_index_time_series(point, selected_index, (today-datetime.timedelta(days=365)).strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
                 if ts_err: st.warning(f"خطای سری زمانی: {ts_err}")
                 elif not ts_df.empty and selected_index in ts_df.columns and not ts_df[selected_index].isna().all():
                      fig_ts = px.line(ts_df.dropna(subset=[selected_index]), y=selected_index, title=f'روند {selected_index} - {selected_farm_name}', markers=True)
                      fig_ts.update_layout(xaxis_title="تاریخ", yaxis_title=selected_index, hovermode="x unified", margin=dict(l=20,r=20,t=40,b=20),paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                      st.plotly_chart(fig_ts, use_container_width=True)
                 else: st.info(f"داده معتبری برای نمودار سری زمانی '{selected_index}' نیست.")

            # Ranking Table
            st.markdown("---")
            st.subheader(f"📊 جدول رتبه‌بندی ({selected_index}, {selected_day})")
            st.markdown("مقایسه هفتگی شاخص.")

            if ranking_data is not None and not ranking_data.empty:
                sort_asc = (selected_index == 'MSI')
                sort_col = f'{selected_index} (هفته جاری)'
                if sort_col in ranking_data.columns:
                    ranked_df_s = ranking_data.sort_values(by=sort_col, ascending=sort_asc, na_position='last').reset_index(drop=True)
                else: ranked_df_s = ranking_data.copy(); st.warning(f"ستون مرتب‌سازی '{sort_col}' نیست.")

                if not ranked_df_s.empty:
                    ranked_df_s.index = ranked_df_s.index + 1; ranked_df_s.index.name = 'رتبه'
                    ranked_df_s['وضعیت'] = ranked_df_s.apply(lambda r: determine_status(r.to_dict(), selected_index), axis=1)
                    ranked_df_s['وضعیت_نمایش'] = ranked_df_s['وضعیت'].apply(status_badge)

                    display_df = ranked_df_s.copy()
                    cols_fmt = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
                    for col in cols_fmt:
                        if col in display_df.columns: display_df[col] = display_df[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")

                    disp_cols = ['مزرعه', 'گروه', 'سن', 'واریته'] + cols_fmt + ['وضعیت_نمایش']
                    final_cols = [c for c in disp_cols if c in display_df.columns]
                    display_df = display_df[final_cols].rename(columns={'وضعیت_نمایش': 'وضعیت'})

                    st.write("<style>td, th {text-align: center !important; vertical-align: middle !important;}</style>", unsafe_allow_html=True)
                    st.write(display_df.to_html(escape=False, index=True, classes=['data-table'], justify='center'), unsafe_allow_html=True)

                    # Summary Stats
                    st.subheader("📊 خلاصه وضعیت")
                    if 'وضعیت' in ranked_df_s.columns:
                         counts = ranked_df_s['وضعیت'].value_counts()
                         neg = sum(c for s, c in counts.items() if any(t in str(s).lower() for t in ["تنش","کاهش","نیاز"]))
                         pos = sum(c for s, c in counts.items() if any(t in str(s).lower() for t in ["بهبود","رشد","افزایش"]))
                         nod = sum(c for s, c in counts.items() if "بدون داده" in str(s).lower() or "n/a" in str(s).lower())
                         neu = len(ranked_df_s) - neg - pos - nod
                         c1,c2,c3,c4 = st.columns(4)
                         with c1: st.metric("🟢 بهبود/رشد", pos)
                         with c2: st.metric("⚪ ثابت/خنثی", neu)
                         with c3: st.metric("🔴 تنش/کاهش", neg)
                         with c4: st.metric("🟡 بدون داده", nod)
                         with st.expander("توضیحات وضعیت"): st.markdown("- **🟢**: بهبود قابل توجه\n- **⚪**: تغییر نامحسوس\n- **🔴**: وضعیت نامطلوب‌تر یا نیاز\n- **🟡**: عدم امکان محاسبه")
                    else: st.warning("ستون 'وضعیت' برای خلاصه نیست.")

                    # AI Summary
                    st.markdown("---")
                    st.subheader("🤖 خلاصه هوش مصنوعی وضعیت مزارع")
                    if gemini_model:
                       with st.spinner("در حال تولید خلاصه AI نقشه..."):
                           ai_summary = get_ai_map_summary(gemini_model, ranked_df_s, selected_index, selected_day)
                           st.markdown(ai_summary)
                    else: st.info("⚠️ سرویس AI در دسترس نیست.")

                    # Download
                    try:
                        dl_df = ranked_df_s.drop(columns=['وضعیت_نمایش'], errors='ignore')
                        csv = dl_df.to_csv(index=True, encoding='utf-8-sig')
                        st.download_button("📥 دانلود جدول رتبه‌بندی (CSV)", csv, f'ranking_{selected_index}_{selected_day}.csv', 'text/csv')
                    except Exception as e: st.error(f"خطای دانلود: {e}")

                else: st.info("داده‌ای برای جدول رتبه‌بندی نیست.")
            elif calculation_errors: st.error("محاسبه شاخص ناموفق بود.")
            else: st.info(f"داده‌ای برای رتبه‌بندی '{selected_index}' نیست.")
# --- End of Tab 1 ---


# ==============================================================================
# Tab 2: Analysis Data
# ==============================================================================
with tab2:
    st.header("📈 تحلیل داده‌های فایل محاسبات")
    st.markdown("مشاهده داده‌های فایل محاسبات مساحت و تولید به صورت نمودارهای تعاملی.")

    if analysis_area_df is None and analysis_prod_df is None: st.error("❌ داده تحلیل بارگذاری نشده.")
    else:
        available_edareh = []
        for df in [analysis_area_df, analysis_prod_df]:
            if df is not None:
                 if isinstance(df.index, pd.MultiIndex) and 'اداره' in df.index.names: available_edareh.extend(df.index.get_level_values('اداره').unique().tolist())
                 elif 'اداره' in df.columns: available_edareh.extend(df['اداره'].unique().tolist())
        available_edareh = sorted(list(set(e for e in available_edareh if pd.notna(e))))

        if not available_edareh: st.warning("⚠️ 'اداره' معتبری یافت نشد.")
        else:
            selected_edareh = st.selectbox("اداره را انتخاب کنید:", options=available_edareh, key='analysis_edareh')
            st.subheader(f"📊 داده‌های اداره: {selected_edareh}")
            c1, c2 = st.columns(2)

            with c1: # Area Plots
                st.markdown("#### مساحت (هکتار)")
                df_sel = None
                if analysis_area_df is not None:
                     try: # Select data for the Edareh
                         if isinstance(analysis_area_df.index, pd.MultiIndex): df_sel = analysis_area_df.loc[selected_edareh].copy() if selected_edareh in analysis_area_df.index.get_level_values('اداره') else None
                         elif 'اداره' in analysis_area_df.columns: df_sel = analysis_area_df[analysis_area_df['اداره'] == selected_edareh].copy(); df_sel = df_sel.set_index('سن', drop=False) if 'سن' in df_sel.columns else df_sel # Adjust index if needed
                     except Exception as e: st.warning(f"خطای انتخاب داده مساحت: {e}")

                     if df_sel is not None and not df_sel.empty:
                         if 'اداره' in df_sel.columns: df_sel = df_sel.drop(columns=['اداره'], errors='ignore') # Drop edareh col if present
                         df_sel=df_sel.fillna(0) # fill na for plotting
                         ages, varieties, z = df_sel.index.astype(str).tolist(), df_sel.columns.tolist(), df_sel.values
                         # Surface Plot
                         if len(ages)>1 and len(varieties)>1:
                             try:
                                 fig3d = go.Figure(data=[go.Surface(z=z,x=ages,y=varieties,colorscale='Viridis')])
                                 fig3d.update_layout(title=f'سطح مساحت - اداره {selected_edareh}', scene=dict(xaxis_title='سن',yaxis_title='واریته',zaxis_title='مساحت'),height=450,margin=dict(l=0,r=0,t=40,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                                 st.plotly_chart(fig3d, use_container_width=True)
                             except Exception as e: st.error(f"خطای نمودار سطح مساحت: {e}"); st.dataframe(df_sel)
                         else: st.info("داده ناکافی برای نمودار سطح."); st.dataframe(df_sel)
                         # Histogram
                         try:
                             df_melt = df_sel.reset_index().melt(id_vars=df_sel.index.name or 'سن', var_name='واریته', value_name='مساحت')
                             df_melt = df_melt[df_melt['مساحت'] > 0]
                             if not df_melt.empty:
                                 fighist = px.histogram(df_melt, x='واریته', y='مساحت', color=df_sel.index.name or 'سن', title=f'هیستوگرام مساحت - {selected_edareh}', barmode='group', text_auto='.2s')
                                 fighist.update_layout(height=400, margin=dict(l=0,r=0,t=40,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                                 st.plotly_chart(fighist, use_container_width=True)
                             else: st.info("داده برای هیستوگرام مساحت نیست.")
                         except Exception as e: st.error(f"خطای هیستوگرام مساحت: {e}")
                     else: st.info(f"داده مساحت برای اداره {selected_edareh} نیست.")
                else: st.info("داده مساحت بارگذاری نشده.")

            with c2: # Production Plots
                st.markdown("#### تولید (تن)")
                df_sel = None
                if analysis_prod_df is not None: # Similar logic as area
                    try:
                        if isinstance(analysis_prod_df.index, pd.MultiIndex): df_sel = analysis_prod_df.loc[selected_edareh].copy() if selected_edareh in analysis_prod_df.index.get_level_values('اداره') else None
                        elif 'اداره' in analysis_prod_df.columns: df_sel = analysis_prod_df[analysis_prod_df['اداره'] == selected_edareh].copy(); df_sel = df_sel.set_index('سن', drop=False) if 'سن' in df_sel.columns else df_sel
                    except Exception as e: st.warning(f"خطای انتخاب داده تولید: {e}")

                    if df_sel is not None and not df_sel.empty:
                        if 'اداره' in df_sel.columns: df_sel = df_sel.drop(columns=['اداره'], errors='ignore')
                        df_sel=df_sel.fillna(0)
                        ages, varieties, z = df_sel.index.astype(str).tolist(), df_sel.columns.tolist(), df_sel.values
                        # Surface plot
                        if len(ages)>1 and len(varieties)>1:
                            try:
                                fig3d=go.Figure(data=[go.Surface(z=z,x=ages,y=varieties,colorscale='Plasma')])
                                fig3d.update_layout(title=f'سطح تولید - اداره {selected_edareh}', scene=dict(xaxis_title='سن',yaxis_title='واریته',zaxis_title='تولید'),height=450,margin=dict(l=0,r=0,t=40,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                                st.plotly_chart(fig3d, use_container_width=True)
                            except Exception as e: st.error(f"خطای نمودار سطح تولید: {e}"); st.dataframe(df_sel)
                        else: st.info("داده ناکافی برای نمودار سطح."); st.dataframe(df_sel)
                        # Histogram
                        try:
                             df_melt = df_sel.reset_index().melt(id_vars=df_sel.index.name or 'سن', var_name='واریته', value_name='تولید')
                             df_melt = df_melt[df_melt['تولید'] > 0]
                             if not df_melt.empty:
                                 fighist = px.histogram(df_melt, x='واریته', y='تولید', color=df_sel.index.name or 'سن', title=f'هیستوگرام تولید - {selected_edareh}', barmode='group', text_auto='.3s')
                                 fighist.update_layout(height=400, margin=dict(l=0,r=0,t=40,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                                 st.plotly_chart(fighist, use_container_width=True)
                             else: st.info("داده برای هیستوگرام تولید نیست.")
                        except Exception as e: st.error(f"خطای هیستوگرام تولید: {e}")
                    else: st.info(f"داده تولید برای اداره {selected_edareh} نیست.")
                else: st.info("داده تولید بارگذاری نشده.")
    st.markdown("---")

# ==============================================================================
# Tab 3: Needs Analysis
# ==============================================================================
with tab3:
    st.header("💧 تحلیل نیاز آبیاری و کوددهی")
    st.markdown("ارزیابی نیازهای احتمالی مزرعه انتخابی با شاخص‌های ماهواره‌ای.")

    is_single_farm = (selected_farm_name != "همه مزارع")

    if not is_single_farm: st.info("👈 لطفاً یک مزرعه خاص از پنل کناری انتخاب کنید.")
    elif filtered_farms_df.empty: st.warning("⚠️ داده‌ای برای مزرعه/روز انتخابی نیست.")
    elif not gee_initialized: st.warning("⚠️ اتصال GEE برقرار نیست.")
    elif not all([start_date_current_str, end_date_current_str, start_date_previous_str, end_date_previous_str]):
         st.warning("⚠️ بازه زمانی نامعتبر.")
    else:
        details_tab3 = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
        geom_tab3 = details_tab3.get('ee_geometry')

        if geom_tab3 is None: st.error(f"❌ هندسه GEE '{selected_farm_name}' نیست.")
        else:
            st.subheader(f"تحلیل نیاز - مزرعه: {selected_farm_name}")
            needs_data = None
            with st.spinner("در حال دریافت داده شاخص نیازها..."):
                 needs_data = get_farm_needs_data(
                     geom_tab3, start_date_current_str, end_date_current_str,
                     start_date_previous_str, end_date_previous_str)

            if needs_data.get('error'): st.error(f"❌ خطا دریافت داده: {needs_data['error']}")
            elif all(pd.isna(needs_data.get(k)) for k in ['NDMI_curr','NDVI_curr','NDMI_prev','NDVI_prev']):
                st.warning("⚠️ داده شاخص لازم (NDMI/NDVI) برای هر دو دوره نیست.")
            else:
                 st.markdown("---")
                 st.markdown("#### نتایج شاخص‌ها")
                 def display_metric(lbl, val): st.metric(lbl, f"{val:.3f}" if pd.notna(val) else "N/A")
                 st.markdown("**هفته جاری:**")
                 c1,c2,c3,c4 = st.columns(4)
                 with c1: display_metric("NDVI", needs_data.get('NDVI_curr'))
                 with c2: display_metric("NDMI", needs_data.get('NDMI_curr'))
                 with c3: display_metric("EVI", needs_data.get('EVI_curr'))
                 with c4: display_metric("SAVI", needs_data.get('SAVI_curr'))
                 st.markdown("**هفته قبل:**")
                 c1p, c2p, c3p, c4p = st.columns(4)
                 with c1p: display_metric("NDVI", needs_data.get('NDVI_prev'))
                 with c2p: display_metric("NDMI", needs_data.get('NDMI_prev'))
                 with c3p: display_metric("EVI", needs_data.get('EVI_prev'))
                 with c4p: display_metric("SAVI", needs_data.get('SAVI_prev'))

                 st.markdown("---")
                 st.markdown("#### توصیه‌های اولیه")
                 recs = []
                 status_inp = {f'{i}_{p}': needs_data.get(f'{i}_{p}') for i in ['NDVI','NDMI','EVI','SAVI'] for p in ['curr','prev']}
                 status_inp_fmt = { # Format for "determine_status" which expects specific keys
                     f'{idx} (هفته جاری)': status_inp.get(f'{idx}_curr') for idx in ['NDVI','NDMI','EVI','SAVI']
                 }
                 status_inp_fmt.update({
                     f'{idx} (هفته قبل)': status_inp.get(f'{idx}_prev') for idx in ['NDVI','NDMI','EVI','SAVI']
                 })

                 ndmi_stat = determine_status(status_inp_fmt, 'NDMI')
                 ndvi_stat = determine_status(status_inp_fmt, 'NDVI')
                 evi_stat = determine_status(status_inp_fmt, 'EVI')

                 if any(t in ndmi_stat for t in ["نیاز آبیاری", "تنش رطوبتی"]): recs.append(f"💧 **نیاز آبیاری:** {ndmi_stat}")
                 elif "کاهش رطوبت" in ndmi_stat: recs.append(f"⚠️ **کاهش رطوبت:** بررسی آبیاری ({ndmi_stat})")
                 elif "افزایش رطوبت" in ndmi_stat: recs.append(f"✅ **رطوبت:** بهبود/افزایش ({ndmi_stat})")
                 elif "رطوبت ثابت" in ndmi_stat: recs.append(f"ℹ️ **رطوبت:** ثابت ({ndmi_stat})")
                 elif "(تنش رطوبتی احتمالی)" in ndmi_stat: recs.append(f"⚠️ **تنش رطوبتی احتمالی:** (بر اساس داده جاری).")

                 veg_concern = False
                 if "تنش / کاهش" in ndvi_stat: recs.append(f"📉 **کاهش پوشش (NDVI):** {ndvi_stat}. بررسی کود/عوامل دیگر."); veg_concern=True
                 if "تنش / کاهش" in evi_stat and not veg_concern: recs.append(f"📉 **کاهش پوشش (EVI):** {evi_stat}. بررسی کود/عوامل دیگر."); veg_concern=True
                 if "(پوشش گیاهی پایین)" in ndvi_stat: recs.append(f"⚠️ **پوشش پایین (NDVI):** (بر اساس داده جاری)."); veg_concern = True
                 elif "(پوشش گیاهی پایین)" in evi_stat and not veg_concern: recs.append(f"⚠️ **پوشش پایین (EVI):** (بر اساس داده جاری).")


                 if not recs: recs.append("✅ وضعیت مزرعه در محدوده نرمال یا تغییرات قابل توجهی نیست.")

                 for r in recs:
                    rl = r.lower()
                    if any(t in rl for t in ["نیاز آبیاری", "تنش رطوبتی", "کاهش رطوبت"]): st.error(r)
                    elif any(t in rl for t in ["کاهش پوشش", "پوشش پایین"]): st.warning(r)
                    elif any(t in rl for t in ["بهبود", "افزایش"]): st.success(r)
                    else: st.info(r)

                 # AI Analysis
                 st.markdown("---")
                 st.markdown("#### تحلیل هوش مصنوعی")
                 if gemini_model:
                     with st.spinner("در حال تولید تحلیل AI نیازها..."):
                         ai_expl = get_ai_needs_analysis(gemini_model, selected_farm_name, needs_data, recs)
                         st.markdown(ai_expl)
                 else: st.info("⚠️ سرویس AI در دسترس نیست.")
    st.markdown("---")
# --- End of Tab 3 ---

# --- End of File app.py ---