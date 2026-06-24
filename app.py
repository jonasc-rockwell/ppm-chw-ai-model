import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(page_title="Power Plant Mall HVAC AI Optimizer", layout="wide")

# Initialize persistent database-like session memory for logs if it doesn't exist
if "hvac_logs" not in st.session_state:
    st.session_state.hvac_logs = pd.DataFrame(columns=[
        "Date", "CH2_kWh", "CH3_kWh", "CH4_kWh", "CH5_kWh", "CH6_kWh", 
        "Avg_Indoor_Temp", "Avg_CO2", "Avg_RH", "TR_Stage", "Event_The_Fifth"
    ])

st.title("❄️ Power Plant Mall Cooling AI Optimizer")

# Create Navigation Tabs
tab1, tab2 = st.tabs(["📊 Dashboard & Forecast", "⚙️ Admin Data Entry"])

# ================= TAB 2: ADMIN DATA ENTRY =================
with tab2:
    st.header("📝 Daily Manual Log Entry Point")
    st.write("Operators can log daily 6:00 AM readings and afternoon averages here.")
    
    with st.form("log_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            log_date = st.date_input("Log Date")
            tr_stage = st.selectbox("Operating TR Stage Today", [1500, 2000, 2500, 3000, 3500], index=2)
            event_day = st.checkbox("Was there an event at 'The Fifth'?")
        with col2:
            st.markdown("**6:00 AM Chiller Consumption (Delta kWh)**")
            ch2 = st.number_input("Chiller 2 kWh used", min_value=0.0, value=0.0)
            ch3 = st.number_input("Chiller 3 kWh used", min_value=0.0, value=0.0)
            ch6 = st.number_input("Chiller 6 kWh used", min_value=0.0, value=0.0)
        with col3:
            st.markdown("**Daily Afternoon Averages (12PM - 6PM)**")
            in_temp = st.number_input("Indoor Temp (°C)", min_value=15.0, max_value=30.0, value=23.0)
            co2 = st.number_input("CO2 Levels (ppm)", min_value=300.0, max_value=2000.0, value=550.0)
            rh = st.number_input("Relative Humidity (%)", min_value=10.0, max_value=100.0, value=62.0)
            
        submit_btn = st.form_submit_button("Save Day's Logs to AI Database")
        
        if submit_btn:
            new_row = {
                "Date": log_date.strftime("%Y-%m-%d"), "CH2_kWh": ch2, "CH3_kWh": ch3, 
                "CH4_kWh": 0.0, "CH5_kWh": 0.0, "CH6_kWh": ch6, 
                "Avg_Indoor_Temp": in_temp, "Avg_CO2": co2, "Avg_RH": rh, 
                "TR_Stage": tr_stage, "Event_The_Fifth": "Yes" if event_day else "No"
            }
            st.session_state.hvac_logs = pd.concat([st.session_state.hvac_logs, pd.DataFrame([new_row])], ignore_index=True)
            st.success(f"Successfully saved data for {log_date.strftime('%Y-%m-%d')}!")

# ================= TAB 1: DASHBOARD & FORECAST =================
with tab1:
    # Calculate Wet-Bulb Temperature (Stull Formula)
    def calculate_wet_bulb(t, rh):
        tw = t * np.arctan(0.151977 * (rh + 8.313659)**0.5) + np.arctan(t + rh) - np.arctan(rh - 1.676331) + 0.00391838 * (rh**1.5) * np.arctan(0.023101 * rh) - 4.686035
        return tw

    @st.cache_data
    def get_weather_data():
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

    # VFD Frequency schedule mapping
    hz_map = {
        1500: {"primary": 40, "secondary": 28, "condenser": 42, "ct": 40},
        2000: {"primary": 45, "secondary": 28, "condenser": 44, "ct": 40},
        2500: {"primary": 33, "secondary": 28, "condenser": 35, "ct": 40},
        3000: {"primary": 50, "secondary": 35, "condenser": 50, "ct": 50},
        3500: {"primary": 60, "secondary": 45, "condenser": 60, "ct": 60}
    }

    st.sidebar.header("Real-Time Simulation Controls")
    current_tr_stage = st.sidebar.selectbox("Simulate Plant Load Stage", [1500, 2000, 2500, 3000, 3500], index=2)
    freqs = hz_map[current_tr_stage]

    def affinity_power(rated_kw, actual_hz):
        return rated_kw * ((actual_hz / 60.0) ** 3)

    p_primary = affinity_power(37, freqs["primary"])
    p_secondary = affinity_power(150, freqs["secondary"])
    p_condenser = affinity_power(100, freqs["condenser"])
    p_ct = affinity_power(55, freqs["ct"])

    st.subheader(f"Current Estimated Plant Status ({current_tr_stage} TR Stage)")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Primary CHW Pump", f"{p_primary:.1f} kW", f"{freqs['primary']} Hz")
    col2.metric("Secondary CHW Pump", f"{p_secondary:.1f} kW", f"{freqs['secondary']} Hz")
    col3.metric("Condenser Pump", f"{p_condenser:.1f} kW", f"{freqs['condenser']} Hz")
    col4.metric("Cooling Tower Fan", f"{p_ct:.1f} kW", f"{freqs['ct']} Hz")

    # Display Accumulated Database Logs
    st.markdown("---")
    st.subheader("📋 Logged Chiller History Database")
    if not st.session_state.hvac_logs.empty:
        st.dataframe(st.session_state.hvac_logs, use_container_width=True)
    else:
        st.info("No logs entered yet. Go to the 'Admin Data Entry' tab to log today's readings.")

    if df_weather is not None:
        st.markdown("---")
        st.subheader("ECMWF Dynamic Ambient vs Wet-Bulb Forecast (Next 7 Days)")
        st.line_chart(df_weather.set_index('time')[['temp', 'wet_bulb']])