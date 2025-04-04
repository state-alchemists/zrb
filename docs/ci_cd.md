# CI/CD Integration for Zrb Projects

This guide provides examples of how to set up Continuous Integration and Continuous Deployment (CI/CD) pipelines for your Zrb projects using popular platforms like GitHub Actions and GitLab CI.

The key principle is to leverage the official Zrb Docker image (`stalchmst/zrb`) which comes pre-installed with Zrb and its dependencies.

## Using the Official Zrb Docker Image

The recommended way to run Zrb commands in a CI/CD environment is by using the official Docker image: `stalchmst/zrb`. You should specify a version tag (e.g., `stalchmst/zrb:1.5.3`) for reproducible builds, rather than using `latest`.

Find available tags on [Docker Hub](https://hub.docker.com/r/stalchmst/zrb/tags).

## GitHub Actions

GitHub Actions allow you to automate workflows directly within your GitHub repository.

1.  **Create Workflow Directory:** Create a directory named `.github/workflows` in the root of your repository if it doesn't exist.
2.  **Create Workflow File:** Inside `.github/workflows`, create a YAML file (e.g., `main.yml` or `ci.yml`).

**Example `.github/workflows/ci.yml`:**

This example demonstrates a basic workflow that runs Zrb tasks (like tests or linting) on every push to the `main` branch and on pull requests targeting `main`.

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
      # Use a specific version for consistency
      image: stalchmst/zrb:1.5.3 

    steps:
      - name: Check out repository code
        uses: actions/checkout@v4 # Use the latest version of checkout action

      - name: Show Environment Info
        run: |
          echo "🏃 Triggered by: ${{ github.actor }}"
          echo "🎉 Event: ${{ github.event_name }}"
          echo "🐧 Runner OS: ${{ runner.os }}"
          echo "🌲 Branch/Ref: ${{ github.ref }}"
          echo "📦 Zrb Version:"
          zrb --version
        shell: bash

      - name: Run Zrb Tests (Example)
        # Replace 'zrb test' with your actual test or linting command
        run: zrb test 
        shell: bash

      - name: Run Zrb Lint (Example)
        # Replace 'zrb lint' with your actual test or linting command
        run: zrb lint
        shell: bash

      # Add more steps for building, deploying, etc.
      # - name: Build Project
      #   run: zrb build
      #   shell: bash

      # - name: Deploy to Staging
      #   if: github.ref == 'refs/heads/main' && github.event_name == 'push'
      #   run: zrb deploy staging
      #   shell: bash
      #   env:
      #     DEPLOY_KEY: ${{ secrets.STAGING_DEPLOY_KEY }} # Example secret
```

**Explanation:**

*   `on`: Defines the triggers for the workflow (pushes and pull requests to `main`).
*   `jobs`: Contains the sequence of tasks to run.
*   `run-zrb-tasks`: The name of the job.
*   `runs-on: ubuntu-latest`: Specifies the type of machine to run the job on.
*   `container.image`: Specifies the Docker image to use for the job steps. We use the official Zrb image.
*   `steps`: A list of individual tasks within the job.
    *   `actions/checkout@v4`: Checks out your repository code into the runner environment.
    *   `run`: Executes shell commands. We use this to run `zrb --version` and your specific Zrb tasks (e.g., `zrb test`, `zrb lint`).
    *   `shell: bash`: Ensures commands run using the bash shell within the container.
*   **Secrets:** For deployment or tasks requiring credentials, use [GitHub Secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions) and reference them using the `secrets` context (e.g., `${{ secrets.YOUR_SECRET_NAME }}`). Pass them as environment variables to the `run` step.

## GitLab CI/CD

GitLab CI/CD uses a `.gitlab-ci.yml` file in the root of your repository to define pipelines.

**Example `.gitlab-ci.yml`:**

This example sets up a simple pipeline with stages for testing and linting.

```yaml
# Use the official Zrb Docker image
image: stalchmst/zrb:1.5.3

stages:
  - setup
  - test
  - lint
  # Add more stages like build, deploy, etc.

variables:
  # Optional: Define variables accessible in scripts
  # MY_VARIABLE: "my-value"

before_script:
  # Commands run before each job
  - echo "🚀 Starting CI/CD pipeline..."
  - echo "📦 Zrb Version:"
  - zrb --version

show_info:
  stage: setup
  script:
    - echo "🏃 Triggered by: $GITLAB_USER_LOGIN"
    - echo "🎉 Event: $CI_PIPELINE_SOURCE"
    - echo "🌲 Branch/Ref: $CI_COMMIT_REF_NAME"
    - echo "📦 Zrb Version:"
    - zrb --version

run_tests:
  stage: test
  script:
    - echo "🧪 Running tests..."
    # Replace 'zrb test' with your actual test command
    - zrb test
  # Optional: Define rules for when the job runs
  # rules:
  #   - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
  #   - if: '$CI_COMMIT_BRANCH == "main"'

run_linting:
  stage: lint
  script:
    - echo "✨ Running linters..."
    # Replace 'zrb lint' with your actual linting command
    - zrb lint
  # Optional: Allow this job to fail without failing the pipeline
  # allow_failure: true

# Example Deployment Job (uncomment and adapt)
# deploy_staging:
#   stage: deploy
#   script:
#     - echo "🚀 Deploying to Staging..."
#     - zrb deploy staging # Replace with your deployment task
#   environment:
#     name: staging
#     url: https://staging.example.com # Optional: Link to deployed environment
#   rules:
#     - if: '$CI_COMMIT_BRANCH == "main"' # Only run on pushes to main
#   variables:
#     # Use GitLab CI/CD Variables for secrets
#     DEPLOY_KEY: $STAGING_DEPLOY_KEY 
```

**Explanation:**

*   `image`: Specifies the default Docker image for all jobs (`stalchmst/zrb:1.5.3`).
*   `stages`: Defines the order of execution for jobs. Jobs in the same stage can run in parallel.
*   `variables`: Defines CI/CD variables. Use GitLab's [CI/CD Variables](https://docs.gitlab.com/ee/ci/variables/) settings for secrets (mark them as "Protected" and "Masked" where appropriate).
*   `before_script`: Commands executed before each job.
*   `job_name` (e.g., `run_tests`): Defines a specific job.
    *   `stage`: Assigns the job to a specific stage.
    *   `script`: The shell commands to execute for the job.
    *   `rules`: Control when jobs are added to a pipeline.
    *   `allow_failure`: If `true`, the pipeline continues even if this job fails.
    *   `environment`: Used for GitLab Environments, helpful for tracking deployments.

## Choosing the Right Zrb Image Version

Always pin your CI/CD pipeline to a specific version of the `stalchmst/zrb` image (e.g., `stalchmst/zrb:1.5.3`). This ensures that your builds are reproducible and won't break unexpectedly if a new `latest` version introduces changes. Update the version tag deliberately when you are ready to adopt newer Zrb features or fixes.