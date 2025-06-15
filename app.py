from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
import pandas as pd
from pydantic import BaseModel
from typing import List, Dict, Optional, Any

# 環境変数を読み込み
load_dotenv()

app = FastAPI(
    title="YouTube マーケティング分析ツール",
    description="YouTubeの動画・チャンネル分析、競合分析、トレンド分析を行うツール",
    version="1.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# YouTube API設定
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
youtube = None

# レスポンスモデル
class VideoInfo(BaseModel):
    video_id: str
    title: str
    channel_id: str
    channel_title: str
    published_at: str
    view_count: int
    like_count: int
    comment_count: int
    duration: str
    thumbnail_url: str
    engagement_rate: float
    description: str

class ChannelInfo(BaseModel):
    channel_id: str
    title: str
    description: str
    subscriber_count: int
    video_count: int
    view_count: int
    published_at: str
    thumbnail_url: str
    average_views: float

class ChannelComparison(BaseModel):
    channels: List[ChannelInfo]
    comparison_metrics: Dict[str, Any]

def initialize_youtube_api():
    """YouTube APIクライアントを初期化"""
    global youtube
    try:
        if not YOUTUBE_API_KEY:
            print("警告: YOUTUBE_API_KEYが設定されていません")
            return False
        
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        print("YouTube API接続成功")
        return True
    except Exception as e:
        print(f"YouTube API初期化エラー: {e}")
        return False

@app.on_event("startup")
async def startup_event():
    initialize_youtube_api()

@app.get("/")
def root():
    """ルートエンドポイント"""
    return {
        "message": "YouTube マーケティング分析ツールへようこそ！",
        "version": "1.0.0",
        "endpoints": {
            "/docs": "APIドキュメント",
            "/search": "動画検索",
            "/video/{video_id}": "動画詳細分析",
            "/channel/{channel_id}": "チャンネル分析",
            "/trending": "トレンド動画",
            "/compare-channels": "チャンネル比較"
        }
    }

@app.get("/search", response_model=List[VideoInfo])
def search_videos(
    keyword: str = Query(..., description="検索キーワード"),
    max_results: int = Query(10, ge=1, le=50, description="取得件数"),
    order: str = Query("relevance", description="並び順: relevance, date, rating, viewCount")
):
    """キーワードで動画を検索し、詳細情報を取得"""
    
    # ここに挿入！（この行の下に）
    # 一時的なテストモード
    if not youtube:
        return [
            VideoInfo(
                video_id="test123",
                title="Python プログラミング入門",
                channel_id="ch123",
                channel_title="テストチャンネル",
                published_at="2024-01-01T00:00:00Z",
                view_count=10000,
                like_count=500,
                comment_count=50,
                duration="PT10M30S",
                thumbnail_url="https://via.placeholder.com/320x180",
                engagement_rate=5.5,
                description="これはテストデータです..."
            )
        ]
    
    if not youtube:
        raise HTTPException(status_code=503, detail="YouTube APIが利用できません")    
    try:
        # 動画を検索
        search_response = youtube.search().list(
            q=keyword,
            part='snippet',
            type='video',
            maxResults=max_results,
            order=order
        ).execute()
        
        video_ids = [item['id']['videoId'] for item in search_response['items']]
        
        # 動画の詳細情報を取得
        videos_response = youtube.videos().list(
            part='statistics,contentDetails,snippet',
            id=','.join(video_ids)
        ).execute()
        
        videos = []
        for item in videos_response['items']:
            stats = item['statistics']
            snippet = item['snippet']
            
            # エンゲージメント率を計算
            view_count = int(stats.get('viewCount', 0))
            like_count = int(stats.get('likeCount', 0))
            comment_count = int(stats.get('commentCount', 0))
            
            engagement_rate = 0
            if view_count > 0:
                engagement_rate = ((like_count + comment_count) / view_count) * 100
            
            video_info = VideoInfo(
                video_id=item['id'],
                title=snippet['title'],
                channel_id=snippet['channelId'],
                channel_title=snippet['channelTitle'],
                published_at=snippet['publishedAt'],
                view_count=view_count,
                like_count=like_count,
                comment_count=comment_count,
                duration=item['contentDetails']['duration'],
                thumbnail_url=snippet['thumbnails']['high']['url'],
                engagement_rate=round(engagement_rate, 2),
                description=snippet['description'][:200] + "..."
            )
            videos.append(video_info)
        
        return videos
        
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/video/{video_id}")
def analyze_video(video_id: str):
    """特定の動画の詳細分析"""
    
    if not youtube:
        raise HTTPException(status_code=503, detail="YouTube APIが利用できません")
    
    try:
        # 動画情報を取得
        video_response = youtube.videos().list(
            part='statistics,contentDetails,snippet',
            id=video_id
        ).execute()
        
        if not video_response['items']:
            raise HTTPException(status_code=404, detail="動画が見つかりません")
        
        item = video_response['items'][0]
        stats = item['statistics']
        snippet = item['snippet']
        
        # コメントの分析（最新10件）
        comments = []
        try:
            comments_response = youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=10,
                order='relevance'
            ).execute()
            
            for comment in comments_response['items']:
                comments.append({
                    'text': comment['snippet']['topLevelComment']['snippet']['textDisplay'],
                    'likeCount': comment['snippet']['topLevelComment']['snippet']['likeCount'],
                    'publishedAt': comment['snippet']['topLevelComment']['snippet']['publishedAt']
                })
        except:
            comments = []
        
        # タグ分析
        tags = snippet.get('tags', [])
        
        return {
            'video_info': {
                'title': snippet['title'],
                'channel': snippet['channelTitle'],
                'published_at': snippet['publishedAt'],
                'description': snippet['description']
            },
            'statistics': {
                'view_count': int(stats.get('viewCount', 0)),
                'like_count': int(stats.get('likeCount', 0)),
                'dislike_count': int(stats.get('dislikeCount', 0)),
                'comment_count': int(stats.get('commentCount', 0)),
                'engagement_rate': round(((int(stats.get('likeCount', 0)) + int(stats.get('commentCount', 0))) / int(stats.get('viewCount', 1))) * 100, 2)
            },
            'tags': tags[:10],
            'top_comments': comments,
            'content_details': {
                'duration': item['contentDetails']['duration'],
                'definition': item['contentDetails']['definition'],
                'caption': item['contentDetails'].get('caption', 'false')
            }
        }
        
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/channel/{channel_id}", response_model=ChannelInfo)
def analyze_channel(channel_id: str):
    """チャンネルの詳細分析"""
    
    if not youtube:
        raise HTTPException(status_code=503, detail="YouTube APIが利用できません")
    
    try:
        # チャンネル情報を取得
        channel_response = youtube.channels().list(
            part='statistics,snippet,contentDetails',
            id=channel_id
        ).execute()
        
        if not channel_response['items']:
            raise HTTPException(status_code=404, detail="チャンネルが見つかりません")
        
        item = channel_response['items'][0]
        stats = item['statistics']
        snippet = item['snippet']
        
        # 平均視聴回数を計算
        view_count = int(stats.get('viewCount', 0))
        video_count = int(stats.get('videoCount', 1))
        average_views = view_count / video_count if video_count > 0 else 0
        
        channel_info = ChannelInfo(
            channel_id=channel_id,
            title=snippet['title'],
            description=snippet['description'][:200] + "..." if snippet['description'] else "",
            subscriber_count=int(stats.get('subscriberCount', 0)),
            video_count=video_count,
            view_count=view_count,
            published_at=snippet['publishedAt'],
            thumbnail_url=snippet['thumbnails']['high']['url'],
            average_views=round(average_views, 0)
        )
        
        return channel_info
        
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/trending")
def get_trending_videos(
    region_code: str = Query("JP", description="地域コード（JP=日本）"),
    category_id: str = Query("0", description="カテゴリID（0=全て）"),
    max_results: int = Query(10, ge=1, le=50)
):
    """トレンド動画を取得"""
    
    if not youtube:
        raise HTTPException(status_code=503, detail="YouTube APIが利用できません")
    
    try:
        # トレンド動画を取得
        request = youtube.videos().list(
            part='snippet,statistics',
            chart='mostPopular',
            regionCode=region_code,
            maxResults=max_results
        )
        
        if category_id != "0":
            request = youtube.videos().list(
                part='snippet,statistics',
                chart='mostPopular',
                regionCode=region_code,
                videoCategoryId=category_id,
                maxResults=max_results
            )
        
        response = request.execute()
        
        trending_videos = []
        for item in response['items']:
            stats = item['statistics']
            snippet = item['snippet']
            
            trending_videos.append({
                'video_id': item['id'],
                'title': snippet['title'],
                'channel': snippet['channelTitle'],
                'published_at': snippet['publishedAt'],
                'view_count': int(stats.get('viewCount', 0)),
                'like_count': int(stats.get('likeCount', 0)),
                'thumbnail_url': snippet['thumbnails']['high']['url'],
                'category': snippet.get('categoryId', 'N/A')
            })
        
        return {
            'region': region_code,
            'total': len(trending_videos),
            'videos': trending_videos
        }
        
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/compare-channels")
def compare_channels(channel_ids: List[str] = Query(..., description="比較するチャンネルIDのリスト")):
    """複数のチャンネルを比較分析"""
    
    if not youtube:
        raise HTTPException(status_code=503, detail="YouTube APIが利用できません")
    
    if len(channel_ids) > 5:
        raise HTTPException(status_code=400, detail="一度に比較できるチャンネルは5つまでです")
    
    try:
        channels_data = []
        
        for channel_id in channel_ids:
            channel_info = analyze_channel(channel_id)
            channels_data.append(channel_info)
        
        # 比較メトリクスを計算
        df = pd.DataFrame([c.dict() for c in channels_data])
        
        comparison_metrics = {
            'average_metrics': {
                'avg_subscribers': int(df['subscriber_count'].mean()),
                'avg_videos': int(df['video_count'].mean()),
                'avg_views': int(df['view_count'].mean()),
                'avg_views_per_video': int(df['average_views'].mean())
            },
            'rankings': {
                'by_subscribers': df.sort_values('subscriber_count', ascending=False)['title'].tolist(),
                'by_total_views': df.sort_values('view_count', ascending=False)['title'].tolist(),
                'by_avg_views': df.sort_values('average_views', ascending=False)['title'].tolist()
            },
            'growth_potential': []
        }
        
        # 成長ポテンシャルを分析
        for _, channel in df.iterrows():
            if channel['subscriber_count'] > 0:
                engagement_score = (channel['average_views'] / channel['subscriber_count']) * 100
                comparison_metrics['growth_potential'].append({
                    'channel': channel['title'],
                    'engagement_score': round(engagement_score, 2),
                    'rating': 'High' if engagement_score > 10 else 'Medium' if engagement_score > 5 else 'Low'
                })
        
        return ChannelComparison(
            channels=channels_data,
            comparison_metrics=comparison_metrics
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/keyword-suggestions")
def get_keyword_suggestions(
    base_keyword: str = Query(..., description="基本キーワード"),
    max_results: int = Query(20, ge=5, le=50)
):
    """関連キーワードの提案"""
    
    if not youtube:
        raise HTTPException(status_code=503, detail="YouTube APIが利用できません")
    
    try:
        # 基本キーワードで検索
        search_response = youtube.search().list(
            q=base_keyword,
            part='snippet',
            type='video',
            maxResults=max_results
        ).execute()
        
        # 関連キーワードを抽出
        keywords = set()
        keywords.add(base_keyword)
        
        for item in search_response['items']:
            # タイトルからキーワードを抽出
            title_words = item['snippet']['title'].lower().split()
            for word in title_words:
                if len(word) > 3 and word not in ['this', 'that', 'with', 'from']:
                    keywords.add(word)
            
            # タグを追加
            video_id = item['id']['videoId']
            try:
                video_response = youtube.videos().list(
                    part='snippet',
                    id=video_id
                ).execute()
                
                if video_response['items']:
                    tags = video_response['items'][0]['snippet'].get('tags', [])
                    keywords.update(tags[:5])
            except:
                pass
        
        # キーワードの人気度を分析
        keyword_analysis = []
        for keyword in list(keywords)[:20]:
            if keyword != base_keyword:
                # 各キーワードの検索結果数を取得
                try:
                    search_count = youtube.search().list(
                        q=keyword,
                        part='id',
                        type='video',
                        maxResults=1
                    ).execute()
                    
                    total_results = search_count.get('pageInfo', {}).get('totalResults', 0)
                    keyword_analysis.append({
                        'keyword': keyword,
                        'search_volume': total_results,
                        'relevance': 'High' if base_keyword.lower() in keyword.lower() else 'Medium'
                    })
                except:
                    pass
        
        # 検索ボリュームでソート
        keyword_analysis.sort(key=lambda x: x['search_volume'], reverse=True)
        
        return {
            'base_keyword': base_keyword,
            'suggestions': keyword_analysis[:15],
            'total_found': len(keyword_analysis)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

print("Debug: Reaching end of file")

if __name__ == "__main__":
    print("Debug: Starting server...")
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)