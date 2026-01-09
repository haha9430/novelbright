-- index 삭제
DROP INDEX idx_user_created
ON conversations;
-- 속도 테스트
SELECT *
FROM conversations
WHERE user_id = 3
ORDER BY created_at DESC;

explain
SELECT *
FROM conversations
WHERE user_id = 3
ORDER BY created_at DESC;

-- index 생성
CREATE INDEX idx_user_created
ON conversations (user_id, created_at);

-- 속도 테스트
SELECT *
FROM conversations
WHERE user_id = 3
ORDER BY created_at DESC;

explain
SELECT *
FROM conversations
WHERE user_id = 3
ORDER BY created_at DESC;