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
# Sidebar
# =========================
with st.sidebar:
    st.header("🔑 TMDB 설정")

    tmdb_key = st.text_input("TMDB API Key", type="password", placeholder="TMDB API Key 입력")

    st.subheader("⚙️ 추천 필터 (고도화)")
    language = st.selectbox("언어", ["ko-KR", "en-US"], index=0)
    region = st.selectbox("지역(국가 코드)", ["KR", "US", "JP", "GB", "FR", "DE"], index=0)
    min_vote_count = st.slider("최소 투표 수(vote_count.gte)", 0, 5000, 300, step=50)
    min_rating = st.slider("최소 평점(vote_average.gte)", 0.0, 9.5, 6.5, step=0.1)
    max_items = st.selectbox("가져올 영화 수", [6, 9, 12], index=1)
    include_providers = st.checkbox("한국 시청 제공처(JustWatch) 표시", value=True)
    include_trailer = st.checkbox("트레일러(YouTube) 표시", value=True)
    include_cast = st.checkbox("주요 출연진 표시", value=True)

    st.caption("🔒 키는 세션에서만 사용됩니다. (저장 X)")

# =========================
# UI
# =========================
st.title("🎬 나와 어울리는 영화는?")
st.write("5개의 질문으로 당신의 영화 취향을 분석하고, TMDB에서 **인기 영화**를 추천해드려요 🍿✨")
st.divider()

# =========================
# Questions (5)
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
    # 동점이면 앞쪽 우선(로맨스/드라마 -> 액션 -> SF/판타지 -> 코미디)
    return max(range(4), key=lambda i: counts[i])

def refine_subgenre(bucket: int, a2: str, a5: str) -> Tuple[str, List[int], str]:
    """
    returns:
      - display_genre_name
      - genre_ids (one or multiple)
      - why (짧은 추천 이유 텍스트)
    """
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
    if params is None:
        params = {}
    params = dict(params)
    params["api_key"] = api_key
    url = f"{TMDB_BASE}{path}"
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=60 * 30)  # 30분 캐시: 같은 조건 재요청 줄이기(레이트리밋/속도 개선)
def discover_movies_cached(api_key: str, genre_ids_csv: str, language: str, region: str,
                          min_vote_count: int, min_rating: float, page: int) -> Dict[str, Any]:
    return tmdb_get(
        api_key,
        "/discover/movie",
        params={
            "with_genres": genre_ids_csv,
            "language": language,
            "region": region,
            "sort_by": "popularity.desc",
            "include_adult": "false",
            "vote_count.gte": min_vote_count,
            "vote_average.gte": min_rating,
            "page": page,
        },
    )

@st.cache_data(ttl=60 * 60)  # 1시간 캐시: 상세정보는 더 오래 캐시
def movie_details_cached(api_key: str, movie_id: int, language: str, append: str) -> Dict[str, Any]:
    # append_to_response로 videos/credits 등을 한 번에 가져오기(요청 수 감소)  :contentReference[oaicite:3]{index=3}
    return tmdb_get(
        api_key,
        f"/movie/{movie_id}",
        params={
            "language": language,
            "append_to_response": append,
        },
    )

@st.cache_data(ttl=60 * 60)
def movie_watch_providers_cached(api_key: str, movie_id: int) -> Dict[str, Any]:
    # 시청 제공처: JustWatch 파트너십 기반(표기 필요) :contentReference[oaicite:4]{index=4}
    return tmdb_get(api_key, f"/movie/{movie_id}/watch/providers", params={})

def safe_poster_url(poster_path: Optional[str]) -> Optional[str]:
    if not poster_path:
        return None
    return f"{POSTER_BASE}{poster_path}"

def short_text(text: str, limit: int = 260) -> str:
    text = (text or "").strip()
    if not text:
        return "줄거리 정보가 없습니다."
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"

def pick_trailer_youtube(videos_obj: Dict[str, Any]) -> Optional[str]:
    # videos.results 중 type=Trailer, site=YouTube 우선
    results = (videos_obj or {}).get("results") or []
    best = None
    for v in results:
        if v.get("site") == "YouTube" and v.get("type") == "Trailer":
            best = v
            break
    if not best:
        for v in results:
            if v.get("site") == "YouTube":
                best = v
                break
    if best and best.get("key"):
        return f"https://www.youtube.com/watch?v={best['key']}"
    return None

def top_cast_names(credits_obj: Dict[str, Any], n: int = 5) -> List[str]:
    cast = (credits_obj or {}).get("cast") or []
    names = []
    for c in cast[:n]:
        name = c.get("name")
        if name:
            names.append(name)
    return names

def providers_in_region(providers_obj: Dict[str, Any], region: str) -> List[str]:
    results = (providers_obj or {}).get("results") or {}
    by_region = results.get(region) or {}
    names = []
    # 우선순위: flatrate(스트리밍) -> rent -> buy
    for key in ["flatrate", "rent", "buy"]:
        for p in (by_region.get(key) or []):
            nm = p.get("provider_name")
            if nm and nm not in names:
                names.append(nm)
    return names

# =========================
# Result Button
# =========================
if st.button("✨ 결과 보기"):
    if not tmdb_key.strip():
        st.error("사이드바에 TMDB API Key를 입력해 주세요.")
        st.stop()

    bucket = decide_genre_bucket(q1, q2, q3, q4, q5)
    genre_label, genre_ids, why_genre = refine_subgenre(bucket, q2, q5)
    counts = bucket_counts(q1, q2, q3, q4, q5)

    # 여러 페이지를 섞어 다양성(중복 감소) 확보
    genre_ids_csv = ",".join(map(str, genre_ids))
    target_n = int(max_items)

    with st.spinner("🎬 TMDB에서 당신 취향에 맞는 영화를 찾는 중..."):
        movies: List[Dict[str, Any]] = []
        seen_ids = set()
        # 페이지 1~3까지 훑어보고 조건에 맞는 것만 수집
        for page in [1, 2, 3]:
            data = discover_movies_cached(
                tmdb_key, genre_ids_csv, language, region, int(min_vote_count), float(min_rating), page
            )
            for m in (data.get("results") or []):
                mid = m.get("id")
                if not mid or mid in seen_ids:
                    continue
                seen_ids.add(mid)
                # 포스터 없는 건 뒤로 빼고 싶으면 여기서 스킵 가능
                movies.append(m)
                if len(movies) >= target_n:
                    break
            if len(movies) >= target_n:
                break

    if not movies:
        st.warning("조건에 맞는 영화를 찾지 못했어요. 필터(평점/투표수)를 낮추거나 다른 선택으로 다시 시도해 주세요.")
        st.stop()

    st.divider()
    st.markdown(f"## 🎯 당신에게 딱인 장르는: **{genre_label}**!")
    st.caption(
        f"선택 분포: 로맨스/드라마 {counts[0]} · 액션/어드벤처 {counts[1]} · SF/판타지 {counts[2]} · 코미디 {counts[3]}"
    )
    st.write(f"**왜 이 장르?** {why_genre}")
    st.divider()

    # =========================
    # 3-column Cards
    # =========================
    cols = st.columns(3)
    for i, m in enumerate(movies):
        col = cols[i % 3]

        movie_id = m.get("id")
        title = m.get("title") or "제목 없음"
        rating = m.get("vote_average")
        overview = m.get("overview")
        poster_url = safe_poster_url(m.get("poster_path"))
        release_date = m.get("release_date")

        with col:
            with st.container(border=True):
                if poster_url:
                    st.image(poster_url, use_container_width=True)
                else:
                    st.info("포스터 없음")

                st.markdown(f"### {title}")
                if rating is not None:
                    st.write(f"⭐ 평점: **{float(rating):.1f} / 10**")
                else:
                    st.write("⭐ 평점: 정보 없음")

                if release_date:
                    st.caption(f"개봉일: {release_date}")

                # “카드 클릭” 느낌은 Streamlit에서 실제 클릭 이벤트가 제한적이라,
                # expander를 카드 내부에 배치해 동일 UX로 제공
                with st.expander("📖 상세 정보 보기", expanded=False):
                    st.write(short_text(overview, 420))

                    if not movie_id:
                        st.warning("상세 정보를 불러올 수 없습니다.")
                        continue

                    # 상세정보 고도화: append_to_response로 videos/credits를 한 번에
                    append_parts = []
                    if include_trailer:
                        append_parts.append("videos")
                    if include_cast:
                        append_parts.append("credits")
                    # (watch/providers는 별도 엔드포인트라 append 대상 아님)
                    append = ",".join(append_parts) if append_parts else ""

                    with st.spinner("상세 정보를 불러오는 중..."):
                        details = movie_details_cached(tmdb_key, int(movie_id), language, append) if append else movie_details_cached(tmdb_key, int(movie_id), language, "")

                    # 기본 상세
                    runtime = details.get("runtime")
                    tagline = (details.get("tagline") or "").strip()
                    genres = [g.get("name") for g in (details.get("genres") or []) if g.get("name")]
                    if genres:
                        st.caption("장르: " + ", ".join(genres))
                    if runtime:
                        st.caption(f"러닝타임: {runtime}분")
                    if tagline:
                        st.markdown(f"> {tagline}")

                    # 트레일러
                    if include_trailer and "videos" in details:
                        trailer_url = pick_trailer_youtube(details.get("videos"))
                        if trailer_url:
                            st.link_button("▶️ 트레일러 보기 (YouTube)", trailer_url)
                        else:
                            st.caption("트레일러 링크를 찾지 못했어요.")

                    # 출연진
                    if include_cast and "credits" in details:
                        names = top_cast_names(details.get("credits"), n=5)
                        if names:
                            st.caption("주요 출연: " + " · ".join(names))

                    # 시청 제공처(JustWatch) — 한국만 표시
                    if include_providers:
                        with st.spinner("시청 제공처를 확인 중..."):
                            prov = movie_watch_providers_cached(tmdb_key, int(movie_id))
                        providers = providers_in_region(prov, region)
                        if providers:
                            st.caption(f"📺 {region} 시청 가능(일부): " + ", ".join(providers))
                            st.caption("데이터 제공: JustWatch")  # JustWatch Attribution Required :contentReference[oaicite:5]{index=5}
                        else:
                            st.caption(f"📺 {region} 시청 제공처 정보가 없어요.")

                    # “추천 이유” (개별)
                    reason_by_bucket = {
                        0: "감정선/관계의 여운을 좋아하는 성향이라, 몰입감 있는 서사가 강한 작품을 우선 골랐어요.",
                        1: "긴장감과 속도감을 선호해서, 전개가 시원하게 뻗는 인기작을 먼저 추천해요.",
                        2: "세계관/상상력을 즐기는 성향이라, 설정이 강한 작품을 우선으로 가져왔어요.",
                        3: "기분 전환형 취향이라, 가볍게 보기 좋은 코미디 인기작을 먼저 추천해요.",
                    }
                    st.caption(f"💡 이 영화를 추천하는 이유: {reason_by_bucket.get(bucket, '선호 장르 기반 추천이에요.')}")

    st.divider()
    st.caption(
        "💡 고도화 포인트: 캐싱으로 반복 호출을 줄이고, "
        "append_to_response로 상세(트레일러/출연진)를 한 번에 받아 요청 수를 감소시켰어요."
    )
