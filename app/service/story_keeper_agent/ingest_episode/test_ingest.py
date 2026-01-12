from app.service.story_keeper_agent.ingest_episode import (
    ingest_episode,
    IngestEpisodeRequest,
    IngestEpisodeError,
)

def main():
    req = IngestEpisodeRequest(
        episode_no=3,
        text_chunks=[
            "첫 번째 청크입니다.\n문단이 있어요.",
            "두 번째 청크입니다. 길이 테스트용!",
        ],
    )

    res = ingest_episode(req)
    print("episode_no:", res.episode_no)
    print("full_text:\n", res.full_text)

    # 에러 테스트(2500자 초과)
    try:
        bad = IngestEpisodeRequest(
            episode_no=3,
            text_chunks=["a" * 2501],
        )
        ingest_episode(bad)
    except IngestEpisodeError as e:
        print("caught error:", str(e))

if __name__ == "__main__":
    main()
