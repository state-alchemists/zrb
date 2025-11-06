---
description: "A workflow for developing with HTML and CSS, including project analysis and best practices."
---
# HTML/CSS Development Guide

This guide provides the baseline for HTML and CSS development. It is superseded by project-specific conventions.

## 1. Project Analysis Checklist

Before coding, inspect the project for these files to determine its conventions:

- **HTML Files:** `*.html`. Look for the overall structure, doctype, and meta tags.
- **CSS Files:** `*.css`. Look for the CSS architecture (e.g., BEM, SMACSS), preprocessors (e.g., Sass, Less), and frameworks (e.g., Bootstrap, Tailwind CSS).
- **Style & Linting Config:** `.stylelintrc`, `.prettierrc`. These define the coding standard.

## 2. Core Principles

- **HTML:**
  - **Semantic HTML:** Use HTML elements for their intended purpose. For example, use `<nav>` for navigation, `<main>` for the main content, and `<article>` for articles.
  - **Accessibility:** Follow accessibility best practices, such as using `alt` attributes for images and `aria-*` attributes for dynamic content.
- **CSS:**
  - **Separation of Concerns:** Keep your CSS separate from your HTML. Use external stylesheets instead of inline styles.
  - **Responsive Design:** Use media queries to create a responsive design that works on all screen sizes.
  - **CSS Methodologies:** If the project uses a CSS methodology like BEM or SMACSS, follow it.

## 3. Implementation Patterns

- **HTML:**
  - **Validation:** Validate your HTML using the W3C Markup Validation Service.
- **CSS:**
  - **Prefixing:** Use a tool like Autoprefixer to add vendor prefixes to your CSS.
  - **Minification:** Use a tool like cssnano to minify your CSS for production.

## 4. Common Commands

- **Linting:** `stylelint "**/*.css"`, `prettier --check "**/*.html"`
- **Formatting:** `prettier --write "**/*.{html,css}"`
