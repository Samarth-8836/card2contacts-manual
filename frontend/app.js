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
document.addEventListener('touchmove', function (e) {
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
    // 1. Handle URL Token (Google Login Return) and Error Parameters
    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get('token');
    const errorType = urlParams.get('error');
    const googleLinked = urlParams.get('google_linked');

    // Handle Google linking errors (incomplete permissions)
    if (errorType === 'incomplete_permissions') {
        const missingScopes = urlParams.get('missing');
        showAlert(
            "Incomplete Permissions",
            "You must grant ALL requested permissions to link your Google account. Please try again and ensure all checkboxes are checked during authorization.",
            () => {
                // After user dismisses, clean URL
                window.history.replaceState({}, document.title, "/");
            }
        );
    }

    // Handle successful Google linking
    if (googleLinked === 'success') {
        showAlert(
            "Google Account Linked",
            "Your Google account has been successfully linked with full permissions!",
            () => {
                window.history.replaceState({}, document.title, "/");
            }
        );
    }

    if (urlToken) {
        localStorage.setItem('access_token', urlToken);
        state.token = urlToken;
        // Clean URL to prevent re-execution on refresh (if no error to show)
        if (!errorType && !googleLinked) {
            window.history.replaceState({}, document.title, "/");
        }
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
    userType: 'single', // 'single' | 'enterprise_admin' | 'sub_account'
    isDistributor: false, // Whether user has distributor role

    // License Information (for single users)
    licenseStatus: 'none', // 'none' | 'valid' | 'expired'
    scansRemaining: null,  // Number or 'unlimited'
    scanCount: 0,
    licenseExpiresAt: null,

    // Scanning Modes
    mode: 'single',   // 'single' | 'dual'
    isBulk: false,    // Toggle state
    isLoginView: true,
    isGoogleLinked: false,  // Has tokens (linked at some point)
    isGoogleConnected: false,  // Has all required scopes
    googleMissingScopes: [],  // Array of missing scope names

    // Logic State
    bulkCountServer: 0, // Count confirmed by server
    uploadingCount: 0,  // Count currently in network flight (Optimistic UI)
    tempFront: null,    // Blob for front image (Dual Mode)

    // Background Queues (Client Side)
    stitchQueue: [],    // { front: Blob, back: Blob }
    uploadQueue: [],    // { blob: Blob }
    isProcessing: false, // Flag to prevent concurrent processing loops

    editingTemplateId: null,
    editingSubAccountId: null, // For editing sub-accounts

    // OTP Login Flow State
    loginSessionToken: null,  // UUID tracking current login attempt
    pendingUserType: null,    // User type during login flow
    pendingIdentifier: null,  // Email/username used for login
    pendingPassword: null,    // Password (needed for resend)
    requiresPasswordChange: false  // Whether user needs to change password after login
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
    adminPanelOverlay: document.getElementById('view-admin-panel'),
    subEditorOverlay: document.getElementById('view-sub-editor'),

    // Auth Overlays
    otpOverlay: document.getElementById('view-otp'),
    setUsernameOverlay: document.getElementById('view-set-username'),
    setAdminEmailOverlay: document.getElementById('view-set-admin-email'),
    passwordResetOverlay: document.getElementById('view-password-reset'),
    changePasswordOverlay: document.getElementById('view-change-password'),

    // Inputs
    authTitle: document.getElementById('auth-title'),
    identifierInp: document.getElementById('inp-identifier'),
    usernameInp: document.getElementById('inp-username'),
    emailInp: document.getElementById('inp-email'),
    passInp: document.getElementById('inp-pass'),
    authBtn: document.getElementById('btn-auth-action'),
    authToggle: document.getElementById('btn-toggle-auth'),
    forgotPasswordBtn: document.getElementById('btn-forgot-password'),
    authError: document.getElementById('auth-error'),
    googleLoginBtn: document.getElementById('btn-google-login'),

    // OTP inputs
    otpEmailDisplay: document.getElementById('otp-email-display'),
    otpInp: document.getElementById('inp-otp'),
    verifyOtpBtn: document.getElementById('btn-verify-otp'),
    resendOtpBtn: document.getElementById('btn-resend-otp'),
    otpError: document.getElementById('otp-error'),

    // Username migration inputs
    migrationUsernameInp: document.getElementById('inp-migration-username'),
    saveUsernameBtn: document.getElementById('btn-save-username'),
    usernameError: document.getElementById('username-error'),

    // Admin email setup inputs
    adminEmailInp: document.getElementById('inp-admin-email'),
    saveAdminEmailBtn: document.getElementById('btn-save-admin-email'),
    adminEmailError: document.getElementById('admin-email-error'),

    // Password reset inputs
    resetEmailInp: document.getElementById('inp-reset-email'),
    resetPasswordBtn: document.getElementById('btn-reset-password'),
    resetMessage: document.getElementById('reset-message'),

    // Change password inputs
    currentPasswordInp: document.getElementById('inp-current-password'),
    newPasswordInp: document.getElementById('inp-new-password'),
    confirmPasswordInp: document.getElementById('inp-confirm-password'),
    changePasswordBtn: document.getElementById('btn-change-password'),
    changePasswordError: document.getElementById('change-password-error'),

    dashUserEmail: document.getElementById('dash-user-email'),
    userTypeBadge: document.getElementById('user-type-badge'),
    googleStatusArea: document.getElementById('google-status-area'),
    googleBtn: document.getElementById('btn-link-google'),
    googleBtnText: document.getElementById('google-btn-text'),
    exportBtn: document.getElementById('btn-export-excel'),
    btnOpenEmail: document.getElementById('btn-open-email'),
    btnOpenAdmin: document.getElementById('btn-open-admin'),
    btnOpenDistributor: document.getElementById('btn-open-distributor'),

    btnBackSettings: document.getElementById('btn-back-settings'),
    emailToggle: document.getElementById('email-toggle'),
    templatesList: document.getElementById('templates-list'),
    btnCreateTpl: document.getElementById('btn-create-template'),
    inpTplSubject: document.getElementById('tpl-subject'),
    inpTplBody: document.getElementById('tpl-body'),
    btnSaveTpl: document.getElementById('btn-save-template'),
    tplAttachment: document.getElementById('tpl-attachment'),
    btnSelectFile: document.getElementById('btn-select-file'),
    attachedFilesList: document.getElementById('attached-files-list'),
    filesContainer: document.getElementById('files-container'),
    totalSizeDisplay: document.getElementById('total-size-display'),

    // Admin Panel
    btnBackAdmin: document.getElementById('btn-back-admin'),
    licenseKeyDisplay: document.getElementById('license-key-display'),
    subAccountCount: document.getElementById('sub-account-count'),
    subAccountsList: document.getElementById('sub-accounts-list'),
    btnCreateSub: document.getElementById('btn-create-sub'),
    btnExpandSeats: document.getElementById('btn-expand-seats'),

    // Sub-Account Editor
    subEditorTitle: document.getElementById('sub-editor-title'),
    subUsername: document.getElementById('sub-username'),
    subPassword: document.getElementById('sub-password'),
    btnSaveSub: document.getElementById('btn-save-sub'),

    // Expand Seats Modal
    expandSeatsOverlay: document.getElementById('view-expand-seats'),
    currentMaxSeats: document.getElementById('current-max-seats'),
    currentUsedSeats: document.getElementById('current-used-seats'),
    seatsToAdd: document.getElementById('seats-to-add'),
    newMaxSeatsPreview: document.getElementById('new-max-seats-preview'),
    btnConfirmExpandSeats: document.getElementById('btn-confirm-expand-seats'),

    // Distributor Dashboard
    distributorOverlay: document.getElementById('view-distributor'),
    btnBackDistributor: document.getElementById('btn-back-distributor'),
    singleTotal: document.getElementById('single-total'),
    enterpriseTotal: document.getElementById('enterprise-total'),
    distSingleUsername: document.getElementById('dist-single-username'),
    distSingleEmail: document.getElementById('dist-single-email'),
    distEntUsername: document.getElementById('dist-ent-username'),
    distEntEmail: document.getElementById('dist-ent-email'),
    btnCreateSingle: document.getElementById('btn-create-single'),
    btnCreateEnterprise: document.getElementById('btn-create-enterprise'),

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
    // 0. Mode Slider Position
    els.modeSlider.style.transform = state.mode === 'single' ? 'translateX(0)' : 'translateX(100%)';

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
        // Check token instead of userEmail (sub-accounts don't have email)
        if (state.token) {
            if (await verifyToken()) openOverlay(els.dashOverlay);
        } else openOverlay(els.authOverlay);
    });

    document.querySelectorAll('.close-overlay').forEach(btn => {
        btn.addEventListener('click', (e) => closeOverlay(e.target.closest('.overlay')));
    });

    els.authToggle.addEventListener('click', () => {
        state.isLoginView = !state.isLoginView;
        els.authTitle.innerText = state.isLoginView ? "Login" : "Sign Up";
        els.authBtn.innerText = state.isLoginView ? "Login" : "Sign Up";
        els.authToggle.innerText = state.isLoginView ? "Create an account" : "Login";

        // Toggle forgot password button visibility
        if (state.isLoginView) {
            if (els.forgotPasswordBtn) els.forgotPasswordBtn.classList.remove('hidden');
        } else {
            if (els.forgotPasswordBtn) els.forgotPasswordBtn.classList.add('hidden');
        }
    });

    els.authBtn.addEventListener('click', handleAuthSubmit);

    // Forgot Password
    if (els.forgotPasswordBtn) {
        els.forgotPasswordBtn.addEventListener('click', () => {
            closeOverlay(els.authOverlay);
            openOverlay(els.passwordResetOverlay);
        });
    }

    // OTP Verification
    if (els.verifyOtpBtn) {
        els.verifyOtpBtn.addEventListener('click', verifyOTP);
    }
    if (els.resendOtpBtn) {
        els.resendOtpBtn.addEventListener('click', resendOTP);
    }

    // Password Reset
    if (els.resetPasswordBtn) {
        els.resetPasswordBtn.addEventListener('click', requestPasswordReset);
    }

    // Change Password
    if (els.changePasswordBtn) {
        els.changePasswordBtn.addEventListener('click', changePassword);
    }

    // GOOGLE AUTH HANDLERS
    if (els.googleLoginBtn) {
        els.googleLoginBtn.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/auth/google/login');
                const data = await res.json();
                window.location.href = data.auth_url;
            } catch (e) {
                showAlert("Network Error", "Unable to reach Google Login. Please check your internet connection.");
            }
        });
    }

    els.googleBtn.addEventListener('click', async () => {
        try {
            const res = await fetch(`/api/auth/google/link?token=${state.token}`);
            const data = await res.json();
            window.location.href = data.auth_url;
        } catch (e) {
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
            if (!res.ok) throw new Error("Server error during export.");

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
            await fetch(`/api/logout?token=${state.token}`, { method: 'POST' });
            localStorage.removeItem('access_token');
            state.token = null;
            state.userEmail = null;
            state.username = null;
            state.userType = 'single';
            updateProfileIcon();
            closeOverlay(els.dashOverlay);
            hideModal();
            stopCamera(); // STOP CAMERA ON LOGOUT
            openOverlay(els.authOverlay); // Show Auth Screen
        });
    });

    // LICENSE UPGRADE
    const upgradeBtn = document.getElementById('btn-upgrade-license');
    if (upgradeBtn) {
        upgradeBtn.addEventListener('click', () => {
            const emailDisplay = document.getElementById('upgrade-email-display');
            if (emailDisplay) emailDisplay.innerText = state.userEmail;
            closeOverlay(els.dashOverlay);
            openOverlay(document.getElementById('view-upgrade-instructions'));
        });
    }

    // CONTACT DISTRIBUTOR
    const contactDistributorBtn = document.getElementById('btn-contact-distributor');
    if (contactDistributorBtn) {
        contactDistributorBtn.addEventListener('click', async () => {
            showSpinner("Sending contact request...");
            try {
                const res = await fetch(`/api/user/contact-distributor?token=${state.token}`, {
                    method: 'POST'
                });

                if (!res.ok) {
                    const errData = await res.json();
                    throw new Error(errData.detail || 'Failed to send contact request');
                }

                const data = await res.json();
                hideSpinner();
                showAlert(data.message || "Your request has been sent successfully!", 'success');
            } catch (err) {
                hideSpinner();
                showAlert(err.message || "Failed to send contact request. Please try again.", 'error');
            }
        });
    }

    // EMAIL SETTINGS
    if (els.btnOpenEmail) els.btnOpenEmail.addEventListener('click', openEmailSettings);
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
        } catch (err) {
            showAlert("Settings Error", err.message);
        } finally { hideSpinner(); }
    });

    els.btnCreateTpl.addEventListener('click', () => {
        state.editingTemplateId = null;
        state.attachedFiles = [];
        els.inpTplSubject.value = "Great connecting with you, {{ first_name }}!";
        els.inpTplBody.value = `Hi {{ first_name }},

It was wonderful meeting you! I wanted to reach out and stay connected.
{{% if company %}}
I'm impressed by the work {{ company }} is doing{{% if category %}} in the {{ category }} space{{% endif %}}.{{% endif %}}{{% if title %}} Your role as {{ title }} sounds exciting, and I'd love to learn more about your work.{{% endif %}}
{{% if notes %}}
Quick note from our conversation: {{ notes }}{{% endif %}}

I believe there could be great opportunities for us to collaborate or share insights. Would love to continue the conversation when you have a moment.
{{% if website %}}
I also checked out {{ website }} - really impressive!{{% endif %}}

Looking forward to staying in touch!

Best regards`;
        renderAttachedFiles();
        document.querySelector('#view-template-editor h2').innerText = "New Template";
        openOverlay(els.tplEditorOverlay);
    });
    els.btnSaveTpl.addEventListener('click', saveTemplate);

    // File attachment handlers
    els.btnSelectFile.addEventListener('click', () => els.tplAttachment.click());
    els.tplAttachment.addEventListener('change', handleFileSelect);

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
        if (res.status === 403) {
            // Scan limit reached
            const errorData = await res.json();
            throw new Error(errorData.detail || "Scan limit reached");
        }
        if (!res.ok) {
            if (res.status === 500) throw new Error("Server Error");
            throw new Error("Scan failed");
        }

        let data;
        try {
            data = await res.json();
        } catch (jsonErr) {
            throw new Error("Invalid response from server. Please try again.");
        }

        populateResult(data);
        openOverlay(els.resOverlay);

        // Refresh user data to update scan count and license status in real-time
        refreshUserData();

    } catch (e) {
        if (e.message === "Auth failed") {
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

            if (els.spinnerText) els.spinnerText.innerText = `Syncing ${pending} items...`;

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
        if (!res.ok) throw new Error("Submit failed");

        const data = await res.json();
        state.bulkCountServer = 0; state.stitchQueue = []; state.uploadQueue = []; state.uploadingCount = 0; state.isBulk = false;

        hideSpinner();
        showAlert("Batch Submitted", `Success! ${data.count} cards are being processed. They will appear in your Google Sheet shortly.`);
        updateHUD();

    } catch (e) {
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
    } catch (e) {
        showAlert("Error", "Could not clear session. " + friendlyError(e));
    } finally {
        updateHUD();
    }
}

// ==========================================
// 10. SESSION & RECOVERY
// ==========================================

/**
 * Refresh user data from server (license status, scan count, etc.)
 * Used to update UI after scans without full page refresh
 */
async function refreshUserData() {
    if (!state.token) return;

    try {
        const res = await fetch(`/api/me?token=${state.token}`);
        if (!res.ok) return;
        const user = await res.json();

        // Update state with latest user data
        state.userEmail = user.email;
        state.isGoogleLinked = user.google_linked || false;
        state.isGoogleConnected = user.google_connected;
        state.googleMissingScopes = user.google_missing_scopes || [];
        state.userType = user.user_type || 'single';
        state.isDistributor = user.is_distributor || false;

        // Update license information (for single users)
        if (user.license_status) {
            state.licenseStatus = user.license_status;
            state.scansRemaining = user.scans_remaining;
            state.scanCount = user.scan_count || 0;
            state.licenseExpiresAt = user.license_expires_at;
        }

        // Refresh UI components
        updateLicenseStatusUI();
        updateProfileIcon();
        updateGoogleLinkButtonVisibility();  // Hide Google link button if already linked
    } catch (e) {
        // Silent fail - don't disrupt user experience
        console.error("Failed to refresh user data:", e);
    }
}

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
        state.isGoogleLinked = user.google_linked || false;
        state.isGoogleConnected = user.google_connected;
        state.googleMissingScopes = user.google_missing_scopes || [];
        state.userType = user.user_type || 'single';
        state.isDistributor = user.is_distributor || false;

        // Store license information (for single users)
        if (user.license_status) {
            state.licenseStatus = user.license_status;
            state.scansRemaining = user.scans_remaining;
            state.scanCount = user.scan_count || 0;
            state.licenseExpiresAt = user.license_expires_at;
        }

        updateProfileIcon();
        updateDashboardUI();
        updateDashboardUIForUserType();
        updateLicenseStatusUI(); // Update license status display
        updateGoogleLinkButtonVisibility();  // Hide Google link button if already linked
        // Display email for all user types
        if (els.dashUserEmail) els.dashUserEmail.innerText = state.userEmail || '';

        // C. Init Camera Only After Success
        initCamera();

        // Initialize mode slider position
        updateHUD();

        // D. Recover Bulk State (skip for sub-accounts as they don't use bulk)
        if (state.isGoogleConnected && state.userType !== 'sub_account') {
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
        state.userType = 'single';
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
        } catch (err2) {
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

function applySharpening(canvas) {
    const ctx = canvas.getContext('2d');
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imageData.data;
    const width = canvas.width;
    const height = canvas.height;

    const kernel = [0, -0.5, 0, -0.5, 3, -0.5, 0, -0.5, 0];
    const kSize = 3;
    const half = Math.floor(kSize / 2);

    const original = new Uint8ClampedArray(data);

    for (let y = half; y < height - half; y++) {
        for (let x = half; x < width - half; x++) {
            let r = 0, g = 0, b = 0;

            for (let ky = 0; ky < kSize; ky++) {
                for (let kx = 0; kx < kSize; kx++) {
                    const px = x + kx - half;
                    const py = y + ky - half;
                    const idx = (py * width + px) * 4;
                    const k = kernel[ky * kSize + kx];

                    r += original[idx] * k;
                    g += original[idx + 1] * k;
                    b += original[idx + 2] * k;
                }
            }

            const idx = (y * width + x) * 4;
            data[idx] = Math.min(255, Math.max(0, r));
            data[idx + 1] = Math.min(255, Math.max(0, g));
            data[idx + 2] = Math.min(255, Math.max(0, b));
        }
    }

    ctx.putImageData(imageData, 0, 0);
}

function captureFrame() {
    const ctx = els.canvas.getContext('2d');
    els.canvas.width = els.video.videoWidth;
    els.canvas.height = els.video.videoHeight;
    ctx.drawImage(els.video, 0, 0);

    applySharpening(els.canvas);

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
    const googleArea = els.googleStatusArea;

    if (state.isGoogleConnected) {
        // Hide the entire Google integration area once ALL permissions are granted
        if (googleArea) googleArea.style.display = 'none';
    } else {
        // Show Google integration area with status/button
        if (googleArea && state.userType !== 'sub_account') {
            googleArea.style.display = 'block';

            if (state.isGoogleLinked) {
                // Linked but missing some permissions
                els.googleBtn.style.background = "#ff9800";  // Orange for warning
                els.googleBtnText.innerText = "Grant Missing Permissions";
            } else {
                // Not linked at all
                els.googleBtn.style.background = "#333";
                els.googleBtnText.innerText = "Link Google Account";
            }
            els.googleBtn.disabled = false;
        }
    }
}

function updateProfileIcon() {
    // Check if user is logged in
    if (state.userEmail) {
        els.profileBtn.innerHTML = '<i class="fa-solid fa-user-check" style="color: #4CAF50;"></i>';
    } else {
        els.profileBtn.innerHTML = '<i class="fa-solid fa-user"></i>';
    }
}

// Alias function for Google link button visibility (uses updateDashboardUI)
function updateGoogleLinkButtonVisibility() {
    updateDashboardUI();
}

function updateLicenseStatusUI() {
    const licenseArea = document.getElementById('license-status-area');
    const statusText = document.getElementById('license-status-text');
    const scansText = document.getElementById('scans-remaining-text');
    const expiryText = document.getElementById('license-expiry-text');
    const upgradeBtn = document.getElementById('btn-upgrade-license');

    // Only show for single users
    if (state.userType !== 'single' || !state.licenseStatus) {
        if (licenseArea) licenseArea.classList.add('hidden');
        return;
    }

    if (licenseArea) licenseArea.classList.remove('hidden');

    // Update status text
    if (state.licenseStatus === 'valid') {
        statusText.innerHTML = '<span style="color: #4CAF50;"><i class="fa-solid fa-circle-check"></i> Licensed Account</span>';
        scansText.innerHTML = `<span style="color: #fff;">Scans: <strong>Unlimited</strong></span>`;
        if (upgradeBtn) upgradeBtn.classList.add('hidden');

        if (state.licenseExpiresAt && expiryText) {
            const expiry = new Date(state.licenseExpiresAt);
            expiryText.innerHTML = `Expires: ${expiry.toLocaleDateString()}`;
        }
    } else if (state.licenseStatus === 'expired') {
        statusText.innerHTML = '<span style="color: #FF9800;"><i class="fa-solid fa-exclamation-triangle"></i> License Expired</span>';
        scansText.innerHTML = `<span style="color: #FF9800;">Free scans remaining: <strong>${state.scansRemaining}/4</strong></span>`;
        if (upgradeBtn) upgradeBtn.classList.remove('hidden');

        if (state.licenseExpiresAt && expiryText) {
            const expiry = new Date(state.licenseExpiresAt);
            expiryText.innerHTML = `Expired on: ${expiry.toLocaleDateString()}`;
        }
    } else {
        // No license
        statusText.innerHTML = '<span style="color: #888;"><i class="fa-solid fa-info-circle"></i> Unlicensed Account</span>';
        scansText.innerHTML = `<span style="color: #FFC107;">Free scans remaining: <strong>${state.scansRemaining}/4</strong></span>`;
        if (upgradeBtn) upgradeBtn.classList.remove('hidden');
        if (expiryText) expiryText.innerHTML = '';
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
    const password = els.passInp.value;

    if (state.isLoginView) {
        // LOGIN FLOW - Use email as identifier
        const identifier = els.identifierInp.value;
        if (!identifier || !password) {
            els.authError.innerText = "Please fill in both email and password.";
            return;
        }
        els.authBtn.innerText = "Processing...";
        els.authError.innerText = "";

        try {
            // Initiate OTP login
            const res = await fetch('/api/login/initiate', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ identifier, password })
            });

            if (res.status === 401) {
                throw new Error("Incorrect email or password.");
            }
            if (res.status === 403) {
                throw new Error("Account deactivated. Contact your administrator.");
            }
            if (!res.ok) throw new Error("Login failed. Please try again.");

            const data = await res.json();

            // Store session info for OTP flow
            state.loginSessionToken = data.session_token;
            state.pendingUserType = data.user_type;
            state.pendingIdentifier = identifier;
            state.pendingPassword = password;
            state.requiresPasswordChange = data.requires_password_change || false;

            // Handle OTP sent status
            if (data.status === 'otp_sent') {
                // Show OTP verification screen
                els.otpEmailDisplay.innerText = data.otp_sent_to;
                els.otpInp.value = '';
                els.otpError.innerText = '';
                closeOverlay(els.authOverlay);
                openOverlay(els.otpOverlay);
            }

        } catch (e) {
            els.authError.innerText = e.message;
        } finally {
            els.authBtn.innerText = "Login";
        }
    } else {
        // REGISTRATION FLOW - Requires email only
        const email = els.identifierInp.value;

        if (!email || !password) {
            els.authError.innerText = "Please fill in email and password.";
            return;
        }
        els.authBtn.innerText = "Processing...";
        els.authError.innerText = "";

        try {
            const res = await fetch('/api/register', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            const data = await res.json();
            if (res.status === 400) throw new Error(data.detail || "Registration failed.");
            if (!res.ok) throw new Error("Registration failed.");

            // Show registration notice
            const noticeMessage = data.notice || "Account created successfully! Please login.";
            showAlert("Account Created", noticeMessage);
            els.authToggle.click();
        } catch (e) {
            els.authError.innerText = e.message;
        } finally {
            els.authBtn.innerText = state.isLoginView ? "Login" : "Sign Up";
        }
    }
}

// OTP Verification
async function verifyOTP() {
    const otpCode = els.otpInp.value.trim();

    if (!otpCode || otpCode.length !== 6) {
        els.otpError.innerText = "Please enter a 6-digit code.";
        return;
    }

    els.verifyOtpBtn.innerText = "Verifying...";
    els.otpError.innerText = "";

    try {
        const res = await fetch('/api/login/verify-otp', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_token: state.loginSessionToken,
                otp_code: otpCode
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Verification failed.");

        // Login successful
        state.token = data.access_token;
        localStorage.setItem('access_token', state.token);
        state.userType = data.user_type || 'single';
        state.requiresPasswordChange = data.requires_password_change || false;

        closeOverlay(els.otpOverlay);

        // Check if password change is required
        if (state.requiresPasswordChange) {
            openOverlay(els.changePasswordOverlay);
        } else {
            await checkSessionAndRecovery();
        }

    } catch (e) {
        els.otpError.innerText = e.message;
    } finally {
        els.verifyOtpBtn.innerText = "Verify";
    }
}

// Resend OTP
async function resendOTP() {
    els.resendOtpBtn.innerText = "Sending...";
    els.otpError.innerText = "";

    try {
        const res = await fetch(`/api/login/resend-otp?session_token=${state.loginSessionToken}`, {
            method: 'POST'
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to resend code.");

        els.otpEmailDisplay.innerText = data.otp_sent_to;
        els.otpError.style.color = '#4CAF50';
        els.otpError.innerText = "New code sent!";
        setTimeout(() => {
            els.otpError.style.color = '';
            els.otpError.innerText = '';
        }, 3000);

    } catch (e) {
        els.otpError.innerText = e.message;
    } finally {
        els.resendOtpBtn.innerText = "Resend Code";
    }
}

// Set username (migration)
// Request password reset
async function requestPasswordReset() {
    const email = els.resetEmailInp.value.trim();

    if (!email) {
        els.resetMessage.innerText = "Please enter your email.";
        return;
    }

    els.resetPasswordBtn.innerText = "Sending...";
    els.resetMessage.innerText = "";

    try {
        const res = await fetch('/api/password/reset-request', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });

        const data = await res.json();

        // Always show success to prevent email enumeration
        els.resetMessage.style.color = '#4CAF50';
        els.resetMessage.innerText = "If this email is registered, a new password has been sent.";

        setTimeout(() => {
            closeOverlay(els.passwordResetOverlay);
            els.resetMessage.style.color = '';
            els.resetMessage.innerText = '';
            els.resetEmailInp.value = '';
        }, 3000);

    } catch (e) {
        els.resetMessage.innerText = "Failed to send reset email. Please try again.";
    } finally {
        els.resetPasswordBtn.innerText = "Send New Password";
    }
}

// Change password
async function changePassword() {
    const currentPassword = els.currentPasswordInp.value;
    const newPassword = els.newPasswordInp.value;
    const confirmPassword = els.confirmPasswordInp.value;

    if (!currentPassword || !newPassword || !confirmPassword) {
        els.changePasswordError.innerText = "Please fill in all fields.";
        return;
    }

    if (newPassword.length < 6) {
        els.changePasswordError.innerText = "New password must be at least 6 characters.";
        return;
    }

    if (newPassword !== confirmPassword) {
        els.changePasswordError.innerText = "New passwords do not match.";
        return;
    }

    els.changePasswordBtn.innerText = "Changing...";
    els.changePasswordError.innerText = "";

    try {
        const res = await fetch(`/api/user/change-password?token=${state.token}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to change password.");

        // Success - clear token and show login
        localStorage.removeItem('access_token');
        state.token = null;
        state.userEmail = null;
        state.username = null;
        state.userType = 'single';

        closeOverlay(els.changePasswordOverlay);
        showAlert("Password Changed", "Your password has been changed. Please login with your new password.");
        openOverlay(els.authOverlay);

        // Clear inputs
        els.currentPasswordInp.value = '';
        els.newPasswordInp.value = '';
        els.confirmPasswordInp.value = '';

    } catch (e) {
        els.changePasswordError.innerText = e.message;
    } finally {
        els.changePasswordBtn.innerText = "Change Password";
    }
}

// Legacy performLogin (keeping for backward compatibility if needed)
async function performLogin(email, password) {
    els.authBtn.innerText = "Processing...";
    els.authError.innerText = "";

    try {
        const res = await fetch('/api/login', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        if (!res.ok) throw new Error("Login failed. Please try again.");

        const data = await res.json();
        state.token = data.access_token;
        localStorage.setItem('access_token', state.token);

        await checkSessionAndRecovery();
        closeOverlay(els.authOverlay);
        els.emailInp.value = "";
        els.passInp.value = "";

    } catch (e) {
        els.authError.innerText = e.message;
    } finally {
        els.authBtn.innerText = "Login";
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

    if (!els.resFields.name.value && data.raw_text) {
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
        els.btnCreateTpl.innerText = `Create New Template (${data.count})`;
        els.btnCreateTpl.disabled = false; // No more limit

        renderTemplates(data.templates);
        closeOverlay(els.dashOverlay);
        openOverlay(els.emailSettingsOverlay);
    } catch (e) {
        showAlert("Error", friendlyError(e));
    } finally {
        hideSpinner();
    }
}

function renderTemplates(templates) {
    els.templatesList.innerHTML = "";
    if (templates.length === 0) {
        els.templatesList.innerHTML = "<p style='text-align:center; padding:20px; color:#666;'>No templates yet.</p>";
        return;
    }

    templates.forEach(t => {
        const isActive = t.active === 'TRUE';
        const div = document.createElement('div');
        div.className = `template-card ${isActive ? 'active' : ''}`;

        // Escape HTML for display to prevent broken rendering
        const safeSubject = t.subject.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        const safeBody = t.body.replace(/</g, '&lt;').replace(/>/g, '&gt;');

        div.innerHTML = `
            <div class="template-header"><h4>${safeSubject}</h4><span class="status-indicator">${isActive ? 'ACTIVE' : 'INACTIVE'}</span></div>
            <p>${safeBody}</p>
            <div class="template-actions">
                <button class="action-btn btn-edit" data-row-id="${t.row_id}">Edit</button>
                <button class="action-btn btn-activate" data-row-id="${t.row_id}" data-active="${isActive}" title="${isActive ? 'Deactivate this template' : 'Activate this template (deactivates others)'}">${isActive ? 'Deactivate' : 'Activate'}</button>
            </div>
        `;

        // Add event listeners for buttons
        const editBtn = div.querySelector('.btn-edit');
        const activateBtn = div.querySelector('.btn-activate');

        if (editBtn) {
            editBtn.addEventListener('click', (e) => {
                console.log('Edit button clicked!', { rowId: t.row_id, subject: t.subject });
                e.stopPropagation(); // Prevent card toggle
                e.preventDefault(); // Prevent any default behavior
                window.openEditMode(t.row_id, t.subject, t.body);
            });
        } else {
            console.error('Edit button not found!');
        }

        if (activateBtn) {
            activateBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent card toggle
                window.toggleTemplateActive(t.row_id, !isActive);
            });
        }

        div.addEventListener('click', (e) => { if (e.target.tagName !== 'BUTTON') div.classList.toggle('expanded'); });
        els.templatesList.appendChild(div);
    });
}

window.openEditMode = function (rowId, subject, body, attachments) {
    console.log('openEditMode called with:', { rowId, subject, body });
    try {
        state.editingTemplateId = rowId;
        state.attachedFiles = [];
        els.inpTplSubject.value = subject;
        els.inpTplBody.value = body.replace(/\\n/g, '\n');

        // TODO: Load existing attachments from the template
        // For now, we just reset. Existing attachments would need to be converted back from base64 to File objects
        // which is complex. Users can re-upload files when editing.

        renderAttachedFiles();
        document.querySelector('#view-template-editor h2').innerText = "Edit Template";
        console.log('About to open overlay');
        openOverlay(els.tplEditorOverlay);
        console.log('Overlay opened successfully');
    } catch (error) {
        console.error('Error in openEditMode:', error);
        alert('Error opening edit mode: ' + error.message);
    }
}

window.toggleTemplateActive = async function (rowId, shouldBeActive) {
    showSpinner("Updating...");
    try {
        const res = await fetch(`/api/email/templates/${rowId}/activate?token=${state.token}&active=${shouldBeActive}`, { method: 'POST' });
        if (handleGoogleError(res)) return;

        const data = await res.json();

        // Show message if email was auto-disabled
        if (data.email_auto_disabled) {
            showAlert("Email Auto-Disabled", "Auto-email has been disabled because no active templates remain. Activate a template to re-enable auto-email.");
        }

        openEmailSettings();
    } catch (e) {
        showAlert("Update Failed", "Could not update template status. " + friendlyError(e));
    } finally {
        hideSpinner();
    }
}

async function saveTemplate() {
    const subject = els.inpTplSubject.value;
    const body = els.inpTplBody.value;
    if (!subject || !body) {
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

        // Prepare the payload
        const payload = { subject, body };

        // Add attachments if present
        if (state.attachedFiles && state.attachedFiles.length > 0) {
            // Convert all files to base64
            const attachmentsData = await Promise.all(
                state.attachedFiles.map(async (file) => ({
                    filename: file.name,
                    data: await fileToBase64(file),
                    size: file.size
                }))
            );
            payload.attachments = attachmentsData;
        }

        const res = await fetch(url, {
            method: method, headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (handleGoogleError(res)) return;

        if (!res.ok) {
            const txt = await res.text();
            throw new Error(txt);
        }
        closeOverlay(els.tplEditorOverlay);
        openEmailSettings();
    } catch (e) {
        showAlert("Save Failed", "Could not save template. " + friendlyError(e));
    } finally {
        els.btnSaveTpl.innerText = "Save Template";
    }
}

// ==========================================
// FILE ATTACHMENT HANDLERS
// ==========================================

function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    if (!files || files.length === 0) return;

    // Initialize attachedFiles array if not exists
    if (!state.attachedFiles) {
        state.attachedFiles = [];
    }

    // Calculate current total size
    const currentTotalSize = state.attachedFiles.reduce((sum, f) => sum + f.size, 0);
    const newFilesSize = files.reduce((sum, f) => sum + f.size, 0);
    const totalSize = currentTotalSize + newFilesSize;

    // Check total size (20 MB = 20 * 1024 * 1024 bytes)
    const maxSize = 20 * 1024 * 1024;
    if (totalSize > maxSize) {
        showAlert("Files Too Large", `Total file size would be ${(totalSize / 1024 / 1024).toFixed(2)} MB. Maximum allowed total size is 20 MB.`);
        els.tplAttachment.value = '';
        return;
    }

    // Add files to state
    state.attachedFiles.push(...files);

    // Update UI
    renderAttachedFiles();

    // Clear the input so same file can be selected again if needed
    els.tplAttachment.value = '';
}

function removeFile(index) {
    if (!state.attachedFiles) return;

    // Remove file at index
    state.attachedFiles.splice(index, 1);

    // Update UI
    renderAttachedFiles();
}

function renderAttachedFiles() {
    if (!state.attachedFiles || state.attachedFiles.length === 0) {
        els.attachedFilesList.classList.add('hidden');
        return;
    }

    // Show the attached files list
    els.attachedFilesList.classList.remove('hidden');

    // Calculate total size
    const totalSize = state.attachedFiles.reduce((sum, f) => sum + f.size, 0);
    els.totalSizeDisplay.textContent = `Total: ${formatFileSize(totalSize)} / 20 MB`;

    // Render each file
    els.filesContainer.innerHTML = '';
    state.attachedFiles.forEach((file, index) => {
        const fileDiv = document.createElement('div');
        fileDiv.style.cssText = 'display: flex; align-items: center; justify-content: space-between; padding: 8px; background: #0a0a0a; border-radius: 4px;';

        const fileInfo = document.createElement('div');
        fileInfo.style.cssText = 'display: flex; flex-direction: column; gap: 2px; flex: 1; min-width: 0;';

        const fileName = document.createElement('span');
        fileName.style.cssText = 'font-size: 12px; color: #fff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;';
        fileName.textContent = file.name;

        const fileSize = document.createElement('span');
        fileSize.style.cssText = 'font-size: 10px; color: #888;';
        fileSize.textContent = formatFileSize(file.size);

        fileInfo.appendChild(fileName);
        fileInfo.appendChild(fileSize);

        const removeBtn = document.createElement('button');
        removeBtn.style.cssText = 'background: rgba(255,68,68,0.2); border: none; color: #ff4444; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; margin-left: 8px;';
        removeBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
        removeBtn.onclick = () => removeFile(index);

        fileDiv.appendChild(fileInfo);
        fileDiv.appendChild(removeBtn);
        els.filesContainer.appendChild(fileDiv);
    });
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            // Remove the data URL prefix (e.g., "data:image/png;base64,")
            const base64 = reader.result.split(',')[1];
            resolve(base64);
        };
        reader.onerror = error => reject(error);
        reader.readAsDataURL(file);
    });
}

function escapeHtml(text) { return text.replace(/'/g, "&apos;").replace(/"/g, "&quot;").replace(/\n/g, "\\n"); }

function openOverlay(el) { el.classList.add('visible'); }
function closeOverlay(el) { el.classList.remove('visible'); }
function showSpinner(t) { if (els.spinnerText) els.spinnerText.innerText = t; els.spinner.classList.remove('hidden'); }
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

// ==========================================
// 14. ENTERPRISE ADMIN PANEL
// ==========================================

/**
 * Update dashboard UI based on user type
 * - Single user: Full dashboard
 * - Enterprise admin: Full dashboard + Admin Panel button
 * - Sub-account: Limited dashboard (logout only)
 */
function updateDashboardUIForUserType() {
    const badge = els.userTypeBadge;
    const adminBtn = els.btnOpenAdmin;
    const distributorBtn = els.btnOpenDistributor;
    const googleArea = els.googleStatusArea;
    const emailBtn = els.btnOpenEmail;
    const exportBtn = els.exportBtn;

    // Reset all - make everything visible by default
    if (badge) badge.classList.add('hidden');
    if (adminBtn) adminBtn.classList.add('hidden');
    if (distributorBtn) distributorBtn.classList.add('hidden');
    if (googleArea) googleArea.style.display = 'block';
    if (emailBtn) emailBtn.style.display = 'flex';
    if (exportBtn) exportBtn.style.display = 'flex';

    // Show distributor button if user has distributor role
    if (state.isDistributor && distributorBtn) {
        distributorBtn.classList.remove('hidden');
    }

    if (state.userType === 'enterprise_admin') {
        // Show admin badge
        if (badge) {
            badge.classList.remove('hidden');
            badge.classList.add('admin');
            badge.classList.remove('sub-account');
            badge.innerText = 'Enterprise Admin';
        }
        // Show admin panel button
        if (adminBtn) adminBtn.classList.remove('hidden');
        // Show all dashboard options (Google, Email, Export)

    } else if (state.userType === 'sub_account') {
        // Show sub-account badge
        if (badge) {
            badge.classList.remove('hidden');
            badge.classList.remove('admin');
            badge.classList.add('sub-account');
            badge.innerText = 'Sub-Account';
        }
        // Hide Google integration for sub-accounts
        if (googleArea) googleArea.style.display = 'none';
        // Hide email settings for sub-accounts
        if (emailBtn) emailBtn.style.display = 'none';
        // Hide export for sub-accounts
        if (exportBtn) exportBtn.style.display = 'none';

    } else {
        // Single user - show everything normally (already set above)
    }
}

// Open Admin Panel
async function openAdminPanel() {
    showSpinner("Loading...");
    try {
        // Fetch license info
        const licenseRes = await fetch(`/api/admin/license?token=${state.token}`);
        if (!licenseRes.ok) throw new Error("Failed to load license info");
        const licenseData = await licenseRes.json();

        if (els.licenseKeyDisplay) els.licenseKeyDisplay.innerText = licenseData.license_key;
        if (els.subAccountCount) els.subAccountCount.innerText = `${licenseData.current_sub_accounts}/${licenseData.max_sub_accounts} seats`;

        // Update create button state
        if (els.btnCreateSub) {
            els.btnCreateSub.disabled = licenseData.current_sub_accounts >= licenseData.max_sub_accounts;
            els.btnCreateSub.innerText = licenseData.current_sub_accounts >= licenseData.max_sub_accounts
                ? 'License Limit Reached'
                : 'Create Sub-Account';
        }

        // Fetch sub-accounts
        const subsRes = await fetch(`/api/admin/sub-accounts?token=${state.token}`);
        if (!subsRes.ok) throw new Error("Failed to load sub-accounts");
        const subsData = await subsRes.json();

        renderSubAccounts(subsData.sub_accounts);

        closeOverlay(els.dashOverlay);
        openOverlay(els.adminPanelOverlay);
    } catch (e) {
        showAlert("Error", friendlyError(e));
    } finally {
        hideSpinner();
    }
}

async function renderSubAccounts(subAccounts) {
    if (!els.subAccountsList) return;

    if (subAccounts.length === 0) {
        els.subAccountsList.innerHTML = '<p style="text-align:center; color:#666; padding:20px;">No sub-accounts yet.</p>';
        return;
    }

    // Fetch available templates if admin has Google connected
    let templates = [];
    if (state.isGoogleConnected) {
        try {
            const res = await fetch(`/api/email/settings?token=${state.token}`);
            if (res.ok) {
                const data = await res.json();
                templates = data.templates || [];
            }
        } catch (e) {
            console.log("Could not fetch templates:", e);
        }
    }

    els.subAccountsList.innerHTML = subAccounts.map(sub => {
        // Build template dropdown options
        let templateOptions = '<option value="none">No Auto-Email</option>';
        templates.forEach(t => {
            const selected = sub.assigned_template_id === t.id ? 'selected' : '';
            templateOptions += `<option value="${t.id}" ${selected}>${escapeHtml(t.subject)}</option>`;
        });

        return `
        <div class="sub-account-card ${sub.is_active ? '' : 'inactive'}">
            <div class="sub-account-info">
                <span class="username">${escapeHtml(sub.email)}</span>
                <span class="status ${sub.is_logged_in ? 'online' : ''}">
                    ${sub.is_active ? (sub.is_logged_in ? 'Online' : 'Offline') : 'Deactivated'}
                </span>
            </div>
            <div class="sub-account-template">
                <label style="font-size: 12px; color: #888; margin-bottom: 4px;">Auto-Email Template:</label>
                <select class="template-dropdown" onchange="assignTemplate(${sub.id}, this.value)">
                    ${templateOptions}
                </select>
            </div>
            <div class="sub-account-actions">
                <button class="sub-action-btn export" onclick="exportSubAccount(${sub.id}, '${escapeHtml(sub.email)}')" title="Export Contacts">
                    <i class="fa-solid fa-download"></i> Export
                </button>
                <button class="sub-action-btn toggle ${sub.is_active ? '' : 'off'}" onclick="toggleSubAccount(${sub.id}, ${!sub.is_active})" title="${sub.is_active ? 'Deactivate' : 'Activate'}">
                    <i class="fa-solid ${sub.is_active ? 'fa-toggle-on' : 'fa-toggle-off'}"></i>
                </button>
                <button class="sub-action-btn edit" onclick="openEditSubAccount(${sub.id}, '${escapeHtml(sub.email)}')" title="Edit">
                    <i class="fa-solid fa-pen"></i>
                </button>
            </div>
        </div>
        `;
    }).join('');
}

// Toggle sub-account active status
window.toggleSubAccount = async function (subId, shouldBeActive) {
    showSpinner("Updating...");
    try {
        const res = await fetch(`/api/admin/sub-accounts/${subId}/toggle?token=${state.token}&active=${shouldBeActive}`, {
            method: 'POST'
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to update");
        }
        // Refresh the panel
        await openAdminPanel();
    } catch (e) {
        showAlert("Error", friendlyError(e));
    } finally {
        hideSpinner();
    }
};

// Open create sub-account form
function openCreateSubAccount() {
    state.editingSubAccountId = null;
    if (els.subEditorTitle) els.subEditorTitle.innerText = "New Sub-Account";
    if (els.subUsername) els.subUsername.value = "";
    if (els.subPassword) els.subPassword.value = "";
    if (els.btnSaveSub) els.btnSaveSub.innerText = "Create Sub-Account";
    openOverlay(els.subEditorOverlay);
}

// Open edit sub-account form
window.openEditSubAccount = function (subId, email) {
    state.editingSubAccountId = subId;
    if (els.subEditorTitle) els.subEditorTitle.innerText = "Edit Sub-Account";
    if (els.subUsername) els.subUsername.value = email;
    if (els.subPassword) els.subPassword.value = "";
    if (els.subPassword) els.subPassword.placeholder = "Leave blank to keep current";
    if (els.btnSaveSub) els.btnSaveSub.innerText = "Save Changes";
    openOverlay(els.subEditorOverlay);
};

// Save sub-account (create or update)
async function saveSubAccount() {
    const email = els.subUsername?.value?.trim();
    const password = els.subPassword?.value;

    if (!email || email.length < 3) {
        showAlert("Invalid Email/Username", "Email/Username must be at least 3 characters.");
        return;
    }

    if (!state.editingSubAccountId && (!password || password.length < 6)) {
        showAlert("Invalid Password", "Password must be at least 6 characters.");
        return;
    }

    if (els.btnSaveSub) els.btnSaveSub.innerText = "Saving...";

    try {
        let url, method, body;

        if (state.editingSubAccountId) {
            // Update existing
            url = `/api/admin/sub-accounts/${state.editingSubAccountId}?token=${state.token}`;
            method = 'PUT';
            body = { email };
            if (password) body.password = password;
        } else {
            // Create new
            url = `/api/admin/sub-accounts?token=${state.token}`;
            method = 'POST';
            body = { email, password };
        }

        const res = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to save");
        }

        closeOverlay(els.subEditorOverlay);
        await openAdminPanel();

    } catch (e) {
        showAlert("Save Failed", e.message);
    } finally {
        if (els.btnSaveSub) els.btnSaveSub.innerText = state.editingSubAccountId ? "Save Changes" : "Create Sub-Account";
    }
}

// Assign template to sub-account
window.assignTemplate = async function (subId, templateId) {
    showSpinner("Assigning Template...");
    try {
        const res = await fetch(`/api/admin/sub-accounts/${subId}/assign-template?token=${state.token}&template_id=${templateId}`, {
            method: 'POST'
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to assign template");
        }
        showAlert("Success", "Template assigned successfully!");
    } catch (e) {
        showAlert("Error", friendlyError(e));
    } finally {
        hideSpinner();
    }
};

// Open expand seats modal
async function openExpandSeats() {
    try {
        // Fetch current license info
        const licenseRes = await fetch(`/api/admin/license?token=${state.token}`);
        if (!licenseRes.ok) throw new Error("Failed to load license info");
        const licenseData = await licenseRes.json();

        // Populate current usage info
        if (els.currentMaxSeats) els.currentMaxSeats.innerText = licenseData.max_sub_accounts;
        if (els.currentUsedSeats) els.currentUsedSeats.innerText = licenseData.current_sub_accounts;

        // Reset input to default value
        if (els.seatsToAdd) els.seatsToAdd.value = 5;

        // Update preview
        updateSeatsPreview();

        // Open the modal
        openOverlay(els.expandSeatsOverlay);
    } catch (e) {
        showAlert("Error", friendlyError(e));
    }
}

// Update seats preview
function updateSeatsPreview() {
    const currentMax = parseInt(els.currentMaxSeats?.innerText || 0);
    const seatsToAdd = parseInt(els.seatsToAdd?.value || 0);
    const newMax = currentMax + seatsToAdd;

    if (els.newMaxSeatsPreview) {
        els.newMaxSeatsPreview.innerText = newMax;
    }
}

// Confirm seat expansion purchase
async function confirmExpandSeats() {
    const seatsToAdd = parseInt(els.seatsToAdd?.value || 0);

    if (seatsToAdd <= 0) {
        showAlert("Invalid Input", "Please enter a valid number of seats to add (minimum 1).");
        return;
    }

    if (els.btnConfirmExpandSeats) els.btnConfirmExpandSeats.innerText = "Processing...";

    try {
        const res = await fetch(`/api/admin/expand-seats?token=${state.token}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ additional_seats: seatsToAdd })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to expand seats");
        }

        const data = await res.json();

        // Close the modal
        closeOverlay(els.expandSeatsOverlay);

        // Show success message
        showAlert("Success!", `Successfully added ${seatsToAdd} seats to your license!\n\nNew total: ${data.new_max} seats\nAvailable: ${data.available_seats} seats`);

        // Refresh the admin panel to show updated info
        await openAdminPanel();
    } catch (e) {
        showAlert("Purchase Failed", friendlyError(e));
    } finally {
        if (els.btnConfirmExpandSeats) els.btnConfirmExpandSeats.innerText = "Confirm Purchase";
    }
}

// Export sub-account contacts
window.exportSubAccount = async function (subId, username) {
    showSpinner("Exporting...");
    try {
        const res = await fetch(`/api/admin/export/sub-account/${subId}?token=${state.token}`);
        if (handleGoogleError(res)) return;

        if (res.status === 400) {
            showAlert("Google Not Connected", "Please link your Google Account in the Dashboard to use export features.");
            return;
        }

        if (res.status === 404) {
            showAlert("No Data", "This sub-account hasn't scanned any contacts yet.");
            return;
        }

        if (!res.ok) throw new Error("Export failed");

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `SubAccount_${username}_Contacts.xlsx`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

    } catch (e) {
        showAlert("Export Failed", friendlyError(e));
    } finally {
        hideSpinner();
    }
};

// Export admin's own contacts
async function exportMyContacts() {
    showSpinner("Exporting...");
    try {
        const res = await fetch(`/api/admin/export/my-contacts?token=${state.token}`);
        if (handleGoogleError(res)) return;

        if (res.status === 400) {
            showAlert("Google Not Connected", "Please link your Google Account in the Dashboard to use export features.");
            return;
        }

        if (!res.ok) throw new Error("Export failed");

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = "My_Contacts.xlsx";
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

    } catch (e) {
        showAlert("Export Failed", friendlyError(e));
    } finally {
        hideSpinner();
    }
}

// Export all contacts combined (admin + all sub-accounts)
async function exportAllCombined() {
    showSpinner("Exporting All...");
    try {
        const res = await fetch(`/api/admin/export/all-combined?token=${state.token}`);
        if (handleGoogleError(res)) return;

        if (res.status === 400) {
            showAlert("Google Not Connected", "Please link your Google Account in the Dashboard to use export features.");
            return;
        }

        if (!res.ok) throw new Error("Export failed");

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = "DigiCard_Combined_All_Users.xlsx";
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

    } catch (e) {
        showAlert("Export Failed", friendlyError(e));
    } finally {
        hideSpinner();
    }
}

// ==========================================
// DISTRIBUTOR DASHBOARD FUNCTIONS
// ==========================================

// Open Distributor Dashboard
async function openDistributorDashboard() {
    showSpinner("Loading Distributor Dashboard...");
    try {
        const res = await fetch(`/api/distributor/dashboard?token=${state.token}`);

        if (!res.ok) {
            if (res.status === 403) {
                showAlert("Access Denied", "You don't have distributor access.");
                return;
            }
            throw new Error("Failed to load distributor dashboard");
        }

        const data = await res.json();

        // Update stats - showing accounts created instead of license inventory
        if (els.singleTotal) els.singleTotal.innerText = data.single.total;
        if (document.getElementById('single-this-month'))
            document.getElementById('single-this-month').innerText = data.single.this_month;
        if (els.enterpriseTotal) els.enterpriseTotal.innerText = data.enterprise.total;
        if (document.getElementById('enterprise-this-month'))
            document.getElementById('enterprise-this-month').innerText = data.enterprise.this_month;
        if (document.getElementById('monthly-total-created'))
            document.getElementById('monthly-total-created').innerText = data.monthly.total_created;

        closeOverlay(els.dashOverlay);
        openOverlay(els.distributorOverlay);

    } catch (e) {
        showAlert("Error", friendlyError(e));
    } finally {
        hideSpinner();
    }
}

// REMOVED: Purchase licenses functionality (no longer needed with direct account creation)
// Licenses are now generated on-the-fly when creating accounts

// Create Single Login Account
async function createSingleAccount() {
    const email = els.distSingleEmail.value.trim();

    if (!email) {
        showAlert("Missing Information", "Please fill in email.");
        return;
    }

    showSpinner("Creating Single Login Account...");
    try {
        const res = await fetch(`/api/distributor/create-account?token=${state.token}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                account_type: "single",
                email: email
                // password is auto-generated
            })
        });

        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || "Account creation failed");
        }

        const data = await res.json();

        // Display appropriate message based on whether account was converted or created
        let alertTitle = "Success";
        let alertMessage = "";

        if (data.converted) {
            alertTitle = "Account Converted";
            alertMessage = `Free trial account successfully converted to licensed account!\n\nEmail: ${data.email}\nLicense: ${data.license_key}\n\nNew credentials sent to ${data.email}`;
        } else if (data.upgraded) {
            alertTitle = "Account Upgraded";
            alertMessage = `Account upgraded!\n\nEmail: ${data.email}\nLicense: ${data.license_key}\n\nCredentials sent to ${data.email}`;
        } else {
            alertMessage = `Account created!\n\nEmail: ${data.email}\nLicense: ${data.license_key}\n\nCredentials sent to ${data.email}`;
        }

        showAlert(alertTitle, alertMessage);

        // Reset form
        els.distSingleEmail.value = '';

        // Refresh dashboard
        await openDistributorDashboard();

    } catch (e) {
        showAlert("Account Creation Failed", friendlyError(e));
    } finally {
        hideSpinner();
    }
}

// Create Enterprise Account
async function createEnterpriseAccount() {
    const email = els.distEntEmail.value.trim();

    if (!email) {
        showAlert("Missing Information", "Please fill in email.");
        return;
    }

    // Basic email validation
    if (!email.includes('@') || !email.includes('.')) {
        showAlert("Invalid Email", "Please enter a valid email address.");
        return;
    }

    showSpinner("Creating Enterprise Account...");
    try {
        const res = await fetch(`/api/distributor/create-account?token=${state.token}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                account_type: "enterprise",
                email: email
                // password is auto-generated
            })
        });

        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || "Account creation failed");
        }

        const data = await res.json();

        // Display appropriate message based on whether account was converted or created
        let alertTitle = "Success";
        let alertMessage = "";

        if (data.converted) {
            alertTitle = "Account Converted";
            alertMessage = `Free trial account successfully converted to licensed enterprise account!\n\nEmail: ${data.email}\nLicense: ${data.license_key}\n\nNew credentials sent to ${data.email}`;
        } else if (data.upgraded) {
            alertTitle = "Account Upgraded";
            alertMessage = `Enterprise account upgraded!\n\nEmail: ${data.email}\nLicense: ${data.license_key}\n\nCredentials sent to ${data.email}`;
        } else {
            alertMessage = `Enterprise account created!\n\nEmail: ${data.email}\nLicense: ${data.license_key}\n\nCredentials sent to ${data.email}`;
        }

        showAlert(alertTitle, alertMessage);

        // Reset form
        els.distEntEmail.value = '';

        // Refresh dashboard
        await openDistributorDashboard();

    } catch (e) {
        showAlert("Account Creation Failed", friendlyError(e));
    } finally {
        hideSpinner();
    }
}

// Setup admin panel event listeners
function setupAdminEventListeners() {
    if (els.btnOpenAdmin) {
        els.btnOpenAdmin.addEventListener('click', openAdminPanel);
    }

    if (els.btnBackAdmin) {
        els.btnBackAdmin.addEventListener('click', () => {
            closeOverlay(els.adminPanelOverlay);
            openOverlay(els.dashOverlay);
        });
    }

    if (els.btnCreateSub) {
        els.btnCreateSub.addEventListener('click', openCreateSubAccount);
    }

    if (els.btnSaveSub) {
        els.btnSaveSub.addEventListener('click', saveSubAccount);
    }

    // Expand seats button
    if (els.btnExpandSeats) {
        els.btnExpandSeats.addEventListener('click', openExpandSeats);
    }

    if (els.btnConfirmExpandSeats) {
        els.btnConfirmExpandSeats.addEventListener('click', confirmExpandSeats);
    }

    // Update preview when seats input changes
    if (els.seatsToAdd) {
        els.seatsToAdd.addEventListener('input', updateSeatsPreview);
    }

    // Export button
    const btnExportAll = document.getElementById('btn-export-all-combined');
    if (btnExportAll) {
        btnExportAll.addEventListener('click', exportAllCombined);
    }
}

// Initialize admin listeners on page load
document.addEventListener('DOMContentLoaded', setupAdminEventListeners);

// Setup distributor dashboard event listeners
function setupDistributorEventListeners() {
    // Open distributor dashboard
    if (els.btnOpenDistributor) {
        els.btnOpenDistributor.addEventListener('click', openDistributorDashboard);
    }

    // Back button from distributor dashboard
    if (els.btnBackDistributor) {
        els.btnBackDistributor.addEventListener('click', () => {
            closeOverlay(els.distributorOverlay);
            openOverlay(els.dashOverlay);
        });
    }

    // REMOVED: Purchase licenses button event listeners (no longer needed)

    // Account type toggle buttons
    const accountTypeBtns = document.querySelectorAll('.account-type-btn');
    accountTypeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active from all
            accountTypeBtns.forEach(b => b.classList.remove('active'));
            // Add active to clicked
            btn.classList.add('active');

            const type = btn.dataset.type;
            const singleForm = document.getElementById('single-account-form');
            const enterpriseForm = document.getElementById('enterprise-account-form');

            if (type === 'single') {
                singleForm.classList.remove('hidden');
                enterpriseForm.classList.add('hidden');
            } else {
                singleForm.classList.add('hidden');
                enterpriseForm.classList.remove('hidden');
            }
        });
    });

    // Create account buttons
    if (els.btnCreateSingle) {
        els.btnCreateSingle.addEventListener('click', createSingleAccount);
    }

    if (els.btnCreateEnterprise) {
        els.btnCreateEnterprise.addEventListener('click', createEnterpriseAccount);
    }
}

// Initialize distributor listeners on page load
document.addEventListener('DOMContentLoaded', setupDistributorEventListeners);