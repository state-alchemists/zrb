function showExistingSession(page, total, data) {
    const ul = document.getElementById("session-history-ul");
    ul.innerHTML = '';  // Clear existing content
    data.forEach(item => {
        const taskStatus = item.task_status[item.main_task_name];
        const finalStatus = getFinalTaskStatus(taskStatus);
        const finalColor = getFinalColor(finalStatus);
        const taskHistories = taskStatus.history;
        const taskStartTime = taskHistories.length > 0 ? taskHistories[0].time : ""
        const li = document.createElement('li');
        const a = document.createElement('a');
        const dateSpan = document.createElement('span');
        const statusSpan = document.createElement('span');
        a.textContent = item.name;
        a.target = '_blank';
        a.href = `${UI_URL}${item.name}`;
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
    const paginationUl = document.getElementById("session-history-pagination-ul");
    paginationUl.innerHTML = '';  // Clear previous pagination

    const totalPages = Math.ceil(total / 10);  // Calculate total pages based on page size
    const maxPagesToShow = 5;  // Number of pages to display around the current page
    const halfMaxPages = Math.floor(maxPagesToShow / 2);
    
    // Add first page and previous controls
    if (page > 0) {
        paginationUl.appendChild(createPageLink("⟪", 0));  // Go to first page
        paginationUl.appendChild(createPageLink("⟨", page - 1));  // Go to previous page
    }

    let startPage = Math.max(0, page - halfMaxPages);
    let endPage = Math.min(totalPages - 1, page + halfMaxPages);

    if (page <= halfMaxPages) {
        endPage = Math.min(totalPages - 1, maxPagesToShow - 1);
    } else if (page + halfMaxPages >= totalPages) {
        startPage = Math.max(0, totalPages - maxPagesToShow);
    }

    if (startPage > 1) {
        paginationUl.appendChild(createEllipsis());
    }

    // Add page links within the calculated range
    for (let i = startPage; i <= endPage; i++) {
        if (i === page) {
            const pageLi = document.createElement('li');
            pageLi.textContent = i + 1;
            paginationUl.append(pageLi)
        } else {
            paginationUl.appendChild(createPageLink(i + 1, i))
        }
    }

    // Add ellipsis after the end page if needed
    if (endPage < totalPages - 2) {
        paginationUl.appendChild(createEllipsis());
    }

    // Add next and last page controls
    if (page < totalPages - 1) {
        paginationUl.appendChild(createPageLink("⟩", page + 1));  // Go to next page
        paginationUl.appendChild(createPageLink("⟫", totalPages - 1));  // Go to last page
    }    
}

function createPageLink(text, page) {
    const li = document.createElement('li');
    const link = document.createElement('a');
    link.textContent = text;
    link.href = '#';
    link.onclick = (e) => {
        e.preventDefault();
        getExistingSessions(page);
    };
    li.appendChild(link);
    return li;
}

function createEllipsis() {
    const li = document.createElement('li');
    li.textContent = '...';
    return li;
}
