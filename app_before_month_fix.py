from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="항만 컨테이너 물동량 대시보드",
    page_icon=":material/directions_boat:",
    layout="wide",
)


DATA_PATH = Path(__file__).parent / "data" / "외내항.csv"
CHART_HEIGHT = 340
SIZE_COLUMNS = {
    "컨테이너수(10피트)": "10피트",
    "컨테이너수(20피트)": "20피트",
    "컨테이너수(40피트)": "40피트",
    "컨테이너수(기타)": "기타",
}


@st.cache_data(show_spinner="데이터를 불러오는 중입니다...")
def load_data(path: Path) -> pd.DataFrame:
    """Load and prepare the source CSV."""
    frame = pd.read_csv(path, encoding="cp949")
    frame["기준월"] = pd.to_datetime(
        frame["연도"].astype(str)
        + "-"
        + frame["월"].astype(str).str.zfill(2)
    )
    return frame


def format_number(value: float) -> str:
    return f"{value:,.0f}"


def format_percent(value: float) -> str:
    return f"{value:.1f}%"


def share(numerator: float, denominator: float) -> float:
    return numerator / denominator * 100 if denominator else 0.0


def monthly_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.groupby("기준월", as_index=False)
        .agg(
            전체물동량=("전체물동량", "sum"),
            전체개수=("전체개수", "sum"),
        )
        .sort_values("기준월")
    )


def latest_mom(summary: pd.DataFrame) -> float | None:
    if len(summary) < 2:
        return None
    previous = summary.iloc[-2]["전체물동량"]
    current = summary.iloc[-1]["전체물동량"]
    if previous == 0:
        return None
    return (current / previous - 1) * 100


def line_chart(summary: pd.DataFrame, color: str | None = None) -> alt.Chart:
    encodings: dict[str, alt.Encoding] = {
        "x": alt.X(
            "월:O",
            title=None,
            sort="ascending",
            axis=alt.Axis(labelExpr="datum.label + '월'")
        ),
        "y": alt.Y(
            "전체물동량:Q",
            title="전체 물동량",
            axis=alt.Axis(format="~s"),
            scale=alt.Scale(zero=False),
        ),
        "tooltip": [
            alt.Tooltip("월:O", title="기준월")
            alt.Tooltip("전체물동량:Q", title="전체 물동량", format=",.0f"),
        ],
    }
    if color:
        encodings["color"] = alt.Color(
            f"{color}:N",
            title="청코드",
            legend=alt.Legend(orient="bottom"),
        )
        encodings["tooltip"].insert(1, alt.Tooltip(f"{color}:N", title="청코드"))

    return (
        alt.Chart(summary)
        .mark_line(point=alt.OverlayMarkDef(size=70), strokeWidth=3)
        .encode(**encodings)
        .properties(height=CHART_HEIGHT)
        .interactive(bind_y=False)
    )


def horizontal_bar_chart(
    data: pd.DataFrame,
    category: str,
    value: str,
    tooltip: list[alt.Tooltip],
) -> alt.Chart:
    return (
        alt.Chart(data)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X(f"{value}:Q", title="전체 물동량", axis=alt.Axis(format="~s")),
            y=alt.Y(
                f"{category}:N",
                title=None,
                sort=alt.EncodingSortField(field=value, order="descending"),
            ),
            color=alt.Color(
                f"{value}:Q",
                title=None,
                scale=alt.Scale(scheme="blues"),
                legend=None,
            ),
            tooltip=tooltip,
        )
        .properties(height=CHART_HEIGHT)
    )


if not DATA_PATH.exists():
    st.error(f"데이터 파일을 찾을 수 없습니다: {DATA_PATH}")
    st.stop()


df = load_data(DATA_PATH)

all_ports = sorted(df["청코드"].unique().tolist())
all_facilities = sorted(df["시설명"].unique().tolist())
all_trades = sorted(df["수출입구분명"].unique().tolist())
all_load_statuses = sorted(df["적공구분"].unique().tolist())


with st.sidebar:
    st.header(":material/filter_alt: 분석 조건")
    month_range = st.slider("월 범위", 1, 12, (1, 12))
    selected_ports = st.multiselect(
        "청코드",
        all_ports,
        default=all_ports,
    )
    selected_facilities = st.multiselect(
        "시설",
        all_facilities,
        placeholder="미선택 시 전체 시설",
    )
    selected_trades = st.multiselect(
        "수출입 구분",
        all_trades,
        default=all_trades,
    )
    selected_load_statuses = st.multiselect(
        "적공 구분",
        all_load_statuses,
        default=all_load_statuses,
    )

    if st.button(":material/restart_alt: 필터 초기화", width="stretch"):
        st.session_state.clear()
        st.rerun()

    st.divider()
    st.caption("원천 데이터: 외내항.csv · 2024년 외항 컨테이너 실적")


filtered = df[
    df["월"].between(month_range[0], month_range[1])
    & df["청코드"].isin(selected_ports)
    & df["수출입구분명"].isin(selected_trades)
    & df["적공구분"].isin(selected_load_statuses)
].copy()

if selected_facilities:
    filtered = filtered[filtered["시설명"].isin(selected_facilities)].copy()


st.title(":material/directions_boat: 항만 컨테이너 물동량 대시보드")
st.caption(
    f"2024년 {month_range[0]}월–{month_range[1]}월 · "
    "선택한 조건에 따라 KPI와 모든 차트가 함께 갱신됩니다."
)

if filtered.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다. 필터를 조정해 주세요.")
    st.stop()


month_chart_data = monthly_summary(filtered)
month_values = month_chart_data.copy()
month_values["월"] = month_values["기준월"].dt.month

month_chart_data = pd.DataFrame({
    "월": range(month_range[0], month_range[1] + 1)
})

month_chart_data = month_chart_data.merge(
    month_values[["월", "전체물동량"]],
    on="월",
    how="left"
)
total_volume = float(filtered["전체물동량"].sum())
total_containers = int(filtered["전체개수"].sum())
month_average = float(month_chart_data["전체물동량"].mean())
mom = latest_mom(month_chart_data)
transshipment_volume = float(
    filtered.loc[
        filtered["수출입구분명"].isin(["수출환적", "수입환적"]),
        "전체물동량",
    ].sum()
)
loaded_volume = float(
    filtered.loc[filtered["적공구분"].eq("적컨"), "전체물동량"].sum()
)
size_counts = filtered[list(SIZE_COLUMNS)].sum()
forty_foot_share = share(
    float(size_counts["컨테이너수(40피트)"]),
    float(size_counts.sum()),
)


with st.container(horizontal=True):
    st.metric(
        "전체 물동량",
        format_number(total_volume),
        border=True,
        chart_data=month_chart_data["전체물동량"].tolist(),
        chart_type="line",
    )
    st.metric("전체 컨테이너 개수", format_number(total_containers), border=True)
    st.metric("월평균 물동량", format_number(month_average), border=True)
    st.metric(
        "최근월 전월 대비",
        format_percent(mom) if mom is not None else "비교 불가",
        border=True,
    )
    st.metric(
        "환적 비중",
        format_percent(share(transshipment_volume, total_volume)),
        border=True,
    )
    st.metric(
        "적컨 비중",
        format_percent(share(loaded_volume, total_volume)),
        border=True,
    )
    st.metric("40피트 비중", format_percent(forty_foot_share), border=True)


st.subheader("물동량 추이")
trend_tab, port_trend_tab = st.tabs(["전체 월별 추이", "청코드별 월별 추이"])

with trend_tab:
    with st.container(border=True):
        st.altair_chart(line_chart(month_chart_data))

with port_trend_tab:
    port_month = (
        filtered.groupby(["기준월", "청코드"], as_index=False)
        .agg(전체물동량=("전체물동량", "sum"))
        .sort_values("기준월")
    )
    with st.container(border=True):
        st.altair_chart(line_chart(port_month, color="청코드"))


left, right = st.columns([3, 2])

with left:
    with st.container(border=True):
        st.subheader("시설별 물동량 TOP 10")
        facility_summary = (
            filtered.groupby("시설명", as_index=False)
            .agg(
                전체물동량=("전체물동량", "sum"),
                전체개수=("전체개수", "sum"),
            )
            .sort_values("전체물동량", ascending=False)
        )
        facility_summary["점유율"] = (
            facility_summary["전체물동량"] / total_volume * 100
        )
        facility_top10 = facility_summary.head(10)
        st.altair_chart(
            horizontal_bar_chart(
                facility_top10,
                "시설명",
                "전체물동량",
                [
                    alt.Tooltip("시설명:N", title="시설"),
                    alt.Tooltip("전체물동량:Q", title="전체 물동량", format=",.0f"),
                    alt.Tooltip("전체개수:Q", title="전체 개수", format=",.0f"),
                    alt.Tooltip("점유율:Q", title="점유율", format=".1f"),
                ],
            )
        )
        leader = facility_top10.iloc[0]
        st.caption(
            f"물동량 1위는 {leader['시설명']}이며 선택 범위의 "
            f"{leader['점유율']:.1f}%를 차지합니다."
        )

with right:
    with st.container(border=True):
        st.subheader("수출입·환적 구성")
        trade_summary = (
            filtered.groupby("수출입구분명", as_index=False)
            .agg(전체물동량=("전체물동량", "sum"))
            .sort_values("전체물동량", ascending=False)
        )
        trade_summary["비중"] = trade_summary["전체물동량"] / total_volume * 100
        trade_chart = (
            alt.Chart(trade_summary)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("수출입구분명:N", title=None, sort="-y"),
                y=alt.Y(
                    "전체물동량:Q",
                    title="전체 물동량",
                    axis=alt.Axis(format="~s"),
                ),
                color=alt.Color(
                    "수출입구분명:N",
                    title=None,
                    legend=None,
                    scale=alt.Scale(scheme="tableau10"),
                ),
                tooltip=[
                    alt.Tooltip("수출입구분명:N", title="구분"),
                    alt.Tooltip("전체물동량:Q", title="전체 물동량", format=",.0f"),
                    alt.Tooltip("비중:Q", title="비중", format=".1f"),
                ],
            )
            .properties(height=CHART_HEIGHT)
        )
        st.altair_chart(trade_chart)
        st.caption(
            f"환적 물동량은 {format_number(transshipment_volume)}이며 "
            f"전체의 {share(transshipment_volume, total_volume):.1f}%입니다."
        )


left, right = st.columns(2)

with left:
    with st.container(border=True):
        st.subheader("청코드별 적컨·공컨 비중")
        load_status = (
            filtered.groupby(["청코드", "적공구분"], as_index=False)
            .agg(전체물동량=("전체물동량", "sum"))
        )
        load_status["청코드합계"] = load_status.groupby("청코드")[
            "전체물동량"
        ].transform("sum")
        load_status["비중"] = load_status["전체물동량"] / load_status["청코드합계"]
        status_chart = (
            alt.Chart(load_status)
            .mark_bar()
            .encode(
                x=alt.X("청코드:N", title=None),
                y=alt.Y(
                    "비중:Q",
                    title="비중",
                    stack="zero",
                    axis=alt.Axis(format="%"),
                    scale=alt.Scale(domain=[0, 1]),
                ),
                color=alt.Color(
                    "적공구분:N",
                    title="적공 구분",
                    scale=alt.Scale(
                        domain=["적컨", "공컨"],
                        range=["#2878B5", "#F28E6B"],
                    ),
                ),
                order=alt.Order("적공구분:N", sort="descending"),
                tooltip=[
                    alt.Tooltip("청코드:N", title="청코드"),
                    alt.Tooltip("적공구분:N", title="구분"),
                    alt.Tooltip("전체물동량:Q", title="전체 물동량", format=",.0f"),
                    alt.Tooltip("비중:Q", title="비중", format=".1%"),
                ],
            )
            .properties(height=CHART_HEIGHT)
        )
        st.altair_chart(status_chart)

with right:
    with st.container(border=True):
        st.subheader("컨테이너 규격별 비중")
        size_summary = (
            size_counts.rename(index=SIZE_COLUMNS)
            .rename("컨테이너개수")
            .reset_index()
            .rename(columns={"index": "컨테이너규격"})
        )
        size_summary["비중"] = size_summary["컨테이너개수"] / size_summary[
            "컨테이너개수"
        ].sum()
        size_chart = (
            alt.Chart(size_summary)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("컨테이너규격:N", title=None, sort=None),
                y=alt.Y(
                    "비중:Q",
                    title="비중",
                    axis=alt.Axis(format="%"),
                ),
                color=alt.Color(
                    "컨테이너규격:N",
                    title=None,
                    legend=None,
                    scale=alt.Scale(scheme="blues"),
                ),
                tooltip=[
                    alt.Tooltip("컨테이너규격:N", title="규격"),
                    alt.Tooltip("컨테이너개수:Q", title="컨테이너 개수", format=",.0f"),
                    alt.Tooltip("비중:Q", title="비중", format=".2%"),
                ],
            )
            .properties(height=CHART_HEIGHT)
        )
        st.altair_chart(size_chart)


with st.container(border=True):
    st.subheader("시설별 상세 실적")
    detail = facility_summary.copy()
    detail["순위"] = range(1, len(detail) + 1)
    detail = detail[["순위", "시설명", "전체물동량", "전체개수", "점유율"]]
    st.dataframe(
        detail,
        hide_index=True,
        column_config={
            "전체물동량": st.column_config.NumberColumn(format="localized"),
            "전체개수": st.column_config.NumberColumn(format="localized"),
            "점유율": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )



