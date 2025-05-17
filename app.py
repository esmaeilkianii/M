import streamlit as st
import pyproj # Added for coordinate transformation
import base64 # For encoding logo image
import os # For path joining


# --- Theme Selection Logic ---
# MUST BE VERY EARLY, ideally after imports and before page_config
# Function to convert hex to RGB and check brightness
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def is_light_color(hex_color):
    r, g, b = hex_to_rgb(hex_color)
    # HSP (Highly Sensitive Poo) equation from http://alienryderflex.com/hsp.html
    hsp = (0.299 * r + 0.587 * g + 0.114 * b)
    return hsp > 127.5 # Returns true if light, false if dark

# Default theme: Light
DEFAULT_THEME_NAME = "روشن (پیش فرض)"

# Theme definitions (moved here for clarity)
THEMES = {
    "روشن (پیش فرض)": {
        "--primary-color": "#547849", # Darker Green for better contrast on light bg
        "--background-color": "#FFFFFF",
        "--secondary-background-color": "#F0F2F6", # Slightly off-white for elements
        "--text-color": "#31333F", # Dark gray for text
        "--accent-color": "#FF8C00", # Dark Orange for accents
        "--sidebar-background": "#F8F9FA",
        "--sidebar-text": "#31333F",
        "--button-bg": "#547849",
        "--button-text": "white",
        "--border-color": "#E0E0E0", # Light gray for borders
        "--container-background-color": "#FFFFFF",
        "--container-border-color": "#D1D5DB",
        "--link-color": "#4A90E2", # Bright blue for links
        "--tab-inactive-bg": "#E9ECEF",
        "--tab-inactive-text": "#495057",
        "--tab-active-bg": "#547849",
        "--tab-active-text": "white",
        "--info-bg": "#E6F7FF", # Light blue for info
        "--info-border": "#91D5FF",
        "--warning-bg": "#FFFBE6", # Light yellow for warning
        "--warning-border": "#FFE58F",
        "--success-bg": "#F6FFED", # Light green for success
        "--success-border": "#B7EB8F",
        "--error-bg": "#FFF1F0",   # Light red for error
        "--error-border": "#FFA39E",
        "--font-family": "Vazirmatn, sans-serif",
        "--box-shadow-light": "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.12)",
        "--box-shadow-medium": "0 3px 6px rgba(0,0,0,0.08), 0 3px 6px rgba(0,0,0,0.15)",
        # Additional variables based on usage
        "--metric-value-color": "#1E88E5", # Blue for metric values
        "--metric-label-color": "#546E7A", # Darker gray for metric labels
        "--dataframe-header-bg": "#547849",
        "--dataframe-header-text": "white",
        "--dataframe-row-even-bg": "#F9F9F9",
        "--dataframe-row-odd-bg": "#FFFFFF",
        "--dataframe-border": "#DCDCDC",
    },
    "تاریک ملایم": {
        "--primary-color": "#66BB6A", # Lighter Green for dark bg
        "--background-color": "#1E1E1E", # Very dark gray, almost black
        "--secondary-background-color": "#2C2C2C", # Dark gray for elements
        "--text-color": "#E0E0E0", # Light gray for text
        "--accent-color": "#FFA726", # Lighter Orange
        "--sidebar-background": "#252525",
        "--sidebar-text": "#E0E0E0",
        "--button-bg": "#66BB6A",
        "--button-text": "#1E1E1E", # Dark text on light green button
        "--border-color": "#424242", # Medium gray for borders
        "--container-background-color": "#2C2C2C",
        "--container-border-color": "#3A3A3A",
        "--link-color": "#81C784", # Light green for links
        "--tab-inactive-bg": "#3A3A3A",
        "--tab-inactive-text": "#B0B0B0",
        "--tab-active-bg": "#66BB6A",
        "--tab-active-text": "#1E1E1E",
        "--info-bg": "#1A2C3A", # Dark blue-gray
        "--info-border": "#3A799E",
        "--warning-bg": "#3A311A", # Dark yellow-brown
        "--warning-border": "#9E8C3A",
        "--success-bg": "#1A3A1B", # Dark green-gray
        "--success-border": "#3A9E3B",
        "--error-bg": "#3A1A1A",   # Dark red-brown
        "--error-border": "#9E3A3A",
        "--font-family": "Vazirmatn, sans-serif",
        "--box-shadow-light": "0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2)", # Darker shadows
        "--box-shadow-medium": "0 3px 6px rgba(0,0,0,0.25), 0 3px 6px rgba(0,0,0,0.2)",
        "--metric-value-color": "#81C784",
        "--metric-label-color": "#B0B0B0",
        "--dataframe-header-bg": "#66BB6A",
        "--dataframe-header-text": "#1E1E1E",
        "--dataframe-row-even-bg": "#2C2C2C",
        "--dataframe-row-odd-bg": "#333333",
        "--dataframe-border": "#424242",
    },
    "خاکستری مدرن": {
        "--primary-color": "#4A5568", # Slate Gray
        "--background-color": "#F7FAFC", # Very Light Gray
        "--secondary-background-color": "#EDF2F7", # Light Gray
        "--text-color": "#2D3748", # Dark Slate
        "--accent-color": "#DD6B20", # Burnt Orange
        "--sidebar-background": "#E2E8F0",
        "--sidebar-text": "#2D3748",
        "--button-bg": "#4A5568",
        "--button-text": "white",
        "--border-color": "#CBD5E0", # Lighter Slate for borders
        "--container-background-color": "#FFFFFF",
        "--container-border-color": "#A0AEC0",
        "--link-color": "#3182CE", # Standard Blue
        "--tab-inactive-bg": "#E2E8F0",
        "--tab-inactive-text": "#4A5568",
        "--tab-active-bg": "#4A5568",
        "--tab-active-text": "white",
        "--info-bg": "#EBF4FF", # Lightest Blue
        "--info-border": "#90CDF4",
        "--warning-bg": "#fef7e0", # Typo corrected from #fef7eT
        "--warning-border": "#c6ac8f",
        "--success-bg": "#F0FFF4", # Lightest Green
        "--success-border": "#9AE6B4",
        "--error-bg": "#FFF5F5",   # Lightest Red
        "--error-border": "#FEB2B2",
        "--font-family": "Vazirmatn, sans-serif",
        "--box-shadow-light": "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
        "--box-shadow-medium": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
        "--metric-value-color": "#DD6B20",
        "--metric-label-color": "#4A5568",
        "--dataframe-header-bg": "#4A5568",
        "--dataframe-header-text": "white",
        "--dataframe-row-even-bg": "#F7FAFC",
        "--dataframe-row-odd-bg": "#EDF2F7",
        "--dataframe-border": "#CBD5E0",
    },
}

# Initialize session state for theme if not already set
if 'selected_theme_name' not in st.session_state:
    st.session_state.selected_theme_name = DEFAULT_THEME_NAME
if 'theme_changed' not in st.session_state:
    st.session_state.theme_changed = False


# Get current theme colors
current_theme_colors = THEMES[st.session_state.selected_theme_name]

# Page Configuration (must be the first Streamlit command)
st.set_page_config(
    page_title="داشبورد پایش مزارع نیشکر",
    page_icon=" sugarcane-emoji.png", # Local emoji from project root
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Load and display logo ---
def get_image_as_base64(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

logo_path = "Dehkhoda-logo.png" # Make sure this path is correct relative to app.py
logo_base64 = get_image_as_base64(logo_path)

if logo_base64:
    # Determine logo filter based on background color brightness for better visibility
    bg_color_for_logo = current_theme_colors.get("--sidebar-background", "#F8F9FA") # Default to light if not found
    logo_filter_style = ""
    # Example: If sidebar is very dark, and logo is dark, invert it or make it lighter.
    # This is a simple example; more sophisticated logic might be needed for generic logos.
    # For this specific logo which has dark and light parts, this might not be ideal.
    # if not is_light_color(bg_color_for_logo):
    #     logo_filter_style = "filter: invert(1) grayscale(100%) brightness(200%);" # Makes it white-ish

    st.markdown(
        f"""
        <div style="display: flex; justify-content: center; margin-bottom: 10px;">
            <img src="data:image/png;base64,{logo_base64}" alt="Dehkhoda Logo" style="max-height: 100px; {logo_filter_style}">
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.warning(f"لوگو در مسیر '{logo_path}' یافت نشد. لطفاً مسیر فایل را بررسی کنید.")

# --- Imports --- (Keep after page_config if they don't cause issues)
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
import json
import datetime
import plotly.express as px
# import os # Redundant, imported at the top
from io import BytesIO
import requests
import traceback
from streamlit_folium import st_folium
import google.generativeai as genai
import time # For potential (not recommended) auto-rerun


# --- Apply Dynamic CSS based on selected theme ---
# This CSS block will use the variables defined in current_theme_colors
# Convert theme dictionary to CSS variables string
css_variables_string = "; ".join([f"{key}: {value}" for key, value in current_theme_colors.items()])

st.markdown(f"""
<style>
    :root {{
        {css_variables_string};
        --toastify-color-info: var(--info-bg);
        --toastify-color-success: var(--success-bg);
        --toastify-color-warning: var(--warning-bg);
        --toastify-color-error: var(--error-bg);
        --toastify-text-color-info: var(--text-color);
        --toastify-text-color-success: var(--text-color);
        --toastify-text-color-warning: var(--text-color);
        --toastify-text-color-error: var(--text-color);
    }}
    html, body, [class*="st-"], .main {{
        font-family: var(--font-family) !important;
        color: var(--text-color) !important;
        background-color: var(--background-color) !important;
    }}
    .stApp {{
        background-color: var(--background-color);
    }}
    .main .block-container {{
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 1rem; /* Reduced padding for wider feel */
        padding-right: 1rem; /* Reduced padding for wider feel */
    }}

    /* Sidebar styling */
    [data-testid="stSidebar"] {{
        background-color: var(--sidebar-background);
        border-right: 1px solid var(--border-color);
        padding: 1rem;
    }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] div {{
        color: var(--sidebar-text) !important;
    }}
    [data-testid="stSidebar"] .stMarkdown {{
         font-size: 0.95em; /* Slightly smaller text in sidebar */
    }}


    /* Button styling */
    .stButton>button {{
        background-color: var(--button-bg);
        color: var(--button-text);
        border: 1px solid var(--button-bg); /* Make border same as bg or a shade darker/lighter */
        border-radius: 0.375rem; /* Tailwind's default rounded-md */
        padding: 0.5rem 1rem;
        font-weight: 500; /* Medium weight */
        transition: background-color 0.2s ease-in-out, transform 0.1s ease-in-out;
        box-shadow: var(--box-shadow-light);
    }}
    .stButton>button:hover {{
        background-color: color-mix(in srgb, var(--button-bg) 85%, black 15%); /* Darken on hover */
        color: var(--button-text); /* Ensure text color remains consistent on hover */
        border: 1px solid color-mix(in srgb, var(--button-bg) 85%, black 15%);
        transform: translateY(-1px); /* Slight lift on hover */
    }}
    .stButton>button:focus {{
        outline: none;
        box-shadow: 0 0 0 0.2rem color-mix(in srgb, var(--accent-color) 40%, transparent 60%);
    }}
     /* Special button for Gemini */
    .stButton button[kind="secondary"] {{ /* Assuming Gemini button might be styled differently or just use default */
        background-color: var(--accent-color);
        color: var(--text-color); /* Ensure contrast if accent is light */
    }}
     .stButton button[kind="secondary"]:hover {{
        background-color: color-mix(in srgb, var(--accent-color) 85%, black 15%);
    }}


    /* Input elements styling */
    .stTextInput input, .stDateInput input, .stSelectbox select, .stTextArea textarea {{
        background-color: var(--secondary-background-color) !important;
        color: var(--text-color) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 0.375rem !important;
        padding: 0.5rem 0.75rem !important;
        box-shadow: var(--box-shadow-light) !important;
    }}
    .stTextInput input:focus, .stDateInput input:focus, .stSelectbox select:focus, .stTextArea textarea:focus {{
        border-color: var(--accent-color) !important;
        box-shadow: 0 0 0 0.2rem color-mix(in srgb, var(--accent-color) 30%, transparent 70%) !important;
    }}
        /* Placeholder text color for inputs */
        .stTextInput input::placeholder {{ color: color-mix(in srgb, var(--text-color) 60%, transparent 40%); }}


    /* Expander styling */
    .stExpander {{
        border: 1px solid var(--container-border-color) !important;
        border-radius: 0.5rem !important; /* Tailwind's rounded-lg */
        background-color: var(--container-background-color) !important;
        margin-bottom: 1rem;
        box-shadow: var(--box-shadow-medium);
    }}
    .stExpander header {{
        font-size: 1.1em;
        font-weight: 600; /* Semi-bold */
        color: var(--primary-color) !important;
        padding: 0.75rem 1rem !important;
        background-color: color-mix(in srgb, var(--container-background-color) 95%, var(--border-color) 5%) !important;
        border-bottom: 1px solid var(--container-border-color) !important;
        border-top-left-radius: 0.5rem;
        border-top-right-radius: 0.5rem;
    }}
    .stExpander header:hover {{
         background-color: color-mix(in srgb, var(--container-background-color) 90%, var(--border-color) 10%) !important;
    }}
    .stExpander div[data-testid="stExpanderDetails"] {{
        padding: 1rem;
         background-color: var(--container-background-color) !important; /* Ensure content area has the right bg */
    }}

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {{
        background-color: var(--secondary-background-color);
        border-radius: 0.5rem;
        padding: 0.25rem;
        box-shadow: var(--box-shadow-light);
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: var(--tab-inactive-bg);
        color: var(--tab-inactive-text);
        border-radius: 0.375rem; /* rounded-md */
        margin: 0.25rem;
        padding: 0.5rem 1rem;
        font-weight: 500;
        transition: background-color 0.2s ease-in-out, color 0.2s ease-in-out;
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        background-color: color-mix(in srgb, var(--tab-inactive-bg) 80%, var(--primary-color) 20%);
        color: var(--tab-active-text); /* Or a slightly different hover text color */
    }}
    .stTabs [aria-selected="true"] {{
        background-color: var(--tab-active-bg) !important;
        color: var(--tab-active-text) !important;
        box-shadow: var(--box-shadow-medium);
    }}

    /* Metric styling */
    [data-testid="stMetricValue"] {{
        color: var(--metric-value-color) !important;
        font-size: 2em !important; /* Larger metric value */
        font-weight: 700 !important; /* Bold */
    }}
    [data-testid="stMetricLabel"] {{
        color: var(--metric-label-color) !important;
        font-size: 0.9em !important;
        font-weight: 500;
    }}
    [data-testid="stMetricDelta"] svg {{ /* Color for delta indicator icon */
        fill: currentColor !important;
    }}

    /* Dataframe styling */
    .dataframe-container .styled-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9em;
        box-shadow: var(--box-shadow-medium);
        border-radius: 0.5rem;
        overflow: hidden; /* Important for border-radius on table */
    }}
    .dataframe-container .styled-table th, .dataframe-container .styled-table td {{
        padding: 0.75rem 1rem; /* Tailwind's p-3 */
        text-align: right; /* Farsi is RTL */
        border-bottom: 1px solid var(--dataframe-border);
    }}
    .dataframe-container .styled-table th {{
        background-color: var(--dataframe-header-bg);
        color: var(--dataframe-header-text);
        font-weight: 600; /* Semi-bold headers */
    }}
    .dataframe-container .styled-table tbody tr:nth-of-type(even) {{
        background-color: var(--dataframe-row-even-bg);
    }}
    .dataframe-container .styled-table tbody tr:nth-of-type(odd) {{
        background-color: var(--dataframe-row-odd-bg);
    }}
    .dataframe-container .styled-table tbody tr:hover {{
        background-color: color-mix(in srgb, var(--accent-color) 20%, var(--dataframe-row-odd-bg) 80%);
    }}
    .dataframe-container .styled-table tbody tr td:first-child,
    .dataframe-container .styled-table tbody tr th:first-child {{ /* For index column */
        font-weight: bold;
        color: var(--primary-color);
    }}

    /* Custom containers for sections */
    .section-container {{
        background-color: var(--container-background-color);
        padding: 1.5rem; /* Tailwind's p-6 */
        border-radius: 0.75rem; /* Tailwind's rounded-xl */
        margin-bottom: 1.5rem;
        box-shadow: var(--box-shadow-medium);
        border: 1px solid var(--container-border-color);
    }}
    .section-container h1, .section-container h2, .section-container h3 {{
        color: var(--primary-color);
        margin-top: 0; /* Remove default top margin for headings in section */
    }}

    /* Status badge styling */
    .status-badge {{
        display: inline-block;
        padding: 0.25em 0.6em;
        font-size: 0.85em;
        font-weight: 600;
        line-height: 1;
        text-align: center;
        white-space: nowrap;
        vertical-align: baseline;
        border-radius: 0.375rem; /* rounded-md */
    }}
    .status-positive {{ background-color: color-mix(in srgb, var(--success-bg) 70%, var(--success-border) 30%); color: color-mix(in srgb, var(--text-color) 80%, black 20%); border: 1px solid var(--success-border); }}
    .status-negative {{ background-color: color-mix(in srgb, var(--error-bg) 70%, var(--error-border) 30%); color: color-mix(in srgb, var(--text-color) 80%, black 20%); border: 1px solid var(--error-border); }}
    .status-neutral {{ background-color: color-mix(in srgb, var(--info-bg) 70%, var(--info-border) 30%); color: color-mix(in srgb, var(--text-color) 70%, black 30%); border: 1px solid var(--info-border); }}

    /* Gemini response styling */
    .gemini-response-default {{
        background-color: color-mix(in srgb, var(--secondary-background-color) 90%, var(--accent-color) 10%);
        border-left: 5px solid var(--accent-color);
        padding: 1rem;
        margin-top: 1rem;
        border-radius: 0.375rem;
        font-size: 0.95em;
        line-height: 1.6;
    }}
    .gemini-response-report {{
        background-color: var(--container-background-color);
        border: 1px solid var(--container-border-color);
        padding: 1.5rem;
        margin-top: 1rem;
        border-radius: 0.5rem;
        font-size: 1em;
        line-height: 1.7;
        box-shadow: var(--box-shadow-light);
    }}
     .gemini-response-report h1, .gemini-response-report h2, .gemini-response-report h3 {{
        color: var(--primary-color);
        border-bottom: 2px solid var(--accent-color);
        padding-bottom: 0.3rem;
        margin-top: 1.2rem;
    }}
    .gemini-response-analysis {{
        background-color: color-mix(in srgb, var(--secondary-background-color) 95%, var(--primary-color) 5%);
        border-left: 5px solid var(--primary-color);
        padding: 1rem;
        margin-top: 1rem;
        border-radius: 0.375rem;
        font-size: 0.95em;
        line-height: 1.6;
    }}

</style>
""", unsafe_allow_html=True)


# ==============================================================================
# Constants and Initializations
# ==============================================================================
INITIAL_LAT = 31.305 # Approximate center for Dehkhoda farms
INITIAL_LON = 48.505
INITIAL_ZOOM = 11
EE_ASSET_PATH = "projects/ee-esmaeilkiani13877/assets/Croplogging-Farm"
index_options = {
    'NDVI': 'NDVI (شاخص گیاهی تفاضلی نرمال شده)',
    'EVI': 'EVI (شاخص گیاهی بهبود یافته)',
    'NDMI': 'NDMI (شاخص رطوبت تفاضلی نرمال شده)',
    'LAI': 'LAI (شاخص سطح برگ)',
    'MSI': 'MSI (شاخص تنش رطوبتی)',
    'CVI': 'CVI (شاخص کلروفیل گیاهی)'
}
# Initialize GEE
try:
    ee.Initialize(opt_url='https://earthengine-highvolume.googleapis.com')
    # st.sidebar.success("✅ اتصال به GEE برقرار شد.") # Sidebar not yet rendered
except Exception as e:
    st.error(f"❌ خطای اتصال به Google Earth Engine: {e}. لطفاً از اتصال اینترنت و تنظیمات GEE خود اطمینان حاصل کنید.")
    st.stop()

# Function to load farm data from GEE asset
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع از GEE...", persist=True)
def load_farm_data_from_gee():
    try:
        fc = ee.FeatureCollection(EE_ASSET_PATH)
        features = fc.getInfo()['features']
        farm_records = []
        for f in features:
            props = f['properties']
            geom = f['geometry']
            
            # Create EE geometry to calculate accurate area
            ee_geom = None
            if geom and geom['type'] == 'Polygon' and geom['coordinates']:
                ee_geom = ee.Geometry.Polygon(geom['coordinates'])
            elif geom and geom['type'] == 'Point' and geom['coordinates']: # Handle if some are points
                ee_geom = ee.Geometry.Point(geom['coordinates'])

            # محاسبه centroid (مرکز هندسی ساده برای پلیگون‌ها)
            centroid_lon, centroid_lat = None, None
            if geom and geom['type'] == 'Polygon' and geom['coordinates'] and len(geom['coordinates'][0]) > 0:
                coords = geom['coordinates'][0] # Assuming outer ring
                centroid_lon = sum([pt[0] for pt in coords]) / len(coords)
                centroid_lat = sum([pt[1] for pt in coords]) / len(coords)
            elif geom and geom['type'] == 'Point' and geom['coordinates']:
                centroid_lon, centroid_lat = geom['coordinates'][0], geom['coordinates'][1]
            
            # محاسبه مساحت دقیق بر اساس هندسه
            area_ha = None
            if ee_geom and ee_geom.type().getInfo() == 'Polygon': # Calculate area only for polygons
                try:
                    area_m2 = ee_geom.area(maxError=1).getInfo()
                    if area_m2 is not None:
                        area_ha = area_m2 / 10000.0  # تبدیل به هکتار
                except Exception:
                    area_ha = None # Keep None if area calculation fails
            
            farm_records.append({
                'مزرعه': props.get('farm', ''),
                'گروه': props.get('group', ''),
                'واریته': props.get('Variety', ''),
                'سن': props.get('Age', ''),
                'مساحت': area_ha if area_ha is not None else props.get('Area', ''),  # استفاده از مساحت محاسبه شده دقیق یا مقدار اصلی
                'روز ': props.get('Day', ''), # Note: trailing space in 'روز '
                'Field': props.get('Field', ''),
                'اداره': props.get('Adminstration', 'N/A'), # Added back, assuming GEE property is 'Adminstration'
                'geometry': geom,
                'centroid_lon': centroid_lon,
                'centroid_lat': centroid_lat,
                'calculated_area_ha': area_ha,  # ذخیره مساحت محاسبه شده به عنوان ستون جداگانه
            })
        df = pd.DataFrame(farm_records)
        st.success(f"✅ داده‌های {len(df)} مزرعه از GEE بارگذاری شد.")
        return df
    except Exception as e:
        st.error(f"❌ خطای بارگذاری داده از GEE Asset: {e}\n{traceback.format_exc()}")
        return pd.DataFrame() # Return empty DataFrame on error


farm_data_df = load_farm_data_from_gee()

# Stop if data loading fails or is empty
if farm_data_df is None or farm_data_df.empty: # Corrected condition
    st.error("❌ بارگذاری داده مزارع از GEE ناموفق بود یا دیتابیس خالی است.")
    st.stop()

# ==============================================================================
# Gemini API Configuration
# ==============================================================================
# !!! هشدار امنیتی: قرار دادن مستقیم API Key در کد ریسک بالایی دارد !!!
# NOTE: Remember to replace "YOUR_GEMINI_API_KEY_HERE" with your actual key for deployment.
# Using st.secrets is the recommended secure approach.
# The following line contains a hardcoded API key. This is a security risk.
GEMINI_API_KEY = "AIzaSyDzirWUubBVyjF10_JZ8UVSd6c6nnTKpLw" # <<<<<<< جایگزین کنید و از st.secrets استفاده کنید >>>>>>>>

gemini_model = None
if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE" and GEMINI_API_KEY != "AIzaSyDzirWUubBVyjF10_JZ8UVSd6c6nnTKpLw": # Check against placeholder too
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        # st.sidebar.success("✅ اتصال به Gemini برقرار شد.") # Sidebar not yet rendered
    except Exception as e:
        # st.sidebar.error(f"اتصال به Gemini ناموفق: {e}") # Sidebar not yet rendered
        gemini_model = None # Ensure model is None on failure
elif GEMINI_API_KEY == "AIzaSyDzirWUubBVyjF10_JZ8UVSd6c6nnTKpLw":
    # This is the placeholder key, treat as if no key is configured for now
    # st.sidebar.warning("از کلید API جمینای نمونه استفاده می‌شود. برای عملکرد کامل، آن را جایگزین کنید.")
    # For actual operation, this key will likely fail or be rate-limited.
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        # st.sidebar.success("✅ اتصال به Gemini برقرار شد (با کلید نمونه).")
    except Exception as e:
        # st.sidebar.error(f"اتصال به Gemini (با کلید نمونه) ناموفق: {e}")
        gemini_model = None


@st.cache_data(ttl=300, show_spinner=False) # Cache Gemini responses for 5 mins
def ask_gemini(prompt, temperature=0.3, top_p=0.95):
    if not gemini_model:
        return "مدل Gemini در دسترس نیست. لطفاً تنظیمات کلید API را بررسی کنید."
    try:
        response = gemini_model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                top_p=top_p
            )
        )
        return response.text
    except Exception as e:
        return f"خطا در ارتباط با Gemini: {e}"


# ==============================================================================
# Sidebar Controls
# ==============================================================================
with st.sidebar:
    st.header("⚙️ تنظیمات نمایش")

    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE" or GEMINI_API_KEY == "AIzaSyDzirWUubBVyjF10_JZ8UVSd6c6nnTKpLw":
        st.warning("⚠️ کلید API جمینای خود را مستقیماً در کد برنامه (متغیر GEMINI_API_KEY) وارد کنید تا قابلیت‌های هوشمند فعال شوند. (توصیه می‌شود از `st.secrets` استفاده شود)")
    elif not gemini_model:
         st.error("اتصال به Gemini ناموفق بود. کلید API را بررسی کنید.")
    else:
         st.success("✅ اتصال به Gemini برقرار است.")

    # Theme Selector
    current_theme_index = list(THEMES.keys()).index(st.session_state.selected_theme_name)
    new_theme_name = st.selectbox(
        "🎨 انتخاب تم:",
        options=list(THEMES.keys()),
        index=current_theme_index,
        key="theme_selector_sb"
    )
    if new_theme_name != st.session_state.selected_theme_name:
        st.session_state.selected_theme_name = new_theme_name
        st.session_state.theme_changed = True # Flag that theme changed
        st.rerun() # Rerun to apply new theme immediately

    st.markdown("---")
    st.header("🗓️ انتخاب دوره و مزرعه")
    available_days = sorted(farm_data_df['روز '].unique(), key=lambda x: ["شنبه", "یکشنبه", "دوشنبه", "سه شنبه", "چهارشنبه", "پنجشنبه", "جمعه"].index(x))
    selected_day = st.selectbox("انتخاب روز هفته:", available_days, index=len(available_days)-1 if available_days else 0)
    filtered_farms_df = farm_data_df[farm_data_df['روز '] == selected_day]

    farm_names = ["همه مزارع"] + sorted(filtered_farms_df['مزرعه'].unique().tolist())
    selected_farm_name = st.selectbox("انتخاب مزرعه:", farm_names)

    selected_index = st.selectbox("انتخاب شاخص:", list(index_options.keys()), format_func=lambda x: index_options[x])

    st.markdown("---")
    st.subheader("📜 بازه‌های زمانی هفتگی")
    today = datetime.date.today()
    persian_to_weekday = {"شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1, "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4}
    try:
        target_weekday = persian_to_weekday[selected_day]
        days_to_subtract = (today.weekday() - target_weekday + 7) % 7
        end_date_current = today - datetime.timedelta(days=days_to_subtract) # Corrected logic

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
# GEE Functions
# ==============================================================================
def maskS2clouds(image):
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
    scl = image.select('SCL')
    good_quality_scl = scl.remap([4, 5, 6], [1, 1, 1], 0) # Keep Veg, Non-Veg, Water
    opticalBands = image.select('B.*').multiply(0.0001)
    return image.addBands(opticalBands, None, True).updateMask(mask).updateMask(good_quality_scl)


def add_indices(image):
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)',
        {'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2')}
    ).rename('EVI')
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    msi = image.expression('SWIR1 / NIR', {'SWIR1': image.select('B11'), 'NIR': image.select('B8').max(ee.Image(0.0001))}).rename('MSI') # Added safety for NIR
    lai_expr = ndvi.multiply(3.5).clamp(0,8)
    lai = lai_expr.rename('LAI')
    green_safe = image.select('B3').max(ee.Image(0.0001)) # Safety for GREEN
    red_safe = image.select('B4').max(ee.Image(0.0001))   # Safety for RED
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
                 error_message += "\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده - زمان محاسبه بیش از حد مجاز)"
            elif 'user memory limit exceeded' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده - حافظه بیش از حد مجاز)"
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
            # Check if the band exists. If not, the value will be null.
            # The .get(index_name) will handle if the band (and thus property) is missing after reduction.
            value = ee.Algorithms.If(
                image.bandNames().contains(index_name),
                image.reduceRegion(
                    reducer=ee.Reducer.mean(), 
                    geometry=_geometry, 
                    scale=10, # Sentinel-2 resolution for the bands used
                    maxPixels=1e9 # Allow for potentially large polygons
                ).get(index_name), # Get the specific index value
                None # ee.ರಿಯാലിಟಿ.null() or simply None for Python side
            )
            return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value})

        # Filter out features where the index value is null (e.g., band didn't exist, or all pixels were masked)
        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.notNull([index_name]))
        
        ts_info = ts_features.getInfo()['features']
        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), "داده‌ای برای سری زمانی یافت نشد (ممکن است هیچ تصویر معتبری در بازه نباشد یا شاخص محاسبه نشده باشد)."
        
        # Ensure properties exist and index_name is a key before accessing
        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} 
                   for f in ts_info if f['properties'] and index_name in f['properties'] and f['properties'][index_name] is not None]
        
        if not ts_data:
            return pd.DataFrame(columns=['date', index_name]), "داده معتبری برای سری زمانی یافت نشد (پس از فیلتر کردن مقادیر null)."

        df = pd.DataFrame(ts_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(by='date').set_index('date')
        return df, None
    except ee.EEException as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای GEE در دریافت سری زمانی: {e}"
    except Exception as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای ناشناخته در دریافت سری زمانی: {e}\n{traceback.format_exc()}"

# ==============================================================================
# Determine active farm geometry
# ==============================================================================
active_farm_geom = None
active_farm_centroid_for_point_ops = None # Retained if needed for specific point operations later
active_farm_name_display = selected_farm_name
active_farm_area_ha_display = "N/A" 

def get_farm_polygon_ee(farm_row): # farm_row is a pandas Series
    try:
        geom_dict = farm_row.get('geometry')
        if geom_dict and isinstance(geom_dict, dict) and geom_dict.get('type') == 'Polygon' and geom_dict.get('coordinates'):
            return ee.Geometry.Polygon(geom_dict['coordinates'])
        # Handle Point geometry if it exists, though area calculations won't apply
        elif geom_dict and isinstance(geom_dict, dict) and geom_dict.get('type') == 'Point' and geom_dict.get('coordinates'):
            return ee.Geometry.Point(geom_dict['coordinates'])
        return None
    except Exception as e:
        # st.warning(f"خطا در تبدیل هندسه برای مزرعه {farm_row.get('مزرعه', 'ناشناخته')}: {e}")
        return None

if selected_farm_name == "همه مزارع":
    if not filtered_farms_df.empty:
        # For "همه مزارع", use a bounding box of the centroids of all farms in the filtered list
        # These centroids ('centroid_lon', 'centroid_lat') were calculated in load_farm_data
        valid_centroids_df = filtered_farms_df.dropna(subset=['centroid_lon', 'centroid_lat'])
        if not valid_centroids_df.empty:
            min_lon_df = valid_centroids_df['centroid_lon'].min()
            min_lat_df = valid_centroids_df['centroid_lat'].min()
            max_lon_df = valid_centroids_df['centroid_lon'].max()
            max_lat_df = valid_centroids_df['centroid_lat'].max()
            
            if pd.notna(min_lon_df) and pd.notna(min_lat_df) and pd.notna(max_lon_df) and pd.notna(max_lat_df):
                try:
                    active_farm_geom = ee.Geometry.Rectangle([min_lon_df, min_lat_df, max_lon_df, max_lat_df])
                    active_farm_centroid_for_point_ops = active_farm_geom.centroid(maxError=1) # Centroid of the bounding box
                    active_farm_area_ha_display = f"{len(filtered_farms_df)} مزرعه"
                except Exception as e_bbox:
                    st.error(f"خطا در ایجاد محدوده کلی مزارع: {e_bbox}")
                    active_farm_geom = None # Ensure it's None on failure
            else:
                st.warning("مختصات معتبری برای ایجاد محدوده کلی مزارع یافت نشد.")
        else:
            st.warning("هیچ مزرعه‌ای با مختصات مرکزی معتبر برای نمایش کلی یافت نشد.")
            
else: # A single farm is selected
    selected_farm_details_active_df = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name]
    if not selected_farm_details_active_df.empty:
        farm_row_active = selected_farm_details_active_df.iloc[0]
        active_farm_geom = get_farm_polygon_ee(farm_row_active) 
        
        if active_farm_geom:
            if active_farm_geom.type().getInfo() == 'Polygon':
                try:
                    # Try to calculate area using GEE for the selected polygon
                    area_m2 = active_farm_geom.area(maxError=1).getInfo()
                    if area_m2 is not None:
                        active_farm_area_ha_display = area_m2 / 10000.0
                    else:
                        # Fallback to pre-calculated area if GEE returns None
                        active_farm_area_ha_display = farm_row_active.get('مساحت', "محاسبه نشد") 
                except Exception as e_area:
                    # Fallback to pre-calculated area on GEE error
                    active_farm_area_ha_display = farm_row_active.get('مساحت', "خطا در محاسبه")
            elif active_farm_geom.type().getInfo() == 'Point':
                 active_farm_area_ha_display = "هندسه نقطه‌ای" # Area not applicable for point
            
            # Set centroid for potential point operations (like map marker for single farm)
            try:
                active_farm_centroid_for_point_ops = active_farm_geom.centroid(maxError=1)
            except: # If centroid fails (e.g. empty geometry if get_farm_polygon_ee returned None but somehow passed)
                active_farm_centroid_for_point_ops = None
        else:
            active_farm_area_ha_display = farm_row_active.get('مساحت', "هندسه نامعتبر") # Use pre-calculated if geom fails
            
    else: 
        st.warning(f"جزئیات مزرعه '{selected_farm_name}' در لیست فیلتر شده یافت نشد.")


# ==============================================================================
# Main Panel Display
# ==============================================================================
tab1, tab2, tab3 = st.tabs(["📊 رتبه‌بندی و جزئیات", "🗺️ نقشه و روند زمانی", "💡 تحلیل هوشمند Gemini"])

with tab1:
    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    if not filtered_farms_df.empty:
        if selected_farm_name == "همه مزارع":
            st.subheader(f"📋 نمایش کلی مزارع برای روز: {selected_day}")
            st.info(f"تعداد مزارع در این روز: {len(filtered_farms_df)}")
        else:
            # Ensure we use the correct row from filtered_farms_df for details
            selected_farm_details_tab1_df = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name]
            if not selected_farm_details_tab1_df.empty:
                 selected_farm_details_tab1 = selected_farm_details_tab1_df.iloc[0]
                 st.subheader(f"📋 جزئیات مزرعه: {selected_farm_name} (روز: {selected_day})")
                 cols_details = st.columns([1,1,1])
                 with cols_details[0]:
                    # استفاده از مساحت دقیق محاسبه شده در GEE یا مقدار موجود در DataFrame
                    farm_area_display_val = selected_farm_details_tab1.get('مساحت') # This comes from load_farm_data_from_gee
                    if pd.notna(farm_area_display_val) and isinstance(farm_area_display_val, (int, float)):
                        st.metric("مساحت (هکتار)", f"{farm_area_display_val:,.2f}")
                    elif isinstance(active_farm_area_ha_display, (int, float)): # Fallback to dynamically calculated for single farm
                        st.metric("مساحت (هکتار)", f"{active_farm_area_ha_display:,.2f}")
                    else:
                        st.metric("مساحت (هکتار)", str(active_farm_area_ha_display)) # Display "N/A", "خطا", etc.
                 with cols_details[1]:
                     st.metric("واریته", f"{selected_farm_details_tab1.get('واریته', 'N/A')}")
                 with cols_details[2]:
                     admin_val = selected_farm_details_tab1.get('اداره', 'N/A')
                     group_val = selected_farm_details_tab1.get('گروه', 'N/A')
                     st.metric("اداره/گروه", f"{admin_val} / {group_val}")
            else:
                 st.warning(f"جزئیات مزرعه '{selected_farm_name}' در لیست فیلتر شده یافت نشد.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.subheader(f"📈 جدول رتبه‌بندی مزارع بر اساس {index_options[selected_index]} (روز: {selected_day})")
    # Corrected Caption: Reflects calculation over farm area
    st.caption("مقایسه مقادیر متوسط شاخص (محاسبه شده بر روی مساحت کامل مزرعه) در هفته جاری با هفته قبل.")

    @st.cache_data(show_spinner=f"⏳ در حال محاسبه {selected_index}...", persist=True)
    def calculate_weekly_indices_for_ranking_table(_farms_df, index_name_calc, start_curr, end_curr, start_prev, end_prev):
        results = []
        errors = []
        total_farms = len(_farms_df)
        prog_bar = st.progress(0, text="شروع پردازش مزارع برای رتبه‌بندی...")

        for i, (idx, farm_row) in enumerate(_farms_df.iterrows()): # farm_row is a Series
            prog_bar.progress((i + 1) / total_farms, text=f"پردازش مزرعه {i+1}/{total_farms}: {farm_row['مزرعه']}")
            farm_name_calc = farm_row['مزرعه']
            
            farm_polygon_for_calc = get_farm_polygon_ee(farm_row) # Pass the Series
            
            if not farm_polygon_for_calc or farm_polygon_for_calc.type().getInfo() != 'Polygon':
                errors.append(f"هندسه نامعتبر یا غیرپلی‌گون برای {farm_name_calc} در جدول رتبه‌بندی. محاسبه شاخص ناموفق.")
                results.append({
                    'مزرعه': farm_name_calc, 
                    'اداره': farm_row.get('اداره', 'N/A'), 
                    'گروه': farm_row.get('گروه', 'N/A'),
                    'مساحت (هکتار)': farm_row.get('مساحت', 'N/A'), # Get area from DataFrame
                    f'{index_name_calc} (هفته جاری)': None, 
                    f'{index_name_calc} (هفته قبل)': None, 
                    'تغییر': None
                })
                continue
            
            farm_area_ha = farm_row.get('مساحت', 'N/A') # Get area from DataFrame
            
            # Inner function to get mean value for a period over the polygon
            def get_mean_value_for_period(start_dt, end_dt):
                try:
                    # Use the full farm polygon for accurate index calculation
                    image_calc, error_calc = get_processed_image(farm_polygon_for_calc, start_dt, end_dt, index_name_calc)
                    if image_calc:
                        mean_dict = image_calc.reduceRegion(
                            reducer=ee.Reducer.mean(), 
                            geometry=farm_polygon_for_calc, 
                            scale=10, 
                            maxPixels=1e9
                        ).getInfo()
                        return mean_dict.get(index_name_calc), None
                    return None, error_calc
                except Exception as e_reduce: 
                    return None, f"خطا در reduceRegion برای {farm_name_calc} ({start_dt}-{end_dt}): {e_reduce}"

            current_val, err_curr = get_mean_value_for_period(start_curr, end_curr)
            if err_curr: errors.append(f"{farm_name_calc} (جاری): {err_curr}")
            
            previous_val, err_prev = get_mean_value_for_period(start_prev, end_prev)
            if err_prev: errors.append(f"{farm_name_calc} (قبلی): {err_prev}")
            
            change = None
            if isinstance(current_val, (int, float)) and isinstance(previous_val, (int, float)):
                change = float(current_val) - float(previous_val)
            
            results.append({
                'مزرعه': farm_name_calc, 
                'اداره': farm_row.get('اداره', 'N/A'), 
                'گروه': farm_row.get('گروه', 'N/A'),   
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
        for err in calculation_errors: st.caption(f"⚠️ {err}") # Show errors as captions

    ranking_df_sorted = pd.DataFrame()
    if not ranking_df.empty:
        # True for MSI (lower is better value for better rank)
        # False for NDVI etc. (higher is better value for better rank)
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
            # For NDVI, EVI, LAI, CVI, NDMI: Higher change is better
            if index_name_col_status in ['NDVI', 'EVI', 'LAI', 'CVI', 'NDMI']:
                if change_val_status > threshold_status: return "<span class='status-badge status-positive'>رشد/بهبود</span>"
                elif change_val_status < -threshold_status: return "<span class='status-badge status-negative'>تنش/کاهش</span>"
                else: return "<span class='status-badge status-neutral'>ثابت</span>"
            # For MSI: Lower change is better (less stress increase, or stress decrease)
            elif index_name_col_status in ['MSI']: 
                if change_val_status < -threshold_status: return "<span class='status-badge status-positive'>بهبود (تنش کمتر)</span>" # Negative change means MSI decreased (good)
                elif change_val_status > threshold_status: return "<span class='status-badge status-negative'>تنش بیشتر</span>" # Positive change means MSI increased (bad)
                else: return "<span class='status-badge status-neutral'>ثابت</span>"
            
            return "<span class='status-badge status-neutral'>نامشخص</span>"


        ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(lambda row: determine_status_html(row, selected_index), axis=1)
        df_display = ranking_df_sorted.copy()
        # Ensure 'مساحت (هکتار)' is also formatted if it's numeric
        cols_to_format_display = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر', 'مساحت (هکتار)']
        for col_fmt_dsp in cols_to_format_display:
            if col_fmt_dsp in df_display.columns:
                 df_display[col_fmt_dsp] = df_display[col_fmt_dsp].apply(
                     lambda x: f"{float(x):.2f}" if col_fmt_dsp == 'مساحت (هکتار)' and pd.notna(x) and isinstance(x, (int, float)) 
                     else (f"{float(x):.3f}" if pd.notna(x) and isinstance(x, (int, float)) 
                           else ("N/A" if pd.isna(x) else str(x)))
                 )
        
        # Define columns to display in the table, including 'مساحت (هکتار)'
        display_cols_ordered = ['مزرعه', 'اداره', 'گروه', 'مساحت (هکتار)', 
                                f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 
                                'تغییر', 'وضعیت']
        # Filter df_display to include only these columns in this order, if they exist
        df_display_final = df_display[[col for col in display_cols_ordered if col in df_display.columns]]

        st.markdown(f"<div class='dataframe-container'>{df_display_final.to_html(escape=False, index=True, classes='styled-table')}</div>", unsafe_allow_html=True)

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
            if 'بهبود (تنش کمتر)' in html_badge: return 'بهبود (تنش کمتر)' # Changed from 'تنش کمتر' for consistency with badge
            if 'ثابت' in html_badge: return 'ثابت'
            if 'تنش/کاهش' in html_badge: return 'تنش/کاهش'
            if 'تنش بیشتر' in html_badge: return 'تنش بیشتر' # For MSI negative status
            # if 'تنش شدید' in html_badge: return 'تنش شدید' # This was not in determine_status_html
            if 'بدون داده' in html_badge: return 'بدون داده'
            if 'خطا در داده' in html_badge: return 'خطا در داده'
            return 'نامشخص'

        csv_data_dl = ranking_df_sorted.copy()
        csv_data_dl['وضعیت'] = csv_data_dl['وضعیت'].apply(extract_status_text)
        # Use the same ordered columns for CSV as for display
        csv_data_dl_final = csv_data_dl[[col for col in display_cols_ordered if col in csv_data_dl.columns]]
        
        csv_output = csv_data_dl_final.to_csv(index=True, encoding='utf-8-sig').encode('utf-8-sig') # Ensure encoding for Farsi
        st.download_button(
            label="📥 دانلود جدول رتبه‌بندی (CSV)", data=csv_output,
            file_name=f"ranking_{selected_day}_{selected_index}_{end_date_current_str}.csv", mime="text/csv"
        )
    else:
        st.info("داده‌ای برای نمایش در جدول رتبه‌بندی یافت نشد.")
    st.markdown("</div>", unsafe_allow_html=True)


with tab2:
    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.subheader(f"🗺️ نقشه ماهواره‌ای شاخص {index_options[selected_index]} (هفته جاری: {start_date_current_str} تا {end_date_current_str})")
    vis_params_map = { 
        'NDVI': {'min': 0.0, 'max': 0.9, 'palette': ['#a50026', '#d73027', '#f46d43', '#fdae61', '#fee08b', '#ffffbf', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837']},
        'EVI': {'min': 0.0, 'max': 0.9, 'palette': ['#a50026', '#d73027', '#f46d43', '#fdae61', '#fee08b', '#ffffbf', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837']},
        'NDMI': {'min': -0.5, 'max': 0.8, 'palette': ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#f5f5f5', '#c7eae5', '#80cdc1', '#35978f', '#01665e']},
        'LAI': {'min': 0, 'max': 7, 'palette': ['#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']},
        'MSI': {'min': 0.2, 'max': 3.0, 'palette': ['#01665e', '#35978f', '#80cdc1', '#c7eae5', '#f5f5f5', '#f6e8c3', '#dfc27d', '#bf812d', '#8c510a']}, # Low Stress (blue/green) to High Stress (yellow/brown)
        'CVI': {'min': 0, 'max': 25, 'palette': ['#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']},
    }
    
    map_center_lat_folium, map_center_lon_folium, initial_zoom_map_val_folium = INITIAL_LAT, INITIAL_LON, INITIAL_ZOOM
    if active_farm_geom: # This is now a polygon for single farm, or bounding box for all
        try:
            if active_farm_geom.coordinates().getInfo(): # Check if coordinates exist
                 centroid_coords = active_farm_geom.centroid(maxError=1).coordinates().getInfo()
                 map_center_lon_folium, map_center_lat_folium = centroid_coords[0], centroid_coords[1]
            
            if selected_farm_name != "همه مزارع": # Single farm selected (polygon)
                 initial_zoom_map_val_folium = 15 
        except Exception: pass # Keep initial map center on error

    m = geemap.Map(location=[map_center_lat_folium, map_center_lon_folium], zoom=initial_zoom_map_val_folium, add_google_map=True)
    m.add_basemap("HYBRID")

    if active_farm_geom:
        image_current_map, error_msg_current_map = get_processed_image(active_farm_geom, start_date_current_str, end_date_current_str, selected_index)
        if image_current_map:
            try:
                m.addLayer(image_current_map, vis_params_map[selected_index], f'{index_options[selected_index]} (جاری)')
                m.add_colorbar(vis_params_map[selected_index], label=index_options[selected_index], layer_name=f'{index_options[selected_index]} (جاری)')
                
                # Add legend using custom HTML if colorbar is not sufficient or for extra info
                legend_html_content = geemap.get_legend(vis_params_map[selected_index], builtin_legend=None, legend_title=None) # Get HTML list items
                if legend_html_content: # geemap.get_legend might return None or an empty string
                    legend_title_map = index_options[selected_index].split('(')[0].strip()
                    legend_html = f'''
                     <div style="position: fixed; bottom: 50px; left: 10px; width: auto;
                                background-color: var(--container-background-color); opacity: 0.85; z-index:1000; padding: 10px; border-radius:8px;
                                font-family: 'Vazirmatn', sans-serif; font-size: 0.9em; box-shadow: 0 2px 5px rgba(0,0,0,0.2); color: var(--text-color);">
                       <p style="margin:0 0 8px 0; font-weight:bold; color:var(--primary-color);">راهنمای {legend_title_map}</p>
                       {legend_html_content}
                     </div>
                    '''
                    m.get_root().html.add_child(folium.Element(legend_html))

                # Draw farm boundaries or markers
                if active_farm_name_display == "همه مزارع":
                     for _, farm_row_map in filtered_farms_df.iterrows():
                         # Display marker at centroid for "همه مزارع" view
                         centroid_lon_map = farm_row_map.get('centroid_lon')
                         centroid_lat_map = farm_row_map.get('centroid_lat')
                         if pd.notna(centroid_lon_map) and pd.notna(centroid_lat_map):
                             folium.Marker(
                                 [centroid_lat_map, centroid_lon_map],
                                 popup=f"<b>{farm_row_map['مزرعه']}</b><br>اداره: {farm_row_map.get('اداره', 'N/A')}<br>گروه: {farm_row_map.get('گروه', 'N/A')}",
                                 tooltip=farm_row_map['مزرعه'], icon=folium.Icon(color='royalblue', icon='leaf', prefix='fa')
                             ).add_to(m)
                # For a single selected farm, draw its boundary if it's a polygon
                elif selected_farm_name != "همه مزارع" and active_farm_geom and active_farm_geom.type().getInfo() == 'Polygon':
                    try:
                        # Convert GEE geometry to GeoJSON for Folium
                        farm_geojson_map = active_farm_geom.getInfo() # This gets the GeoJSON structure
                        folium.GeoJson(
                            farm_geojson_map,
                            name=f"مرز مزرعه: {selected_farm_name}",
                            style_function=lambda x: {'color': 'yellow', 'weight': 2.5, 'opacity': 0.8, 'fillOpacity': 0.1},
                            tooltip=f"مزرعه: {selected_farm_name}"
                        ).add_to(m)
                        # Optionally, also add a marker at its centroid
                        if active_farm_centroid_for_point_ops:
                            point_coords_map = active_farm_centroid_for_point_ops.coordinates().getInfo()
                            folium.Marker(
                                [point_coords_map[1], point_coords_map[0]],
                                popup=f"<b>{selected_farm_name}</b><br>مرکز",
                                tooltip=f"مرکز {selected_farm_name}",
                                icon=folium.Icon(color='red', icon='info-sign')
                            ).add_to(m)
                    except Exception as e_geojson:
                        st.caption(f"نکته: خطا در نمایش مرز مزرعه {selected_farm_name} روی نقشه: {e_geojson}")

            except Exception as map_err: st.error(f"خطا در افزودن لایه به نقشه: {map_err}\n{traceback.format_exc()}")
        else: st.warning(f"تصویری برای نمایش روی نقشه یافت نشد. {error_msg_current_map}")
        st_folium(m, width=None, height=500, use_container_width=True, returned_objects=[])
    else: st.warning("هندسه مزرعه برای نمایش نقشه انتخاب نشده یا نامعتبر است.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.subheader(f"📊 نمودار روند زمانی شاخص {index_options[selected_index]} برای '{active_farm_name_display}'")
    st.caption("روند زمانی شاخص بر اساس داده‌های استخراج شده از کل مساحت مزرعه (در صورت انتخاب مزرعه منفرد) محاسبه می‌شود.")

    if active_farm_name_display == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را برای نمایش نمودار سری زمانی انتخاب کنید.")
    elif selected_farm_name != "همه مزارع" and active_farm_geom: # Check if a single farm is selected AND its geometry is available
        ts_end_date_chart = today.strftime('%Y-%m-%d')
        # User selects start date for the chart
        ts_start_date_chart_user = st.date_input("تاریخ شروع برای سری زمانی:", 
            value=today - datetime.timedelta(days=365), # Default 1 year back
            min_value=datetime.date(2017,1,1), max_value=today - datetime.timedelta(days=30), # Min 30 days data needed
            key="ts_start_date_chart", help="بازه زمانی حداقل ۳۰ روز و حداکثر ۲ سال توصیه می‌شود."
        )
        
        if st.button("📈 نمایش/به‌روزرسانی نمودار سری زمانی", key="btn_ts_chart_show"):
            max_days_chart = 365 * 2 # Max 2 years for chart
            if (today - ts_start_date_chart_user).days > max_days_chart:
                st.warning(f"بازه زمانی به ۲ سال ({max_days_chart} روز) محدود شد.")
                ts_start_date_chart_user = today - datetime.timedelta(days=max_days_chart)

            with st.spinner(f"⏳ در حال دریافت و ترسیم سری زمانی برای '{active_farm_name_display}'..."):
                # Use the full farm polygon (active_farm_geom) for time series calculation
                ts_df_chart, ts_error_chart = get_index_time_series(
                    active_farm_geom, selected_index, 
                    start_date_str=ts_start_date_chart_user.strftime('%Y-%m-%d'),
                    end_date_str=ts_end_date_chart
                )

                if ts_error_chart:
                    st.error(f"خطا در دریافت سری زمانی برای نمودار: {ts_error_chart}")
                elif not ts_df_chart.empty:
                    fig_chart = px.line(ts_df_chart, x=ts_df_chart.index, y=selected_index, markers=True,
                                        title=f"روند زمانی {index_options[selected_index]} برای {active_farm_name_display}")
                    fig_chart.update_layout(
                        font=dict(family="Vazirmatn", color="var(--text-color)"),
                        xaxis_title="تاریخ", yaxis_title=index_options[selected_index],
                        plot_bgcolor="var(--container-background-color)", 
                        paper_bgcolor="var(--container-background-color)",
                        hovermode="x unified"
                    )
                    fig_chart.update_traces(line=dict(color="var(--accent-color)", width=2.5), marker=dict(color="var(--primary-color)", size=6))
                    st.plotly_chart(fig_chart, use_container_width=True)
                else: st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} برای مزرعه '{active_farm_name_display}' یافت نشد. ممکن است در بازه انتخابی تصویر مناسبی موجود نباشد.")
    else: 
        st.warning("نمودار سری زمانی فقط برای مزارع منفرد (با هندسه معتبر) قابل نمایش است.")
    st.markdown("</div>", unsafe_allow_html=True)


with tab3:
    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.header("💡 تحلیل هوشمند با Gemini")
    st.caption("پاسخ‌های Gemini بر اساس داده‌های موجود و الگوهای کلی تولید می‌شوند و نباید جایگزین نظر کارشناسان شوند.")

    if not gemini_model:
        st.warning("⚠️ قابلیت‌های هوشمند Gemini با وارد کردن صحیح کلید API در کد (متغیر GEMINI_API_KEY) فعال می‌شوند. (توصیه می‌شود از `st.secrets` استفاده شود)")
    else:
        # Data Preparation for Tab 3 - uses cached ranking_df from Tab 1 if inputs are the same
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
            ascending_sort_tab3 = selected_index in ['MSI']
            ranking_df_sorted_tab3 = ranking_df_tab3.sort_values(
                by=f'{selected_index} (هفته جاری)', ascending=ascending_sort_tab3, na_position='last'
            ).reset_index(drop=True)
            ranking_df_sorted_tab3.index = ranking_df_sorted_tab3.index + 1 
            ranking_df_sorted_tab3.index.name = 'رتبه'
            
            ranking_df_sorted_tab3['وضعیت_html'] = ranking_df_sorted_tab3.apply(lambda row: determine_status_html(row, selected_index), axis=1)
            ranking_df_sorted_tab3['وضعیت'] = ranking_df_sorted_tab3['وضعیت_html'].apply(extract_status_text)

            count_positive_summary_tab3 = sum(1 for s in ranking_df_sorted_tab3['وضعیت_html'] if 'status-positive' in s)
            count_neutral_summary_tab3 = sum(1 for s in ranking_df_sorted_tab3['وضعیت_html'] if 'status-neutral' in s and 'بدون داده' not in s and 'خطا' not in s)
            count_negative_summary_tab3 = sum(1 for s in ranking_df_sorted_tab3['وضعیت_html'] if 'status-negative' in s)
            count_nodata_summary_tab3 = sum(1 for s in ranking_df_sorted_tab3['وضعیت_html'] if 'بدون داده' in s or 'خطا' in s or 'نامشخص' in s)
        else:
            essential_cols = ['مزرعه', 'اداره', 'گروه', 'وضعیت_html', 'وضعیت', 
                              f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر', 'مساحت (هکتار)']
            ranking_df_sorted_tab3 = pd.DataFrame(columns=[col for col in essential_cols if col in ranking_df_tab3.columns or col in ['مزرعه', 'وضعیت_html', 'وضعیت']]) # Ensure core columns exist
            count_nodata_summary_tab3 = len(filtered_farms_df) if filtered_farms_df is not None else 0


        farm_details_for_gemini_tab3 = ""
        analysis_basis_str_gemini_tab3 = "تحلیل شاخص‌ها بر اساس میانگین مقادیر پیکسل‌ها روی مساحت کامل پلی‌گون هر مزرعه انجام می‌شود."
        if active_farm_name_display != "همه مزارع":
            farm_details_for_gemini_tab3 = f"مزرعه مورد نظر: '{active_farm_name_display}'.\n"
            
            area_display_gemini = active_farm_area_ha_display # This is calculated in "Determine active farm geometry"
            if isinstance(area_display_gemini, (int, float)):
                farm_details_for_gemini_tab3 += f"مساحت (محاسبه شده با GEE): {area_display_gemini:,.2f} هکتار.\n"
            else: # Could be "N/A", "خطا در محاسبه", "هندسه نقطه‌ای", etc.
                farm_details_for_gemini_tab3 += f"مساحت: {str(area_display_gemini)}.\n"
            
            if filtered_farms_df is not None and not filtered_farms_df.empty:
                 csv_farm_details_tab3_series_df = filtered_farms_df[filtered_farms_df['مزرعه'] == active_farm_name_display]
                 if not csv_farm_details_tab3_series_df.empty:
                     csv_farm_detail_row = csv_farm_details_tab3_series_df.iloc[0]
                     farm_details_for_gemini_tab3 += f"واریته (از داده ورودی): {csv_farm_detail_row.get('واریته', 'N/A')}.\n"
                     farm_details_for_gemini_tab3 += f"اداره (از داده ورودی): {csv_farm_detail_row.get('اداره', 'N/A')}.\n"
                     farm_details_for_gemini_tab3 += f"گروه (از داده ورودی): {csv_farm_detail_row.get('گروه', 'N/A')}.\n"
                     farm_details_for_gemini_tab3 += f"سن (از داده ورودی): {csv_farm_detail_row.get('سن', 'N/A')}.\n"


        with st.expander("💬 پرسش و پاسخ هوشمند", expanded=True):
            st.markdown("##### سوال خود را در مورد وضعیت عمومی مزارع یا یک مزرعه خاص بپرسید.")
            user_farm_q_gemini = st.text_area(
                f"سوال شما درباره '{active_farm_name_display}' یا مزارع روز '{selected_day}' (شاخص: {index_options[selected_index]}):", 
                key="gemini_farm_q_text_tab3", 
                height=100
            )
            if st.button("✉️ ارسال سوال به Gemini", key="btn_gemini_farm_q_send_tab3"):
                if not user_farm_q_gemini.strip():
                    st.warning("لطفاً سوال خود را وارد کنید.")
                else:
                    prompt_gemini_q = f"شما یک دستیار هوشمند تحلیل داده‌های کشاورزی از راه دور هستید. به سوال کاربر در مورد مزارع نیشکر پاسخ دهید.\nروز مشاهده: {selected_day}.\nهفته منتهی به: {end_date_current_str}.\n{analysis_basis_str_gemini_tab3}\n"
                    context_data_gemini_q = farm_details_for_gemini_tab3
                    
                    if active_farm_name_display != "همه مزارع":
                        farm_data_for_prompt_q = pd.DataFrame()
                        if not ranking_df_sorted_tab3.empty:
                            farm_data_for_prompt_q = ranking_df_sorted_tab3[ranking_df_sorted_tab3['مزرعه'] == active_farm_name_display]
                        
                        if not farm_data_for_prompt_q.empty:
                            current_farm_data = farm_data_for_prompt_q.iloc[0]
                            status_text_gemini_q = current_farm_data['وضعیت']
                            current_val_str_gemini_q = f"{current_farm_data[f'{selected_index} (هفته جاری)']:.3f}" if pd.notna(current_farm_data[f'{selected_index} (هفته جاری)']) and isinstance(current_farm_data[f'{selected_index} (هفته جاری)'], (int, float)) else "N/A"
                            prev_val_str_gemini_q = f"{current_farm_data[f'{selected_index} (هفته قبل)']:.3f}" if pd.notna(current_farm_data[f'{selected_index} (هفته قبل)']) and isinstance(current_farm_data[f'{selected_index} (هفته قبل)'], (int, float)) else "N/A"
                            change_str_gemini_q = f"{current_farm_data['تغییر']:.3f}" if pd.notna(current_farm_data['تغییر']) and isinstance(current_farm_data['تغییر'], (int, float)) else "N/A"
                            
                            context_data_gemini_q += (
                                f"داده‌های مزرعه '{active_farm_name_display}' برای شاخص {index_options[selected_index]} (هفته منتهی به {end_date_current_str}):\n"
                                f"- مقدار میانگین هفته جاری: {current_val_str_gemini_q}\n" # Corrected: Added "میانگین"
                                f"- مقدار میانگین هفته قبل: {prev_val_str_gemini_q}\n" # Corrected: Added "میانگین"
                                f"- تغییر (میانگین جاری - میانگین قبلی): {change_str_gemini_q}\n" # Corrected: Added "میانگین"
                                f"- وضعیت کلی (بر اساس تغییر): {status_text_gemini_q}\n"
                            )
                        else:
                            context_data_gemini_q += f"داده‌های عددی میانگین هفتگی برای شاخص '{selected_index}' جهت مزرعه '{active_farm_name_display}' در جدول رتبه‌بندی یافت نشد.\n"
                        prompt_gemini_q += f"کاربر در مورد '{active_farm_name_display}' پرسیده: '{user_farm_q_gemini}'.\n{context_data_gemini_q}پاسخ جامع و مفید به فارسی ارائه دهید."
                    else: # "همه مزارع"
                        context_data_gemini_q = f"وضعیت کلی مزارع برای روز '{selected_day}' و شاخص '{index_options[selected_index]}'. تعداد {len(filtered_farms_df) if filtered_farms_df is not None else 0} مزرعه فیلتر شده‌اند."
                        if not ranking_df_sorted_tab3.empty:
                            context_data_gemini_q += (
                                f"\nخلاصه وضعیت مزارع (بر اساس میانگین روی مساحت کامل) برای شاخص {selected_index}:\n" # Corrected caption
                                f"- بهبود/رشد: {count_positive_summary_tab3}\n"
                                f"- ثابت: {count_neutral_summary_tab3}\n"
                                f"- تنش/کاهش: {count_negative_summary_tab3}\n"
                                f"- بدون داده/خطا: {count_nodata_summary_tab3}\n"
                            )
                        prompt_gemini_q += f"کاربر در مورد وضعیت کلی مزارع پرسیده: '{user_farm_q_gemini}'.\n{context_data_gemini_q}پاسخ جامع و مفید به فارسی ارائه دهید."
                    
                    with st.spinner("⏳ در حال پردازش پاسخ با Gemini..."):
                        response_gemini_q = ask_gemini(prompt_gemini_q)
                        st.markdown(f"<div class='gemini-response-default'>{response_gemini_q}</div>", unsafe_allow_html=True)

        with st.expander("📝 تولید گزارش وضعیت مزرعه (هفتگی)", expanded=False):
            if active_farm_name_display == "همه مزارع":
                st.info("لطفاً یک مزرعه خاص را از سایدبار برای تولید گزارش انتخاب کنید.")
            else:
                farm_data_for_report_gemini = pd.DataFrame()
                if not ranking_df_sorted_tab3.empty:
                    farm_data_for_report_gemini = ranking_df_sorted_tab3[ranking_df_sorted_tab3['مزرعه'] == active_farm_name_display]

                if farm_data_for_report_gemini.empty:
                    st.info(f"داده‌های رتبه‌بندی (محاسبه شده بر اساس میانگین مساحت) برای '{active_farm_name_display}' (شاخص: {selected_index}) جهت تولید گزارش موجود نیست.")
                elif st.button(f"📝 تولید گزارش برای '{active_farm_name_display}'", key="btn_gemini_report_gen_tab3"):
                    report_context_gemini = farm_details_for_gemini_tab3
                    current_farm_report_data = farm_data_for_report_gemini.iloc[0]
                    current_val_str_rep = f"{current_farm_report_data[f'{selected_index} (هفته جاری)']:.3f}" if pd.notna(current_farm_report_data[f'{selected_index} (هفته جاری)']) and isinstance(current_farm_report_data[f'{selected_index} (هفته جاری)'], (int,float)) else "N/A"
                    prev_val_str_rep = f"{current_farm_report_data[f'{selected_index} (هفته قبل)']:.3f}" if pd.notna(current_farm_report_data[f'{selected_index} (هفته قبل)']) and isinstance(current_farm_report_data[f'{selected_index} (هفته قبل)'], (int,float)) else "N/A"
                    change_str_rep = f"{current_farm_report_data['تغییر']:.3f}" if pd.notna(current_farm_report_data['تغییر']) and isinstance(current_farm_report_data['تغییر'], (int,float)) else "N/A"
                    status_text_rep = current_farm_report_data['وضعیت']
                    
                    report_context_gemini += (
                        f"داده‌های شاخص {index_options[selected_index]} برای '{active_farm_name_display}' (هفته منتهی به {end_date_current_str} - محاسبه میانگین روی مساحت کامل):\n"
                        f"- میانگین هفته جاری: {current_val_str_rep}\n" # Corrected: Added "میانگین"
                        f"- میانگین هفته قبل: {prev_val_str_rep}\n" # Corrected: Added "میانگین"
                        f"- تغییر (میانگین جاری - میانگین قبلی): {change_str_rep}\n" # Corrected: Added "میانگین"
                        f"- وضعیت کلی: {status_text_rep}\n"
                    )
                    prompt_rep = (
                        f"شما یک دستیار هوشمند برای تهیه گزارش‌های کشاورزی هستید. لطفاً یک گزارش توصیفی و ساختاریافته به زبان فارسی در مورد وضعیت '{active_farm_name_display}' برای هفته منتهی به {end_date_current_str} تهیه کنید.\n"
                        f"اطلاعات موجود:\n{report_context_gemini}{analysis_basis_str_gemini_tab3}\n"
                        f"در گزارش به موارد فوق اشاره کنید، تحلیل مختصری از وضعیت (با توجه به شاخص {selected_index} و تغییرات هفتگی آن) ارائه دهید و در صورت امکان، پیشنهادهای کلی (نه تخصصی و قطعی) برای بررسی میدانی یا مدیریتی بیان کنید. گزارش باید رسمی، دارای عنوان، تاریخ، و بخش‌های مشخص (مقدمه، وضعیت فعلی، تحلیل، پیشنهادات) و قابل فهم برای مدیران کشاورزی باشد."
                    )
                    with st.spinner(f"⏳ در حال تولید گزارش برای '{active_farm_name_display}'..."):
                        response_rep = ask_gemini(prompt_rep, temperature=0.6, top_p=0.9)
                        st.subheader(f"گزارش وضعیت مزرعه: {active_farm_name_display}")
                        st.markdown(f"**تاریخ گزارش:** {datetime.date.today().strftime('%Y-%m-%d')}")
                        st.markdown(f"**بازه زمانی:** {start_date_current_str} الی {end_date_current_str}")
                        st.markdown(f"<div class='gemini-response-report'>{response_rep}</div>", unsafe_allow_html=True)
        
        with st.expander("⚠️ دستیار اولویت‌بندی مزارع بحرانی", expanded=False):
            st.markdown(f"##### شناسایی مزارع نیازمند توجه فوری بر اساس شاخص '{index_options[selected_index]}' (بر اساس میانگین روی مساحت کامل مزرعه).")
            if count_negative_summary_tab3 == 0 and (not ranking_df_sorted_tab3.empty):
                st.info(f"بر اساس شاخص '{selected_index}'، هیچ مزرعه‌ای در وضعیت 'تنش/کاهش' برای روز '{selected_day}' شناسایی نشد.")
            elif ranking_df_sorted_tab3.empty :
                  st.info(f"داده‌ای برای رتبه‌بندی و اولویت‌بندی مزارع بر اساس شاخص '{selected_index}' یافت نشد.")
            elif st.button(f"🔍 تحلیل و اولویت‌بندی مزارع بحرانی", key="btn_gemini_priority_assist_tab3"):
                problematic_farms_df = ranking_df_sorted_tab3[
                    ranking_df_sorted_tab3['وضعیت'].str.contains('تنش|کاهش|بیشتر', case=False, na=False) # 'تنش بیشتر' for MSI
                ]
                
                sort_asc_for_change = selected_index not in ['MSI'] 
                problematic_farms_for_prompt = problematic_farms_df.sort_values(by='تغییر', ascending=sort_asc_for_change)
                                
                prompt_priority = f"""شما یک دستیار هوشمند برای اولویت‌بندی در مدیریت مزارع نیشکر هستید.
روز مشاهده: {selected_day}
شاخص مورد بررسی: {index_options[selected_index]} (ماهیت شاخص: {'مقدار بالاتر بهتر است (مثلاً پوشش گیاهی بیشتر)' if selected_index not in ['MSI'] else 'مقدار بالاتر بدتر است (تنش بیشتر / رطوبت کمتر)'})
هفته منتهی به: {end_date_current_str}

بر اساس جدول رتبه‌بندی هفتگی (محاسبه شده بر اساس میانگین روی مساحت کامل هر مزرعه)، {count_negative_summary_tab3} مزرعه وضعیت 'تنش/کاهش' یا تغییر نامطلوب قابل توجهی را نشان می‌دهند.
اطلاعات حداکثر ۵ مزرعه از این مزارع بحرانی (مرتب شده بر اساس شدت تغییر نامطلوب):
{problematic_farms_for_prompt[['مزرعه', 'اداره', 'گروه', f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر', 'وضعیت']].head(5).to_string(index=False)}

وظیفه شما:
1.  از بین مزارع فوق، حداکثر ۳ مورد از بحرانی‌ترین‌ها را بر اساس شدت وضعیت نامطلوب (مقدار 'تغییر' و مقدار میانگین فعلی شاخص) انتخاب کنید.
2.  برای هر مزرعه منتخب:
    الف. نام مزرعه، اداره/گروه، و داده‌های کلیدی آن (مقدار میانگین شاخص جاری، میانگین قبلی، تغییر، وضعیت) را ذکر کنید.
    ب. دو یا سه دلیل احتمالی اولیه برای این وضعیت نامطلوب (با توجه به ماهیت شاخص {selected_index}) ارائه دهید. (مثال: برای NDVI پایین: تنش آبی، آفات، بیماری، برداشت اخیر. برای MSI بالا: خشکی، تنش آبی شدید، آفات ریشه‌خوار).
    ج. یک یا دو اقدام اولیه پیشنهادی برای بررسی میدانی یا مدیریتی ارائه دهید. (مثال: بررسی سیستم آبیاری، پایش آفات/بیماری، نمونه برداری خاک/گیاه، بازدید کارشناس).
3.  در ابتدا یک جمله کلی در مورد وضعیت مزارع بحرانی ارائه دهید.
4.  اگر هیچ مزرعه‌ای وضعیت بحرانی ندارد (که در اینجا قاعدتا نباید اینطور باشد چون دکمه فعال شده)، این موضوع را اعلام کنید.

پاسخ باید به فارسی، ساختاریافته (با استفاده از لیست‌ها یا بخش‌بندی برای هر مزرعه)، و کاربردی باشد.
{analysis_basis_str_gemini_tab3}
"""
                with st.spinner("⏳ در حال تحلیل اولویت‌بندی با Gemini..."):
                    response_priority = ask_gemini(prompt_priority, temperature=0.5)
                    st.markdown(f"<div class='gemini-response-analysis'>{response_priority}</div>", unsafe_allow_html=True)
        
        with st.expander(f"📉 تحلیل هوشمند روند زمانی شاخص {index_options[selected_index]}", expanded=False):
            st.markdown(f"##### تحلیل روند زمانی شاخص '{index_options[selected_index]}' برای مزرعه '{active_farm_name_display}' (بر اساس کل مساحت مزرعه).")
            if active_farm_name_display == "همه مزارع":
                st.info("لطفاً یک مزرعه خاص را از سایدبار برای تحلیل سری زمانی انتخاب کنید.")
            elif active_farm_geom: # Check if a single farm's geometry is available
                # For this Gemini feature, use a fixed recent period (e.g., last 6 months)
                # No date input from user to keep it simple for this specific feature
                if st.button(f"🔍 تحلیل روند زمانی {selected_index} برای '{active_farm_name_display}' با Gemini", key="btn_gemini_timeseries_an_tab3"):
                    ts_end_date_gemini_ts = today.strftime('%Y-%m-%d')
                    ts_start_date_gemini_ts = (today - datetime.timedelta(days=180)).strftime('%Y-%m-%d') # Fixed 6 months
                    
                    with st.spinner(f"⏳ در حال دریافت داده‌های سری زمانی برای '{active_farm_name_display}' جهت تحلیل Gemini..."):
                        # Use active_farm_geom (full polygon) for time series
                        ts_df_gemini_ts, ts_error_gemini_ts = get_index_time_series(
                            active_farm_geom, selected_index, 
                            start_date_str=ts_start_date_gemini_ts, end_date_str=ts_end_date_gemini_ts
                        )
                    
                    if ts_error_gemini_ts:
                        st.error(f"خطا در دریافت داده‌های سری زمانی برای Gemini: {ts_error_gemini_ts}")
                    elif not ts_df_gemini_ts.empty:
                        ts_summary_gemini = f"داده‌های سری زمانی شاخص {index_options[selected_index]} برای '{active_farm_name_display}' در بازه {ts_start_date_gemini_ts} تا {ts_end_date_gemini_ts} (استخراج شده از کل مساحت مزرعه):\n"
                        sample_freq_gemini = max(1, len(ts_df_gemini_ts) // 10) 
                        ts_sampled_data_str = ts_df_gemini_ts.iloc[::sample_freq_gemini][[selected_index]].to_string(header=True, index=True, float_format='%.3f')
                        if len(ts_df_gemini_ts) > 1 and (len(ts_df_gemini_ts)-1) % sample_freq_gemini != 0 : # Ensure last point is included if not already
                             ts_sampled_data_str += f"\n...\n{ts_df_gemini_ts[[selected_index]].iloc[-1].to_string(header=False, float_format='%.3f')}"

                        ts_summary_gemini += ts_sampled_data_str
                        if len(ts_df_gemini_ts) > 0:
                             ts_summary_gemini += f"\nمقدار اولیه حدود {ts_df_gemini_ts[selected_index].iloc[0]:.3f} ({ts_df_gemini_ts.index[0].strftime('%Y-%m-%d')}) و نهایی حدود {ts_df_gemini_ts[selected_index].iloc[-1]:.3f} ({ts_df_gemini_ts.index[-1].strftime('%Y-%m-%d')})."
                             ts_summary_gemini += f"\n میانگین: {ts_df_gemini_ts[selected_index].mean():.3f}, کمترین: {ts_df_gemini_ts[selected_index].min():.3f} (در تاریخ {ts_df_gemini_ts[selected_index].idxmin().strftime('%Y-%m-%d')}), بیشترین: {ts_df_gemini_ts[selected_index].max():.3f} (در تاریخ {ts_df_gemini_ts[selected_index].idxmax().strftime('%Y-%m-%d')})."
                        else:
                             ts_summary_gemini += "\n داده‌ای در این بازه یافت نشد."
                        
                        prompt_ts_an = (
                            f"شما یک تحلیلگر داده‌های کشاورزی خبره هستید. {analysis_basis_str_gemini_tab3}\n"
                            f" بر اساس داده‌های سری زمانی زیر برای شاخص {index_options[selected_index]} مزرعه '{active_farm_name_display}' طی بازه {ts_start_date_gemini_ts} تا {ts_end_date_gemini_ts}:\n{ts_summary_gemini}\n"
                            f"اطلاعات تکمیلی مزرعه (در صورت موجود بودن): {farm_details_for_gemini_tab3}\n"
                            f"وظایف تحلیلگر:\n"
                            f"۱. روند کلی تغییرات شاخص را توصیف کنید (مثلاً صعودی، نزولی، نوسانی، ثابت) در کل بازه و زیربازه‌های مهم.\n"
                            f"۲. آیا دوره‌های خاصی از رشد قابل توجه، کاهش شدید یا ثبات طولانی مدت مشاهده می‌شود؟ اگر بله، به تاریخ‌های تقریبی اشاره کنید و شدت تغییرات را توصیف کنید.\n"
                            f"۳. با توجه به ماهیت شاخص '{selected_index}' ({'مقدار بالاتر بهتر است (مثلاً نشان‌دهنده رشد یا سلامت بیشتر)' if selected_index not in ['MSI'] else 'مقدار بالاتر بدتر است (نشان‌دهنده تنش بیشتر یا رطوبت کمتر)'}) و روند مشاهده شده، چه تفسیرهای اولیه‌ای در مورد سلامت و وضعیت گیاه در طول این دوره می‌توان داشت؟ (مثلاً آیا در زمان‌های خاصی تنش وجود داشته است؟ آیا رشد طبیعی بوده است؟)\n"
                            f"۴. چه نوع مشاهدات میدانی یا اطلاعات تکمیلی (مثل تاریخ کاشت/برداشت، سابقه آبیاری، گزارش آفات/بیماری‌ها، سوابق آب و هوا) می‌تواند به درک بهتر این روند و تأیید تحلیل شما کمک کند؟\n"
                            f"پاسخ به فارسی، ساختاریافته (با استفاده از لیست‌ها)، تحلیلی و کاربردی باشد. از ارائه اعداد دقیق زیاد در متن گزارش خودداری کنید و بیشتر روی روندها و تفسیرها تمرکز کنید."
                        )
                        with st.spinner(f"⏳ در حال تحلیل روند زمانی {selected_index} با Gemini..."):
                            response_ts_an = ask_gemini(prompt_ts_an, temperature=0.5)
                            st.markdown(f"<div class='gemini-response-analysis'>{response_ts_an}</div>", unsafe_allow_html=True)
                    else:
                        st.info(f"داده‌ای برای تحلیل سری زمانی {selected_index} برای '{active_farm_name_display}' در بازه انتخاب شده یافت نشد. ممکن است تصویر مناسبی موجود نباشد.")
            else:
                 st.info("تحلیل روند زمانی فقط برای یک مزرعه منفرد با مختصات مشخص (پلی‌گون) قابل انجام است.")

        with st.expander("🗣️ پرسش و پاسخ عمومی", expanded=False):
            st.markdown("##### سوالات عمومی خود را در مورد مفاهیم کشاورزی، شاخص‌های سنجش از دور، نیشکر یا عملکرد این سامانه بپرسید.")
            user_general_q_gemini = st.text_area(
                "سوال عمومی شما:", 
                key="gemini_general_q_text_tab3", 
                height=100
            )
            if st.button("❓ پرسیدن سوال عمومی از Gemini", key="btn_gemini_general_q_send_tab3"):
                if not user_general_q_gemini.strip():
                    st.warning("لطفاً سوال عمومی خود را وارد کنید.")
                else:
                    prompt_gen_q = f"شما یک دستیار هوشمند و آگاه در زمینه کشاورزی، سنجش از دور، و به طور خاص کشت نیشکر هستید. به سوال عمومی زیر از کاربر به زبان فارسی پاسخ دهید:\n\n'{user_general_q_gemini}'\n\nپاسخ باید آموزنده، دقیق و در حد امکان جامع باشد. اگر سوال در مورد عملکرد این سامانه است، توضیح دهید که این سامانه برای پایش مزارع نیشکر با استفاده از تصاویر ماهواره‌ای و شاخص‌های گیاهی طراحی شده است."
                    with st.spinner("⏳ در حال جستجو برای پاسخ با Gemini..."):
                        response_gen_q = ask_gemini(prompt_gen_q, temperature=0.4)
                        st.markdown(f"<div class='gemini-response-default'>{response_gen_q}</div>", unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True) # End of section-container for tab3