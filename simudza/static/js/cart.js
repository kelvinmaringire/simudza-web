const CART_STORAGE_KEY = "simudza_cart_v2";
const CART_TOKEN_KEY = "simudza_cart_token";

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

function getOrCreateCartToken() {
    try {
        let token = localStorage.getItem(CART_TOKEN_KEY);
        if (token) {
            return token;
        }
        if (window.crypto && crypto.randomUUID) {
            token = crypto.randomUUID();
        } else {
            token = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
                const r = (Math.random() * 16) | 0;
                const v = c === "x" ? r : (r & 0x3) | 0x8;
                return v.toString(16);
            });
        }
        localStorage.setItem(CART_TOKEN_KEY, token);
        return token;
    } catch (e) {
        return "";
    }
}

function getCsrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    if (match) {
        return decodeURIComponent(match[1]);
    }
    const input = document.querySelector("input[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
}

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
        isLoggedIn: false,
        _syncTimer: null,
        _syncGen: 0,

        get count() {
            return this.items.reduce(function (total, item) {
                return total + Number(item.quantity || 0);
            }, 0);
        },

        get isEmpty() {
            return this.items.length === 0;
        },

        get subtotal() {
            return this.items
                .reduce(function (total, item) {
                    return total + Number(item.price || 0) * Number(item.quantity || 0);
                }, 0)
                .toFixed(2);
        },

        get taxAmount() {
            if (!this.taxEnabled) {
                return "0.00";
            }
            const subtotal = Number(this.subtotal);
            const rate = Number(this.taxRate) / 100;
            if (!(subtotal > 0) || !(rate > 0)) {
                return "0.00";
            }
            let tax;
            if (this.taxMode === "included") {
                tax = (subtotal * rate) / (1 + rate);
            } else {
                tax = subtotal * rate;
            }
            return tax.toFixed(2);
        },

        get totalWithTax() {
            const subtotal = Number(this.subtotal);
            if (!this.taxEnabled || this.taxMode === "included") {
                return subtotal.toFixed(2);
            }
            return (subtotal + Number(this.taxAmount)).toFixed(2);
        },

        quantityOf(id) {
            const itemId = Number(id);
            const item = this.items.find(function (entry) {
                return Number(entry.id) === itemId;
            });
            return item ? Number(item.quantity) : 0;
        },

        lineTotal(item) {
            return (Number(item.price || 0) * Number(item.quantity || 0)).toFixed(2);
        },

        init() {
            const root = document.documentElement;
            this.canSync = root.dataset.cartSync === "1";
            this.isLoggedIn = root.dataset.cartLoggedIn === "1";
            this.syncUrl = root.dataset.cartSyncUrl || this.syncUrl;
            this.taxEnabled = root.dataset.taxEnabled === "1";
            this.taxMode = root.dataset.taxMode || "excluded";
            this.taxRate = root.dataset.taxRate || "0";
            this.items = readCartStorage();
            getOrCreateCartToken();
            if (this.canSync && (this.isLoggedIn || this.items.length)) {
                this.sync({ apply: !this.isLoggedIn || this.items.length > 0 });
            }
        },

        clear() {
            this.items = [];
            writeCartStorage(this.items);
            this._syncGen += 1;
            try {
                localStorage.removeItem(CART_TOKEN_KEY);
            } catch (e) {}
            getOrCreateCartToken();
        },

        persist() {
            writeCartStorage(this.items);
            // Invalidate in-flight syncs so a slower "add" response cannot
            // resurrect an item the user already removed.
            this._syncGen += 1;
            this.scheduleSync();
        },

        scheduleSync() {
            if (!this.canSync) {
                return;
            }
            const self = this;
            if (self._syncTimer) {
                clearTimeout(self._syncTimer);
            }
            self._syncTimer = setTimeout(function () {
                self._syncTimer = null;
                self.sync();
            }, 800);
        },

        applyServerItems(serverItems) {
            if (!Array.isArray(serverItems)) {
                return;
            }
            this.items = serverItems.map(function (item) {
                return {
                    id: Number(item.id),
                    name: item.name,
                    variantLabel: item.variantLabel || "",
                    price: item.price,
                    imageUrl: item.imageUrl || "",
                    url: item.url || "",
                    maxQty: Number(item.maxQty || 99),
                    quantity: Number(item.quantity),
                };
            });
            writeCartStorage(this.items);
        },

        add(line, quantity) {
            const id = Number(line.id);
            const maxQty = Number(line.maxQty || 99);
            const addQty = Math.max(1, Math.floor(Number(quantity) || 1));
            const existing = this.items.find(function (item) {
                return Number(item.id) === id;
            });

            if (existing) {
                this.items = this.items.map(function (item) {
                    if (Number(item.id) !== id) {
                        return item;
                    }
                    return Object.assign({}, item, {
                        quantity: Math.min(Number(item.quantity) + addQty, maxQty),
                        maxQty: maxQty,
                        name: line.name,
                        variantLabel: line.variantLabel || item.variantLabel || "",
                        price: line.price,
                        imageUrl: line.imageUrl || item.imageUrl || "",
                        url: line.url || item.url || "",
                    });
                });
            } else {
                this.items = this.items.concat([
                    {
                        id: id,
                        name: line.name,
                        variantLabel: line.variantLabel || "",
                        price: line.price,
                        imageUrl: line.imageUrl || "",
                        url: line.url || "",
                        maxQty: maxQty,
                        quantity: Math.min(addQty, maxQty),
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

        toggle(line) {
            if (this.quantityOf(line.id) > 0) {
                this.remove(line.id);
                return;
            }
            this.add(line);
        },

        openDrawer() {
            const drawer = document.getElementById("cart-drawer");
            if (drawer) {
                drawer.checked = true;
            }
        },

        sync(options) {
            if (!this.canSync) {
                return Promise.resolve(null);
            }

            const token = getOrCreateCartToken();
            if (!token) {
                return Promise.resolve(null);
            }

            const apply = !options || options.apply !== false;
            const gen = this._syncGen;

            const payload = {
                token: token,
                apply: apply,
                items: this.items.map(function (item) {
                    return {
                        variant_id: Number(item.id),
                        quantity: Number(item.quantity),
                    };
                }),
            };

            const csrfToken = getCsrfToken();
            const self = this;

            return fetch(this.syncUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify(payload),
                credentials: "same-origin",
            })
                .then(function (response) {
                    if (!response.ok) {
                        return null;
                    }
                    if (response.status === 204) {
                        return null;
                    }
                    return response.json();
                })
                .then(function (data) {
                    if (gen !== self._syncGen) {
                        return data;
                    }
                    if (data && data.token) {
                        try {
                            localStorage.setItem(CART_TOKEN_KEY, data.token);
                        } catch (e) {}
                    }
                    if (data && Object.prototype.hasOwnProperty.call(data, "items")) {
                        self.applyServerItems(data.items);
                    }
                    return data;
                })
                .catch(function () {
                    return null;
                });
        },

        goToCheckout(url) {
            const self = this;
            const target = url || "/marketplace/checkout/";
            if (self.isEmpty) {
                return;
            }
            self.sync({ apply: true }).then(function () {
                window.location.href = target;
            });
        },
    });
});
