/* ========================================================
   Impairer — Client-side logic
   ======================================================== */

// --- DOM refs ---
const folderInput    = document.getElementById("folder-input");
const loadBtn        = document.getElementById("load-btn");
const toolbar        = document.getElementById("toolbar");
const compArea       = document.getElementById("comparison-area");
const controls       = document.getElementById("controls");
const progressText   = document.getElementById("progress-text");
const doneOverlay    = document.getElementById("done-overlay");
const doneFilename   = document.getElementById("done-filename");
const doneRestart    = document.getElementById("done-restart");

// Side-by-side
const sideContainer  = document.getElementById("sidebyside-container");
const panelLeft      = document.getElementById("panel-left");
const panelRight     = document.getElementById("panel-right");
const imgLeft        = document.getElementById("img-left");
const imgRight       = document.getElementById("img-right");
const fnLeft         = document.getElementById("filename-left");
const fnRight        = document.getElementById("filename-right");
const chooseLeft     = document.getElementById("choose-left");
const chooseRight    = document.getElementById("choose-right");

// Slider
const sliderContainer = document.getElementById("slider-container");
const sliderBase      = document.getElementById("slider-img-base");
const sliderOverlay   = document.getElementById("slider-overlay");
const sliderOverImg   = document.getElementById("slider-img-overlay");
const sliderDivider   = document.getElementById("slider-divider");

// Toolbar buttons
const modeBtns = document.querySelectorAll(".mode-btn");
const zoomBtns = document.querySelectorAll(".zoom-btn");
const sliderZoomBtns = document.querySelectorAll(".slider-zoom-btn");

// --- State ---
let currentMode = "sidebyside"; // "sidebyside" | "slider"
let currentZoom = "fit";        // "fit" | "actual" | "2x"
let sliderZoom  = "fit";        // "fit" | "actual"
let champion = null;
let challenger = null;
let championSide = "left";      // which panel currently shows the champion
let total = 0;
let sliderRatio = 0.5;          // current slider position
let sliderRatioY = 0.5;         // current vertical pan position

// Natural sizes (populated on image load)
let natLeft  = { w: 0, h: 0 };
let natRight = { w: 0, h: 0 };

// =====================================================
// API helpers
// =====================================================
async function apiPost(url, body) {
    const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    return resp.json();
}

function imageUrl(filename) {
    return "/api/image/" + encodeURIComponent(filename);
}

// =====================================================
// Load folder
// =====================================================
loadBtn.addEventListener("click", loadFolder);
folderInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") loadFolder();
});

async function loadFolder() {
    const folder = folderInput.value.trim();
    if (!folder) return;

    loadBtn.disabled = true;
    const data = await apiPost("/api/load", { folder });
    loadBtn.disabled = false;

    if (data.error) {
        alert(data.error);
        return;
    }

    total = data.total;

    if (data.status === "done") {
        showDone(data.winner);
        return;
    }

    champion = data.champion;
    challenger = data.challenger;
    championSide = "left";
    showComparison(data);
}

// =====================================================
// Show / update comparison
// =====================================================
function showComparison(data) {
    toolbar.classList.remove("hidden");
    compArea.classList.remove("hidden");
    controls.classList.remove("hidden");
    doneOverlay.classList.add("hidden");

    champion = data.champion;
    challenger = data.challenger;

    updateProgress(data.remaining);
    loadImages();
}

function updateProgress(remaining) {
    progressText.textContent = remaining + " comparison" + (remaining !== 1 ? "s" : "") + " left";
}

function loadImages() {
    const leftFile  = championSide === "left" ? champion : challenger;
    const rightFile = championSide === "left" ? challenger : champion;
    const leftSrc  = imageUrl(leftFile);
    const rightSrc = imageUrl(rightFile);

    // Side-by-side images
    imgLeft.src  = leftSrc;
    imgRight.src = rightSrc;

    // Slider images
    sliderBase.src   = leftSrc;
    sliderOverImg.src = rightSrc;

    fnLeft.textContent  = leftFile;
    fnLeft.title        = leftFile;
    fnRight.textContent = rightFile;
    fnRight.title       = rightFile;

    // Wait for both side-by-side images to load, then apply zoom
    let loaded = 0;
    function onLoad() {
        loaded++;
        if (loaded >= 2) {
            natLeft  = { w: imgLeft.naturalWidth,  h: imgLeft.naturalHeight };
            natRight = { w: imgRight.naturalWidth, h: imgRight.naturalHeight };
            if (currentMode === "slider") {
                applySliderZoom();
                updateSlider(sliderRatio);
            } else {
                applyZoom();
            }
        }
    }
    imgLeft.onload  = onLoad;
    imgRight.onload = onLoad;
}

// =====================================================
// Choose winner
// =====================================================
chooseLeft.addEventListener("click",  () => {
    const winner = championSide === "left" ? champion : challenger;
    chooseWinner(winner, "left");
});
chooseRight.addEventListener("click", () => {
    const winner = championSide === "right" ? champion : challenger;
    chooseWinner(winner, "right");
});

async function chooseWinner(winner, chosenSide) {
    chooseLeft.disabled  = true;
    chooseRight.disabled = true;

    const data = await apiPost("/api/choose", { winner });

    chooseLeft.disabled  = false;
    chooseRight.disabled = false;

    if (data.error) {
        alert(data.error);
        return;
    }

    if (data.status === "done") {
        showDone(data.winner);
        return;
    }

    championSide = chosenSide;
    showComparison(data);
}

// =====================================================
// Done screen
// =====================================================
function showDone(winner) {
    toolbar.classList.add("hidden");
    compArea.classList.add("hidden");
    controls.classList.add("hidden");
    doneOverlay.classList.remove("hidden");
    doneFilename.textContent = winner;
}

doneRestart.addEventListener("click", () => {
    doneOverlay.classList.add("hidden");
    folderInput.value = "";
    folderInput.focus();
});

// =====================================================
// Mode toggle
// =====================================================
modeBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
        const mode = btn.dataset.mode;
        if (mode === currentMode) return;
        currentMode = mode;
        modeBtns.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        applyMode();
    });
});

function applyMode() {
    compArea.classList.remove("mode-sidebyside", "mode-slider");
    compArea.classList.add("mode-" + currentMode);

    if (currentMode === "slider") {
        document.body.classList.add("slider-mode");
        applySliderZoom();
        // Reset slider to 50%
        updateSlider(0.5);
    } else {
        document.body.classList.remove("slider-mode");
        applyZoom();
    }
}

// =====================================================
// Zoom toggle
// =====================================================
zoomBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
        const zoom = btn.dataset.zoom;
        if (zoom === currentZoom) return;
        currentZoom = zoom;
        zoomBtns.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        applyZoom();
    });
});

function applyZoom() {
    compArea.classList.remove("zoom-fit", "zoom-actual", "zoom-2x", "zoom-4x");
    compArea.classList.add("zoom-" + currentZoom);

    const maxW = Math.max(natLeft.w, natRight.w);
    const maxH = Math.max(natLeft.h, natRight.h);
    if (maxW === 0 || maxH === 0) return;

    const pW = panelLeft.clientWidth;
    const pH = panelLeft.clientHeight;

    let imgW, imgH;
    if (currentZoom === "fit") {
        const scale = Math.min(pW / maxW, pH / maxH);
        imgW = maxW * scale;
        imgH = maxH * scale;
    } else if (currentZoom === "actual") {
        imgW = maxW;
        imgH = maxH;
    } else if (currentZoom === "2x") {
        imgW = maxW * 2;
        imgH = maxH * 2;
    } else {
        imgW = maxW * 4;
        imgH = maxH * 4;
    }

    imgLeft.style.width   = imgW + "px";
    imgLeft.style.height  = imgH + "px";
    imgRight.style.width  = imgW + "px";
    imgRight.style.height = imgH + "px";

    // Horizontal: push images toward center gap when narrower than panel
    if (imgW > pW) {
        panelLeft.style.justifyContent = "flex-start";
        panelRight.style.justifyContent = "flex-start";
    } else {
        panelLeft.style.justifyContent = "flex-end";
        panelRight.style.justifyContent = "flex-start";
    }

    // Vertical: center when shorter than panel, top-align for panning
    if (imgH > pH) {
        panelLeft.style.alignItems = "flex-start";
        panelRight.style.alignItems = "flex-start";
    } else {
        panelLeft.style.alignItems = "center";
        panelRight.style.alignItems = "center";
    }

    // Reset transform — panning will update when the mouse moves
    imgLeft.style.transform  = "";
    imgRight.style.transform = "";
}

// =====================================================
// Panning (side-by-side, zoomed modes)
// =====================================================
sideContainer.addEventListener("mousemove", (e) => {
    if (currentMode !== "sidebyside") return;
    if (currentZoom === "fit") return;

    const panelW = panelLeft.clientWidth;
    const panelH = panelLeft.clientHeight;
    const imgW   = imgLeft.offsetWidth;
    const imgH   = imgLeft.offsetHeight;

    if (imgW <= panelW && imgH <= panelH) return;

    // Normalized cursor position across the entire side-by-side container
    const rect = sideContainer.getBoundingClientRect();
    const nx = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const ny = Math.max(0, Math.min(1, (e.clientY - rect.top)  / rect.height));

    const overflowX = Math.max(0, imgW - panelW);
    const overflowY = Math.max(0, imgH - panelH);

    const tx = -overflowX * nx;
    const ty = -overflowY * ny;

    const t = `translate(${tx}px, ${ty}px)`;
    imgLeft.style.transform  = t;
    imgRight.style.transform = t;
});

// =====================================================
// Slider interaction
// =====================================================
sliderContainer.addEventListener("mousemove", (e) => {
    if (currentMode !== "slider") return;
    const rect = sliderContainer.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    sliderRatioY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
    updateSlider(ratio);
});

function updateSlider(ratio) {
    sliderRatio = ratio;
    const pct = ratio * 100;

    const containerW = sliderContainer.clientWidth;
    const containerH = sliderContainer.clientHeight;
    const maxW = Math.max(natLeft.w, natRight.w);
    const maxH = Math.max(natLeft.h, natRight.h);

    if (maxW === 0 || maxH === 0) {
        sliderOverlay.style.clipPath = "inset(0 " + (100 - pct) + "% 0 0)";
        sliderDivider.style.left = pct + "%";
        return;
    }

    let imgW, imgH;
    if (sliderZoom === "fit") {
        const scale = Math.min(containerW / maxW, containerH / maxH);
        imgW = maxW * scale;
        imgH = maxH * scale;
    } else if (sliderZoom === "2x") {
        imgW = maxW * 2;
        imgH = maxH * 2;
    } else if (sliderZoom === "4x") {
        imgW = maxW * 4;
        imgH = maxH * 4;
    } else {
        imgW = maxW;
        imgH = maxH;
    }

    // Center the image within the container
    let tx = (containerW - imgW) / 2;
    let ty = (containerH - imgH) / 2;

    // Pan when image overflows (all modes except fit)
    if (sliderZoom !== "fit") {
        if (imgW > containerW) tx = -(imgW - containerW) * ratio;
        if (imgH > containerH) ty = -(imgH - containerH) * sliderRatioY;
    }

    const t = `translate(${tx}px, ${ty}px)`;
    sliderBase.style.transform = t;
    sliderOverImg.style.transform = t;

    sliderOverlay.style.clipPath = "inset(0 " + (100 - pct) + "% 0 0)";
    sliderDivider.style.left = pct + "%";
}

// =====================================================
// Slider zoom toggle
// =====================================================
sliderZoomBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
        const zoom = btn.dataset.szoom;
        if (zoom === sliderZoom) return;
        sliderZoom = zoom;
        sliderZoomBtns.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        applySliderZoom();
    });
});

function applySliderZoom() {
    compArea.classList.remove("slider-fit", "slider-actual", "slider-2x", "slider-4x");
    compArea.classList.add("slider-" + sliderZoom);

    const containerW = sliderContainer.clientWidth;
    const containerH = sliderContainer.clientHeight;
    const maxW = Math.max(natLeft.w, natRight.w);
    const maxH = Math.max(natLeft.h, natRight.h);
    if (maxW === 0 || maxH === 0) return;

    let imgW, imgH;
    if (sliderZoom === "fit") {
        const scale = Math.min(containerW / maxW, containerH / maxH);
        imgW = maxW * scale;
        imgH = maxH * scale;
    } else if (sliderZoom === "2x") {
        imgW = maxW * 2;
        imgH = maxH * 2;
    } else if (sliderZoom === "4x") {
        imgW = maxW * 4;
        imgH = maxH * 4;
    } else {
        imgW = maxW;
        imgH = maxH;
    }

    sliderBase.style.width = imgW + "px";
    sliderBase.style.height = imgH + "px";
    sliderOverImg.style.width = imgW + "px";
    sliderOverImg.style.height = imgH + "px";

    updateSlider(sliderRatio);
}

// =====================================================
// Window resize → reapply zoom
// =====================================================
window.addEventListener("resize", () => {
    if (currentMode === "sidebyside") {
        applyZoom();
    }
    if (currentMode === "slider") {
        applySliderZoom();
    }
});

// =====================================================
// Heartbeat & shutdown (keeps exe alive while tab is open)
// =====================================================
setInterval(() => {
    fetch("/api/heartbeat", { method: "POST" }).catch(() => {});
}, 3000);

window.addEventListener("beforeunload", () => {
    navigator.sendBeacon("/api/shutdown");
});
