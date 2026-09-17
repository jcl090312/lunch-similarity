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
    메뉴 이름에서 괄호와 괄호 안의 내용을 제거합니다.

    예:
    오징어초무침(무x,부찬)
    → 오징어초무침
    """

    if pd.isna(menu):
        return ""

    menu = str(menu)

    # 괄호와 괄호 안의 내용 제거
    menu = re.sub(r"\([^)]*\)", "", menu)

    return menu.strip()


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

    # 한 끼에 같은 메뉴가 여러 번 있더라도 한 번만 계산
    menus = sorted(set(menus))

    if menus:
        baskets.append(menus)


# =========================================================
# 전체 급식 일수
# =========================================================

total_days = len(baskets)


# =========================================================
# 메뉴별 등장 횟수
# =========================================================

menu_count = {}

for basket in baskets:

    for menu in basket:

        menu_count[menu] = menu_count.get(menu, 0) + 1


menu_type_count = len(menu_count)


# =========================================================
# 메뉴 쌍별 동시 등장 횟수 계산
# =========================================================

pair_count = {}

for basket in baskets:

    # 하루에 함께 나온 모든 메뉴 조합
    for a, b in itertools.combinations(basket, 2):

        pair = tuple(sorted([a, b]))

        pair_count[pair] = pair_count.get(pair, 0) + 1


# =========================================================
# 연관 규칙 계산
# =========================================================

rules = []

for (a, b), together_count in pair_count.items():

    # -----------------------------------------
    # A → B
    # -----------------------------------------

    support = together_count / total_days

    confidence_a_b = together_count / menu_count[a]

    lift_a_b = confidence_a_b / (
        menu_count[b] / total_days
    )

    rules.append({
        "조건": a,
        "결과": b,
        "동시": together_count,
        "지지도": support,
        "신뢰도": confidence_a_b,
        "향상도": lift_a_b
    })

    # -----------------------------------------
    # B → A
    # -----------------------------------------

    confidence_b_a = together_count / menu_count[b]

    lift_b_a = confidence_b_a / (
        menu_count[a] / total_days
    )

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
# 상단 메뉴 좁혀 보기
# =========================================================

st.subheader("🔎 메뉴별 규칙 찾기")

menu_options = ["전체 메뉴"] + sorted(menu_count.keys())

selected_menu = st.selectbox(
    "메뉴를 선택하면 해당 메뉴가 포함된 규칙만 볼 수 있습니다.",
    menu_options,
    key="rule_menu_selector"
)


# =========================================================
# 최소 동시 일수 슬라이더
# =========================================================

min_together = st.slider(
    "최소 동시 일수",
    min_value=1,
    max_value=10,
    value=1,
    step=1,
    help="선택한 횟수보다 적게 함께 나온 규칙은 표와 그래프에서 제외됩니다."
)


# =========================================================
# 최소 동시 일수 필터
# =========================================================

filtered_rules = rules_df[
    rules_df["동시"] >= min_together
].copy()


# =========================================================
# 메뉴 필터
# =========================================================

if selected_menu != "전체 메뉴":

    filtered_rules = filtered_rules[
        (filtered_rules["조건"] == selected_menu) |
        (filtered_rules["결과"] == selected_menu)
    ].copy()


# =========================================================
# 정렬 기준
# =========================================================

sort_option = st.selectbox(
    "정렬 기준",
    ["향상도 순", "신뢰도 순", "동시 순"]
)

if sort_option == "향상도 순":

    filtered_rules = filtered_rules.sort_values(
        by=["향상도", "신뢰도", "동시"],
        ascending=[False, False, False]
    )

elif sort_option == "신뢰도 순":

    filtered_rules = filtered_rules.sort_values(
        by=["신뢰도", "향상도", "동시"],
        ascending=[False, False, False]
    )

else:

    filtered_rules = filtered_rules.sort_values(
        by=["동시", "향상도", "신뢰도"],
        ascending=[False, False, False]
    )


# =========================================================
# 현재 남은 규칙 수
# =========================================================

st.write(
    f"현재 조건에서 표에 남은 규칙은 **{len(filtered_rules)}개**입니다."
)


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

    st.warning(
        "현재 조건에 해당하는 규칙이 없습니다. "
        "최소 동시 일수를 낮춰 보세요."
    )

else:

    display_df = filtered_rules.copy()

    # 지지도 / 신뢰도 퍼센트 표시
    display_df["지지도"] = display_df["지지도"].map(
        lambda x: f"{x:.2%}"
    )

    display_df["신뢰도"] = display_df["신뢰도"].map(
        lambda x: f"{x:.2%}"
    )

    # 향상도 소수 셋째 자리까지
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
# 함께 나온 적 없는 짝
# =========================================================

st.subheader("🚫 함께 나온 적 없는 짝")

st.caption(
    "선택한 메뉴와 한 번도 같은 날 나오지 않았으면서, "
    "혼자서는 10일 이상 나온 메뉴를 보여줍니다."
)


# ---------------------------------------------------------
# 함께 나온 적 없는 짝용 메뉴 선택
# ---------------------------------------------------------

no_pair_menu = st.selectbox(
    "비교할 메뉴를 선택하세요.",
    sorted(menu_count.keys()),
    key="no_pair_menu_selector"
)


# =========================================================
# 선택 메뉴가 등장한 날짜 찾기
# =========================================================

selected_dates = set()

for i, basket in enumerate(baskets):

    if no_pair_menu in basket:
        selected_dates.add(i)


selected_menu_days = len(selected_dates)


# =========================================================
# 다른 메뉴와 함께 나온 날짜 찾기
# =========================================================

coexisting_menus = set()

for i, basket in enumerate(baskets):

    if no_pair_menu in basket:

        for menu in basket:

            if menu != no_pair_menu:
                coexisting_menus.add(menu)


# =========================================================
# 함께 나온 적 없는 메뉴 찾기
# 조건:
# 1. 선택 메뉴와 한 번도 같이 나오지 않음
# 2. 자기 자신은 10일 이상 등장
# =========================================================

never_together = []

for menu, count in menu_count.items():

    # 자기 자신은 제외
    if menu == no_pair_menu:
        continue

    # 10일 미만 등장 메뉴 제외
    if count < 10:
        continue

    # 한 번이라도 함께 나온 메뉴 제외
    if menu in coexisting_menus:
        continue

    never_together.append({
        "메뉴": menu,
        "나온 날 수": count
    })


# =========================================================
# 나온 날 수가 많은 순으로 정렬
# =========================================================

never_together_df = pd.DataFrame(
    never_together
)

if not never_together_df.empty:

    never_together_df = never_together_df.sort_values(
        by="나온 날 수",
        ascending=False
    ).reset_index(drop=True)


# =========================================================
# 결과 표시
# =========================================================

st.write(
    f"**{no_pair_menu}**은(는) 총 **{selected_menu_days}일** 나왔습니다."
)

st.write(
    f"조건을 만족하는 '함께 나온 적 없는 짝'은 "
    f"**{len(never_together_df)}개**입니다."
)


if never_together_df.empty:

    st.info(
        "조건을 만족하는 메뉴가 없습니다."
    )

else:

    st.dataframe(
        never_together_df[
            [
                "메뉴",
                "나온 날 수"
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

    st.info(
        "그래프로 표시할 규칙이 없습니다."
    )

else:

    chart_df = filtered_rules.head(10).copy()

    # 그래프용 규칙 이름
    chart_df["규칙"] = (
        chart_df["조건"]
        + " → "
        + chart_df["결과"]
    )

    # Plotly 가로 막대그래프는 아래에서 위로 표시되므로
    # 낮은 향상도부터 정렬
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
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20
        )
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
# 지표 설명
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
# 원본 데이터 보기
# =========================================================

with st.expander("📄 원본 급식 데이터 보기"):

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )
