import streamlit as st
import pandas as pd
import plotly.express as px

def render_dashboard(farm_data_df, filters):
    """
    Renders the main dashboard with farm data visualizations
    """
    st.title("📊 داشبورد مدیریت مزارع نیشکر")
    
    if farm_data_df.empty:
        st.warning("داده‌های مزارع بارگذاری نشده است")
        return
    
    # Filter data based on selected farm if available
    filtered_df = farm_data_df
    if 'selected_farm' in filters:
        farm_name_col = 'farm_name' if 'farm_name' in farm_data_df.columns else 'name'
        filtered_df = farm_data_df[farm_data_df[farm_name_col] == filters['selected_farm']]
    
    # Display basic metrics
    st.subheader("آمار کلی مزارع")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_farms = len(filtered_df['farm_id'].unique()) if 'farm_id' in filtered_df.columns else len(filtered_df)
        st.metric("تعداد مزارع", f"{total_farms}")
    
    with col2:
        if 'area_ha' in filtered_df.columns:
            total_area = filtered_df['area_ha'].sum()
            st.metric("مساحت کل (هکتار)", f"{total_area:.2f}")
        else:
            st.metric("مساحت کل (هکتار)", "داده موجود نیست")
    
    with col3:
        if 'yield_tons' in filtered_df.columns:
            avg_yield = filtered_df['yield_tons'].mean()
            st.metric("میانگین عملکرد (تن)", f"{avg_yield:.2f}")
        else:
            st.metric("میانگین عملکرد (تن)", "داده موجود نیست")
    
    with col4:
        if 'ndvi' in filtered_df.columns:
            avg_ndvi = filtered_df['ndvi'].mean()
            st.metric("میانگین NDVI", f"{avg_ndvi:.2f}")
        else:
            st.metric("میانگین NDVI", "داده موجود نیست")
    
    # Create sample charts
    st.subheader("نمودارها و تحلیل‌ها")
    
    # Create charts based on available columns
    chart_cols = [col for col in filtered_df.columns if filtered_df[col].dtype in ['int64', 'float64']]
    
    if chart_cols:
        col1, col2 = st.columns(2)
        
        with col1:
            try:
                # Sample bar chart
                if 'area_ha' in filtered_df.columns and 'farm_name' in filtered_df.columns:
                    fig = px.bar(
                        filtered_df, 
                        x='farm_name', 
                        y='area_ha',
                        title="مساحت مزارع (هکتار)",
                        labels={"farm_name": "نام مزرعه", "area_ha": "مساحت (هکتار)"}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("داده‌های کافی برای نمایش نمودار موجود نیست")
            except Exception as e:
                st.error(f"خطا در ایجاد نمودار: {str(e)}")
        
        with col2:
            try:
                # Sample pie chart for farm distribution
                if 'farm_type' in filtered_df.columns:
                    type_counts = filtered_df['farm_type'].value_counts().reset_index()
                    type_counts.columns = ['farm_type', 'count']
                    
                    fig = px.pie(
                        type_counts,
                        values='count',
                        names='farm_type',
                        title="توزیع انواع مزارع",
                        hole=0.4
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("داده‌های کافی برای نمایش نمودار موجود نیست")
            except Exception as e:
                st.error(f"خطا در ایجاد نمودار: {str(e)}")
    
    # Display farm data table
    st.subheader("جدول داده‌های مزارع")
    st.dataframe(filtered_df, use_container_width=True) 