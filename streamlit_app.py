import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import os
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# ページ設定
st.set_page_config(
    page_title="YouTube マーケティング分析ツール",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 環境変数を読み込み
load_dotenv()

# スタイル設定
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        color: #FF0000;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# YouTube API設定
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

@st.cache_resource
def init_youtube_api():
    """YouTube APIクライアントを初期化"""
    try:
        if not YOUTUBE_API_KEY:
            st.error("YouTube APIキーが設定されていません。.envファイルを確認してください。")
            return None
        return build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    except Exception as e:
        st.error(f"YouTube API初期化エラー: {e}")
        return None

# APIクライアントを初期化
youtube = init_youtube_api()

# タイトル
st.markdown('<h1 class="main-header">📺 YouTube マーケティング分析ツール</h1>', unsafe_allow_html=True)

# サイドバー
st.sidebar.title("🎯 分析メニュー")
analysis_type = st.sidebar.selectbox(
    "分析タイプを選択",
    ["動画検索・分析", "チャンネル分析", "トレンド分析", "競合分析", "キーワード分析"]
)

# メイン関数
def search_videos(keyword, max_results=10, order="relevance"):
    """動画を検索して詳細情報を取得"""
    
    # YouTubeAPIが初期化されているかチェック
    if not youtube:
        st.error("YouTube APIが初期化されていません。APIキーを確認してください。")
        return pd.DataFrame()
    
    try:
        # 動画を検索
        search_response = youtube.search().list(
            q=keyword,
            part='snippet',
            type='video',
            maxResults=max_results,
            order=order
        ).execute()
        
        # レスポンスの検証
        if 'items' not in search_response or not search_response['items']:
            st.warning("検索結果が見つかりませんでした。")
            return pd.DataFrame()
        
        video_ids = [item['id']['videoId'] for item in search_response['items']]
        
        # 動画の詳細情報を取得
        videos_response = youtube.videos().list(
            part='statistics,contentDetails,snippet',
            id=','.join(video_ids)
        ).execute()
        
        # レスポンスの検証
        if 'items' not in videos_response or not videos_response['items']:
            st.warning("動画の詳細情報を取得できませんでした。")
            return pd.DataFrame()
        
        videos_data = []
        for item in videos_response['items']:
            stats = item.get('statistics', {})
            snippet = item.get('snippet', {})
            
            # エンゲージメント率を計算
            view_count = int(stats.get('viewCount', 0))
            like_count = int(stats.get('likeCount', 0))
            comment_count = int(stats.get('commentCount', 0))
            
            engagement_rate = 0
            if view_count > 0:
                engagement_rate = ((like_count + comment_count) / view_count) * 100
            
            # サムネイルURLの安全な取得
            thumbnail_url = ""
            if 'thumbnails' in snippet and 'medium' in snippet['thumbnails']:
                thumbnail_url = snippet['thumbnails']['medium']['url']
            
            videos_data.append({
                'タイトル': snippet.get('title', 'タイトル不明'),
                'チャンネル': snippet.get('channelTitle', 'チャンネル不明'),
                '公開日': snippet.get('publishedAt', '')[:10] if snippet.get('publishedAt') else '',
                '視聴回数': view_count,
                'いいね数': like_count,
                'コメント数': comment_count,
                'エンゲージメント率': round(engagement_rate, 2),
                '動画ID': item.get('id', ''),
                'サムネイル': thumbnail_url
            })
        
        return pd.DataFrame(videos_data)
    
    except HttpError as e:
        st.error(f"APIエラー: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"予期しないエラーが発生しました: {e}")
        return pd.DataFrame()

def analyze_channel(channel_id):
    """チャンネルの詳細分析"""
    
    # YouTubeAPIが初期化されているかチェック
    if not youtube:
        st.error("YouTube APIが初期化されていません。APIキーを確認してください。")
        return None, pd.DataFrame()
    
    try:
        # チャンネル情報を取得
        channel_response = youtube.channels().list(
            part='statistics,snippet,contentDetails',
            id=channel_id
        ).execute()
        
        # レスポンスの検証を強化
        if not channel_response or 'items' not in channel_response or not channel_response['items']:
            st.error("チャンネルが見つかりません。チャンネルIDを確認してください。")
            return None, pd.DataFrame()
        
        item = channel_response['items'][0]
        stats = item.get('statistics', {})
        snippet = item.get('snippet', {})
        content_details = item.get('contentDetails', {})
        
        # サムネイルURLの安全な取得
        thumbnail_url = ""
        if 'thumbnails' in snippet and 'high' in snippet['thumbnails']:
            thumbnail_url = snippet['thumbnails']['high']['url']
        
        channel_data = {
            'チャンネル名': snippet.get('title', 'チャンネル名不明'),
            '登録者数': int(stats.get('subscriberCount', 0)),
            '動画本数': int(stats.get('videoCount', 0)),
            '総視聴回数': int(stats.get('viewCount', 0)),
            '開設日': snippet.get('publishedAt', '')[:10] if snippet.get('publishedAt') else '',
            '説明': (snippet.get('description', '')[:200] + "...") if snippet.get('description') else "説明なし",
            'サムネイル': thumbnail_url
        }
        
        # 最新動画を取得
        recent_videos = pd.DataFrame()
        
        if 'relatedPlaylists' in content_details and 'uploads' in content_details['relatedPlaylists']:
            playlist_id = content_details['relatedPlaylists']['uploads']
            
            try:
                playlist_response = youtube.playlistItems().list(
                    part='snippet',
                    playlistId=playlist_id,
                    maxResults=10
                ).execute()
                
                if 'items' in playlist_response and playlist_response['items']:
                    recent_videos_data = []
                    for video in playlist_response['items']:
                        video_snippet = video.get('snippet', {})
                        recent_videos_data.append({
                            'タイトル': video_snippet.get('title', 'タイトル不明'),
                            '公開日': video_snippet.get('publishedAt', '')[:10] if video_snippet.get('publishedAt') else ''
                        })
                    recent_videos = pd.DataFrame(recent_videos_data)
            except HttpError as e:
                st.warning(f"最新動画の取得に失敗しました: {e}")
        
        return channel_data, recent_videos
    
    except HttpError as e:
        st.error(f"APIエラー: {e}")
        return None, pd.DataFrame()
    except Exception as e:
        st.error(f"予期しないエラーが発生しました: {e}")
        return None, pd.DataFrame()

# メインコンテンツ
if analysis_type == "動画検索・分析":
    st.header("🔍 動画検索・分析")
    
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        keyword = st.text_input("検索キーワード", placeholder="例: Python プログラミング")
    with col2:
        max_results = st.number_input("取得件数", min_value=1, max_value=50, value=10)
    with col3:
        order = st.selectbox("並び順", ["relevance", "date", "viewCount", "rating"])
    
    if st.button("検索", type="primary", use_container_width=True):
        if keyword:
            with st.spinner("検索中..."):
                df = search_videos(keyword, max_results, order)
                
            if not df.empty:
                # メトリクスの表示
                st.subheader("📊 検索結果の統計")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("検索結果数", f"{len(df)}件")
                with col2:
                    st.metric("平均視聴回数", f"{df['視聴回数'].mean():,.0f}回")
                with col3:
                    st.metric("平均エンゲージメント率", f"{df['エンゲージメント率'].mean():.2f}%")
                with col4:
                    st.metric("総視聴回数", f"{df['視聴回数'].sum():,.0f}回")
                
                # グラフ表示
                st.subheader("📈 視聴回数とエンゲージメント率の関係")
                fig = px.scatter(df, 
                    x='視聴回数', 
                    y='エンゲージメント率',
                    size='いいね数',
                    hover_data=['タイトル', 'チャンネル'],
                    color='エンゲージメント率',
                    color_continuous_scale='Reds'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                # 動画リスト
                st.subheader("🎥 動画一覧")
                for idx, row in df.iterrows():
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        if row['サムネイル']:
                            st.image(row['サムネイル'], width=200)
                    with col2:
                        st.markdown(f"### {row['タイトル']}")
                        st.text(f"チャンネル: {row['チャンネル']} | 公開日: {row['公開日']}")
                        
                        col_a, col_b, col_c, col_d = st.columns(4)
                        with col_a:
                            st.metric("視聴回数", f"{row['視聴回数']:,}")
                        with col_b:
                            st.metric("いいね数", f"{row['いいね数']:,}")
                        with col_c:
                            st.metric("コメント数", f"{row['コメント数']:,}")
                        with col_d:
                            st.metric("エンゲージメント率", f"{row['エンゲージメント率']}%")
                        
                        if row['動画ID']:
                            st.markdown(f"[YouTubeで見る](https://youtube.com/watch?v={row['動画ID']})")
                    st.divider()
        else:
            st.warning("検索キーワードを入力してください")

elif analysis_type == "チャンネル分析":
    st.header("📺 チャンネル分析")
    
    channel_input = st.text_input(
        "チャンネルID または URL", 
        placeholder="例: UCNtZPzvkjjB3EuPMNY71cmA"
    )
    
    # URLからチャンネルIDを抽出
    if "youtube.com/channel/" in channel_input:
        channel_id = channel_input.split("channel/")[1].split("/")[0]
    else:
        channel_id = channel_input
    
    if st.button("分析", type="primary", use_container_width=True):
        if channel_id:
            with st.spinner("分析中..."):
                channel_data, recent_videos = analyze_channel(channel_id)
                
            if channel_data:
                col1, col2 = st.columns([1, 3])
                with col1:
                    if channel_data['サムネイル']:
                        st.image(channel_data['サムネイル'])
                with col2:
                    st.title(channel_data['チャンネル名'])
                    st.text(f"開設日: {channel_data['開設日']}")
                
                # メトリクス
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("登録者数", f"{channel_data['登録者数']:,}")
                with col2:
                    st.metric("動画本数", f"{channel_data['動画本数']:,}")
                with col3:
                    st.metric("総視聴回数", f"{channel_data['総視聴回数']:,}")
                with col4:
                    avg_views = channel_data['総視聴回数'] / max(channel_data['動画本数'], 1)
                    st.metric("平均視聴回数", f"{avg_views:,.0f}")
                
                # 説明
                st.subheader("📝 チャンネル説明")
                st.text(channel_data['説明'])
                
                # 最新動画
                if not recent_videos.empty:
                    st.subheader("🎬 最新動画")
                    st.dataframe(recent_videos, use_container_width=True)
        else:
            st.warning("チャンネルIDを入力してください")

elif analysis_type == "トレンド分析":
    st.header("🔥 トレンド分析")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        region = st.selectbox("地域", ["JP", "US", "GB", "KR", "IN"])
    with col2:
        category = st.selectbox(
            "カテゴリ",
            ["0 - すべて", "10 - 音楽", "20 - ゲーム", "22 - ブログ", "23 - コメディ", "24 - エンターテイメント"]
        )
    with col3:
        max_results = st.number_input("取得件数", min_value=1, max_value=50, value=10)
    
    if st.button("トレンドを取得", type="primary", use_container_width=True):
        if not youtube:
            st.error("YouTube APIが初期化されていません。")
        else:
            with st.spinner("取得中..."):
                try:
                    category_id = category.split(" - ")[0]
                    
                    request_params = {
                        'part': 'snippet,statistics',
                        'chart': 'mostPopular',
                        'regionCode': region,
                        'maxResults': max_results
                    }
                    
                    if category_id != "0":
                        request_params['videoCategoryId'] = category_id
                    
                    response = youtube.videos().list(**request_params).execute()
                    
                    # レスポンスの検証
                    if 'items' not in response or not response['items']:
                        st.warning("トレンド動画が見つかりませんでした。")
                    else:
                        trending_data = []
                        for item in response['items']:
                            stats = item.get('statistics', {})
                            snippet = item.get('snippet', {})
                            
                            # サムネイルURLの安全な取得
                            thumbnail_url = ""
                            if 'thumbnails' in snippet and 'medium' in snippet['thumbnails']:
                                thumbnail_url = snippet['thumbnails']['medium']['url']
                            
                            trending_data.append({
                                'タイトル': snippet.get('title', 'タイトル不明'),
                                'チャンネル': snippet.get('channelTitle', 'チャンネル不明'),
                                '視聴回数': int(stats.get('viewCount', 0)),
                                'いいね数': int(stats.get('likeCount', 0)),
                                'サムネイル': thumbnail_url,
                                '動画ID': item.get('id', '')
                            })
                        
                        df = pd.DataFrame(trending_data)
                        
                        if not df.empty:
                            # グラフ表示
                            st.subheader("📊 トレンド動画の視聴回数")
                            fig = px.bar(df.head(10), 
                                x='タイトル', 
                                y='視聴回数',
                                color='視聴回数',
                                color_continuous_scale='Reds'
                            )
                            fig.update_xaxes(tickangle=-45)
                            fig.update_layout(height=500)
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # 動画リスト
                            st.subheader("🎥 トレンド動画")
                            for i, (_, row) in enumerate(df.iterrows(), start=1):
                                col1, col2 = st.columns([1, 4])
                                with col1:
                                    if row['サムネイル']:
                                        st.image(row['サムネイル'], width=200)
                                with col2:
                                    st.markdown(f"### {i}. {row['タイトル']}")
                                    st.text(f"チャンネル: {row['チャンネル']}")
                                    col_a, col_b = st.columns(2)
                                    with col_a:
                                        st.metric("視聴回数", f"{row['視聴回数']:,}")
                                    with col_b:
                                        st.metric("いいね数", f"{row['いいね数']:,}")
                                    if row['動画ID']:
                                        st.markdown(f"[YouTubeで見る](https://youtube.com/watch?v={row['動画ID']})")
                                st.divider()
                                
                except HttpError as e:
                    st.error(f"APIエラー: {e}")
                except Exception as e:
                    st.error(f"予期しないエラーが発生しました: {e}")

elif analysis_type == "競合分析":
    st.header("⚔️ 競合チャンネル分析")
    
    st.info("複数のチャンネルを比較分析します（最大5つまで）")
    
    channels = []
    for i in range(5):
        channel = st.text_input(f"チャンネルID {i+1}", key=f"channel_{i}")
        if channel:
            channels.append(channel)
    
    if st.button("比較分析", type="primary", use_container_width=True) and channels:
        if not youtube:
            st.error("YouTube APIが初期化されていません。")
        else:
            with st.spinner("分析中..."):
                comparison_data = []
                
                for channel_id in channels:
                    try:
                        channel_response = youtube.channels().list(
                            part='statistics,snippet',
                            id=channel_id
                        ).execute()
                        
                        if channel_response and 'items' in channel_response and channel_response['items']:
                            item = channel_response['items'][0]
                            stats = item.get('statistics', {})
                            snippet = item.get('snippet', {})
                            
                            video_count = max(int(stats.get('videoCount', 1)), 1)  # ゼロ除算を防ぐ
                            
                            comparison_data.append({
                                'チャンネル名': snippet.get('title', 'チャンネル名不明'),
                                '登録者数': int(stats.get('subscriberCount', 0)),
                                '動画本数': int(stats.get('videoCount', 0)),
                                '総視聴回数': int(stats.get('viewCount', 0)),
                                '平均視聴回数': int(stats.get('viewCount', 0)) / video_count
                            })
                    except Exception as e:
                        st.warning(f"チャンネルID {channel_id} の取得に失敗しました: {e}")
                
                if comparison_data:
                    df = pd.DataFrame(comparison_data)
                    
                    # レーダーチャート
                    st.subheader("📊 総合比較")
                    
                    # 正規化
                    df_normalized = df.copy()
                    for col in ['登録者数', '動画本数', '総視聴回数', '平均視聴回数']:
                        max_val = df[col].max()
                        if max_val > 0:
                            df_normalized[col] = (df[col] / max_val) * 100
                    
                    fig = go.Figure()
                    
                    for _, row in df_normalized.iterrows():
                        values = row[['登録者数', '動画本数', '総視聴回数', '平均視聴回数']].tolist()
                        values.append(values[0])  # 最初の値を追加してループを閉じる
                        
                        fig.add_trace(
                            go.Scatterpolar(
                                r=values,
                                theta=['登録者数', '動画本数', '総視聴回数', '平均視聴回数', '登録者数'],
                                fill='toself',
                                name=row['チャンネル名']
                            )
                        )
                    
                    fig.update_layout(
                        polar=dict(
                            radialaxis=dict(
                                visible=True,
                                range=[0, 100]
                            )),
                        showlegend=True,
                        height=500
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 詳細テーブル
                    st.subheader("📋 詳細データ")
                    st.dataframe(df.style.format({
                        '登録者数': '{:,}',
                        '動画本数': '{:,}',
                        '総視聴回数': '{:,}',
                        '平均視聴回数': '{:,.0f}'
                    }), use_container_width=True)
                else:
                    st.error("チャンネルデータを取得できませんでした。チャンネルIDを確認してください。")

else:  # キーワード分析
    st.header("🔑 キーワード分析")
    
    base_keyword = st.text_input("基本キーワード", placeholder="例: Python")
    
    if st.button("関連キーワードを分析", type="primary", use_container_width=True):
        if base_keyword:
            if not youtube:
                st.error("YouTube APIが初期化されていません。")
            else:
                with st.spinner("分析中..."):
                    try:
                        # 基本キーワードで検索
                        search_response = youtube.search().list(
                            q=base_keyword,
                            part='snippet',
                            type='video',
                            maxResults=50
                        ).execute()
                        
                        # レスポンスの検証
                        if 'items' not in search_response or not search_response['items']:
                            st.warning("検索結果が見つかりませんでした。")
                        else:
                            # キーワードを抽出
                            keywords = {}
                            
                            for item in search_response['items']:
                                snippet = item.get('snippet', {})
                                title = snippet.get('title', '').lower()
                                # タイトルから単語を抽出
                                words = title.split()
                                for word in words:
                                    if len(word) > 3 and word != base_keyword.lower():
                                        keywords[word] = keywords.get(word, 0) + 1
                            
                            # 上位キーワード
                            top_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:20]
                            
                            if top_keywords:
                                # 棒グラフ
                                df = pd.DataFrame(top_keywords, columns=['キーワード', '出現回数'])
                                
                                fig = px.bar(df, 
                                    x='出現回数', 
                                    y='キーワード',
                                    orientation='h',
                                    color='出現回数',
                                    color_continuous_scale='Reds'
                                )
                                fig.update_layout(height=600)
                                st.plotly_chart(fig, use_container_width=True)
                                
                                # ワードクラウド風の表示
                                st.subheader("🏷️ 関連キーワード")
                                cols = st.columns(4)
                                for idx, (keyword, count) in enumerate(top_keywords):
                                    with cols[idx % 4]:
                                        st.button(f"{keyword} ({count})", key=f"kw_{idx}")
                            else:
                                st.warning("関連キーワードが見つかりませんでした。")
                                
                    except HttpError as e:
                        st.error(f"APIエラー: {e}")
                    except Exception as e:
                        st.error(f"予期しないエラーが発生しました: {e}")
        else:
            st.warning("キーワードを入力してください")

# フッター
st.markdown("---")
st.markdown("🚀 YouTube マーケティング分析ツール | Powered by YouTube Data API v3")