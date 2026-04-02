-- Snowflake minimal setup for this project.
-- Run this once in a Snowflake worksheet.

USE ROLE ACCOUNTADMIN;

CREATE WAREHOUSE IF NOT EXISTS DEV_ECOSYSTEM_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE;

CREATE DATABASE IF NOT EXISTS DEV_ECOSYSTEM;

-- Optional: create schemas up-front (the loader/dbt will also create what they need)
CREATE SCHEMA IF NOT EXISTS DEV_ECOSYSTEM.RAW;
CREATE SCHEMA IF NOT EXISTS DEV_ECOSYSTEM.ANALYTICS;

