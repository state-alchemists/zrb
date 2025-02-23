const CRUD_UTIL = {

    renderPagination(paginationComponent, crudState, total, fetchFunction = "fetchRows") {
        const totalPages = Math.ceil(total / crudState.pageSize);
        paginationComponent.innerHTML = "";
        // Ensure left alignment (if not already handled by PicoCSS or external CSS)
        paginationComponent.style.textAlign = "left";
        let paginationHTML = "";
        // Only show "First" and "Previous" if we're not on page 1
        if (crudState.currentPage > 1) {
            paginationHTML += `<button class="secondary" onclick="${fetchFunction}(1)">&laquo;</button>`;
            paginationHTML += `<button class="secondary" onclick="${fetchFunction}(${crudState.currentPage - 1})">&lt;</button>`;
        }
        if (totalPages <= 5) {
            // If total pages are few, simply list them all
            for (let i = 1; i <= totalPages; i++) {
                paginationHTML += `<button class="secondary" onclick="${fetchFunction}(${i})" ${i === crudState.currentPage ? "disabled" : ""}>${i}</button>`;
            }
        } else {
            // Always show first page
            paginationHTML += `<button class="secondary" onclick="${fetchFunction}(1)" ${crudState.currentPage === 1 ? "disabled" : ""}>1</button>`;
            // Determine start and end for the page range around current page
            const start = Math.max(2, crudState.currentPage - 1);
            const end = Math.min(totalPages - 1, crudState.currentPage + 1);
            // Add ellipsis if there's a gap between first page and the start of the range
            if (start > 2) {
                paginationHTML += `<span style="padding: 0 5px;">...</span>`;
            }
            // Render the range around the current page
            for (let i = start; i <= end; i++) {
                paginationHTML += `<button class="secondary" onclick="${fetchFunction}(${i})" ${i === crudState.currentPage ? "disabled" : ""}>${i}</button>`;
            }
            // Add ellipsis if there's a gap between the end of the range and the last page
            if (end < totalPages - 1) {
                paginationHTML += `<span style="padding: 0 5px;">...</span>`;
            }
            // Always show last page
            paginationHTML += `<button class="secondary" onclick="${fetchFunction}(${totalPages})" ${crudState.currentPage === totalPages ? "disabled" : ""}>${totalPages}</button>`;
        }
        // Only show "Next" and "Last" if we're not on the last page
        if (crudState.currentPage < totalPages) {
            paginationHTML += `<button class="secondary" onclick="${fetchFunction}(${crudState.currentPage + 1})">&gt;</button>`;
            paginationHTML += `<button class="secondary" onclick="${fetchFunction}(${totalPages})">&raquo;</button>`;
        }
        paginationComponent.innerHTML = paginationHTML;
    },

    splitUnescaped(query, delimiter=",") {
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