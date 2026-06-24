import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(page_title="PPM HVAC AI Optimizer", layout="wide")

st.title("❄️ Power Plant Mall Cooling AI Optimizer")
st.write("Predictive HVAC physics model driven by ECMWF weather data.")

# 1. Calculate Wet-Bulb Temperature (Stull Formula)
def calculate_wet_bulb(t, rh):
    tw = t * np.arctan(0.151977 * (rh + 8.313659)**0.5) + np.arctan(t + rh) - np.arctan(rh - 1.676331) + 0.00391838 * (rh**1.5) * np.arctan(0.023101 * rh) - 4.686035
    return tw

# 2. Fetch ECMWF Data from Open-Meteo
@st.cache_data
def get_weather_data():
    # Makati City Coordinates
    url = "https://api.open-meteo.com/v1/ecmwf?latitude=14.55&longitude=121.02&hourly=temperature_2m,relative_humidity_2m&timezone=Asia%2FSingapore"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data['hourly'])
        df['time'] = pd.to_datetime(df['time'])
        df.rename(columns={'temperature_2m': 'temp', 'relative_humidity_2m': 'rh'}, inplace=True)
        df['wet_bulb'] = calculate_wet_bulb(df['temp'], df['rh'])
        return df
    return None

df_weather = get_weather_data()

# 3. Sidebar - Current Plant Rules Input
st.sidebar.header("Plant Operating Parameters")
current_tr_stage = st.sidebar.selectbox("Simulate Plant Load Stage", [1500, 2000, 2500])

# VFD Frequencies based on user sheet
hz_map = {
    1500: {"primary": 40, "secondary": 28, "condenser": 42, "ct": 40},
    2000: {"primary": 45, "secondary": 28, "condenser": 44, "ct": 40},
    2500: {"primary": 33, "secondary": 28, "condenser": 35, "ct": 40} # Note: 33Hz at 2500TR from user data
}

freqs = hz_map[current_tr_stage]

# Physics-based Power calculations (Affinity Laws)
def affinity_power(rated_kw, actual_hz):
    return rated_kw * ((actual_hz / 60.0) ** 3)

# Calculate power demands based on specs provided
p_primary = affinity_power(37, freqs["primary"])   # Baldor 37kW
p_secondary = affinity_power(150, freqs["secondary"]) # Baldor 150kW
p_condenser = affinity_power(100, freqs["condenser"]) # Baldor 100kW
p_ct = affinity_power(55, freqs["ct"])             # BAC 55kW

st.subheader(f"Current Baseline Simulation at {current_tr_stage} TR Stage")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Primary CHW Pump", f"{p_primary:.1f} kW", f"{freqs['primary']} Hz")
col2.metric("Secondary CHW Pump", f"{p_secondary:.1f} kW", f"{freqs['secondary']} Hz")
col3.metric("Condenser Pump", f"{p_condenser:.1f} kW", f"{freqs['condenser']} Hz")
col4.metric("Cooling Tower Fan", f"{p_ct:.1f} kW", f"{freqs['ct']} Hz")

# Display Forecast
if df_weather is not None:
    st.markdown("---")
    st.subheader("ECMWF Dynamic Ambient vs Wet-Bulb Forecast (Next 7 Days)")
    st.write("When Wet-Bulb temperature drops, your cooling towers operate significantly more efficiently. The AI will look for these gaps.")
    st.line_chart(df_weather.set_index('time')[['temp', 'wet_bulb']])