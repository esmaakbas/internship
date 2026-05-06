-- Manual one-time migration for simplified prediction schema.
-- Target columns: id, user_id, input_json, output_json, created_at, model_version

ALTER TABLE predictions
    CHANGE COLUMN input_payload input_json JSON NULL,
    CHANGE COLUMN output_payload output_json JSON NULL;

ALTER TABLE predictions
    DROP COLUMN status,
    DROP COLUMN execution_time_ms,
    DROP COLUMN pdf_path,
    DROP COLUMN pipeline_version,
    DROP COLUMN error_message;
