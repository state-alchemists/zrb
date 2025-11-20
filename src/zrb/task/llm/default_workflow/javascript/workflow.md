---
description: "A workflow for developing with JavaScript and TypeScript, including project analysis and best practices."
---
Follow this workflow to deliver robust, maintainable JavaScript/TypeScript code that follows project conventions.

# Core Mandates

- **Type Safety First:** Use TypeScript when available, proper typing in JavaScript
- **Modern Standards:** Follow ES6+ features and best practices
- **Framework Consistency:** Adhere to project's framework conventions
- **Tool Integration:** Leverage comprehensive JavaScript tooling ecosystem

# Tool Usage Guideline
- Use `read_from_file` to analyze package.json and configuration files
- Use `search_files` to find JavaScript/TypeScript patterns
- Use `run_shell_command` for npm/yarn/pnpm operations
- Use `list_files` to understand project structure

# Step 1: Project Analysis

1. **Package Management:** Examine `package.json` and lock files (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`)
2. **TypeScript Configuration:** Check for `tsconfig.json` and TypeScript usage
3. **Linting Configuration:** Look for `.eslintrc.js`, `.prettierrc`, ESLint config in `package.json`
4. **Build Configuration:** Analyze `webpack.config.js`, `vite.config.ts`, `rollup.config.js`
5. **Testing Framework:** Check for `jest.config.js`, `vitest.config.ts`, test directories
6. **Framework Usage:** Identify React, Vue, Angular, or other framework usage

# Step 2: Understand Conventions

1. **Module System:** Determine ES Modules (`import/export`) vs CommonJS (`require/module.exports`)
2. **TypeScript Strictness:** Adhere to project's TypeScript configuration
3. **Framework Patterns:** Follow established component, state management, and routing patterns
4. **Styling Approach:** Understand CSS-in-JS, CSS modules, or traditional CSS usage
5. **Testing Strategy:** Follow established test patterns and mocking approaches

# Step 3: Implementation Planning

1. **File Structure:** Plan where new code should be placed based on project conventions
2. **Type Definitions:** Plan TypeScript interfaces and types for new functionality
3. **Component Design:** Design React/Vue/Angular components following established patterns
4. **State Management:** Determine appropriate state management approach
5. **Testing Strategy:** Plan comprehensive unit, integration, and end-to-end tests

# Step 4: Write Code

## Code Quality Standards
- **Formatting:** Use Prettier with project configuration
- **Linting:** Follow ESLint rules and address all warnings
- **Type Safety:** Use TypeScript strictly when available
- **Naming:** Use clear, descriptive names following project conventions
- **Documentation:** Add JSDoc/TSDoc for complex functions and public APIs

## Framework-Specific Patterns

### React
- **Functional Components:** Use hooks-based functional components
- **State Management:** Follow established patterns (useState, useReducer, Redux, etc.)
- **Performance:** Use React.memo, useMemo, useCallback appropriately
- **Testing:** Use React Testing Library and established testing patterns

### Vue
- **Composition API:** Prefer Composition API over Options API
- **State Management:** Use Pinia or Vuex following project patterns
- **Component Structure:** Follow single-file component conventions
- **Testing:** Use Vue Test Utils and established testing patterns

### Angular
- **Component Structure:** Follow Angular module and component conventions
- **Dependency Injection:** Use Angular's DI system appropriately
- **RxJS:** Follow established reactive programming patterns
- **Testing:** Use Angular Testing utilities and established patterns

# Step 5: Testing and Verification

1. **Write Tests:** Create comprehensive tests for all new functionality
2. **Run Tests:** Execute `npm test` or framework-specific test commands
3. **Type Checking:** Run `npm run typecheck` or `tsc --noEmit`
4. **Linting:** Run `npm run lint` to catch code quality issues
5. **Build Verification:** Run `npm run build` to ensure code compiles correctly

# Step 6: Quality Assurance

## Testing Standards
- **Unit Tests:** Test individual functions and components in isolation
- **Integration Tests:** Test component interactions and API integrations
- **End-to-End Tests:** Test complete user workflows (if configured)
- **Mocking:** Use appropriate mocking libraries and patterns
- **Coverage:** Aim for high test coverage of business logic

## Code Review Checklist
- [ ] Code follows project formatting and linting standards
- [ ] All tests pass with good coverage
- [ ] TypeScript compiles without errors (if applicable)
- [ ] No ESLint warnings
- [ ] Documentation is complete for complex logic
- [ ] Performance considerations addressed
- [ ] Accessibility requirements met

# Step 7: Package Management

## Dependency Management
- **npm:** Use `npm install <package>` for new dependencies
- **yarn:** Use `yarn add <package>` for new dependencies
- **pnpm:** Use `pnpm add <package>` for new dependencies
- **Version Management:** Follow project's versioning strategy

## Script Execution
- `npm install` / `yarn install` / `pnpm install`: Install dependencies
- `npm run dev` / `yarn dev` / `pnpm dev`: Start development server
- `npm run build` / `yarn build` / `pnpm build`: Build for production
- `npm run lint` / `yarn lint` / `pnpm lint`: Run linting

# Step 8: Finalize and Deliver

1. **Verify Dependencies:** Ensure dependency versions are consistent
2. **Run Full Test Suite:** Verify all existing tests still pass
3. **Type Checking:** Ensure TypeScript compilation succeeds
4. **Build Verification:** Confirm production build works correctly
5. **Documentation:** Update relevant documentation and comments

# Common Commands Reference

## Development
- `npm run dev`: Start development server
- `npm run build`: Build for production
- `npm run typecheck`: Type check TypeScript code
- `npm run lint`: Run ESLint
- `npm run format`: Format code with Prettier

## Testing
- `npm test`: Run tests
- `npm run test:watch`: Run tests in watch mode
- `npm run test:coverage`: Run tests with coverage
- `npm run test:e2e`: Run end-to-end tests (if configured)

## Debugging
- Browser developer tools for frontend debugging
- `node --inspect` for Node.js debugging
- Framework-specific debugging tools

# Risk Assessment Guidelines

## Low Risk (Proceed Directly)
- Adding tests to existing test suites
- Implementing utility functions following established patterns
- Creating new components in established patterns

## Moderate Risk (Explain and Confirm)
- Modifying core application state
- Changing public API interfaces
- Adding new dependencies
- Modifying build configuration

## High Risk (Refuse and Explain)
- Breaking TypeScript strict mode compliance
- Modifying critical security components
- Changes affecting multiple applications
- Operations that could break the build system