# C++ Development Guide

This guide provides the baseline for C++ development. It is superseded by project-specific conventions.

## 1. Project Analysis Checklist

Before coding, inspect the project for these files to determine its conventions:

- **Build System:** `CMakeLists.txt` (CMake), `Makefile` (Make), or a Visual Studio solution file (`*.sln`).
- **C++ Standard:** Look for flags like `-std=c++11`, `-std=c++14`, `-std=c++17`, or `-std=c++20` in the build files.
- **Style & Linting Config:** `.clang-format`, `.clang-tidy`. These define the coding standard.
- **Testing Framework:** Look for a `tests/` directory and check the build files for dependencies like `gtest` or `catch2`.

## 2. Core Principles

- **Style:** Strictly adhere to the project's configured formatter (e.g., clang-format) and linter (e.g., clang-tidy). If none exist, default to the Google C++ Style Guide.
- **Modern C++:** Use modern C++ features, such as smart pointers, range-based for loops, and auto.
- **RAII (Resource Acquisition Is Initialization):** Use RAII to manage resources like memory, files, and network connections.

## 3. Implementation Patterns

- **Error Handling:** Replicate existing patterns for error handling. Use exceptions for errors that cannot be handled locally.
- **Testing:** Use the project's existing test structure. Write unit tests for all new code.

## 4. Common Commands

- **CMake:**
  - **Configure:** `cmake -B build`
  - **Build:** `cmake --build build`
  - **Test:** `cd build && ctest`
- **Make:**
  - **Build:** `make`
  - **Test:** `make test`
