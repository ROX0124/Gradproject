def get_script_from_db(sentence_id: int) -> str:
    """DB 조회 스텁: 실제 DB 연결이 없으면 간단한 예시 문장을 반환합니다.

    실제로는 SQLite/Postgres 등에서 문장을 조회하도록 구현하세요.
    """
    # TODO: 실제 DB 로직으로 교체
    return f"예시 문장 (id={sentence_id})"
