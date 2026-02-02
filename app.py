import streamlit as st
import requests
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI

# =========================
# Page Config
# =========================
st.set_page_config(page_title="🎬 상황 맞춤 영화 추천", page_icon="🎬", layout="wide")

TMDB_BASE = "https://api.themoviedb.org/3"
POSTER_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_MOVIE_WEB = "https://www.themoviedb.org/movie/"

# 장르 ID (요청에서 주어진 것)
GENRE_IDS = {
    "액션": 28,
    "코미디": 35,
    "드라마": 18,
    "SF": 878,
    "로맨스": 10749,
    "판타지": 14,
}

# =========================
# Session State
# =========================
if "excluded_ids" not in st.session_state:
    st.session_state.excluded_ids = set()  # 사용자가 "이미 봤어요"로 제외한 영화 ID

if "last_reco" not in st.session_state:
    st.session_state.last_reco = None  # {"movie_id":..., "title":..., "reason":...}

if "candidates" not in st.session_state:
    st.session_state.candidates = []  # 현재 화면에 보여줄 후보 리스트

# =========================
# Sidebar
# =========================
with st.sidebar:
    st.header("🔑 API 설정")

    tmdb_key = st.text_input("TMDB API Key", type="password", placeholder="TMDB API Key 입력")
    openai_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")

    st.subheader("⚙️ 추천 설정")
    language = st.selectbox("언어", ["ko-KR", "en-US"], index=0)
    region = st.selectbox("지역(국가 코드)", ["KR", "US", "JP", "GB", "FR", "DE"], index=0)
    max_items = st.selectbox("후보 영화 개수(화면 표시)", [6, 9, 12], index=1)
    min_vote_count = st.slider("최소 투표 수", 0, 5000, 200, step=50)
    min_rating = st.slider("최소 평점", 0.0, 9.5, 6.0, step=0.1)

    st.divider()
    if st.button("🧹 제외 목록/결과 초기화"):
        st.session_state.excluded_ids = set()
        st.session_state.last_reco = None
        st.session_state.candidates = []
        st.rerun()

    st.caption("🔒 키는 세션에서만 사용됩니다. (저장 X)")

# =========================
# UI
# =========================
st.title("🎬 지금 상황에 딱 맞는 영화 추천")
st.write(
    "질문 대신, **지금 내 상황/기분**을 적으면 TMDB에서 후보를 가져오고, "
    "**LLM이 그중 딱 1편**을 최종 추천해줘요 🍿✨"
)
st.divider()

situation = st.text_area(
    "📝 지금 어떤 상황/기분인가요?",
    placeholder="예: 과제 때문에 머리가 터질 것 같고 지쳐요. 아무 생각 없이 웃고 싶어요.\n예: 연애 감성 터지는 날… 여운 남는 영화 보고 싶어.",
    height=120,
)

colA, colB = st.columns([2, 1])
with colA:
    st.caption("팁) 키워드가 구체적일수록 좋아요: '힐링', '통쾌', '현실도피', '감성', '웃고 싶다', '긴장감' 등")
with colB:
    fallback_mood = st.selectbox(
        "무드 직접 선택(선택사항)",
        ["자동 분류", "힐링/잔잔", "감성/여운", "통쾌/에너지", "현실도피/판타지", "웃음/가벼움", "긴장/스릴"],
        index=0,
    )

st.divider()

# =========================
# TMDB Helpers (cached)
# =========================
def tmdb_get(api_key: str, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = params or {}
    params = dict(params)
    params["api_key"] = api_key
    url = f"{TMDB_BASE}{path}"
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=60 * 30)
def discover_movies_cached(
    api_key: str,
    with_genres: str,
    language: str,
    region: str,
    min_vote_count: int,
    min_rating: float,
    page: int,
) -> Dict[str, Any]:
    return tmdb_get(
        api_key,
        "/discover/movie",
        params={
            "with_genres": with_genres,
            "language": language,
            "region": region,
            "sort_by": "popularity.desc",
            "include_adult": "false",
            "vote_count.gte": min_vote_count,
            "vote_average.gte": min_rating,
            "page": page,
        },
    )

@st.cache_data(ttl=60 * 60)
def movie_videos_cached(api_key: str, movie_id: int, language: str) -> Dict[str, Any]:
    return tmdb_get(api_key, f"/movie/{movie_id}/videos", params={"language": language})

@st.cache_data(ttl=60 * 60)
def movie_details_cached(api_key: str, movie_id: int, language: str) -> Dict[str, Any]:
    return tmdb_get(api_key, f"/movie/{movie_id}", params={"language": language})

def pick_trailer_youtube(videos_obj: Dict[str, Any]) -> Optional[str]:
    results = (videos_obj or {}).get("results") or []
    for v in results:
        if v.get("site") == "YouTube" and v.get("type") == "Trailer" and v.get("key"):
            return f"https://www.youtube.com/watch?v={v['key']}"
    for v in results:
        if v.get("site") == "YouTube" and v.get("key"):
            return f"https://www.youtube.com/watch?v={v['key']}"
    return None

def poster_clickable_html(poster_url: str, link_url: str, title: str) -> str:
    return f"""
    <a href="{link_url}" target="_blank" style="text-decoration:none;">
        <img src="{poster_url}" alt="{title}" style="width:100%; border-radius:14px;" />
    </a>
    """

def short_text(text: str, limit: int = 260) -> str:
    text = (text or "").strip()
    if not text:
        return "줄거리 정보가 없습니다."
    return text if len(text) <= limit else text[:limit].rstrip() + "…"

def safe_poster_url(poster_path: Optional[str]) -> Optional[str]:
    if not poster_path:
        return None
    return f"{POSTER_BASE}{poster_path}"

# =========================
# Mood Classifier (rule-based)
# =========================
def classify_mood(text: str, fallback: str) -> Tuple[str, List[int], str]:
    if fallback != "자동 분류":
        mapping = {
            "힐링/잔잔": ("힐링/잔잔", [GENRE_IDS["드라마"]], "지금은 마음을 안정시키는 ‘잔잔한 흐름’이 우선이라 봤어요."),
            "감성/여운": ("감성/여운", [GENRE_IDS["로맨스"], GENRE_IDS["드라마"]], "감정선과 여운이 필요한 상황이라 봤어요."),
            "통쾌/에너지": ("통쾌/에너지", [GENRE_IDS["액션"]], "답답함을 뚫는 속도감/해결감이 필요한 상황이라 봤어요."),
            "현실도피/판타지": ("현실도피/판타지", [GENRE_IDS["SF"], GENRE_IDS["판타지"]], "현실을 잠시 잊게 해줄 세계관이 필요한 상황이라 봤어요."),
            "웃음/가벼움": ("웃음/가벼움", [GENRE_IDS["코미디"]], "가볍게 웃고 기분을 리셋하는 게 우선이라 봤어요."),
            "긴장/스릴": ("긴장/스릴", [GENRE_IDS["액션"], GENRE_IDS["SF"]], "집중해서 몰입할 ‘긴장감’이 필요한 상황이라 봤어요."),
        }
        return mapping[fallback]

    t = (text or "").lower()
    score = {k: 0 for k in ["힐링/잔잔", "감성/여운", "통쾌/에너지", "현실도피/판타지", "웃음/가벼움", "긴장/스릴"]}

    def has_any(words: List[str]) -> bool:
        return any(w in t for w in words)

    if has_any(["힐링", "잔잔", "편안", "쉬고", "지쳤", "위로", "따뜻", "포근", "안정", "휴식"]):
        score["힐링/잔잔"] += 3
    if has_any(["감성", "여운", "눈물", "울고", "연애", "사랑", "이별", "설렘", "로맨스"]):
        score["감성/여운"] += 3
    if has_any(["통쾌", "사이다", "스트레스", "답답", "화나", "빡치", "에너지", "액션", "카타르시스"]):
        score["통쾌/에너지"] += 3
    if has_any(["현실도피", "판타지", "마법", "우주", "외계", "미래", "세계관", "sf", "모험"]):
        score["현실도피/판타지"] += 3
    if has_any(["웃고", "웃긴", "코미디", "빵터", "가볍", "기분전환", "유머"]):
        score["웃음/가벼움"] += 3
    if has_any(["긴장", "몰입", "스릴", "서스펜스", "추격", "전투", "위기", "손에땀"]):
        score["긴장/스릴"] += 3

    mood = max(score, key=lambda k: score[k]) if max(score.values()) > 0 else "힐링/잔잔"

    mapping = {
        "힐링/잔잔": ("힐링/잔잔", [GENRE_IDS["드라마"]], "피로를 낮추고 마음을 정돈하는 흐름이 우선으로 보여서, 잔잔한 드라마 중심으로 골랐어요."),
        "감성/여운": ("감성/여운", [GENRE_IDS["로맨스"], GENRE_IDS["드라마"]], "감정의 결이 중요한 상황으로 보여서, 여운이 남는 로맨스/드라마를 우선 추천해요."),
        "통쾌/에너지": ("통쾌/에너지", [GENRE_IDS["액션"]], "답답함을 해소할 ‘해결감’이 필요해 보여서, 속도감 있는 액션을 우선 추천해요."),
        "현실도피/판타지": ("현실도피/판타지", [GENRE_IDS["SF"], GENRE_IDS["판타지"]], "현실에서 잠깐 벗어나고 싶어 보여서, SF/판타지 중심으로 추천해요."),
        "웃음/가벼움": ("웃음/가벼움", [GENRE_IDS["코미디"]], "가볍게 웃으며 리셋하는 게 최우선으로 보여서, 코미디를 우선 추천해요."),
        "긴장/스릴": ("긴장/스릴", [GENRE_IDS["액션"], GENRE_IDS["SF"]], "집중해서 몰입할 자극이 필요해 보여서, 긴장감 높은 액션/SF로 추천해요."),
    }
    return mapping[mood]

# =========================
# Candidate Fetch (excluding watched)
# =========================
def fetch_candidates(
    api_key: str,
    genre_ids: List[int],
    language: str,
    region: str,
    min_vote_count: int,
    min_rating: float,
    need: int,
    excluded_ids: set,
) -> List[Dict[str, Any]]:
    genre_csv = ",".join(str(x) for x in genre_ids)
    movies: List[Dict[str, Any]] = []
    seen = set()

    # 여러 페이지를 탐색해 excluded를 피해 충분히 채움
    for page in [1, 2, 3, 4, 5]:
        data = discover_movies_cached(api_key, genre_csv, language, region, min_vote_count, min_rating, page)
        for m in (data.get("results") or []):
            mid = m.get("id")
            if not mid or mid in excluded_ids or mid in seen:
                continue
            seen.add(mid)
            movies.append(m)
            if len(movies) >= need:
                return movies
    return movies

# =========================
# OpenAI: pick ONE final movie
# =========================
def llm_pick_one_movie(
    openai_api_key: str,
    situation_text: str,
    mood_label: str,
    candidates: List[Dict[str, Any]],
    language: str,
) -> Dict[str, Any]:
    """
    Returns:
      {"movie_id": int, "title": str, "reason": str}
    """
    client = OpenAI(api_key=openai_api_key)

    # 후보를 LLM 입력용으로 축약
    packed = []
    for m in candidates:
        packed.append(
            {
                "id": m.get("id"),
                "title": m.get("title") or m.get("name"),
                "vote_average": m.get("vote_average"),
                "vote_count": m.get("vote_count"),
                "release_date": m.get("release_date"),
                "overview": (m.get("overview") or "")[:500],
            }
        )

    system = (
        "당신은 영화 추천 전문가입니다. 사용자의 '상황/기분'과 '무드'에 가장 잘 맞는 영화 한 편만 고릅니다.\n"
        "- 과장/허위 없이, 후보 목록 안에서만 선택하세요.\n"
        "- 추천 사유는 2~4문장으로 짧고 명확하게.\n"
        "- 출력은 반드시 JSON만: {\"movie_id\":..., \"title\":..., \"reason\":...}\n"
    )

    user = {
        "situation": situation_text,
        "mood": mood_label,
        "candidates": packed,
        "language": language,
        "selection_criteria": [
            "상황과 무드에의 적합도(가장 중요)",
            "접근성(너무 무겁거나 극단적으로 난해한 작품은 피함)",
            "대중성(평점/인기도 참고, 단 맹신하지 않음)",
        ],
    }

    resp = client.responses.create(
        model="gpt-5-mini",
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"{user}"},
        ],
    )

    # Responses API: output_text에 모델의 텍스트 출력이 들어옴
    text = resp.output_text.strip()

    # 아주 단순 파서(안전하게 실패 처리)
    import json
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("not dict")
        return {
            "movie_id": int(data["movie_id"]),
            "title": str(data["title"]),
            "reason": str(data["reason"]),
        }
    except Exception:
        # 파싱 실패 시: 첫 후보로 fallback
        first = packed[0]
        return {
            "movie_id": int(first["id"]),
            "title": str(first["title"]),
            "reason": "후보 중 상황과 무드에 가장 무난하게 맞는 작품으로 우선 추천합니다.",
        }

# =========================
# Buttons
# =========================
left_btn, right_btn = st.columns([1, 1])
with left_btn:
    run_btn = st.button("✨ 후보 가져오기", use_container_width=True)
with right_btn:
    reroll_btn = st.button("🔁 (봤던 것 제외) 다시 뽑기", use_container_width=True)

if run_btn or reroll_btn:
    if not tmdb_key.strip():
        st.error("사이드바에 TMDB API Key를 입력해 주세요.")
        st.stop()

    if not situation.strip() and fallback_mood == "자동 분류":
        st.warning("상황을 한 줄이라도 적어주세요! (또는 무드를 직접 선택해도 돼요)")
        st.stop()

    mood_label, genre_ids, mood_reason = classify_mood(situation, fallback_mood)

    with st.spinner("🎬 TMDB에서 후보 영화를 가져오는 중..."):
        st.session_state.candidates = fetch_candidates(
            api_key=tmdb_key,
            genre_ids=genre_ids,
            language=language,
            region=region,
            min_vote_count=int(min_vote_count),
            min_rating=float(min_rating),
            need=int(max_items),
            excluded_ids=st.session_state.excluded_ids,
        )
        st.session_state.last_reco = None  # 후보 새로 뽑으면 최종 추천은 리셋

# =========================
# Render Candidates + Watched Exclusion
# =========================
if st.session_state.candidates:
    mood_label, genre_ids, mood_reason = classify_mood(situation, fallback_mood)

    st.divider()
    st.markdown(f"## 🎯 지금 당신에게 딱인 분위기: **{mood_label}**")
    st.write(f"**추천 근거:** {mood_reason}")
    st.caption(f"이미 본 영화는 카드에서 체크하면 다음 추천에서 자동 제외됩니다. ✅")
    st.divider()

    # 최종 1편 추천(LLM)
    final_btn = st.button("🤖 후보 중 '딱 1편' 최종 추천 받기", use_container_width=True)
    if final_btn:
        if not openai_key.strip():
            st.error("사이드바에 OpenAI API Key를 입력해 주세요.")
            st.stop()

        with st.spinner("🤖 당신에게 가장 맞는 1편을 고르는 중..."):
            st.session_state.last_reco = llm_pick_one_movie(
                openai_api_key=openai_key,
                situation_text=situation.strip(),
                mood_label=mood_label,
                candidates=st.session_state.candidates,
                language=language,
            )

    # 최종 추천 표시
    if st.session_state.last_reco:
        reco = st.session_state.last_reco
        st.success(f"✅ 최종 추천: **{reco['title']}**")
        st.write(reco["reason"])
        st.divider()

    # 3열 카드
    cols = st.columns(3)

    for i, m in enumerate(st.session_state.candidates):
        col = cols[i % 3]

        movie_id = m.get("id")
        title = m.get("title") or "제목 없음"
        rating = m.get("vote_average")
        overview = m.get("overview") or ""
        poster_url = safe_poster_url(m.get("poster_path"))

        # 예고편 링크 준비(캐시됨)
        trailer_url = None
        if movie_id:
            try:
                vids = movie_videos_cached(tmdb_key, int(movie_id), language)
                trailer_url = pick_trailer_youtube(vids)
            except Exception:
                trailer_url = None

        # 포스터 클릭 시: 예고편 있으면 예고편, 없으면 TMDB 페이지
        link_url = trailer_url or (f"{TMDB_MOVIE_WEB}{movie_id}" if movie_id else None)

        with col:
            with st.container(border=True):
                # 포스터(클릭 -> 예고편)
                if poster_url and link_url:
                    st.markdown(poster_clickable_html(poster_url, link_url, title), unsafe_allow_html=True)
                    st.caption("🖱️ 포스터 클릭 → 예고편(또는 TMDB 페이지)")
                elif poster_url:
                    st.image(poster_url, use_container_width=True)
                else:
                    st.info("포스터 없음")

                # 기본 정보
                st.markdown(f"### {title}")
                if rating is not None:
                    st.write(f"⭐ 평점: **{float(rating):.1f} / 10**")
                else:
                    st.write("⭐ 평점: 정보 없음")

                # 이미 본 영화 제외 체크
                watched_key = f"watched_{movie_id}"
                default_checked = movie_id in st.session_state.excluded_ids
                watched = st.checkbox("✅ 이미 봤어요 (다음 추천에서 제외)", value=default_checked, key=watched_key)
                if watched and movie_id:
                    st.session_state.excluded_ids.add(movie_id)
                if (not watched) and movie_id and (movie_id in st.session_state.excluded_ids):
                    st.session_state.excluded_ids.remove(movie_id)

                # 상세
                with st.expander("📖 상세 정보 / 예고편", expanded=False):
                    st.write(short_text(overview, 450))

                    # 앱 내 예고편 재생(추가 UX)
                    if trailer_url:
                        st.video(trailer_url)
                    elif movie_id:
                        st.link_button("🔗 TMDB에서 보기", f"{TMDB_MOVIE_WEB}{movie_id}")

                    # 간단 추천 이유(상황 기반)
                    if mood_label in ["힐링/잔잔", "감성/여운"]:
                        reason = "지금은 마음의 속도를 낮추는 영화가 잘 맞아서, 감정선/여운이 좋은 작품이 어울려요."
                    elif mood_label in ["통쾌/에너지", "긴장/스릴"]:
                        reason = "지금은 텐션과 몰입감이 필요해 보여서, 전개가 빠르고 에너지 있는 작품이 어울려요."
                    elif mood_label == "웃음/가벼움":
                        reason = "지금은 가볍게 웃고 리셋하는 게 목적이라, 부담 없이 즐길 수 있는 작품이 어울려요."
                    else:
                        reason = "현실을 잠깐 잊게 해주는 세계관이 필요해 보여서, 설정이 강한 작품이 어울려요."

                    st.caption(f"💡 추천 이유: {reason}")

    st.divider()
    st.caption("※ ‘다시 뽑기’는 체크한 ‘이미 본 영화’를 제외하고 후보를 새로 가져옵니다.")
else:
    st.info("왼쪽에 상황을 적고 **‘후보 가져오기’**를 눌러 시작해보세요! 🎬")
