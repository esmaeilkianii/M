import streamlit as st

def apply_custom_styles():
    """
    Apply custom CSS styles to the application
    """
    # Set default theme if not already set
    if 'selected_theme_name' not in st.session_state:
        st.session_state.selected_theme_name = "پیش‌فرض (آبی تیره)"
    
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
    
    # Get current theme colors
    current_theme_colors = THEMES[st.session_state.selected_theme_name]
    
    # Generate CSS variables from theme
    css_vars = "\n".join([f"{var}: {val};" for var, val in current_theme_colors.items()])
    
    # Apply custom CSS
    st.markdown(f"""
    <style>
        /* Apply theme variables */
        :root {{
            {css_vars}
        }}
        
        /* Right-to-left (RTL) Support */
        .stApp {{
            direction: rtl;
            text-align: right;
        }}
        
        /* Headers */
        h1, h2, h3, h4, h5, h6 {{
            color: var(--header-text-color);
            font-family: 'Vazirmatn', 'Arial', sans-serif !important;
        }}
        
        /* General text */
        p, div, span, label {{
            color: var(--text-color);
            font-family: 'Vazirmatn', 'Arial', sans-serif !important;
        }}
        
        /* Containers */
        .stApp {{
            background-color: var(--background-color);
        }}
        
        .block-container, div.stBlock {{
            background-color: var(--container-background-color);
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }}
        
        /* Metrics */
        [data-testid="stMetric"] {{
            background-color: var(--container-background-color);
            border-radius: 10px;
            padding: 1rem;
            border-left: 4px solid var(--metric-border-accent);
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        }}
        
        /* Buttons */
        .stButton > button {{
            background-color: var(--button-bg-color) !important;
            color: white !important;
            border: none !important;
            border-radius: 6px !important;
            padding: 0.5rem 1rem !important;
            transition: all 0.3s ease !important;
        }}
        
        .stButton > button:hover {{
            background-color: var(--button-hover-bg-color) !important;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }}
        
        /* Tables */
        .stDataFrame {{
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        }}
        
        .dataframe thead tr th {{
            background-color: var(--table-header-bg) !important;
            color: white !important;
            font-weight: 600 !important;
        }}
        
        /* Alerts and Info boxes */
        .stAlert {{
            border-radius: 8px !important;
            border-width: 1px !important;
        }}
        
        [data-baseweb="notification"] {{
            border-radius: 8px !important;
        }}
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 1px;
            background-color: #f0f2f6;
            border-radius: 10px;
            padding: 5px;
        }}
        
        .stTabs [data-baseweb="tab"] {{
            height: 50px;
            white-space: pre-wrap;
            border-radius: 6px;
            margin-left: 5px;
            margin-right: 5px; 
            transition: all 0.3s ease;
        }}

        .stTabs [aria-selected="true"] {{
            background-color: var(--tab-active-bg) !important;
            color: var(--tab-active-text) !important;
            font-weight: 600;
        }}
        
        /* Text areas and inputs */
        .stTextArea textarea, .stTextInput input, .stSelectbox, .stMultiselect {{
            border-radius: 6px !important;
            border: 1px solid #dee2e6 !important;
            padding: 0.5rem !important;
        }}
        
        /* Animations */
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .stBlock, .stDataFrame, .stMetric, .stText, .stAlert, [data-testid="stExpander"] {{
            animation: fadeIn 0.5s ease-out;
        }}
    </style>
    
    <!-- Add Vazirmatn font for Persian language support -->
    <link href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css" rel="stylesheet" type="text/css" />
    """, unsafe_allow_html=True) 