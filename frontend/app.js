/**
 * DIGICARD APP LOGIC
 * Version: Production Ready (Phase 6 - Optimization & UI Polish)
 * Updates:
 * - Added Business Category field support (VCF + Sheet)
 * - Replaced native confirm() with Modal
 * - "Humanized" all error messages
 */

// ==========================================
// 1. INIT & SCROLL BEHAVIOR
// ==========================================

// Prevent scrolling on body but allow interaction with specific controls
document.addEventListener('touchmove', function(e) {
    const isScrollable = e.target.closest('.scrollable');
    const isInteractive = 
        e.target.closest('button') || 
        e.target.closest('.switch') || 
        e.target.closest('input') || 
        e.target.closest('.control-side') || 
        e.target.closest('.slider');

    if (!isScrollable && !isInteractive) {
        e.preventDefault();
    }
}, { passive: false });

document.addEventListener('DOMContentLoaded', () => {
    // 1. Handle URL Token (Google Login Return)
    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get('token');

    if (urlToken) {
        localStorage.setItem('access_token', urlToken);
        state.token = urlToken;
        // Clean URL to prevent re-execution on refresh
        window.history.replaceState({}, document.title, "/");
    } else {
        state.token = localStorage.getItem('access_token');
    }

    // 2. Setup Listeners (Buttons, Toggles, etc.)
    setupEventListeners();
    
    // 3. Check Session -> IF Valid, THEN Start Camera
    checkSessionAndRecovery(); 
});

// ==========================================
// 2. STATE MANAGEMENT
// ==========================================
const state = {
    userEmail: null,
    token: localStorage.getItem('access_token'),
    
    // Scanning Modes
    mode: 'single',   // 'single' | 'dual'
    isBulk: false,    // Toggle state
    isLoginView: true,
    isGoogleConnected: false,
    
    // Logic State
    bulkCountServer: 0, // Count confirmed by server
    uploadingCount: 0,  // Count currently in network flight (Optimistic UI)
    tempFront: null,    // Blob for front image (Dual Mode)
    
    // Background Queues (Client Side)
    stitchQueue: [],    // { front: Blob, back: Blob }
    uploadQueue: [],    // { blob: Blob }
    isProcessing: false, // Flag to prevent concurrent processing loops
    
    editingTemplateId: null
};

// ==========================================
// 3. DOM ELEMENTS
// ==========================================
const els = {
    video: document.getElementById('camera-feed'),
    canvas: document.getElementById('capture-canvas'),
    
    // Visual Effects
    flashOverlay: document.getElementById('flash-overlay'),
    
    // HUD
    modeSlider: document.getElementById('mode-slider'),
    modeTexts: document.querySelectorAll('.mode-text'),
    
    bulkToggle: document.getElementById('bulk-toggle'),
    bulkIconArea: document.getElementById('bulk-icon-area'),
    submitIconArea: document.getElementById('submit-icon-area'),
    
    shutterBtn: document.getElementById('shutter-btn'),
    counterBadge: document.getElementById('counter-badge'),
    resetBtn: document.getElementById('btn-reset-scan'),
    
    profileBtn: document.getElementById('profile-btn'),
    
    // Overlays
    authOverlay: document.getElementById('view-auth'),
    dashOverlay: document.getElementById('view-dashboard'),
    resOverlay: document.getElementById('view-result'),
    emailSettingsOverlay: document.getElementById('view-email-settings'),
    tplEditorOverlay: document.getElementById('view-template-editor'),
    
    // Inputs
    authTitle: document.getElementById('auth-title'),
    emailInp: document.getElementById('inp-email'),
    passInp: document.getElementById('inp-pass'),
    authBtn: document.getElementById('btn-auth-action'),
    authToggle: document.getElementById('btn-toggle-auth'),
    authError: document.getElementById('auth-error'),
    googleLoginBtn: document.getElementById('btn-google-login'),
    
    dashUserEmail: document.getElementById('dash-user-email'),
    googleBtn: document.getElementById('btn-link-google'),
    googleBtnText: document.getElementById('google-btn-text'),
    exportBtn: document.getElementById('btn-export-excel'),
    btnOpenEmail: document.getElementById('btn-open-email'),
    
    btnBackSettings: document.getElementById('btn-back-settings'),
    emailToggle: document.getElementById('email-toggle'),
    templatesList: document.getElementById('templates-list'),
    btnCreateTpl: document.getElementById('btn-create-template'),
    inpTplSubject: document.getElementById('tpl-subject'),
    inpTplBody: document.getElementById('tpl-body'),
    btnSaveTpl: document.getElementById('btn-save-template'),
    
    resFields: {
        name: document.getElementById('res-name'),
        company: document.getElementById('res-company'),
        role: document.getElementById('res-role'),
        category: document.getElementById('res-category'), // NEW FIELD
        email: document.getElementById('res-email'),
        phone: document.getElementById('res-phone'),
        url: document.getElementById('res-url'),
        address: document.getElementById('res-address'),
        notes: document.getElementById('res-notes')
    },
    saveBtn: document.getElementById('btn-save-vcf'),
    
    // Alerts
    spinner: document.getElementById('spinner'),
    spinnerText: document.querySelector('#spinner p') || document.getElementById('spinner-text'),
    modal: document.getElementById('generic-modal'),
    mTitle: document.getElementById('modal-title'),
    mDesc: document.getElementById('modal-desc'),
    mConfirm: document.getElementById('modal-confirm'),
    mCancel: document.getElementById('modal-cancel'),
};

const CFG = {
    ANIM_DURATION: 0.4, 
    FADE_DURATION: 1.0 
};

// ==========================================
// 4. UI UPDATE LOGIC
// ==========================================

function updateHUD() {
    // 1. Shutter Button Border (Yellow for "Waiting for Back")
    if (state.mode === 'dual' && state.tempFront) {
        els.shutterBtn.style.border = "4px solid #FFC107"; 
    } else {
        els.shutterBtn.style.border = "4px solid white";
    }

    // 2. Counter Badge (Server + Local Queues + In-Flight Uploads)
    let totalPending = state.bulkCountServer + state.stitchQueue.length + state.uploadQueue.length + state.uploadingCount;
    
    // Fractional Logic: If Front is captured but Back isn't, represent as .5
    let badgeText = totalPending;
    if (state.tempFront) {
        badgeText = totalPending > 0 ? `${totalPending}.5` : "0.5";
    }

    // 3. Counter Badge Visibility
    if (totalPending > 0 || state.tempFront) {
        els.counterBadge.innerText = badgeText;
        els.counterBadge.classList.remove('hidden');
    } else {
        els.counterBadge.classList.add('hidden');
    }

    // 4. Left Control: Toggle vs Submit
    // If we are mid-capture (tempFront exists), Disable/Grey-out Submit
    if (state.tempFront) {
        els.bulkToggle.classList.add('disabled');
    } else {
        els.bulkToggle.classList.remove('disabled');
    }

    if (totalPending > 0) {
        els.bulkIconArea.classList.add('hidden');
        els.submitIconArea.classList.remove('hidden');
        els.bulkToggle.classList.remove('active'); 
    } else {
        els.bulkIconArea.classList.remove('hidden');
        els.submitIconArea.classList.add('hidden');
        els.bulkToggle.classList.toggle('active', state.isBulk);
    }

    // 5. Right Control: Reset / Cancel
    if (state.tempFront || totalPending > 0) {
        els.resetBtn.classList.remove('hidden');
        
        const label = els.resetBtn.querySelector('.label');
        const icon = els.resetBtn.querySelector('i');
        
        if (state.tempFront) {
            label.innerText = "Retake";
            label.style.color = "#FFC107";
            icon.style.color = "#FFC107";
            icon.className = "fa-solid fa-rotate-left";
        } else {
            label.innerText = "Cancel";
            label.style.color = "#ff4444";
            icon.style.color = "#ff4444";
            icon.className = "fa-solid fa-xmark";
        }
    } else {
        els.resetBtn.classList.add('hidden');
    }
}

// ==========================================
// 5. ANIMATIONS (Dynamic & Non-Blocking)
// ==========================================

function triggerCaptureAnimation(blob) {
    const url = URL.createObjectURL(blob);
    
    // Create NEW image element for every click to allow overlapping animations
    const img = document.createElement('img');
    img.src = url;
    img.classList.add('flying-photo'); 
    document.body.appendChild(img);

    img.style.opacity = '1';
    img.style.transform = 'scale(1) translate(0, 0)';
    img.style.borderRadius = '0';

    const flash = els.flashOverlay;
    flash.classList.remove('hidden');
    flash.style.opacity = '0.6';

    void img.offsetWidth;

    requestAnimationFrame(() => {
        flash.style.opacity = '0';
        img.style.transition = `transform ${CFG.ANIM_DURATION}s cubic-bezier(0.2, 1, 0.3, 1), border-radius ${CFG.ANIM_DURATION}s`;
        img.style.transform = 'scale(0.15) translate(20px, -120px)'; // To Bottom Left
        img.style.borderRadius = '10px';
    });

    setTimeout(() => {
        flash.classList.add('hidden');
    }, CFG.ANIM_DURATION * 1000);

    setTimeout(() => {
        img.style.transition = `opacity ${CFG.FADE_DURATION}s ease`;
        img.style.opacity = '0';
        setTimeout(() => {
            img.remove();
            URL.revokeObjectURL(url);
        }, CFG.FADE_DURATION * 1000);
    }, CFG.ANIM_DURATION * 1000);
}

// ==========================================
// 6. EVENT LISTENERS
// ==========================================
function setupEventListeners() {
    
    // --- MODE SWITCH (Replaced Native Confirm) ---
    els.modeTexts.forEach(el => {
        el.addEventListener('click', () => {
            const desiredMode = el.dataset.mode;
            
            // If active already, do nothing
            if (el.classList.contains('active')) return;

            const performSwitch = () => {
                state.tempFront = null;
                state.mode = desiredMode;
                els.modeTexts.forEach(t => t.classList.remove('active'));
                el.classList.add('active');
                els.modeSlider.style.transform = state.mode === 'single' ? 'translateX(0)' : 'translateX(100%)';
                updateHUD();
            };

            // If we have a partial scan, prompt the user
            if (state.tempFront) {
                showModal(
                    "Discard Partial Scan?", 
                    "Switching modes now will delete the front side of the card you just captured.", 
                    () => {
                        performSwitch();
                        hideModal();
                    }
                );
            } else {
                performSwitch();
            }
        });
    });

    // --- BULK TOGGLE / SUBMIT ---
    els.bulkToggle.addEventListener('click', async () => {
        if (!await ensureLoggedIn()) return;
        
        // Safety: If disabled (mid-dual scan), do nothing
        if (state.tempFront) return;

        const totalPending = state.bulkCountServer + state.stitchQueue.length + state.uploadQueue.length + state.uploadingCount;
        
        if (totalPending > 0) {
            // Submit Logic
            attemptSubmitBulk();
            return;
        }

        // --- NEW: VERIFY GOOGLE CONNECTION BEFORE ENABLING BULK ---
        if (!state.isBulk) {
            showSpinner("Verifying Connection...");
            try {
                const res = await fetch(`/api/auth/google/verify?token=${state.token}`);
                if (handleGoogleError(res)) return; // Checks 403
                
                if (res.status === 400) {
                    showAlert("Link Required", "Bulk Mode requires a linked Google Account. Please link it in the Dashboard.");
                    return;
                }
                
                if (!res.ok) throw new Error("Connection failed");
            } catch (e) {
                showAlert("Connection Error", "Could not verify Google permissions. Please check your internet or re-link your account.");
                hideSpinner();
                return; // Stop toggle
            } finally {
                hideSpinner();
            }
        }

        // Toggle Logic
        state.isBulk = !state.isBulk;
        updateHUD();
    });

    // --- RESET / CANCEL ---
    els.resetBtn.addEventListener('click', () => {
        // Priority 1: Retake Dual Front (0.5 -> 0)
        if (state.tempFront) {
            state.tempFront = null;
            updateHUD();
            return;
        }

        // Priority 2: Cancel Bulk Session
        const totalPending = state.bulkCountServer + state.stitchQueue.length + state.uploadQueue.length + state.uploadingCount;
        if (totalPending > 0) {
            showModal("Discard Session?", 
                "Are you sure you want to discard all pending images? This cannot be undone.", 
                async () => {
                    hideModal(); 
                    showSpinner("Cancelling..."); 
                    state.stitchQueue = [];
                    state.uploadQueue = [];
                    state.uploadingCount = 0; 
                    await cancelBulkSession();
                    hideSpinner();
                }
            );
        }
    });

    // --- SHUTTER ---
    els.shutterBtn.addEventListener('click', async () => {
        if (!await ensureLoggedIn()) return;
        els.shutterBtn.style.transform = "scale(0.9)";
        setTimeout(() => els.shutterBtn.style.transform = "scale(1)", 150);
        handleShutterPress();
    });

    // --- AUTH & OVERLAYS ---
    els.profileBtn.addEventListener('click', async () => {
        if (state.userEmail) { if(await verifyToken()) openOverlay(els.dashOverlay); } 
        else openOverlay(els.authOverlay);
    });

    document.querySelectorAll('.close-overlay').forEach(btn => {
        btn.addEventListener('click', (e) => closeOverlay(e.target.closest('.overlay')));
    });

    els.authToggle.addEventListener('click', () => {
        state.isLoginView = !state.isLoginView;
        els.authTitle.innerText = state.isLoginView ? "Login" : "Sign Up";
        els.authBtn.innerText = state.isLoginView ? "Login" : "Sign Up";
        els.authToggle.innerText = state.isLoginView ? "Create an account" : "Login";
    });

    els.authBtn.addEventListener('click', handleAuthSubmit);

    // GOOGLE AUTH HANDLERS
    if(els.googleLoginBtn) {
        els.googleLoginBtn.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/auth/google/login');
                const data = await res.json();
                window.location.href = data.auth_url;
            } catch(e) { 
                showAlert("Network Error", "Unable to reach Google Login. Please check your internet connection."); 
            }
        });
    }

    els.googleBtn.addEventListener('click', async () => {
        try {
            const res = await fetch(`/api/auth/google/link?token=${state.token}`);
            const data = await res.json();
            window.location.href = data.auth_url;
        } catch(e) { 
            showAlert("Network Error", "Unable to connect. Please check your internet connection."); 
        }
    });

    // DASHBOARD
    els.exportBtn.addEventListener('click', async () => {
        showSpinner("Exporting...");
        try {
            const res = await fetch(`/api/contacts/export?token=${state.token}`);
            if (handleGoogleError(res)) return; // Check for 403
            
            if (res.status === 410) { 
                showAlert("File Not Found", "The 'DigiCard_Contacts' sheet was deleted or moved from your Google Drive."); 
                return; 
            }
            if(!res.ok) throw new Error("Server error during export.");
            
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = "DigiCard_Contacts.xlsx"; document.body.appendChild(a); a.click(); a.remove();
        } catch (e) { 
            showAlert("Export Failed", "We couldn't download your contacts.\nDetails: " + friendlyError(e)); 
        } finally { hideSpinner(); }
    });

    document.getElementById('btn-logout').addEventListener('click', () => {
        showModal("Sign Out?", "You will need to sign in again to access your saved templates.", async () => {
            await fetch(`/api/logout?token=${state.token}`, {method:'POST'});
            localStorage.removeItem('access_token');
            state.token = null; 
            state.userEmail = null;
            updateProfileIcon(); 
            closeOverlay(els.dashOverlay); 
            hideModal();
            stopCamera(); // STOP CAMERA ON LOGOUT
            openOverlay(els.authOverlay); // Show Auth Screen
        });
    });

    // EMAIL SETTINGS
    if(els.btnOpenEmail) els.btnOpenEmail.addEventListener('click', openEmailSettings);
    els.btnBackSettings.addEventListener('click', () => {
        closeOverlay(els.emailSettingsOverlay);
        openOverlay(els.dashOverlay);
    });
    
    // Toggle Email Fix
    els.emailToggle.addEventListener('click', async (e) => {
        const desiredState = e.target.checked; 
        e.preventDefault(); 
        showSpinner("Saving Settings...");
        try {
            const res = await fetch(`/api/email/toggle?token=${state.token}&enabled=${desiredState}`, { method: 'POST' });
            if (handleGoogleError(res)) return;
            
            if (!res.ok) {
                const errData = await res.json();
                if (errData.detail && errData.detail.includes("active templates")) {
                    throw new Error("You must have at least one Active template before enabling Auto-Email.");
                }
                throw new Error("Failed to save setting.");
            }
            
            els.emailToggle.checked = desiredState;
        } catch(err) { 
            showAlert("Settings Error", err.message); 
        } finally { hideSpinner(); }
    });

    els.btnCreateTpl.addEventListener('click', () => {
        state.editingTemplateId = null;
        els.inpTplSubject.value = ""; els.inpTplBody.value = "Hi [Name],\n\n...";
        document.querySelector('#view-template-editor h2').innerText = "New Template";
        openOverlay(els.tplEditorOverlay);
    });
    els.btnSaveTpl.addEventListener('click', saveTemplate);

    // RESULT
    els.saveBtn.addEventListener('click', generateVCF);
    els.mCancel.addEventListener('click', hideModal);
}

// ==========================================
// 7. CAPTURE LOGIC (PIPELINE)
// ==========================================

async function handleShutterPress() {
    const blob = await captureFrame();
    triggerCaptureAnimation(blob);

    // --- DUAL MODE ---
    if (state.mode === 'dual') {
        if (!state.tempFront) {
            // STEP 1: Front
            state.tempFront = blob;
            updateHUD(); 
        } else {
            // STEP 2: Back -> Merge
            const front = state.tempFront;
            state.tempFront = null; // Reset immediately
            
            // Logic Fix: Only go to Bulk Queue if BULK MODE is active
            if (state.isBulk) {
                state.stitchQueue.push({ front, back: blob });
                updateHUD();
                processQueues(); // Background
            } else {
                // Not Bulk: Process Single Dual-Sided Scan
                const merged = await stitchImages(front, blob);
                
                setTimeout(() => {
                    uploadAndProcessSingle(merged);
                }, CFG.ANIM_DURATION * 500);
            }
        }
    } 
    // --- SINGLE MODE ---
    else {
        // If Bulk is active OR we have pending items -> Add to Upload Queue
        const totalPending = state.bulkCountServer + state.stitchQueue.length + state.uploadQueue.length + state.uploadingCount;
        
        if (state.isBulk || totalPending > 0) {
            state.uploadQueue.push({ blob });
            state.isBulk = true;
            
            updateHUD();
            processQueues(); 
        } else {
            // Pure Single Mode (Immediate View)
            setTimeout(() => {
                uploadAndProcessSingle(blob);
            }, CFG.ANIM_DURATION * 500);
        }
    }
}

// ==========================================
// 8. BACKGROUND PROCESSOR
// ==========================================

async function processQueues() {
    if (state.isProcessing) return; 
    state.isProcessing = true;

    try {
        while (state.stitchQueue.length > 0 || state.uploadQueue.length > 0) {
            
            // PRIORITY 1: Stitching
            if (state.stitchQueue.length > 0) {
                const pair = state.stitchQueue.shift(); 
                try {
                    const mergedBlob = await stitchImages(pair.front, pair.back);
                    state.uploadQueue.push({ blob: mergedBlob }); 
                    updateHUD();
                } catch (e) {
                    console.error("Stitch failed", e);
                }
                continue; 
            }

            // PRIORITY 2: Uploading
            if (state.uploadQueue.length > 0) {
                const item = state.uploadQueue.shift();
                state.uploadingCount++;
                updateHUD();

                try {
                    await uploadToStage(item.blob);
                } catch (e) {
                    console.error("Upload failed", e);
                    // If permissions revoked, stop queue
                    if (e.message.includes('403')) {
                        state.uploadQueue.unshift(item); 
                        state.isProcessing = false;
                        return;
                    }
                } finally {
                    state.uploadingCount--;
                    updateHUD(); 
                }
            }
        }
    } finally {
        state.isProcessing = false;
        updateHUD();
    }
}

async function uploadToStage(blob) {
    const fd = new FormData();
    fd.append('file', blob, "bulk.jpg");
    
    // NOTE: If fetch fails due to network, it throws.
    const res = await fetch(`/api/scan?token=${state.token}&bulk_stage=true`, { 
        method: 'POST', body: fd 
    });
    
    if (res.status === 403) {
        handleGoogleError(res);
        throw new Error("403 Forbidden");
    }
    
    if (!res.ok) throw new Error("Staging failed");
    
    // Handle JSON parsing specifically
    try {
        const data = await res.json();
        state.bulkCountServer = data.count;
    } catch (e) {
        throw new Error("Server response invalid");
    }
}

// SINGLE SCAN LOGIC (Blocking UI)
async function uploadAndProcessSingle(blob) {
    showSpinner("Processing...");
    try {
        const fd = new FormData();
        fd.append('file', blob, "scan.jpg");

        const res = await fetch(`/api/scan?token=${state.token}`, { method: 'POST', body: fd });

        if (res.status === 401) throw new Error("Auth failed");
        if (!res.ok) {
            if(res.status === 500) throw new Error("Server Error");
            throw new Error("Scan failed");
        }

        let data;
        try {
            data = await res.json();
        } catch(jsonErr) {
            throw new Error("Invalid response from server. Please try again.");
        }

        populateResult(data);
        openOverlay(els.resOverlay);

    } catch (e) {
        if(e.message === "Auth failed") {
            openOverlay(els.authOverlay);
        } else {
            // Humanized Error
            let msg = friendlyError(e);
            showAlert("Scan Failed", msg);
        }
    } finally {
        hideSpinner();
        state.tempFront = null;
        updateHUD();
    }
}

// ==========================================
// 9. SUBMIT & CANCEL LOGIC
// ==========================================

async function attemptSubmitBulk() {
    if (state.stitchQueue.length > 0 || state.uploadQueue.length > 0 || state.uploadingCount > 0) {
        
        showSpinner("Syncing items...");
        
        const check = setInterval(() => {
            const pending = state.stitchQueue.length + state.uploadQueue.length + state.uploadingCount;
            
            if(els.spinnerText) els.spinnerText.innerText = `Syncing ${pending} items...`;
            
            if (!state.isProcessing && (state.stitchQueue.length > 0 || state.uploadQueue.length > 0)) {
                processQueues();
            }

            if (pending === 0) {
                clearInterval(check);
                finalizeSubmit();
            }
        }, 500);
        
    } else {
        finalizeSubmit();
    }
}

async function finalizeSubmit() {
    showSpinner("Submitting Batch...");
    try {
        const res = await fetch(`/api/bulk/submit?token=${state.token}`, { method: 'POST' });
        if (handleGoogleError(res)) return;
        if(!res.ok) throw new Error("Submit failed");
        
        const data = await res.json();
        state.bulkCountServer = 0; state.stitchQueue = []; state.uploadQueue = []; state.uploadingCount = 0; state.isBulk = false;
        
        hideSpinner();
        showAlert("Batch Submitted", `Success! ${data.count} cards are being processed. They will appear in your Google Sheet shortly.`);
        updateHUD();
        
    } catch(e) {
        hideSpinner();
        showAlert("Submit Failed", "We couldn't submit your batch. " + friendlyError(e));
    }
}

async function cancelBulkSession() {
    try {
        const res = await fetch(`/api/bulk/cancel?token=${state.token}`, { method: 'POST' });
        if (handleGoogleError(res)) return;
        state.bulkCountServer = 0;
        state.uploadingCount = 0;
    } catch(e) {
        showAlert("Error", "Could not clear session. " + friendlyError(e));
    } finally {
        updateHUD();
    }
}

// ==========================================
// 10. SESSION & RECOVERY
// ==========================================

async function checkSessionAndRecovery() {
    // A. Not Logged In -> Show Auth, Don't Init Camera
    if (!state.token) {
        openOverlay(els.authOverlay);
        return;
    }
    
    try {
        // B. Logged In -> Verify Token
        const res = await fetch(`/api/me?token=${state.token}`);
        if (!res.ok) throw new Error();
        const user = await res.json();
        
        state.userEmail = user.email;
        state.isGoogleConnected = user.google_connected;
        
        updateProfileIcon();
        updateDashboardUI();
        if(els.dashUserEmail) els.dashUserEmail.innerText = state.userEmail;
        
        // C. Init Camera Only After Success
        initCamera();

        // D. Recover Bulk State
        if (state.isGoogleConnected) {
            const bulkRes = await fetch(`/api/bulk/check?token=${state.token}`);
            if (bulkRes.status === 403) {
                state.isGoogleConnected = false;
                updateDashboardUI();
                return;
            }
            const bulkData = await bulkRes.json();
            if (bulkData.count > 0) {
                state.bulkCountServer = bulkData.count;
                state.isBulk = true; 
                updateHUD();
                showModal("Pending Uploads", 
                    `We found ${bulkData.count} scanned cards from a previous session. Would you like to submit them now?`, 
                    () => { attemptSubmitBulk(); hideModal(); }
                );
            }
        }

    } catch {
        // Token Invalid -> Reset and Show Auth
        state.token = null;
        state.userEmail = null;
        localStorage.removeItem('access_token');
        updateProfileIcon();
        openOverlay(els.authOverlay);
    }
}

// ==========================================
// 11. IMAGE HELPERS
// ==========================================

async function initCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { 
                facingMode: 'environment', 
                width: { ideal: 1920 },
                height: { ideal: 1080 }
            }
        });
        els.video.srcObject = stream;
    } catch (e) {
        try {
             const stream = await navigator.mediaDevices.getUserMedia({ video: true });
             els.video.srcObject = stream;
        } catch(err2) {
            console.error("Camera failed", err2);
        }
    }
}

function stopCamera() {
    if (els.video.srcObject) {
        els.video.srcObject.getTracks().forEach(track => track.stop());
        els.video.srcObject = null;
    }
}

function captureFrame() {
    const ctx = els.canvas.getContext('2d');
    els.canvas.width = els.video.videoWidth;
    els.canvas.height = els.video.videoHeight;
    ctx.drawImage(els.video, 0, 0);
    return new Promise(resolve => els.canvas.toBlob(resolve, 'image/jpeg', 0.9));
}

async function stitchImages(blobFront, blobBack) {
    const loadImg = (b) => new Promise(res => { 
        const i = new Image(); 
        i.onload = () => res(i); 
        i.src = URL.createObjectURL(b); 
    });
    
    const [img1, img2] = await Promise.all([loadImg(blobFront), loadImg(blobBack)]);
    
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(img1.width, img2.width);
    canvas.height = img1.height + img2.height;
    
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img1, 0, 0);
    ctx.drawImage(img2, 0, img1.height);
    
    return new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.9));
}

// ==========================================
// 12. GENERAL HELPERS
// ==========================================

async function ensureLoggedIn() {
    if (state.token && await verifyToken()) return true;
    openOverlay(els.authOverlay);
    return false;
}

async function verifyToken() { return !!state.token; }

function updateDashboardUI() {
    if (state.isGoogleConnected) {
        els.googleBtn.style.background = "#4CAF50";
        els.googleBtn.style.color = "white";
        els.googleBtnText.innerText = "Manage Connection";
        els.googleBtn.disabled = false;
    } else {
        els.googleBtn.style.background = "#333";
        els.googleBtnText.innerText = "Link Google Account";
        els.googleBtn.disabled = false;
    }
}

function updateProfileIcon() {
    if (state.userEmail) {
        els.profileBtn.innerHTML = '<i class="fa-solid fa-user-check" style="color: #4CAF50;"></i>';
    } else {
        els.profileBtn.innerHTML = '<i class="fa-solid fa-user"></i>';
    }
}

/**
 * HUMAN READABLE ERROR MESSAGES
 * Converts technical exceptions into user-friendly text.
 */
function friendlyError(e) {
    const msg = e.message || "";
    if (msg.includes("Failed to fetch") || msg.includes("Network")) return "No internet connection.";
    if (msg.includes("JSON") || msg.includes("SyntaxError")) return "Server response was invalid. Please try again.";
    if (msg.includes("500")) return "Our server encountered a hiccup.";
    if (msg.includes("403")) return "Permission denied by Google.";
    if (msg.includes("401")) return "Session expired.";
    return msg; // Fallback
}

// GLOBAL ERROR HANDLER FOR 403 (Revoked Permissions)
function handleGoogleError(res) {
    if (res.status === 403) {
        hideSpinner();
        state.isGoogleConnected = false;
        updateDashboardUI();
        showModal(
            "Permissions Revoked", 
            "Google permissions are missing or expired. Please re-link your account to continue.", 
            () => {
                hideModal();
                // Trigger link flow
                els.googleBtn.click();
            }
        );
        return true;
    }
    return false;
}

async function handleAuthSubmit() {
    const email = els.emailInp.value;
    const password = els.passInp.value;
    
    if (!email || !password) {
        els.authError.innerText = "Please fill in both email and password.";
        return;
    }
    els.authBtn.innerText = "Processing...";
    els.authError.innerText = "";

    try {
        if (state.isLoginView) {
            const statusRes = await fetch('/api/check-status', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({email, password})
            });
            
            if (statusRes.status === 401) {
                throw new Error("Incorrect email or password.");
            }
            if (!statusRes.ok) throw new Error("Connection failed.");
            
            const res = await fetch('/api/login', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({email, password})
            });
            if (!res.ok) throw new Error("Login failed. Please try again.");
            
            const data = await res.json();
            state.token = data.access_token;
            localStorage.setItem('access_token', state.token);
            
            await checkSessionAndRecovery(); 
            closeOverlay(els.authOverlay);
            els.emailInp.value = ""; els.passInp.value = "";

        } else {
            const res = await fetch('/api/register', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({email, password})
            });
            if (res.status === 400) throw new Error("This email is already registered.");
            if (!res.ok) throw new Error("Registration failed.");
            
            showAlert("Welcome", "Account created successfully! Please login.");
            els.authToggle.click(); 
        }
    } catch (e) {
        els.authError.innerText = e.message;
    } finally {
        els.authBtn.innerText = state.isLoginView ? "Login" : "Sign Up";
    }
}

function populateResult(data) {
    const info = data.structured || {};
    const safeJoin = (arr) => Array.isArray(arr) ? arr.join('\n') : (arr || "");

    els.resFields.name.value = safeJoin(info.fn);
    els.resFields.company.value = info.org || "";
    els.resFields.role.value = info.title || "";
    // Populate new category field
    els.resFields.category.value = safeJoin(info.cat) || ""; 
    els.resFields.email.value = safeJoin(info.email);
    els.resFields.phone.value = safeJoin(info.tel);
    els.resFields.url.value = safeJoin(info.url);
    els.resFields.address.value = safeJoin(info.adr);
    els.resFields.notes.value = info.notes || "";
    
    if(!els.resFields.name.value && data.raw_text) {
        els.resFields.notes.value = "RAW TEXT:\n" + data.raw_text;
    }
}

async function generateVCF() {
    const split = (val) => val.value.split('\n').map(s => s.trim()).filter(Boolean);
    const splitComma = (val) => val.value.split(',').map(s => s.trim()).filter(Boolean);

    const f = els.resFields;
    
    const contactData = {
        fn: split(f.name), org: f.company.value.trim(), title: f.role.value.trim(),
        tel: split(f.phone), email: split(f.email), url: split(f.url),
        adr: split(f.address), 
        cat: splitComma(f.category), // New Field
        notes: f.notes.value.trim()
    };

    if (state.token && state.isGoogleConnected) {
        els.saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
        try {
            const response = await fetch(`/api/contacts/save?token=${state.token}`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(contactData)
            });
            if (handleGoogleError(response)) return;
            const data = await response.json();
            showAlert("Contact Saved", data.detail); 
        } catch (e) {
            console.error(e);
            showAlert("Cloud Save Failed", "We couldn't save to Google, but you can still download the VCF.");
        } finally {
            els.saveBtn.innerHTML = '<i class="fa-solid fa-download"></i> Save Contact';
        }
    } else if (!state.isGoogleConnected) {
         // Silent proceed if not connected, just download VCF
    }

    const primaryName = contactData.fn[0] || "Unknown";
    let vcf = ["BEGIN:VCARD", "VERSION:3.0", `FN:${primaryName}`];
    contactData.tel.forEach(p => vcf.push(`TEL;TYPE=CELL:${p}`));
    contactData.email.forEach(e => vcf.push(`EMAIL;TYPE=WORK:${e}`));
    
    // Add CATEGORIES to VCF
    if (contactData.cat.length > 0) {
        vcf.push(`CATEGORIES:${contactData.cat.join(",")}`);
    }

    vcf.push("END:VCARD");

    const blob = new Blob([vcf.join("\n")], { type: "text/vcard" });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${primaryName}.vcf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    
    closeOverlay(els.resOverlay);
}

async function openEmailSettings() {
    showSpinner("Loading...");
    try {
        const res = await fetch(`/api/email/settings?token=${state.token}`);
        if (handleGoogleError(res)) return;
        if (res.status === 400) { 
            showAlert("Feature Locked", "Please link your Google Account in the Dashboard to use email features."); 
            return; 
        }
        const data = await res.json();
        
        els.emailToggle.checked = data.enabled;
        els.btnCreateTpl.innerText = `Create New Template (${data.count}/5)`;
        els.btnCreateTpl.disabled = data.count >= 5;
        
        renderTemplates(data.templates);
        closeOverlay(els.dashOverlay);
        openOverlay(els.emailSettingsOverlay);
    } catch(e) {
        showAlert("Error", friendlyError(e));
    } finally {
        hideSpinner();
    }
}

function renderTemplates(templates) {
    els.templatesList.innerHTML = "";
    if(templates.length === 0) {
        els.templatesList.innerHTML = "<p style='text-align:center; padding:20px; color:#666;'>No templates yet.</p>";
        return;
    }
    
    templates.forEach(t => {
        const isActive = t.active === 'TRUE';
        const div = document.createElement('div');
        div.className = `template-card ${isActive ? 'active' : ''}`;
        div.innerHTML = `
            <div class="template-header"><h4>${t.subject}</h4><span class="status-indicator">${isActive ? 'ACTIVE' : 'INACTIVE'}</span></div>
            <p>${t.body}</p>
            <div class="template-actions">
                <button class="action-btn" onclick="window.openEditMode('${t.row_id}', '${escapeHtml(t.subject)}', '${escapeHtml(t.body)}')">Edit</button>
                <button class="action-btn btn-activate" onclick="window.toggleTemplateActive(${t.row_id}, ${!isActive})">${isActive ? 'Deactivate' : 'Set Active'}</button>
            </div>
        `;
        div.addEventListener('click', (e) => { if(e.target.tagName !== 'BUTTON') div.classList.toggle('expanded'); });
        els.templatesList.appendChild(div);
    });
}

window.openEditMode = function(rowId, subject, body) {
    state.editingTemplateId = rowId;
    els.inpTplSubject.value = subject;
    els.inpTplBody.value = body.replace(/\\n/g, '\n');
    document.querySelector('#view-template-editor h2').innerText = "Edit Template";
    openOverlay(els.tplEditorOverlay);
}

window.toggleTemplateActive = async function(rowId, shouldBeActive) {
    showSpinner("Updating...");
    try {
        const res = await fetch(`/api/email/templates/${rowId}/activate?token=${state.token}&active=${shouldBeActive}`, {method:'POST'});
        if (handleGoogleError(res)) return;
        openEmailSettings();
    } catch(e) {
        showAlert("Update Failed", "Could not update template status. " + friendlyError(e));
    } finally {
        hideSpinner();
    }
}

async function saveTemplate() {
    const subject = els.inpTplSubject.value;
    const body = els.inpTplBody.value;
    if(!subject || !body) {
        showAlert("Missing Info", "Please provide both a subject and body for the template.");
        return;
    }
    
    els.btnSaveTpl.innerText = "Saving...";
    try {
        let url = `/api/email/templates?token=${state.token}`;
        let method = 'POST';
        if (state.editingTemplateId) {
            url = `/api/email/templates/${state.editingTemplateId}?token=${state.token}`;
            method = 'PUT';
        }
        const res = await fetch(url, {
            method: method, headers: {'Content-Type':'application/json'},
            body: JSON.stringify({subject, body})
        });
        if (handleGoogleError(res)) return;
        
        if(!res.ok) {
            const txt = await res.text();
            throw new Error(txt);
        }
        closeOverlay(els.tplEditorOverlay);
        openEmailSettings();
    } catch(e) {
        showAlert("Save Failed", "Could not save template. " + friendlyError(e));
    } finally {
        els.btnSaveTpl.innerText = "Save Template";
    }
}

function escapeHtml(text) { return text.replace(/'/g, "&apos;").replace(/"/g, "&quot;").replace(/\n/g, "\\n"); }

function openOverlay(el) { el.classList.add('visible'); }
function closeOverlay(el) { el.classList.remove('visible'); }
function showSpinner(t) { if(els.spinnerText) els.spinnerText.innerText = t; els.spinner.classList.remove('hidden'); }
function hideSpinner() { els.spinner.classList.add('hidden'); }

// ==========================================
// 13. MODAL SYSTEM
// ==========================================

function showModal(title, desc, onConfirm) {
    els.mTitle.innerText = title;
    els.mDesc.innerText = desc;
    els.modal.classList.remove('hidden');
    
    // Ensure Cancel is visible for Confirm style modals
    els.mCancel.classList.remove('hidden');
    
    // Reset Confirm Button state
    const newConfirm = els.mConfirm.cloneNode(true);
    newConfirm.innerText = "Confirm";
    els.mConfirm.parentNode.replaceChild(newConfirm, els.mConfirm);
    els.mConfirm = newConfirm;
    
    els.mConfirm.addEventListener('click', onConfirm);
}

function showAlert(title, desc) {
    els.mTitle.innerText = title;
    els.mDesc.innerText = desc;
    els.modal.classList.remove('hidden');
    
    // Hide Cancel for Alert style modals
    els.mCancel.classList.add('hidden');
    
    // Set Confirm Button to 'OK' and just hide modal on click
    const newConfirm = els.mConfirm.cloneNode(true);
    newConfirm.innerText = "OK";
    els.mConfirm.parentNode.replaceChild(newConfirm, els.mConfirm);
    els.mConfirm = newConfirm;
    
    els.mConfirm.addEventListener('click', hideModal);
}

function hideModal() { els.modal.classList.add('hidden'); }