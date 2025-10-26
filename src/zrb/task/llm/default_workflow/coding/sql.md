# SQL Development Guide

This guide provides the baseline for SQL development. It is superseded by project-specific conventions.

## 1. Project Analysis Checklist

Before coding, inspect the project for these files to determine its conventions:

- **Schema Definitions:** `*.sql` files that define the database schema.
- **Migrations:** A directory containing migration files (e.g., `db/migrations`).
- **Database Client:** The database client used in the project (e.g., `psql`, `mysql`, `sqlcmd`).

## 2. Core Principles

- **Style:**
  - **Keywords:** Use uppercase for SQL keywords (e.g., `SELECT`, `FROM`, `WHERE`).
  - **Identifiers:** Use snake_case for table and column names.
  - **Indentation:** Use consistent indentation to make your queries readable.
- **Data Types:** Use the most appropriate data types for your columns.
- **Normalization:** Normalize your database to reduce data redundancy and improve data integrity.
- **Indexes:** Use indexes to improve the performance of your queries.

## 3. Implementation Patterns

- **Transactions:** Use transactions to ensure data consistency.
- **Stored Procedures:** Use stored procedures to encapsulate complex business logic.
- **Views:** Use views to simplify complex queries and to enforce security.

## 4. Common Commands

- **Connect to database:**
  - **PostgreSQL:** `psql -h <host> -U <user> -d <database>`
  - **MySQL:** `mysql -h <host> -u <user> -p <database>`
  - **SQL Server:** `sqlcmd -S <server> -U <user> -P <password> -d <database>`
- **Run a script:**
  - **PostgreSQL:** `psql -h <host> -U <user> -d <database> -f <script.sql>`
  - **MySQL:** `mysql -h <host> -u <user> -p <database> < <script.sql>`
  - **SQL Server:** `sqlcmd -S <server> -U <user> -P <password> -d <database> -i <script.sql>`
