# Improvement Plan for `zrb` LLM Features

This plan has been completely revised based on the understanding that `pydantic-ai` has a built-in, configurable retry mechanism that automatically feeds back validation errors to the LLM. The previous plan was not doable as it proposed re-implementing this core feature.

The core problem is that the default retry behavior is not sufficient to prevent the LLM from getting stuck in a failure loop when generating complex, invalid JSON.

This new plan focuses on **doable** steps that work *with* the `pydantic-ai` framework.

## 1. Enhance the Pydantic Tool Schema for Clearer LLM Guidance

The most direct way to prevent errors is to give the LLM better instructions before it acts. The tool's schema and docstrings are the primary source of instruction for the LLM.

**Doable Action:**

- **Refine `FileToWrite` Model and Docstrings**: The `FileToWrite` Pydantic model and the `write_to_file` tool's docstring should be updated with explicit warnings about JSON string escaping.
  - In the `FileToWrite` model, the `content` field's description should include a strong warning.
  - **Example:** `content: str = Field(description="The content to write. CRITICAL: This string will be embedded in JSON. Ensure all special characters, especially quotes and backslashes, are properly escaped.")`
- This provides a direct, contextual instruction to the LLM at the moment it's deciding on the field's value, making it more likely to produce correct output on the first try.

## 2. Leverage `pydantic-ai`'s Advanced Error Handling (Investigation)

While `pydantic-ai` handles retries, its effectiveness can be improved. The documentation mentions advanced features that should be investigated.

**Doable Action:**

- **Investigate Custom Error Formatting**: Research if `pydantic-ai` allows for customizing the validation error message that is fed back to the LLM.
  - The goal is to transform a standard Pydantic `ValidationError` into a more instructional prompt. For example, instead of just the error, the feedback could be: `"A tool call failed with validation error: <error>. You sent: <invalid_json>. Please correct the JSON, paying close attention to the schema and character escaping, and try again."`
- This makes the existing retry mechanism "smarter" by giving the LLM better guidance on how to fix its mistake, rather than just showing it a raw error.

## 3. Architect for Resilience: Stage Large Content

This recommendation remains the most robust long-term solution and is perfectly compatible with `pydantic-ai`. It avoids the problem of generating large, fragile JSON strings altogether.

**Doable Action:**

- **Introduce a `stage_content` Tool**:
  1. Create a new, simple tool: `stage_content(content: str) -> str`. This tool takes a string, saves it to a temporary file, and returns the file's path.
  2. The LLM can then be instructed to use this tool first for any large or complex content.
  3. Modify the `write_to_file` tool to accept either direct content or a path to a staged file.
- This changes the task for the LLM from "generate a massive, perfectly-escaped JSON object" to "call two simple tools in sequence," which is a much more reliable workflow.