---
description: "A workflow for developing with JavaScript and TypeScript, including project analysis and best practices."
---
# JavaScript/TypeScript Development Guide

This guide provides the baseline for JS/TS development. It is superseded by project-specific conventions.

## 1. Project Analysis Checklist

Before coding, inspect the project for these files to determine its conventions:

- **Package Manager:** `package.json` (and `package-lock.json`, `yarn.lock`, or `pnpm-lock.yaml`). Note the `scripts` and `dependencies`.
- **TypeScript/JavaScript Config:** `tsconfig.json` or `jsconfig.json`. This defines module system, strictness, and paths.
- **Style & Linting Config:** `.eslintrc.js`, `.prettierrc`, `package.json` (for `eslintConfig`, `prettier`). These define the coding standard.
- **Build/Vite Config:** `webpack.config.js`, `vite.config.ts`, `rollup.config.js`.
- **Testing Framework:** Look for a `tests/` or `__tests__/` directory, and config files like `jest.config.js` or `vitest.config.ts`.

## 2. Core Principles

- **Style:** Strictly adhere to the project's configured linter (`ESLint`) and formatter (`Prettier`).
- **TypeScript:** If the project uses TypeScript (`tsconfig.json` exists), you MUST use it for all new code. Adhere to the configured strictness level.
- **Module System:** Match the project's module system (e.g., ES Modules `import/export` or CommonJS `require/module.exports`). This is usually defined in `package.json` (`"type": "module"`) or `tsconfig.json`.

## 3. Package Management

- **`npm`:** If the project uses `package-lock.json`, add new dependencies using `npm install <package-name>`.
- **`yarn`:** If the project uses `yarn.lock`, add new dependencies using `yarn add <package-name>`.
- **`pnpm`:** If the project uses `pnpm-lock.yaml`, add new dependencies using `pnpm add <package-name>`.

## 4. Framework Conventions

- **React:** If the project uses React, follow its component structure (e.g., functional components with hooks), state management (e.g., `useState`, `useReducer`, Redux), and JSX syntax.
- **Vue:** If the project uses Vue, follow its single-file component structure, `v-` directives, and state management patterns (e.g., Pinia).
- **Angular:** If the project uses Angular, follow its module and component structure, dependency injection, and RxJS-based patterns.

## 5. Implementation Patterns

- **Error Handling:** Replicate existing patterns for `try/catch`, Promises (`.catch()`), and async/await error handling.
- **Testing:** Use the project's existing test runner (`Jest`, `Vitest`, `Mocha`), assertion library, and mocking patterns. Add tests for all new code.
- **Debugging:** Use the browser's developer tools for front-end code and the Node.js debugger (`node --inspect`) for back-end code.

## 6. Common Commands

- **Install Dependencies:** `npm install`, `yarn install`, `pnpm install`
- **Linting/Formatting:** `npm run lint`, `npm run format`
- **Type Checking:** `npm run typecheck`, `tsc --noEmit`
- **Testing:** `npm test`, `npm run test`
- **Building:** `npm run build`