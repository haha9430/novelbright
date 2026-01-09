INSERT INTO users (name, email)
VALUES ('kim', 'kim@naver.com');

INSERT INTO users (name, email)
VALUES ('kim', 'kim@upstage.ai'),
       ('seo', 'seo@upstage.ai'),
        ('kim', 'kim12@upstage.ai');


SELECT * FROM users;
SELECT * FROM users WHERE name='kim';

UPDATE users SET name='lee' WHERE id=1;
DELETE FROM users WHERE id=1;

SELECT id, name
FROM users
WHERE name = 'kim'
ORDER BY created_at DESC
LIMIT 5;

