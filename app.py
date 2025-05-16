import streamlit as st

# --- Theme Selection Logic ---
# MUST BE VERY EARLY, ideally after imports and before page_config
if 'selected_theme_name' not in st.session_state:
    st.session_state.selected_theme_name = "پیش‌فرض (آبی تیره)" # Default theme

# Define theme colors (CSS variables)
# Each theme will override these variables
THEMES = {
    "پیش‌فرض (آبی تیره)": {
        "--primary-color": "#1a535c",       # Dark Teal
        "--secondary-color": "#4ecdc4",     # Light Teal
        "--accent-color": "#e76f51",        # Coral
        "--background-color": "#f0f2f6",    # Light Grey Page BG
        "--container-background-color": "#ffffff", # White Container BG
        "--text-color": "#212529",          # Dark Text
        "--header-text-color": "#1a535c",
        "--button-bg-color": "#264653",
        "--button-hover-bg-color": "#2a9d8f",
        "--metric-border-accent": "#4ecdc4",
        "--table-header-bg": "#2a9d8f",
        "--tab-active-bg": "#4ecdc4",
        "--tab-active-text": "white",
        "--info-bg": "#e6f7ff", # Light blue for info boxes
        "--info-border": "#007bff",
        "--warning-bg": "#fff3cd", # Light yellow for warning
        "--warning-border": "#ffc107",
        "--success-bg": "#f0fff0", # Light green for success
        "--success-border": "#28a745",
    },
    "تم سبز (طبیعت)": {
        "--primary-color": "#2d6a4f",       # Dark Green
        "--secondary-color": "#74c69d",     # Medium Green
        "--accent-color": "#fca311",        # Orange accent
        "--background-color": "#f4f9f4",
        "--container-background-color": "#ffffff",
        "--text-color": "#1b4332",
        "--header-text-color": "#2d6a4f",
        "--button-bg-color": "#40916c",
        "--button-hover-bg-color": "#52b788",
        "--metric-border-accent": "#74c69d",
        "--table-header-bg": "#40916c",
        "--tab-active-bg": "#74c69d",
        "--tab-active-text": "white",
        "--info-bg": "#e6fff0",
        "--info-border": "#2d6a4f",
        "--warning-bg": "#fff9e6",
        "--warning-border": "#fca311",
        "--success-bg": "#e6fff0",
        "--success-border": "#2d6a4f",
    },
    "تم قرمز (هشدار)": {
        "--primary-color": "#9d0208",       # Dark Red
        "--secondary-color": "#dc2f02",     # Medium Red
        "--accent-color": "#ffba08",        # Yellow accent
        "--background-color": "#fff5f5",
        "--container-background-color": "#ffffff",
        "--text-color": "#370617",
        "--header-text-color": "#9d0208",
        "--button-bg-color": "#ae2012",
        "--button-hover-bg-color": "#dc2f02",
        "--metric-border-accent": "#dc2f02",
        "--table-header-bg": "#ae2012",
        "--tab-active-bg": "#dc2f02",
        "--tab-active-text": "white",
        "--info-bg": "#ffeeee",
        "--info-border": "#9d0208",
        "--warning-bg": "#fff0e6",
        "--warning-border": "#ffba08",
        "--success-bg": "#eeffee", # Less prominent success
        "--success-border": "#555",
    },
    "تم زرد/نارنجی (گرم)": {
        "--primary-color": "#e76f51",       # Coral (Primary)
        "--secondary-color": "#f4a261",     # Sandy Brown
        "--accent-color": "#2a9d8f",        # Teal Accent
        "--background-color": "#fff8f0",
        "--container-background-color": "#ffffff",
        "--text-color": "#854d0e", # Brown text
        "--header-text-color": "#d95f02", # Dark Orange
        "--button-bg-color": "#e76f51",
        "--button-hover-bg-color": "#f4a261",
        "--metric-border-accent": "#f4a261",
        "--table-header-bg": "#e76f51",
        "--tab-active-bg": "#f4a261",
        "--tab-active-text": "white",
        "--info-bg": "#fff8e1",
        "--info-border": "#e76f51",
        "--warning-bg": "#fff3cd",
        "--warning-border": "#f4a261",
        "--success-bg": "#f0fff0",
        "--success-border": "#2a9d8f",
    },
     "تم قهوه‌ای (خاکی)": {
        "--primary-color": "#544741",      # Dark Brown
        "--secondary-color": "#8a786f",    # Medium Brown
        "--accent-color": "#c6ac8f",       # Light Tan/Beige
        "--background-color": "#f5f2ef",
        "--container-background-color": "#ffffff",
        "--text-color": "#3d2c25",
        "--header-text-color": "#544741",
        "--button-bg-color": "#6f5f55",
        "--button-hover-bg-color": "#8a786f",
        "--metric-border-accent": "#8a786f",
        "--table-header-bg": "#6f5f55",
        "--tab-active-bg": "#8a786f",
        "--tab-active-text": "white",
        "--info-bg": "#f9f6f3",
        "--info-border": "#544741",
        "--warning-bg": "#fef7eT",
        "--warning-border": "#c6ac8f",
        "--success-bg": "#f3f9f3",
        "--success-border": "#777",
    },
    "تم روشن (ساده)": {
        "--primary-color": "#4A5568",      # Cool Gray
        "--secondary-color": "#718096",    # Medium Gray
        "--accent-color": "#3182CE",       # Blue Accent
        "--background-color": "#F7FAFC",
        "--container-background-color": "#FFFFFF",
        "--text-color": "#2D3748",
        "--header-text-color": "#2D3748",
        "--button-bg-color": "#4A5568",
        "--button-hover-bg-color": "#2D3748",
        "--metric-border-accent": "#718096",
        "--table-header-bg": "#E2E8F0",
        "--tab-active-bg": "#4A5568",
        "--tab-active-text": "white",
        "--info-bg": "#EBF8FF",
        "--info-border": "#3182CE",
        "--warning-bg": "#FFFBEB",
        "--warning-border": "#ECC94B",
        "--success-bg": "#F0FFF4",
        "--success-border": "#48BB78",
    }
}
current_theme_colors = THEMES[st.session_state.selected_theme_name]


# --- Page Config ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide"
)

# Load Font Awesome for better icons
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    /* Loading Animation */
    .loading-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100vh;
        width: 100%;
        position: fixed;
        top: 0;
        left: 0;
        background-color: var(--background-color);
        z-index: 9999;
        transition: opacity 0.5s;
    }
    .loading-spinner {
        width: 80px;
        height: 80px;
        border: 8px solid rgba(0, 0, 0, 0.1);
        border-radius: 50%;
        border-top-color: var(--accent-color);
        animation: spin 1s ease-in-out infinite;
    }
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    .loading-text {
        position: absolute;
        margin-top: 120px;
        font-weight: 600;
        color: var(--primary-color);
    }
    /* Animation to fade out loader */
    @keyframes fadeOut {
        from { opacity: 1; }
        to { opacity: 0; visibility: hidden; }
    }

    /* Animations optimization to improve performance */
    .section-container:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 15px rgba(0,0,0,0.08);
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.12);
    }

    /* Reduce shadows for better performance */
    .ai-dashboard-card, .ai-insight-card, .gemini-response-default,
    .gemini-response-report, .gemini-response-analysis {
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    }

    /* Optimize animations with GPU acceleration */
    .section-container, .ai-dashboard-card, .ai-insight-card, .gemini-response-default,
    .gemini-response-report, .gemini-response-analysis, .stButton > button {
        will-change: transform;
        transform: translateZ(0);
    }

    /* Simplify hover animations */
    .ai-dashboard-card:hover, .ai-insight-card:hover, 
    .gemini-response-default:hover, .gemini-response-report:hover, 
    .gemini-response-analysis:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 10px rgba(0,0,0,0.08);
    }

    /* Remove ripple animation for better performance */
    .stButton > button::after {
        animation: none;
    }

    /* Optimize icon animations */
    .icon-pulse {
        animation: pulse 3s ease-in-out infinite;
    }

    .icon-rotate {
        animation: rotate 5s linear infinite;
    }

    /* Optimize decorative elements */
    .gradient-decor {
        opacity: 0.05;
    }
</style>

<script>
    document.addEventListener('DOMContentLoaded', () => {
        const loader = document.getElementById('app-loader');
        if (loader) {
            setTimeout(() => {
                loader.style.animation = 'fadeOut 0.5s forwards';
            }, 1500);
        }
    });
</script>

<div id="app-loader" class="loading-container">
    <div class="loading-spinner"></div>
    <div class="loading-text">در حال بارگذاری سامانه پایش نیشکر...</div>
</div>
""", unsafe_allow_html=True)

# --- Imports --- (Keep after page_config if they don't cause issues)
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


# --- Apply Dynamic CSS based on selected theme ---
# This CSS block will use the variables defined in current_theme_colors
st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700&display=swap');
        
        :root {{
            {"; ".join([f"{key}: {value}" for key, value in current_theme_colors.items()])};
        }}

        body {{
            font-family: 'Vazirmatn', sans-serif;
            background-color: var(--background-color);
            color: var(--text-color);
            background-image: linear-gradient(to bottom right, color-mix(in srgb, var(--background-color) 98%, var(--primary-color) 2%), var(--background-color));
            background-attachment: fixed;
        }}
        
        /* Main container - not directly targetable, use for .main if Streamlit uses it */
        .main {{
            font-family: 'Vazirmatn', sans-serif;
            background-color: var(--background-color);
        }}
        
        /* Headers */
        h1, h2, h3 {{
            font-family: 'Vazirmatn', sans-serif;
            text-align: right;
            font-weight: 600;
        }}
        h1 {{
            color: var(--header-text-color);
            border-bottom: 2px solid var(--secondary-color);
            padding-bottom: 0.3em;
            margin-bottom: 0.7em;
        }}
        h2 {{
            color: var(--primary-color);
        }}
        h3 {{
            color: var(--accent-color);
            font-weight: 500;
        }}
        
        /* Metrics - Enhanced Styling */
        .stMetric {{
            font-family: 'Vazirmatn', sans-serif;
            background-color: var(--container-background-color);
            border: 1px solid #e0e0e0;
            border-left: 5px solid var(--metric-border-accent);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
        }}
        .stMetric:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 16px rgba(0,0,0,0.12);
        }}
        .stMetric > label {{
            font-weight: 500;
            color: var(--primary-color);
        }}
        .stMetric > div[data-testid="stMetricValue"] {{
            font-size: 2em;
            font-weight: 600;
            color: var(--text-color);
        }}
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 5px;
            direction: rtl;
            border-bottom: 2px solid #e0e0e0;
        }}
        .stTabs [data-baseweb="tab"] {{
            height: 60px;
            padding: 14px 28px;
            background-color: #f8f9fa; /* Neutral non-active tab */
            border-radius: 12px 12px 0 0;
            font-family: 'Vazirmatn', sans-serif;
            font-weight: 600;
            color: var(--text-color);
            border: 1px solid #e0e0e0;
            border-bottom: none;
            transition: background-color 0.2s, color 0.2s, transform 0.2s;
        }}
        .stTabs [data-baseweb="tab"]:hover {{
            transform: translateY(-3px);
        }}
        .stTabs [data-baseweb="tab"][aria-selected="true"] {{
            background-color: var(--tab-active-bg);
            color: var(--tab-active-text);
            border-color: var(--tab-active-bg);
            transform: translateY(-5px);
        }}
        
        /* Tables */
        .dataframe-container table {{
            font-family: 'Vazirmatn', sans-serif;
            text-align: right;
            border-collapse: collapse;
            width: 100%;
            box-shadow: 0 4px 8px rgba(0,0,0,0.08);
            border-radius: 12px;
            overflow: hidden;
        }}
        .dataframe-container th {{
            background-color: var(--table-header-bg);
            color: white;
            padding: 14px 18px;
            font-weight: 600;
            text-align: right;
        }}
        .dataframe-container td {{
            padding: 12px 18px;
            border-bottom: 1px solid #e0e0e0;
            background-color: var(--container-background-color); /* Ensure TD matches container */
        }}
        .dataframe-container tr:nth-child(even) td {{
            background-color: color-mix(in srgb, var(--container-background-color) 90%, var(--background-color) 10%);
        }}
        .dataframe-container tr:hover td {{
            background-color: color-mix(in srgb, var(--container-background-color) 80%, var(--secondary-color) 20%);
        }}

        /* Sidebar */
        .css-1d391kg {{ /* Streamlit's default sidebar class */
            font-family: 'Vazirmatn', sans-serif;
            direction: rtl;
            background-color: var(--container-background-color);
            box-shadow: 2px 0 10px rgba(0,0,0,0.1);
            padding: 1.8rem;
            border-left: 1px solid #e0e0e0;
        }}
        .css-1d391kg .stSelectbox label, .css-1d391kg .stTextInput label, .css-1d391kg .stButton > button {{
            font-weight: 500;
            color: var(--text-color);
        }}
        
        /* Custom status badges */
        .status-badge {{ 
            padding: 6px 12px; 
            border-radius: 18px; 
            font-size: 0.85em; 
            font-weight: 500; 
            display: inline-block; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .status-badge:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 6px rgba(0,0,0,0.15);
        }}
        .status-positive {{ 
            background-color: #d1fae5; 
            color: #065f46; 
            border: 1px solid #6ee7b7; 
        }}
        .status-neutral {{ 
            background-color: #feF3c7; 
            color: #92400e; 
            border: 1px solid #fcd34d; 
        }}
        .status-negative {{ 
            background-color: #fee2e2; 
            color: #991b1b; 
            border: 1px solid #fca5a5; 
        }}

        /* Custom containers for better visual grouping */
        .section-container {{
            background-color: var(--container-background-color);
            padding: 1.8rem;
            border-radius: 16px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            margin-bottom: 2.5rem;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border: 1px solid rgba(0,0,0,0.05);
        }}
        
        .section-container:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 15px rgba(0,0,0,0.08);
        }}

        /* Styling for buttons */
        .stButton > button {{
            font-family: 'Vazirmatn', sans-serif;
            background-color: var(--button-bg-color);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 12px;
            font-weight: 500;
            letter-spacing: 0.5px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            position: relative;
            overflow: hidden;
        }}
        .stButton > button:hover {{
            background-color: var(--button-hover-bg-color);
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.12);
        }}
        .stButton > button:active {{
            background-color: color-mix(in srgb, var(--button-bg-color) 80%, black 20%);
            transform: translateY(0px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stButton > button::after {{
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 5px;
            height: 5px;
            background: rgba(255, 255, 255, 0.5);
            opacity: 0;
            border-radius: 100%;
            transform: scale(1, 1) translate(-50%);
            transform-origin: 50% 50%;
        }}
        .stButton > button:hover::after {{
            animation: ripple 1s ease-out;
        }}
        @keyframes ripple {{
            0% {{ transform: scale(0, 0); opacity: 0.5; }}
            100% {{ transform: scale(20, 20); opacity: 0; }}
        }}

        /* Input fields */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stDateInput input {{
            border-radius: 12px !important; /* Ensure high specificity */
            border: 1px solid #ced4da !important;
            background-color: var(--container-background-color) !important;
            color: var(--text-color) !important;
            padding: 12px !important;
            transition: all 0.3s ease !important;
        }}
        .stTextInput input:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within, .stDateInput input:focus {{
            border-color: var(--accent-color) !important;
            box-shadow: 0 0 0 0.25rem color-mix(in srgb, var(--accent-color) 30%, transparent 70%) !important;
            transform: translateY(-2px);
        }}
        /* Placeholder text color for inputs */
        .stTextInput input::placeholder {{ color: color-mix(in srgb, var(--text-color) 60%, transparent 40%); }}


        /* Markdown links */
        a {{ color: var(--accent-color); text-decoration: none; transition: all 0.2s ease; }}
        a:hover {{ text-decoration: underline; transform: translateY(-1px); }}

        /* Custom Gemini response box styles */
        .gemini-response-default {{ 
            background-color: var(--info-bg); 
            border-left: 5px solid var(--info-border); 
            padding: 18px; 
            border-radius: 12px; 
            margin-top:20px; 
            box-shadow: 0 2px 6px rgba(0,0,0,0.06);
            transition: all 0.3s ease;
        }}
        .gemini-response-default:hover {{
            box-shadow: 0 4px 10px rgba(0,0,0,0.08);
            transform: translateY(-2px);
        }}
        .gemini-response-report {{ 
            background-color: var(--success-bg); 
            border-left: 5px solid var(--success-border); 
            padding: 18px; 
            border-radius: 12px; 
            margin-top:20px; 
            box-shadow: 0 2px 6px rgba(0,0,0,0.06);
            transition: all 0.3s ease;
        }}
        .gemini-response-report:hover {{
            box-shadow: 0 4px 10px rgba(0,0,0,0.08);
            transform: translateY(-2px);
        }}
        .gemini-response-analysis {{ 
            background-color: var(--warning-bg); 
            border-left: 5px solid var(--warning-border); 
            padding: 18px; 
            border-radius: 12px; 
            margin-top:20px; 
            box-shadow: 0 2px 6px rgba(0,0,0,0.06);
            transition: all 0.3s ease;
        }}
        .gemini-response-analysis:hover {{
            box-shadow: 0 4px 10px rgba(0,0,0,0.08);
            transform: translateY(-2px);
        }}

        /* Custom AI Analysis Dashboard Styles */
        .ai-dashboard-card {{
            background-color: var(--container-background-color);
            border-radius: 16px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            padding: 20px;
            margin-bottom: 20px;
            transition: all 0.3s ease;
            border: 1px solid rgba(0,0,0,0.05);
            position: relative;
            overflow: hidden;
        }}
        .ai-dashboard-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.12);
        }}
        .ai-card-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 15px;
            border-bottom: 2px solid rgba(0,0,0,0.05);
            padding-bottom: 10px;
        }}
        .ai-card-title {{
            font-size: 1.2em;
            font-weight: 600;
            color: var(--primary-color);
            margin: 0;
            display: flex;
            align-items: center;
        }}
        .ai-card-icon {{
            margin-left: 8px;
            font-size: 1.5em;
            color: var(--accent-color);
        }}
        .ai-card-body {{
            padding: 10px 0;
        }}
        .ai-card-footer {{
            margin-top: 15px;
            font-size: 0.85em;
            color: color-mix(in srgb, var(--text-color) 70%, transparent 30%);
            border-top: 1px solid rgba(0,0,0,0.05);
            padding-top: 10px;
        }}
        
        /* AI Analysis Insight Cards */
        .ai-insight-card {{
            padding: 15px;
            background-color: color-mix(in srgb, var(--container-background-color) 98%, var(--accent-color) 2%);
            border-radius: 12px;
            margin-bottom: 15px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.06);
            transition: all 0.3s ease;
            border-left: 4px solid var(--accent-color);
        }}
        .ai-insight-card:hover {{
            box-shadow: 0 4px 10px rgba(0,0,0,0.08);
            transform: translateY(-2px);
        }}
        .ai-insight-header {{
            display: flex;
            align-items: center;
            margin-bottom: 10px;
            font-weight: 600;
            color: var(--primary-color);
        }}
        .ai-insight-icon {{
            margin-left: 8px;
            color: var(--accent-color);
            font-size: 1.2em;
        }}
        .ai-insight-content {{
            font-size: 0.95em;
            line-height: 1.5;
        }}
        
        /* Animated icons for AI components */
        .icon-pulse {{
            animation: pulse 3s ease-in-out infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(1); opacity: 1; }}
            50% {{ transform: scale(1.1); opacity: 0.8; }}
            100% {{ transform: scale(1); opacity: 1; }}
        }}
        
        .icon-rotate {{
            animation: rotate 5s linear infinite;
        }}
        @keyframes rotate {{
            from {{ transform: rotate(0deg); }}
            to {{ transform: rotate(360deg); }}
        }}
        
        /* Farm status indicators */
        .farm-status-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-left: 5px;
        }}
        .status-green {{ 
            background-color: #10b981; 
            box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
        }}
        .status-yellow {{ 
            background-color: #f59e0b; 
            box-shadow: 0 0 8px rgba(245, 158, 11, 0.6);
        }}
        .status-red {{ 
            background-color: #ef4444; 
            box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);
        }}
        
        /* Gradient decorations */
        .gradient-decor {{
            position: absolute;
            width: 150px;
            height: 150px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--secondary-color) 0%, transparent 70%);
            opacity: 0.05;
            z-index: 0;
        }}
        .decor-top-right {{
            top: -50px;
            right: -50px;
        }}
        .decor-bottom-left {{
            bottom: -50px;
            left: -50px;
        }}
        
        /* Font Awesome Integration */
        .fa {{
            font-family: "Font Awesome 5 Free";
            font-weight: 900;
        }}
    </style>
""", unsafe_allow_html=True)


# --- Configuration ---
APP_TITLE = "سامانه پایش هوشمند نیشکر"
APP_SUBTITLE = "مطالعات کاربردی شرکت کشت و صنعت دهخدا"
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 12

# --- File Paths (Relative to the script location in Hugging Face) ---
CSV_FILE_PATH = 'cleaned_output.csv'
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

# --- Load Farm Data ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data(csv_path=CSV_FILE_PATH):
    try:
        df = pd.read_csv(csv_path)
        required_cols = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته', 'coordinates_missing']
        if not all(col in df.columns for col in required_cols):
            st.error(f"❌ فایل CSV باید شامل ستون‌های ضروری باشد: {', '.join(required_cols)}")
            return None
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        df['coordinates_missing'] = df['coordinates_missing'].fillna(False).astype(bool)
        df = df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
        df = df[~df['coordinates_missing']]
        if df.empty:
            st.warning("⚠️ داده معتبری برای مزارع یافت نشد.")
            return None
        df['روزهای هفته'] = df['روزهای هفته'].astype(str).str.strip()
        st.success(f"✅ داده‌های {len(df)} مزرعه بارگذاری شد.")
        return df
    except FileNotFoundError:
        st.error(f"❌ فایل '{csv_path}' یافت نشد.")
        return None
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری CSV: {e}")
        return None

if initialize_gee():
    farm_data_df = load_farm_data()
else:
    st.error("❌ اتصال به GEE ناموفق بود.")
    st.stop()

if farm_data_df is None:
    st.error("❌ بارگذاری داده مزارع ناموفق بود.")
    st.stop()

# ==============================================================================
# Gemini API Configuration
# ==============================================================================
# !!! هشدار امنیتی: قرار دادن مستقیم API Key در کد ریسک بالایی دارد !!!
GEMINI_API_KEY = "AIzaSyDzirWUubBVyjF10_JZ8UVSd6c6nnTKpLw" # <<<<<<< جایگزین کنید >>>>>>>>

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
    st.markdown("""
    <div style="text-align:center; margin-bottom:20px;">
        <div style="font-weight:700; font-size:1.3em; color:var(--primary-color); margin-bottom:5px;">
            <i class="fas fa-seedling" style="margin-left:8px;"></i>سامانه پایش هوشمند نیشکر
        </div>
        <div style="font-size:0.9em; color:var(--text-color); opacity:0.8;">شرکت کشت و صنعت دهخدا</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="margin-bottom:20px;">
        <div style="display:flex; align-items:center; margin-bottom:10px;">
            <i class="fas fa-palette" style="color:var(--primary-color); margin-left:8px;"></i>
            <div style="font-weight:600; font-size:1.1em;">انتخاب تم</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    selected_theme_name_sidebar = st.selectbox(
        "تم رنگی برنامه را انتخاب کنید:",
        options=list(THEMES.keys()),
        index=list(THEMES.keys()).index(st.session_state.selected_theme_name),
        key="theme_selector_widget"
    )
    if selected_theme_name_sidebar != st.session_state.selected_theme_name:
        st.session_state.selected_theme_name = selected_theme_name_sidebar
        st.rerun() # Rerun to apply new theme CSS

    st.markdown("<hr style='margin:25px 0;'>", unsafe_allow_html=True)
    st.markdown("""
    <div style="margin-bottom:20px;">
        <div style="display:flex; align-items:center; margin-bottom:10px;">
            <i class="fas fa-cog" style="color:var(--primary-color); margin-left:8px;"></i>
            <div style="font-weight:600; font-size:1.1em;">تنظیمات نمایش</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if GEMINI_API_KEY == "AIzaSyDzirWUubBVyjF10_JZ8UVSd6c6nnTKpLw":
        st.warning("⚠️ کلید API جمینای خود را مستقیماً در کد برنامه (متغیر GEMINI_API_KEY) وارد کنید تا قابلیت‌های هوشمند فعال شوند.")
    elif not gemini_model:
         st.error("اتصال به Gemini ناموفق بود. کلید API را بررسی کنید.")
    else:
        st.success("✅ اتصال به Gemini برقرار است.")


    available_days = sorted(farm_data_df['روزهای هفته'].unique())
    
    st.markdown("""
    <div style="margin:15px 0 10px 0;">
        <div style="display:flex; align-items:center;">
            <i class="fas fa-calendar-alt" style="color:var(--accent-color); margin-left:8px;"></i>
            <div style="font-weight:600;">روز هفته</div>
        </div>
    <div class='gradient-decor decor-top-right'></div>
    <div class='gradient-decor decor-bottom-left'></div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class='ai-insight-card'>
        <div class='ai-insight-header'>
            <span class='ai-insight-icon'>⚠️</span>
            توجه
        </div>
        <div class='ai-insight-content'>
            پاسخ‌های Gemini بر اساس داده‌های موجود و الگوهای کلی تولید می‌شوند و نباید جایگزین نظر کارشناسان شوند.
        </div>
    </div>
    """, unsafe_allow_html=True)

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
        analysis_basis_str_gemini_tab3 = "تحلیل بر اساس نقطه مرکزی مزرعه از داده‌های CSV انجام می‌شود."
        if active_farm_name_display != "همه مزارع":
            farm_details_for_gemini_tab3 = f"مزرعه مورد نظر: '{active_farm_name_display}'.\n"
            if active_farm_area_ha_display: # This is from initial farm selection, should be okay
                farm_details_for_gemini_tab3 += f"مساحت ثبت شده در CSV: {active_farm_area_ha_display:,.2f} هکتار.\n"
            
            # Get Varete from filtered_farms_df (original source)
            if filtered_farms_df is not None and not filtered_farms_df.empty:
                 csv_farm_details_tab3_series = filtered_farms_df[filtered_farms_df['مزرعه'] == active_farm_name_display]
                 if not csv_farm_details_tab3_series.empty:
                     farm_details_for_gemini_tab3 += f"واریته (از CSV): {csv_farm_details_tab3_series.iloc[0].get('واریته', 'N/A')}.\n"
                     
        # Display analytics dashboard summary
        st.markdown("""
        <div class='ai-dashboard-card'>
            <div class='ai-card-header'>
                <h3 class='ai-card-title'>
                    <span class='ai-card-icon icon-pulse'>📊</span>
                    خلاصه وضعیت هوشمند
                </h3>
            </div>
            <div class='ai-card-body'>
        """, unsafe_allow_html=True)
        
        col1_dash, col2_dash, col3_dash, col4_dash = st.columns(4)
        with col1_dash: 
            st.markdown(f"""
            <div style="text-align:center;">
                <div style="font-size:2.2em; font-weight:bold; color:#10b981; margin-bottom:5px;">{count_positive_summary_tab3}</div>
                <div style="font-size:0.9em; color:var(--text-color);">🟢 بهبود/رشد</div>
            </div>
            """, unsafe_allow_html=True)
        with col2_dash: 
            st.markdown(f"""
            <div style="text-align:center;">
                <div style="font-size:2.2em; font-weight:bold; color:#f59e0b; margin-bottom:5px;">{count_neutral_summary_tab3}</div>
                <div style="font-size:0.9em; color:var(--text-color);">⚪ ثابت</div>
            </div>
            """, unsafe_allow_html=True)
        with col3_dash: 
            st.markdown(f"""
            <div style="text-align:center;">
                <div style="font-size:2.2em; font-weight:bold; color:#ef4444; margin-bottom:5px;">{count_negative_summary_tab3}</div>
                <div style="font-size:0.9em; color:var(--text-color);">🔴 تنش/کاهش</div>
            </div>
            """, unsafe_allow_html=True)
        with col4_dash: 
            st.markdown(f"""
            <div style="text-align:center;">
                <div style="font-size:2.2em; font-weight:bold; color:#9ca3af; margin-bottom:5px;">{count_nodata_summary_tab3}</div>
                <div style="font-size:0.9em; color:var(--text-color);">❔ بدون داده</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("""
            </div>
            <div class='ai-card-footer'>
                تحلیل بر اساس شاخص های منتخب از داده های دریافتی از سنجش از دور
            </div>
        </div>
        """, unsafe_allow_html=True)


        # --- 1. Intelligent Q&A ---
        st.markdown("""
        <div class='ai-dashboard-card'>
            <div class='ai-card-header'>
                <h3 class='ai-card-title'>
                    <span class='ai-card-icon'>💬</span>
                    پرسش و پاسخ هوشمند
                </h3>
            </div>
            <div class='ai-card-body'>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="margin-bottom:15px;">
            سوال خود را در مورد وضعیت عمومی مزارع یا مزرعه <span style="color:var(--accent-color); font-weight:bold;">{active_farm_name_display}</span> بپرسید.
        </div>
        """, unsafe_allow_html=True)
        
        user_farm_q_gemini = st.text_area(
            f"سوال شما درباره '{active_farm_name_display}' یا مزارع روز '{selected_day}' (شاخص: {index_options[selected_index]}):", 
            key="gemini_farm_q_text_tab3", 
            height=100
        )
        if st.button("✉️ ارسال سوال به Gemini", key="btn_gemini_farm_q_send_tab3"):
            if not user_farm_q_gemini:
                st.info("لطفاً سوال خود را وارد کنید.")
            else:
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
                
                with st.spinner("⏳ در حال پردازش پاسخ با Gemini..."):
                    response_gemini_q = ask_gemini(prompt_gemini_q)
                    st.markdown(f"<div class='gemini-response-default'>{response_gemini_q}</div>", unsafe_allow_html=True)
        
        st.markdown("""
            </div>
        </div>
        """, unsafe_allow_html=True)

        # --- 2. Automatic Weekly Report ---
        st.markdown("""
        <div class='ai-dashboard-card'>
            <div class='ai-card-header'>
                <h3 class='ai-card-title'>
                    <span class='ai-card-icon'>📄</span>
                    تولید گزارش خودکار هفتگی
                </h3>
            </div>
            <div class='ai-card-body'>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="margin-bottom:15px;">
            گزارش تحلیلی هفتگی برای مزرعه <span style="color:var(--accent-color); font-weight:bold;">{active_farm_name_display}</span> بر اساس شاخص <span style="color:var(--primary-color);">{index_options[selected_index]}</span>
        </div>
        """, unsafe_allow_html=True)
        
        if active_farm_name_display == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را از سایدبار برای تولید گزارش انتخاب کنید.")
        else:
            farm_data_for_report_gemini = pd.DataFrame()
            if not ranking_df_sorted_tab3.empty:
                farm_data_for_report_gemini = ranking_df_sorted_tab3[ranking_df_sorted_tab3['مزرعه'] == active_farm_name_display]

            if farm_data_for_report_gemini.empty:
                st.info(f"داده‌های رتبه‌بندی برای '{active_farm_name_display}' (شاخص: {selected_index}) جهت تولید گزارش موجود نیست.")
            elif st.button(f"📝 تولید گزارش برای '{active_farm_name_display}'", key="btn_gemini_report_gen_tab3"):
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
                with st.spinner(f"⏳ در حال تولید گزارش برای '{active_farm_name_display}'..."):
                    response_rep = ask_gemini(prompt_rep, temperature=0.6, top_p=0.9)
                    st.markdown(f"""
                    <div style="text-align:center; margin-bottom:15px;">
                        <h3 style="color:var(--accent-color);">گزارش هفتگی '{active_farm_name_display}'</h3>
                        <div style="font-size:0.9em; color:var(--text-color); margin-bottom:5px;">
                            <strong>تاریخ گزارش:</strong> {datetime.date.today().strftime('%Y-%m-%d')}
                        </div>
                        <div style="font-size:0.9em; color:var(--text-color); margin-bottom:10px;">
                            <strong>بازه زمانی:</strong> {start_date_current_str} الی {end_date_current_str}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"<div class='gemini-response-report'>{response_rep}</div>", unsafe_allow_html=True)
        
        st.markdown("""
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # --- 3. Prioritization Assistant (NEW) ---
        st.markdown("""
        <div class='ai-dashboard-card'>
            <div class='ai-card-header'>
                <h3 class='ai-card-title'>
                    <span class='ai-card-icon icon-pulse'>⚠️</span>
                    دستیار اولویت‌بندی مزارع بحرانی
                </h3>
            </div>
            <div class='ai-card-body'>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="margin-bottom:15px;">
            شناسایی مزارع نیازمند توجه فوری بر اساس شاخص <span style="color:var(--primary-color);">{index_options[selected_index]}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Create visual indicators of farm priorities
        if not ranking_df_sorted_tab3.empty:
            problematic_farms_df = ranking_df_sorted_tab3[
                ranking_df_sorted_tab3['وضعیت'].str.contains('تنش|کاهش', case=False, na=False)
            ]
            
            if not problematic_farms_df.empty:
                st.markdown("""
                <div style="background-color:rgba(239, 68, 68, 0.1); border-radius:10px; padding:15px; margin-bottom:15px;">
                    <div style="font-weight:bold; color:#991b1b; margin-bottom:10px; display:flex; align-items:center;">
                        <span style="margin-left:8px;">🔔</span> مزارع در وضعیت بحرانی
                    </div>
                """, unsafe_allow_html=True)
                
                # Display up to 3 critical farms with visual indicators
                sort_asc_for_change = selected_index not in ['MSI']
                critical_farms = problematic_farms_df.sort_values(by='تغییر', ascending=sort_asc_for_change).head(3)
                
                for idx, farm in critical_farms.iterrows():
                    farm_name = farm['مزرعه']
                    current_val = f"{farm[f'{selected_index} (هفته جاری)']:.3f}" if pd.notna(farm[f'{selected_index} (هفته جاری)']) else "N/A"
                    change_val = f"{farm['تغییر']:.3f}" if pd.notna(farm['تغییر']) else "N/A"
                    
                    st.markdown(f"""
                    <div style="border-bottom:1px solid rgba(239, 68, 68, 0.3); padding-bottom:8px; margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div style="font-weight:600;">
                                <span class="farm-status-indicator status-red"></span> {farm_name}
                            </div>
                            <div style="font-size:0.9em;">{current_val} ({change_val})</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("</div>", unsafe_allow_html=True)
        
        if count_negative_summary_tab3 == 0 and (not ranking_df_sorted_tab3.empty):
            st.markdown("""
            <div style="background-color:rgba(16, 185, 129, 0.1); border-radius:10px; padding:15px; margin-bottom:15px;">
                <div style="font-weight:bold; color:#065f46; margin-bottom:10px; display:flex; align-items:center;">
                    <span style="margin-left:8px;">✅</span> وضعیت مطلوب
                </div>
                <div>بر اساس شاخص انتخاب شده، هیچ مزرعه‌ای در وضعیت «تنش/کاهش» شناسایی نشد.</div>
            </div>
            """, unsafe_allow_html=True)
        elif ranking_df_sorted_tab3.empty:
             st.info(f"داده‌ای برای رتبه‌بندی و اولویت‌بندی مزارع بر اساس شاخص '{index_options[selected_index]}' یافت نشد.")
        elif st.button(f"🔍 تحلیل و اولویت‌بندی مزارع بحرانی", key="btn_gemini_priority_assist_tab3"):
            # Prepare data for the prompt: farms with negative status
            # Sort by 'تغییر' to get the most negative changes first for positive-is-good indices
            # For MSI (stress index, higher is worse), a positive change is bad.
            # The existing 'وضعیت' text captures this logic.
            
            problematic_farms_df = ranking_df_sorted_tab3[
                ranking_df_sorted_tab3['وضعیت'].str.contains('تنش|کاهش', case=False, na=False)
            ]
            # Sort by 'تغییر' column to highlight most significant changes for the prompt context
            # For NDVI, EVI, etc. (higher is better), a more negative 'تغییر' is worse.
            # For MSI (higher is worse), a more positive 'تغییر' is worse.
            # The 'ascending' parameter of sort_values handles this based on index nature.
            # However, 'تغییر' itself is just a difference. 'status_text' is more reliable for "bad".
            
            # Let's sort the problematic farms by the 'تغییر' to show Gemini the ones with biggest issues first.
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
            with st.spinner("⏳ در حال تحلیل اولویت‌بندی با Gemini..."):
                response_priority = ask_gemini(prompt_priority, temperature=0.5)
                st.markdown(f"<div class='gemini-response-analysis'>{response_priority}</div>", unsafe_allow_html=True)
        
        st.markdown("""
            </div>
        </div>
        """, unsafe_allow_html=True)

        # --- 4. Intelligent Timeseries Analysis ---
        st.markdown("""
        <div class='ai-dashboard-card'>
            <div class='ai-card-header'>
                <h3 class='ai-card-title'>
                    <span class='ai-card-icon icon-rotate'>📉</span>
                    تحلیل هوشمند روند زمانی
                </h3>
            </div>
            <div class='ai-card-body'>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="margin-bottom:15px;">
            تحلیل روند زمانی شاخص <span style="color:var(--primary-color);">{index_options[selected_index]}</span> 
            برای مزرعه <span style="color:var(--accent-color); font-weight:bold;">{active_farm_name_display}</span>
        </div>
        """, unsafe_allow_html=True)
        
        if active_farm_name_display == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را از سایدبار برای تحلیل سری زمانی انتخاب کنید.")
        elif active_farm_geom and active_farm_geom.type().getInfo() == 'Point':
            # Add a quick preview of time series chart trend
            ts_preview_date = today.strftime('%Y-%m-%d')
            ts_preview_start_date = (today - datetime.timedelta(days=90)).strftime('%Y-%m-%d')  # Last 3 months
            
            with st.spinner(f"⏳ در حال دریافت پیش‌نمایش روند..."):
                # This is using the cached function, so should be relatively quick
                ts_preview_df, ts_preview_error = get_index_time_series(
                    active_farm_geom, selected_index,
                    start_date_str=ts_preview_start_date, end_date_str=ts_preview_date
                )
                
                if not ts_preview_df.empty and not ts_preview_error:
                    # Create a simplified preview chart
                    preview_fig = px.line(ts_preview_df, y=selected_index, markers=True)
                    preview_fig.update_layout(
                        height=200, margin=dict(l=10, r=10, t=10, b=10),
                        showlegend=False,
                        font=dict(family="Vazirmatn", size=10, color="var(--text-color)"),
                        xaxis=dict(title=None, showticklabels=True, showgrid=False),
                        yaxis=dict(title=None, showticklabels=True, showgrid=False),
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)"
                    )
                    preview_fig.update_traces(
                        line=dict(color="var(--accent-color)", width=2), 
                        marker=dict(color="var(--primary-color)", size=4)
                    )
                    st.plotly_chart(preview_fig, use_container_width=True, config={'displayModeBar': False})
            
            if st.button(f"🔍 تحلیل روند زمانی {selected_index} برای '{active_farm_name_display}' با Gemini", key="btn_gemini_timeseries_an_tab3"):
                ts_end_date_gemini_ts = today.strftime('%Y-%m-%d')
                ts_start_date_gemini_ts = (today - datetime.timedelta(days=180)).strftime('%Y-%m-%d')  # 6 months
                
                with st.spinner(f"⏳ در حال دریافت داده‌های سری زمانی برای Gemini..."):
                    # get_index_time_series is cached
                    ts_df_gemini_ts, ts_error_gemini_ts = get_index_time_series(
                        active_farm_geom, selected_index,
                        start_date_str=ts_start_date_gemini_ts, end_date_str=ts_end_date_gemini_ts
                    )
                
                if ts_error_gemini_ts:
                    st.error(f"خطا در دریافت داده‌های سری زمانی برای Gemini: {ts_error_gemini_ts}")
                elif not ts_df_gemini_ts.empty:
                    ts_summary_gemini = f"داده‌های سری زمانی شاخص {index_options[selected_index]} برای '{active_farm_name_display}' در 6 ماه گذشته ({ts_start_date_gemini_ts} تا {ts_end_date_gemini_ts}):\n"
                    # Sample data for conciseness in prompt, but provide key stats
                    sample_freq_gemini = max(1, len(ts_df_gemini_ts) // 10)  # Max 10 samples + ends
                    ts_sampled_data_str = ts_df_gemini_ts.iloc[::sample_freq_gemini][selected_index].to_string(header=True, index=True)
                    if len(ts_df_gemini_ts) > 1:
                        ts_sampled_data_str += f"\n...\n{ts_df_gemini_ts[[selected_index]].iloc[-1].to_string(header=False)}"  # Ensure last point is included

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
                    with st.spinner(f"⏳ در حال تحلیل روند زمانی {selected_index} با Gemini..."):
                        response_ts_an = ask_gemini(prompt_ts_an, temperature=0.5)
                        st.markdown(f"<div class='gemini-response-analysis'>{response_ts_an}</div>", unsafe_allow_html=True)
                else:
                    st.info(f"داده‌ای برای تحلیل سری زمانی {selected_index} برای '{active_farm_name_display}' در 6 ماه گذشته یافت نشد.")
        else:  # Not a single farm or no geometry
            st.info("تحلیل روند زمانی فقط برای یک مزرعه منفرد با مختصات مشخص قابل انجام است.")
        
        st.markdown("""
            </div>
        </div>
        """, unsafe_allow_html=True)

        # --- 5. General Q&A ---
        st.markdown("""
        <div class='ai-dashboard-card'>
            <div class='ai-card-header'>
                <h3 class='ai-card-title'>
                    <span class='ai-card-icon'>🗣️</span>
                    پرسش و پاسخ عمومی
                </h3>
            </div>
            <div class='ai-card-body'>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="margin-bottom:15px;">
            سوالات عمومی خود را در مورد مفاهیم کشاورزی، شاخص‌های سنجش از دور، نیشکر یا عملکرد این سامانه بپرسید.
        </div>
        """, unsafe_allow_html=True)
        
        user_general_q_gemini = st.text_area(
            "سوال عمومی شما:", 
            key="gemini_general_q_text_tab3", 
            height=100
        )
        if st.button("❓ پرسیدن سوال عمومی از Gemini", key="btn_gemini_general_q_send_tab3"):
            if not user_general_q_gemini:
                st.info("لطفاً سوال خود را وارد کنید.")
            else:
                prompt_gen_q = (
                    f"شما یک دانشنامه هوشمند در زمینه کشاورزی (با تمرکز بر نیشکر) و سنجش از دور هستید. "
                    f"لطفاً به سوال زیر که توسط یک کاربر سامانه پایش نیشکر پرسیده شده است، به زبان فارسی پاسخ دهید. "
                    f"سعی کنید پاسخ شما ساده، قابل فهم، دقیق و در حد امکان جامع باشد.\n"
                    f"سوال کاربر: '{user_general_q_gemini}'"
                )
                with st.spinner("⏳ در حال جستجو برای پاسخ با Gemini..."):
                    response_gen_q = ask_gemini(prompt_gen_q, temperature=0.4)
                    st.markdown(f"<div class='gemini-response-default'>{response_gen_q}</div>", unsafe_allow_html=True)
        
        st.markdown("""
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)  # End of section-container for tab3

@st.cache_data(show_spinner="⏳ در حال پردازش تصاویر ماهواره‌ای...", persist=True, ttl=3600)
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