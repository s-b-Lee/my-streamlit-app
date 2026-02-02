import streamlit as st
import requests

# =========================
# Page Config
# =========================
st.set_page_config(page_title="나와 어울리는 영화는?", page_icon="🎬")

# =========================
# Sidebar (TMDB Key)
# =========================
with st.sidebar:
    st.header("🔑 TMDB 설정")
    tmdb_key = st.text_input("TMDB API Key", type="password", placeholder="입력하면 추천이 활성화돼요")
    st.caption("TMDB 키는 이 세션에서만 사용됩니다.")

# =========================
# UI
# =========================
st.title("🎬 나와 어울리는 영화는?")
st.write("5개의 질문으로 당신의 영화 취향을 분석하고, TMDB에서 **인기 영화 5편**을 추천해드려요 🍿✨")
st.divider()

# =========================
# Questions (5) - 4 options each (장르 선호 반영)
# 옵션 인덱스: 0=로맨스/드라마, 1=액션/어드벤처, 2=SF/판타지, 3=코미디
# =========================
q1_opts = [
    "💌 조용한 카페에서 여운 있는 영화 한 편",
    "💥 친구들이랑 스트레스 풀 겸 통쾌한 액션 영화",
    "🚀 현실 잊게 만드는 다른 세계관 영화 몰아보기",
    "😂 아무 생각 없이 웃긴 영화 보면서 쉬기",
]
q2_opts = [
    "🌸 사람들 사이의 감정과 관계가 중심이 되는 삶",
    "🏃 위험하지만 매 순간이 긴박한 모험의 연속",
    "🪐 현실엔 없는 능력이나 세계가 존재하는 삶",
    "🤡 크게 심각하지 않고, 웃지 못할 상황도 웃어넘기는 삶",
]
q3_opts = [
    "🤍 “너랑 얘기하면 생각이 많아져”",
    "🔥 “너 진짜 추진력 하나는 인정”",
    "🧠 “너 생각하는 거 좀 독특하다?”",
    "😆 “너 있으면 분위기 살잖아”",
]
q4_opts = [
    "🎭 배우의 연기력과 감정선",
    "🎬 몰입감 있는 전개와 스케일",
    "🌌 세계관 설정과 상상력",
    "🎉 얼마나 많이 웃게 해주느냐",
]
q5_opts = [
    "🌧️ 조용히 혼자 걷는 감정적인 장면",
    "⚡ 바쁘게 움직이며 사건을 해결하는 장면",
    "🌀 현실과 다른 공간을 떠도는 장면",
    "🎈 실수 연발이지만 웃음이 터지는 장면",
]

q1 = st.radio("1️⃣ 시험 끝난 날, 가장 하고 싶은 건?", q1_opts)
q2 = st.radio("2️⃣ 영화 주인공으로 살아야 한다면, 어떤 인생이 좋아?", q2_opts)
q3 = st.radio("3️⃣ 친구들이 너한테 자주 하는 말은?", q3_opts)
q4 = st.radio("4️⃣ 영화 볼 때 가장 중요한 요소는?", q4_opts)
q5 = st.radio("5️⃣ 요즘 네 상태를 영화 장면으로 표현한다면?", q5_opts)

st.divider()

# =========================
# TMDB constants
# =========================
POSTER_BASE = "https://image.tmdb.org/t/p/w500"

GENRE_IDS = {
    "액션": 28,
    "코미디": 35,
    "드라마": 18,
    "SF": 878,
    "로맨스": 10749,
    "판타지": 14,
}

# =========================
# Helpers
# =========================
def option_index(answer: str, options: list[str]) -> int:
    """Return 0..3 based on which option user picked."""
    return options.index(answer)

def decide_genre_bucket(a1, a2, a3, a4, a5) -> int:
    """
    0=로맨스/드라마, 1=액션/어드벤처, 2=SF/판타지, 3=코미디
    """
    picks = [
        option_index(a1, q1_opts),
        option_index(a2, q2_opts),
        option_index(a3, q3_opts),
        option_index(a4, q4_opts),
        option_index(a5, q5_opts),
    ]
    counts = [0, 0, 0, 0]
    for p in picks:
        counts[p] += 1
    # 최고 득표 버킷 선택 (동점이면 앞쪽 우선)
    return max(range(4), key=lambda i: counts[i])

def refine_subgenre(bucket: int, a2: str, a5: str) -> tuple[str, int]:
    """
    TMDB 장르로 최종 매핑.
    - 로맨스/드라마 버킷이면: 로맨스 vs 드라마 간단 판별
    - SF/판타지 버킷이면: SF vs 판타지 간단 판별
    """
    if bucket == 0:
        # 관계 중심(로맨스) 쪽 선택이 강하면 로맨스, 아니면 드라마
        romance_signals = 0
        if a2 == q2_opts[0]:  # 관계 중심 삶
            romance_signals += 2
        if a5 == q5_opts[0]:  # 감정적인 장면
            romance_signals += 1
        if romance_signals >= 2:
            return "로맨스", GENRE_IDS["로맨스"]
        return "드라마", GENRE_IDS["드라마"]

    if bucket == 1:
        return "액션", GENRE_IDS["액션"]

    if bucket == 2:
        # “현실과 다른 공간/우주” 느낌이면 SF, 아니면 판타지
        sf_signals = 0
        if a5 == q5_opts[2]:
            sf_signals += 2
        if a2 == q2_opts[2]:
            sf_signals += 1
        if sf_signals >= 2:
            return "SF", GENRE_IDS["SF"]
        return "판타지", GENRE_IDS["판타지"]

    return "코미디", GENRE_IDS["코미디"]

def fetch_tmdb_popular_movies(api_key: str, genre_id: int, n: int = 5):
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": api_key,
        "with_genres": str(genre_id),
        "language": "ko-KR",
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "page": 1,
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    return (data.get("results") or [])[:n]

def make_reason(genre_name: str, bucket: int, counts: list[int]) -> str:
    # 짧고 교수님 톤으로 "왜 이 장르인지" 설명
    highlight = {
        0: "감정선/관계/여운",
        1: "속도감/긴장감/해결",
        2: "세계관/상상력/비현실",
        3: "가벼움/유머/기분전환",
    }[bucket]
    return f"답변에서 **{highlight}** 성향이 가장 강하게 나타났기 때문에, 우선 **{genre_name}** 장르에서 인기작을 골랐습니다."

def bucket_counts(a1, a2, a3, a4, a5):
    picks = [
        option_index(a1, q1_opts),
        option_index(a2, q2_opts),
        option_index(a3, q3_opts),
        option_index(a4, q4_opts),
        option_index(a5, q5_opts),
    ]
    counts = [0, 0, 0, 0]
    for p in picks:
        counts[p] += 1
    return counts

# =========================
# Result Button
# =========================
if st.button("✨ 결과 보기"):
    if not tmdb_key.strip():
        st.error("사이드바에 TMDB API Key를 입력해 주세요.")
        st.stop()

    counts = bucket_counts(q1, q2, q3, q4, q5)
    bucket = decide_genre_bucket(q1, q2, q3, q4, q5)
    genre_name, genre_id = refine_subgenre(bucket, q2, q5)

    st.subheader("🔎 분석 결과")
    st.write(make_reason(genre_name, bucket, counts))
    st.caption(f"선택 분포: 로맨스/드라마 {counts[0]} · 액션/어드벤처 {counts[1]} · SF/판타지 {counts[2]} · 코미디 {counts[3]}")
    st.divider()

    try:
        movies = fetch_tmdb_popular_movies(tmdb_key, genre_id, n=5)
        if not movies:
            st.warning("해당 장르에서 가져올 영화가 없어요. 다른 장르로 다시 시도해 주세요.")
            st.stop()

        st.subheader(f"🍿 추천 영화 5편 ({genre_name})")

        for m in movies:
            title = m.get("title") or m.get("name") or "제목 없음"
            rating = m.get("vote_average")
            overview = (m.get("overview") or "").strip()
            poster_path = m.get("poster_path")

            poster_url = f"{POSTER_BASE}{poster_path}" if poster_path else None
            short_overview = overview if overview else "줄거리 정보가 없습니다."
            if len(short_overview) > 280:
                short_overview = short_overview[:280].rstrip() + "…"

            with st.container(border=True):
                cols = st.columns([1, 2])
                with cols[0]:
                    if poster_url:
                        st.image(poster_url, use_container_width=True)
                    else:
                        st.info("포스터 없음")

                with cols[1]:
                    st.markdown(f"### {title}")
                    if rating is not None:
                        st.write(f"⭐ 평점: {rating:.1f}/10")
                    else:
                        st.write("⭐ 평점: 정보 없음")

                    st.write(short_overview)

                    # 간단 추천 이유(개별 영화)
                    st.caption(f"💡 이 영화를 추천하는 이유: 당신의 선택이 **{genre_name}** 성향에 가까워서, 이 장르에서 **대중적 인기도(인기순)**가 높은 작품을 우선 제시했어요.")

    except requests.HTTPError as e:
        st.error(
            "TMDB 요청에 실패했어요.\n\n"
            f"- HTTP 오류: {e}\n"
            "API 키가 올바른지, 호출 제한에 걸리지 않았는지 확인해 주세요."
        )
    except Exception as e:
        st.error(f"오류가 발생했어요: {e}")
