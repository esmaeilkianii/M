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
# !!! WARNING: This is a security vulnerability.
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
         }

        .modern-card {
            background: linear-gradient(135deg, #43cea2 0%, #185a9d 100%);
            color: white;
            border-radius: 18px;
            padding: 20px;
            margin: 15px 0;
            box-shadow: 0 6px 20px rgba(30,60,114,0.1);
            text-align: center;
            transition: transform 0.3s ease-in-out, box-shadow 0.3s ease-in-out;
             overflow: hidden;
        }
        .modern-card:hover {
            transform: translateY(-5px) scale(1.02);
            box-shadow: 0 10px 30px rgba(30,60,114,0.15);
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

        .sidebar-logo {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 2rem;
             padding-top: 1rem;
        }
        .sidebar-logo img {
            width: 100px;
            height: 100px;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(30,60,114,0.15);
        }

        .main-logo {
            width: 55px;
            height: 55px;
            border-radius: 15px;
            margin-left: 15px;
            vertical-align: middle;
             box-shadow: 0 2px 8px rgba(30,60,114,0.1);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 20px;
        }
        .stTabs [data-baseweb="tab-list"] button {
            background-color: #f0f2f6;
            padding: 10px 15px;
            border-radius: 8px 8px 0 0;
            border-bottom: 2px solid transparent;
            transition: all 0.3s ease;
             font-weight: 700;
             color: #555;
        }
         .stTabs [data-baseweb="tab-list"] button:hover {
            background-color: #e2e6eb;
            color: #185a9d;
             border-bottom-color: #185a9d;
        }
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
            background-color: #ffffff;
            border-bottom-color: #43cea2;
            color: #185a9d;
             box-shadow: 0 -2px 8px rgba(30,60,114,0.05);
        }
         .stTabs [data-baseweb="tab-panel"] {
             padding: 20px 5px;
         }

        .status-badge {
            display: inline-block;
            padding: 0.3em 0.6em;
            font-size: 0.8em;
            font-weight: bold;
            line-height: 1.2;
            text-align: center;
            white-space: nowrap;
            vertical-align: middle;
            border-radius: 0.35rem;
            color: #fff;
             margin: 2px;
        }
        .status-positive { background-color: #28a745; }
        .status-negative { background-color: #dc3545; }
        .status-neutral { background-color: #6c757d; color: #fff; }
        .status-nodata { background-color: #ffc107; color: #212529; }

        table {
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
             box-shadow: 0 4px 12px rgba(0,0,0,0.05);
             border-radius: 8px;
             overflow: hidden;
        }
        th, td {
            text-align: center;
            padding: 10px;
            border-bottom: 1px solid #ddd;
            vertical-align: middle !important;
        }
        th {
            background-color: #185a9d;
            color: white;
             font-weight: 700;
        }
        tr:nth-child(even) { background-color: #f2f2f2; }
         @media (prefers-color-scheme: dark) {
             table { box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
              th { background-color: #0e3a5d; color: #f8f8f8; }
             tr:nth-child(even) { background-color: #3a3a3a; }
            tr:nth-child(odd) { background-color: #2b2b2b; }
             td { border-bottom-color: #555; }
         }

        .stAlert {
             border-radius: 8px;
             margin: 15px 0;
             padding: 15px;
             display: flex;
             align-items: flex-start;
        }
        .stAlert > div:first-child {
             font-size: 1.5em;
             margin-right: 15px;
             flex-shrink: 0;
        }
         .stAlert > div:last-child {
             font-size: 1em;
             line-height: 1.5;
             flex-grow: 1;
         }
          .stAlert a { color: #185a9d; }
           @media (prefers-color-scheme: dark) {
               .stAlert a { color: #43cea2; }
           }

         .js-plotly-plot {
             border-radius: 8px;
             overflow: hidden;
             margin: 20px 0;
             box-shadow: 0 4px 12px rgba(0,0,0,0.05);
         }
         @media (prefers-color-scheme: dark) {
             .js-plotly-plot { box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
         }

         .stSidebar {
             background: linear-gradient(180deg, #cce7ff 0%, #e0f7fa 100%);
             color: #333;
             padding: 20px;
         }
         @media (prefers-color-scheme: dark) {
             .stSidebar {
                background: linear-gradient(180deg, #1a435a 0%, #2b2b2b 100%);
                 color: #f8f8f8;
             }
              .stSidebar label { color: #f8f8f8; }
                .stSidebar .stTextInput > div > div > input,
                .stSidebar .stSelectbox > div > div > div > input[type="text"],
                .stSidebar .stNumberInput > div > div > input {
                    background-color: #3a3a3a;
                    color: #f8f8f8;
                    border-color: #555;
                }
                 .stSidebar .stTextInput > div > div > input:focus,
                 .stSidebar .stSelectbox > div > div > div > input[type="text"]:focus,
                 .stSidebar .stNumberInput > div > div > input:focus {
                    border-color: #43cea2;
                    box-shadow: 0 0 5px rgba(67, 206, 162, 0.5);
                }
                 .stSidebar .stRadio > label > div:first-child { color: #f8f8f8; }

         }
          .stSidebar h2 { color: #185a9d; }
          .stSidebar .stRadio > label > div:first-child { padding-right: 10px; }
           .stSidebar .stSelectbox > label { font-weight: 700; }
           .stSidebar .stSlider > label { font-weight: 700; }

         .stTextInput > div > div > input,
         .stSelectbox > div > div > div > input[type="text"],
         .stNumberInput > div > div > input {
             border-radius: 8px;
             border: 1px solid #ccc;
             padding: 8px 12px;
             transition: border-color 0.3s;
         }
          .stTextInput > div > div > input:focus,
          .stSelectbox > div > div > div > input[type="text"]:focus,
          .stNumberInput > div > div > input:focus {
             border-color: #43cea2;
             outline: none;
             box-shadow: 0 0 5px rgba(67, 206, 162, 0.5);
         }

         .stButton > button {
             background-color: #185a9d;
             color: white;
             border-radius: 8px;
             padding: 10px 20px;
             font-size: 1em;
             transition: background-color 0.3s, transform 0.1s;
             border: none;
             cursor: pointer;
         }
          .stButton > button:hover { background-color: #0f3c66; transform: translateY(-1px); }
           .stButton > button:active { transform: translateY(0); background-color: #0a2840; }

          .stDownloadButton > button { background-color: #43cea2; }
           .stDownloadButton > button:hover { background-color: #31a380; }
            .stDownloadButton > button:active { background-color: #247a60; }

         .stExpander {
              border-radius: 8px;
              border: 1px solid #ddd;
              box-shadow: 0 2px 8px rgba(0,0,0,0.03);
              margin: 15px 0;
          }
           .stExpander div[data-baseweb="accordion-header"] {
               background-color: #f8f8f8;
               border-bottom: 1px solid #ddd;
               border-top-left-radius: 8px;
               border-top-right-radius: 8px;
               padding: 10px 15px;
               font-weight: 700;
               color: #333;
           }
            .stExpander div[data-baseweb="accordion-panel"] { padding: 15px; }
           @media (prefers-color-scheme: dark) {
               .stExpander { border-color: #555; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
               .stExpander div[data-baseweb="accordion-header"] {
                   background-color: #3a3a3a;
                   border-bottom-color: #555;
                   color: #f8f8f8;
               }
           }

           hr { border-top: 2px dashed #ccc; margin: 30px 0; }
           @media (prefers-color-scheme: dark) { hr { border-top: 2px dashed #555; } }

            [data-testid="stMetricValue"] {
                text-align: center;
                width: 100%;
                display: block;
            }
             [data-testid="stMetricLabel"] {
                 text-align: center;
                 width: 100%;
                 display: block;
             }

    </style>
""", unsafe_allow_html=True)


def status_badge(status: str) -> str:
    """Returns HTML for a status badge with color."""
    if "بهبود" in status or "رشد مثبت" in status:
        badge_class = "status-positive"
    elif "تنش" in status or "کاهش" in status or "بدتر شدن" in status:
        badge_class = "status-negative"
    elif "ثابت" in status or "رطوبت ثابت" in status or "پوشش گیاهی پایین" in status: # Added NDMI/Low vegetation neutral terms
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


gemini_model = None
if gee_initialized:
    gemini_model = configure_gemini(GEMINI_API_KEY_HARDCODED)
    if gemini_model is None:
         st.warning("⚠️ سرویس تحلیل هوش مصنوعی به دلیل خطای پیکربندی در دسترس نیست. قابلیت‌های تحلیل هوش مصنوعی غیرفعال است.")
    st.warning("⚠️ **هشدار امنیتی:** کلید API جمینای مستقیماً در کد قرار داده شده است. این روش **ناامن** است و به شدت توصیه می‌شود از Streamlit Secrets برای مدیریت امن کلید استفاده کنید.", icon="🔒")


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
                      st.warning(f"⚠️ مختصات WGS84 یا هندسه GEE معتبر برای مزرعه '{selected_farm_name}' یافت نشد. نمایش نقشه محدود خواهد بود.")
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
                    lon_diff = bounds['even'][2] - bounds['even'][0]
                    lat_diff = bounds['even'][3] - bounds['even'][1]
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

                               if is_single_farm and selected_farm_details is not None:
                                   farm_data_for_popup = None
                                   if 'ranking_df' in locals() and not ranking_df.empty:
                                        farm_data_for_popup_list = ranking_df[ranking_df['مزرعه'] == farm_name]
                                        if not farm_data_for_popup_list.empty:
                                             farm_data_for_popup = farm_data_for_popup_list.iloc[0]

                                   if farm_data_for_popup is not None:
                                        current_index_val = f"{farm_data_for_popup.get(f'{selected_index} (هفته جاری)', 'N/A'):.3f}" if pd.notna(farm_data_for_popup.get(f'{selected_index} (هفته جاری)')) else 'N/A'
                                        previous_index_val = f"{farm_data_for_popup.get(f'{selected_index} (هفته قبل)', 'N/A'):.3f}" if pd.notna(farm_data_for_popup.get(f'{selected_index} (هفته قبل)')) else 'N/A'
                                        change_val = farm_data_for_popup.get('تغییر')
                                        change_val_display = f"{change_val:.3f}" if pd.notna(change_val) else 'N/A'
                                        status_text = determine_status(farm_data_for_popup, selected_index)


                               elif not is_single_farm and not ranking_df_map_popups.empty:
                                    farm_data_for_popup_list = ranking_df_map_popups[ranking_df_map_popups['مزرعه'] == farm_name]
                                    if not farm_data_for_popup_list.empty:
                                        farm_data_for_popup = farm_data_for_popup_list.iloc[0]
                                        current_index_val = f"{farm_data_for_popup.get(f'{selected_index} (هفته جاری)', 'N/A'):.3f}" if pd.notna(farm_data_for_popup.get(f'{selected_index} (هفته جاری)')) else 'N/A'
                                        previous_index_val = f"{farm_data_for_popup.get(f'{selected_index} (هفته قبل)', 'N/A'):.3f}" if pd.notna(farm_data_for_popup.get(f'{selected_index} (هفته قبل)')) else 'N/A'
                                        change_val = farm_data_for_popup.get('تغییر')
                                        change_val_display = f"{change_val:.3f}" if pd.notna(change_val) else 'N/A'
                                        status_text = determine_status(farm_data_for_popup, selected_index)


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
                          return None, f"GEE Error for {farm_name} ({start}-{end}): {e}"
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
                    f'{index_name} (هفته جاری)': current_val,
                    f'{index_name} (هفته قبل)': previous_val,
                    'تغییر': change,
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

            sort_col_name = f'{selected_index} (هفته جاری)'
            temp_sort_col = f'{sort_col_name}_sortable'

            if sort_col_name in ranking_df.columns:
                if ascending_sort:
                     ranking_df[temp_sort_col] = pd.to_numeric(ranking_df[sort_col_name], errors='coerce').fillna(float('inf'))
                else:
                     ranking_df[temp_sort_col] = pd.to_numeric(ranking_df[sort_col_name], errors='coerce').fillna(float('-inf'))

                ranking_df_sorted = ranking_df.sort_values(
                    by=temp_sort_col,
                    ascending=ascending_sort,
                ).drop(columns=[temp_sort_col]).reset_index(drop=True)
            else:
                 st.warning(f"⚠️ ستون '{sort_col_name}' برای مرتب‌سازی جدول یافت نشد.")
                 ranking_df_sorted = ranking_df.copy()


            if not ranking_df_sorted.empty:
                 ranking_df_sorted.index = ranking_df_sorted.index + 1
                 ranking_df_sorted.index.name = 'رتبه'

                 ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(
                     lambda row: determine_status(row, selected_index), axis=1
                 )

                 ranking_df_sorted['وضعیت_نمایش'] = ranking_df_sorted['وضعیت'].apply(lambda s: status_badge(s))

                 cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
                 for col in cols_to_format:
                     if col in ranking_df_sorted.columns:
                          ranking_df_sorted[col] = ranking_df_sorted[col].map(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")

                 display_columns = ['مزرعه', 'گروه', 'سن', 'واریته'] + cols_to_format + ['وضعیت_نمایش']
                 final_display_columns = [col for col in display_columns if col in ranking_df_sorted.columns]

                 ranking_df_display = ranking_df_sorted[final_display_columns].rename(columns={'وضعیت_نمایش': 'وضعیت'})

                 st.write("<style>td {vertical-align: middle !important;}</style>", unsafe_allow_html=True)
                 st.write(ranking_df_display.to_html(escape=False, index=True), unsafe_allow_html=True)

                 st.subheader("📊 خلاصه وضعیت مزارع (بر اساس رتبه‌بندی)")

                 status_counts = ranking_df_sorted['وضعیت'].value_counts()

                 positive_terms = [s for s in status_counts.index if "بهبود" in s or "رشد مثبت" in s]
                 negative_terms = [s for s in status_counts.index if any(sub in s for sub in ["تنش", "کاهش", "بدتر", "نیاز"])]
                 neutral_terms = [s for s in status_counts.index if any(sub in s for sub in ["ثابت", "رطوبت ثابت", "پوشش گیاهی پایین"])]
                 nodata_terms = [s for s in status_counts.index if "بدون داده" in s]

                 col1, col2, col3, col4 = st.columns(4)

                 with col1:
                     pos_count = sum(status_counts.get(term, 0) for term in positive_terms)
                     st.metric("🟢 بهبود", pos_count)

                 with col2:
                     neutral_count = sum(status_counts.get(term, 0) for term in neutral_terms)
                     st.metric("⚪ ثابت", neutral_count) # Corrected label to use a static string

                 with col3:
                     neg_count = sum(status_counts.get(term, 0) for term in negative_terms)
                     st.metric("🔴 تنش", neg_count)

                 with col4:
                      nodata_count = sum(status_counts.get(term, 0) for term in nodata_terms)
                      st.metric("🟡 بدون داده", nodata_count) # Corrected label to use a static string

                 st.info(f"""
                 **توضیحات وضعیت:**
                 - **🟢 بهبود/رشد مثبت**: مزارعی که نسبت به هفته قبل بهبود قابل توجهی داشته‌اند (افزایش شاخص‌هایی مانند NDVI یا کاهش شاخص‌هایی مانند MSI).
                 - **⚪ ثابت**: مزارعی که تغییر معناداری در شاخص نداشته‌اند (درون آستانه تغییر).
                 - **🔴 تنش/کاهش/بدتر شدن**: مزارعی که نسبت به هفته قبل وضعیت نامطلوب‌تری داشته‌اند (کاهش شاخص‌هایی مانند NDVI یا افزایش شاخص‌هایی مانند MSI) یا نیاز آبیاری/کودی تشخیص داده شده است.
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

    if not is_single_farm:
        st.info("⚠️ لطفاً یک مزرعه خاص را از پنل کناری (سمت چپ) انتخاب کنید تا تحلیل نیازهای آن نمایش داده شود.")
    elif not gee_initialized:
         st.warning("⚠️ اتصال به Google Earth Engine برقرار نیست. تحلیل نیازهای آبیاری و کوددهی در دسترس نمی‌باشد.")
    elif selected_farm_details is None or selected_farm_details.get('ee_geometry') is None:
         st.warning(f"⚠️ هندسه GEE معتبر برای مزرعه '{selected_farm_name}' یافت نشد. تحلیل نیازها امکان‌پذیر نیست.")
    elif not start_date_current_str or not end_date_current_str or not start_date_previous_str or not end_date_previous_str:
         st.warning("⚠️ بازه‌های زمانی معتبر برای تحلیل نیازها در دسترس نیست. لطفاً روز هفته را انتخاب کنید.")
    else:
        st.subheader(f"تحلیل برای مزرعه: {selected_farm_name}")

        st.markdown("---")
        st.markdown("#### نتایج شاخص‌ها (هفته جاری و قبل)")
        if farm_needs_data.get('error'):
            st.error(f"❌ خطا در دریافت داده‌های شاخص برای تحلیل نیازها: {farm_needs_data['error']}")
        elif pd.isna(farm_needs_data.get('NDMI_curr')) and pd.isna(farm_needs_data.get('NDVI_curr')):
            st.warning("⚠️ داده‌های شاخص لازم (NDMI و NDVI) برای تحلیل در دوره فعلی یافت نشد. (ممکن است به دلیل پوشش ابری باشد).")
        else:
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

            if pd.notna(farm_needs_data.get('NDMI_curr')) and farm_needs_data['NDMI_curr'] <= NDMI_IRRIGATION_THRESHOLD:
                recommendations.append(f"💧 نیاز به آبیاری (NDMI = {farm_needs_data['NDMI_curr']:.3f} <= آستانه {NDMI_IRRIGATION_THRESHOLD:.2f})")

            current_ndvi = farm_needs_data.get('NDVI_curr')
            previous_ndvi = farm_needs_data.get('NDVI_prev')

            if pd.notna(current_ndvi) and pd.notna(previous_ndvi):
                 if previous_ndvi is not None and previous_ndvi > 0.01:
                      ndvi_change = current_ndvi - previous_ndvi
                      ndvi_change_percent = (ndvi_change / previous_ndvi) * 100

                      if ndvi_change < 0 and abs(ndvi_change_percent) > NDVI_DROP_PERCENT_THRESHOLD:
                          recommendations.append(f"⚠️ نیاز به بررسی کوددهی (افت NDVI: {ndvi_change:.3f}, معادل {abs(ndvi_change_percent):.1f}% افت نسبت به هفته قبل)")

                 elif previous_ndvi is not None and previous_ndvi <= 0.01 and current_ndvi > previous_ndvi:
                    recommendations.append("ℹ️ NDVI هفته قبل بسیار پایین بوده است. افزایش در هفته جاری مشاهده می‌شود.")
                 elif previous_ndvi is not None and previous_ndvi <= 0.01 and current_ndvi <= previous_ndvi:
                      recommendations.append("⚠️ NDVI در هفته جاری و هفته قبل بسیار پایین است. نیاز به بررسی وضعیت عمومی مزرعه.")


            elif pd.isna(previous_ndvi) and pd.notna(current_ndvi):
                 st.caption("ℹ️ داده NDVI هفته قبل برای بررسی افت در دسترس نیست.")
            elif pd.notna(previous_ndvi) and pd.isna(current_ndvi):
                 st.warning("⚠️ داده NDVI هفته جاری برای بررسی وضعیت پوشش گیاهی در دسترس نیست.")


            if not recommendations:
                 recommendations.append("✅ بر اساس شاخص‌های فعلی و آستانه‌ها، وضعیت مزرعه مطلوب به نظر می‌رسد. (یا داده کافی برای تشخیص مشکل وجود ندارد).")

            for rec in recommendations:
                if "نیاز به آبیاری" in rec: st.error(rec)
                elif "نیاز به بررسی کوددهی" in rec or "بسیار پایین" in rec: st.warning(rec)
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