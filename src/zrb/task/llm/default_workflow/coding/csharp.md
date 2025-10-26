# C# Development Guide

This guide provides the baseline for C# development. It is superseded by project-specific conventions.

## 1. Project Analysis Checklist

Before coding, inspect the project for these files to determine its conventions:

- **Project File:** `*.csproj`. This defines the project structure, dependencies, and build settings.
- **Solution File:** `*.sln`. This defines the solution that contains one or more projects.
- **.NET Version:** Look for a `global.json` file, or check the `*.csproj` file.
- **Style & Linting Config:** `.editorconfig`, `.stylecop.json`. These define the coding standard.
- **Testing Framework:** Look for a `*Tests` directory and check the project file for dependencies like `xunit`, `nunit`, or `mstest`.

## 2. Core Principles

- **Style:** Strictly adhere to the project's configured linter (e.g., StyleCop). If none exists, default to the .NET coding conventions.
- **Idiomatic C#:** Embrace C#'s core features:
  - Use properties instead of public fields.
  - Use LINQ for data manipulation.
  - Use `async/await` for asynchronous programming.
- **Object-Oriented Design:** Follow SOLID principles and use design patterns where appropriate.

## 3. Implementation Patterns

- **Error Handling:** Replicate existing patterns for exceptions. Use `try-catch-finally` blocks for exception handling.
- **Testing:** Use the project's existing test structure. Write unit tests for all new code.

## 4. Common Commands

- **Build:** `dotnet build`
- **Run:** `dotnet run`
- **Test:** `dotnet test`
- **Clean:** `dotnet clean`
- **Publish:** `dotnet publish`
