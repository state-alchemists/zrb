🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > CI/CD Integration

# CI/CD Integration for Zrb Projects

Zrb is perfectly suited for Continuous Integration and Continuous Deployment (CI/CD) pipelines. By integrating your Zrb tasks into your CI/CD workflows, you ensure consistency, reliability, and automation across your development lifecycle.

The key principle is to leverage the official Zrb Docker image (`stalchmst/zrb`), which comes pre-installed with Zrb and its dependencies.

---

## Table of Contents

- [Using the Official Docker Image](#1-using-the-official-zrb-docker-image)
- [GitHub Actions](#2-github-actions)
- [GitLab CI/CD](#3-gitlab-cicd)
- [Bitbucket Pipelines](#4-bitbucket-pipelines)
- [Best Practices](#5-choosing-the-right-zrb-image-version)
- [Quick Reference](#quick-reference)

---

## 1. Using the Official Zrb Docker Image

The recommended way to run Zrb commands in a CI/CD environment is by using the official Docker image: `stalchmst/zrb`.

> ⚠️ **Important:** Always specify a version tag (e.g., `stalchmst/zrb:2.0.0`) for reproducible builds, rather than using `latest`.

Find available tags on [Docker Hub](https://hub.docker.com/r/stalchmst/zrb/tags).

---

## 2. GitHub Actions

GitHub Actions allow you to automate workflows directly within your GitHub repository.

### Setup

1. Create directory: `.github/workflows/`
2. Create workflow file: `ci.yml`

### Example Workflow

```yaml
name: Zrb CI Pipeline

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  run-zrb-tasks:
    runs-on: ubuntu-latest
    container:
      image: stalchmst/zrb:2.0.0

    steps:
      - name: Check out repository code
        uses: actions/checkout@v4

      - name: Show Environment Info
        run: |
          echo "🏃 Triggered by: ${{ github.actor }}"
          echo "🎉 Event: ${{ github.event_name }}"
          echo "🌲 Branch/Ref: ${{ github.ref }}"
          zrb --version
        shell: bash

      - name: Run Tests
        run: zrb test 
        shell: bash

      - name: Run Lint
        run: zrb lint
        shell: bash
```

### GitHub Actions Reference

| Key | Description |
|-----|-------------|
| `on` | Triggers (push, pull_request) |
| `container.image` | Docker image to use |
| `steps[].run` | Shell commands to execute |
| `shell: bash` | Ensure bash shell in container |

---

## 3. GitLab CI/CD

GitLab CI/CD uses a `.gitlab-ci.yml` file in the root of your repository.

### Example Pipeline

```yaml
image: stalchmst/zrb:2.0.0

stages:
  - setup
  - test
  - lint

before_script:
  - echo "🚀 Starting CI/CD pipeline..."
  - zrb --version

show_info:
  stage: setup
  script:
    - echo "🏃 Triggered by: $GITLAB_USER_LOGIN"
    - echo "🌲 Branch: $CI_COMMIT_REF_NAME"

run_tests:
  stage: test
  script:
    - echo "🧪 Running tests..."
    - zrb test

run_linting:
  stage: lint
  script:
    - echo "✨ Running linters..."
    - zrb lint
```

### GitLab CI/CD Reference

| Key | Description |
|-----|-------------|
| `image` | Docker image for all jobs |
| `stages` | Order of execution |
| `before_script` | Commands before each job |
| `variables` | CI/CD variables (use for secrets) |

---

## 4. Bitbucket Pipelines

Bitbucket Pipelines uses a `bitbucket-pipelines.yml` file.

### Example Pipeline

```yaml
image: stalchmst/zrb:2.0.0

pipelines:
  default:
    - step:
        name: "Show Environment Info"
        script:
          - echo "🚀 Starting CI/CD pipeline..."
          - zrb --version
          - echo "🌲 Branch: $BITBUCKET_BRANCH"

    - step:
        name: "Run Tests"
        script:
          - echo "🧪 Running tests..."
          - zrb test

    - step:
        name: "Run Lint"
        script:
          - echo "✨ Running linters..."
          - zrb lint
```

### Bitbucket Pipelines Reference

| Key | Description |
|-----|-------------|
| `image` | Docker image for all steps |
| `pipelines.default` | Default pipeline on every push |
| `step.name` | Descriptive step name |
| `step.script` | Shell commands |

---

## 5. Choosing the Right Zrb Image Version

> 💡 **Best Practice:** Pin your CI/CD pipeline to a specific version.

| Approach | Pros | Cons |
|----------|------|------|
| `stalchmst/zrb:2.0.0` | Reproducible builds | Manual updates needed |
| `stalchmst/zrb:latest` | Always newest | May break unexpectedly |

Update the version tag deliberately when ready to adopt newer features or fixes.

---

## Quick Reference

| Platform | Config File | Image |
|----------|-------------|-------|
| GitHub Actions | `.github/workflows/ci.yml` | `stalchmst/zrb:VERSION` |
| GitLab CI/CD | `.gitlab-ci.yml` | `stalchmst/zrb:VERSION` |
| Bitbucket | `bitbucket-pipelines.yml` | `stalchmst/zrb:VERSION` |

---