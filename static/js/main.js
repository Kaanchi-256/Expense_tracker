// main.js — students will add JavaScript here as features are built

// Row actions dropdown (Recent transactions table)
document.addEventListener("click", function (event) {
    const openMenu = document.querySelector(".actions-menu.is-open");
    const toggleBtn = event.target.closest(".actions-menu-btn");

    if (openMenu && (!toggleBtn || toggleBtn.closest(".actions-menu") !== openMenu)) {
        openMenu.classList.remove("is-open");
        openMenu.querySelector(".actions-menu-btn").setAttribute("aria-expanded", "false");
    }

    if (!toggleBtn) return;

    const menu = toggleBtn.closest(".actions-menu");
    const isOpen = menu.classList.toggle("is-open");
    toggleBtn.setAttribute("aria-expanded", isOpen ? "true" : "false");
});

document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    const openMenu = document.querySelector(".actions-menu.is-open");
    if (!openMenu) return;
    openMenu.classList.remove("is-open");
    openMenu.querySelector(".actions-menu-btn").setAttribute("aria-expanded", "false");
});
