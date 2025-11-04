# Ruby on Rails Development Guide

This guide provides the baseline for Ruby on Rails development. It is superseded by project-specific conventions.

## 1. Project Analysis Checklist

Before coding, inspect the project for these files to determine its conventions:

- **Gemfile:** This file contains all the gems used in the project.
- **config/routes.rb:** This file defines the application's routes.
- **app/models/:** This directory contains the application's models.
- **app/views/:** This directory contains the application's views.
- **app/controllers/:** This directory contains the application's controllers.
- **db/schema.rb:** This file defines the database schema.

## 2. Core Principles

- **Convention over Configuration:** Follow the Rails conventions for file and class naming.
- **Fat Model, Skinny Controller:** Keep your controllers thin and your models fat.
- **RESTful Design:** Use RESTful principles for your application's design.

## 3. Implementation Patterns

- **Active Record:** Use Active Record for database interaction.
- **Action View:** Use Action View for creating views.
- **Action Controller:** Use Action Controller for handling requests and responses.

## 4. Common Commands

- **Start the server:** `bin/rails server`
- **Run the console:** `bin/rails console`
- **Run the tests:** `bin/rails test`
- **Generate code:** `bin/rails generate`
- **Run database migrations:** `bin/rails db:migrate`
