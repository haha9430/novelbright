CREATE TABLE conversations (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  role ENUM("user", "assistant") NOT NULL,
  message VARCHAR(500) NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_user_created (user_id, created_at)
);

INSERT INTO conversations (user_id, role, message, created_at) VALUES
(1, 'user',      'Hello',                        '2024-01-10 10:00:00'),
(1, 'assistant', 'Hello! How can I help?',       '2024-01-10 10:00:02'),
(2, 'user',      'Need help with payment',       '2024-01-15 09:30:00'),
(3, 'user',      'Order not received',           '2024-02-01 12:10:00'),
(3, 'assistant', 'Checking the order status...', '2024-02-01 12:11:00'),
(4, 'user',      'Recommend me something',       '2024-03-05 14:45:00');
