import sqlite3
import pickle  # 데이터 직렬화 및 역직렬화를 위한 모듈
import streamlit as st  # Streamlit 모듈
from tmdbv3api import Movie, TMDb  # 영화 정보를 가져오기 위한 TMDB API 모듈
import pandas as pd  # 데이터 조작 및 분석을 위한 모듈
import altair as alt  # 대화형 시각화를 위한 모듈
import plotly.express as px  # 대화형 시각화를 위한 모듈
import streamlit.components.v1 as components  # Streamlit 컴포넌트 모듈
from streamlit_option_menu import option_menu  # 옵션 메뉴를 위한 모듈

# TMDb API 설정 (API Key와 언어 설정)
tmdb = TMDb()
tmdb.api_key = 'Your_Api_Key'
tmdb.language = 'ko-KR'
movie = Movie()

# Streamlit 페이지 설정
st.set_page_config(
    page_title="MyNextMovies",
    page_icon="./images/clapperboard_cinema_icon-icons.com_66131.png",
    layout='wide'
)

# 데이터베이스 연결
conn = sqlite3.connect('movies.db')
c = conn.cursor()

# 평점 테이블 생성 (평점 테이블이 없으면 새로 생성)
c.execute('''
    CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER,
        user TEXT,
        rating INTEGER,
        review TEXT
    )
''')
conn.commit()

# 세션 상태 초기화 (검색 결과 및 검색된 영화 목록을 세션 상태에 저장)
if 'search_results' not in st.session_state:
    st.session_state['search_results'] = None

if 'search_movies' not in st.session_state:
    st.session_state['search_movies'] = None

# 영화 추천 함수 (선택한 영화와 유사한 영화를 추천)
def get_recommendations(title):
    # 선택한 영화의 인덱스 가져오기
    idx = movies[movies['title'] == title].index[0]
    # 유사도 점수 계산
    sim_scores = list(enumerate(cosine_sim[idx]))
    # 유사도 점수 내림차순으로 정렬
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
    # 상위 10개의 유사한 영화 선택
    sim_scores = sim_scores[1:11]
    movie_indices = [i[0] for i in sim_scores]
    similarities = [i[1] for i in sim_scores]

    # 추천 영화 포스터와 제목 가져오기
    images = []
    titles = []
    for i in movie_indices:
        id = movies['id'].iloc[i]
        details = movie.details(id)

        image_path = details['poster_path']
        if image_path:
            image_path = 'https://image.tmdb.org/t/p/w500' + image_path
        else:
            image_path = 'no_image.jpg'

        images.append(image_path)
        titles.append(details['title'])

    return images, titles, similarities

# 영화의 상세 정보와 평점 입력 폼을 표시하는 함수
def show_movie_details(title):
    movie_info = movie.search(title)[0]
    movie_id = movie_info.id
    details = movie.details(movie_id)

    st.write(f"**{details['title']}** ({details['release_date']})")
    st.image(f"https://image.tmdb.org/t/p/w500{details['poster_path']}", use_column_width=False, width=400)
    st.write(f"**장르:** {', '.join([genre['name'] for genre in details['genres']])}")
    st.write(f"**평점:** {details['vote_average']} (투표 수: {details['vote_count']})")
    st.write(f"**개요:** {details['overview']}")

    st.write("### 리뷰 작성")
    user = st.text_input("이름", "")
    rating = st.slider("평점", 1, 10, 5)
    review = st.text_area("리뷰")

    if st.button("리뷰 제출"):
        # 이름이 입력되지 않은 경우 '익명'으로 설정
        if not user:
            user = '익명'
        c.execute('''
            INSERT INTO ratings (movie_id, user, rating, review)
            VALUES (?, ?, ?, ?)
        ''', (movie_id, user, rating, review))
        conn.commit()
        st.success("리뷰가 제출되었습니다!")

    st.write("### 리뷰 목록")
    reviews = c.execute('''
        SELECT id, user, rating, review FROM ratings
        WHERE movie_id = ?
    ''', (movie_id,)).fetchall()

    for review in reviews:
        st.write(f"**{review[1]}** (평점: {review[2]})")
        st.write(review[3])
        if st.button("삭제", key=f"del_{review[0]}"):
            c.execute('DELETE FROM ratings WHERE id = ?', (review[0],))
            conn.commit()
            # 삭제 후에도 리뷰 목록을 다시 로드하여 갱신
            st.experimental_rerun()
        st.write("---")

# 사전에 저장된 영화 데이터 및 유사도 매트릭스 로드
movies = pickle.load(open('movies.pickle', 'rb'))
cosine_sim = pickle.load(open('cosine_sim.pickle', 'rb'))

# 메뉴 설정 및 페이지 전환
with st.sidebar:
    choose = option_menu("Menu", ["Main", "Bar Graph", "Circular Graph", "Details", "Search", "Search Details"], 
                         icons=['house', 'bar-chart-fill', 'pie-chart-fill', 'info-circle-fill', 'search', 'book'], 
                         menu_icon="app-indicator", default_index=0, 
                         styles={
                             "container": {"padding": "5!important", "background-color": "#000"},
                             "icon": {"color": "orange", "font-size": "25px"},
                             "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px", "--hover-color": "#323232"},
                             "nav-link-selected": {"background-color": "#020f37"},
                         })

# CSS to hide the image enlarge button
hide_img_button = """
    <style>
    button[title="View fullscreen"] {
        display: none;
    }
    </style>
"""
st.markdown(hide_img_button, unsafe_allow_html=True)

# 영화 제목 검색 함수
def search_movie_titles(query):
    if query:
        matched_titles = movies[movies['title'].str.contains(query, case=False, na=False)]['title'].values
        return matched_titles
    return []

# "Main" 메뉴 선택 시 실행되는 코드
if choose == "Main":
    st.header('MyNextMovies')
    movie_list = movies['title'].values
    title = st.selectbox('당신이 좋아하는 영화를 고르세요!', movie_list)

    if st.button('검색하기'):
        with st.spinner('잠시 기다려주세요...'):
            images, titles, similarities = get_recommendations(title)
            st.session_state['search_results'] = (images, titles, similarities)

    if st.session_state['search_results']:
        images, titles, similarities = st.session_state['search_results']
        idx = 0
        for i in range(0, 2):
            cols = st.columns(5)
            for col in cols:
                col.image(images[idx], use_column_width=True)
                col.write(titles[idx])
                idx += 1

# "Bar Graph" 메뉴 선택 시 실행되는 코드
elif choose == "Bar Graph":
    if st.session_state['search_results']:
        images, titles, similarities = st.session_state['search_results']
        df_similarities = pd.DataFrame({
            'title': titles,
            'similarity': similarities
        })
        
        color_scale = alt.Scale(scheme='blues')
        chart_similarities = (
            alt.Chart(df_similarities)
            .mark_bar()
            .encode(
                y=alt.Y("title:N", title='영화제목'),
                x=alt.X("similarity:Q", title="유사도",
                        axis=alt.Axis(tickMinStep=0.04)),
                color=alt.Color("similarity:Q", scale=color_scale, legend=None),
            )
            .properties(height=500)
        )
        st.altair_chart(chart_similarities, theme="streamlit", use_container_width=True)

# "Circular Graph" 메뉴 선택 시 실행되는 코드
elif choose == "Circular Graph":
    if st.session_state['search_results']:
        images, titles, similarities = st.session_state['search_results']
        df_similarities = pd.DataFrame({
            'title': titles,
            'similarity': similarities
        })
        fig = px.pie(df_similarities, values='similarity', names='title', title='유사도 분포')
        st.plotly_chart(fig)

# "Details" 메뉴 선택 시 실행되는 코드
elif choose == "Details":
    if st.session_state['search_results']:
        images, titles, similarities = st.session_state['search_results']
        selected_movie = st.selectbox('영화 선택', titles)
        show_movie_details(selected_movie)

# "Search" 메뉴 선택 시 실행되는 코드
elif choose == "Search":
    st.header('영화 검색')

    movie_list = movies['title'].values
    title = st.selectbox('검색할 영화를 고르세요!', movie_list)

    if st.button('검색하기'):
        with st.spinner('잠시 기다려주세요...'):
            search_results = movie.search(title)
            st.session_state['search_movies'] = search_results
    
    if st.session_state['search_movies']:
        search_results = st.session_state['search_movies']
        images = []
        titles = []
        movie_ids = []
        for result in search_results:
            if result.poster_path:
                images.append(f"https://image.tmdb.org/t/p/w500{result.poster_path}")
            else:
                images.append('no_image.jpg')
            titles.append(result.title)
            movie_ids.append(result.id)

        idx = 0
        for i in range(0, 2):
            cols = st.columns(5)
            for col in cols:
                if idx < len(images):
                    col.image(images[idx], use_column_width=True)
                    col.write(titles[idx])
                    idx += 1

# "Search Details" 메뉴 선택 시 실행되는 코드
elif choose == "Search Details":
    st.header('검색된 영화 상세 정보')

    if st.session_state['search_movies']:
        search_results = st.session_state['search_movies']
        titles = [result.title for result in search_results]
        selected_movie = st.selectbox('영화 선택', titles)
        show_movie_details(selected_movie)
