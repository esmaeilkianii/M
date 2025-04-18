import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import json
from datetime import datetime, timedelta
import folium
from folium.plugins import Draw, Fullscreen
import base64
from io import BytesIO

# Set page configuration
st.set_page_config(
    page_title="داشبورد مانیتورینگ مزارع نیشکر دهخدا",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS to improve the Persian text display and RTL support
st.markdown("""
<style>
    @font-face {
        font-family: 'Vazir';
        src: url('https://cdn.jsdelivr.net/gh/rastikerdar/vazir-font@v30.1.0/dist/Vazir.woff2');
    }
    body {
        font-family: 'Vazir', sans-serif !important;
        direction: rtl;
    }
    .main .block-container {
        direction: rtl;
        text-align: right;
    }
    h1, h2, h3, h4, h5, h6, .sidebar .sidebar-content {
        direction: rtl;
        text-align: right;
    }
    .stButton button {
        width: 100%;
    }
    .stDataFrame {
        direction: rtl;
    }
    .stDateInput {
        direction: ltr;
    }
    div[data-testid="stMetricValue"] {
        direction: ltr;
    }
    .plot-container {
        direction: ltr;
    }
</style>
""", unsafe_allow_html=True)

# Function to authenticate with GEE service account
def authenticate_gee():
    try:
        service_account_key_file = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'
        
        if os.path.exists(service_account_key_file):
            with open(service_account_key_file, 'r') as f:
                service_account_info = json.load(f)
                
            service_account = service_account_info.get('dehkhodamap-e9f0da4ce9f6514021@ee-esmaeilkiani13877.iam.gserviceaccount.com')
            credentials = ee.ServiceAccountCredentials(service_account, service_account_key_file)
            ee.Initialize(credentials)
            st.sidebar.success("اتصال به Google Earth Engine با موفقیت انجام شد.")
            return True
        else:
            st.sidebar.error("فایل کلید سرویس اکانت یافت نشد.")
            return False
    except Exception as e:
        st.sidebar.error(f"خطا در اتصال به Google Earth Engine: {str(e)}")
        return False

# Load farm data from CSV
@st.cache_data
def load_farm_data():
    try:
        df = pd.read_csv('output (1).csv')
        return df
    except Exception as e:
        st.error(f"خطا در بارگذاری فایل CSV مزارع: {str(e)}")
        return pd.DataFrame()

# Calculate agricultural indices
def calculate_indices(image, geometry):
    # NDVI (Normalized Difference Vegetation Index)
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    
    # EVI (Enhanced Vegetation Index)
    evi = image.expression(
        '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
        {
            'NIR': image.select('B8'),
            'RED': image.select('B4'),
            'BLUE': image.select('B2')
        }
    ).rename('EVI')
    
    # NDMI (Normalized Difference Moisture Index)
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    
    # MSI (Moisture Stress Index)
    msi = image.select('B11').divide(image.select('B8')).rename('MSI')
    
    # LAI (Leaf Area Index) - Simplified model
    lai = image.expression(
        '3.618 * EVI - 0.118',
        {
            'EVI': evi
        }
    ).rename('LAI')
    
    # Biomass estimation based on LAI
    biomass = lai.multiply(0.5).add(0.2).rename('Biomass')
    
    # Chlorophyll index
    chlorophyll = image.expression(
        '(NIR / RE) - 1',
        {
            'NIR': image.select('B8'),
            'RE': image.select('B5')  # Red Edge
        }
    ).rename('Chlorophyll')
    
    # Add all indices to the image
    image_with_indices = image.addBands([ndvi, evi, ndmi, msi, lai, biomass, chlorophyll])
    
    return image_with_indices

# Get Sentinel-2 image collection for specific date range
def get_sentinel_imagery(geometry, start_date, end_date):
    # Get Sentinel-2 Surface Reflectance collection
    s2_collection = (ee.ImageCollection('COPERNICUS/S2_SR')
                    .filterDate(start_date, end_date)
                    .filterBounds(geometry)
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)))
    
    # If collection is empty, return None
    if s2_collection.size().getInfo() == 0:
        return None
    
    # Get the median image to reduce cloud interference
    median_image = s2_collection.median()
    
    return median_image

# Function to get ET (Evapotranspiration) data from MODIS
def get_et_data(geometry, start_date, end_date):
    et_collection = (ee.ImageCollection('MODIS/006/MOD16A2')
                    .filterDate(start_date, end_date)
                    .filterBounds(geometry))
    
    if et_collection.size().getInfo() == 0:
        return None
    
    # Get ET band and scale it
    et_image = et_collection.select('ET').median()
    # MODIS ET is in kg/m^2/8day, convert to mm/day
    et_image = et_image.multiply(0.1).rename('ET')
    
    return et_image

# Generate color palettes for different indices
def get_color_palette(index_name):
    palettes = {
        'NDVI': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850'],
        'EVI': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850'],
        'NDMI': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850'],
        'MSI': ['#1a9850', '#66bd63', '#a6d96a', '#d9ef8b', '#fee08b', '#fdae61', '#f46d43', '#d73027'],
        'LAI': ['#ffffcc', '#d9f0a3', '#addd8e', '#78c679', '#41ab5d', '#238443', '#006837', '#004529'],
        'Biomass': ['#ffffcc', '#d9f0a3', '#addd8e', '#78c679', '#41ab5d', '#238443', '#006837', '#004529'],
        'Chlorophyll': ['#ffffcc', '#d9f0a3', '#addd8e', '#78c679', '#41ab5d', '#238443', '#006837', '#004529'],
        'ET': ['#eff3ff', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b']
    }
    
    # Default to NDVI palette if index not found
    return palettes.get(index_name, palettes['NDVI'])

# Define value ranges for indices
def get_index_range(index_name):
    ranges = {
        'NDVI': (-0.2, 1.0),
        'EVI': (-0.2, 1.0),
        'NDMI': (-0.5, 0.5),
        'MSI': (0.4, 2.0),
        'LAI': (0, 7),
        'Biomass': (0, 5),
        'Chlorophyll': (0, 5),
        'ET': (0, 10)
    }
    
    return ranges.get(index_name, (-1, 1))

# Create map for specific index
def create_index_map(image, geometry, index_name):
    m = geemap.Map(
        zoom_control=True,
        plugin_Draw=True,
        plugin_LatLngPopup=True,
        locate_control=True,
        search_control=True
    )
    
    # Add a basemap
    m.add_basemap('HYBRID')
    
    # Center the map on the geometry
    center = geometry.centroid().coordinates().getInfo()
    m.setCenter(center[0], center[1], 14)
    
    # Add the index layer with appropriate styling
    palette = get_color_palette(index_name)
    vis_min, vis_max = get_index_range(index_name)
    
    # Visualization parameters
    vis_params = {
        'min': vis_min,
        'max': vis_max,
        'palette': palette,
        'opacity': 0.8
    }
    
    # Add the index layer to the map
    m.addLayer(image.select(index_name), vis_params, index_name)
    
    # Add the geometry outline
    empty = ee.Image().byte()
    outline = empty.paint(geometry=geometry, color=1, width=2)
    m.addLayer(outline, {'palette': 'red'}, 'Farm Boundary')
    
    # Add a legend
    m.add_colorbar(vis_params, label=index_name, orientation='vertical', layer_name=index_name)
    
    # Add fullscreen and additional controls
    Draw(show=True).add_to(m)
    Fullscreen().add_to(m)
    
    return m

# Function to plot time series for an index
def plot_time_series(start_date, end_date, geometry, index_name, farm_name):
    # Convert dates to ee.Date format
    ee_start = ee.Date(start_date)
    ee_end = ee.Date(end_date)
    
    # Get Sentinel-2 collection
    collection = (ee.ImageCollection('COPERNICUS/S2_SR')
                .filterDate(ee_start, ee_end)
                .filterBounds(geometry)
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)))
    
    # Map the function to calculate indices for each image
    def add_indices(image):
        return calculate_indices(image, geometry)
    
    collection_with_indices = collection.map(add_indices)
    
    # Define the chart
    chart = geemap.chart.Image.series(
        collection_with_indices.select(index_name),
        geometry,
        {
            'title': f'روند زمانی {index_name} برای مزرعه {farm_name}',
            'pointSize': 3,
            'lineWidth': 2,
            'curveType': 'function',
            'colors': ['green'],
            'vAxis': {'title': index_name},
            'hAxis': {'title': 'تاریخ', 'format': 'MMM yyyy'}
        }
    )
    
    # Convert Earth Engine chart to Matplotlib figure
    chart_data = chart.getInfo()
    
    if 'rows' not in chart_data or not chart_data['rows']:
        return None
    
    dates = []
    values = []
    
    for row in chart_data['rows']:
        if 'c' in row and len(row['c']) >= 2:
            if row['c'][0] and 'v' in row['c'][0] and row['c'][0]['v'] is not None:
                date_val = row['c'][0]['v'] / 1000  # Convert milliseconds to seconds
                dates.append(datetime.fromtimestamp(date_val))
            
            if row['c'][1] and 'v' in row['c'][1] and row['c'][1]['v'] is not None:
                values.append(row['c'][1]['v'])
    
    if not dates or not values or len(dates) != len(values):
        return None
    
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, values, 'o-', color='green', markersize=4)
    ax.set_title(f'روند زمانی {index_name} برای مزرعه {farm_name}')
    ax.set_xlabel('تاریخ')
    ax.set_ylabel(index_name)
    ax.grid(True, linestyle='--', alpha=0.7)
    fig.autofmt_xdate()
    
    return fig

# Function to create a ranking table based on index values
def create_ranking_table(farms_data, selected_index):
    # Create an empty dataframe to store results
    results = []
    
    for _, farm in farms_data.iterrows():
        # Create ee.Geometry for each farm
        try:
            # Parse coordinates
            farm_coords = farm['coordinates']
            if isinstance(farm_coords, str) and farm_coords.strip():
                # Convert string coordinates to ee.Geometry
                coords_parts = farm_coords.replace('[', '').replace(']', '').split(',')
                lon = float(coords_parts[0])
                lat = float(coords_parts[1])
                farm_geom = ee.Geometry.Point(lon, lat).buffer(100)  # 100m buffer around the point
                
                # Get recent image (last 14 days)
                now = datetime.now()
                end_date = now.strftime('%Y-%m-%d')
                start_date = (now - timedelta(days=14)).strftime('%Y-%m-%d')
                
                image = get_sentinel_imagery(farm_geom, start_date, end_date)
                
                if image is not None:
                    # Calculate indices
                    image_with_indices = calculate_indices(image, farm_geom)
                    
                    # Get the mean value of the selected index
                    mean_value = image_with_indices.select(selected_index).reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=farm_geom,
                        scale=10
                    ).get(selected_index).getInfo()
                    
                    # Add to results
                    results.append({
                        'نام مزرعه': farm['مزرعه'],
                        'شاخص': mean_value,
                        'واریته': farm['واریته'] if 'واریته' in farm else '-',
                        'سن': farm['سن'] if 'سن' in farm else '-',
                        'مساحت': farm['مساحت داشت'] if 'مساحت داشت' in farm else '-'
                    })
        except Exception as e:
            st.warning(f"خطا در پردازش مزرعه {farm['مزرعه']}: {str(e)}")
            continue
    
    # Create dataframe and sort by index value
    if results:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values(by='شاخص', ascending=False)
        return df_results
    else:
        return pd.DataFrame()

# Function to get appropriate status based on index value
def get_status(index_name, value):
    status_ranges = {
        'NDVI': [(0.7, 1.0, 'عالی'), (0.5, 0.7, 'خوب'), (0.3, 0.5, 'متوسط'), (-1, 0.3, 'ضعیف')],
        'EVI': [(0.6, 1.0, 'عالی'), (0.4, 0.6, 'خوب'), (0.2, 0.4, 'متوسط'), (-1, 0.2, 'ضعیف')],
        'NDMI': [(0.3, 1.0, 'عالی'), (0.1, 0.3, 'خوب'), (-0.1, 0.1, 'متوسط'), (-1, -0.1, 'ضعیف')],
        'MSI': [(0.4, 0.8, 'عالی'), (0.8, 1.2, 'خوب'), (1.2, 1.6, 'متوسط'), (1.6, 5.0, 'ضعیف')],
        'LAI': [(4.0, 10.0, 'عالی'), (2.5, 4.0, 'خوب'), (1.0, 2.5, 'متوسط'), (0, 1.0, 'ضعیف')],
        'Biomass': [(3.0, 10.0, 'عالی'), (2.0, 3.0, 'خوب'), (1.0, 2.0, 'متوسط'), (0, 1.0, 'ضعیف')],
        'Chlorophyll': [(3.0, 10.0, 'عالی'), (2.0, 3.0, 'خوب'), (1.0, 2.0, 'متوسط'), (0, 1.0, 'ضعیف')],
        'ET': [(6.0, 10.0, 'عالی'), (4.0, 6.0, 'خوب'), (2.0, 4.0, 'متوسط'), (0, 2.0, 'ضعیف')]
    }
    
    if index_name not in status_ranges:
        return 'نامشخص'
    
    for min_val, max_val, status in status_ranges[index_name]:
        if min_val <= value <= max_val:
            return status
    
    return 'نامشخص'

# Generate a downloadable figure
def get_figure_download_link(fig, filename):
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=300)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    href = f'<a href="data:image/png;base64,{b64}" download="{filename}">دانلود نمودار</a>'
    return href

# Main function to run the app
def main():
    # Application title and description
    st.title("سامانه هوشمند پایش مزارع نیشکر دهخدا 🌾")
    st.markdown("""
    این داشبورد برای مانیتورینگ پیشرفته مزارع نیشکر دهخدا طراحی شده و با استفاده از تصاویر ماهواره‌ای سنتینل۲، شاخص‌های مهم 
    کشاورزی را محاسبه و نمایش می‌دهد. با استفاده از این ابزار می‌توانید وضعیت سلامت گیاه، میزان بیوماس، تبخیر و تعرق و دیگر 
    شاخص‌های مهم را در هر روز از هفته مشاهده نمایید.
    """)
    
    # Sidebar
    st.sidebar.title("تنظیمات")
    
    # Authenticate with GEE
    gee_connected = authenticate_gee()
    
    if not gee_connected:
        st.warning("لطفاً ابتدا به Google Earth Engine متصل شوید.")
        return
    
    # Load farm data
    farms_data = load_farm_data()
    
    if farms_data.empty:
        st.error("داده‌های مزارع بارگذاری نشده‌اند. لطفاً فایل CSV را بررسی کنید.")
        return
    
    # Filter options
    days_of_week = farms_data['روزهای هفته'].unique().tolist() if 'روزهای هفته' in farms_data.columns else []
    selected_day = st.sidebar.selectbox("انتخاب روز هفته", days_of_week if days_of_week else ["همه روزها"])
    
    # Filter farms by selected day
    if selected_day != "همه روزها" and 'روزهای هفته' in farms_data.columns:
        filtered_farms = farms_data[farms_data['روزهای هفته'] == selected_day]
    else:
        filtered_farms = farms_data
    
    # Select farm
    farm_names = filtered_farms['مزرعه'].unique().tolist() if 'مزرعه' in filtered_farms.columns else []
    selected_farm = st.sidebar.selectbox("انتخاب مزرعه", farm_names)
    
    # Get selected farm data
    farm_data = filtered_farms[filtered_farms['مزرعه'] == selected_farm].iloc[0] if not filtered_farms.empty else None
    
    # Select index to display
    available_indices = ['NDVI', 'EVI', 'NDMI', 'MSI', 'LAI', 'Biomass', 'Chlorophyll', 'ET']
    selected_index = st.sidebar.selectbox("انتخاب شاخص", available_indices)
    
    # Date range selection
    st.sidebar.subheader("بازه زمانی")
    today = datetime.now()
    default_end_date = today.strftime('%Y-%m-%d')
    default_start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
    
    start_date = st.sidebar.date_input("تاریخ شروع", datetime.strptime(default_start_date, '%Y-%m-%d'))
    end_date = st.sidebar.date_input("تاریخ پایان", datetime.strptime(default_end_date, '%Y-%m-%d'))
    
    # Convert dates to strings
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    # Main content
    if farm_data is not None and 'مزرعه' in farm_data:
        # Create tabs
        tab1, tab2, tab3, tab4 = st.tabs(["نقشه", "نمودار زمانی", "جدول رتبه‌بندی", "اطلاعات مزرعه"])
        
        # Farm information
        with tab4:
            st.subheader(f"اطلاعات مزرعه {farm_data['مزرعه']}")
            
            # Create columns for better layout
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**اداره:** {farm_data['اداره'] if 'اداره' in farm_data else 'نامشخص'}")
                st.markdown(f"**کانال:** {farm_data['کانال'] if 'کانال' in farm_data else 'نامشخص'}")
                st.markdown(f"**واریته:** {farm_data['واریته'] if 'واریته' in farm_data else 'نامشخص'}")
            
            with col2:
                st.markdown(f"**مساحت داشت:** {farm_data['مساحت داشت'] if 'مساحت داشت' in farm_data else 'نامشخص'} هکتار")
                st.markdown(f"**سن:** {farm_data['سن'] if 'سن' in farm_data else 'نامشخص'}")
                st.markdown(f"**روز بازدید:** {farm_data['روزهای هفته'] if 'روزهای هفته' in farm_data else 'نامشخص'}")
            
            # Display coordinates
            st.markdown("### مختصات جغرافیایی")
            lat = farm_data.get('عرض جغرافیایی', farm_data.get('Latitude', None))
            lon = farm_data.get('طول جغرافیایی', farm_data.get('Longitude', None))
            
            if lat is not None and lon is not None:
                st.markdown(f"**عرض جغرافیایی:** {lat}")
                st.markdown(f"**طول جغرافیایی:** {lon}")
                
                # Create a small map to show the location
                location_map = folium.Map(location=[lat, lon], zoom_start=12)
                folium.Marker([lat, lon], popup=farm_data['مزرعه']).add_to(location_map)
                st.components.v1.html(location_map._repr_html_(), height=300)
            else:
                st.warning("مختصات جغرافیایی برای این مزرعه موجود نیست.")
        
        # Map tab
        with tab1:
            st.subheader(f"نقشه {selected_index} برای مزرعه {farm_data['مزرعه']}")
            
            try:
                # Create geometry for the farm
                if 'coordinates' in farm_data and farm_data['coordinates']:
                    # Parse coordinates
                    coords = farm_data['coordinates']
                    if isinstance(coords, str):
                        coords_parts = coords.replace('[', '').replace(']', '').split(',')
                        lon = float(coords_parts[0])
                        lat = float(coords_parts[1])
                    else:
                        lon = farm_data.get('طول جغرافیایی', farm_data.get('Longitude'))
                        lat = farm_data.get('عرض جغرافیایی', farm_data.get('Latitude'))
                        
                    if lat is not None and lon is not None:
                        # Create point geometry with buffer
                        geometry = ee.Geometry.Point([lon, lat]).buffer(100)  # 100m buffer
                        
                        # Get Sentinel-2 imagery
                        image = get_sentinel_imagery(geometry, start_date_str, end_date_str)
                        
                        if image is not None:
                            # Calculate all indices
                            image_with_indices = calculate_indices(image, geometry)
                            
                            # If the index is ET, get ET data separately
                            if selected_index == 'ET':
                                et_image = get_et_data(geometry, start_date_str, end_date_str)
                                if et_image is not None:
                                    # Create map for ET
                                    m = create_index_map(et_image, geometry, 'ET')
                                else:
                                    st.warning("داده تبخیر و تعرق (ET) برای این دوره زمانی موجود نیست.")
                                    m = None
                            else:
                                # Create map for other indices
                                m = create_index_map(image_with_indices, geometry, selected_index)
                            
                            if m is not None:
                                # Display the map
                                m_html = m.to_html()
                                st.components.v1.html(m_html, height=500)
                                
                                # Get index statistics
                                stats = image_with_indices.select(selected_index).reduceRegion(
                                    reducer=ee.Reducer.mean().combine(
                                        reducer2=ee.Reducer.stdDev(),
                                        sharedInputs=True
                                    ).combine(
                                        reducer2=ee.Reducer.minMax(),
                                        sharedInputs=True
                                    ),
                                    geometry=geometry,
                                    scale=10
                                ).getInfo()
                                
                                # Display statistics
                                st.subheader("آمار شاخص")
                                cols = st.columns(4)
                                
                                mean_val = stats.get(f"{selected_index}_mean", 0)
                                min_val = stats.get(f"{selected_index}_min", 0)
                                max_val = stats.get(f"{selected_index}_max", 0)
                                std_val = stats.get(f"{selected_index}_stdDev", 0)
                                
                                cols[0].metric("میانگین", f"{mean_val:.3f}")
                                cols[1].metric("حداقل", f"{min_val:.3f}")
                                cols[2].metric("حداکثر", f"{max_val:.3f}")
                                cols[3].metric("انحراف معیار", f"{std_val:.3f}")
                                
                                # Status based on mean value
                                status = get_status(selected_index, mean_val)
                                st.info(f"وضعیت مزرعه بر اساس شاخص {selected_index}: **{status}**")
                                
                                # Download map button
                                if st.button("دانلود نقشه"):
                                    m.to_streamlit(height=500)
                            else:
                                st.warning("خطا در ایجاد نقشه")
                        else:
                            st.warning("تصویر ماهواره‌ای برای این بازه زمانی موجود نیست یا میزان ابر بیش از حد مجاز است.")
                    else:
                        st.warning("مختصات جغرافیایی برای این مزرعه موجود نیست.")
                else:
                    st.warning("مختصات جغرافیایی برای این مزرعه موجود نیست.")
            except Exception as e:
                st.error(f"خطا در پردازش نقشه: {str(e)}")
        
        # Time series tab
        with tab2:
            st.subheader(