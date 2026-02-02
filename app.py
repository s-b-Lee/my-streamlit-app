import streamlit as st
import requests
from typing import Dict, Any, List, Optional, Tuple

# =========================
# Page Config
# =========================
st.set_page_config(page_title="나와 어울리는 영화는?", page_icon="🎬", layout="wide")

# =========================
# Constants
# =========================
TMDB_BASE = "https://api.themoviedb.org/3"
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
# Session State Init
# =========================
if "watched_ids" not in st.session_state:
    st.session_state.watched_ids = set()  # 이미 본 영화 id

if "saved_ids" not in st.session_state:
    st.session_state.saved_ids = set()  # 관심 목록 id

if "saved_movies" not in st.session_state:
    st.session_state.saved_movies = {}  # id -> movie dict(간단정보)

if "last_reco_params" not in st.session_state:
    st.session_state.last_reco_params = None  # 마지막 추천 조건 저장(추가 추천용)

if "reco_page" not in st.session_state:
    st.session_state.reco_page = 1  # 추가 추천 페이지

if "current_recos" not in st.session_state:
    st.session_state.current_recos = []  # 현재 화면에 보여주는 추천 리스트

# =========================
# Sidebar
# =========================
with st.sidebar:
    st.header("🔑 TMDB 설정")
    tmdb_key = st.text_input("TMDB API Key", type="password", placeholder="TMDB API Key 입력")
    st.caption("🔒 키는 세션에서만 사용됩니다. (저장 X)")

    st.divider()
    st.subheader("⚙️ 추천 옵션")
    language = st.selectbox("언어", ["ko-KR", "en-US"], index=0)
    region = st.selectbox("지역(국가 코드)", ["KR", "US", "JP", "GB", "FR", "DE"], index=0)

    sort_ui = st.selectbox("정렬 기준", ["인기순", "평점 순"], index=0)
    sort_by = "popularity.desc" if sort_ui == "인기순" else "vote_average.desc"

    min_vote_count = st.slider("최소 투표 수(vote_count.gte)", 0, 5000, 300, step=50)
    min_rating = st.slider("최소 평점(vote_average.gte)", 0.0, 9.5, 6.5, step=0.1)

    max_items = st.selectbox("추천 표시 개수(첫 결과)", [6, 9, 12], index=1)
    include_providers = st.checkbox("시청 제공처(JustWatch) 표시", value=True)
    include_trailer = st.checkbox("트레일러(YouTube) 표시", value=True)
    include_cast = st.checkbox("주요 출연진 표시", value=True)
    include_series = st.checkbox("시리즈(컬렉션) 안내 표시", value=True)

    st.divider()
    st.subheader("🧹 관리")
    if st.button("대화/추천 초기화(추천만)", use_container_width=True):
        st.session_state.last_reco_params = None
        st.session_state.reco_page = 1
        st.session_state.current_recos = []
        st.rerun()

    if st.button("봤어요 목록 비우기", use_container_width=True):
        st.session_state.watched_ids = set()
        st.rerun()

    if st.button("내 목록 비우기", use_container_width=True):
        st.session_state.saved_ids = set()
        st.session_state.saved_movies = {}
        st.rerun()

# =========================
# UI Header
# =========================
st.title("🎬 나와 어울리는 영화는?")
st.write("5개의 질문으로 당신의 영화 취향을 분석하고, TMDB에서 **영화 추천**을 받아보세요 🍿✨")
st.caption("✅ 이미 본 영화는 체크해서 제외하고, 마음에 드는 영화는 ‘내 목록’에 저장할 수 있어요.")
st.divider()

# =========================
# Questions (5) - 4 options each
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
# Helpers: quiz -> genre
# =========================
def option_index(answer: str, options: List[str]) -> int:
    return options.index(answer)

def bucket_counts(a1, a2, a3, a4, a5) -> List[int]:
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

def decide_genre_bucket(a1, a2, a3, a4, a5) -> int:
    counts = bucket_counts(a1, a2, a3, a4, a5)
    return max(range(4), key=lambda i: counts[i])  # 동점이면 앞쪽 우선

def refine_subgenre(bucket: int, a2: str, a5: str) -> Tuple[str, List[int], str]:
    if bucket == 0:
        romance_signals = 0
        if a2 == q2_opts[0]:
            romance_signals += 2
        if a5 == q5_opts[0]:
            romance_signals += 1
        if romance_signals >= 2:
            return "로맨스/드라마", [GENRE_IDS["로맨스"], GENRE_IDS["드라마"]], "감정선과 관계의 여운을 중요하게 보는 선택이 많았어요."
        return "드라마", [GENRE_IDS["드라마"]], "현실적인 감정과 몰입감 있는 서사를 선호하는 선택이 많았어요."

    if bucket == 1:
        return "액션", [GENRE_IDS["액션"]], "속도감과 긴장감, 통쾌한 전개를 선호하는 선택이 많았어요."

    if bucket == 2:
        sf_signals = 0
        if a5 == q5_opts[2]:
            sf_signals += 2
        if a2 == q2_opts[2]:
            sf_signals += 1
        if sf_signals >= 2:
            return "SF", [GENRE_IDS["SF"]], "세계관/비현실 설정을 즐기는 선택이 많았어요."
        return "판타지", [GENRE_IDS["판타지"]], "상상력과 환상적인 분위기를 선호하는 선택이 많았어요."

    return "코미디", [GENRE_IDS["코미디"]], "가볍게 웃고 기분 전환하는 요소를 선호하는 선택이 많았어요."

# =========================
# Helpers: TMDB API (with caching)
# =========================
def tmdb_get(api_key: str, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = dict(params or {})
    params["api_key"] = api_key
    url = f"{TMDB_BASE}{path}"
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=60 * 30)
def discover_movies_cached(api_key: str, genre_ids_csv: str, language: str, region: str,
                          min_vote_count: int, min_rating: float, sort_by: str, page: int) -> Dict[str, Any]:
    return tmdb_get(
        api_key,
        "/discover/movie",
        params={
            "with_genres": genre_ids_csv,
            "language": language,
            "region": region,
            "sort_by": sort_by,
            "include_adult": "false",
            "vote_count.gte": min_vote_count,
            "vote_average.gte": min_rating,
            "page": page,
        },
    )

@st.cache_data(ttl=60 * 60)
def movie_details_cached(api_key: str, movie_id: int, language: str, append: str) -> Dict[str, Any]:
    return tmdb_get(
        api_key,
        f"/movie/{movie_id}",
        params={
            "language": language,
            "append_to_response": append,
       
