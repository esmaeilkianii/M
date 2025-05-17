import streamlit as st
import pandas as pd
import geopandas as gpd
from streamlit_folium import folium_static
import folium
import json

def render_map(farm_data_df, filters):
    """
    Renders a map view of the farm data with NDVI visualization
    """
    st.title("🗺️ نقشه مزارع و شاخص NDVI")
    
    if farm_data_df.empty:
        st.warning("داده‌های مزارع بارگذاری نشده است")
        return
    
    # Try to load GeoJSON data
    try:
        geojson_file = "farm_geodata_fixed.geojson"
        
        # Load GeoJSON file
        with open(geojson_file, 'r', encoding='utf-8') as f:
            farm_geojson = json.load(f)
        
        # Create a map centered on the area
        m = folium.Map(location=[31.0, 48.5], zoom_start=10)
        
        # Add GeoJSON layer to map
        folium.GeoJson(
            farm_geojson,
            name="مزارع",
            tooltip=folium.GeoJsonTooltip(
                fields=["name", "area_ha"],
                aliases=["نام مزرعه:", "مساحت (هکتار):"],
                localize=True
            ),
            style_function=lambda x: {
                'fillColor': '#28a745',
                'color': '#000',
                'weight': 1,
                'fillOpacity': 0.7
            }
        ).add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Display the map
        folium_static(m)
        
    except Exception as e:
        st.error(f"خطا در بارگذاری داده‌های نقشه: {str(e)}")
        st.info("برای نمایش نقشه، فایل GeoJSON مزارع مورد نیاز است.")
        
    # Add NDVI information section
    st.subheader("راهنمای شاخص NDVI")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("""
        **مقادیر شاخص NDVI:**
        - 0.8 - 1.0: پوشش گیاهی متراکم سالم
        - 0.6 - 0.8: پوشش گیاهی خوب
        - 0.4 - 0.6: پوشش گیاهی متوسط
        - 0.2 - 0.4: پوشش گیاهی کم
        - 0.0 - 0.2: خاک بایر یا پوشش گیاهی ضعیف
        - منفی: آب، ابر یا برف
        """)
    
    with col2:
        st.markdown("""
        **شاخص NDVI (Normalized Difference Vegetation Index)** یا شاخص نرمال‌شده اختلاف پوشش گیاهی:
        
        شاخصی است که وضعیت سلامت و تراکم پوشش گیاهی را نشان می‌دهد. این شاخص از تفاوت بازتاب نور مرئی و مادون قرمز نزدیک محاسبه می‌شود. گیاهان سالم نور مرئی را جذب و نور مادون قرمز نزدیک را بازتاب می‌کنند.
        
        NDVI برای مدیریت مزارع نیشکر اهمیت زیادی دارد و می‌تواند وضعیت رشد، تنش‌های محیطی و مشکلات احتمالی را نشان دهد.
        """) 