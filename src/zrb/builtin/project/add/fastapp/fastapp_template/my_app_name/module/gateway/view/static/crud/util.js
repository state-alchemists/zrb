const CRUD_UTIL = {

    renderPagination(paginationComponent, crudApp, total) {
        const { pageSize, currentPage } = crudApp.state;
        const totalPages = Math.ceil(total / pageSize);
        paginationComponent.innerHTML = "";
        // Ensure left alignment
        paginationComponent.style.textAlign = "left";
        let buttons = [];
        // "First" and "Previous" buttons if not on the first page
        if (currentPage > 1) {
            buttons.push({ label: "&laquo;", page: 1 });
            buttons.push({ label: "&lt;", page: currentPage - 1 });
        }
        if (totalPages <= 5) {
            // List all pages
            for (let i = 1; i <= totalPages; i++) {
                buttons.push({ label: i, page: i });
            }
        } else {
            // Always show the first page
            buttons.push({ label: "1", page: 1, disabled: currentPage === 1 });
            const start = Math.max(2, currentPage - 1);
            const end = Math.min(totalPages - 1, currentPage + 1);
            // Add ellipsis if there's a gap
            if (start > 2) {
                buttons.push({ label: "...", isSpan: true });
            }
            // Pages around current page
            for (let i = start; i <= end; i++) {
                buttons.push({ label: i, page: i });
            }
            if (end < totalPages - 1) {
                buttons.push({ label: "...", isSpan: true });
            }
            // Always show the last page
            buttons.push({ label: totalPages, page: totalPages, disabled: currentPage === totalPages });
        }
        // "Next" and "Last" buttons if not on the last page
        if (currentPage < totalPages) {
            buttons.push({ label: "&gt;", page: currentPage + 1 });
            buttons.push({ label: "&raquo;", page: totalPages });
        }
        // Render buttons and spans
        buttons.forEach(btn => {
            if (btn.isSpan) {
                paginationComponent.insertAdjacentHTML("beforeend", `<span style="padding: 0 5px;">${btn.label}</span>`);
            } else {
                const buttonEl = document.createElement("button");
                buttonEl.className = "secondary";
                buttonEl.innerHTML = btn.label;
                if (btn.disabled) {
                    buttonEl.disabled = true;
                } else {
                    buttonEl.dataset.page = btn.page;
                }
                paginationComponent.appendChild(buttonEl);
            }
        });
        // Attach event listeners to pagination buttons
        paginationComponent.querySelectorAll("button[data-page]").forEach(button => {
            button.addEventListener("click", () => {
                const page = parseInt(button.dataset.page);
                crudApp.fetchRows(page);
            });
        });
    },

    splitUnescaped(query, delimiter = ",") {
        const parts = [];
        let current = "";
        let escaped = false;
        for (let i = 0; i < query.length; i++) {
            const char = query[i];
            if (escaped) {
                current += char;
                escaped = false;
            } else if (char === "\\") {
                escaped = true;
            } else if (char === delimiter) {
                parts.push(current);
                current = "";
            } else {
                current += char;
            }
        }
        if (current != "") {
            parts.push(current);
        }
        return parts;
    },

    isValidFilterQuery(query) {
        const filterPattern = /^([\w]+):(eq|ne|gt|gte|lt|lte|like|in):(.+)$/;
        const parts = this.splitUnescaped(query);
        return parts.every(part => filterPattern.test(part));
    },

    getSearchParam(crudState, defaultSearchColumn, apiMode = false) {
        return new URLSearchParams({
            page: crudState.currentPage || 1,
            page_size: crudState.pageSize || 10,
            filter: this._getFilterSearchParamValue(crudState, defaultSearchColumn, apiMode),
        }).toString();
    },

    _getFilterSearchParamValue(crudState, defaultSearchColumn, apiMode = false) {
        const filter = crudState.filter || "";
        if (!apiMode) {
            return filter;
        }
        return this.isValidFilterQuery(filter) ? filter : `${defaultSearchColumn}:like:%${filter}%`;
    }

}