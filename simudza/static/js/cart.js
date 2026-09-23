const CART_STORAGE_KEY = "simudza_cart";

function readCartStorage() {
    try {
        const raw = localStorage.getItem(CART_STORAGE_KEY);
        if (!raw) {
            return [];
        }
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
        return [];
    }
}

function writeCartStorage(items) {
    try {
        localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(items));
    } catch (e) {}
}

function getCsrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    if (match) {
        return decodeURIComponent(match[1]);
    }
    const input = document.querySelector("input[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
}

// Register before Alpine init so cart sync POSTs always carry CSRF.
document.addEventListener("htmx:configRequest", function (event) {
    const verb = (event.detail.verb || "").toLowerCase();
    if (verb && verb !== "get") {
        event.detail.headers["X-CSRFToken"] = getCsrfToken();
    }
});

document.addEventListener("alpine:init", function () {
    Alpine.store("cart", {
        items: readCartStorage(),
        syncUrl: "/marketplace/cart/sync/",
        canSync: false,

        get count() {
            return this.items.reduce(function (total, item) {
                return total + Number(item.quantity || 0);
            }, 0);
        },

        get isEmpty() {
            return this.items.length === 0;
        },

        init() {
            const root = document.documentElement;
            this.canSync = root.dataset.cartSync === "1";
            this.syncUrl = root.dataset.cartSyncUrl || this.syncUrl;
            this.items = readCartStorage();
            if (this.canSync && this.items.length) {
                this.sync();
            }
        },

        persist() {
            writeCartStorage(this.items);
            this.sync();
        },

        add(product) {
            const id = Number(product.id);
            const maxQty = Number(product.maxQty || 99);
            const existing = this.items.find(function (item) {
                return Number(item.id) === id;
            });

            if (existing) {
                this.items = this.items.map(function (item) {
                    if (Number(item.id) !== id) {
                        return item;
                    }
                    return Object.assign({}, item, {
                        quantity: Math.min(Number(item.quantity) + 1, maxQty),
                        maxQty: maxQty,
                        name: product.name,
                        price: product.price,
                        imageUrl: product.imageUrl || item.imageUrl || "",
                    });
                });
            } else {
                this.items = this.items.concat([
                    {
                        id: id,
                        name: product.name,
                        price: product.price,
                        imageUrl: product.imageUrl || "",
                        maxQty: maxQty,
                        quantity: 1,
                    },
                ]);
            }

            this.persist();
            this.openDrawer();
        },

        setQuantity(id, quantity) {
            const itemId = Number(id);
            let qty = Number(quantity);
            if (Number.isNaN(qty) || qty <= 0) {
                this.items = this.items.filter(function (item) {
                    return Number(item.id) !== itemId;
                });
            } else {
                this.items = this.items.map(function (item) {
                    if (Number(item.id) !== itemId) {
                        return item;
                    }
                    return Object.assign({}, item, {
                        quantity: Math.min(qty, Number(item.maxQty || 99)),
                    });
                });
            }
            this.persist();
        },

        remove(id) {
            const itemId = Number(id);
            this.items = this.items.filter(function (item) {
                return Number(item.id) !== itemId;
            });
            this.persist();
        },

        openDrawer() {
            const drawer = document.getElementById("cart-drawer");
            if (drawer) {
                drawer.checked = true;
            }
        },

        sync() {
            if (!this.canSync) {
                return;
            }

            const payload = {
                items: this.items.map(function (item) {
                    return {
                        product_id: Number(item.id),
                        quantity: Number(item.quantity),
                    };
                }),
            };

            // Silent backend store — no UI swap. Always send CSRF (do not rely on
            // simudza.js; it loads after Alpine and can race with init sync).
            const csrfToken = getCsrfToken();
            if (window.htmx) {
                htmx.ajax("POST", this.syncUrl, {
                    values: { payload: JSON.stringify(payload) },
                    swap: "none",
                    headers: { "X-CSRFToken": csrfToken },
                });
                return;
            }

            fetch(this.syncUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify(payload),
                credentials: "same-origin",
            }).catch(function () {});
        },
    });
});
