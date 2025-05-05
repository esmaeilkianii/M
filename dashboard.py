import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from plotly.subplots import make_subplots

# تنظیمات صفحه
st.set_page_config(
    page_title="داشبورد تحلیلی نیشکر",
    page_icon="🌾",
    layout="wide"
)

# استایل سفارشی
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
        @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');
        @import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');
        
        .main {
            font-family: 'Vazirmatn', sans-serif;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        }
        
        /* Header with animation */
        .header {
            background: linear-gradient(135deg, #43cea2 0%, #185a9d 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
            text-align: center;
            position: relative;
            overflow: hidden;
            animation: fadeIn 0.8s ease-in-out;
        }
        
        .header::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(45deg, transparent, rgba(255,255,255,0.1), transparent);
            transform: rotate(45deg);
            animation: shine 3s infinite linear;
        }
        
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 900;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            animation: bounceIn 1s ease-in-out;
        }
        
        .card {
            background-color: #ffffff;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
            margin: 15px 0;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            border: 1px solid rgba(0, 0, 0, 0.05);
            animation: fadeIn 0.6s ease-in-out;
        }
        
        .card:hover {
            transform: translateY(-10px);
            box-shadow: 0 15px 30px rgba(0, 0, 0, 0.12);
        }
        
        .metric-card {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            border-radius: 15px;
            padding: 25px;
            margin: 15px 0;
            text-align: center;
            position: relative;
            overflow: hidden;
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.15);
            transition: all 0.5s ease;
            animation: bounceIn 0.8s ease-in-out;
        }
        
        .metric-card::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 5px;
            background: linear-gradient(to right, #43cea2, #185a9d);
        }
        
        .metric-card:hover {
            transform: translateY(-5px) scale(1.02);
            box-shadow: 0 15px 30px rgba(0, 0, 0, 0.2);
        }
        
        .metric-card h3 {
            font-size: 1.2em;
            opacity: 0.9;
            margin-bottom: 10px;
            font-weight: 500;
        }
        
        .metric-card h2 {
            font-size: 2.5em;
            font-weight: 900;
            margin: 0;
            padding: 0;
            line-height: 1;
        }
        
        .metric-card i {
            font-size: 2em;
            margin-bottom: 15px;
            display: block;
            opacity: 0.8;
        }
        
        .chart-container {
            background-color: #ffffff;
            border-radius: 15px;
            padding: 25px;
            margin: 20px 0;
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.08);
            transition: all 0.3s ease;
            animation: fadeIn 0.8s ease-in-out;
            position: relative;
            border: 1px solid rgba(0, 0, 0, 0.05);
        }
        
        .chart-container:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0, 0, 0, 0.12);
        }
        
        .chart-container h3 {
            color: #185a9d;
            font-weight: 700;
            margin-bottom: 20px;
            font-size: 1.5em;
            padding-bottom: 10px;
            border-bottom: 3px solid #43cea2;
            display: inline-block;
        }
        
        /* Animation keyframes */
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes bounceIn {
            0% {
                opacity: 0;
                transform: scale(0.3);
            }
            50% {
                opacity: 1;
                transform: scale(1.05);
            }
            70% { transform: scale(0.9); }
            100% { transform: scale(1); }
        }
        
        @keyframes shine {
            0% {
                left: -100%;
                opacity: 0;
            }
            100% {
                left: 100%;
                opacity: 0.3;
            }
        }
        
        /* Filter panel styling */
        .filter-container {
            background: #f8f9fa;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.05);
            border: 1px solid rgba(0, 0, 0, 0.05);
            animation: fadeIn 0.6s ease-in-out;
        }
        
        /* Custom button styling */
        .custom-button {
            display: inline-block;
            background: linear-gradient(135deg, #43cea2 0%, #185a9d 100%);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 600;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            border: none;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            text-decoration: none;
        }
        
        .custom-button:hover {
            transform: translateY(-3px);
            box-shadow: 0 7px 14px rgba(0, 0, 0, 0.15);
        }
        
        .custom-button:active {
            transform: translateY(0);
        }
    </style>
""", unsafe_allow_html=True)

# هدر جدید با انیمیشن
st.markdown("""
    <div class="header">
        <h1>🌾 داشبورد تحلیلی نیشکر</h1>
        <p style="margin-top: 10px; font-size: 1.2em; opacity: 0.9;">سیستم هوشمند مدیریت و پایش مزارع نیشکر</p>
    </div>
""", unsafe_allow_html=True)

# پنل فیلتر
st.markdown("""
    <div class="filter-container">
        <h3 style="color: #185a9d; margin-bottom: 15px; font-size: 1.3em;">فیلترها</h3>
    </div>
""", unsafe_allow_html=True)
col_filter1, col_filter2, col_filter3 = st.columns(3)

with col_filter1:
    variate_filter = st.selectbox("انتخاب واریته", ["همه", "CP69", "CP73", "CP48", "CP57", "CP65", "CP70", "IR01-412", "IRC99-07", "IRC00-14"])

with col_filter2:
    department_filter = st.selectbox("انتخاب اداره", ["همه", "اداره یک", "اداره دو", "اداره سه", "اداره چهار"])

with col_filter3:
    age_filter = st.selectbox("انتخاب سن", ["همه", "1", "2", "3", "4", "5", "6", "7", "8", "9"])

# خواندن داده‌ها
@st.cache_data
def load_data():
    df = pd.read_csv('محاسبات 2.csv')
    return df

df = load_data()

# ایجاد کارت‌های متریک با آیکون و انیمیشن
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
        <div class="metric-card">
            <i class="fas fa-chart-area"></i>
            <h3>کل مساحت (هکتار)</h3>
            <h2>9,421.30</h2>
        </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
        <div class="metric-card">
            <i class="fas fa-seedling"></i>
            <h3>تعداد واریته‌ها</h3>
            <h2>9</h2>
        </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
        <div class="metric-card">
            <i class="fas fa-building"></i>
            <h3>تعداد ادارات</h3>
            <h2>4</h2>
        </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
        <div class="metric-card">
            <i class="fas fa-calendar-alt"></i>
            <h3>تعداد سن‌ها</h3>
            <h2>9</h2>
        </div>
    """, unsafe_allow_html=True)

# نمودار سه بعدی مساحت به تفکیک اداره، سن و واریته
st.markdown("""
    <div class="chart-container">
        <h3>نمودار سه بعدی مساحت به تفکیک اداره، سن و واریته</h3>
        <p style="color: #666; margin-bottom: 20px;">این نمودار نمایش تعاملی از توزیع مساحت مزارع را بر اساس سه پارامتر اداره، سن و واریته نشان می‌دهد.</p>
    </div>
""", unsafe_allow_html=True)

# پردازش داده‌ها برای نمودار سه بعدی
def prepare_3d_data(df):
    # تبدیل داده‌ها به فرمت مناسب برای نمودار سه بعدی
    data = []
    for _, row in df.iterrows():
        if row['اداره'] != 'Grand Total' and row['سن'] != 'total':
            for col in ['CP69', 'CP73', 'CP48', 'CP57', 'CP65', 'CP70', 'IR01-412', 'IRC99-07', 'IRC00-14']:
                if pd.notna(row[col]) and row[col] != 0:
                    data.append({
                        'اداره': row['اداره'],
                        'سن': row['سن'],
                        'واریته': col,
                        'مساحت': row[col]
                    })
    return pd.DataFrame(data)

df_3d = prepare_3d_data(df)

# ایجاد نمودار سه بعدی بهبود یافته
fig = go.Figure(data=[go.Scatter3d(
    x=df_3d['اداره'],
    y=df_3d['سن'],
    z=df_3d['مساحت'],
    mode='markers',
    marker=dict(
        size=df_3d['مساحت']/10,
        color=df_3d['مساحت'],
        colorscale='Viridis',
        opacity=0.8,
        colorbar=dict(title="مساحت (هکتار)"),
        symbol='circle'
    ),
    text=df_3d['واریته'],
    hovertemplate="اداره: %{x}<br>سن: %{y}<br>مساحت: %{z:.2f} هکتار<br>واریته: %{text}<extra></extra>"
)])

fig.update_layout(
    scene = dict(
        xaxis_title=dict(text="اداره", font=dict(size=14, family="Vazirmatn")),
        yaxis_title=dict(text="سن", font=dict(size=14, family="Vazirmatn")),
        zaxis_title=dict(text="مساحت (هکتار)", font=dict(size=14, family="Vazirmatn")),
        xaxis=dict(backgroundcolor="rgba(230, 230, 230, 0.3)"),
        yaxis=dict(backgroundcolor="rgba(230, 230, 230, 0.3)"),
        zaxis=dict(backgroundcolor="rgba(230, 230, 230, 0.3)")
    ),
    margin=dict(l=0, r=0, b=0, t=30),
    height=600,
    scene_camera=dict(
        eye=dict(x=1.5, y=1.5, z=1.2)
    ),
    font=dict(family="Vazirmatn"),
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)'
)

st.plotly_chart(fig, use_container_width=True)

# دکمه‌های تعاملی برای تغییر نمای نمودار
col_btn1, col_btn2, col_btn3 = st.columns(3)
with col_btn1:
    st.markdown("""
        <div class="custom-button" onclick="Plotly.relayout('_plotly_graph_0', 
        {'scene.camera.eye': {'x': 1.5, 'y': 1.5, 'z': 1.2}})">
            نمای استاندارد
        </div>
    """, unsafe_allow_html=True)
with col_btn2:
    st.markdown("""
        <div class="custom-button" onclick="Plotly.relayout('_plotly_graph_0', 
        {'scene.camera.eye': {'x': 0, 'y': 2.5, 'z': 0.1}})">
            نمای از بالا
        </div>
    """, unsafe_allow_html=True)
with col_btn3:
    st.markdown("""
        <div class="custom-button" onclick="Plotly.relayout('_plotly_graph_0', 
        {'scene.camera.eye': {'x': 2.5, 'y': 0, 'z': 0.1}})">
            نمای از کنار
        </div>
    """, unsafe_allow_html=True)

# نمودار هیستوگرام سورفیس
st.markdown("""
    <div class="chart-container">
        <h3>هیستوگرام سورفیس مساحت به تفکیک اداره و سن</h3>
        <p style="color: #666; margin-bottom: 20px;">این نمودار توزیع سطحی مساحت را بر اساس اداره و سن نشان می‌دهد.</p>
    </div>
""", unsafe_allow_html=True)

# پردازش داده‌ها برای هیستوگرام سورفیس
def prepare_surface_data(df):
    data = []
    for _, row in df.iterrows():
        if row['اداره'] != 'Grand Total' and row['سن'] != 'total':
            data.append({
                'اداره': row['اداره'],
                'سن': row['سن'],
                'مساحت': row['Grand Total']
            })
    return pd.DataFrame(data)

df_surface = prepare_surface_data(df)

# ایجاد هیستوگرام سورفیس بهبود یافته
fig_surface = go.Figure(data=[go.Surface(
    x=df_surface['اداره'].unique(),
    y=df_surface['سن'].unique(),
    z=df_surface.pivot(index='سن', columns='اداره', values='مساحت').values,
    colorscale='Viridis',
    colorbar=dict(title="مساحت (هکتار)"),
    lighting=dict(ambient=0.6, diffuse=0.5, fresnel=0.1, specular=0.2, roughness=0.5),
    contours=dict(
        z=dict(show=True, usecolormap=True, highlightcolor="white", project=dict(z=True))
    )
)])

fig_surface.update_layout(
    scene = dict(
        xaxis_title=dict(text="اداره", font=dict(size=14, family="Vazirmatn")),
        yaxis_title=dict(text="سن", font=dict(size=14, family="Vazirmatn")),
        zaxis_title=dict(text="مساحت (هکتار)", font=dict(size=14, family="Vazirmatn")),
        xaxis=dict(backgroundcolor="rgba(230, 230, 230, 0.3)"),
        yaxis=dict(backgroundcolor="rgba(230, 230, 230, 0.3)"),
        zaxis=dict(backgroundcolor="rgba(230, 230, 230, 0.3)")
    ),
    margin=dict(l=0, r=0, b=0, t=30),
    height=600,
    scene_camera=dict(
        eye=dict(x=1.5, y=1.5, z=1.2)
    ),
    font=dict(family="Vazirmatn"),
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)'
)

st.plotly_chart(fig_surface, use_container_width=True)

# نمودار مقایسه‌ای واریته‌ها
st.markdown("""
    <div class="chart-container">
        <h3>مقایسه واریته‌ها در ادارات مختلف</h3>
        <p style="color: #666; margin-bottom: 20px;">این نمودار مساحت اختصاص داده شده به هر واریته را در ادارات مختلف مقایسه می‌کند.</p>
    </div>
""", unsafe_allow_html=True)

# پردازش داده‌ها برای نمودار مقایسه‌ای
varieties = ['CP69', 'CP73', 'CP48', 'CP57', 'CP65', 'CP70', 'IR01-412', 'IRC99-07', 'IRC00-14']
fig_varieties = go.Figure()

for i, variety in enumerate(varieties):
    data = df[df['اداره'] != 'Grand Total'].groupby('اداره')[variety].sum()
    fig_varieties.add_trace(go.Bar(
        name=variety,
        x=data.index,
        y=data.values,
        marker=dict(
            color=px.colors.qualitative.G10[i % len(px.colors.qualitative.G10)],
            line=dict(color='rgba(0,0,0,0.1)', width=0.5)
        ),
        hovertemplate="اداره: %{x}<br>مساحت: %{y:.2f} هکتار<extra>%{fullData.name}</extra>"
    ))

fig_varieties.update_layout(
    barmode='group',
    xaxis_title=dict(text="اداره", font=dict(size=14, family="Vazirmatn")),
    yaxis_title=dict(text="مساحت (هکتار)", font=dict(size=14, family="Vazirmatn")),
    height=450,
    font=dict(family="Vazirmatn"),
    legend=dict(
        title=dict(text="واریته"),
        orientation="h",
        y=1.1,
        xanchor="center",
        x=0.5
    ),
    margin=dict(l=0, r=0, b=0, t=50),
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    hovermode="closest"
)

st.plotly_chart(fig_varieties, use_container_width=True)

# بخش جدید: خلاصه آماری
st.markdown("""
    <div class="chart-container">
        <h3>خلاصه آماری واریته‌ها</h3>
        <p style="color: #666; margin-bottom: 20px;">این نمودار آمار توصیفی واریته‌های مختلف را نمایش می‌دهد.</p>
    </div>
""", unsafe_allow_html=True)

# محاسبه آمار توصیفی
summary_data = []
for variety in varieties:
    variety_data = df[df['اداره'] != 'Grand Total'][variety]
    variety_data = variety_data[variety_data > 0]  # حذف صفرها
    if not variety_data.empty:
        summary_data.append({
            'واریته': variety,
            'مساحت کل (هکتار)': variety_data.sum(),
            'میانگین مساحت (هکتار)': variety_data.mean(),
            'بیشترین مساحت (هکتار)': variety_data.max(),
            'کمترین مساحت (هکتار)': variety_data.min(),
            'تعداد قطعات': len(variety_data)
        })

summary_df = pd.DataFrame(summary_data)

# نمایش جدول خلاصه آماری
st.dataframe(summary_df.style.format({
    'مساحت کل (هکتار)': '{:.2f}',
    'میانگین مساحت (هکتار)': '{:.2f}',
    'بیشترین مساحت (هکتار)': '{:.2f}',
    'کمترین مساحت (هکتار)': '{:.2f}'
}), height=300, use_container_width=True)

# نمودار راداری برای مقایسه واریته‌ها
categories = ['مساحت کل', 'میانگین مساحت', 'بیشترین مساحت', 'تعداد قطعات']

fig_radar = go.Figure()

for i, row in summary_df.iterrows():
    variety = row['واریته']
    
    # نرمال‌سازی داده‌ها برای نمودار راداری
    total_area_normalized = row['مساحت کل (هکتار)'] / summary_df['مساحت کل (هکتار)'].max()
    mean_area_normalized = row['میانگین مساحت (هکتار)'] / summary_df['میانگین مساحت (هکتار)'].max()
    max_area_normalized = row['بیشترین مساحت (هکتار)'] / summary_df['بیشترین مساحت (هکتار)'].max()
    count_normalized = row['تعداد قطعات'] / summary_df['تعداد قطعات'].max()
    
    fig_radar.add_trace(go.Scatterpolar(
        r=[total_area_normalized, mean_area_normalized, max_area_normalized, count_normalized],
        theta=categories,
        fill='toself',
        name=variety
    ))

fig_radar.update_layout(
    polar=dict(
        radialaxis=dict(
            visible=True,
            range=[0, 1]
        )
    ),
    showlegend=True,
    height=500,
    font=dict(family="Vazirmatn"),
    legend=dict(
        orientation="h",
        y=-0.1,
        xanchor="center",
        x=0.5
    )
)

st.plotly_chart(fig_radar, use_container_width=True)

# Footer
st.markdown("""
    <div style="text-align: center; margin-top: 50px; padding: 20px; border-top: 1px solid rgba(0,0,0,0.1);">
        <p style="color: #666; font-size: 0.9em;">© سامانه پایش هوشمند نیشکر - تمامی حقوق محفوظ است.</p>
    </div>
""", unsafe_allow_html=True) 