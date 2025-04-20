import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.colors as mcolors
import os

# Set the style for better visualization
plt.style.use('seaborn-v0_8-darkgrid')

# Read the data
df = pd.read_csv('محاسبات 2.csv')

# Function to clean and prepare the data
def prepare_data(df):
    # Split the data into two dataframes (area and production)
    area_df = df.iloc[:33].copy()
    production_df = df.iloc[34:].copy()
    
    # Clean the data
    area_df = area_df.dropna(subset=['اداره'])
    production_df = production_df.dropna(subset=['تولید'])
    
    # Rename columns for consistency
    production_df = production_df.rename(columns={'تولید': 'اداره'})
    
    # Melt the dataframes to get long format
    area_melted = pd.melt(area_df, 
                          id_vars=['اداره', 'سن'], 
                          value_vars=['CP69', 'CP73', 'CP48', 'CP57', 'CP65', 'CP70', 'IR01-412', 'IRC99-07', 'IRC00-14'],
                          var_name='واریته', 
                          value_name='مساحت')
    
    production_melted = pd.melt(production_df, 
                               id_vars=['اداره', 'سن'], 
                               value_vars=['CP69', 'CP73', 'CP48', 'CP57', 'CP65', 'CP70', 'IR01-412', 'IRC99-07', 'IRC00-14'],
                               var_name='واریته', 
                               value_name='تولید')
    
    # Merge the dataframes
    merged_df = pd.merge(area_melted, production_melted, on=['اداره', 'سن', 'واریته'])
    
    # Convert numeric columns to float
    merged_df['مساحت'] = pd.to_numeric(merged_df['مساحت'], errors='coerce')
    merged_df['تولید'] = pd.to_numeric(merged_df['تولید'], errors='coerce')
    
    # Fill NaN values with 0
    merged_df = merged_df.fillna(0)
    
    return merged_df

# Prepare the data
data = prepare_data(df)

# Create output directory if it doesn't exist
os.makedirs('visualizations', exist_ok=True)

# 1. 3D Surface Histogram for Area by Department, Age, and Variety
def create_3d_surface_area():
    # Create a pivot table for the 3D surface
    pivot_data = data.pivot_table(
        values='مساحت', 
        index='سن', 
        columns='واریته', 
        aggfunc='sum'
    ).fillna(0)
    
    # Create the 3D surface plot
    fig = go.Figure(data=[go.Surface(
        x=pivot_data.columns,
        y=pivot_data.index,
        z=pivot_data.values,
        colorscale='Viridis',
        showscale=True,
        colorbar=dict(title='مساحت (هکتار)')
    )])
    
    # Update layout
    fig.update_layout(
        title='توزیع مساحت به تفکیک سن و واریته',
        scene=dict(
            xaxis_title='واریته',
            yaxis_title='سن',
            zaxis_title='مساحت (هکتار)',
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.5)
            )
        ),
        width=1000,
        height=800,
        font=dict(family="Vazirmatn, Arial", size=14)
    )
    
    # Save the figure
    fig.write_html('visualizations/3d_surface_area.html')
    fig.write_image('visualizations/3d_surface_area.png', scale=2)
    
    return fig

# 2. 3D Surface Histogram for Production by Department, Age, and Variety
def create_3d_surface_production():
    # Create a pivot table for the 3D surface
    pivot_data = data.pivot_table(
        values='تولید', 
        index='سن', 
        columns='واریته', 
        aggfunc='sum'
    ).fillna(0)
    
    # Create the 3D surface plot
    fig = go.Figure(data=[go.Surface(
        x=pivot_data.columns,
        y=pivot_data.index,
        z=pivot_data.values,
        colorscale='Plasma',
        showscale=True,
        colorbar=dict(title='تولید (تن)')
    )])
    
    # Update layout
    fig.update_layout(
        title='توزیع تولید به تفکیک سن و واریته',
        scene=dict(
            xaxis_title='واریته',
            yaxis_title='سن',
            zaxis_title='تولید (تن)',
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.5)
            )
        ),
        width=1000,
        height=800,
        font=dict(family="Vazirmatn, Arial", size=14)
    )
    
    # Save the figure
    fig.write_html('visualizations/3d_surface_production.html')
    fig.write_image('visualizations/3d_surface_production.png', scale=2)
    
    return fig

# 3. Area Chart by Department and Age
def create_area_chart_by_dept_age():
    # Group by department and age
    dept_age_data = data.groupby(['اداره', 'سن'])['مساحت'].sum().reset_index()
    
    # Create the area chart
    fig = px.area(
        dept_age_data, 
        x='سن', 
        y='مساحت', 
        color='اداره',
        title='مساحت به تفکیک اداره و سن',
        labels={'مساحت': 'مساحت (هکتار)', 'سن': 'سن', 'اداره': 'اداره'},
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    # Update layout
    fig.update_layout(
        width=1000,
        height=600,
        font=dict(family="Vazirmatn, Arial", size=14),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Save the figure
    fig.write_html('visualizations/area_chart_by_dept_age.html')
    fig.write_image('visualizations/area_chart_by_dept_age.png', scale=2)
    
    return fig

# 4. Area Chart by Department and Variety
def create_area_chart_by_dept_variety():
    # Group by department and variety
    dept_variety_data = data.groupby(['اداره', 'واریته'])['مساحت'].sum().reset_index()
    
    # Create the area chart
    fig = px.area(
        dept_variety_data, 
        x='واریته', 
        y='مساحت', 
        color='اداره',
        title='مساحت به تفکیک اداره و واریته',
        labels={'مساحت': 'مساحت (هکتار)', 'واریته': 'واریته', 'اداره': 'اداره'},
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    # Update layout
    fig.update_layout(
        width=1000,
        height=600,
        font=dict(family="Vazirmatn, Arial", size=14),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Save the figure
    fig.write_html('visualizations/area_chart_by_dept_variety.html')
    fig.write_image('visualizations/area_chart_by_dept_variety.png', scale=2)
    
    return fig

# 5. 3D Bar Chart for Area by Department, Age, and Variety
def create_3d_bar_chart():
    # Create a figure
    fig = plt.figure(figsize=(15, 10))
    ax = fig.add_subplot(111, projection='3d')
    
    # Get unique values
    departments = data['اداره'].unique()
    ages = data['سن'].unique()
    varieties = data['واریته'].unique()
    
    # Create a color map
    colors = plt.cm.viridis(np.linspace(0, 1, len(varieties)))
    
    # Create the 3D bar chart
    for i, dept in enumerate(departments):
        for j, age in enumerate(ages):
            for k, variety in enumerate(varieties):
                # Get the value
                value = data[(data['اداره'] == dept) & 
                            (data['سن'] == age) & 
                            (data['واریته'] == variety)]['مساحت'].values
                
                if len(value) > 0 and value[0] > 0:
                    # Create the bar
                    ax.bar3d(i, j, k, 0.8, 0.8, value[0], color=colors[k], alpha=0.8)
    
    # Set labels
    ax.set_xlabel('اداره')
    ax.set_ylabel('سن')
    ax.set_zlabel('مساحت (هکتار)')
    
    # Set ticks
    ax.set_xticks(np.arange(len(departments)) + 0.4)
    ax.set_xticklabels(departments)
    
    ax.set_yticks(np.arange(len(ages)) + 0.4)
    ax.set_yticklabels(ages)
    
    # Set title
    plt.title('توزیع مساحت به تفکیک اداره، سن و واریته', fontsize=16)
    
    # Add a colorbar
    sm = plt.cm.ScalarMappable(cmap=plt.cm.viridis, norm=plt.Normalize(vmin=0, vmax=len(varieties)-1))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, pad=0.1)
    cbar.set_label('واریته')
    cbar.set_ticks(np.arange(len(varieties)))
    cbar.set_ticklabels(varieties)
    
    # Save the figure
    plt.tight_layout()
    plt.savefig('visualizations/3d_bar_chart.png', dpi=300, bbox_inches='tight')
    
    return fig

# 6. Heatmap for Area by Department and Age
def create_heatmap_area():
    # Create a pivot table for the heatmap
    pivot_data = data.pivot_table(
        values='مساحت', 
        index='اداره', 
        columns='سن', 
        aggfunc='sum'
    ).fillna(0)
    
    # Create the heatmap
    fig = go.Figure(data=go.Heatmap(
        z=pivot_data.values,
        x=pivot_data.columns,
        y=pivot_data.index,
        colorscale='Viridis',
        colorbar=dict(title='مساحت (هکتار)')
    ))
    
    # Update layout
    fig.update_layout(
        title='مساحت به تفکیک اداره و سن',
        xaxis_title='سن',
        yaxis_title='اداره',
        width=900,
        height=600,
        font=dict(family="Vazirmatn, Arial", size=14)
    )
    
    # Save the figure
    fig.write_html('visualizations/heatmap_area.html')
    fig.write_image('visualizations/heatmap_area.png', scale=2)
    
    return fig

# 7. Heatmap for Production by Department and Age
def create_heatmap_production():
    # Create a pivot table for the heatmap
    pivot_data = data.pivot_table(
        values='تولید', 
        index='اداره', 
        columns='سن', 
        aggfunc='sum'
    ).fillna(0)
    
    # Create the heatmap
    fig = go.Figure(data=go.Heatmap(
        z=pivot_data.values,
        x=pivot_data.columns,
        y=pivot_data.index,
        colorscale='Plasma',
        colorbar=dict(title='تولید (تن)')
    ))
    
    # Update layout
    fig.update_layout(
        title='تولید به تفکیک اداره و سن',
        xaxis_title='سن',
        yaxis_title='اداره',
        width=900,
        height=600,
        font=dict(family="Vazirmatn, Arial", size=14)
    )
    
    # Save the figure
    fig.write_html('visualizations/heatmap_production.html')
    fig.write_image('visualizations/heatmap_production.png', scale=2)
    
    return fig

# 8. Stacked Bar Chart for Area by Department and Variety
def create_stacked_bar_chart():
    # Create a pivot table for the stacked bar chart
    pivot_data = data.pivot_table(
        values='مساحت', 
        index='اداره', 
        columns='واریته', 
        aggfunc='sum'
    ).fillna(0)
    
    # Create the stacked bar chart
    fig = go.Figure()
    
    for variety in pivot_data.columns:
        fig.add_trace(go.Bar(
            name=variety,
            x=pivot_data.index,
            y=pivot_data[variety],
            text=pivot_data[variety].round(1),
            textposition='auto',
        ))
    
    # Update layout
    fig.update_layout(
        title='مساحت به تفکیک اداره و واریته',
        xaxis_title='اداره',
        yaxis_title='مساحت (هکتار)',
        barmode='stack',
        width=1000,
        height=600,
        font=dict(family="Vazirmatn, Arial", size=14),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Save the figure
    fig.write_html('visualizations/stacked_bar_chart.html')
    fig.write_image('visualizations/stacked_bar_chart.png', scale=2)
    
    return fig

# 9. 3D Scatter Plot for Area, Production, and Age
def create_3d_scatter_plot():
    # Create the 3D scatter plot
    fig = go.Figure(data=[go.Scatter3d(
        x=data['مساحت'],
        y=data['تولید'],
        z=data['سن'].map(lambda x: {'P': 0, 'R1': 1, 'R2': 2, 'R3': 3, 'R4': 4, 'R5': 5, 'R6': 6, 'R7': 7, 'R8': 8, 'R9': 9}.get(x, 0)),
        mode='markers',
        marker=dict(
            size=8,
            color=data['اداره'].map({'1': 0, '2': 1, '3': 2, '4': 3, 'دهخدا': 4}),
            colorscale='Viridis',
            opacity=0.8
        ),
        text=data['واریته'],
        hovertemplate="<b>واریته:</b> %{text}<br>" +
                      "<b>مساحت:</b> %{x:.2f} هکتار<br>" +
                      "<b>تولید:</b> %{y:.2f} تن<br>" +
                      "<b>سن:</b> %{z}<br>" +
                      "<extra></extra>"
    )])
    
    # Update layout
    fig.update_layout(
        title='رابطه بین مساحت، تولید و سن',
        scene=dict(
            xaxis_title='مساحت (هکتار)',
            yaxis_title='تولید (تن)',
            zaxis_title='سن',
            zaxis=dict(
                ticktext=['P', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8', 'R9'],
                tickvals=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
            )
        ),
        width=1000,
        height=800,
        font=dict(family="Vazirmatn, Arial", size=14)
    )
    
    # Save the figure
    fig.write_html('visualizations/3d_scatter_plot.html')
    fig.write_image('visualizations/3d_scatter_plot.png', scale=2)
    
    return fig

# Generate all visualizations
def generate_all_visualizations():
    print("Generating 3D Surface Histogram for Area...")
    create_3d_surface_area()
    
    print("Generating 3D Surface Histogram for Production...")
    create_3d_surface_production()
    
    print("Generating Area Chart by Department and Age...")
    create_area_chart_by_dept_age()
    
    print("Generating Area Chart by Department and Variety...")
    create_area_chart_by_dept_variety()
    
    print("Generating 3D Bar Chart...")
    create_3d_bar_chart()
    
    print("Generating Heatmap for Area...")
    create_heatmap_area()
    
    print("Generating Heatmap for Production...")
    create_heatmap_production()
    
    print("Generating Stacked Bar Chart...")
    create_stacked_bar_chart()
    
    print("Generating 3D Scatter Plot...")
    create_3d_scatter_plot()
    
    print("All visualizations have been generated and saved to the 'visualizations' directory.")

# Run the function to generate all visualizations
if __name__ == "__main__":
    generate_all_visualizations() 