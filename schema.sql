CREATE DATABASE IF NOT EXISTS expense_tracker;
USE expense_tracker;

CREATE TABLE IF NOT EXISTS users(
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(50),
  email VARCHAR(100) UNIQUE,
  password VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS expenses(
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT,
  category VARCHAR(50),
  amount DECIMAL(10,2),
  description TEXT,
  date DATE,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
