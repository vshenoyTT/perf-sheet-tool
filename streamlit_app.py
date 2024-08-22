import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# Streamlit application to analyze Tenstorrent performance sheets

st.title('Tenstorrent Perf Sheet Processor')
st.markdown("Calculate FPS and Adjusted Utilization, along with filtering a sheet to specific operations")

hide_decoration_bar_style = '''
    <style>
        header {visibility: hidden;}
    </style>
'''
st.markdown(hide_decoration_bar_style, unsafe_allow_html=True)

option = st.radio("Select Configuration:", ('Grayskull', 'Wormhole'))

core_count = 0
if option == 'Grayskull':
    core_count = 108
else:
    core_count = 64

#st.write(f"Selected configuration: {option}, Core Count: {core_count}")
st.write("")

# File uploader for excel or csv
uploaded_file = st.file_uploader("Upload an excel or csv performance sheet", type=["xlsx", "csv"])

if uploaded_file is not None:
    name = uploaded_file.name
    # Process an Excel file
    if ".xlsx" in name:
        df_excel = pd.read_excel(uploaded_file)

        # Insert three empty columns before "CORE COUNT"
        core_count_idx = df_excel.columns.get_loc('CORE COUNT')
        for i in range(3):
            df_excel.insert(core_count_idx, f'Empty {i+1}', '')

        # Calculate FPS for all operations and MatMul + Conv operations only
        filtered_df = df_excel[df_excel['OP CODE'].str.contains('matmul|conv', case=False, na=False)].copy()

        total_device_kernel_duration_ns_filtered = filtered_df['DEVICE KERNEL DURATION [ns]'].sum()
        total_device_kernel_duration_s_filtered = total_device_kernel_duration_ns_filtered * 1e-9

        total_device_kernel_duration_ns = df_excel['DEVICE KERNEL DURATION [ns]'].sum()
        total_device_kernel_duration_s = total_device_kernel_duration_ns * 1e-9

        fps_filtered = 1 / total_device_kernel_duration_s_filtered
        fps = 1 / total_device_kernel_duration_s

        # Create a sheet for other device operations
        other_device_ops_df = df_excel[
            (df_excel['OP TYPE'] == 'tt_dnn_device') &
            (~df_excel['OP CODE'].str.contains('matmult|conv', case=False, na=False))
        ].copy()

        total_device_kernel_duration_ns_other = other_device_ops_df['DEVICE KERNEL DURATION [ns]'].sum()
        total_device_kernel_duration_s_other = total_device_kernel_duration_ns_other * 1e-9
        fps_other = 1 / total_device_kernel_duration_s_other

        # Display FPS on interface
        st.write(f"FPS (MatMul/Conv Ops only): {round(fps_filtered, 3)}")
        st.write(f"FPS (Other On-Device Ops): {round(fps_other, 3)}")
        st.write(f"FPS (All Ops): {round(fps, 3)}")

        adjUtil = 'Adjusted Utilization = (PM ideal/device kernel duration)*(108/core count)'

        # Calculate Adjusted Utilization for the filtered data
        filtered_df[adjUtil] = ((filtered_df['PM IDEAL [ns]'] / filtered_df['DEVICE KERNEL DURATION [ns]']) * (core_count / filtered_df['CORE COUNT']) * 100)
        filtered_df[adjUtil] = filtered_df[adjUtil].replace([np.inf, -np.inf], np.nan).fillna(0)

        filtered_df[adjUtil] = filtered_df[adjUtil].astype(float)
        filtered_df[adjUtil] = filtered_df[adjUtil].astype(int).astype(str) + '%'
        filtered_df['FPS (matmul/conv ops only)'] = round(fps_filtered, 3)

        # Reorder columns for filtered data
        cols = list(filtered_df.columns)
        cols.remove('DEVICE KERNEL DURATION [ns]')
        cols.remove('CORE COUNT')
        cols.remove('Empty 1')
        cols.remove('Empty 2')
        cols.remove('Empty 3')
        cols.insert(cols.index(adjUtil), 'Empty 1')
        cols.insert(cols.index(adjUtil), 'Empty 2')
        cols.insert(cols.index(adjUtil), 'Empty 3')
        cols.insert(cols.index(adjUtil), 'CORE COUNT')
        cols.insert(cols.index(adjUtil), 'DEVICE KERNEL DURATION [ns]')
        filtered_df = filtered_df[cols]

        # Convert DataFrame --> Excel for filtered data
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            filtered_df.to_excel(writer, index=False, sheet_name='Processed Data')
        
        processed_data = output.getvalue()

        # Button to download the filtered file
        st.download_button(
            label="Download MatMul/Conv Performance Sheet",
            data=processed_data,
            file_name="filtered_perf_sheet.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        other_device_ops_df[adjUtil] = ((other_device_ops_df['PM IDEAL [ns]'] / other_device_ops_df['DEVICE KERNEL DURATION [ns]']) * (core_count / other_device_ops_df['CORE COUNT']) * 100)
        other_device_ops_df[adjUtil] = other_device_ops_df[adjUtil].replace([np.inf, -np.inf], np.nan).fillna(0)
        other_device_ops_df[adjUtil] = other_device_ops_df[adjUtil].astype(float)
        other_device_ops_df[adjUtil] = other_device_ops_df[adjUtil].astype(int).astype(str) + '%'
        other_device_ops_df['FPS (other device ops)'] = round(fps_other, 3)

        # Reorder columns for other device ops
        cols_other = list(other_device_ops_df.columns)
        cols_other.remove('DEVICE KERNEL DURATION [ns]')
        cols_other.remove('CORE COUNT')
        cols_other.remove('Empty 1')
        cols_other.remove('Empty 2')
        cols_other.remove('Empty 3')
        cols_other.insert(cols_other.index(adjUtil), 'Empty 1')
        cols_other.insert(cols_other.index(adjUtil), 'Empty 2')
        cols_other.insert(cols_other.index(adjUtil), 'Empty 3')
        cols_other.insert(cols_other.index(adjUtil), 'CORE COUNT')
        cols_other.insert(cols_other.index(adjUtil), 'DEVICE KERNEL DURATION [ns]')
        other_device_ops_df = other_device_ops_df[cols_other]

        output_other_device_ops = BytesIO()
        with pd.ExcelWriter(output_other_device_ops, engine='xlsxwriter') as writer:
            other_device_ops_df.to_excel(writer, index=False, sheet_name='Other Device Ops')
        other_device_ops_data = output_other_device_ops.getvalue()

        # Button to download the other device operations file
        st.download_button(
            label="Download Other On-Device Operations Sheet",
            data=other_device_ops_data,
            file_name="other_device_ops_perf_sheet.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        # Create a simple DataFrame with overall FPS + Adj Util
        overall_df = df_excel.copy()
        overall_df['FPS (all ops)'] = round(fps, 3)
        overall_df['FPS (matmul/conv ops only)'] = round(fps_filtered, 3)
        overall_df[adjUtil] = ((overall_df['PM IDEAL [ns]'] / overall_df['DEVICE KERNEL DURATION [ns]']) * (core_count / overall_df['CORE COUNT']) * 100)
        overall_df[adjUtil] = overall_df[adjUtil].replace([np.inf, -np.inf], np.nan).fillna(0)
        overall_df[adjUtil] = overall_df[adjUtil].astype(float)
        overall_df[adjUtil] = overall_df[adjUtil].astype(int).astype(str) + '%'
        overall_df = overall_df[cols]
        overall_df['FPS (all ops)'] = round(fps, 3)

        output_overall = BytesIO()
        with pd.ExcelWriter(output_overall, engine='xlsxwriter') as writer:
            overall_df.to_excel(writer, index=False, sheet_name='Overall Data')
        overall_data = output_overall.getvalue()

        # Button to download the full file
        st.download_button(
            label="Download Full Performance Sheet",
            data=overall_data,
            file_name="full_perf_sheet.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
    # Process a CSV file
    if ".csv" in name:
        df_csv = pd.read_csv(uploaded_file)

        # Insert three empty columns before "CORE COUNT"
        core_count_idx = df_csv.columns.get_loc('CORE COUNT')
        for i in range(3):
            df_csv.insert(core_count_idx, f'Empty {i+1}', '')

        # Calculate FPS for all operations and MatMul + Conv operations only
        filtered_df = df_csv[df_csv['OP CODE'].str.contains('matmul|conv', case=False, na=False)].copy()

        total_device_kernel_duration_ns_filtered = filtered_df['DEVICE KERNEL DURATION [ns]'].sum()
        total_device_kernel_duration_s_filtered = total_device_kernel_duration_ns_filtered * 1e-9

        total_device_kernel_duration_ns = df_csv['DEVICE KERNEL DURATION [ns]'].sum()
        total_device_kernel_duration_s = total_device_kernel_duration_ns * 1e-9

        fps_filtered = 1 / total_device_kernel_duration_s_filtered
        fps = 1 / total_device_kernel_duration_s

        # Create a sheet for other device operations
        other_device_ops_df = df_csv[
            (df_csv['OP TYPE'] == 'tt_dnn_device') &
            (~df_csv['OP CODE'].str.contains('matmult|conv', case=False, na=False))
        ].copy()

        total_device_kernel_duration_ns_other = other_device_ops_df['DEVICE KERNEL DURATION [ns]'].sum()
        total_device_kernel_duration_s_other = total_device_kernel_duration_ns_other * 1e-9
        fps_other = 1 / total_device_kernel_duration_s_other

        # Display FPS on interface
        st.write(f"FPS (MatMul/Conv Ops only): {round(fps_filtered, 3)}")
        st.write(f"FPS (Other Device Ops): {round(fps_other, 3)}")
        st.write(f"FPS (All Ops): {round(fps, 3)}")

        adjUtil = 'Adjusted Utilization = (PM ideal/device kernel duration)*(108/core count)'

        # Calculate Adjusted Utilization for the filtered data
        filtered_df[adjUtil] = ((filtered_df['PM IDEAL [ns]'] / filtered_df['DEVICE KERNEL DURATION [ns]']) * (core_count / filtered_df['CORE COUNT']) * 100)
        filtered_df[adjUtil] = filtered_df[adjUtil].replace([np.inf, -np.inf], np.nan).fillna(0)

        filtered_df[adjUtil] = filtered_df[adjUtil].astype(float)
        filtered_df[adjUtil] = filtered_df[adjUtil].astype(int).astype(str) + '%'
        filtered_df['FPS (matmul/conv ops only)'] = round(fps_filtered, 3)

        # Reorder columns for filtered data
        cols = list(filtered_df.columns)
        cols.remove('DEVICE KERNEL DURATION [ns]')
        cols.remove('CORE COUNT')
        cols.remove('Empty 1')
        cols.remove('Empty 2')
        cols.remove('Empty 3')
        cols.insert(cols.index(adjUtil), 'Empty 1')
        cols.insert(cols.index(adjUtil), 'Empty 2')
        cols.insert(cols.index(adjUtil), 'Empty 3')
        cols.insert(cols.index(adjUtil), 'CORE COUNT')
        cols.insert(cols.index(adjUtil), 'DEVICE KERNEL DURATION [ns]')
        filtered_df = filtered_df[cols]

        # Convert DataFrame --> CSV for filtered data
        output = BytesIO()
        processed_data = filtered_df.to_csv(index=False)

        # Button to download the filtered file
        st.download_button(
            label="Download MatMul/Conv Performance Sheet",
            data=processed_data,
            file_name="filtered_perf_sheet.csv",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        other_device_ops_df[adjUtil] = ((other_device_ops_df['PM IDEAL [ns]'] / other_device_ops_df['DEVICE KERNEL DURATION [ns]']) * (core_count / other_device_ops_df['CORE COUNT']) * 100)
        other_device_ops_df[adjUtil] = other_device_ops_df[adjUtil].replace([np.inf, -np.inf], np.nan).fillna(0)
        other_device_ops_df[adjUtil] = other_device_ops_df[adjUtil].astype(float)
        other_device_ops_df[adjUtil] = other_device_ops_df[adjUtil].astype(int).astype(str) + '%'
        other_device_ops_df['FPS (other device ops)'] = round(fps_other, 3)

        # Reorder columns for other device ops
        cols_other = list(other_device_ops_df.columns)
        cols_other.remove('DEVICE KERNEL DURATION [ns]')
        cols_other.remove('CORE COUNT')
        cols_other.remove('Empty 1')
        cols_other.remove('Empty 2')
        cols_other.remove('Empty 3')
        cols_other.insert(cols_other.index(adjUtil), 'Empty 1')
        cols_other.insert(cols_other.index(adjUtil), 'Empty 2')
        cols_other.insert(cols_other.index(adjUtil), 'Empty 3')
        cols_other.insert(cols_other.index(adjUtil), 'CORE COUNT')
        cols_other.insert(cols_other.index(adjUtil), 'DEVICE KERNEL DURATION [ns]')
        other_device_ops_df = other_device_ops_df[cols_other]

        output_other_device_ops = BytesIO()
        other_device_ops_data = filtered_df.to_csv(index=False)

        # Button to download the other device operations file
        st.download_button(
            label="Download Other Device Operations Sheet",
            data=other_device_ops_data,
            file_name="other_device_ops_perf_sheet.csv",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        # Create a simple DataFrame with overall FPS + Adj Util
        overall_df = df_csv.copy()
        overall_df['FPS (all ops)'] = round(fps, 3)
        overall_df['FPS (matmul/conv ops only)'] = round(fps_filtered, 3)
        overall_df[adjUtil] = ((overall_df['PM IDEAL [ns]'] / overall_df['DEVICE KERNEL DURATION [ns]']) * (core_count / overall_df['CORE COUNT']) * 100)
        overall_df[adjUtil] = overall_df[adjUtil].replace([np.inf, -np.inf], np.nan).fillna(0)
        overall_df[adjUtil] = overall_df[adjUtil].astype(float)
        overall_df[adjUtil] = overall_df[adjUtil].astype(int).astype(str) + '%'
        overall_df = overall_df[cols]
        overall_df['FPS (all ops)'] = round(fps, 3)

        output_overall = BytesIO()
        overall_data = filtered_df.to_csv(index=False)

        # Button to download the full file
        st.download_button(
            label="Download Full Performance Sheet",
            data=overall_data,
            file_name="full_perf_sheet.csv",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )