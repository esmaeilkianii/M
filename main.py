import streamlit as st
from components.sidebar import render_sidebar
from components.dashboard import render_dashboard
from components.map_view import render_map
from components.ai_analysis import render_ai_analysis
from utils.initialize import initialize_app, load_farm_data
import utils.styles as styles

# Initialize application
styles.apply_custom_styles()
initialize_app()

# Load farm data (will be cached)
farm_data_df = load_farm_data()

# Render sidebar and get selected filters
selected_filters = render_sidebar(farm_data_df)

# Render main content based on selected tab
tab1, tab2, tab3 = st.tabs(["📊 داشبورد", "🧠 Gemini", "🗺️ نقشه NDVI"])

with tab1:
    render_dashboard(farm_data_df, selected_filters)
    
with tab2:
    render_ai_analysis(farm_data_df, selected_filters)
    
with tab3:
    render_map(farm_data_df, selected_filters)

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با 💻 توسط [اسماعیل کیانی] با استفاده از Streamlit, Google Earth Engine, geemap و Gemini API")
st.sidebar.markdown("🌾 شرکت کشت و صنعت دهخدا")