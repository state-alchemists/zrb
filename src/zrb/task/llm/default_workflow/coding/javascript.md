# JavaScript/TypeScript Development Guide

## Core Principles
- **Follow project's style guide** (ESLint, Prettier, etc.)
- **Use TypeScript** if the project uses it
- **Match module system** (CommonJS, ES modules)

## Project Analysis
- Check for: `package.json`, `tsconfig.json`, `jsconfig.json`
- Look for style guides: `.eslintrc`, `.prettierrc`, `.editorconfig`
- Identify testing framework: `jest`, `mocha`, `vitest`
- Check build tools: `webpack`, `vite`, `rollup`

## Implementation Patterns
- **Module System:** Follow project's import/export patterns
- **Error Handling:** Match promise/async patterns and error types
- **TypeScript:** Use same strictness level and type patterns
- **Testing:** Use project's test utilities and mocking patterns

## Common Commands
- Package management: `npm`, `yarn`, `pnpm`
- Testing: `npm test`, `npm run test`
- Linting: `npm run lint`, `eslint`
- Building: `npm run build`, `tsc`