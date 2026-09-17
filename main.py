import streamlit as st
import pandas as pd
import itertools
import re
import plotly.express as px

# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="급식 규칙 찾기",
    page_icon="🍚",
    layout="wide"
)

DATA_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/danggok_meals_184.csv"


# =========================================================
# 제목
# =========================================================

st.title("🍚 급식 규칙 찾기")
st.caption("당곡고 중식 데이터를 이용해 함께 등장하는 메뉴의 규칙을 찾아봅니다.")


# =========================================================
# 데이터 불러오기
# =========================================================

@st.cache_data
def load_data():
    df = pd.read_csv(
        DATA_URL,
        encoding="utf-8"
    )

    # 날짜를 날짜 형식으로 변환
    df["날짜"] = pd.to_datetime(
        df["날짜"].astype(str),
        format="%Y%m%d",
        errors="coerce"
    )

    return df


try:
    df = load_data()
except Exception as e:
    st.error("CSV 데이터를 불러오는 데 실패했습니다.")
    st.exception(e)
    st.stop()


# =========================================================
# 메뉴 전처리
# =========================================================

def clean_menu(menu):
    """
    메뉴 이름에서 괄호와 괄호 안의 내용을 제거한다.

    예:
    오징어초무침(무x,부찬)
    -> 오징어초무침

    돈까스샐러드(허니소스)
    -> 돈까스샐러드
    """

    if pd.isna(menu):
        return ""

    menu = str(menu)

    # 소괄호와 그 안의 내용 제거
    menu = re.sub(r"\([^)]*\)", "", menu)

    # 앞뒤 공백 제거
    menu = menu.strip()

    return menu


# =========================================================
# 하루 = 하나의 장바구니
# =========================================================

baskets = []

for _, row in df.iterrows():

    menu_text = row["메뉴"]

    if pd.isna(menu_text):
        continue

    # | 기준으로 메뉴 분리
    menus = str(menu_text).split("|")

    # 괄호 제거
    menus = [clean_menu(menu) for menu in menus]

    # 빈 메뉴 제거
    menus = [menu for menu in menus if menu]

    # 같은 날 같은 메뉴가 중복으로 들어간 경우 한 번만 계산
    menus = sorted(set(menus))

    if menus:
        baskets.append(menus)


# =========================================================
# 메뉴별 등장 횟수
# =========================================================

menu_count = {}

for basket in baskets:
    for menu in basket:
        menu_count[menu] = menu_count.get(menu, 0) + 1


total_days = len(baskets)
menu_type_count = len(menu_count)


# =========================================================
# 메뉴 쌍 계산
# =========================================================

pair_count = {}

for basket in baskets:

    # 한 장바구니 안에서 가능한 모든 메뉴 조합
    for a, b in itertools.combinations(basket, 2):

        pair = tuple(sorted([a, b]))

        pair_count[pair] = pair_count.get(pair, 0) + 1


# =========================================================
# 연관 규칙 계산
# =========================================================

rules = []

for (a, b), together_count in pair_count.items():

    # -----------------------------------------
    # A -> B
    # -----------------------------------------

    support = together_count / total_days

    confidence_a_b = together_count / menu_count[a]

    # 향상도 = 신뢰도 / 결과 메뉴의 지지도
    lift_a_b = confidence_a_b / (menu_count[b] / total_days)

    rules.append({
        "조건": a,
        "결과": b,
        "동시": together_count,
        "지지도": support,
        "신뢰도": confidence_a_b,
        "향상도": lift_a_b
    })

    # -----------------------------------------
    # B -> A
    # -----------------------------------------

    confidence_b_a = together_count / menu_count[b]

    lift_b_a = confidence_b_a / (menu_count[a] / total_days)

    rules.append({
        "조건": b,
        "결과": a,
        "동시": together_count,
        "지지도": support,
        "신뢰도": confidence_b_a,
        "향상도": lift_b_a
    })


rules_df = pd.DataFrame(rules)


# =========================================================
# 메뉴 선택
# =========================================================

st.subheader("🔎 메뉴별 규칙 찾기")

menu_options = ["전체 메뉴"] + sorted(menu_count.keys())

selected_menu = st.selectbox(
    "메뉴를 선택하면 해당 메뉴가 포함된 규칙만 볼 수 있습니다.",
    menu_options
)


# =========================================================
# 정렬 기준
# =========================================================

sort_option = st.selectbox(
    "정렬 기준",
    ["향상도 순", "신뢰도 순", "동시 순"]
)

if sort_option == "향상도 순":
    rules_df = rules_df.sort_values(
        by=["향상도", "신뢰도", "동시"],
        ascending=[False, False, False]
    )

elif sort_option == "신뢰도 순":
    rules_df = rules_df.sort_values(
        by=["신뢰도", "향상도", "동시"],
        ascending=[False, False, False]
    )

else:
    rules_df = rules_df.sort_values(
        by=["동시", "향상도", "신뢰도"],
        ascending=[False, False, False]
    )


# =========================================================
# 메뉴 필터
# =========================================================

if selected_menu != "전체 메뉴":

    filtered_rules = rules_df[
        (rules_df["조건"] == selected_menu) |
        (rules_df["결과"] == selected_menu)
    ].copy()

else:

    filtered_rules = rules_df.copy()


# =========================================================
# 상단 요약 정보
# =========================================================

unique_pairs = len(pair_count)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "급식 일수",
        f"{total_days}일"
    )

with col2:
    st.metric(
        "메뉴 종류 수",
        f"{menu_type_count}개"
    )

with col3:
    st.metric(
        "함께 나온 메뉴 쌍",
        f"{unique_pairs}쌍"
    )


# =========================================================
# 규칙 표
# =========================================================

st.subheader("📋 급식 규칙")

if filtered_rules.empty:

    st.warning("선택한 조건에 해당하는 규칙이 없습니다.")

else:

    display_df = filtered_rules.copy()

    # 보기 좋은 형태로 변경
    display_df["지지도"] = display_df["지지도"].map(
        lambda x: f"{x:.2%}"
    )

    display_df["신뢰도"] = display_df["신뢰도"].map(
        lambda x: f"{x:.2%}"
    )

    display_df["향상도"] = display_df["향상도"].map(
        lambda x: f"{x:.3f}"
    )

    st.dataframe(
        display_df[
            [
                "조건",
                "결과",
                "동시",
                "지지도",
                "신뢰도",
                "향상도"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# 향상도 TOP 10 그래프
# =========================================================

st.subheader("📊 향상도 상위 10개 규칙")

if filtered_rules.empty:

    st.info("그래프로 표시할 규칙이 없습니다.")

else:

    chart_df = filtered_rules.head(10).copy()

    # 그래프용 규칙 이름
    chart_df["규칙"] = (
        chart_df["조건"]
        + " → "
        + chart_df["결과"]
    )

    # 향상도 높은 순
    chart_df = chart_df.sort_values(
        "향상도",
        ascending=True
    )

    fig = px.bar(
        chart_df,
        x="향상도",
        y="규칙",
        orientation="h",
        text="향상도",
        hover_data={
            "규칙": True,
            "향상도": ":.3f",
            "신뢰도": ":.2%",
            "지지도": ":.2%",
            "동시": True
        },
        labels={
            "향상도": "향상도",
            "규칙": "메뉴 규칙",
            "신뢰도": "신뢰도",
            "지지도": "지지도",
            "동시": "함께 나온 횟수"
        },
        title="향상도 상위 10개 메뉴 규칙"
    )

    fig.update_layout(
        height=max(450, len(chart_df) * 45),
        margin=dict(l=20, r=20, t=60, b=20)
    )

    fig.update_traces(
        texttemplate="%{text:.3f}",
        textposition="outside"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


# =========================================================
# 설명
# =========================================================

with st.expander("📖 지표가 무엇을 의미하나요?"):

    st.markdown("""
### 지지도
전체 급식일 중 두 메뉴가 함께 나온 비율입니다.

**지지도 = 두 메뉴가 함께 나온 횟수 ÷ 전체 급식일**

### 신뢰도
조건 메뉴가 나온 날에 결과 메뉴도 함께 나온 비율입니다.

**신뢰도 = 두 메뉴가 함께 나온 횟수 ÷ 조건 메뉴가 나온 횟수**

### 향상도
두 메뉴가 서로 관련되어 함께 나오는 정도를 나타냅니다.

**향상도 = 신뢰도 ÷ 결과 메뉴의 지지도**

- 향상도 > 1 : 함께 나오는 경향이 기대보다 높음
- 향상도 = 1 : 서로 특별한 관련이 없는 경우
- 향상도 < 1 : 함께 나오는 경향이 기대보다 낮음

예를 들어

**A → B**

라는 규칙이 있다면,

**B → A**

도 별도의 규칙으로 계산합니다.
""")


# =========================================================
# 데이터 미리보기
# =========================================================

with st.expander("📄 원본 급식 데이터 보기"):

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )
