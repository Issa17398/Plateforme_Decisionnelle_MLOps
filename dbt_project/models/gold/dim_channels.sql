{{ config(materialized='table') }}

with silver_videos as (
    select * from {{ ref('stg_silver_videos') }}
)

select
    channel_id,
    channel_title,
    min(published_at) as first_video_published_at,
    max(published_at) as latest_video_published_at,
    cast(min(published_at) as date) as first_publication_date,
    cast(max(published_at) as date) as latest_publication_date,
    count(*) as total_videos,
    sum(view_count) as total_cumulative_views,
    sum(coalesce(like_count, 0)) as total_identified_likes,
    sum(coalesce(comment_count, 0)) as total_identified_comments,
    current_timestamp as gold_processed_at
from silver_videos
group by channel_id, channel_title
