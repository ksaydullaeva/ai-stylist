import React, { useState, useEffect } from 'react';
import { api } from '../api';

const PersonIcon = () => (
    <svg className="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
    </svg>
);

const ChangeIcon = () => (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
        <path d="M3 3v5h5" />
    </svg>
);

export default function StudioPage({
    preview,
    userPhotoPreview,
    userPhoto,
    onFileChange,
    onUserPhotoChange,
    onRemoveItem,
    onRemoveUserPhoto,
    runPipeline,
    loading,
    file,
    error
}) {
    const hasItem = !!file;
    const hasModel = !!userPhoto;
    const [itemStepConfirmed, setItemStepConfirmed] = useState(false);
    /** User must confirm full-body preview before we run step 3 (API validation). */
    const [fullBodyConfirmed, setFullBodyConfirmed] = useState(false);

    const [validatingItem, setValidatingItem] = useState(false);
    const [validatingUser, setValidatingUser] = useState(false);
    const validating = validatingItem || validatingUser;

    const [itemValidation, setItemValidation] = useState(null);
    const [userValidation, setUserValidation] = useState(null);

    // Reset validations when the corresponding upload changes
    useEffect(() => {
        setItemValidation(null);
        setItemStepConfirmed(false);
    }, [file]);

    useEffect(() => {
        setUserValidation(null);
    }, [userPhoto]);

    useEffect(() => {
        setFullBodyConfirmed(false);
    }, [file, userPhoto]);

    // Step 1 validation only (runs only when item + full-body photo exist).
    // Both setItemValidation and setValidatingItem are called inside the same
    // .then()/.catch() callback so React 18 batches them into one render —
    // preventing a window where validatedPair is true but validating is still true.
    useEffect(() => {
        if (!file || !userPhoto || !fullBodyConfirmed) return;
        if (validatingItem) return;
        setValidatingItem(true);
        api.validateItem(file)
            .then((res) => { setItemValidation(res); setValidatingItem(false); })
            .catch(() => {
                setItemValidation({
                    item_ok: false,
                    item_error: 'validation_failed',
                    item_message: 'Validation failed.',
                });
                setValidatingItem(false);
            });
    }, [file, userPhoto, fullBodyConfirmed]);

    // Step 2 validation only (runs when the full-body photo changes).
    useEffect(() => {
        if (!userPhoto || !fullBodyConfirmed) return;
        if (validatingUser) return;
        setValidatingUser(true);
        api.validateUserPhoto(userPhoto)
            .then((res) => { setUserValidation(res); setValidatingUser(false); })
            .catch(() => {
                setUserValidation({
                    user_ok: false,
                    user_error: 'validation_failed',
                    user_message: 'Validation failed.',
                });
                setValidatingUser(false);
            });
    }, [userPhoto, fullBodyConfirmed]);

    const handleSkip = async () => {
        if (!file || validating) return;
        setValidatingItem(true);
        try {
            await api.analyze(file);
            setItemValidation({ item_ok: true, item_message: null });
            runPipeline();
        } catch (err) {
            setItemValidation({
                item_ok: false,
                item_error: 'analysis_failed',
                item_message: err?.message || 'The image does not appear to contain a clothing item.'
            });
        } finally {
            setValidatingItem(false);
        }
    };

    const validatedItem = itemValidation && itemValidation.item_ok;
    const validatedUser = userValidation && userValidation.user_ok;
    const validatedPair = hasItem && hasModel && validatedItem && validatedUser;

    const itemFailedNoModel = itemValidation && !itemValidation.item_ok;
    const itemFailedPair = itemValidation && hasItem && hasModel && !itemValidation.item_ok;
    const userFailedPair = userValidation && hasItem && hasModel && !userValidation.user_ok;
    const swapLikely = itemFailedPair && userFailedPair;
    const validationFailed = hasItem && hasModel && itemValidation && userValidation && !validatedPair;
    const showPairedPreview = hasItem && hasModel && validatedPair && !validating;
    const canCreate = hasItem && !validating && (!hasModel || validatedPair);
    const checkingDone = validatedPair;
    const activeStep = !hasItem
        ? 1
        : !itemStepConfirmed
          ? 1
          : !hasModel
            ? 2
            : !fullBodyConfirmed
              ? 2
              : validating || checkingDone
                ? 3
                : 2;

    // Each step is independently done based on its own data, not just activeStep position.
    // This means clicking "Change" on one step leaves the other steps' indicators untouched.
    // While validating, avoid showing step "done" checkmarks early (parallel async validations).
    // Only show "done" after validation completes for the relevant step.
    const step1Done =
        hasItem &&
        (!hasModel ? true : !fullBodyConfirmed ? true : !validating && !!itemValidation?.item_ok);
    const step3Done = checkingDone;
    // step2Done must be in sync with step3Done: if checking passed, step 2 is certainly done.
    // Deriving step2Done from checkingDone prevents a render where step3 shows ✓ but step2 still
    // shows the number (state variables for step2 settle in the same React batch as checkingDone).
    const step2Done =
        checkingDone ||
        (!hasModel && activeStep >= 3) ||
        (hasModel && fullBodyConfirmed && !validating && !!userValidation?.user_ok);

    return (
        <section className="studio-container studio-container-sequential tcm-studio-shell">
            <div className="tcm-studio-card">
                <div className="tcm-stepper">
                    <div className={`tcm-step ${(step1Done || activeStep >= 1) ? 'active' : ''} ${step1Done ? 'done' : ''}`}>
                        <span className="tcm-step-dot">{step1Done ? '✓' : '1'}</span>
                        <span>Clothing Item</span>
                    </div>
                    <div className={`tcm-step ${(step2Done || activeStep >= 2) ? 'active' : ''} ${step2Done ? 'done' : ''}`}>
                        <span className="tcm-step-dot">{step2Done ? '✓' : '2'}</span>
                        <span>Full-body Image</span>
                    </div>
                    <div className={`tcm-step ${(step3Done || activeStep >= 3) ? 'active' : ''} ${step3Done ? 'done' : ''}`}>
                        <span className="tcm-step-dot">{step3Done ? '✓' : '3'}</span>
                        <span>Checking</span>
                    </div>
                </div>

                {validating && hasItem && !hasModel && (
                    <div className="upload-validating tcm-checking-state">
                        <div className="upload-validating-icons">
                            <span className="upload-validating-icon upload-validating-icon-item">
                                <img className="upload-validating-icon-img" src="/icons/clothing-upload.png" alt="" />
                            </span>
                            <span className="upload-validating-icon upload-validating-icon-model">
                                <PersonIcon />
                            </span>
                        </div>
                        <span className="upload-validating-text">Checking your photos</span>
                        <span className="upload-validating-dots">...</span>
                        <div className="upload-validating-bar" />
                    </div>
                )}

                {validating && hasItem && hasModel && (
                    <div className="upload-validating tcm-checking-state">
                        <div className="upload-validating-icons">
                            <span className="upload-validating-icon upload-validating-icon-item">
                                <img className="upload-validating-icon-img" src="/icons/clothing-upload.png" alt="" />
                            </span>
                            <span className="upload-validating-icon upload-validating-icon-model">
                                <PersonIcon />
                            </span>
                        </div>
                        <span className="upload-validating-text">Checking your photos</span>
                        <span className="upload-validating-dots">...</span>
                        <div className="upload-validating-bar" />
                    </div>
                )}

                {/* Step 2 review: only the full-body upload (same single-card pattern as step 1). Next → checking (step 3). */}
                {!validating && !showPairedPreview && hasItem && hasModel && userPhotoPreview && !fullBodyConfirmed && (
                    <>
                        <div className="studio-image-block tcm-preview-card tcm-single-preview">
                            <div className="studio-image-wrap">
                                <img src={userPhotoPreview} alt="Your full-body photo" className="studio-image-img" />
                            </div>
                            <button type="button" className="upload-received-change tcm-change-btn" onClick={onRemoveUserPhoto}>
                                <ChangeIcon /> Change
                            </button>
                        </div>
                        <button
                            type="button"
                            className="btn-primary tcm-main-btn"
                            onClick={() => setFullBodyConfirmed(true)}
                            disabled={loading || validating}
                        >
                            Next
                        </button>
                    </>
                )}

                {/* After confirm: both previews when not in the active API check (pair shown here or on Create step after checks pass). */}
                {!validating && !showPairedPreview && hasItem && hasModel && preview && userPhotoPreview && fullBodyConfirmed && (
                    <div className="studio-images-side-by-side tcm-preview-grid">
                        <div className="studio-image-block tcm-preview-card">
                            <div className="studio-image-wrap">
                                <img src={preview} alt="Your item" className="studio-image-img" />
                            </div>
                            <button type="button" className="upload-received-change tcm-change-btn" onClick={onRemoveItem}>
                                <ChangeIcon /> Change
                            </button>
                        </div>
                        <div className="studio-image-block tcm-preview-card">
                            <div className="studio-image-wrap">
                                <img src={userPhotoPreview} alt="Your full-body photo" className="studio-image-img" />
                            </div>
                            <button type="button" className="upload-received-change tcm-change-btn" onClick={onRemoveUserPhoto}>
                                <ChangeIcon /> Change
                            </button>
                        </div>
                    </div>
                )}

                {!validating && !showPairedPreview && !hasItem && (
                    <>
                        <div className="dropzone tcm-dropzone" onClick={() => document.getElementById('item-input').click()}>
                            <input id="item-input" type="file" className="hidden" accept="image/*" onChange={onFileChange} />
                            <img className="dropzone-icon" src="/icons/clothing-upload.png" alt="" />
                            <span className="dropzone-text">Drop the item you want to style.</span>
                            <span className="tcm-dropzone-hint">
                                Upload a photo where only ONE garment is visible. Use a plain background, good lighting, and make sure the full garment is visible.
                            </span>
                            <span className="tcm-dropzone-hint">JPEG, JPG, and PNG formats, up to 5 MB</span>
                        </div>
                        <button className="btn-primary tcm-main-btn" type="button" disabled>
                            Next
                        </button>
                    </>
                )}

                {!validating && !showPairedPreview && hasItem && !hasModel && !itemStepConfirmed && (
                    <>
                        <div className="studio-image-block tcm-preview-card tcm-single-preview">
                            <div className="studio-image-wrap">
                                <img src={preview} alt="Your item" className="studio-image-img" />
                            </div>
                            <button type="button" className="upload-received-change tcm-change-btn" onClick={onRemoveItem}>
                                <ChangeIcon /> Change
                            </button>
                        </div>
                        <button
                            className="btn-primary tcm-main-btn"
                            type="button"
                            onClick={() => setItemStepConfirmed(true)}
                            disabled={loading || validating}
                        >
                            Next
                        </button>
                    </>
                )}

                {!validating && !showPairedPreview && hasItem && !hasModel && itemStepConfirmed && (
                    <>
                        {itemFailedNoModel && itemValidation?.item_message && (
                            <div className="banner error" style={{ width: '100%', marginBottom: 0 }}>{itemValidation.item_message}</div>
                        )}
                        {!itemFailedNoModel && (
                            <div className="dropzone tcm-dropzone" onClick={() => document.getElementById('user-input').click()}>
                                <input id="user-input" type="file" className="hidden" accept="image/*" onChange={onUserPhotoChange} />
                                <PersonIcon />
                                <span className="dropzone-text">Drop a full-body photo of yourself.</span>
                                <span className="tcm-dropzone-hint">
                                    Head-to-toe, face visible, stand straight. Please remove coats/heavy winter layers.
                                </span>
                                <span className="tcm-dropzone-hint">JPEG, JPG, and PNG formats, up to 5 MB</span>
                            </div>
                        )}
                        <button className="btn-secondary tcm-main-btn tcm-skip-btn" type="button" onClick={handleSkip} disabled={!canCreate || loading}>
                            Skip section and generate
                        </button>
                    </>
                )}

                {!validating && !showPairedPreview && hasItem && hasModel && validationFailed && (itemFailedPair || userFailedPair) && (
                    swapLikely ? (
                        /* Both photos failed — most likely they're swapped */
                        <div className="tcm-val-error-card">
                            <div className="tcm-val-error-swap-thumbs">
                                <div className="tcm-val-error-thumb-wrap">
                                    <span className="tcm-val-error-step-badge">Step 1</span>
                                    <img src={preview} alt="Uploaded item" className="tcm-val-error-thumb" />
                                </div>
                                <span className="tcm-val-error-swap-arrow" aria-hidden>⇄</span>
                                <div className="tcm-val-error-thumb-wrap">
                                    <span className="tcm-val-error-step-badge">Step 2</span>
                                    <img src={userPhotoPreview} alt="Uploaded photo" className="tcm-val-error-thumb" />
                                </div>
                            </div>
                            <p className="tcm-val-error-title">Your photos look swapped</p>
                            <p className="tcm-val-error-body">
                                Step 1 needs a <strong>garment photo</strong> (plain background, one item).<br />
                                Step 2 needs a <strong>full-body photo of you</strong> (head-to-toe).
                            </p>
                            <div className="tcm-val-error-actions">
                                <button className="btn-primary tcm-main-btn" type="button" onClick={onRemoveItem}>
                                    Replace clothing item
                                </button>
                                <button className="btn-secondary tcm-main-btn" type="button" onClick={onRemoveUserPhoto}>
                                    Replace your photo
                                </button>
                            </div>
                        </div>
                    ) : itemFailedPair ? (
                        /* Step 1 (clothing item) failed */
                        <div className="tcm-val-error-card">
                            <div className="tcm-val-error-thumb-wrap">
                                <span className="tcm-val-error-step-badge">Step 1 — Clothing Item</span>
                                <img src={preview} alt="Uploaded item" className="tcm-val-error-thumb" />
                            </div>
                            <p className="tcm-val-error-title">
                                {itemValidation?.item_message || "We couldn't identify a clothing item in this photo."}
                            </p>
                            <p className="tcm-val-error-body">
                                Use a photo of a <strong>single garment</strong> on a plain background with the full item visible.
                            </p>
                            <button className="btn-primary tcm-main-btn" type="button" onClick={onRemoveItem}>
                                Replace clothing item
                            </button>
                        </div>
                    ) : (
                        /* Step 2 (full-body photo) failed */
                        <div className="tcm-val-error-card">
                            <div className="tcm-val-error-thumb-wrap">
                                <span className="tcm-val-error-step-badge">Step 2 — Full-body Image</span>
                                <img src={userPhotoPreview} alt="Uploaded photo" className="tcm-val-error-thumb" />
                            </div>
                            <p className="tcm-val-error-title">
                                {userValidation?.user_message || "We couldn't verify this as a full-body photo."}
                            </p>
                            <p className="tcm-val-error-body">
                                Stand <strong>head-to-toe</strong>, face visible, on a clear background. Remove heavy coats or layers.
                            </p>
                            <button className="btn-primary tcm-main-btn" type="button" onClick={onRemoveUserPhoto}>
                                Replace your photo
                            </button>
                        </div>
                    )
                )}

                {showPairedPreview && (
                    <>
                        <div className="studio-images-side-by-side tcm-preview-grid">
                            <div className="studio-image-block tcm-preview-card">
                                <div className="studio-image-wrap">
                                    <img src={preview} alt="Your item" className="studio-image-img" />
                                </div>
                                <button type="button" className="upload-received-change tcm-change-btn" onClick={onRemoveItem}>
                                    <ChangeIcon /> Change
                                </button>
                            </div>
                            <div className="studio-image-block tcm-preview-card">
                                <div className="studio-image-wrap">
                                    <img src={userPhotoPreview} alt="You" className="studio-image-img" />
                                </div>
                                <button type="button" className="upload-received-change tcm-change-btn" onClick={onRemoveUserPhoto}>
                                    <ChangeIcon /> Change
                                </button>
                            </div>
                        </div>
                        <button className="btn-primary tcm-main-btn" onClick={runPipeline} disabled={loading}>
                            Create Your Look
                        </button>
                    </>
                )}

                {error && <div className="banner error" style={{ width: '100%', marginBottom: 0 }}>{error}</div>}
            </div>
        </section>
    );
}
