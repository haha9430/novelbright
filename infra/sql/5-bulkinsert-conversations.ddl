-- 데이터 입력을 위한 프로시저
CREATE PROCEDURE insert_dummy_conversations (IN p_count INT)
BEGIN
  DECLARE i INT DEFAULT 1;
  WHILE i <= p_count DO
    INSERT INTO conversations (user_id, role, message, created_at)
    VALUES (
      FLOOR(1 + RAND() * 5),                  -- 1~5 랜덤 user_id
      'user',                                 -- role 고정
      CONCAT('msg_', i),                      -- msg_1, msg_2, ...
      DATE_ADD('2024-01-01',                  -- 2024-01-01 기준 랜덤 날짜
               INTERVAL FLOOR(RAND() * 90) DAY)
    );
    SET i = i + 1;
  END WHILE;
END //
DELIMITER ;
-- 데이터 입력을 실행 (10000개 입력)
CALL insert_dummy_conversations(10000);

