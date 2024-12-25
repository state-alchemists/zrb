const PAST_SESSION = {
    shouldPoll: true,

    async startPolling() {
        await this.getAndRenderPastSession(cfg.PAGE);
        while (this.shouldPoll) {
            await UTIL.delay(5000);
            await this.getAndRenderPastSession(cfg.PAGE);
        }
    },

    stopPolling() {
        this.shouldPoll = false;
    },

    async getAndRenderPastSession(page) {
        cfg.PAGE=page
        const minStartAtInput = document.getElementById("min-start-at-input");
        const minStartAt = UTIL.formatDate(minStartAtInput.value);
        const maxStartAtInput = document.getElementById("max-start-at-input");
        const maxStartAt = UTIL.formatDate(maxStartAtInput.value);
        const queryString = new URLSearchParams({
            page: page,
            from: minStartAt,
            to: maxStartAt,
        }).toString();
        try {
            // Send the AJAX request
            const response = await fetch(`${cfg.SESSION_API_URL}list?${queryString}`, {
                method: "GET",
                headers: {
                    "Content-Type": "application/json"
                },
            });
            if (response.ok) {
                const {total, data} = await response.json();
                this.showPastSession(page, total, data);
            } else {
                console.error("Error:", response);
            }
        } catch (error) {
            console.error("Error:", error);
        }
    },

    showPastSession(page, total, data) {
        const ul = document.getElementById("past-session-ul");
        ul.innerHTML = '';  // Clear existing content
        data.forEach(item => {
            const taskStatus = item.task_status[item.main_task_name];
            const finalStatus = UTIL.getFinalTaskStatus(taskStatus);
            const finalColor = UTIL.getFinalColor(finalStatus);
            const taskHistories = taskStatus.history;
            const taskStartTime = taskHistories.length > 0 ? taskHistories[0].time : ""
            const li = document.createElement('li');
            const a = document.createElement('a');
            const dateSpan = document.createElement('span');
            const statusSpan = document.createElement('span');
            a.textContent = item.name;
            a.target = '_blank';
            a.href = `${cfg.UI_URL}${item.name}`;
            li.appendChild(a);
            statusSpan.style.marginLeft = "10px";
            statusSpan.style.display = 'inline-block';
            statusSpan.style.width = '15px';
            statusSpan.style.height = '15px';
            statusSpan.style.borderRadius = '50%';
            statusSpan.style.border = '2px solid black';
            statusSpan.style.backgroundColor = finalColor;
            li.appendChild(statusSpan);
            dateSpan.style.marginLeft = "10px";
            dateSpan.textContent = taskStartTime;
            li.appendChild(dateSpan);
            ul.appendChild(li);
        }); 
        const paginationUl = document.getElementById("past-session-pagination-ul");
        paginationUl.innerHTML = '';  // Clear previous pagination

        const totalPages = Math.ceil(total / 10);  // Calculate total pages based on page size
        const maxPagesToShow = 5;  // Number of pages to display around the current page
        const halfMaxPages = Math.floor(maxPagesToShow / 2);
        
        // Add first page and previous controls
        if (page > 0) {
            paginationUl.appendChild(this.createPageLink("⟪", 0));  // Go to first page
            paginationUl.appendChild(this.createPageLink("⟨", page - 1));  // Go to previous page
        }

        let startPage = Math.max(0, page - halfMaxPages);
        let endPage = Math.min(totalPages - 1, page + halfMaxPages);

        if (page <= halfMaxPages) {
            endPage = Math.min(totalPages - 1, maxPagesToShow - 1);
        } else if (page + halfMaxPages >= totalPages) {
            startPage = Math.max(0, totalPages - maxPagesToShow);
        }

        if (startPage > 1) {
            paginationUl.appendChild(this.createEllipsis());
        }

        // Add page links within the calculated range
        for (let i = startPage; i <= endPage; i++) {
            if (i === page) {
                const pageLi = document.createElement('li');
                pageLi.textContent = i + 1;
                paginationUl.append(pageLi)
            } else {
                paginationUl.appendChild(this.createPageLink(i + 1, i))
            }
        }

        // Add ellipsis after the end page if needed
        if (endPage < totalPages - 2) {
            paginationUl.appendChild(this.createEllipsis());
        }

        // Add next and last page controls
        if (page < totalPages - 1) {
            paginationUl.appendChild(this.createPageLink("⟩", page + 1));  // Go to next page
            paginationUl.appendChild(this.createPageLink("⟫", totalPages - 1));  // Go to last page
        }    
    },

    createPageLink(text, page) {
        const li = document.createElement('li');
        const link = document.createElement('a');
        link.textContent = text;
        link.href = '#';
        link.onclick = (e) => {
            e.preventDefault();
            this.getAndRenderPastSession(page);
        };
        li.appendChild(link);
        return li;
    },

    createEllipsis() {
        const li = document.createElement('li');
        li.textContent = '...';
        return li;
    },

}