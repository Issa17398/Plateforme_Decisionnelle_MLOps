{{ config(materialized='table') }}

with silver_videos as (
    select * from {{ ref('stg_silver_videos') }}
)

select
    video_id,
    channel_id,
    title,
    
    -- Classification métier du format de contenu
    case
        when lower(title) like '%bande annonce%' or lower(title) like '%teaser%' or lower(title) like '%trailer%'
            then 'TEASER'
        when (lower(title) like '%episode%' or lower(title) like '%épisode%' or lower(title) like '%ep%') and duration_seconds > 600
            then 'EPISODE'
        when duration_seconds <= 60
            then 'SHORT'
        else 'OTHER'
    end as content_type,
    
    -- Durée et segmentation
    duration_seconds,
    round(duration_seconds / 60.0, 2) as duration_minutes,
    case
        when duration_seconds <= 60 then '< 1 min (Short)'
        when duration_seconds <= 300 then '1-5 min (Teaser/Clip)'
        when duration_seconds <= 1200 then '5-20 min (Moyen format)'
        else '> 20 min (Épisode long)'
    end as duration_category,
    
    -- Attributs temporels pré-calculés (évite l'over-engineering d'une table calendrier)
    published_at,
    cast(published_at as date) as published_date,
    extract(year from published_at) as published_year,
    extract(month from published_at) as published_month,
    dayname(published_at) as published_day_name,
    extract(hour from published_at) as published_hour,
    case when dayofweek(published_at) in (0, 6) then true else false end as is_weekend,
    
    -- Métriques brutes certifiées
    view_count,
    like_count,
    comment_count,
    
    -- Indicateurs d'engagement (protection contre division par zéro et préservation des NULLs)
    round(((coalesce(like_count, 0) + coalesce(comment_count, 0)) * 100.0) / nullif(view_count, 0), 3) as engagement_rate_pct,
    round((like_count * 100.0) / nullif(view_count, 0), 3) as like_view_ratio_pct,
    round((comment_count * 100.0) / nullif(view_count, 0), 3) as comment_view_ratio_pct,
    
    -- Attributs techniques et lignage
    definition,
    has_caption,
    source_file as silver_source_file,
    current_timestamp as gold_processed_at

from silver_videos
