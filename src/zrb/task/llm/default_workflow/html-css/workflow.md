---
description: "A workflow for developing with HTML and CSS, including project analysis and best practices."
---
Follow this workflow to create accessible, responsive, and maintainable web interfaces.

# Core Mandates

- **Semantic HTML:** Use HTML elements for their intended purpose
- **Accessibility First:** Ensure content is accessible to all users
- **Responsive Design:** Create interfaces that work across all devices
- **Performance:** Optimize for fast loading and smooth interactions

# Tool Usage Guideline
- Use `read_from_file` to analyze HTML/CSS structure and patterns
- Use `search_files` to find specific styles or markup patterns
- Use `run_shell_command` for linting and formatting tools
- Use `list_files` to understand project structure

# Step 1: Project Analysis

1. **HTML Files:** Examine `*.html` for structure, doctype, and meta tags
2. **CSS Files:** Analyze `*.css` for architecture (BEM, SMACSS) and frameworks
3. **Preprocessors:** Check for Sass (`*.scss`), Less (`*.less`), or other preprocessors
4. **Frameworks:** Identify usage of Bootstrap, Tailwind CSS, or other CSS frameworks
5. **Configuration:** Look for `.stylelintrc`, `.prettierrc`, and other config files
6. **Build Tools:** Check for Webpack, Vite, or other build configurations

# Step 2: Understand Conventions

1. **HTML Standards:** Follow semantic HTML5 elements and attributes
2. **CSS Methodology:** Adhere to project's CSS architecture (BEM, SMACSS, etc.)
3. **Accessibility:** Implement WCAG guidelines and ARIA attributes
4. **Responsive Patterns:** Follow established breakpoints and grid systems
5. **Performance:** Optimize images, minimize CSS, and leverage browser caching

# Step 3: Implementation Planning

1. **Component Structure:** Plan HTML structure based on project patterns
2. **Styling Approach:** Determine CSS organization and naming conventions
3. **Responsive Strategy:** Plan breakpoints and adaptive layouts
4. **Accessibility:** Identify required ARIA attributes and keyboard navigation
5. **Browser Compatibility:** Consider cross-browser testing requirements

# Step 4: Write Markup and Styles

## HTML Best Practices
- **Semantic Structure:** Use appropriate elements (`<nav>`, `<main>`, `<article>`, etc.)
- **Accessibility:** Include `alt` attributes, proper headings, and ARIA labels
- **SEO Optimization:** Use proper meta tags and semantic markup
- **Performance:** Minimize DOM depth and avoid unnecessary elements

## CSS Best Practices
- **Methodology:** Follow established naming conventions (BEM, etc.)
- **Organization:** Use logical grouping and consistent ordering
- **Responsive Design:** Implement mobile-first media queries
- **Performance:** Minimize specificity and avoid expensive selectors
- **Maintainability:** Use variables and modular organization

# Step 5: Testing and Verification

1. **HTML Validation:** Validate markup using W3C validator
2. **Accessibility Testing:** Test with screen readers and accessibility tools
3. **Cross-Browser Testing:** Verify rendering across target browsers
4. **Responsive Testing:** Test on different screen sizes and devices
5. **Performance Testing:** Check load times and rendering performance

# Step 6: Quality Assurance

## Linting and Formatting
- **HTML Linting:** Use tools like HTMLHint or validator
- **CSS Linting:** Run `stylelint` with project configuration
- **Formatting:** Use Prettier or project-specific formatters
- **Code Quality:** Ensure consistent indentation and organization

## Browser Compatibility
- **Progressive Enhancement:** Ensure core functionality works everywhere
- **Feature Detection:** Use modern features with fallbacks
- **Vendor Prefixing:** Use Autoprefixer for cross-browser compatibility

# Step 7: Optimization

## Performance Optimization
- **CSS Minification:** Use tools like cssnano for production
- **Image Optimization:** Compress and use appropriate formats
- **Critical CSS:** Inline above-the-fold styles for faster rendering
- **Lazy Loading:** Defer non-critical resources

## Accessibility Optimization
- **Keyboard Navigation:** Ensure all interactive elements are keyboard accessible
- **Screen Reader Compatibility:** Test with NVDA, VoiceOver, or JAWS
- **Color Contrast:** Verify sufficient contrast ratios
- **Focus Management:** Implement proper focus indicators and order

# Step 8: Finalize and Deliver

1. **Final Validation:** Run comprehensive validation and testing
2. **Documentation:** Update style guides or component documentation
3. **Performance Review:** Verify optimization targets are met
4. **Accessibility Audit:** Complete final accessibility checks

# Common Commands Reference

## Development Tools
- `stylelint "**/*.css"`: Lint CSS files
- `prettier --check "**/*.html"`: Check HTML formatting
- `prettier --write "**/*.{html,css}"`: Format HTML and CSS files
- `npx htmlhint "**/*.html"`: Lint HTML files

## Build and Optimization
- `npm run build`: Build project (if using build tools)
- `npm run dev`: Start development server
- `npm run lint`: Run all linting
- `npm run format`: Format all code

## Testing
- `npm test`: Run tests (if test framework configured)
- Browser developer tools for manual testing
- Lighthouse for performance and accessibility audits

# Risk Assessment Guidelines

## Low Risk (Proceed Directly)
- Adding new CSS classes following established patterns
- Creating new HTML components with semantic markup
- Running linters and validators

## Moderate Risk (Explain and Confirm)
- Modifying core layout or grid systems
- Changing established CSS architecture
- Adding new dependencies or frameworks

## High Risk (Refuse and Explain)
- Breaking existing responsive layouts
- Removing accessibility features
- Changes that affect multiple pages or components