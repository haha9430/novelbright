-- 부분 검색
SELECT id, name
FROM users
WHERE name like 'ki%';

SELECT id, name
FROM users
WHERE name = 'kim'
ORDER BY created_at DESC
LIMIT 5;

-- 기간 검색
SELECT * FROM users
WHERE created_at BETWEEN '2025-11-01' AND '2026-02-28';
