document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".copy-box").forEach(box => {
        box.addEventListener("click", function () {
            const text = this.getAttribute("data-copy");
    
            navigator.clipboard.writeText(text).then(() => {
                this.classList.add("copied");
    
                setTimeout(() => {
                    this.classList.remove("copied");
                    }, 1200);
            });
        });
    });
});



document.addEventListener("DOMContentLoaded", function () {
    const flashes = document.querySelectorAll(".flash");

    flashes.forEach(flash => {
        setTimeout(() => {
            flash.classList.add("hide");
            setTimeout(() =>{
                flash.remove();
            }, 600);
        }, 5000);
    });
});


document.addEventListener("DOMContentLoaded", function () {
    console.log("SCRIPT LOADED")

    const copyBtn = document.getElementById("copyBtn");
    const textToCopy = document.getElementById("textToCopy");
    const copyStatus = document.getElementById("copyStatus");
    
    copyBtn.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(textToCopy.innerText);
            copyStatus.innerText = "Copied!";
            setTimeout(() => (copyStatus.innerText = ""), 3500);
        } catch (err) {
            copyStatus.innerText = "Copy failed!";
            setTimeout(() => (copyStatus.innerText = ""), 3500);
        }
    });
    
});



document.addEventListener("DOMContentLoaded", function () {
    const hamburger = document.getElementById("hamburger");
    const mainNavLinks = document.getElementById("mainNavLinks");
    const icon = hamburger.querySelector("i");
    
    hamburger.addEventListener('click', function() {
        mainNavLinks.classList.toggle("open");
    
        if (mainNavLinks.classList.contains("open")) {
            icon.classList.replace("fa-bars", "fa-xmark");
        } else {
            icon.classList.replace("fa-xmark", "fa-bars");
        }
    });
});



const sidebar = document.querySelector(".sidebar");
const sidebarToggler = document.querySelector(".sidebar-toggler");


sidebarToggler.addEventListener('click', () => {
    sidebar.classList.toggle("collapsed");
});

const text = document.getElementById("textToCopy")?.innerText;
navigator.clipboard.writeText(text);