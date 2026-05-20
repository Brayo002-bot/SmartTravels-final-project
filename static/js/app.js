const menuBtn = document.getElementById("menuBtn");
const mobileMenu = document.getElementById("mobileMenu");

menuBtn.addEventListener("click", () => {
  if (mobileMenu.classList.contains("mobile-menu-open")) {
    mobileMenu.classList.remove("mobile-menu-open");
    mobileMenu.classList.add("mobile-menu-closed");
  } else {
    mobileMenu.classList.remove("mobile-menu-closed");
    mobileMenu.classList.add("mobile-menu-open");
  }
});