import streamlit as st
import requests
import pandas as pd
import numpy as np
import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="PPM HVAC AI Optimizer", layout="wide")

st.title("Power Plant Mall HVAC Predictive Optimizer")
st.write("Dynamic physics-based asset allocation mapped against live ECMWF weather forecasts.")

# -------------------------------------------------------------
# Live GMT+8 Clock
# -------------------------------------------------------------
clock_html = """
<div id="clock" style="font-family: sans-serif; font-size: 16px; font-weight: bold; color: #1f77b4; padding-bottom: 10px;"></div>
<script>
    function updateTime() {
        let d = new Date();
        let optionsTime = { timeZone: 'Asia/Manila', hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' };
        let optionsDate = { timeZone: 'Asia/Manila', year: 'numeric', month: '2-digit', day: '2-digit' };
        let timeString = new Intl.DateTimeFormat('en-US', optionsTime).format(d);
        let dateString = new Intl.DateTimeFormat('en-US', optionsDate).format(d);
        document.getElementById('clock').innerText = "Current PH Time: " + dateString + " " + timeString + " (GMT+8)";
    }
    setInterval(updateTime, 1000);
    updateTime();
</script>
"""
components.html(clock_html, height=40)

# 1. Weather Fetch & Wet-Bulb Calculations
def calculate_wet_bulb(t, rh):
    tw = t * np.arctan(0.151977 * (rh + 8.313659)**0.5) + np.arctan(t + rh) - np.arctan(rh - 1.676331) + 0.00391838 * (rh**1.5) * np.arctan(0.023101 * rh) - 4.686035
    return tw

@st.cache_data(ttl="1h")
def get_weather_data():
    url = "https://api.open-meteo.com/v1/ecmwf?latitude=14.56&longitude=121.04&hourly=temperature_2m,relative_humidity_2m&timezone=Asia%2FSingapore"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data['hourly'])
        df['time'] = pd.to_datetime(df['time'])
        df.rename(columns={'temperature_2m': 'temp', 'relative_humidity_2m': 'rh'}, inplace=True)
        df['wet_bulb'] = calculate_wet_bulb(df['temp'], df['rh']).round(2)
        df['temp'] = df['temp'].round(2)
        return df
    return None

df_weather = get_weather_data()

# ================= SIDEBAR INPUTS =================
st.sidebar.header("🗓️ Tomorrow's Operational Inputs")
has_event = st.sidebar.checkbox("Event scheduled at 'The Fifth' tomorrow?", value=False)

# Target Tomorrow's Time Horizon (GMT+8 Aware)
ph_tz = datetime.timezone(datetime.timedelta(hours=8))
now_ph = datetime.datetime.now(ph_tz)
tomorrow = now_ph.date() + datetime.timedelta(days=1)
tomorrow_weekday = tomorrow.weekday()

# Automated Schedule Adjustments
if tomorrow_weekday == 5: # Saturday
    day_label = "Saturday"
    mall_open = "10:00 AM"
    full_load_init = "9:00 AM"
    reduce_load = "9:00 PM"
elif tomorrow_weekday == 6: # Sunday
    day_label = "Sunday"
    mall_open = "10:00 AM"
    full_load_init = "9:00 AM"
    reduce_load = "8:00 PM"
else:
    day_label = "Weekday (Mon-Fri)"
    mall_open = "11:00 AM"
    full_load_init = "10:00 AM"
    reduce_load = "8:00 PM"

if df_weather is not None:
    df_tomorrow = df_weather[df_weather['time'].dt.date == tomorrow]
    
    if not df_tomorrow.empty:
        peak_temp = df_tomorrow['temp'].max()
        min_wb = df_tomorrow['wet_bulb'].min()
        avg_wb_midday = df_tomorrow[(df_tomorrow['time'].dt.hour >= 11) & (df_tomorrow['time'].dt.hour <= 18)]['wet_bulb'].mean()
        
        # --- CUSTOM TAILORED RULES ENGINE ---
        if has_event:
            predicted_tr = 3000
            reasoning = "Active event scheduled at 'The Fifth'. High occupancy heat load override active."
        elif peak_temp < 23.0:
            predicted_tr = 2000
            reasoning = f"Favorable outdoor conditions predicted (Peak: {peak_temp:.2f}°C). Safely scaled down to 2000 TR."
        else:
            predicted_tr = 2500
            reasoning = f"Standard operation baseline. Outdoor peak temperature: {peak_temp:.2f}°C."

        # --- DYNAMIC PHYSICS POWER MAPPING ---
        # Base asset configurations matching your motor data inputs
        if predicted_tr == 2000:
            active_towers = 4 if avg_wb_midday < 24.0 else 5
            ct_hz = 40.0
            pri_pump_kw = 37.0; pri_hz = 45.0  # Baldor 37 kW
            sec_pump_kw = 150.0; sec_hz = 32.0 # Baldor 150 kW (throttled down)
            cnd_pump_kw = 100.0; cnd_hz = 40.0 # Baldor 100 kW
        elif predicted_tr == 2500:
            active_towers = 5
            ct_hz = 42.0
            pri_pump_kw = 37.0; pri_hz = 48.0
            sec_pump_kw = 150.0; sec_hz = 38.0
            cnd_pump_kw = 100.0; cnd_hz = 44.0
        else: # 3000 TR
            active_towers = 5
            ct_hz = 50.0
            pri_pump_kw = 55.0; pri_hz = 50.0  # Scaled up to WEG 55 kW pump
            sec_pump_kw = 150.0; sec_hz = 45.0
            cnd_pump_kw = 100.0; cnd_hz = 50.0

        # Fluid Affinity Cubic Math Functions: Power = Rated_Power * (Hz / 50)^3
        def compute_affinity_kw(rated_kw, target_hz):
            return rated_kw * ((target_hz / 50.0) ** 3)

        actual_pri_kw = compute_affinity_kw(pri_pump_kw, pri_hz)
        actual_sec_kw = compute_affinity_kw(sec_pump_kw, sec_hz)
        actual_cnd_kw = compute_affinity_kw(cnd_pump_kw, cnd_hz)
        actual_ct_kw = compute_affinity_kw(55.0, ct_hz) * active_towers
        
        # Calculate potential optimization baseline differences vs full 50Hz lockdown
        baseline_unoptimized_kw = pri_pump_kw + sec_pump_kw + cnd_pump_kw + (55.0 * 5)
        optimized_total_kw = actual_pri_kw + actual_sec_kw + actual_cnd_kw + actual_ct_kw
        estimated_kw_savings = max(0.0, baseline_unoptimized_kw - optimized_total_kw)

        # Display Strategy Panels
        st.success(f"### 🎯 Target Profile: {predicted_tr} TR Stage ({tomorrow.strftime('%m/%d/%Y')})")
        st.caption(f"**AI Strategy Analysis:** {reasoning}")
        
        # Layout Results Blocks
        st.markdown("### ⚙️ Dispatch Schedule Guide & VFD Settings")
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"📌 **Chiller Startup Sequences ({day_label})**\n"
                    "* **06:30 Precooling:** Start **Chiller 2 or Chiller 3** (1000 TR Clivet Magnetic Centrifugal) to capture low-lift advantages.\n"
                    f"* **{full_load_init} Pre-Load:** Initialize full {predicted_tr} TR target configuration 1 hour before doors open.\n"
                    f"* **{reduce_load} Drop Step:** Shed secondary load units down to exactly **1000 TR**.\n"
                    "* **Closing Target:** Shutdown complete roofdeck central plant after cinema/event clear.")
        with col2:
            st.metric("Recommended Active Cooling Towers", f"{active_towers} Cells", f"Target Speed: {ct_hz:.1f} Hz")
            st.caption(f"**Optimization Safeguard:** If dropping to {ct_hz:.1f} Hz causes your Condenser Entering Water Temp (CEWT) to rise above **30.5°C**, scale fans back up to 50 Hz immediately.")

        st.markdown("#### Calculated VFD Outputs & Power Consumption Profiles")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Primary Pumps", f"{pri_hz:.1f} Hz", f"Est: {actual_pri_kw:.1f} kW")
        c2.metric("Secondary Pumps", f"{sec_hz:.1f} Hz", f"Est: {actual_sec_kw:.1f} kW")
        c3.metric("Condenser Pumps", f"{cnd_hz:.1f} Hz", f"Est: {actual_cnd_kw:.1f} kW")
        c4.metric("Total CT Fan Power", f"{ct_hz:.1f} Hz", f"Est: {actual_ct_kw:.1f} kW Total")
        
        st.metric("⚡ Estimated Plant Demand Side Savings Rate", f"{estimated_kw_savings:.2f} kW Lower than Baseline Floor")

        st.markdown("---")
        st.subheader(f"📊 Tomorrow's Hourly Temperature Profiles (°C) - {tomorrow.strftime('%m/%d/%Y')}")
        st.line_chart(df_tomorrow.set_index('time')[['temp', 'wet_bulb']])
        
    else:
        st.warning("Weather profile formatting next-day sequence data bounds...")
        
    st.markdown("---")
    st.subheader("🗓️ Continuous 7-Day Context Forecast (°C)")
    st.line_chart(df_weather.set_index('time')['temp'])
else:
    st.error("Unable to capture target forecasting streams from ECMWF servers.")