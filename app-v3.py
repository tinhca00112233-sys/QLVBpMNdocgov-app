import streamlit as st
import pandas as pd
import numpy as np
import json
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="DocGov - Phường Mỹ Ngãi (GIS & SQLite Enabled)",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DATABASE SETUP & INITIALIZATION ---
DB_FILE = "docgov.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Table Khom Stats with GIS Coordinates
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS khom_stats (
        khom TEXT PRIMARY KEY,
        cu_tri_y_kien INTEGER,
        vneid_rate REAL,
        don_thu INTEGER,
        hai_long_rate REAL,
        lat REAL,
        lon REAL
    )
    """)
    
    # Check if lat/lon columns exist (for migration from v2)
    cursor.execute("PRAGMA table_info(khom_stats)")
    columns = [col[1] for col in cursor.fetchall()]
    if "lat" not in columns:
        cursor.execute("ALTER TABLE khom_stats ADD COLUMN lat REAL")
        cursor.execute("ALTER TABLE khom_stats ADD COLUMN lon REAL")
    
    # Seed or Update GIS Khom Stats
    coords_map = [
        ("Khóm 1", 5, 97.5, 1, 99.1, 10.4680, 105.6250),
        ("Khóm 2", 3, 96.0, 0, 98.5, 10.4710, 105.6280),
        ("Khóm 3", 8, 95.8, 2, 98.2, 10.4650, 105.6320),
        ("Khóm 4", 2, 98.2, 0, 99.5, 10.4750, 105.6350),
        ("Khóm 5", 6, 96.5, 1, 98.8, 10.4690, 105.6380),
        ("Khóm 6", 4, 95.0, 0, 98.0, 10.4620, 105.6290),
        ("Khóm 7", 7, 97.1, 1, 98.9, 10.4780, 105.6420),
        ("Khóm 8", 3, 96.8, 0, 99.0, 10.4730, 105.6450),
        ("Khóm 9", 5, 95.4, 0, 98.4, 10.4660, 105.6480),
        ("Khóm 10", 2, 98.0, 1, 99.2, 10.4810, 105.6310),
        ("Khóm 11", 4, 96.2, 0, 98.6, 10.4590, 105.6360),
        ("Khóm 12", 6, 95.9, 1, 98.7, 10.4840, 105.6400)
    ]
    
    for row in coords_map:
        cursor.execute("""
        INSERT INTO khom_stats (khom, cu_tri_y_kien, vneid_rate, don_thu, hai_long_rate, lat, lon)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(khom) DO UPDATE SET
            lat=excluded.lat,
            lon=excluded.lon,
            vneid_rate=excluded.vneid_rate,
            hai_long_rate=excluded.hai_long_rate
        """, row)
        
    # 2. Table Đại biểu HĐND
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dai_bieu_hdnd (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ho_ten TEXT,
        don_vi TEXT,
        chuc_vu TEXT,
        trang_thai TEXT
    )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM dai_bieu_hdnd")
    if cursor.fetchone()[0] == 0:
        db_list = []
        for i in range(21):
            ho_ten = f"Đại biểu Nguyễn Văn {chr(65+i)}"
            don_vi = f"Khóm {(i%12)+1}"
            chuc_vu = ["Trưởng Ban", "Phó Ban", "Ủy Viên", "Đại Biểu"][i % 4]
            trang_thai = "Đã có mặt" if i != 3 else "Vắng mặt (Có lý do)"
            db_list.append((ho_ten, don_vi, chuc_vu, trang_thai))
        cursor.executemany("INSERT INTO dai_bieu_hdnd (ho_ten, don_vi, chuc_vu, trang_thai) VALUES (?, ?, ?, ?)", db_list)

    # 3. Table Ý kiến cử tri (Kanban)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS y_kien_cu_tri (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        khom TEXT,
        noi_dung TEXT,
        giai_doan TEXT,
        ngay_tao TEXT
    )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM y_kien_cu_tri")
    if cursor.fetchone()[0] == 0:
        yk_list = [
            ("Khóm 3", "Sửa chữa đường đê bao nông nghiệp.", "1. Tiếp Nhận", "2026-09-10"),
            ("Khóm 5", "Nâng cấp hệ thống chiếu sáng hẻm 42.", "1. Tiếp Nhận", "2026-09-11"),
            ("Khóm 7", "Lắp đặt thùng rác công cộng.", "1. Tiếp Nhận", "2026-09-12"),
            ("Khóm 1", "Khảo sát địa chính khu đất công.", "2. Phân Công", "2026-09-08"),
            ("Khóm 8", "Kiểm tra thoát nước đường Mai Văn Khải.", "2. Phân Công", "2026-09-09"),
            ("Khóm 2", "Phản ánh tiếng ồn cơ sở sản xuất.", "3. Đang Xác Minh", "2026-09-05"),
            ("Khóm 10", "Cấp GCN QSDĐ dồn thửa đổi thửa.", "3. Đang Xác Minh", "2026-09-06"),
            ("Khóm 4", "Đã xử lý điểm sạt lở bờ kênh.", "4. Đã Giải Quyết", "2026-09-01"),
            ("Khóm 6", "Phát quang cây xanh che khuất tầm nhìn.", "4. Đã Giải Quyết", "2026-09-02"),
            ("Khóm 9", "Sửa chữa cầu nông nghiệp Khóm 9.", "4. Đã Giải Quyết", "2026-09-03"),
            ("Khóm 12", "Bố trí lại biển báo giao thông.", "4. Đã Giải Quyết", "2026-09-04")
        ]
        cursor.executemany("INSERT INTO y_kien_cu_tri (khom, noi_dung, giai_doan, ngay_tao) VALUES (?, ?, ?, ?)", yk_list)

    # 4. Table Đánh giá cán bộ
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS can_bo_danh_gia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ho_ten TEXT,
        chuc_danh TEXT,
        diem_so INTEGER,
        xep_loai TEXT,
        thang TEXT
    )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM can_bo_danh_gia")
    if cursor.fetchone()[0] == 0:
        cb_list = [
            ("Nguyễn Văn A", "Địa chính - Xây dựng", 98, "Xuất Sắc", "Tháng 09/2026"),
            ("Trần Thị B", "Tư pháp - Hộ tịch", 95, "Xuất Sắc", "Tháng 09/2026"),
            ("Lê Văn C", "Văn phòng - Thống kê", 88, "Tốt", "Tháng 09/2026"),
            ("Phạm Văn D", "Lao động - TBXH", 92, "Xuất Sắc", "Tháng 09/2026"),
            ("Hoàng Thị E", "Tài chính - Kế toán", 85, "Tốt", "Tháng 09/2026")
        ]
        cursor.executemany("INSERT INTO can_bo_danh_gia (ho_ten, chuc_danh, diem_so, xep_loai, thang) VALUES (?, ?, ?, ?, ?)", cb_list)

    # 5. Table Sổ tiếp công dân
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tiep_cong_dan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ngay TEXT,
        ho_ten TEXT,
        dia_chi TEXT,
        noi_dung TEXT,
        trang_thai TEXT
    )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM tiep_cong_dan")
    if cursor.fetchone()[0] == 0:
        tcd_list = [
            ("10/09/2026", "Nguyễn Văn X", "Khóm 2", "Khiếu nại ranh giới đất", "Đã thụ lý"),
            ("12/09/2026", "Trần Thị Y", "Khóm 5", "Kiến nghị tranh chấp ranh hẻm", "Đang xác minh")
        ]
        cursor.executemany("INSERT INTO tiep_cong_dan (ngay, ho_ten, dia_chi, noi_dung, trang_thai) VALUES (?, ?, ?, ?, ?)", tcd_list)

    conn.commit()
    conn.close()

init_db()

# --- CUSTOM CSS FOR GOVERNMENT STYLING ---
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    .main-header h1 {
        margin: 0;
        font-size: 26px;
        font-weight: 700;
        color: #ffffff;
    }
    .main-header p {
        margin: 5px 0 0 0;
        font-size: 14px;
        color: #e0e7ff;
    }
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        text-align: center;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #1e3a8a;
    }
    .metric-label {
        font-size: 13px;
        color: #4b5563;
        margin-top: 4px;
    }
    .kanban-card {
        background-color: white;
        padding: 10px;
        border-radius: 6px;
        margin-bottom: 8px;
        border-left: 4px solid #2563eb;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        white-space: pre-wrap;
        background-color: #f8fafc;
        border-radius: 6px 6px 0px 0px;
        padding-top: 10px;
        padding-bottom: 10px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e3a8a !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER SECTION ---
st.markdown("""
<div class="main-header">
    <div style="display: flex; align-items: center; justify-content: space-between;">
        <div>
            <h1>🏛️ TRUNG TÂM ĐIỀU HÀNH SỐ & QUẢN TRỊ CƠ SỞ (DOCGOV)</h1>
            <p>UBND PHƯỜNG MỸ NGÃI - THÀNH PHỐ CAO LÃNH - TỈNH ĐỒNG THÁP</p>
        </div>
        <div style="text-align: right; font-size: 13px; background: rgba(255,255,255,0.15); padding: 8px 15px; border-radius: 6px;">
            <b>🗺️ GIS 12 Khóm & SQLite Integrated</b><br>
            Cập nhật: Real-time (2026)
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- SIDEBAR NAVIGATION ---
st.sidebar.image("https://img.icons8.com/color/96/vietnam.png", width=60)
st.sidebar.title("DocGov Navigation")
st.sidebar.caption("Hệ thống Điều hành Số Phường Mỹ Ngãi")

menu = st.sidebar.radio(
    "Chọn Không Gian Nghiệp Vụ:",
    [
        "📊 Exec-Briefing & Bản Đồ GIS 12 Khóm",
        "🏛️ KG1: HĐND & Ý Kiến Cử Tri",
        "⚖️ KG2: Cán Bộ & CCHC",
        "🌐 KG3: Chuyển Đổi Số & GIS Đề Án 06",
        "🎓 KG4: Giáo Dục & Xã Hội Học Tập",
        "💾 CSDL SQLite & Báo Cáo Văn Bản"
    ]
)

# Helper function to build GIS map
def build_gis_map(df, color_col="vneid_rate", hover_title="VNeID Rate"):
    fig = px.scatter_mapbox(
        df,
        lat="lat",
        lon="lon",
        hover_name="Khóm",
        hover_data={
            "lat": False,
            "lon": False,
            "VNeID Mức 2 (%)": True,
            "Tỷ Lệ Hài Lòng (%)": True,
            "Cử Tri (Ý Kiến)": True,
            "Đơn Thư Khiếu Nại": True
        },
        color=color_col,
        size="Cử Tri (Ý Kiến)",
        size_max=22,
        color_continuous_scale="Viridis" if color_col == "vneid_rate" else "RdYlGn",
        zoom=13.2,
        center={"lat": 10.4720, "lon": 105.6360},
        title=f"Bản Đồ Địa Lý GIS 12 Khóm - Phường Mỹ Ngãi ({hover_title})"
    )
    fig.update_layout(
        mapbox_style="carto-positron",
        height=480,
        margin=dict(l=10, r=10, t=40, b=10)
    )
    return fig

# ==========================================
# 1. TỔNG QUAN EXECUTIVE BRIEFING & BẢN ĐỒ GIS
# ==========================================
if menu == "📊 Exec-Briefing & Bản Đồ GIS 12 Khóm":
    st.subheader("📌 Executive Briefing Mode - Bản Đồ Điều Hành GIS 12 Khóm")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown("""<div class="metric-card"><div class="metric-value">100/100</div><div class="metric-label">Điểm PAR Index</div></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""<div class="metric-card"><div class="metric-value">>92/100</div><div class="metric-label">Chỉ Số DTI Cấp Xã</div></div>""", unsafe_allow_html=True)
    with col3:
        st.markdown("""<div class="metric-card"><div class="metric-value">96.2%</div><div class="metric-label">Kích Hoạt VNeID Mức 2</div></div>""", unsafe_allow_html=True)
    with col4:
        st.markdown("""<div class="metric-card"><div class="metric-value">100%</div><div class="metric-label">Giải Quyết Hồ Sơ Đúng Hạn</div></div>""", unsafe_allow_html=True)
    with col5:
        st.markdown("""<div class="metric-card"><div class="metric-value">98.6%</div><div class="metric-label">Hài Lòng SIPAS</div></div>""", unsafe_allow_html=True)
        
    st.divider()
    
    # GIS MAP SECTION
    st.markdown("### 🗺️ Bản Đồ Tương Tác GIS Địa Lý 12 Khóm (Phường Mỹ Ngãi)")
    st.caption("Trực quan hóa chỉ số điều hành theo tọa độ địa lý thực tế của 12 Khóm trên nền địa hình OpenStreetMap")
    
    conn = get_db_connection()
    data_khom_gis = pd.read_sql_query("""
        SELECT khom AS 'Khóm', 
               cu_tri_y_kien AS 'Cử Tri (Ý Kiến)', 
               vneid_rate AS 'VNeID Mức 2 (%)', 
               don_thu AS 'Đơn Thư Khiếu Nại', 
               hai_long_rate AS 'Tỷ Lệ Hài Lòng (%)',
               lat, lon,
               vneid_rate, hai_long_rate
        FROM khom_stats
    """, conn)
    conn.close()
    
    map_mode = st.radio(
        "Chọn Lớp Dữ Liệu Hiển Thị Trên Bản Đồ GIS:",
        ["📱 Tỷ Lệ VNeID Mức 2 (%)", "😊 Tỷ Lệ Hài Lòng SIPAS (%)", "⚠️ Đơn Thư Khiếu Nại & Ý Kiến Cử Tri"],
        horizontal=True
    )
    
    col_map, col_table = st.columns([3, 2])
    with col_map:
        if "VNeID" in map_mode:
            fig_gis = build_gis_map(data_khom_gis, "vneid_rate", "Tỷ Lệ Kích Hoạt VNeID Mức 2")
        elif "Hài Lòng" in map_mode:
            fig_gis = build_gis_map(data_khom_gis, "hai_long_rate", "Chỉ Số Hài Lòng SIPAS")
        else:
            fig_gis = px.scatter_mapbox(
                data_khom_gis, lat="lat", lon="lon", hover_name="Khóm",
                hover_data={"Cử Tri (Ý Kiến)": True, "Đơn Thư Khiếu Nại": True},
                color="Đơn Thư Khiếu Nại", size="Cử Tri (Ý Kiến)", size_max=24,
                color_continuous_scale="OrRd", zoom=13.2, center={"lat": 10.4720, "lon": 105.6360},
                title="Bản Đồ GIS Cảnh Báo Đơn Thư Khiếu Nại & Ý Kiến Cử Tri"
            )
            fig_gis.update_layout(mapbox_style="carto-positron", height=480, margin=dict(l=10, r=10, t=40, b=10))
            
        st.plotly_chart(fig_gis, use_container_width=True)

    with col_table:
        st.markdown("##### 📋 Dữ Liệu Tọa Độ GIS 12 Khóm (SQLite)")
        st.dataframe(
            data_khom_gis[["Khóm", "VNeID Mức 2 (%)", "Tỷ Lệ Hài Lòng (%)", "Cử Tri (Ý Kiến)", "lat", "lon"]].style.highlight_max(axis=0, color="#dcfce7"),
            use_container_width=True,
            height=440
        )

# ==========================================
# 2. KHÔNG GIAN 1: HĐND & Ý KIẾN CỬ TRI
# ==========================================
elif menu == "🏛️ KG1: HĐND & Ý Kiến Cử Tri":
    st.subheader("🏛️ Không Gian 1: Hội Đồng Nhân Dân & Ý Kiến Cử Tri")
    
    tabs1, tabs2, tabs3, tabs4, tabs5 = st.tabs([
        "📋 21 Đại Biểu & QR Điểm Danh",
        "🗂️ Kanban Ý Kiến Cử Tri (Interactive)",
        "🤖 Trợ Lý Gov-Copilot (Luật Đất Đai 2024)",
        "📺 Smart TV 85\" Biểu Quyết",
        "📑 Sổ Tiếp Công Dân (Lưu SQLite)"
    ])
    
    with tabs1:
        st.markdown("#### Quản lý Danh sách 21 Đại biểu HĐND Phường Khóa XII (SQLite Connected)")
        
        conn = get_db_connection()
        db_df = pd.read_sql_query("SELECT id AS 'STT', ho_ten AS 'Họ và Tên', don_vi AS 'Đơn Vị Bầu Cử', chuc_vu AS 'Chức Vụ', trang_thai AS 'Trạng Thái' FROM dai_bieu_hdnd", conn)
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.dataframe(db_df, use_container_width=True, height=350)
            
            st.markdown("##### ✏️ Cập Nhật Trạng Thái Điểm Danh Đại Biểu")
            with st.form("update_diem_danh"):
                db_selected = st.selectbox("Chọn đại biểu:", db_df["Họ và Tên"].tolist())
                status_selected = st.selectbox("Trạng thái:", ["Đã có mặt", "Vắng mặt (Có lý do)", "Vắng mặt (Không lý do)"])
                btn_update = st.form_submit_button("Cập Nhật Vào SQLite")
                if btn_update:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE dai_bieu_hdnd SET trang_thai = ? WHERE ho_ten = ?", (status_selected, db_selected))
                    conn.commit()
                    st.success(f"✅ Đã cập nhật trạng thái của **{db_selected}** thành **'{status_selected}'** trong SQLite!")
                    st.rerun()
        conn.close()

        with c2:
            st.markdown("""
            <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;">
                <h4>📱 Mã QR Điểm Danh Điện Tử</h4>
                <p>Đại biểu quét QR bằng Điện thoại / Zalo để xác nhận có mặt</p>
                <img src="https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=DOCGOV_MYNGAI_DIEMDANH_HDND" width="160" />
                <br><br>
                <b>Thống Kê Tỷ Lệ Hiện Tại:</b>
                <h3 style="color: #16a34a; margin: 5px 0;">20/21 Có Mặt (95.2%)</h3>
            </div>
            """, unsafe_allow_html=True)

    with tabs2:
        st.markdown("#### Bảng Kanban Quản Lý Ý Kiến Cử Tri 12 Khóm")
        
        with st.expander("➕ **Thêm Ý Kiến Cử Tri Mới Vào CSDL**"):
            with st.form("add_ykien"):
                khom_f = st.selectbox("Chọn Khóm:", [f"Khóm {i}" for i in range(1, 13)])
                noi_dung_f = st.text_input("Nội dung phản ánh:")
                giai_doan_f = st.selectbox("Giai đoạn khởi tạo:", ["1. Tiếp Nhận", "2. Phân Công", "3. Đang Xác Minh", "4. Đã Giải Quyết"])
                if st.form_submit_button("Lưu Vào CSDL SQLite"):
                    if noi_dung_f:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        today_str = datetime.now().strftime("%Y-%m-%d")
                        cursor.execute("INSERT INTO y_kien_cu_tri (khom, noi_dung, giai_doan, ngay_tao) VALUES (?, ?, ?, ?)",
                                       (khom_f, noi_dung_f, giai_doan_f, today_str))
                        conn.commit()
                        conn.close()
                        st.success("✅ Đã ghi nhận ý kiến cử tri mới vào CSDL SQLite!")
                        st.rerun()

        conn = get_db_connection()
        ykien_df = pd.read_sql_query("SELECT * FROM y_kien_cu_tri", conn)
        conn.close()
        
        col_k1, col_k2, col_k3, col_k4 = st.columns(4)
        stages = [
            ("1. Tiếp Nhận", col_k1, "📥 1. Tiếp Nhận", "#2563eb"),
            ("2. Phân Công", col_k2, "👤 2. Phân Công", "#d97706"),
            ("3. Đang Xác Minh", col_k3, "🔍 3. Đang Xác Minh", "#9333ea"),
            ("4. Đã Giải Quyết", col_k4, "✅ 4. Đã Giải Quyết", "#16a34a")
        ]
        
        for stage_key, col_obj, stage_title, color in stages:
            with col_obj:
                items = ykien_df[ykien_df["giai_doan"] == stage_key]
                st.markdown(f"##### {stage_title} ({len(items)})")
                for _, row in items.iterrows():
                    st.markdown(f"""
                    <div class="kanban-card" style="border-left-color: {color};">
                        <b>{row['khom']}:</b> {row['noi_dung']}<br>
                        <small style="color: #6b7280;">Ngày: {row['ngay_tao']}</small>
                    </div>
                    """, unsafe_allow_html=True)

    with tabs3:
        st.markdown("#### 🤖 Trợ Lý Gov-Copilot: Trả Lời Ý Kiến Cử Tri")
        user_q = st.text_area("Nhập ý kiến cử tri cần xử lý:", "Cử tri Khóm 3 hỏi về thủ tục chuyển mục đích sử dụng đất nông nghiệp sang đất ở theo Luật Đất đai 2024 tại Phường Mỹ Ngãi?")
        if st.button("🚀 Gov-Copilot Phân Tích & Soạn Phản Hồi"):
            st.success("✅ Đã khởi tạo dự thảo phản hồi tự động bám sát Luật Đất đai 2024:")
            st.info("""
            **Kính gửi cử tri Khóm 3, Phường Mỹ Ngãi,**
            
            Căn cứ Luật Đất đai 2024 và Kế hoạch sử dụng đất hàng năm của TP. Cao Lãnh:
            1. **Điều kiện chuyển mục đích:** Thửa đất phải phù hợp với Quy hoạch sử dụng đất cấp thành phố đã được phê duyệt.
            2. **Trình tự thực hiện:** Nộp hồ sơ tại Bộ phận Một cửa Phường Mỹ Ngãi hoặc Dịch vụ công trực tuyến.
            3. **Hồ sơ gồm:** Đơn đăng ký biến động đất đai, Giấy chứng nhận QSDĐ hiện có, Bản vẽ trích đo địa chính.
            """)

    with tabs4:
        st.markdown("#### 📺 Màn Hình Trình Chiếu Biểu Quyết Smart TV 85\" (Fullscreen Mode)")
        st.markdown("""
        <div style="background-color: #0f172a; color: white; padding: 25px; border-radius: 12px; text-align: center;">
            <h2 style="color: #f59e0b;">NGHỊ QUYẾT HĐND PHƯỜNG MỸ NGÃI - KỲ HỌP THƯỜNG KỲ KHOÁ XII</h2>
            <p>Mã Nghị Quyết: NQ-HDND-2026-04 | V/v Thông qua Kế hoạch Phát triển Kinh tế - Xã hội năm 2026</p>
            <hr style="border-color: #334155;">
            <div style="display: flex; justify-content: space-around; margin: 20px 0;">
                <div>
                    <h1 style="color: #22c55e; font-size: 48px; margin: 0;">21 / 21</h1>
                    <p>TÁN THÀNH (100%)</p>
                </div>
                <div>
                    <h1 style="color: #ef4444; font-size: 48px; margin: 0;">0</h1>
                    <p>KHÔNG TÁN THÀNH (0%)</p>
                </div>
                <div>
                    <h1 style="color: #94a3b8; font-size: 48px; margin: 0;">0</h1>
                    <p>KHÔNG Ý KIẾN (0%)</p>
                </div>
            </div>
            <div style="background-color: #1e293b; padding: 15px; border-radius: 8px;">
                <h3 style="color: #4ade80; margin: 0;">🎉 KẾT QUẢ: NGHỊ QUYẾT ĐÃ ĐƯỢC THÔNG QUA VỚI TỶ LỆ 100% ĐẠI BIỂU TÁN THÀNH</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with tabs5:
        st.markdown("#### Sổ Tiếp Công Dân Điện Tử (Lưu Trữ SQLite)")
        conn = get_db_connection()
        tcd_df = pd.read_sql_query("SELECT id AS 'Mã Đơn', ngay AS 'Ngày', ho_ten AS 'Họ Tên Dân', dia_chi AS 'Địa Chỉ', noi_dung AS 'Nội Dung', trang_thai AS 'Trạng Thái' FROM tiep_cong_dan", conn)
        st.dataframe(tcd_df, use_container_width=True)
        
        with st.expander("➕ **Ghi Sổ Tiếp Công Dân Mới**"):
            with st.form("add_tcd"):
                ngay_t = st.date_input("Ngày tiếp:").strftime("%d/%m/%Y")
                ten_t = st.text_input("Họ tên công dân:")
                dc_t = st.selectbox("Khóm cư trú:", [f"Khóm {i}" for i in range(1, 13)])
                nd_t = st.text_area("Nội dung khiếu nại / kiến nghị:")
                tt_t = st.selectbox("Trạng thái thụ lý:", ["Đã thụ lý", "Đang xác minh", "Đã hướng dẫn", "Đã giải quyết xong"])
                if st.form_submit_button("Lưu Vào Sổ Tiếp Dân (SQLite)"):
                    if ten_t and nd_t:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO tiep_cong_dan (ngay, ho_ten, dia_chi, noi_dung, trang_thai) VALUES (?, ?, ?, ?, ?)",
                                       (ngay_t, ten_t, dc_t, nd_t, tt_t))
                        conn.commit()
                        st.success("✅ Đã ghi nhận đơn thư tiếp công dân mới vào SQLite!")
                        st.rerun()
        conn.close()

# ==========================================
# 3. KHÔNG GIAN 2: CÁN BỘ & CCHC
# ==========================================
elif menu == "⚖️ KG2: Cán Bộ & CCHC":
    st.subheader("⚖️ Không Gian 2: Cán Bộ, Công Chức & Cải Cách Hành Chính (CCHC)")
    
    tabs_c1, tabs_c2, tabs_c3, tabs_c4 = st.tabs([
        "📈 Dashboard Một Cửa & Nhiệm Vụ CCHC",
        "⭐ Chấm Điểm Công Chức (Lưu SQLite)",
        "📊 Bảng PAR Index (100 Điểm)",
        "🧪 What-If Simulator (Giả Lập CCHC)"
    ])
    
    with tabs_c1:
        st.markdown("#### Điều Hành Bộ Phận Một Cửa Real-Time")
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Tổng Hồ Sơ Tiếp Nhận", "1,248", "+12%")
        mc2.metric("Giải Quyết Trước/Đúng Hạn", "100%", "0%")
        mc3.metric("Tỷ Lệ Số Hóa Hồ Sơ", "99.8%", "+0.5%")
        mc4.metric("Chỉ Số SIPAS", "98.6%", "+0.2%")
        
        tasks_df = pd.DataFrame({
            "STT": range(1, 13),
            "Nhiệm Vụ CCHC": [
                "100% hồ sơ TTHC số hóa đầu vào", "Triển khai Kios tự phục vụ", "Tập huấn dịch vụ công trực tuyến",
                "Chuẩn hóa 100% quy trình ISO", "Chăm sóc khách hàng tự động", "Rà soát cắt giảm 20% thời gian giải quyết",
                "Số hóa kho lưu trữ lịch sử", "Thanh toán trực tuyến không dùng tiền mặt", "Đánh giá công chức tự động",
                "Tăng cường kiểm tra công vụ", "Cung cấp DVC toàn trình", "Diễn tập an toàn thông tin"
            ],
            "Tiến Độ": ["100%", "95%", "100%", "90%", "85%", "100%", "92%", "98%", "100%", "90%", "95%", "100%"],
            "Trạng Thái": ["Hoàn thành", "Đang chạy", "Hoàn thành", "Đang chạy", "Đang chạy", "Hoàn thành", "Đang chạy", "Đang chạy", "Hoàn thành", "Đang chạy", "Đang chạy", "Hoàn thành"]
        })
        st.dataframe(tasks_df, use_container_width=True)

    with tabs_c2:
        st.markdown("#### Chấm Điểm Đánh Giá Công Chức Hàng Tháng (SQLite)")
        col_cb1, col_cb2 = st.columns([1, 2])
        
        with col_cb1:
            can_bo_ten = st.text_input("Tên Công chức:", "Nguyễn Văn A")
            can_bo_chuc = st.selectbox("Chức danh:", ["Địa chính - Xây dựng", "Tư pháp - Hộ tịch", "Văn phòng - Thống kê", "Lao động - TBXH", "Tài chính - Kế toán"])
            score_cb = st.slider("Chấp hành giờ giấc (Max 10)", 0, 10, 10)
            score_hs = st.slider("Xử lý hồ sơ đúng hạn (Max 30)", 0, 30, 30)
            score_sk = st.slider("Sáng kiến CCHC cộng thêm", 0, 10, 5)
            late_deduct = st.number_input("Trừ điểm hồ sơ trễ hạn", 0, 20, 0)
            
            total_score = 55 + score_cb + score_hs + score_sk - late_deduct
            st.metric("Tổng Điểm Tính Toán", f"{total_score} / 100")
            
            xl_str = "Xuất Sắc" if total_score >= 90 else ("Tốt" if total_score >= 75 else "Hoàn Thành")
            
            if st.button("💾 Lưu Kết Quả Đánh Giá Vào SQLite"):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO can_bo_danh_gia (ho_ten, chuc_danh, diem_so, xep_loai, thang) VALUES (?, ?, ?, ?, ?)",
                               (can_bo_ten, can_bo_chuc, total_score, xl_str, "Tháng 09/2026"))
                conn.commit()
                conn.close()
                st.success(f"✅ Đã lưu kết quả đánh giá của **{can_bo_ten}** vào SQLite!")
                st.rerun()
                
        with col_cb2:
            conn = get_db_connection()
            cb_df = pd.read_sql_query("SELECT id AS 'Mã CB', ho_ten AS 'Cán Bộ', chuc_danh AS 'Chức Danh', diem_so AS 'Tổng Điểm', xep_loai AS 'Xếp Loại', thang AS 'Tháng' FROM can_bo_danh_gia ORDER BY id DESC", conn)
            conn.close()
            st.dataframe(cb_df, use_container_width=True, height=400)

    with tabs_c3:
        par_df = pd.DataFrame({
            "Lĩnh Vực Đánh Giá": [
                "1. Công tác chỉ đạo, điều hành CCHC", "2. Xây dựng và tổ chức thực hiện VBQPPL",
                "3. Cải cách thủ tục hành chính", "4. Cải cách tổ chức bộ máy",
                "5. Cải cách chế độ công vụ", "6. Cải cách tài chính công", "7. Xây dựng và phát triển Chính quyền số"
            ],
            "Điểm Tối Đa": [15, 10, 20, 10, 15, 10, 20],
            "Điểm Phường Tự Chấm": [15, 10, 20, 10, 15, 10, 20],
            "Kho Minh Chứng Số": ["MC_01.pdf", "MC_02.pdf", "MC_03.pdf", "MC_04.pdf", "MC_05.pdf", "MC_06.pdf", "MC_07.pdf"]
        })
        st.dataframe(par_df, use_container_width=True)
        st.success("🏆 Tổng Điểm PAR Index Phường Mỹ Ngãi Tự Chấm: 100 / 100 Điểm")

    with tabs_c4:
        st.markdown("#### 🧪 What-If Simulator: Bộ Giả Lập Kịch Bản Điều Hành CCHC")
        sim_dvc = st.slider("Tỷ lệ dịch vụ công trực tuyến toàn trình (%)", 50, 100, 95)
        sim_tre = st.slider("Số lượng hồ sơ trễ hạn phát sinh trong tháng", 0, 50, 0)
        calculated_sipas = 98.6 - (sim_tre * 0.2) + ((sim_dvc - 80) * 0.1)
        st.info(f"📊 Kết quả giả lập: Tỷ lệ DVC **{sim_dvc}%**, trễ hạn **{sim_tre}** -> SIPAS dự kiến: **{calculated_sipas:.2f}%**.")

# ==========================================
# 4. KHÔNG GIAN 3: CHUYỂN ĐỔI SỐ & GIS ĐỀ ÁN 06
# ==========================================
elif menu == "🌐 KG3: Chuyển Đổi Số & GIS Đề Án 06":
    st.subheader("🌐 Không Gian 3: Chuyển Đổi Số & Tích Hợp GIS Đề Án 06/CP")
    
    c_ds1, c_ds2 = st.columns(2)
    with c_ds1:
        st.markdown("#### 🗺️ Bản Đồ GIS 3 Tuyến Phố Không Dùng Tiền Mặt & Trường Học")
        
        # Spatial dataframe for streets and points of interest
        gis_poi = pd.DataFrame({
            "Tên Địa Điểm": [
                "Tuyến Phố Không Tiền Mặt Nguyễn Huệ",
                "Tuyến Phố Không Tiền Mặt Mai Văn Khải",
                "Tuyến Phố Không Tiền Mặt Điện Biên Phủ",
                "Trường Mầm Non Mỹ Ngãi (Chuẩn 1)",
                "Trường Tiểu Học Mỹ Ngãi (Chuẩn 2)",
                "Trường THCS Mỹ Ngãi (Chuẩn 1)"
            ],
            "Loại Hình": ["Tuyến Phố Số", "Tuyến Phố Số", "Tuyến Phố Số", "Trường Học", "Trường Học", "Trường Học"],
            "lat": [10.4670, 10.4720, 10.4760, 10.4650, 10.4710, 10.4780],
            "lon": [105.6270, 105.6390, 105.6330, 105.6260, 105.6370, 105.6410],
            "Thống Kê": ["100% Cửa hàng QR", "98.5% Tiểu thương", "99.0% Giao dịch số", "Đạt Chuẩn Mức 1", "Đạt Chuẩn Mức 2", "Đạt Chuẩn Mức 1"]
        })
        
        fig_poi = px.scatter_mapbox(
            gis_poi, lat="lat", lon="lon", hover_name="Tên Địa Điểm",
            hover_data={"Loại Hình": True, "Thống Kê": True, "lat": False, "lon": False},
            color="Loại Hình", size_max=18, zoom=13.0, center={"lat": 10.4720, "lon": 105.6360},
            title="Bản Đồ GIS Địa Lý Các Điểm Hạ Tầng Số & Trường Học"
        )
        fig_poi.update_layout(mapbox_style="carto-positron", height=420, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_poi, use_container_width=True)

    with c_ds2:
        st.markdown("#### 🛡️ Tiến Độ 7 Mô Hình Đề Án 06/CP Trọng Tâm")
        de_an_06 = pd.DataFrame({
            "Mô Hình Đề Án 06": [
                "1. Chi trả an sinh xã hội không dùng tiền mặt",
                "2. Số hóa dữ liệu hộ tịch lịch sử",
                "3. Tích hợp BHYT vào Căn cước công dân",
                "4. Khám chữa bệnh bằng CCCD gắn chip",
                "5. Quản lý lưu trú qua VNeID",
                "6. Mở tài khoản ngân hàng cho đối tượng yếu thế",
                "7. Số hóa hồ sơ cấp GCN QSDĐ"
            ],
            "Tỷ Lệ Hoàn Thành": ["100%", "100%", "98.5%", "99.0%", "96.2%", "95.0%", "92.0%"]
        })
        st.dataframe(de_an_06, use_container_width=True)

# ==========================================
# 5. KHÔNG GIAN 4: GIÁO DỤC & XÃ HỘI HỌC TẬP
# ==========================================
elif menu == "🎓 KG4: Giáo Dục & Xã Hội Học Tập":
    st.subheader("🎓 Không Gian 4: Giáo Dục Toàn Diện & Xã Hội Học Tập")
    
    col_edu1, col_edu2 = st.columns(2)
    with col_edu1:
        st.markdown("#### 🏫 Mạng Lưới Trường Học Đạt Chuẩn Quốc Gia")
        st.markdown("""
        * **Trường Mầm Non Mỹ Ngãi:** Đạt chuẩn quốc gia Mức độ 1.
        * **Trường Tiểu Học Mỹ Ngãi:** Đạt chuẩn quốc gia Mức độ 2.
        * **Trường THCS Mỹ Ngãi:** Đạt chuẩn quốc gia Mức độ 1.
        """)
        
        st.dataframe(pd.DataFrame({
            "Cấp Học / Bậc Học": ["Mầm non (5 tuổi)", "Tiểu học", "Trung học cơ sở", "Xóa mù chữ"],
            "Mức Độ Đạt Chuẩn": ["Đạt chuẩn Phổ cập", "Mức độ 3", "Mức độ 3", "Mức độ 2"],
            "Tỷ Lệ": ["100%", "99.8%", "98.5%", "99.2%"]
        }), use_container_width=True)

    with col_edu2:
        st.markdown("#### 🏅 Phong Trào Xã Hội Học Tập & Quỹ Khuyến Học")
        st.markdown("""
        * **Gia đình học tập:** 2,450 / 2,600 hộ (94.2%)
        * **Dòng họ học tập:** 18 / 18 Dòng họ (100%)
        * **Khóm học tập:** 12 / 12 Khóm (100%)
        * **Quỹ Khuyến Học Nguyễn Sinh Sắc Phường Mỹ Ngãi:**
          * Tổng quỹ vận động 2026: **350,000,000 VNĐ**
          * Số suất học bổng đã trao: **120 suất**
        """)
        st.image("https://img.icons8.com/color/96/graduation-cap.png", width=80)

# ==========================================
# 6. CSDL SQLITE & BÁO CÁO VĂN BẢN
# ==========================================
elif menu == "💾 CSDL SQLite & Báo Cáo Văn Bản":
    st.subheader("💾 Trình Quản Trị Cơ Sở Dữ Liệu SQLite & Xuất Văn Bản Hành Chính")
    
    col_db1, col_db2 = st.columns([1, 1])
    
    with col_db1:
        st.markdown("#### 🗄️ Kiểm Tra Tình Trạng CSDL SQLite (`docgov.db`)")
        if os.path.exists(DB_FILE):
            db_size = os.path.getsize(DB_FILE) / 1024
            st.success(f"✅ Tệp CSDL `docgov.db` hoạt động bình thường (Dung lượng: {db_size:.2f} KB)")
        else:
            st.error("❌ Chưa tìm thấy tệp CSDL SQLite!")
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        st.markdown(f"**Danh sách Bảng Dữ Liệu ({len(tables)} tables):**")
        selected_table = st.selectbox("Chọn bảng cần xem chi tiết dữ liệu:", tables)
        
        if selected_table:
            conn = get_db_connection()
            table_data = pd.read_sql_query(f"SELECT * FROM {selected_table}", conn)
            conn.close()
            st.dataframe(table_data, use_container_width=True)

        if os.path.exists(DB_FILE):
            with open(DB_FILE, "rb") as f:
                st.download_button(
                    label="📥 Tải File CSDL SQLite (`docgov.db`) Về Máy",
                    data=f,
                    file_name="docgov.db",
                    mime="application/x-sqlite3"
                )

    with col_db2:
        st.markdown("#### 🖨️ Xuất Văn Bản Chuẩn Thể Thức Hành Chính")
        doc_type = st.selectbox("Chọn mẫu văn bản cần xuất:", [
            "1. Báo cáo CCHC & Chỉ số PAR Index",
            "2. Phiếu chuyển tác chiến hỏa tốc",
            "3. Biên bản kỳ họp HĐND Phường",
            "4. Kết luận giám sát chuyên đề",
            "5. Giấy mời tiếp công dân",
            "6. Thông báo thụ lý đơn thư khiếu nại"
        ])
        
        if st.button("📥 Xuất Văn Bản Hành Chính Mẫu"):
            st.success(f"✅ Đã khởi tạo văn bản: **{doc_type}** chuẩn định dạng hành chính!")
            st.code(f"""
            UBND PHƯỜNG MỸ NGÃI                CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
            Bộ phận Một cửa                       Độc lập - Tự do - Hạnh phúc
            
            Số: .../BC-UBND                    Mỹ Ngãi, ngày {datetime.now().strftime('%d tháng %m năm %Y')}
            
                                 {doc_type.upper()}
            Kính gửi: Thường trực UBND TP. Cao Lãnh
            
            UBND Phường Mỹ Ngãi báo cáo nội dung chi tiết theo trích xuất dữ liệu từ CSDL SQLite docgov.db...
            """, language="markdown")

# --- FOOTER ---
st.divider()
st.caption("© 2026 DocGov Phường Mỹ Ngãi, TP. Cao Lãnh, Đồng Tháp. Tích hợp Bản đồ GIS 12 Khóm & CSDL SQLite vĩnh viễn.")
pip install nbconvert
jupyter nbconvert --to html ten_file.py

