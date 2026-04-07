(function () {
    const toastContainer = document.getElementById("toast-container");
    const messageNodes = document.querySelectorAll("#server-messages [data-message]");
    const commandPalette = document.getElementById("command-palette");
    const commandInput = document.getElementById("command-input");
    const commandResults = document.getElementById("command-results");
    const commandUrl = document.body.dataset.commandUrl;
    const pollUrl = document.body.dataset.notificationPollUrl;
    const pollInterval = Number(document.body.dataset.pollInterval || 30000);

    function csrfToken() {
        const token = document.querySelector("input[name='csrfmiddlewaretoken']");
        return token ? token.value : "";
    }

    function renderToast(message, level) {
        if (!toastContainer || !message) return;
        const toast = document.createElement("div");
        toast.className = `toast ${level || "info"}`;
        toast.textContent = message;
        toastContainer.appendChild(toast);
        window.setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(-4px)";
            window.setTimeout(() => toast.remove(), 220);
        }, 3600);
    }

    window.Nivora = {
        toast: renderToast,
        openModal(id) {
            const modal = document.getElementById(id);
            if (modal) modal.classList.remove("hidden");
        },
        closeModal(id) {
            const modal = document.getElementById(id);
            if (modal) modal.classList.add("hidden");
        },
        toggleDropdown(id) {
            const node = document.getElementById(id);
            if (node) node.classList.toggle("hidden");
        },
    };

    messageNodes.forEach((node) => renderToast(node.dataset.message, node.dataset.level));

    function openCommandPalette() {
        if (!commandPalette) return;
        commandPalette.classList.remove("hidden");
        commandPalette.setAttribute("aria-hidden", "false");
        if (commandInput) {
            commandInput.value = "";
            commandInput.focus();
        }
        if (commandResults) {
            commandResults.innerHTML = '<div class="muted">Start typing to search the workspace.</div>';
        }
    }

    function closeCommandPalette() {
        if (!commandPalette) return;
        commandPalette.classList.add("hidden");
        commandPalette.setAttribute("aria-hidden", "true");
    }

    document.querySelectorAll("[data-command-open]").forEach((button) => {
        button.addEventListener("click", openCommandPalette);
    });

    document.querySelectorAll("[data-command-close]").forEach((button) => {
        button.addEventListener("click", closeCommandPalette);
    });

    document.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
            event.preventDefault();
            openCommandPalette();
        }
        if (event.key === "Escape") {
            closeCommandPalette();
        }
    });

    let commandTimer;
    if (commandInput && commandUrl) {
        commandInput.addEventListener("input", () => {
            window.clearTimeout(commandTimer);
            const query = commandInput.value.trim();
            if (query.length < 2) {
                commandResults.innerHTML = '<div class="muted">Search products, orders, suppliers, and customers.</div>';
                return;
            }

            commandTimer = window.setTimeout(async () => {
                try {
                    const response = await fetch(`${commandUrl}?q=${encodeURIComponent(query)}`, {
                        headers: {
                            "X-Requested-With": "XMLHttpRequest",
                            "X-CSRFToken": csrfToken(),
                        },
                    });
                    const payload = await response.json();
                    const results = (payload.data || {}).results || [];
                    if (!results.length) {
                        commandResults.innerHTML = '<div class="muted">No matching records found.</div>';
                        return;
                    }
                    commandResults.innerHTML = results
                        .map(
                            (result) => `
                                <a class="command-result" href="${result.url}">
                                    <div>
                                        <strong>${result.title}</strong>
                                        <div class="muted">${result.subtitle || ""}</div>
                                    </div>
                                    <div class="muted">${result.type}</div>
                                </a>
                            `
                        )
                        .join("");
                } catch (error) {
                    commandResults.innerHTML = '<div class="muted">Search is temporarily unavailable.</div>';
                }
            }, 180);
        });
    }

    async function pollNotifications() {
        if (!pollUrl) return;
        try {
            const response = await fetch(pollUrl, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            const payload = await response.json();
            const data = payload.data || {};
            const countNode = document.getElementById("notification-count");
            if (countNode) {
                countNode.textContent = data.unread_count || "";
            }
        } catch (error) {
            // Polling should fail silently to keep the UI stable.
        }
    }

    if (pollUrl) {
        pollNotifications();
        window.setInterval(pollNotifications, pollInterval);
    }
})();
