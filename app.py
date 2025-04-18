import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import datetime
import json
from datetime import timedelta
import plotly.express as px
import plotly.graph_objects as go
from streamlit_folium import folium_static

# Set page configuration
st.set_page_config(
    page_title="پایش مزارع نیشکر دهخدا",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add custom CSS for RTL support and styling
st.markdown("""
<style>
    body {
        direction: rtl;
    }
    .stApp {
        font-family: 'Vazir', sans-serif;
    }
    .css-18e3th9 {
        padding-top: 0rem;
        padding-bottom: 10rem;
        padding-left: 5rem;
        padding-right: 5rem;
    }
    .css-1d391kg {
        padding-top: 3.5rem;
        padding-right: 1rem;
        padding-bottom: 3.5rem;
        padding-left: 1rem;
    }
    .reportview-container .sidebar-content {
        direction: rtl;
    }
    .stMetricLabel {
        font-size: 18px;
        font-weight: bold;
    }
    div[data-testid="stMetricValue"] > div {
        font-size: 25px;
        font-weight: bold;
    }
    .css-1xarl3l {
        font-size: 1.25rem;
        padding-bottom: 0.5rem;
    }
    .main-header {
        font-size: 2.5em;
        font-weight: bold;
        text-align: center;
        color: #3c9a8a;
        margin-bottom: 10px;
    }
    .sub-header {
        font-size: 1.5em;
        text-align: center;
        color: #636363;
        margin-bottom: 20px;
    }
    .stats-box {
        background-color: #f1f1f1;
        border-radius: 5px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .stats-value {
        font-size: 2em;
        font-weight: bold;
        color: #3c9a8a;
    }
    .stats-label {
        font-size: 1em;
        color: #636363;
    }
    .styled-table {
        border-collapse: collapse;
        margin: 25px 0;
        font-size: 0.9em;
        font-family: sans-serif;
        width: 100%;
        box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
    }
    .styled-table thead tr {
        background-color: #3c9a8a;
        color: white;
        text-align: right;
    }
    .styled-table th,
    .styled-table td {
        padding: 12px 15px;
        text-align: right;
    }
    .styled-table tbody tr {
        border-bottom: 1px solid #dddddd;
    }
    .styled-table tbody tr:nth-of-type(even) {
        background-color: #f3f3f3;
    }
    .styled-table tbody tr:last-of-type {
        border-bottom: 2px solid #3c9a8a;
    }
</style>
""", unsafe_allow_html=True)

# Function to authenticate with Earth Engine
def ee_authenticate():
    try:
        # Check if service account key file exists
        service_account_key = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'
        if os.path.exists(service_account_key):
            credentials = ee.ServiceAccountCredentials(
                email=json.load(open(service_account_key))['dehkhodamap-e9f0da4ce9f6514021@ee-esmaeilkiani13877.iam.gserviceaccount.com'],
                key_file=service_account_key
            )
            ee.Initialize(credentials)
            st.sidebar.success("✓ اتصال به Google Earth Engine با موفقیت انجام شد")
            return True
        else:
            st.sidebar.error("⚠️ فایل کلید سرویس GEE یافت نشد")
            return False
    except Exception as e:
        st.sidebar.error(f"⚠️ خطا در اتصال به Google Earth Engine: {str(e)}")
        return False

# Load farm data
@st.cache_data
def load_data():
    try:
        df = pd.read_csv('output (1).csv')
        return df
    except Exception as e:
        st.error(f"خطا در بارگذاری فایل CSV: {str(e)}")
        return None

# Function to calculate indices
def calculate_indices(image, geometry, index_name):
    if index_name == 'NDVI':
        # NDVI = (NIR - Red) / (NIR + Red)
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        return ndvi
    
    elif index_name == 'EVI':
        # EVI = 2.5 * (NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1)
        evi = image.expression(
            '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)', {
                'NIR': image.select('B8'),
                'RED': image.select('B4'),
                'BLUE': image.select('B2')
            }
        ).rename('EVI')
        return evi
    
    elif index_name == 'NDMI':
        # NDMI = (NIR - SWIR) / (NIR + SWIR)
        ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
        return ndmi
    
    elif index_name == 'LAI':
        # LAI calculation using empirical model based on NDVI
        ndvi = image.normalizedDifference(['B8', 'B4'])
        lai = ndvi.expression(
            '3.618 * exp(2.718 * NDVI)', {
                'NDVI': ndvi
            }
        ).rename('LAI')
        return lai
    
    elif index_name == 'Biomass':
        # Biomass = a * LAI + b (calibrated coefficients)
        ndvi = image.normalizedDifference(['B8', 'B4'])
        lai = ndvi.expression(
            '3.618 * exp(2.718 * NDVI)', {
                'NDVI': ndvi
            }
        )
        biomass = lai.expression(
            '0.8 * LAI + 0.5', {
                'LAI': lai
            }
        ).rename('Biomass')
        return biomass
    
    elif index_name == 'MSI':
        # MSI = SWIR / NIR
        msi = image.expression(
            'SWIR / NIR', {
                'SWIR': image.select('B11'),
                'NIR': image.select('B8')
            }
        ).rename('MSI')
        return msi
    
    elif index_name == 'Chlorophyll':
        # Chlorophyll index (CI) = (NIR / Red Edge) - 1
        ci = image.expression(
            '(NIR / RE) - 1', {
                'NIR': image.select('B8'),
                'RE': image.select('B5')  # Red Edge for Sentinel-2
            }
        ).rename('Chlorophyll')
        return ci
    
    elif index_name == 'ET':
        # Simple ET approximation (this is a simplified approach, 
        # a more sophisticated ET model would require additional inputs)
        ndvi = image.normalizedDifference(['B8', 'B4'])
        et = ndvi.expression(
            'NDVI * 5', {  # Simple scaling of NDVI as proxy for ET
                'NDVI': ndvi
            }
        ).rename('ET')
        return et
    
    else:
        return None

# Function to get Sentinel-2 imagery
def get_sentinel_imagery(start_date, end_date, geometry):
    # Get Sentinel-2 collection
    s2 = ee.ImageCollection("COPERNICUS/S2_SR") \
        .filterDate(start_date, end_date) \
        .filterBounds(geometry) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
    
    if s2.size().getInfo() == 0:
        return None
    
    # Get the median to reduce cloud influence
    median = s2.median()
    return median

# Function to create a visualization layer for a specific index
def create_index_layer(image, index_name, geometry):
    # Define visualization parameters based on index type
    viz_params = {
        'NDVI': {'min': -0.2, 'max': 0.8, 'palette': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']},
        'EVI': {'min': -0.1, 'max': 0.7, 'palette': ['#a50026', '#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63']},
        'NDMI': {'min': -0.1, 'max': 0.5, 'palette': ['#d7191c', '#fdae61', '#ffffbf', '#abd9e9', '#2c7bb6']},
        'LAI': {'min': 0, 'max': 5, 'palette': ['#ffffcc', '#c2e699', '#78c679', '#31a354', '#006837']},
        'Biomass': {'min': 0, 'max': 10, 'palette': ['#ffffcc', '#d9f0a3', '#addd8e', '#78c679', '#41ab5d', '#238443', '#005a32']},
        'MSI': {'min': 0.4, 'max': 2, 'palette': ['#1a9850', '#66bd63', '#a6d96a', '#d9ef8b', '#fee08b', '#fdae61', '#f46d43', '#d73027']},
        'Chlorophyll': {'min': 0, 'max': 2, 'palette': ['#ffffe5', '#f7fcb9', '#d9f0a3', '#addd8e', '#78c679', '#41ab5d', '#238443', '#005a32']},
        'ET': {'min': 0, 'max': 4, 'palette': ['#ffffcc', '#a1dab4', '#41b6c4', '#2c7fb8', '#253494']}
    }
    
    # Calculate index
    index_image = calculate_indices(image, geometry, index_name)
    
    if index_image is None:
        return None
    
    # Create the layer
    layer = geemap.ee_tile_layer(
        index_image.clip(geometry), 
        viz_params[index_name], 
        f"{index_name} Index"
    )
    
    return layer

# Function to generate time series plot for a specific index
def generate_time_series_plot(point, index_name, start_date, end_date):
    try:
        # Convert point to ee.Geometry
        point_geom = ee.Geometry.Point([point[1], point[0]])  # [lon, lat]
        
        # Get Sentinel-2 collection
        s2 = ee.ImageCollection("COPERNICUS/S2_SR") \
            .filterDate(start_date, end_date) \
            .filterBounds(point_geom) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
        
        if s2.size().getInfo() == 0:
            return None
        
        # Map over the collection to compute the index for each image
        def add_index(image):
            date = image.date().format('YYYY-MM-dd')
            index_value = calculate_indices(image, point_geom, index_name) \
                .reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=point_geom,
                    scale=10
                ).get(index_name)
            
            return ee.Feature(None, {'date': date, 'index_value': index_value})
        
        # Compute index for each image in collection
        index_collection = s2.map(add_index)
        
        # Get the time series data
        time_series = index_collection.reduceColumns(
            reducer=ee.Reducer.toList(2),
            selectors=['date', 'index_value']
        ).get('list').getInfo()
        
        # Convert to dataframe
        if time_series:
            df = pd.DataFrame(time_series, columns=['date', 'value'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Create plotly figure
            fig = px.line(df, x='date', y='value', title=f"{index_name} Time Series")
            fig.update_layout(
                xaxis_title="Date",
                yaxis_title=index_name,
                xaxis={'dir': 'ltr'},
                autosize=True,
                height=400
            )
            
            return fig
        else:
            return None
            
    except Exception as e:
        st.error(f"Error generating time series: {str(e)}")
        return None

# Function to create farm health ranking table
def create_farm_health_table(farms_df, selected_index):
    try:
        # Create a copy of the dataframe
        df = farms_df.copy()
        
        # Define threshold values for health status classification
        health_thresholds = {
            'NDVI': {'excellent': 0.7, 'good': 0.5, 'fair': 0.3, 'poor': 0.1},
            'EVI': {'excellent': 0.6, 'good': 0.4, 'fair': 0.3, 'poor': 0.1},
            'NDMI': {'excellent': 0.4, 'good': 0.3, 'fair': 0.2, 'poor': 0.1},
            'LAI': {'excellent': 4.0, 'good': 3.0, 'fair': 2.0, 'poor': 1.0},
            'Biomass': {'excellent': 8.0, 'good': 6.0, 'fair': 4.0, 'poor': 2.0},
            'MSI': {'excellent': 0.6, 'good': 0.8, 'fair': 1.0, 'poor': 1.5},
            'Chlorophyll': {'excellent': 1.5, 'good': 1.2, 'fair': 0.8, 'poor': 0.4},
            'ET': {'excellent': 3.5, 'good': 2.5, 'fair': 1.5, 'poor': 0.8}
        }
        
        # Generate random index values for demonstration
        # In a real application, these would come from actual GEE calculations
        np.random.seed(42)  # For reproducible results
        if selected_index == 'MSI':
            # For MSI, lower is better
            values = np.random.uniform(0.4, 2.0, size=len(df))
        else:
            # For all other indices, higher is better
            min_val = 0
            max_val = health_thresholds[selected_index]['excellent'] * 1.2
            values = np.random.uniform(min_val, max_val, size=len(df))
        
        df[selected_index] = values
        
        # Classify health status
        def classify_health(value, index):
            if index == 'MSI':
                # For MSI, lower is better
                if value <= health_thresholds[index]['excellent']:
                    return 'عالی'
                elif value <= health_thresholds[index]['good']:
                    return 'خوب'
                elif value <= health_thresholds[index]['fair']:
                    return 'متوسط'
                elif value <= health_thresholds[index]['poor']:
                    return 'ضعیف'
                else:
                    return 'بحرانی'
            else:
                # For all other indices, higher is better
                if value >= health_thresholds[index]['excellent']:
                    return 'عالی'
                elif value >= health_thresholds[index]['good']:
                    return 'خوب'
                elif value >= health_thresholds[index]['fair']:
                    return 'متوسط'
                elif value >= health_thresholds[index]['poor']:
                    return 'ضعیف'
                else:
                    return 'بحرانی'
        
        df['وضعیت'] = df[selected_index].apply(lambda x: classify_health(x, selected_index))
        
        # Sort by index value (ascending or descending based on index type)
        if selected_index == 'MSI':
            # For MSI, lower is better
            df = df.sort_values(by=selected_index, ascending=True)
        else:
            # For all other indices, higher is better
            df = df.sort_values(by=selected_index, ascending=False)
        
        # Select columns for display
        display_df = df[['مزرعه', 'اداره', 'واریته', selected_index, 'وضعیت']].reset_index(drop=True)
        display_df.index = display_df.index + 1  # Start index from 1
        
        return display_df
    
    except Exception as e:
        st.error(f"Error creating health table: {str(e)}")
        return None

# Main application
def main():
    # Display header
    st.markdown('<div class="main-header">پایش مزارع نیشکر دهخدا</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">داشبورد تعاملی و هوشمند برای مانیتورینگ پیشرفته مزارع</div>', unsafe_allow_html=True)
    
    # Authenticate with Earth Engine
    ee_auth_success = ee_authenticate()
    
    if not ee_auth_success:
        st.warning("لطفا فایل کلید سرویس GEE را در مسیر پروژه قرار دهید.")
        return
    
    # Load farm data
    farms_data = load_data()
    
    if farms_data is None:
        st.warning("لطفا فایل CSV اطلاعات مزارع را در مسیر پروژه قرار دهید.")
        return
    
    # Sidebar
    st.sidebar.title("تنظیمات")
    
    # Date selection
    current_date = datetime.datetime.now()
    end_date = st.sidebar.date_input(
        "تاریخ پایان",
        value=current_date,
        key="end_date"
    )
    
    # Default to 30 days before end date
    start_date = st.sidebar.date_input(
        "تاریخ شروع",
        value=end_date - timedelta(days=30),
        key="start_date"
    )
    
    # Convert to string format for GEE
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    # Day of week filter
    weekdays = farms_data['روزهای هفته'].unique().tolist()
    selected_day = st.sidebar.selectbox(
        "فیلتر روز هفته",
        options=weekdays,
        index=0  # Default to first day
    )
    
    # Filter data based on selected day
    filtered_farms = farms_data[farms_data['روزهای هفته'] == selected_day]
    
    # Farm selection
    farm_names = filtered_farms['مزرعه'].unique().tolist()
    selected_farm = st.sidebar.selectbox(
        "انتخاب مزرعه",
        options=farm_names,
        index=0  # Default to first farm
    )
    
    # Get selected farm data
    farm_data = filtered_farms[filtered_farms['مزرعه'] == selected_farm].iloc[0]
    
    # Index selection
    index_options = ['NDVI', 'EVI', 'NDMI', 'LAI', 'Biomass', 'MSI', 'Chlorophyll', 'ET']
    selected_index = st.sidebar.selectbox(
        "انتخاب شاخص",
        options=index_options,
        index=0  # Default to NDVI
    )
    
    # Get farm coordinates
    farm_lat = farm_data['عرض جغرافیایی']
    farm_lon = farm_data['طول جغرافیایی']
    
    # Create a point geometry for the selected farm
    farm_point = [farm_lat, farm_lon]
    
    # Create a buffer around the farm point (500 meters)
    farm_buffer = ee.Geometry.Point([farm_lon, farm_lat]).buffer(500)
    
    # Main content area with tabs
    tab1, tab2, tab3 = st.tabs(["نقشه و شاخص‌ها", "تحلیل زمانی", "مقایسه مزارع"])
    
    with tab1:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Create map
            m = geemap.Map(
                center=[farm_lat, farm_lon],
                zoom=14,
                basemap='HYBRID'
            )
            
            # Get Sentinel-2 imagery
            sentinel_image = get_sentinel_imagery(start_date_str, end_date_str, farm_buffer)
            
            if sentinel_image is not None:
                # Create index layer
                index_layer = create_index_layer(sentinel_image, selected_index, farm_buffer)
                
                if index_layer is not None:
                    # Add index layer to map
                    m.add_layer(index_layer)
                    
                    # Add farm point
                    m.add_marker(location=[farm_lat, farm_lon], popup=farm_data['مزرعه'])
                    
                    # Add farm boundary (simplified as a circle for demonstration)
                    m.add_circle_markers(
                        locations=[[farm_lat, farm_lon]],
                        radius=10,
                        color='white',
                        fill_color='#3388ff'
                    )
                    
                    # Add scale bar and layers control
                    m.add_scale_bar()
                    
                    # Display map
                    folium_static(m)
                else:
                    st.warning("خطا در محاسبه شاخص. لطفاً شاخص دیگری را انتخاب کنید.")
            else:
                st.warning("داده‌های ماهواره‌ای برای بازه زمانی انتخاب شده در دسترس نیست.")
        
        with col2:
            # Display farm information
            st.subheader("اطلاعات مزرعه")
            
            farm_info = {
                "نام مزرعه": farm_data['مزرعه'],
                "اداره": farm_data['اداره'],
                "کانال": farm_data['کانال'],
                "مساحت داشت (هکتار)": farm_data['مساحت داشت'],
                "واریته": farm_data['واریته'],
                "سن مزرعه": farm_data['سن'],
                "مختصات": f"{farm_lat:.6f}, {farm_lon:.6f}"
            }
            
            for key, value in farm_info.items():
                st.write(f"**{key}:** {value}")
            
            # Display index information
            st.subheader(f"اطلاعات شاخص {selected_index}")
            
            # Index descriptions
            index_descriptions = {
                'NDVI': "شاخص تفاضل نرمال‌شده پوشش گیاهی که نشان‌دهنده سبزینگی و سلامت گیاه است.",
                'EVI': "شاخص پوشش گیاهی بهبود یافته که برای مناطق با پوشش گیاهی متراکم مناسب‌تر است.",
                'NDMI': "شاخص رطوبت تفاضلی نرمال‌شده که میزان رطوبت برگ و تنش آبی را نشان می‌دهد.",
                'LAI': "شاخص سطح برگ که نسبت سطح برگ به سطح زمین را نشان می‌دهد.",
                'Biomass': "شاخص توده زیستی که میزان ماده خشک گیاهی را تخمین می‌زند.",
                'MSI': "شاخص تنش رطوبتی که نشان‌دهنده سطح تنش آبی در گیاه است.",
                'Chlorophyll': "شاخص کلروفیل که میزان محتوای کلروفیل برگ را نشان می‌دهد.",
                'ET': "شاخص تبخیر و تعرق که میزان تبخیر آب از سطح خاک و تعرق گیاه را نشان می‌دهد."
            }
            
            st.write(index_descriptions[selected_index])
            
            # Generate random index statistics for demonstration
            # In a real application, these would come from actual GEE calculations
            np.random.seed(int(farm_data['مزرعه'].sum()))
            
            if selected_index == 'MSI':
                # For MSI, lower is better
                farm_index_value = np.random.uniform(0.5, 1.5)
                min_val, max_val = 0.5, 2.0
                optimal_range = "0.4 - 0.8"
                if farm_index_value < 0.8:
                    status = "خوب"
                    status_color = "#66bd63"
                elif farm_index_value < 1.2:
                    status = "متوسط"
                    status_color = "#fee08b"
                else:
                    status = "ضعیف"
                    status_color = "#d73027"
            else:
                # For all other indices, higher is better
                if selected_index == 'NDVI':
                    farm_index_value = np.random.uniform(0.3, 0.8)
                    min_val, max_val = 0, 1.0
                    optimal_range = "0.6 - 0.8"
                    if farm_index_value > 0.6:
                        status = "خوب"
                        status_color = "#66bd63"
                    elif farm_index_value > 0.4:
                        status = "متوسط"
                        status_color = "#fee08b"
                    else:
                        status = "ضعیف"
                        status_color = "#d73027"
                elif selected_index == 'LAI':
                    farm_index_value = np.random.uniform(1.5, 4.5)
                    min_val, max_val = 0, 6.0
                    optimal_range = "3.0 - 5.0"
                    if farm_index_value > 3.0:
                        status = "خوب"
                        status_color = "#66bd63"
                    elif farm_index_value > 2.0:
                        status = "متوسط"
                        status_color = "#fee08b"
                    else:
                        status = "ضعیف"
                        status_color = "#d73027"
                elif selected_index == 'Biomass':
                    farm_index_value = np.random.uniform(3.0, 9.0)
                    min_val, max_val = 0, 12.0
                    optimal_range = "6.0 - 10.0"
                    if farm_index_value > 6.0:
                        status = "خوب"
                        status_color = "#66bd63"
                    elif farm_index_value > 4.0:
                        status = "متوسط"
                        status_color = "#fee08b"
                    else:
                        status = "ضعیف"
                        status_color = "#d73027"
                else:
                    farm_index_value = np.random.uniform(0.2, 0.7)
                    min_val, max_val = 0, 1.0
                    optimal_range = "0.5 - 0.8"
                    if farm_index_value > 0.5:
                        status = "خوب"
                        status_color = "#66bd63"
                    elif farm_index_value > 0.3:
                        status = "متوسط"
                        status_color = "#fee08b"
                    else:
                        status = "ضعیف"
                        status_color = "#d73027"
            
            # Display index value with gauge
            st.write(f"**مقدار شاخص:** {farm_index_value:.2f}")
            st.write(f"**محدوده بهینه:** {optimal_range}")
            
            # Create gauge chart
            gauge_fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=farm_index_value,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': f"شاخص {selected_index}"},
                gauge={
                    'axis': {'range': [min_val, max_val]},
                    'bar': {'color': status_color},
                    'steps': [
                        {'range': [min_val, min_val + (max_val - min_val) * 0.33], 'color': "#d73027"},
                        {'range': [min_val + (max_val - min_val) * 0.33, min_val + (max_val - min_val) * 0.67], 'color': "#fee08b"},
                        {'range': [min_val + (max_val - min_val) * 0.67, max_val], 'color': "#66bd63"}
                    ]
                }
            ))
            
            gauge_fig.update_layout(
                height=250,
                margin=dict(l=30, r=30, t=50, b=30)
            )
            
            st.plotly_chart(gauge_fig, use_container_width=True)
            
            # Display status
            st.markdown(f"<div style='text-align: center; font-size: 1.2em;'>وضعیت: <span style='color: {status_color}; font-weight: bold;'>{status}</span></div>", unsafe_allow_html=True)
    
    with tab2:
        st.subheader("تحلیل زمانی شاخص‌ها")
        
        # Generate time series plot
        time_series_fig = generate_time_series_plot(farm_point, selected_index, start_date_str, end_date_str)
        
        if time_series_fig is not None:
            st.plotly_chart(time_series_fig, use_container_width=True)
            
            # Add interpretation
            st.subheader("تفسیر نمودار")
            
            interpretations = {
                'NDVI': "روند NDVI نشان‌دهنده تغییرات سبزینگی و فعالیت فتوسنتزی گیاه در طول زمان است. افزایش NDVI نشان‌دهنده رشد مناسب و کاهش آن می‌تواند نشانه تنش یا رسیدگی محصول باشد.",
                'EVI': "EVI نسبت به NDVI در پوشش گیاهی متراکم اشباع نمی‌شود و به تغییرات ساختار تاج پوشش حساس‌تر است. نوسانات EVI می‌تواند نشان‌دهنده تغییرات در ساختار برگ و تاج پوشش باشد.",
                'NDMI': "روند NDMI نشان‌دهنده تغییرات محتوای آب برگ است. کاهش NDMI می‌تواند نشانه تنش آبی باشد که نیاز به آبیاری را نشان می‌دهد.",
                'LAI': "شاخص سطح برگ (LAI) با توسعه تاج پوشش افزایش می‌یابد. کاهش ناگهانی LAI می‌تواند نشان‌دهنده ریزش برگ، آفت یا بیماری باشد.",
                'Biomass': "روند توده زیستی نشان‌دهنده تجمع ماده خشک گیاهی است. افزایش پیوسته نشان‌دهنده رشد مناسب و توقف یا کاهش آن می‌تواند نشانه مشکلات رشد باشد.",
                'MSI': "شاخص تنش رطوبتی (MSI) با افزایش تنش آبی افزایش می‌یابد. افزایش MSI نشان‌دهنده نیاز به آبیاری است.",
                'Chlorophyll': "روند شاخص کلروفیل نشان‌دهنده سلامت فیزیولوژیکی گیاه است. کاهش می‌تواند نشانه کمبود نیتروژن یا سایر تنش‌های تغذیه‌ای باشد.",
                'ET': "روند تبخیر و تعرق (ET) نشان‌دهنده مصرف آب گیاه است. کاهش ناگهانی ET می‌تواند نشانه تنش آبی یا بسته شدن روزنه‌ها در اثر تنش باشد."
            }
            
            st.write(interpretations[selected_index])
            
            # Historical comparison (random data for demonstration)
            st.subheader("مقایسه با سال‌های گذشته")
            
            # Generate random comparative data
            dates = pd.date_range(start=start_date, end=end_date)
            current_year_data = pd.Series(np.random.uniform(0.3, 0.8, len(dates)), index=dates)
            last_year_data = pd.Series(np.random.uniform(0.25, 0.75, len(dates)), index=dates)
            
            # Create comparison dataframe
            comp_df = pd.DataFrame({
                'امسال': current_year_data,
                'سال گذشته': last_year_data
            })
            
            # Create comparison plot
            comp_fig = px.line(comp_df, title=f"مقایسه {selected_index} با سال گذشته")
            comp_fig.update_layout(
                xaxis_title="تاریخ",
                yaxis_title=selected_index,
                xaxis={'dir': 'ltr'},
                autosize=True,
                height=350
            )
            
            st.plotly_chart(comp_fig, use_container_width=True)
            
            # Calculate stats
            current_mean = current_year_data.mean()
            last_mean = last_year_data.mean()
            percent_change = ((current_mean - last_mean) / last_mean) * 100
            
            # Display comparison stats
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "میانگین امسال",
                    f"{current_mean:.2f}",
                    f"{percent_change:.1f}%" if percent_change >= 0 else f"{percent_change:.1f}%"
                )
            
            with col2:
                st.metric(
                    "میانگین سال گذشته",
                    f"{last_mean:.2f}"
                )
            
            with col3:
                st.metric(
                    "تغییرات",
                    f"{percent_change:.1f}%",
                    f"{percent_change:.1f}%" if percent_change >= 0 else f"{percent_change:.1f}%",
                    delta_color="normal" if selected_index == "MSI" else "inverse" if selected_index == "MSI" else "normal"
                )
        
        else:
            st.warning("داده‌های کافی برای ایجاد نمودار زمانی وجود ندارد. لطفاً بازه زمانی دیگری را انتخاب کنید.")
    
    with tab3:
        st.subheader("مقایسه وضعیت مزارع")
        
        # Create health ranking table
        health_table = create_farm_health_table(filtered_farms, selected_index)
        
        if health_table is not None:
            # Create color-coded dataframe
            def color_status(val):
                if val == 'عالی':
                    return 'background-color: #1a9850; color: white'
                elif val == 'خوب':
                    return 'background-color: #66bd63; color: white'
                elif val == 'متوسط':
                    return 'background-color: #fee08b'
                elif val == 'ضعیف':
                    return 'background-color: #f46d43; color: white'
                else:  # بحرانی
                    return 'background-color: #d73027; color: white'
            
            # Apply styling
            styled_table = health_table.style.applymap(
                color_status, subset=['وضعیت']
            )
            
            # Display table
            st.dataframe(styled_table, use_container_width=True)
            
            # Create distribution chart
            status_counts = health_table['وضعیت'].value_counts()
            
            status_fig = px.pie(
                values=status_counts.values,
                names=status_counts.index,
                title="توزیع وضعیت مزارع",
                color=status_counts.index,
                color_discrete_map={
                    'عالی': '#1a9850',
                    'خوب': '#66bd63',
                    'متوسط': '#fee08b',
                    'ضعیف': '#f46d43',
                    'بحرانی': '#d73027'
                }
            )
            
            status_fig.update_layout(
                legend_title="وضعیت",
                height=350
            )
            
            st.plotly_chart(status_fig)
            
            # Add summary statistics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown(
                    f"""
                    <div class="stats-box">
                        <div class="stats-value">{len(health_table)}</div>
                        <div class="stats-label">تعداد کل مزارع</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            with col2:
                good_count = sum(status_counts[status] for status in ['عالی', 'خوب'] if status in status_counts)
                st.markdown(
                    f"""
                    <div class="stats-box">
                        <div class="stats-value">{good_count}</div>
                        <div class="stats-label">مزارع با وضعیت خوب</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            with col3:
                medium_count = status_counts.get('متوسط', 0)
                st.markdown(
                    f"""
                    <div class="stats-box">
                        <div class="stats-value">{medium_count}</div>
                        <div class="stats-label">مزارع با وضعیت متوسط</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            with col4:
                poor_count = sum(status_counts[status] for status in ['ضعیف', 'بحرانی'] if status in status_counts)
                st.markdown(
                    f"""
                    <div class="stats-box">
                        <div class="stats-value">{poor_count}</div>
                        <div class="stats-label">مزارع با وضعیت ضعیف</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            # Add download button
            csv = health_table.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="دانلود جدول به صورت CSV",
                data=csv,
                file_name=f"{selected_index}_farm_health_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        else:
            st.warning("خطا در ایجاد جدول رتبه‌بندی مزارع.")
    
    # Footer
    st.markdown("""
    ---
    <div style="text-align: center; color: gray; font-size: 0.8em;">
        داشبورد پایش مزارع نیشکر دهخدا | طراحی و توسعه: 2025
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()