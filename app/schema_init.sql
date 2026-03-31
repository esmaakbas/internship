-- =========================================================
-- Initial schema for mobilab_app
-- Purpose:
--   1. Store application users (for future Auth0 mapping)
--   2. Store pipeline prediction records (for future history)
-- Target DB:
--   MySQL 8.0+
-- =========================================================

CREATE TABLE IF NOT EXISTS users (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    auth0_sub VARCHAR(255) NULL UNIQUE,
    email VARCHAR(254) NOT NULL UNIQUE,
    display_name VARCHAR(255) NULL,
    role ENUM('admin', 'user') NOT NULL DEFAULT 'user',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login_at DATETIME NULL,

    PRIMARY KEY (id),
    INDEX idx_users_role (role),
    INDEX idx_users_is_active (is_active)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS predictions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id INT UNSIGNED NULL,
    status ENUM('pending', 'running', 'success', 'failed') NOT NULL DEFAULT 'pending',
    input_payload JSON NULL,
    output_payload JSON NULL,
    pipeline_version VARCHAR(100) NULL,
    error_message TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_predictions_user (user_id),
    INDEX idx_predictions_status (status),
    INDEX idx_predictions_created_at (created_at),

    CONSTRAINT fk_predictions_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;