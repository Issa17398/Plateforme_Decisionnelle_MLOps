{{ config(materialized='view') }}

with source_data as (
    select * from {{ source('silver', 'videos') }}
)

select
    video_id,
    channel_title,
    channel_id,
    title,
    published_at,
    duration_iso,
    duration_seconds,
    view_count,
    like_count,
    comment_count,
    definition,
    caption as has_caption,
    collected_at,
    silver_processed_at,
    source_file
from source_data
