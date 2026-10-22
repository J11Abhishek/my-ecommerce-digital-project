/* ShopSphere front-end: fetch based cart updates + tiny UX helpers. */
(function () {
    "use strict";

    function getCookie(name) {
        var value = null;
        document.cookie.split(";").forEach(function (raw) {
            var cookie = raw.trim();
            if (cookie.indexOf(name + "=") === 0) {
                value = decodeURIComponent(cookie.substring(name.length + 1));
            }
        });
        return value;
    }

    function toast(message, isError) {
        if (!message) return;
        var el = document.createElement("div");
        el.className = "toast" + (isError ? " error" : "");
        el.textContent = message;
        document.body.appendChild(el);
        window.setTimeout(function () {
            el.classList.add("show");
        }, 20);
        window.setTimeout(function () {
            el.classList.remove("show");
            window.setTimeout(function () { el.remove(); }, 250);
        }, 2600);
    }

    function updateBadge(cart) {
        if (!cart || cart.count === undefined) return;
        var badge = document.getElementById("cart-count");
        if (badge) badge.textContent = cart.count;
    }

    function post(url, body) {
        var headers = { "X-Requested-With": "XMLHttpRequest" };
        var options = { method: "POST", headers: headers, credentials: "same-origin" };
        if (body instanceof FormData) {
            options.body = body;
        } else {
            headers["Content-Type"] = "application/json";
            headers["X-CSRFToken"] = getCookie("csrftoken");
            options.body = JSON.stringify(body);
        }
        return fetch(url, options).then(function (response) {
            return response.json().then(function (data) {
                return { ok: response.ok, data: data };
            });
        });
    }

    /* Add to cart without a full page reload. */
    document.querySelectorAll(".add-to-cart-form").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            if (!window.fetch) return; // graceful fallback to a normal post
            event.preventDefault();
            var button = form.querySelector("button[type=submit]");
            var original = button ? button.textContent : "";
            if (button) { button.disabled = true; button.textContent = "Adding..."; }

            post(form.action, new FormData(form))
                .then(function (result) {
                    var data = result.data || {};
                    updateBadge(data.cart);
                    toast(data.message, !data.ok);
                    if (data.ok && button) {
                        button.textContent = "Added \u2713";
                        window.setTimeout(function () { button.textContent = original; }, 1400);
                    }
                })
                .catch(function () { form.submit(); })
                .finally(function () {
                    window.setTimeout(function () {
                        if (button) { button.disabled = false; }
                    }, 500);
                });
        });
    });

    /* Cart page: quantity steppers, remove and clear. */
    var cartBody = document.querySelector("[data-cart-url]");
    if (cartBody) {
        var cartUrl = cartBody.getAttribute("data-cart-url");

        cartBody.addEventListener("click", function (event) {
            var removeBtn = event.target.closest("[data-remove-item]");
            if (removeBtn) {
                event.preventDefault();
                post(removeBtn.dataset.removeItem, { action: "remove" })
                    .then(function (result) { window.location.reload(); });
                return;
            }
            var stepBtn = event.target.closest("[data-step]");
            if (stepBtn) {
                event.preventDefault();
                var wrap = stepBtn.closest("[data-item-row]");
                var input = wrap.querySelector("input[name=quantity]");
                var next = parseInt(input.value, 10) + parseInt(stepBtn.dataset.step, 10);
                if (next < 1) return;
                input.value = next;
                post(stepBtn.dataset.updateUrl, { quantity: next }).then(function (result) {
                    var data = result.data || {};
                    updateBadge(data.cart);
                    toast(data.message, !data.ok);
                    if (data.ok) window.location.reload();
                    else input.value = wrap.dataset.currentQuantity;
                });
            }
        });
    }

    /* Confirm destructive actions such as cancelling an order. */
    document.querySelectorAll("[data-confirm]").forEach(function (element) {
        element.addEventListener("click", function (event) {
            if (!window.confirm(element.getAttribute("data-confirm"))) {
                event.preventDefault();
            }
        });
    });

    /* Client-side filter convenience: submit the form on select change. */
    document.querySelectorAll("[data-autosubmit]").forEach(function (element) {
        element.addEventListener("change", function () { element.form.submit(); });
    });
})();
